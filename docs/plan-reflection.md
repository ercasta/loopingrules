# D7 — Reflection: rules as data, and the control channel

Status: the two probes are **built** (`loopingrules_reflect/{r0,r1}.py`, pinned
by `tests/test_reflect_r0.py` and `tests/test_reflect_r1.py`), and the one
engine primitive they need ships with them (`loopingrules.reflect`:
`RuleCard`, `RuleControl`, `reify`, `rule_hash`, plus the `_tick_order` read
that makes a control real). Nothing is folded in beyond that primitive; the
IR is **not** yet moved into the engine. This doc states the design the
probes test, names the departure it takes, and ends with what it does not
settle — the same posture as D1-D6.

## The problem, stated once

Two things the substrate could not do, and the discussion that produced them:

1. **Control a rule without editing it.** The stigmergic way to "activate" a
   building block is to attach a component its rule reads — but that only
   works if the rule was *authored* reading that component. A controller that
   must edit every rule it controls is not a controller; it is a refactor.
2. **Let one rule reason over another.** Rules are functions; `World` stores
   data, never callables (`world._lower` refuses a Python object). So no rule
   could read another rule's structure, and "rules over rules" was impossible
   in principle, not merely unbuilt.

Both are answered by the same move: **put rules into the blackboard as
data**, and let the loop — which already knows every rule — be the one
reader.

## Design 1 — the control channel

A rule's identity is a **content hash** (`reflect.rule_hash`; provisional,
see below). `reflect.reify(loop)` deposits one `RuleCard` per registered rule:
its `hash`, its `name`, and its `reads`/`writes` (component class names),
derived by `analyze` — so a card cannot drift from the rule it describes.
`reflect.RuleControl(hash, enabled, priority)` is the shape the **loop** reads,
at the top of each tick:

- `enabled=False` ⇒ the matching rule is dropped from the order and never
  called. `priority` ⇒ it runs in a different place.

A **controller** is then just a rule — a `priority>0` rule that reads
`RuleCard` (what each rule does) and, optionally, `memory.Remembered` (what
each rule has done) and writes `RuleControl`. It is the D4 move ("an adapter
is just a rule whose output is a knob") with the schedule as the knob.

**This is a second channel, and it is named as one.** `PRINCIPLES.md` says
"the only channel between them is what gets deposited into the shared
`World`." A control is still deposited as a component and read by an
oblivious reader — the loop — so it stays stigmergic in the load-bearing
sense; but the reader is now the loop, not each rule, and the substrate has a
control shell it did not have before. That is the departure, stated plainly.

**Precedence is the soundness rule: `RuleControl` may only SUBTRACT or
REORDER.** `analyze`'s derived gate still decides dormancy. An enabled rule
whose gate is closed stays skipped; no controller can make a rule act on
reads it does not have. `r0`'s `test_enabling_a_rule_whose_gate_is_closed_...`
pins exactly this.

**The lag is one tick**, and it is the same discipline `world.changes`
already enforces: a control written during a tick is read at the *start* of a
tick, so it acts on the next one. It settles for the same reason everything
else does — a controller that keeps re-emitting an *equal* control moves
nothing.

## Design 2 — rules as data (IR-native)

The control channel works with Python rules today (a card is derived by
`analyze`). The stronger version — the one that makes reflection uniform, and
EA safe — is to make the **rule's structure itself a value**, i.e. an
operational semantics over a closed node set, with Python as a rendering.

`plan-forge.md` chose the opposite: "the DSL is a front-end; the Python rule
is the backend," and M0's reshape concluded "the IR IS a Python-subset AST."
D7 moves the ground truth to the IR, for one reason that the plan under-sold:

> `analyze` on Python is a **partial** function — it raises `Opaque` because
> Python is open. Analysis over a **closed** IR is a **total** function.

Totality is what makes an EA trustworthy: a frozen operator set means every
mutation has a complete, static account of what it reads and writes. It is
also what makes reflection uniform: a rule over rule-data is the ordinary
operator machinery, not a bespoke introspection API.

**Homoiconicity buys reflection, and that is stated as its engineering claim,
not more.** Rules-as-data is what lets a controller reference rules, the
forge translate them, and `modeling.md`'s "the model is the world's rules…
structure derived from the code" become literal — the model *is* the rule
datum. It is the same reason XCS works (classifiers are data a GA mutates in
the action set). **The two probes test the two halves that are cheap to
falsify and load-bearing to build on:**

- **R0 (runtime).** A controller reading `Remembered` + `RuleCard` tames a
  loop that alone is `hot`, with the controlled rule's source untouched; and
  an *oscillating* controller stays `hot`, caught by the existing budget.
- **R1 (static).** `reads`/`writes`/`negated_reads`/`destroys` over the forge
  IR agree with `analyze` on the lowered Python for all twelve `cards` rules —
  total, with one named edge (below).

### The three layers, kept apart

The self-reference hazard is exactly where homoiconicity bites, so the
authority is split:

| Layer | What | Mutable | Authority |
|---|---|---|---|
| Rule set as data | `RuleCard`, the IR | inspectable, hashable, **frozen** | authored / generated |
| Scheduler state | `RuleControl` | **online** (a controller writes it) | the controller |
| Rule creation | new/rewritten rules | **offline only** | the forge + gates + freeze |

A runtime controller **selects among a frozen set**; it never adds, removes
or rewrites a rule. That is program synthesis, and it is locked decision 8
("nothing learned sits in the runtime core's decision path") restated.

## Reflection, not consciousness

The intuition this doc is built on — *if the agent's memory tracks the rules
that fired and the rules are inspectable, you can make rules over memory +
rules* — is correct, and D7 builds its testable half. What it yields is a
**self-model** and a **metacognitive loop**: the system can represent its own
processing and act on that representation. That is the property the useful
literature is about — blackboard architectures are the computational analogue
of **Global Workspace Theory** (Baars; Dehaene and Changeux), and "rules over
rules" is **reflective towers** (Smith, *Procedural Reflection in Programming
Languages*, 3-Lisp, 1982; Friedman and Wand, *Reification: Reflection without
Metaphysics*, 1984; Maude's rewriting-logic reflection, which *is* homoiconic
execution). `docs/study-guide.md` carries the reading list for both.

