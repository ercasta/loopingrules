# Tuning: examples-driven parameter search over a blackboard

Recap of a design discussion, and the plan that came out of it. Started
from `review.md`'s Tuning note and `examples/cards.py`; nothing here is
built yet.

## The idea

Provide examples of desired / undesired trading (or an automatic scoring
mechanism where the domain already has ground truth), and let a search
"tune" the parameter components the rules read. Changing a threshold makes
a rule deposit a different tag, which changes which downstream rule's
query matches, which changes the trajectory from that point on. The
`cards` domain is already the worked example: `RiskProfile` and
`RiskTolerance` are components, not literals, and `Wanted` /
`Affordable` / `FairPriced` / `TooRisky` are the gates.

This is not a new mechanism so much as naming and searching one that is
half-built:

- **Knobs are already components the rules read.**
  `cards.RiskProfile(max_spend_per_trade, min_cash_reserve, max_premium)`
  and `judge.RiskTolerance(max_level)` are seeded by `install` and read by
  `tag_affordable` / `tag_fair_priced` / `tag_risk_level` /
  `flag_too_risky`. The contrast is `shopping.HORIZON_DAYS`, a module
  constant and therefore *not* tunable. The design rule that follows:
  **a tunable rule never hard-codes its threshold; it reads a component.**
- **The trajectory is already observable.** `Loop.tick()` returns the
  names of the rules that changed something; `run()` returns
  `Settled(ticks, hot)`. A trajectory is `[(tick, [fired])]` plus a final
  world snapshot — cheap, and reproducible because tick order, `each()`
  ordering and the budget are all deterministic.
- **The artifact of tuning is a saved world.** Parameters are components,
  so a tuned result is `save.dump()` output, not generated code. Nothing
  arbitrary enters the engine.

## What is genuinely new

1. **A declared tunable surface.** A generic tuner cannot discover which
   components are knobs, or their ranges, by convention or AST. The domain
   must declare it, the way `install` already seeds it — explicitly, never
   inferred.
2. **A scenario / episode.** An initial world (seed parameters) plus a
   scripted list of inputs (`Said`s) to replay.
3. **A scorer.** `score(final_world, trace, scenario) -> float`, living
   *outside* the engine as a harness function — the same standing a tool
   or channel has. "Desired/undesired examples" and "automatic scoring"
   are two implementations of one interface.

## Two hazards

**The objective is step-shaped.** A threshold crossing flips a tag and
switches branches, so the score as a function of the knobs is
piecewise-constant with plateaus and cliffs. Gradient methods are
meaningless; use derivative-free search and *report* plateaus. Many
distinct settings produce the same trajectory, so tune to a behavioral
equivalence class (hash the trajectory), not a unique numeric solution.

**Local calibration fights global behavior.** `review.md` says each
scoring rule is tuned in isolation on its own dataset, but a locally
calibrated threshold does not guarantee the composed run behaves: the
distribution of `Risk.level` inputs met in a real trajectory is not the
calibration set (a change to `max_premium` changes which listings survive
to produce future `Risk` values and future purse room). This is covariate
shift, and the theory below *predicts* it. The remedy is not a global
objective but narrow bridges and honest per-island datasets.

Also: penalize `hot` / non-settling runs in the scorer, and assert
reproducibility (run twice, same trajectory hash) before trusting a score.

Two refinements: **tune values, never structure** (adding/removing rules is
program synthesis, not tuning — `README.md` is explicit that the closed
catalog was built *for* a future search but none is built yet); and
**prefer ranking examples (A ≻ B) over absolute labels**, which the
substrate already speaks via `decide.Option` / `Score` / `Winner` and
`Risk.level`'s free ranking.

## The theory this rests on

Complex reasoning is not a single faculty; it is applied in **islands**
(domains, each with its own rules), connected by **bridges**, with a few
**content-free operators** (enumerate, choose) reused both inside islands
and on bridges. Operators generalize; semantics do not. This is the No
Free Lunch theorem read cognitively: generalization is only ever relative
to a prior, and a prior is a domain.

The architecture already embodies it:

