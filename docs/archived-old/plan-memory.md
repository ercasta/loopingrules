# D1 — Memory and the change log

Phase 2. Non-breaking: no change to the rule API, no change to any example's
rules, no rewrite of the trajectory model. This is the piece that makes
history-aware rules, midway checks, provenance, and sharper calibration
signatures possible.

**Status: built.** `World` records every applied write as a `Change` (`seq`,
`tick`, `rule`, `kind`, `target`, `payload`) and exposes it through
`World.changes(...)` / `World.recent(n)` / `World.clear_changes()`; the log is
transient, never saved, and bounded only by `Loop(capacity=...)`. `Loop.tick`
stamps each record with the running rule and the tick, so a rule reading the
log sees only changes from before its own tick. `analyze` attributes
`changes(changed=SomeType)` as a read, so a memory-reading rule keeps its
gate. The calibration kit's `replay` fills `Trace.changes` from it (the
signature is unchanged -- the log is a separate field). Tests:
`tests/test_changes.py`. Retention is `Loop(capacity=...)`; the `signature`
deliberately does NOT include the log (settled: plateaus keep their meaning,
the log is a separate field).

**Promotion is built too** (2026-10-30): `loopingrules.memory` ships
`Memory`/`MemoryPolicy`/`Remembered`/`MemoryCursor`, the `remember`/`forget`
rules, and `install`, with the declared `@tunable` surface in
`loopingrules_patterns.memory` (the engine cannot import calibration). Tests:
`tests/test_memory.py`. No `examples/` domain installs it for real yet -- the
mechanism is proven against bare entities in tests, not an independently-
authored domain, and that is real, separate work.

## Problem

Today the loop can only tell *that* a rule fired, not *what it did*.
`Loop.tick()` compares `world.revision` before and after each rule and returns
the rule's name (`loop.py`). That is enough to settle, and it is what
`examples/tuning.py` hashes into a behavioural `signature` — but it discards
the actual mutations:

- A rule cannot condition on **what happened** earlier, only on **what is**
  true now. `examples/party.py`'s dedup *by existence* is the current idiom; a
  rule cannot ask "was this already attempted, even though the marker was
  removed?"
- A scorer/check cannot read the blackboard **midway** with any fidelity: it
  sees the world's state per tick, but not the deltas between ticks.