Whether to call that a form of consciousness is a definitional move, not
something a substrate can settle, and the invariants here actively constrain
the strong reading ("values are primitives only; a type system over values
*is* an ontology"; no learned structure in the runtime path). D7 builds it as
reflection, and calls it that, so every claim stays checkable: the system
**represents itself at runtime and changes itself only offline.**

## The self-reference hazard, named

A controller that reads its own firing and writes `RuleControl` is a feedback
loop — the liar/oscillator. `plan-islands.md` already names the location
("monotone vs. revisable promotion… where flicker lives"); D4 names the
failure mode (oscillation → `hot`). Idempotence + settle + the budget breaker
are the safety net, **not a stability proof**: `r0.flip_flop` is a controller
whose own action flips the evidence it acts on, and it stays `hot` — which is
what must happen, and is pinned. A production controller needs monotonicity,
hysteresis or a rate limit (D4's own list), none of which D7 adds.

## Results

**R0.** The controlled run settles (`ticks=6`), the uncontrolled and
oscillating runs are `hot` after the budget, and the disabled rule's own
source contains no `RuleControl` — control is data, verified by reading the
world, not by argument.

**R1.** `12/12` rules: IR analysis equals `analyze`. One finding, and it is
the concession ledger showing up in *analysis*: `hear_status`'s reads live in
the verbatim helper `_status_text` (raw Python, the M0 escape for
lexing/formatting), so they cannot be recovered from the IR alone. The walker
therefore **requires** a verbatim helper to DECLARE its reads (`external=`,
derived once by `analyze`) and **refuses** otherwise — "a closed semantics
makes analysis total; it does not make the edge disappear, only forced and
named."

## What this does not settle

- **The hash.** `rule_hash` hashes the rule's SOURCE, so identical-source
  rules share a hash (intended for a DSL, a named hazard for same-source
  closures). The target is a hash of the IR datum + component schema +
  operator version — a per-rule projection of `m2.Frozen.version` — not
  built.
- **Where the IR lives.** IR-native means the IR should become a frozen
  engine core (the deleted `circuits.py` precedent), with `analyze`
  re-targeted onto it and `analyze`-on-Python kept as an audit. D7 does not
  move it; R1 proves the seam first.
- **One control per hash, one controller per rule.** Multi-controller
  interaction and multi-knob coupling are unprobed (D4's own open question).
- **Credit assignment.** How a controller learns *which* rule to move is the
  calibration kit's scoring plus the forge's search, not this doc.
- **The engine grew.** `_tick_order` now reads a component. It is opt-in (no
  control exists until a rule writes one) and `PRINCIPLES.md` calls the
  engine frozen; a core change that turns out to be wrong ripples outward.
  The mitigation is the probes and the four gates, not the prose.

## Open questions

1. Does the scheduler read live in the loop core, or in a `scheduler` module
   the loop imports — the closer to `circuits.py`'s own separation?
2. Is a `RuleCard` one component per rule, or a single declared catalog the
   loop owns (closer to the forge's derived/declared/presented split)?
3. Does a controller address a rule by hash alone, or by a declared *name*
   that a hash backs (so a human can read the control state)?
4. Do runtime controllers belong in `loopingrules_patterns` as a shipped
   *shape* once a second domain depends on one — the standing promotion bar?