- **Physics + operators** = the engine. `World` / `Loop` know nothing of
  cards or shopping; `each` / `first` / `the` / `all` are enumerate,
  `pick_winner` is choose. These are frozen — never tuned.
- **Islands** = domains, with their own components and decision
  boundaries.
- **Bridges** = the tiny shared vocabulary a *second* island is forced to
  agree on: `judge.Risk` / `RiskTolerance`, `decide.Option` / `Score`.
  Bridges are asymmetric and carry meaning opaquely: `Risk(level, reason)`
  lets an island project its own fact onto the bridge's shape while the
  bridge reads only `level` and never interprets `reason`. Built only when
  two islands actually collide — "grow it only at the rule that actually
  collides."

"Complex reasoning is an illusion" is worth sharpening: the depth is real
and emergent (no single rule authored `decide_buy`'s composed behavior);
only the **attribution** to a central reasoner is the illusion.

## Relationship to ML

Not reinforcement learning in any load-bearing sense:

- **No action space.** Nothing selects among actions; a threshold moves a
  decision boundary on a projected feature. This is *direct / parameterized
  policy search* — practically controller tuning, not policy learning.
- **Fully known, deterministic model.** RL earns its keep when the model
  is unknown and the state is perceptual. Here you can roll out the exact
  world cheaply, so classical search and black-box optimization dominate.
- **Sparse terminal reward**, but with a crisp symbolic transcript, so
  structural intermediate credit is available that RL would have to learn.
- **Determinism vs. differentiability is a real fork.** A stochastic
  (probabilistic) tag attach would smooth the objective and permit
  gradients, but breaks the reproducibility this repo treats as
  load-bearing. So: black-box search, not gradients.
- **Factored / relational state.** This is a relational MDP; `analyze.
  component_map` is essentially the static predicate-dependency graph an
  RMDP learner would try to recover.
- **Credit assignment is structural, not temporal**, and tags behave like
  option-termination conditions (options / hierarchical RL).

Closest formal cousins, ranked: simulation-based / black-box optimization
of a parameterized controller; supervised threshold calibration (a
single-threshold classifier — `flag_too_risky` is exactly this, i.e.
operating-point selection on an ROC/cost curve); imitation / preference
learning to *define* the objective (IRL, ranking), then black-box search to
hit it; stigmergy / ACO and MARL-with-independent-learners for the
emergent-control picture; classical production / expert systems, where
tuning thresholds was a known manual pain — automating it from examples is
the genuinely underexplored part.

The honest name is **grey-box parameter tuning of a deterministic,
hand-authored, stigmergic controller** — *learning to configure*, not
*learning to act*.

## The sample-efficiency question

The scaling camp's bet is not brute force; it is that a sufficiently broad
generic prior over sequences subsumes depth of domain-specific priors,
given data (Solomonoff / compression: to predict a corpus well you must
model the world that generated it). The strongest form of the user's
critique is not "mere correlation, no world model" — implicit world models
in sequence predictors are real — but **observational vs. interventional
structure**: the model learns the shadow the world casts on text, not
`P(world | do(intervention))`.

The reframe that lands: the pretraining corpus is the **fossilized output
of human island-building** (programs, proofs, textbooks, disambiguated
pages). Scaling did not discover a domain-free engine; it ate the island
library and distilled it. Mechanistic interpretability is consistent with
this — MLP layers as key-value memories (an island library) over a thin
layer of general operators (induction heads) — so the real dispute is
narrower than "islands vs. a general engine": it is **authored islands vs.
learned islands, over a shared, thin operator layer.**

## Plan: a measurement instrument

All of it in `examples/`, none in the engine — the same bar `judge` /
`decide` waited at.

1. **Declared tunable surface** on `cards.install`: the three
   `RiskProfile` fields plus `RiskTolerance.max_level`, with ranges.
2. **Scenario + deterministic replay**: fresh `Loop` → `install` → feed
   inputs → `run()` → capture `[(tick, fired)]` + final world. Assert
   determinism by hashing the trajectory.
3. **Scorer**: automatic terms first (goal met? overpaid? reserve
   respected?) plus a few labeled good/bad scenarios. Held-out, and
   identical across every system under test — the scorer is itself a prior.
4. **Tuner**: on four scalars, grid *exhaustively* — no optimizer
   confound on the parameter axis.
5. **Learning-curve harness**: for N = 1, 2, 5, 10, …, tune, evaluate on
   held-out scenarios, repeat over random draws of which examples; report
   mean ± variance, not just the mean.
6. **De novo baseline**: a real learner over raw world features and the
   same labels (decision tree / logistic / k-NN), no `Risk`, no tags, no
   composition.

### Experiment 1 — bridge transfer (build first)

`cards` and `shopping` share `judge.Risk` / `RiskTolerance` while
projecting different things onto it (resource exhaustion vs. time
pressure). Calibrate `RiskTolerance` from N cards-labeled examples and
evaluate on shopping's urgency labels, as a function of N. Compare:
(a) bridge threshold calibrated on cards, tested on shopping; (b) bridge
threshold calibrated in-domain on shopping; (c) an island-local knob
(`RiskProfile`) calibrated on cards and tested on shopping.

- Prediction (islands don't transfer, bridges do): (a) ≈ (b) ≫ (c) = chance.
- A hit quantifies "a bridge buys sample efficiency across islands"; a miss
  falsifies the strongest positive claim in the theory.
- Cheapest real result, because the shared bridge already exists.

### Experiment 2 — structure ablation

Authored tag architecture (structure given, four knobs tuned) vs. the de
novo learner, same labels. Held-out competence vs. N. Measure the data cost
of *discovering* the composition that authorship provided for free.
Expected honestly: on `cards` the gap may be small — which is itself a
useful result (it says `cards` is too small to be evidence).

### Experiment 3 — new island (novelty crux)

Add a deliberately absent behavior (selling) as a new island. Measure what
each system needs to acquire it: authored = a couple of new rules plus a
knob; de novo = more labels, and whether it can even represent the new
decision without a new projection. This is where the theory and the scaling
camp actually disagree.

### To be evidence, not anecdote

Run the same instrument across a ladder of increasing structural complexity
— `cards` → `shopping` (two islands, one bridge) → `trip` (an option/score
bridge plus search) → a domain needing counting/recursion — and measure how
examples-to-competence scales with the number of islands and bridges,
structured vs. unstructured. A single point is an anecdote; **the slope is
the argument.**

## Status

### Built

- `examples/tuning.py` — the instrument: `Knob` (a declared tunable field
  on a singleton component), `Scenario`, `replay` (deterministic, records
  the per-tick firing trace and a behavioural `signature`), `read_knobs` /
  `write_knobs` (refuse when the component was never seeded), `grid`, and
  an optimizer-free `search`.
- `examples/bridge_transfer.py` — Experiment 1, using the real domains.
- `examples/market.py` — rung 1 of the ladder: a richer trading island with
  **selling**, a **second bridge** (`examples.decide`'s `Option`/`Score` /
  `Winner`, ranking rival listings), and a **cross-entity** condition
  (`market.Strands`). `cards` stays rung 0, untouched.
- `examples/quorum.py` — the **counting** rung: a motion passes iff
  `#{for votes} >= Quorum.needed`, a count over a set of unknown size that
  no per-row condition can flatten.
- `examples/ablation.py` — Experiment 2: an observation harness (the
  authored buy verdict, computed on a scoring-only loop), a small stdlib
  axis-aligned decision tree with a balanced-accuracy learning curve,
  a controlled **depth-dial** probe (`slope`), a **relevance sweep**
  (`relevance`) that dials the cross-entity condition's arity, and two more
  ladder rungs — `ranking` on `trip`'s bridge and `counting` on `quorum`.
- `loopingrules/analyze.analyze` is now memoized by function object (safe:
  no caller mutates the returned `Analysis`). Rule registration repeated
  thousands of times by a replay harness parses each rule once — the
  ablation suite dropped from ~84s to ~5s, the whole suite to ~10s.
- Tests: `test_examples_tuning.py`, `test_examples_bridge.py`,
  `test_examples_market.py`, `test_examples_quorum.py`,
  `test_examples_ablation.py` — `229 passing`.

### What Experiment 1 found

The original sketch ("bridge vs. raw features") is **degenerate** for these
two islands: each island's `Risk.level` *is* its normalized raw feature
(cards `price/room`, shopping `1 - days/HORIZON`), so a threshold on the
bridge and one on the raw ratio are the same boundary. The meaningful split
is **form vs. value**, which is also what the islands/operators theory
predicts:

- **Form transfers at zero cost.** `cards`/`shopping` import the same
  `Risk` / `RiskTolerance` / `TooRisky` / `flag_too_risky` *objects* from
  `examples.judge` — identity, not same-shaped copies. No new rules, no new
  examples (`new_rules_or_data == 0`).
- **Value does not transfer across a policy gap.** A threshold fit on
  cards lands at `0.625` (cards' policy is `0.6`); scored against shopping
  it is `1.0` while the two policies agree (`delta` in `0..0.1`) and falls
  symmetrically to `0.625` at `|delta| = 0.4`. One value serves two
  policies only while they agree — so the bridge shares the *shape*, while
  the *threshold* is island policy.
- **Sample efficiency is easy on the bridge axis.** One parameter, so the
  learning curve is flat early: mean held-out accuracy `0.75` at `N=1`,
  `0.93` at `N=5`, `0.99` at `N=21`. Exact number matters less than its
  shape (a step up, then flat) — it is the baseline the harder experiments
  will be measured against.
- **No shared raw axis exists.** `raw_axes()` shows cards' `(price, room)`
  and shopping's `(days,)` do not intersect: without a bridge there is no
  axis to transfer along at all. That, not merely convenience, is the
  bridge's job.

### What Experiment 2 found

Target: the authored **buy verdict**, computed on a scoring-only loop (the
acting rules left out, so nothing is bought). Learner: a plain axis-aligned
decision tree. Three representations of the same target and the same
data budget -- **primitive** (raw fields only), **structure** (the authored
tags as features, a control), and **authored** (the rules themselves,
perfect at `N = 0` *by construction*, and named as such rather than dressed
up). Metric: balanced accuracy (a buy is rare, so plain accuracy would sit
on the majority class) on balanced held-out splits. The ladder is `cards`
(rung 0) vs `market` (rung 1).

- **Structure is worth roughly an order of magnitude of data.** To reach
  ~`0.9` balanced accuracy the tag representation needs about `16`
  examples; primitive features need more than `128` (`0.88` at `128`, still
  climbing). The gap holds on **both** rungs, and the tag control reaches
  ~`1.0` by `N ≈ 64`. This is the core result: the authored composition is
  cheap to *use* and expensive to *discover*.
- **The slope did not widen with `market` at this scale -- an honest
  non-result.** `market`'s primitive curve is essentially `cards`'
  (~`0.90` at `N = 128`), so the extra structural depth did not add a
  detectable imitation penalty. Diagnosed by measurement, not guessed:
  - With one listing per sample the `decide` bridge is **inert** --
    `Winner` is never false (`0/4000`). After giving each sample two rival
    listings, `Winner` discriminates (`53%` of listings lose), but a
    depth-6 tree handles the comparison readily.
  - `market.Strands` changes only `13/4000` labels: it is a real condition
    that the sampled distribution rarely makes binding.
- **The conclusion that follows:** added structure pays off only to the
  extent the domain's distribution actually exercises it. A bridge or a
  cross-entity island buys sample efficiency across the trajectories that
  cross it -- and nothing on the ones that do not. That is consistent with
  the theory, and it means the ladder's slope has to be earned by sampling
  that exercises the structure, not assumed.

### The slope, earned: a controlled depth dial

To earn the slope the composition is made deeper ON PURPOSE, with the
feature vectors still drawn from `market`'s own distribution and only the
DEPTH of the composed target dialled. Two families isolate the mechanism:
**axis** conditions on a single feature (`price > 50`), which one
axis-aligned split expresses exactly; **relational** conditions comparing
features (`price > cash - reserve`, `other_priority > priority`), which the
tree can only staircase. The reported quantity is the gap
`structure - primitive` in held-out balanced accuracy.

| family | depth 1 | depth 5 | reading |
|---|---|---|---|
| axis, N=32 | ~0.00 | ~0.01 | axis-aligned composition is nearly **free** |
| relational, N=32 | ~0.16 | ~0.23 | relations are where structure **pays** |
| relational, N=64 | ~0.09 | ~0.16 | the gap **widens** with relational depth |

Across all of it the tag representation stays at or above `~0.85` while
the primitive representation rises slowly. Capping the learner's capacity
(`max_depth`) barely changes the picture -- the primitive tree uses few
levels regardless, so the deficit is information-theoretic, not a
capacity artifact.

- **The slope is real, and it is about RELATIONS, not depth as such.**
  Adding axis-aligned conjuncts costs the flat learner nothing; adding
  *feature-comparing* conjuncts widens the gap. This is exactly what the
  tags, islands and bridges supply -- ratios, differences, cross-entity
  comparisons -- and it explains the domain-natural non-result above:
  `cards` and `market` are both built out of relational conditions, so both
  show the same ~10× advantage, and `market`'s extra depth added nothing
  because its extra condition rarely bound.
- **Caveat.** This is a *controlled probe over the domain's real feature
  distribution*, complementing -- not replacing -- the domain-natural
  `report`. The target is authored by construction, so the measured
  quantity is the imitation cost of the authored composition, stated as
  such rather than dressed up.

### Generalizing the slope: the real verdict

The dial above composes a synthetic target. This one dials the DOMAIN, on
the real authored verdict and over the natural distribution. `competitors`
is how many other cards carry a competing want, and each one MAY or MAY NOT
outrank the target's (`priority = target + drawn delta`), so the count can
grow the composition without driving the condition degenerate. Two
diagnostics locate the condition: `reach`, the fraction of worlds where a
listing is otherwise buyable at all (the only place `Strands` can matter),
and `binding`, the fraction of THOSE the condition actually flips.

The parameterisation is market-natural, not tuned to a result: `price =
value * m`, and `cash = price + slack` -- an agent whose cash only just
covers a purchase is the ordinary case. That is what keeps `reach` a
healthy fraction instead of collapsing (`TooRisky` dominating).

| competitors | reach | binding | gap @ N=32 |
|---|---|---|---|
| 1 | ~0.22 | ~0.25 | ~0.21 |
| 2 | ~0.22 | ~0.44 | ~0.23 |
| 3 | ~0.22 | ~0.58 | ~0.29 |

The tag representation stays at `~0.94`-`0.97`; the primitive one falls from
`~0.74` to `~0.68`.

- **The slope reproduces on the real verdict over the natural
  distribution.** The gap widens monotonically with the number of competing
  wants (`~0.21` -> `~0.29`) while `reach` is held constant, so this is not
  a conditioning artifact: the baseline decision is the same, only the
  composition of the cross-entity condition grows. `binding` rising
  (`0.25` -> `0.58`) is the mechanism.
- **It is a sample-efficiency effect, not representability.** At `N=32` the
  flat learner trails; by `N≈128` both converge (`gap ~0.12`-`0.15`). Authored
  structure buys DATA, exactly as the depth dial showed, and the widening is
  visible in the small-budget regime where that matters.
- **Caveat.** Single-seed estimates are noisy at this scale -- `reach` and
  `binding` say where the condition lives, and the parameterisation is what
  makes it reachable at all. The earlier attempt (an ill-chosen cash/price
  regime) put `reach` at `~0.07`, where the aggregate gap showed no widening
  for the same underlying reason: the structure was rarely exercised.

### The rest of the ladder: ranking and counting

Two more rungs, each a different KIND of composition than `market`'s
conjunction, measured the same way (real verdict, per-row flat learner vs
the authored tag, balanced accuracy on the balanced pool):

- **Ranking** (`trip`'s `decide` bridge): `rivals` complete itineraries for
  one request, projected onto `Option`/`Score` and ranked by
  `decide.pick_winner`. The flat learner gets its own cost/time AND each
  rival's in fixed slots, so the answer is expressible — but only as
  `own_score < every rival's score`, a comparison over the projected score.
  The tag is `Winner`.
- **Counting** (`quorum`): a motion passes iff `#{for votes} >= needed`. The
  flat learner gets every vote's choice in fixed slots but never the count,
  so it must reconstruct a cardinality. The tag is `Passed`.

| rung | setting | gap | structure |
|---|---|---|---|
| ranking | 2 rivals, N=32 | ~0.32 | 1.00 |
| ranking | 6 rivals, N=32 | ~0.32 | 1.00 |
| ranking | 2 rivals, N=256 | ~0.16 | 1.00 |
| ranking | 6 rivals, N=256 | ~0.18 | 1.00 |
| counting | 2 votes, N=32 | ~0.00 | 1.00 |
| counting | 4 votes, N=32 | ~0.21 | 1.00 |
| counting | 8 votes, N=32 | ~0.19 | 1.00 |

- **Ranking's deficit is large and roughly CONSTANT in the number of
  rivals.** It is about the KIND of composition — a total order — not its
  arity, and it closes only slowly with data (`~0.32` -> `~0.16` from
  `N=32` to `N=256`), never reaching the tag's `1.00`. This is the sharp
  contrast with `market`'s conjunction, whose deficit scaled with the number
  of conjuncts. (The tie rate rises with rivals, `0.11` -> `0.30`, since
  more candidates mean more exact ties `pick_winner` refuses.)
- **Counting is free at tiny arity and saturating beyond it.** At two votes
  the gap is `~0.00` — a tree expresses "at least one of two" directly. It
  appears once the count must be reconstructed (`~0.21` at four) and then
  *stops growing* (`~0.19` at eight): past a few votes the flat learner
  cannot count at all, so extra arity adds nothing.
- **The ladder's summary.** The authored gap's SHAPE depends on the type of
  composition: conjunction scales with arity, ranking is arity-insensitive
  and budget-limited, counting is free at tiny arity then saturating. The
  tag representation is exact (`1.00`) in every case.
- **Caveat.** Same controlled-imitation framing (target is the authored
  verdict), single-seed estimates, and one flat baseline (an axis-aligned
  tree) rather than the strongest possible learner.

### Repairs needed to run (pre-existing breakage)

The `simplification` commits had left the package unable to register any
real domain's rules; fixed to proceed:

- `loopingrules/analyze.py` referenced an undefined `_CORE_REPLY` (the
  removed `world.reply` helper) — dead branch removed, stale docstring
  corrected, unused `Reply` import dropped.
- `examples/cards.py` / `examples/shopping.py` still called `World.learn`,
  removed in the same simplification — dead calls removed.

### Next

- **A domain-natural ranking and count.** Ranking and counting are measured
  on the controlled-imitation harness; reproduce them over a natural
  distribution the way `relevance` did for the conjunction -- sample so the
  composition is genuinely exercised, not only where a fixed rival set makes
  it convenient.
- **Stabilize the estimate.** The domain-natural result rests on single-seed
  runs whose `reach`/`binding` are noisy at this scale; averaging over
  several dataset draws would put an error bar on the slope rather than one
  number.
- **Experiment 3** — new island: `market` already has selling; measure what
  each system needs to ACQUIRE it (authored: a couple of rules plus a knob;
  de novo: labels, and whether it can represent the new decision).

## Limits

- `cards`/`market` are small; the ablation's gap is suggestive, not proof,
  and a stronger flat learner (a kernel, a relational model) might close
  it. One honest baseline, not the strongest possible one.
- The LLM comparison is tempting and confounded: pretraining leakage is
  unmeasurable. It is honest only framed as "does an existing pretrained
  prior already contain this island?" — and a positive answer there is
  evidence *for* the scaling camp.
- Avoid the tautology: authored structure helping sample efficiency is true
  by construction. The measurable question is how much structure a generic
  learner can *recover*, and at what data cost — i.e. *is the structure
  discoverable, or must it be authored?*