- Provenance is absent: given a component, nothing says which rule attached it
  and on which tick (structural credit assignment, which `docs/tuning.md`
  names as this substrate's model, has no surface).
- The behavioural `signature` is coarse: two settings that fire the same rules
  but deposit different values collapse together.

The simplification removed exactly the machinery for this: `loop.py` says
"tracing was removed along with `World.tracing`/`changes`", and `Loop.__init__`
still carries a dead `trace: bool = False`. This doc revives it as a
first-class, queryable log rather than a debug trace.

## Decision

Instrument `World`'s six write methods — `spawn`, `attach`, `replace`,
`detach`, `remove`, `destroy` — to append an attributed record to an
**ordered, append-only change log owned by the loop**. The world stays
dependency-free; the loop sets the acting rule around each call.

This is deliberately *not* the "rules return a descriptor" model. `loop.py`'s
"why a rule may touch the world directly" argued that model down for a
different reason (contract enforcement), and the one thing it cost —
a `Pending` placeholder for an entity `spawn()` has not made real yet — does
not arise here, because writes still happen immediately. See "Descriptors,"
below, for the separate decision.

## Design

### The record

A `Change` is plain data, `json.dumps`-able per `concepts.md`:

```
Change(seq:int, tick:int, rule:str|None, kind:str, target:int|None, payload)
```

- `kind` in {`spawn`, `attach`, `replace`, `detach`, `remove`, `destroy`}.
- `target` is the entity id the change touched (`None` for `spawn` before the
  id exists — the id is in `payload`).
- `payload` holds component values (spawn/attach/replace: the components;
  detach/remove: the kinds/component); another entity is its plain int id, as
  `World.attach` already normalises (`concepts.md`).
- `rule`/`tick` come from the loop; `None` for changes made outside a rule's
  turn (`install` seeding, a slash command's own writes).

**Only changes that actually happened are logged.** `World.attach` already
dedups and only moves `revision` on a real change (`concepts.md`,
"Revision"); the log records exactly those. A rule re-attaching an equal value
logs nothing and does not "fire" — the existing idempotence discipline, now
observable.

### Attribution

The loop already owns calling rules (`Loop.tick`). Around each call it sets
`world._actor = (tick, rule_name)` (cleared after), and `World` reads that when
appending. This is a one-field coupling from loop to world, no import either
way, and it keeps the world's "depends on nothing but the standard library"
property (`architecture.md`).

### The read API

The log is **loop-side and transient** (locked decision). Rules read it
through `World`, backed by the loop's list:

```
w.changes(since=None, by=None, kind=None, changed=None, target=None) -> list[Change]
w.recent(n) -> list[Change]
```

- `changed=SomeComponent` filters to changes that touched that type.
- `since` takes a `seq` or a tick; **default is "strictly before the current
  tick"** so a rule never sees its own write in the same tick (termination
  discipline; see below).
- No mutation: the API returns copies/read-only views.

### `analyze`

A rule calling `w.changes(...)` uses its world parameter in a way outside
`analyze.py`'s dialect. Two options, both acceptable:

1. **Preferred:** add the memory-read helpers to `analyze.py`'s named
   exceptions (it already special-cases `reply`/`propose`/`arbitrate`/
   `census`), attributing a synthetic read (e.g. a `MemoryReads` marker) plus
   whichever `changed=` type is passed, so the rule keeps a correct dormancy
   gate.
2. **Fallback:** leave it `Opaque`. The rule runs every tick (correct, just
   un-optimised), which is the same safe fallback every opaque rule gets.

Do (1) for the shipped helpers; it is the difference between memory-aware
rules being cheap and being called every tick.

### Termination

History-aware rules are a new way to loop. Discipline:

- Memory reads default to pre-tick changes, so a rule cannot see (and react
  to) its own write in the same tick.
- History-aware rules keep the **same idempotence obligation** every other
  rule has: recompute, attach an equal value, move nothing, settle.
- The budget remains the circuit breaker (`loop.py`); a rule that reacts to a
  change it keeps generating shows up as `hot`, which is already a named
  failure and already penalised by a scorer.

### The trace object and the signature

The loop exposes the log as part of a **trace** (defined in D2). For
calibration, `examples/tuning.py`'s `_signature` can stop hashing only `(fired,
final world)` and hash `(changes, fired, final world)` — a strictly sharper
behavioural-equivalence class (`docs/tuning.md`'s "tune to a behavioural
equivalence class, not a unique numeric solution"). Keep both: the trace
source is pluggable (D3) so the kit runs today and sharpens when this lands.

## Promotion: how anything becomes durable

Locked decision: the log is **not** written to `save`. Long-term memory enters
persistence only through authored rules:

```
@loop.rule
def promote_lesson(w):
    for change in w.changes(kind="detach", changed=Attempted):
        w.attach(lesson_entity, Remembered(change.target_id, change.seq))
```

- Promotion reads the transient log and attaches **ordinary durable
  components**. The durable memory is then indistinguishable from any other
  world data: queryable, `save`-able, shareable.
- Promotion is a **decision**, so it is calibratable: *what* to promote,
  *how much*, *when* can be knobs (D3), and promotion rules can be tuned
  offline like any other rule.
- Rules never read a "durable memory API" — they read data another rule chose
  to make. The log is only ever the short-term look-back window. This keeps
  `analyze`'s story clean and keeps `save` honest.

Shipped (2026-10-30) as exactly this shape: `loopingrules.memory`'s
`remember` reads `w.changes(since=MemoryCursor.seq)` and spawns a durable
`Remembered` per qualifying change; `forget` destroys the entries past a
tuned `MemoryPolicy`. The retention policy this doc left open was chosen as
a COUNT (`max_entries`/`max_per_target`), not a tick window — see the
module's own "what this does not settle".

Cost named, not hidden: promoted memory lands in `save`, so it has a size and
lifetime cost and it changes replay. Each durable artifact should declare what
it remembers and why.

## What this does not settle

- **Retention.** The log grows unboundedly over a long session. A cap, a ring
  buffer, or a "keep last N ticks plus everything promoted" policy is needed
  and is not decided here.
- **Descriptors.** Deferred (locked). `loop.py`'s recorded objection stands;
  the independent merits (atomicity of a rule's effect, a validation/policy
  boundary before changes land, and the bridge to a rules-as-data authoring
  surface per `review.md`) are real and deserve their own doc (Phase 6).
- **Serialisation of the log.** Whether a trace is itself `save`-able, and in
  what format, is D2's question.
- **Cross-world semantics.** What `share.py` means for provenance and for
  promoted memory.
- **Non-rule writes.** The log includes install-time and command-time changes
  with `rule=None`; whether that is noise or signal for scoring is D2's
  question.

## Open questions

1. Log retention policy: bounded ring, tick window, or promotion-only?
2. Should `spawn` payload carry the new id so cross-references within one
   rule resolve post hoc?
3. Should `changes()` be analyzable (option 1) for every shipped helper, or
   only for the ones the stdlib's patterns actually use?
4. Does provenance extend to *which channel* an input came from, for scoring?
