# Comparison: LoopingRules and SOAR

Where this substrate sits relative to **SOAR** (Laird, Newell and Rosenbloom,
1987) — a *cognitive architecture* built around the Problem Space
Computational Model: behavior is search over states via operators toward a
goal. It is written to place the repo, not to endorse it: SOAR is the
best-known production system with a *decision procedure*, and this repo
recently grew a recognize–act cycle of its own
([the scheduler](plan-scheduler.md)), so the two are worth separating
carefully. Read alongside [Modeling](modeling.md), which names the
production-system ancestors this repo *does* claim (OPS5/KEE/ART, the
blackboard) — SOAR is not one of them, deliberately.

## The short version

Both are **production systems over a shared working memory** in which rules
communicate only through that memory. Where they part is the spine:

- SOAR's default cycle **always ends in a decision** — one operator selected
  per cycle — and an **impasse → substate** recursion when it cannot.
- This repo's default loop **fires every rule to a fixpoint** and has *no*
  decision procedure; the operator-selection machinery exists only as an
  **opt-in, rule-level** extension.

The recognize–act cycle here is therefore closer to **OPS5/CLIPS conflict
resolution plus a numeric preference layer** than to SOAR's decision cycle.
Three of SOAR's defining mechanisms are **absent as mechanisms**: unique
symbolic preference-based selection, automatic impasse/subgoaling, and
chunking. Conversely this repo has three things SOAR does not: a reified rule
set with a runtime control channel, deterministic save/replay world-cloning,
and a strict "generate offline, gate, freeze; learn nothing at run time"
discipline.

## Mapping

| Dimension | SOAR | LoopingRules | Where |
|---|---|---|---|
| Working memory | WME graph: id–attr–value triples | ECS: entities + entity-attached components (relations are int refs; edges declared in the catalog) | `world.py`, [Core concepts](concepts.md), [The forge](plan-forge.md) |
| Procedural knowledge | productions (opaque rules) | Python functions of `World`, **reified as `RuleCard` data** | `reflect.py` |
| Match | **RETE**, incremental, all instantiations | re-run the query each tick; gate is `analyze`'s *over-approximation*; exact match only in the `q0` probe | `analyze.py`, `loopingrules_forge/q0.py` |
| Default cycle | mandatory decision procedure: input → elaboration → decision → application → output | **every rule, in order, to a fixpoint** (`revision` stops moving) | `loop.py` |
| Conflict resolution | symbolic **preferences** (`acceptable`/`best`/`better`/`worst`) → one unique selection | registration order / `priority`; or numeric score `argmax` (opt-in `schedule=True`) | `loop.py`, [The scheduler](plan-scheduler.md) |
| Stalling | **impasse → substate → recursive subgoaling** | budget breaker + `hot`; a recorded **`Doubt`** (no recursion) | `loop.py`, `plan-scheduler.md` |
| Learning | **chunking** (in-cycle) + reinforcement learning | memory promotion; forge/GP + calibration **offline**, frozen before run time | `memory.py`, `loopingrules_forge/`, [The forge](plan-forge.md) |
| Reflection | not native (rules are a fixed knowledge base) | **`RuleCard`/`RuleControl`** — rules over rules, one level | `reflect.py`, [Reflection](plan-reflection.md) |
| Termination | guaranteed elaboration quiescence + one decision | no proof; the budget is "a circuit breaker, not a proof" | `loop.py` |
| Model / persistence | none native | `save`/`load` JSONL + deterministic `replay` = world cloning | `save.py`, [Modeling](modeling.md) |

## Where they line up

- **Communication only through memory.** SOAR productions coordinate via
  working memory; here, "rules never call each other — the only channel
  between them is what they deposit in the `World`" (`PRINCIPLES.md`). Both
  are stigmergic in that sense.
- **A recognize–act shape.** `plan-scheduler.md` reframes a rule as
  `LHS → RHS`, an **activation** as `(rule, binding)`, and the loop as
  **match → resolve → act**. Resolution is `argmax` over a per-activation
  score, with a conflict-resolution discipline borrowed in name from the
  production-system tradition (refraction, recency, specificity). `q0` proves
  the mechanism on three claims and `Loop(schedule=True)` carries the
  rule-level half into the engine.

## Where they diverge

**1. Fixpoint vs. decision.** SOAR's core loop always ends in an operator
decision. This repo's default (`Loop.tick`) does the opposite: it fires
every rule, in a fixed order, and repeats until a whole pass changes nothing
— SOAR's *elaboration phase* running forever, with nothing on top. The
decision machinery is **opt-in** and **rule-level**: the engine "cannot see a
rule's bindings," so *which part* of the blackboard to act on is unbuilt
design (`plan-scheduler.md`).

