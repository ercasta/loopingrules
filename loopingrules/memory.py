"""`loopingrules.memory` -- short-term memory: promote selected changes out
of the transient change log and into ordinary, durable entities a later rule
can read.

`world.py` already records every applied write as a `Change` in a transient
log (`World.changes`), never saved and bounded only by `Loop(capacity=...)`.
That log is the world's short-term account of what HAPPENED, but it is not
memory: nothing in it survives the session, and a rule that consults it must
scan the whole window every tick. `docs/plan-memory.md` names the missing
half -- a PROMOTION rule that reads the transient log and deposits ordinary
durable entities, so "we already tried this" stays answerable after the
marker that recorded it was removed. This module is that half.

It lives in the engine, not in a pattern, because what it reads is an engine
primitive (`World.changes`) and this package imports nothing above it. Under
the attribute substrate (`docs/plan-attributes.md`, D8) each "component" is a
SHAPE an entity carries, tagged with a flag; and so they are saved, shared
and queried like any other world data. A promoted memory is a real size and
lifetime cost, named here rather than hidden:

* `memory` (flag) -- a singleton tag a domain deposits to OPT IN. Every rule
  below abstains until one exists.
* `memory_policy` (flag) + `max_entries`, `max_per_target`, `kinds` -- a
  singleton holding the rules' tunable surface. Nothing here hard-codes a
  threshold; both rules read this entity, which is what makes them
  calibratable. The DECLARED `@tunable` surface sits in
  `loopingrules_patterns.memory`, because the engine must not import
  `loopingrules_calibration`.
* `remembered` (flag) + `seq`, `tick`, `rule`, `kind`, `target`, `types` --
  its OWN entity per promoted change, keyed by the change's `seq`. A second
  entity per memory, rather than a growing list on one, so a single memory
  can be FORGOTTEN by destroying it: `analyze` understands `destroy(entity)`,
  but not `remove(entity, some_name)` on a queried entity.
* `memory_cursor` (flag) + `seq` -- the high-water mark: the last change
  `remember` has already looked at.

## Promotion, and what gets promoted

`remember` walks `w.changes(since=cursor)` -- the changes from BEFORE its own
tick (a rule never sees its own write) -- narrowed by `kinds`, and deposits a
`remembered` entity for each one, whose `types` are the ATTRIBUTE NAMES the
change's deltas mention. It skips its own writes (`_memory_write`). Without
that exclusion, remembering would be something to remember, and the rule
would run away.

## Forgetting

`forget` enforces the policy: no more than `max_entries` entries across the
whole trail, and no more than `max_per_target` remembering any one `target`
(both `0` means unbounded). It DESTROYS the over-quota entries, newest kept.
That is the "short" in short-term: what it drops is gone from the world.

## What this does not settle

* **Age-based decay.** Retention here is a COUNT, not a clock.
* **What is WORTH remembering.** `kinds` is a coarse filter.
* **Cross-world semantics.** What `share.py` means for a promoted memory --
  and for the `memory_cursor` -- is not decided; `save.py` restores it as
  ordinary data, cursor and all.
"""

from __future__ import annotations


MEMORY = "memory"
POLICY = "memory_policy"
REMEMBERED = "remembered"
CURSOR = "memory_cursor"

_POLICY_FIELDS = ("max_entries", "max_per_target", "kinds")
_REMEMBERED_FIELDS = ("seq", "tick", "rule", "kind", "target", "types")

DEFAULTS = {"max_entries": 64, "max_per_target": 0, "kinds": ()}


def _rule_name(fn) -> str:
    """`memory.remember` -- the name `Loop.rule` infers for `fn`, so this
    module can recognise its own writes in the change log."""
    return "%s.%s" % (fn.__module__.rsplit(".", 1)[-1], fn.__name__)


def policy_of(world) -> "dict":
    """The policy fields, or `None` if no `memory_policy` entity exists.
    Field names are LITERALS, not a loop over a tuple, so `analyze` can
    attribute them and the rules stay gate-able (see `analyze.py`)."""
    row = world.first("memory_policy")
    if row is None:
        return None
    entity = row[0]
    return {"max_entries": world.get(entity, "max_entries", 64),
            "max_per_target": world.get(entity, "max_per_target", 0),
            "kinds": world.get(entity, "kinds", [])}


def seeded(world) -> bool:
    """Whether this domain has opted in -- a `memory` marker exists."""
    return world.populated("memory")


def remember_field(world, entity, name):
    """One field off a `remembered` entity (the reader's convenience)."""
    return world.get(entity, name)


