# D9 — The stigmergic control network: grown scoring and control rules

Status: **design only.** This doc extends D7 (`plan-reflection.md`, the control
channel) and the [scheduler](plan-scheduler.md) (activations and resolution).
It records the direction in discussion, and — per the repo's posture — what it
does not settle. There is no probe for the *network* half yet; the pieces it
builds on are built (D7's `RuleControl`, the scheduler's `q0` probe and the
rule-level `Loop(schedule=True)`), and the fog is named.

## The problem, stated once

D7 controls a **rule**: `RuleControl(hash, enabled, priority)` is read by the
loop, which may drop or reorder one rule. The scheduler (extends D7) controls an
**activation**: it resolves `(rule, binding)` by an `argmax` over a per-
activation **score**, and records a `Doubt` when nothing covers the situation.

Both are one **decision**, made in one place, by one scorer. What neither does
is let the training process grow a **network**:

- **many scoring rules**, not one scorer, that score the *applications* of
  rules (an application = an activation `(rule, binding)`), and
- **control rules** — rules whose effect is to set **control attributes**,
  opaque identifiers that carry no domain meaning and exist only to steer,

wired so that **one attribute-set steers the next application**, which scores
and sets another attribute, and so on — the trajectory altered in **multiple
steps**, not by a single argmax. The intent is that a scoring rule can be
**shared**: like the upper levels of a decision tree, one decision *cuts out a
whole branch* of downstream rules, and the downstream scorers are reused by
every case that reaches them.

## The shape

### The control layer is rules, like everything else

The control layer is **not** a new kind of object. It is ordinary rules over
ordinary attributes — the discipline `PRINCIPLES.md` states ("the only channel
between rules is what they deposit in the `World`"), applied to control. Three
roles, one substrate:

| Role | What it does | Example |
|---|---|---|
| **Domain rule** | the work being controlled: reads domain attributes, writes domain attributes | `cards.decide_buy` |
| **Scoring rule** | reads an *application* (an activation) and writes a score, or a control attribute derived from it | "this candidate's `Risk` is high → set `route=hold`" |
| **Control rule** | reads control attributes and writes more control attributes (or `RuleControl`) | "if `route=hold` and `budget` low → `route=defer`" |

Nothing calls anything. A scoring rule deposits a control attribute; a control
rule reads it; the loop resolves the next application against what is now in
the world. That *is* stigmergy, at control grain.

### Opaque control attributes

A control attribute's **name and value are opaque**: `route=hold`, `mode=3`,
`gate=a1`. They mean nothing to any domain rule and nothing outside the network
— **only the network assigns and reads them**. Opacity is the point, not an
accident:

- it makes the network **searchable** — the generator grows structure over an
  alphabet it does not have to interpret, the way XCS mutates classifier
  conditions over an action set, and the way a decision tree's internal node is
  just an id until the data gives it meaning;
- it keeps the *meaning* discovered (by the search, from the checks) rather than
  declared, which is the "derive, don't declare" posture at control grain;
- it keeps control attributes out of the domain's semantic vocabulary, so the
  domain's own attributes stay the semantic ones (`PRINCIPLES.md`: semantics
  lives in the name; here, semantics lives in the *domain* name).

Control attributes are ordinary attributes under the [attribute substrate](plan-attributes.md)
(D8) — which is why the network needs no new storage.

### Multi-step trajectories

Because a control attribute is world state and the loop runs to a fixpoint,
setting one **steers later applications**. The trajectory is altered in steps:

```
application a1 scores -> control rule sets route=hold
  -> application a2 (which reads route) resolves differently -> sets mode=3
    -> application a3 (which reads mode) ... -> the domain effect differs
```

Under D7 the control lands on the next tick; under the scheduler the loop is
three phases per tick and control lands *within* the tick. Either way the chain
of control rules unfolds against a fixpoint, so "multi-step" is a sequence of
ordinary rule applications, not a new interpreter.

### Sharing: the decision-tree reading

This is the load-bearing claim and the reason to build a *network* rather than
another flat scorer. In a decision tree an **upper split removes whole branches
at once** — one test makes every downstream node inside the surviving branch
shared. Here:

- a **scoring rule high in the network** writes a control attribute; every
  application that reads it is routed at once — the split;
- the **scoring/control rules below it are shared** across all the cases that
  arrive — reused, not re-decided;
- the generator therefore searches *factorized* control, and a control decision
  pays for itself across a subtree rather than once.

This is the control-layer form of the reuse the islands doc (D6) argues for at
the domain layer, and of *automatically defined functions* / library learning in
the study guide: a shared split is an abstraction the search discovered, not one
an author anticipated.

### How it relates to the scheduler

The scheduler's `argmax` over activations is the **degenerate, one-step case**:
one scoring rule, no control attributes, one decision. D9 generalises it —
many scoring rules, chained through control attributes, over multiple steps,
with reuse across subtrees. D7's `RuleControl` remains the *effect* a control
rule may write (it can still only subtract or reorder a domain rule); the
network is what *decides* which control to write, and it decides in steps.

## Credit assignment — the crux

