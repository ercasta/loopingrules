# The scheduler: activations, the recognize–act cycle, and resolution

Status: **the first probe is built** (`loopingrules_forge/q0.py`, pinned by
`tests/test_forge_q0.py`); everything beyond it is design. This is the
scheduler half of the control channel. D7 (`plan-reflection.md`) gave the
substrate a way to control a *rule* (`RuleControl`); this doc records where the
discussion landed on *what* a controller controls, *how* ambiguity among rules
is resolved, and *what* keeps that resolution from starving. It **extends D7**
and depends on the IR-native decision (locked 13, `plan-forge.md`/D5) for its
first precondition: total analysis.

`Q0` proves the MECHANISM on three claims and nothing more (see *Results*);
it does not touch the engine. The rest of this doc is still untested prose,
and the repo has deleted untested prose before (`DECISION_PATTERNS.md`,
`cdf98d6`) — so what `Q0` does not pin is named as design, not as a claim.

## The problem, stated once

D7 controls a *rule*: `RuleControl(hash, …)` is read by the loop at the top of
each tick and may disable or reorder one rule. But a rule is a **production** —
a left-hand side (a condition over the blackboard) and a right-hand side (the
effects) — and one rule may match *many* parts of the blackboard at once.
`items.consider` matches every projected candidate; `cards.decide_buy` matches
every affordable listing. When a rule matches several entities, D7's per-rule
control cannot say *which part to act on*; it can only turn the whole rule on
or off. Choosing wisely among the matches is exactly the leverage
`plan-islands.md` describes ("the branch factor at an entity is the number of
bridges whose reads are satisfied… the space of askable questions is finite
and authored; only the answers are calibrated") — and D7 does not do it.

Second, **"would fire" is not currently decidable.** `analyze`'s derived gate
is "the rule's read-set is populated" — a cheap *over-approximation* of firing.
A rule whose gate is open may still write nothing (abstain), so an
eligibility-based doubt would fire forever. Deciding "would fire" needs the
rule's **condition as data**, evaluated without side effects — which is the
LHS/RHS reshape and IR-native (locked 13).

## The shape

### Rules are productions, and the cycle is the recognize–act cycle

A rule becomes `LHS → RHS`: a **condition** (a pure predicate over the world)
and an **effect**. The loop is then the production system's own cycle —
**match → conflict resolution → act** — the ancestor `modeling.md` names
("frames plus production rules = the expert system, OPS5/KEE/ART — the classic
ancestor of a blackboard"). OPS5 resolves conflict with static strategies
(priority, specificity, recency, refraction); here the order is recomputed
per tick from the world.

### The unit is the activation, not the rule

One rule applied to one binding of its LHS is an **activation**: `(rule,
binding)`. Conflict is resolved among activations. An activation's identity
extends the content-hash discipline already in the substrate:

```
activation_key = ir_hash(rule_datum, canonical_binding)
```

### The three-phase tick

1. **Match.** Evaluate every rule's LHS over the world; materialise the
   activations as **derived world data** (a component, like `RuleCard`), so a
   controller can *read* them. Match is a generic interpreter over the rules'
   LHS data, not hand-maintained.
2. **Resolve.** The control network reads the activations (plus `RuleCard` and
   `Remembered`) and writes `RuleControl`.
3. **Act.** Fire the chosen activations; re-match (writes gate rules in and
   out) and repeat to a fixpoint.

### `RuleControl` has two scopes

D7's `RuleControl` is per-rule and durable. Activation control is per-binding
and **transient** (a binding can vanish with an entity). One shape carries
both, and the scope is the binding:

```
RuleControl(hash, binding=None, enabled=True, priority=0)
# binding=None  -> the whole rule (D7's meaning; the durable default)
# binding=(3,7) -> one activation (this tick; transient)
```

Never key a durable component on a transient binding, or it dangles.

### Scoring activations

Resolution is `argmax` over a per-activation **score**:

- **pure and total** — a function of `(rule, binding, world)`, analyzable like
  everything else (a read of the change log is a read);
- **recomputed each tick, not stored** — a derived value, so it cannot drift;
  only the *effect* persists, and it changes the next score;
- **a total order** — a deterministic tie-break, so equal scores are
  reproducible;
- **frozen** — the scorer is a control-layer rule (authored, or generated and
  gated); its weights are `Knob`s fitted offline. Nothing learned runs in the
  runtime path (locked 8).

This is one idea wearing three familiar hats: CLIPS's recency/specificity made
dynamic; XCS's prediction array, with *covering* as the no-match default; and
the repo's own `checks`, at activation grain.

### The conflict-resolution discipline (starvation and livelock)

Choosing one activation per tick can starve the others, and re-choosing the
same one forever never reaches a fixpoint. The guards below are **D4's own
list** (hysteresis, rate limit, bounds, idempotence) applied at activation
grain, not new machinery:

1. **Refract by consumption** *(strongest)*. The effect *consumes* its
   trigger — a seeded marker the LHS reads `without=`, so the activation can
   never match again. "Don't fire twice is consuming a component" (TODO's own
   conclusion); starvation is impossible by construction.
2. **Refract by marker.** For repeatable activations: act, then attach
   `Fired`/`Seen` (or promote to `Remembered`) and let the score read it and
   drop. This is the substrate-native form of refraction — *change a component
   so the next evaluation scores differently* — pure stigmergy, no separate
   fairness bookkeeping.
3. **Aging / fairness.** `score += age_weight · (ticks since this activation
   last fired)`, age from `Remembered`/`LastFired`; `age_weight` is a knob. A
   starved activation eventually outranks a repeat winner.
4. **Deterministic tie-break** — a stable key (activation hash, then name) so
   `argmax` is well-defined and reproducible.
5. **Hysteresis + rate limit** (D4, verbatim): change only past a `margin`; at
   most one control change per N ticks.
6. **Bounds.** Keep the score finite (knob `low`/`high`) so ordering is stable.
7. **A termination measure.** It settles only if repeated argmax-firing drives
   the match set toward empty; state that as an obligation; the budget breaker
   stays the backstop.
8. **Novelty fallback.** No activation scores above threshold → the **frozen
   default score** (specificity/priority), and **record the doubt** (below).

Consumption and aging are the two poles; most domains want one of them plus
(4).

### Stigmergy survives; no hazard graph is needed

The loop is a fixpoint and stigmergy works across ticks (`RuleControl` lands
next tick; `changes` lags by a tick). Two cases collapse:

- rules that **settle** (monotone/confluent): order does not change the final
  world, so serialising to one activation per tick — *fairly* — reaches the
  same fixpoint; it costs ticks, not results;
- rules that **do not settle** (non-monotone/conflicting): order *is* semantic,
  and that is exactly when arbitration is wanted.

So a static hazard graph would buy **speed, not correctness**, and is not
needed. The cost is ticks (≈ rule applications) and a fatter trace (a decision
per doubt, `plan-adaptation.md`).

### The control layer level-stops

The control network is itself rules. It is **not** itself arbitrated — one
level of reflection, as D7 fixes it — so its own conflicts resolve
deterministically (one `RuleControl` per key; last in `each()` order wins).
Otherwise the cycle recurses.

### Novelty: a doubt is durable world data

When no controller covers the situation, the loop falls back to the **frozen
default score** (the offline-calibrated schedule — D4's own "baseline and
pull-back") and records a **`Doubt`** as an ordinary component. It is then
observable, promotable (`memory`), and a **training signal for the forge**: a
runtime doubt is the cousin of `plan-forge.md`'s compile-time *gap*, and the
generator grows a controller for it offline, gated and frozen.

## The forced build order

Each step is a probe that pins "no ambiguity ⇒ identical `signature`" and
"settles":

1. **IR-native rules** (LHS/RHS, total analysis) — locked 13; requires the LHS
   as data. *Nothing downstream is sound without it.*
2. **Activations as derived data** — a generic matcher over the rules' LHS.
3. **The recognize–act cycle + activation-level `RuleControl`.**
4. **Novelty fallback + `Doubt`.**

## Results

**Q0 (probe built: `loopingrules_forge/q0.py`, pinned by
`tests/test_forge_q0.py`).** A walking skeleton on three claims, taking the
engine-lighter path (the cycle is a standalone scheduler over a `World`, not a
change to `loop.py`):

- **Match is exact, not the gate.** `cards.decide_buy`'s guard is re-expressed
  as LHS data; its match set equals the set of listings the real rule buys, and
  is *narrower* than `analyze`'s gate (the tags the rule reads). The reshape
  widens no escape: the guard is total, `decide_buy` still analyzes clean, and
  the declared verbatim-helper set is unchanged.
- **No ambiguity ⇒ identical `signature`.** With at most one activation
  eligible per tick, the cycle reproduces the run-all signature exactly (every
  rule, all its matches, per tick) — the scheduler is a conservative
  extension.
- **Starvation, refraction, novelty.** Several activations eligible every
  tick, resolved by the deterministic DEFAULT score, starve all but one
  (`(6, 0)`); a controller whose effect moves its own score (`refraction`,
  OPS5's move as a component) restores fairness (`(3, 3)`) and still settles.
  The default fallback is the novelty path: no controller had an opinion ⇒ the
  frozen score, and a `Doubt` deposited as ordinary world data.

What it does NOT do: it does not touch the engine; it does not partition
activations into conflict sets (it picks ONE activation per tick, globally);
its RHS is a small effect IR, not full `m0`; and no-op activations are not
handled (every effect here moves the world).

## What this does not settle

- **The degenerate binding**: a rule with no binding (a singleton condition)
  is its own activation; that case must be defined.
- **Where the refraction marker goes** when a binding names several entities —
  argued to be the *subject*, but unprobed.
- **Who materialises activations** — the engine core, or a generic matcher
  rule over `RuleCard` LHS data (the stigmergic, engine-lighter option). The
  largest unbuilt decision; the engine stays frozen until a probe earns the
  change (`_tick_order` is the precedent for how carefully).
- **Fairness/stability** — the discipline above *reduces* starvation and
  oscillation; it does not prove them away. `plan-adaptation.md` offers no
  stability guarantee, and neither does this.
- **Cost** — ticks, matching cost each tick, and trace fattening; all bounded
  by the fixpoint, none measured.
- **Multi-controller interaction** and multi-knob coupling (D7/D4's own open
  questions), now at activation grain.
- **The number** — this extends D7; whether it becomes its own D-number is
  undecided.

## Open questions

1. Is the engine's tick three phases, or is *match* a rule and only *act* the
   engine's job? (D7's own "loop core vs a `scheduler` module" question,
   restated.)
2. Is the unit of `argmax` one activation, or a **maximal non-conflicting set**
   (so independent activations co-fire and only true contention is arbitrated)?
   The hazard graph was dropped for *correctness* — but it is the thing that
   would recover *speed* here.
3. Does the score persist (for the trace) or only the decision?
4. When a chosen activation no-ops (writes an equal value), is it dropped and
   re-chosen within the tick, or deferred a tick?

## The next probes

`Q0` proves the mechanism. The next steps, each still a probe first, are the
ones the build order names and `Q0` deliberately stopped short of:

- **Materialise activations** as derived world data (a generic matcher over
  `RuleCard` LHS data, or the engine core — the open decision above).
- **Activation-level `RuleControl` in the loop**, i.e. the *engine* change
  `Q0` did not make: resolve within the tick.
- **Conflict sets**, if the tick cost of one-activation-per-tick warrants the
  hazard graph the plan dropped.
- **Aging** (the second anti-starvation pole) and **no-op activations**.