def _memory_write(world, change) -> bool:
    """Whether `change` is one of memory's own writes, which must never be
    promoted -- or remembering would remember itself and never settle.

    Three signals: the write was made by `remember`/`forget` (their `rule`
    name); one of its deltas names a `remembered`/`memory_cursor`/`memory`/
    `memory_policy`; or its TARGET is an entity tagged as one of those --
    which catches an install-time cursor/policy `set` whose delta names only
    an ordinary field (`seq`, `max_entries`) and so cannot be told from any
    other write by name alone.
    """
    if change.rule in (_rule_name(remember), _rule_name(forget)):
        return True
    if any(delta[0] in (REMEMBERED, CURSOR, MEMORY, POLICY)
           for delta in change.payload):
        return True
    if change.target is not None:
        target = world.entity(change.target)
        if (world.has(target, "remembered") or world.has(target, "memory_cursor")
                or world.has(target, "memory") or world.has(target, "memory_policy")):
            return True
    return False


def remember(w) -> None:
    """Promote every not-yet-remembered change into its own `remembered`
    entity, then advance the `memory_cursor` past what was examined.

    Reads the transient log only backwards -- `w.changes(since=...)`, which
    inside a rule never includes the current tick. Idempotent by
    construction: the cursor is monotonic. Abstains until a `memory` marker
    and a `memory_policy` both exist.
    """
    policy = policy_of(w)
    if policy is None or not seeded(w):
        return
    cursor_row = w.first("memory_cursor")
    since = w.get(cursor_row[0], "seq", -1) if cursor_row else -1
    tail = w.changes(since=since)
    for change in tail:
        if policy["kinds"] and change.kind not in policy["kinds"]:
            continue
        if _memory_write(w, change):
            continue
        entity = w.spawn()
        w.mark(entity, "remembered")
        w.set(entity, "seq", change.seq)
        w.set(entity, "tick", change.tick)
        w.set(entity, "rule", change.rule)
        w.set(entity, "kind", change.kind)
        w.set(entity, "target", change.target)
        w.set(entity, "types", sorted({delta[0] for delta in change.payload}))
    examined = [change.seq for change in tail if not _memory_write(w, change)]
    if examined:
        moved = max(examined)
        # The cursor move is memory's own write (its rule is `remember`), so
        # it is skipped in turn and the rule settles rather than chasing
        # itself.
        world_cursor = w.first("memory_cursor")
        if world_cursor is not None:
            w.set(world_cursor[0], "seq", moved)
        else:
            entity = w.spawn()
            w.mark(entity, "memory_cursor")
            w.set(entity, "seq", moved)


def forget(w) -> None:
    """Drop the `remembered` entries the `memory_policy` no longer keeps --
    newest kept -- by destroying their entities.

    Enforces `max_entries` across the whole trail and `max_per_target` for
    each `target` separately; both `0` means unbounded. Abstains until a
    `memory` marker and a `memory_policy` both exist.
    """
    policy = policy_of(w)
    if policy is None or not seeded(w):
        return
    entries = sorted(
        ((entity, w.get(entity, "seq", -1), w.get(entity, "target", -1))
         for entity, _ in w.each("remembered")),
        key=lambda row: row[1])
    doomed = set()
    if policy["max_entries"] and len(entries) > policy["max_entries"]:
        keep_from = len(entries) - policy["max_entries"]
        doomed.update(seq for _entity, seq, _target in entries[:keep_from])
    if policy["max_per_target"]:
        per_target = {}
        for _entity, seq, target in reversed(entries):
            per_target.setdefault(target, []).append(seq)
        for seqs in per_target.values():
            doomed.update(seqs[policy["max_per_target"]:])
    for entity, seq, _target in entries:
        if seq in doomed:
            w.destroy(entity)


def install(loop, policy=None) -> object:
    """Turn short-term memory on for `loop`: deposit the `memory` marker,
    seed a `memory_policy` (the fields given, or the defaults), move the
    `memory_cursor` past whatever is already in the log, and register
    `remember`/`forget`.

    `policy` is a plain dict of `max_entries`/`max_per_target`/`kinds`, or
    None for `DEFAULTS`. Idempotent about seeding: a marker or policy
    already present is left alone. Returns the loop.
    """
    world = loop.world
    if not world.populated("memory"):
        marker = world.spawn()
        world.mark(marker, "memory")
    if not world.populated("memory_policy"):
        fields = dict(DEFAULTS)
        fields.update(policy or {})
        entity = world.spawn()
        world.mark(entity, "memory_policy")
        world.set(entity, "max_entries", fields["max_entries"])
        world.set(entity, "max_per_target", fields["max_per_target"])
        world.set(entity, "kinds", list(fields["kinds"]))
    if not world.populated("memory_cursor"):
        entity = world.spawn()
        world.mark(entity, "memory_cursor")
        world.set(entity, "seq", -1)
        world.set(entity, "seq", world.changes()[-1].seq)
    loop.rule(remember)
    loop.rule(forget)
    return loop