The hard question the network raises, and the one the study guide already points
at: **which scoring rule gets credit** for a final outcome? A deep network has
many scorers on the path to a trajectory, and a maze solved (or a world settled
wrongly) says little about which split helped. This is exactly the problem
**XCS** solves for classifier systems — *fitness is accuracy, not reward*, and
the genetic algorithm acts only inside the action set that matched the current
state, with Q-learning-style updates assigning reward back through the
population. The repo's own material lines up:

- `World.changes` is "exactly the firing context XCS needs" (`study-guide.md`);
- the scheduler's **`Doubt`** is the no-match default (XCS's **covering**) and a
  training signal for the forge;
- the per-activation **score** is D7/scheduler's prediction array.

Credit assignment is named here as the crux and left to the generator
(below); the doc does not pretend a scalar fitness over a whole trajectory is
enough.

## Growing the network — the algorithm is open

The generator slot is locked decision 12 ("one grammar, many generators") and
the forge already has one generator: `loopingrules_forge.evolve`, GP over the
IR that grows **one** controller's condition. Growing a **network** is the
natural next shape, and the honest state is: **the algorithm is not chosen
yet.** The candidates the study guide already maps:

| Candidate | What it contributes | Where |
|---|---|---|
| **GP / Grammatical Evolution** over the IR | generation of well-formed rules; the grammar is the attribute schema | `evolve`, `study-guide.md` |
| **XCS** | per-rule credit assignment by accuracy; covering as the novelty default | study guide, hardest-reading slot |
| **MAP-Elites / novelty search** | a *population* of diverse networks, not one — the control-layer analogue of an island library | study guide |
| **Library learning (Stitch/LILO, DreamCoder)** | discover the **shared splits** — the reusable abstractions the decision-tree reading is about | study guide |
| **ILP** | induce rules over a declared, typed predicate set; the "rules over a declared predicate set" mirror | study guide |

The sketching bet, stated so it is checkable: **GP/GE proposes the network,
XCS-style accuracy assigns the credit, and library learning compresses shared
splits into reusable abstractions.** Whether that three-part shape holds, or one
of the pieces dominates, is exactly what the first probe (the knowledge-maze
benchmark, D10) is for. Choosing the algorithm now would be the untested prose
this repo has deleted before (`DECISION_PATTERNS.md`, `cdf98d6`).

## Discipline (what must not erode)

- **One level of reflection.** The network is rules over rules; it is **not**
  itself arbitrated by a further level ("the control layer level-stops",
  `plan-scheduler.md`). Its own conflicts resolve deterministically (one control
  attribute per key), or the cycle recurses.
- **The network selects; it does not rewrite.** It may subtract or reorder
  domain rules (`RuleControl`) and set control attributes; it never adds,
  removes or rewrites a domain rule. That is locked decision 8 ("nothing learned
  sits in the runtime core's decision path") and locked decision 13, unchanged.
- **Frozen before it runs.** The network is grown and gated **offline** and
  frozen, like every other structure (D5's freeze-before-tune). Runtime control
  moves values and control attributes; the network's *structure* is fixed for
  the run.
- **A `Doubt` is a first-class output.** No scoring rule covers a situation →
  the frozen default and a recorded `Doubt`, which is the offline training
  signal (grow a control rule for it) — the runtime cousin of the forge's
  compile-time *gap*.
- **Determinism stays a gate.** The generated network is analyzed (total, over
  the IR), gated, and replay-verified like everything else.

## What this does not settle

- **The algorithm**, above — deliberately open, to be chosen by a probe.
- **Credit assignment** across a multi-step network — XCS is the candidate, not
  a solution.
- **The stake in the ground vs the domain.** How much of a domain's behavior a
  network may control before it is "the program" — the schedule? the goal? a
  domain rule's own effect? — is unstated.
- **Interaction with D7's one control per hash.** Many scoring rules may want
  to write the same control attribute; the discipline says last-in-`each()`-order
  wins, which is deterministic but not argued as right.
- **Stability.** A network whose own control attributes feed back into its own
  scoring is the self-reference hazard (`plan-reflection.md`), larger: a chain
  of such rules can oscillate. D4's guards (hysteresis, rate limit, bounds)
  reduce it; nothing here proves it away.
- **Cost.** Multi-step control multiplies rule applications, and a naive
  network is a search over a large space; whether the decision-tree sharing
  actually buys sample efficiency is the empirical claim, unmeasured.

## Open questions

1. Is a **scoring rule** allowed to write a control attribute directly, or does
   it only write a score and a separate control rule maps scores to attributes?
   (Direct is simpler; separated keeps scoring pure — D2's sandbox discipline.)
2. Are control attributes **one namespace** shared by the whole network, or
   scoped (per rule, per activation, per maze)?
3. Does the generator search a **flat population of scoring rules** plus a
   wiring, or a **tree/graph genome** directly? (The decision-tree reading
   argues for the graph.)
4. Is a **shared split** a first-class artifact the search can name and reuse
   (an ADF / a library entry), or does sharing emerge only from what the
   generated rules happen to read?
5. Where does a grown network **live** — a `patterns` shape, a forge artifact
   with provenance, or engine data (the scheduler's "who materialises
   activations" question, restated for control)?
6. Does the network replace the scheduler's single scorer, or sit above it (a
   network of scorers feeding the scheduler's `argmax`)?
