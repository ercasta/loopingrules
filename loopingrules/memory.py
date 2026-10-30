"""`loopingrules.memory` -- short-term memory: promote selected changes out
of the transient change log and into ordinary, durable components a later
rule can read.

`world.py` already records every applied write as a `Change` in a transient
log (`World.changes`), never saved and bounded only by `Loop(capacity=...)`.
That log is the world's short-term account of what HAPPENED, but it is not
memory: nothing in it survives the session, and a rule that consults it must
scan the whole window every tick. `docs/plan-memory.md` names the missing
half -- a PROMOTION rule that reads the transient log and attaches ordinary
durable components, so "we already tried this" stays answerable after the
marker that recorded it was removed. This module is that half.

It lives in the engine, not in a pattern, because what it reads is an engine
primitive (`World.changes`) and this package imports nothing above it. The
components it ships are all ORDINARY -- and so they are saved, shared and
queried like any other world data; a promoted memory is a real size and
lifetime cost, named here rather than hidden:

* `Memory()` -- a singleton a domain spawns to OPT IN. Every rule below
  abstains until one exists, the same abstention `judge.flag_too_risky`
  takes when no tolerance has been seeded.
* `MemoryPolicy(max_entries, max_per_target, kinds)` -- a singleton holding
  the rules' tunable surface. Nothing here hard-codes a threshold; both
  rules read this component, which is what makes them calibratable. The
  DECLARED `@tunable` surface sits in `loopingrules_patterns.memory`,
  because the engine must not import `loopingrules_calibration`.
* `Remembered(seq, tick, rule, kind, target, types)` -- its OWN entity per
  promoted change, keyed by the change's `seq`. A second entity per memory,
  rather than a growing list on one, so a single memory can be FORGOTTEN by
  destroying it: `analyze` understands `destroy(entity)`, but not
  `remove(entity, some_queried_component)`.
* `MemoryCursor(seq)` -- the high-water mark: the last change `remember` has
  already looked at. Without it, `forget` would be undone every tick -- a
  change the log still holds would be re-remembered the moment its entry was
  dropped -- and the two rules would fight forever.

## Promotion, and what gets promoted

`remember` walks `w.changes(since=cursor.seq)` -- the changes from BEFORE
its own tick (a rule never sees its own write; `world.py`'s termination
discipline), narrowed by `MemoryPolicy.kinds` -- and spawns a `Remembered`
for each one. It skips its own writes (`_memory_write`): a change the
`remember`/`forget` rules themselves made, or one whose payload names a
`Remembered`/`MemoryCursor`. Without that exclusion, remembering would be
something to remember, and the rule would run away. Install-time seeding sits
behind the cursor `install()` writes, so the world a domain starts from is
not replayed as history.

## Forgetting

`forget` enforces the policy: no more than `max_entries` entries across the
whole trail, and no more than `max_per_target` remembering any one `target`
(both `0` means unbounded). It DESTROYS the over-quota entries, newest kept.
That is the "short" in short-term: what it drops is gone from the world, not
merely hidden from a view.

## What this does not settle

* **Age-based decay.** Retention here is a COUNT, not a clock. `docs/
  plan-memory.md` leaves the retention policy open, and a rule is given no
  public handle on the current tick to expire against; a count is
  deterministic and needs none. A tick window may want one later.
* **What is WORTH remembering.** `kinds` is a coarse filter. There is no
  notion of importance or novelty, so a chatty rule can still spend the
  budget on trivia. A domain that wants more can project its own component
  and filter on it before these rules run.
* **Cross-world semantics.** What `share.py` means for a promoted memory --
  and for the `MemoryCursor` that decides what is already known -- is not
  decided; `save.py` restores it as ordinary data, cursor and all.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Memory:
    """A domain's opt-in marker: spawn one and the rules here start
    promoting changes into `Remembered` entities; without one they touch
    nothing."""


@dataclass(frozen=True)
class MemoryPolicy:
    """The memory rules' tunable surface, as one singleton component.

    `max_entries` -- how many `Remembered` entries to keep across the whole
    trail, newest first; `0` for unbounded. `max_per_target` -- how many to
    keep remembering any ONE `target` entity; `0` for no per-target cap.
    `kinds` -- which change kinds to admit (`"spawn"`, `"attach"`,
    `"replace"`, `"detach"`, `"remove"`, `"destroy"`, `"changed"`,
    `"purge"`); `()` admits every kind.
    """

    max_entries: int = 64
    max_per_target: int = 0
    kinds: tuple = ()


@dataclass(frozen=True)
class Remembered:
    """One promoted change, as a durable component on its own entity.

    `seq` is the change's own `Change.seq` and the identity a caller keys
    on; `tick`, `rule`, `kind` and `target` are copied straight from the
    change; `types` are the NAMES of the component classes its payload
    mentioned. A `spawn`'s payload is empty by construction, so its `types`
    is `()`, and the components it went on to carry arrive as their own
    `attach` changes -- read a change by its `kind` before trusting `types`
    to describe it.
    """

    seq: int
    tick: int
    rule: object
    kind: str
    target: object
    types: tuple = ()


@dataclass(frozen=True)
class MemoryCursor:
    """The last change `remember` has already looked at -- see the module
    note. Its own entity, so the rule that advances it can `replace` it
    without disturbing anything else."""

    seq: int


def _rule_name(fn) -> str:
    """`memory.remember` -- the name `Loop.rule` infers for `fn`, so this
    module can recognise its own writes in the change log."""
    return "%s.%s" % (fn.__module__.rsplit(".", 1)[-1], fn.__name__)


def _memory_write(change) -> bool:
    """Whether `change` is one of memory's own writes, which must never be
    promoted -- or remembering would remember itself and never settle.

    Two signals, deliberately state-independent: the write was made by
    `remember`/`forget` (their `rule` name in the log), or its payload names
    a `Remembered`/`MemoryCursor` (a detach/destroy of one, or a cursor
    `replace`). A `Remembered` entity's own SPAWN has an empty payload by
    `World.spawn`'s own record, and its entity may already have been
    forgotten by the time a later tick looks -- so it is caught by the rule
    name, not by asking whether its target still carries anything.
    """
    if change.rule in (_rule_name(remember), _rule_name(forget)):
        return True
    return any(isinstance(payload, (Remembered, MemoryCursor))
               for payload in change.payload)


def remember(w) -> None:
    """Promote every not-yet-remembered change into its own `Remembered`
    entity, then advance the `MemoryCursor` past what was examined.

    Reads the transient log only backwards -- `w.changes(since=...)`, which
    inside a rule never includes the current tick -- so this rule can never
    react to its own write. Idempotent by construction: the cursor is
    monotonic, so a change is examined once, and a promoted one is a plain
    component value another tick's `attach` would have deduped anyway.

    Abstains -- touches nothing -- until a `Memory` and a `MemoryPolicy`
    both exist.
    """
    policy = w.the(MemoryPolicy)
    if policy is None or not w.populated(Memory):
        return
    cursor_row = w.first(MemoryCursor)
    since = cursor_row[1].seq if cursor_row is not None else -1
    tail = w.changes(since=since)
    for change in tail:
        if policy.kinds and change.kind not in policy.kinds:
            continue
        if _memory_write(change):
            continue
        w.spawn(Remembered(
            seq=change.seq, tick=change.tick, rule=change.rule,
            kind=change.kind, target=change.target,
            types=tuple(sorted(type(payload).__name__
                               for payload in change.payload))))
    # Advance only past changes that are NOT ours: setting the cursor to a
    # cursor-write's own seq would make the next tick see that write, write
    # again, and never settle. With no non-memory change in the tail, the
    # cursor stays put and this rule goes dormant.
    examined = [change.seq for change in tail if not _memory_write(change)]
    if examined:
        moved = max(examined)
        if cursor_row is not None:
            w.replace(cursor_row[0], MemoryCursor(moved))
        else:
            w.spawn(MemoryCursor(moved))


def forget(w) -> None:
    """Drop the `Remembered` entries the `MemoryPolicy` no longer keeps --
    newest kept -- by destroying their entities.

    Enforces `max_entries` across the whole trail and `max_per_target` for
    each `target` separately; both `0` means unbounded. Abstains until a
    `Memory` and a `MemoryPolicy` both exist.
    """
    policy = w.the(MemoryPolicy)
    if policy is None or not w.populated(Memory):
        return
    entries = sorted(w.each(Remembered), key=lambda row: row[1].seq)
    doomed = set()
    if policy.max_entries and len(entries) > policy.max_entries:
        keep_from = len(entries) - policy.max_entries
        doomed.update(entry.seq for _entity, entry in entries[:keep_from])
    if policy.max_per_target:
        per_target = {}
        for _entity, entry in reversed(entries):
            per_target.setdefault(entry.target, []).append(entry.seq)
        for seqs in per_target.values():
            doomed.update(seqs[policy.max_per_target:])
    for entity, entry in entries:
        if entry.seq in doomed:
            w.destroy(entity)


def install(loop, policy=None) -> object:
    """Turn short-term memory on for `loop`: spawn the `Memory` marker, seed
    a `MemoryPolicy` (the one given, or the default), set the `MemoryCursor`
    past whatever is already in the log, and register `remember`/`forget`.

    Idempotent about seeding: a marker or policy already present is left
    alone, so a restored world keeps its tuned policy and a domain may seed
    its own before calling this. The cursor is seeded after its OWN spawn
    record, so install-time seeding -- including the cursor's -- is never
    replayed as history. Returns the loop.
    """
    world = loop.world
    if not world.populated(Memory):
        world.spawn(Memory())
    if not world.populated(MemoryPolicy):
        world.spawn(policy if policy is not None else MemoryPolicy())
    if not world.populated(MemoryCursor):
        # Spawn first, then move the cursor past the spawn's OWN record: a
        # `spawn` logs an empty-payload record `remember` could not tell
        # from a domain write, so the seed must sit after it. The `replace`
        # that does so is memory's own (its payload names `MemoryCursor`)
        # and is skipped in turn.
        world.spawn(MemoryCursor(-1))
        cursor_entity, _cursor = world.first(MemoryCursor)
        world.replace(cursor_entity, MemoryCursor(world.changes()[-1].seq))
    loop.rule(remember)
    loop.rule(forget)
    return loop