**2. Preferences vs. score; ordering as a first-class property.** SOAR
resolves among operators with typed symbolic preferences and a decision
procedure, and its productions are **order-independent**. Here, order is
authored and load-bearing — registration order, `priority=`, and runtime
`RuleControl` — and the scheduler resolves with a **numeric `argmax` and a
deterministic tie-break**, described in the plan as "CLIPS's
recency/specificity made dynamic" and "XCS's prediction array." Conflict
*sets* are dropped entirely (one activation per tick) because "the loop is a
fixpoint, so a fair serialization reaches the same fixpoint."

**3. The defining gap: no impasse → substate.** SOAR detects a
tie/no-change/conflict impasse and *automatically* creates a substate,
recursing. This repo hits the analogous "no controller has an opinion" case
and **falls back to a frozen default score and records a `Doubt` as ordinary
world data** — observable, promotable, a training signal for the forge, but
**not a subgoal**. Nothing recursively reasons about the stuck state; the
answer to oscillation is a budget breaker and idempotence, not subgoaling.
That is also why termination differs: SOAR's elaboration is monotone and
provably quiesces, while rules here may `detach`/`destroy` (a tag is a
*fluent*, not a class membership), so the loop needs a hard tick cap.

**4. Learning: offline-frozen vs. in-cycle chunking.** SOAR learns inside
problem solving — chunking compiles a subgoal's result into a faster
production, plus RL on preferences. This repo inverts that by
**locked decision 8**: "nothing learned sits in the runtime core's decision
path." Structure is generated offline (the forge: an LM or the GP `evolve`),
gated, and **frozen before tuning**; only *values* are fitted by search;
runtime control may only **subtract or reorder**. There is **no chunking
equivalent**. `memory.py` is closer to an episodic trace — a transient change
log promoted into durable `Remembered` components, count-rather-than-clock
retention.

**5. Matching.** SOAR uses RETE — incremental, delta-driven rematching. Here
matching re-scans each tick behind an existence-only per-rule gate derived
from the AST, which the repo openly names as *not* "what a real Rete network
would do." Exact matching exists only as the `q0` probe over an IR.

## Where this repo has something SOAR does not

- **Reflection / metacognition** (`reflect.py`). Each rule is reified into
  the blackboard as a `RuleCard` (content hash, name, derived reads/writes),
  and a rule may write `RuleControl`, which the loop reads each tick to
  disable or reprioritize a rule **without editing it** — "rules over rules,"
  a self-model and metacognitive loop (the docs cite Global Workspace Theory
  and reflective towers). SOAR productions cannot introspect or schedule each
  other this way. Bounded on purpose: one level, subtract/reorder only, a
  frozen rule set.
- **Forkable world as model.** `save` + deterministic `replay` gives **world
  cloning** — a plan is search over forked futures (`modeling.md`). SOAR has
  no native snapshot/fork semantics.
- **Determinism as a gate.** Same input → same output in a fixed order is
  load-bearing here, enforced through the calibration kit's `signature`, not
  merely assumed as in SOAR.

## Bottom line

Architecturally this is a **blackboard/ECS production substrate** that has
grown a **SOAR-flavored recognize–act scheduler**, but the scheduler is
closer to **OPS5/CLIPS conflict resolution with a numeric preference layer**
than to SOAR's decision cycle. The three things that most define SOAR are
present in *shape* (a probe and an opt-in engine path) but not in
*substance*: unique symbolic preference-based operator selection, automatic
impasse → substate subgoaling, and chunking. SOAR is goal-directed operator
search; this is goal-free stigmergic fixpoint computation that borrows the
recognize–act vocabulary without adopting the cognitive commitments — and
adds a reflective control channel, world-cloning, and an offline/frozen
learning discipline that SOAR lacks.

## What this does not settle

- **Not a benchmark.** This compares architectures on paper, not behavior;
  no task is run in both, and no claim about comparative capability is made
  or implied.
- **SOAR keeps moving.** SOAR 9 adds semantic and episodic memory,
  reinforcement learning and mental imagery; the mapping above describes the
  classic decision cycle and chunking, and parts of the "SOAR does not"
  column may be narrower than the current system.
- **The repo's side is partly design.** The scheduler is a probe plus a
  rule-level engine change; activation-level control, aging, conflict sets
  and the IR-native rules are unbuilt (`plan-scheduler.md`). "Absent" above
  sometimes means "not yet built," not "rejected" — impasse/subgoaling in
  particular is not argued against anywhere in the repo, only unbuilt.
- **The spine question is open.** Whether this repo *should* grow a decision
  procedure and an impasse mechanism, or stay a fixpoint substrate with
  opt-in scheduling, is not settled here or in `plan-scheduler.md`.
