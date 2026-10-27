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

- **The instrument is now a package**, `loopingrules_calibration` (Phase 1
  of `docs/plan.md`): `Knob` (a declared tunable field on a singleton
  component, with a `scope` saying whether a runtime controller may move it
  later), `Scenario`, `replay` (deterministic, records the per-tick firing
  trace and a behavioural `signature`), `read_knobs` / `write_knobs` (refuse
  when the component was never seeded), `grid`, and an optimizer-free
  `search` -- plus `calibrate`/`Report` (held-out scores, plateaus,
  sensitivity) and replay caching. It was `examples/tuning.py`; the three
  experiments that used it now import the package. Its `signature` corrects
  two flaws in the original hash: it EXCLUDES the knob components (so many
  settings can share one trajectory) and INCLUDES `@transient` tags (so
  behaviour recorded only in a tag is not invisible).
- **The tunable surface is declared on the rule, and checked** (Phase 3 of
  `docs/plan.md`): `@tunable(Knob(...))` co-locates a rule's knobs with the
  rule (`loopingrules_calibration.surface`), `knobs(loop)` collects them from
  a domain's registered rules, and `lint` -- over the same `analyze` AST
  walk, as `analyze.literals` -- flags a numeric literal where a tunable rule
  should read a component, reporting a knobbed rule `analyze` cannot see as
  `unlintable` and excusing a literal only with a reason. This is
  `docs/plan-calibration.md`'s linter: the enforcement of this file's own
  design rule that a tunable rule never hard-codes its threshold.
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
- `examples/acquisition.py` — Experiment 3, the novelty crux: acquiring the
  SELL behaviour `cards` deliberately lacks, authored (a couple of rules plus
  a knob) vs de novo (a flat learner over raw facts), with a convergence
  probe for the representability question. Also `examples/trade.py` +
  `examples/adapters.py` — an ownership island and an explicit
  representation adapter, a side probe of whether an effect-carrying concept
  stratifies (hub) or meshes (adapter); not on Experiment 3's critical path.
- `examples/hierarchy.py` — Experiment 4: the "tune islands, freeze them,
  tune only the bridge" scheme, measured. Two islands (weighted, graded
  opinions), a weighted-threshold bridge, and a hidden global objective that
  needs both signals unequally; reach, freeze cost, and covariate shift.
- `examples/party.py` — Experiment 5: composing simple local rules into a
  CHAINED investigation with NO central scheduler. Questions are entities,
  raised by scoped conditions and answered by oblivious rules; a finding
  makes a later rule's condition true (weather -> backup). Measured: the
  chain terminates, and the SCOPE of the watched conditions decides both
  correctness (too narrow skips a step) and cost (too broad wastes checks).
- `examples/planning.py` — Experiment 6: (b) a finding that raises a CHOICE
  among next questions (a rainy outdoor venue -> backup venue vs tent,
  resolved locally by `examples.decide`'s `Option`/`Score`/`Winner`), and
  (c) tuning the investigation's thresholds (`rain_threshold`, `max_checks`)
  against a TRAJECTORY score (`valid - cost`) with `tuning.search`.
- `examples/branching.py` — Experiment 7: deepening the branch -- the chosen
  remedy raises ANOTHER choice (tent -> which tent?), both levels resolved by
  the same `pick_winner` keyed by the question entity. `prefer_relocate` and
  `max_checks` are tuned to pick the shallow `relocate` branch over the
  deeper `tent` one; too small a depth budget silently refuses.
- `loopingrules/analyze.analyze` is now memoized by function object (safe:
  no caller mutates the returned `Analysis`). Rule registration repeated
  thousands of times by a replay harness parses each rule once — the
  ablation suite dropped from ~84s to ~5s, the whole suite to ~10s.
- Tests: `test_calibration.py`, `test_examples_bridge.py`,
  `test_examples_market.py`, `test_examples_quorum.py`,
  `test_examples_ablation.py`, `test_examples_acquisition.py`,
  `test_examples_adapters.py`, `test_examples_hierarchy.py`,
  `test_examples_party.py`, `test_examples_planning.py`,
  `test_examples_branching.py` — `271 passing`.

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

### What Experiment 3 found

`examples/acquisition.py`, the novelty crux: acquire the SELL behaviour
`cards` deliberately lacks, and measure what each system pays for it. The
authored arm is a couple of rules (`tag_surplus` plus `decide_sell`'s
held-gate) and one knob (`Policy.sell_premium`), perfect at `N = 0` by
construction. The de novo arm is the same flat tree over the raw facts
(`offer`, `value`, `held`, `premium`), never the `Surplus` tag; the target
is the real sell verdict, observed on a scoring-only loop so nothing sells.

- **The projection buys roughly `4x` the data at the 0.9 line, `~8x` at
  0.95.** The tag reaches `0.9` balanced accuracy at `N = 16` and is exact
  by `N = 32`; the raw facts need `N = 64` for `0.9` and only reach `~0.95`
  by `N = 128`. The gap bites at small `N` (`~0.16` at `N = 8`).
- **The new decision IS representable without the projection — at a
  price.** Pushed to `N = 1024` the raw curve climbs to `~0.99` and never
  quite closes on the tag's `1.0`: a DATA cost, not an impossibility. So on
  this behaviour the de novo camp's objection survives weakly ("more data
  buys it") while the theory holds strongly ("structure buys the data, and
  a residual never fully closes").
- **It reproduces the relational reading where `market` did not.** Unlike
  Experiment 2's `market` non-result (its extra condition rarely bound),
  the sell condition is a comparison against a PRODUCT
  (`offer >= value*(1+premium)`) — the family the depth dial showed
  structure pays for — and here the gap is real.
- **A structural wrinkle, named.** Experiment 2's buy verdict is ALL
  attached tags; the sell verdict is a projection (`Surplus`) PLUS an
  inline guard (`held >= 1`) `decide_sell` never reifies. A structure
  control carrying only `Surplus` under-specified the target and scored
  *below* primitive (`~0.79` vs `~0.95`); the fair control carries both.
  "The authored tags" is not automatically the authored DECISION — inline
  control flow is structure too, and must be reified to be measured.
- **Caveat.** Same controlled-imitation framing, single seed, one flat
  baseline. The `4x` is one behaviour on one distribution, not a law.

### What Experiment 4 found

`examples/hierarchy.py`, the "tune islands, freeze them, tune only the
bridge" scheme, measured on a controlled two-island probe (a graded opinion
per island, a weighted-threshold bridge, a hidden global objective
`0.7*x1 + 0.3*x2 >= 0.5` that needs both signals unequally). Numbers are
held-in (the probe measures REACH, not generalization).

- **The bridge does the work, and the freeze is not free.** Bridge tuning
  beats an equal-weight bridge (`0.963` vs `0.873` aligned; `0.933` vs
  `0.902` misaligned); the joint ceiling is `0.983`.
- **Freezing costs more when local tasks misalign** (`joint - staged`:
  `~0.02` aligned, `~0.05` misaligned) -- and not zero even when aligned,
  because joint tuning sets biases away from the local optimum to make a
  saturating island the linear bridge can exploit. "The local task's best
  knob" is not "the best feature for the global task."
- **Conditioning the data is not the lever.** The locally-tuned knob does
  not move under a shifted input distribution for a well-specified
  threshold OR calibration task; it moves only under MISSPECIFICATION
  (`gain 2`, conditioned to `x1 < 0.4`: `0.5 -> 0.4`). Conditioning hard
  enough can also make the local labels single-class, making the local
  objective undefined.
- **The load-bearing assumption** is that each island's LOCAL objective is
  an honest proxy for the GLOBAL one. Where it is, freezing is nearly free;
  where it is not, re-weighting helps but does not close the gap -- the fix
  is to re-target the objective, not re-condition the data.
- **Caveat.** A controlled, static, single-seed probe with one bridge
  shape. It cannot show the SEQUENTIAL covariate shift `tuning.md` names
  (one rule's change altering what later reaches another); that needs a
  multi-tick domain.

### What Experiment 5 found

`examples/party.py`, composing simple local rules into a chained
investigation with **no central scheduler**. A `Question(kind)` is an
entity; a rule raises one only when its own condition holds and none is
pending or `Checked` (dedup BY EXISTENCE); an oblivious rule answers it,
leaving a finding a later rule's condition can read (`Rain` -> ask for a
backup). `decide` waits on `w.first(Question) is None` (a NEGATED read, so
`analyze` does not gate it dormant on the absent type).

Two scenarios, venues `hall(indoor,50)`/`garden(outdoor,40)`, rain, budget
100; reported as `(planned, valid, asks)`:

- **Scope decides correctness.** On `outdoor_risky` (book the garden), a
  `narrow` raiser that checks the weather for the FIRST venue only (the
  indoor hall) never sees the rain, and the cautious decision REFUSES the
  party: `(False, -, 0)`. `scoped`/`broad` run the full chain: `(True, True,
  2)`.
- **Scope decides cost.** On `indoor_chosen` (book the hall), `narrow`/
  `scoped` ask nothing (`0`); `broad` asks about the weather for a venue
  nobody is booking (`2`) -- a wasted check.
- **A sub-scoped trigger is silent, not safe.** With a TRUSTING decision
  ("no `Rain` found means fine"), the same narrow scope yields `(True,
  **False**, 0)` -- a confident, INVALID plan (outdoor party in the rain,
  no backup). The cautious decision is what turns a too-narrow scope from a
  wrong answer into a refusal.
- **No scheduler was needed.** Every step is a condition: "after the
  weather check, ask for a backup" is the backup rule reading the `Rain` a
  finding left behind. Sequencing is data.
- **Caveat.** Every fact is already in the world (checks are conditional
  DERIVATION, not external I/O -- `architecture.md`: no rule may block). A
  version where a check must fetch an absent fact, and cost is real, is a
  named next step.

### What Experiment 6 found

`examples/planning.py`, extending the party probe with (b) a CHOICE among
next questions and (c) tuning against TRAJECTORY examples.

- **(b) The choice point is a local conflict resolution, not a scheduler.**
  A rainy outdoor booking raises a `Question("remedy")`; `propose_backup`
  and `propose_tent` each attach `examples.decide`'s `Option`/`Score` to a
  candidate (score = negated cost); `decide.pick_winner` -- reused verbatim
  from the option/score bridge -- crowns the cheaper (the tent at 30 over
  the hall at 50); `resolve_remedy` applies it. The dedup is per remedy
  KIND, or the second proposer would be blocked and there would be no
  choice at all.
- **(c) The knobs are the trajectory.** `Policy(rain_threshold,
  max_checks)` are the tunable surface; `score_replay` scores the RUN
  (`valid*2 - 0.5*checks`), never a final number. Two failure modes and one
  fix, on five scenarios:
  - a `rain_threshold` of `0.9` calls a `0.4` drizzle "clear" and books an
    unprotected outdoor venue -- INVALID, `2.0`;
  - `max_checks = 1` cuts the chain right after the weather check, so the
    remedy is never sought -- refused, `2.0`;
  - `tuning.search` finds `(0.0, 2)` at `6.5`, beating the default
    `(0.5, 4)` at `5.0` on validity-per-check. The surface has PLATEAUS
    (any threshold below the lightest rain and above zero is equally good)
    -- a behavioural equivalence class, per `tuning.md`, not one number.
- **Caveat.** Same as Experiment 5: facts are present, checks are
  derivation; and the two knobs are the only structure -- tuning still may
  not move structure, only values.

### What Experiment 7 found

`examples/branching.py`, deepening the branch: the level-1 choice can OPEN
a level-2 choice -- `rain -> Q(cover): tent OR relocate`, and if tent wins,
`Q(tent_size): which tent?`. Both levels are the SAME mechanism (propose
candidates carrying `decide.Option`/`Score`; `decide.pick_winner` crowns the
best), kept apart by making each QUESTION ENTITY its own `occasion` --
`Option(cover_id)` at level 1, `Option(tent_size_id)` at level 2 -- so one
oblivious rule resolves both and the branch is just a condition. Score
`valid*3 - checks`, four scenarios (small party, big party, dry, indoor):

- **The branch is really two levels, and it is data-bounded.** The small
  party under the default policy rents a tent and then chooses a TENT SIZE:
  `checks = [weather, cover, tent_size]`, both `tent` and `tent_option`
  winners present. Nothing authored "two levels"; level 2 exists only
  because level 1 won with `tent`.
- **Depth costs, and that is the trajectory.** The `tent` branch is 3
  checks; `relocate` is 2. Tuning `prefer_relocate` up (`>= 40`) moves the
  small party onto the shallow branch: total `6 -> 7`, all valid.
- **A too-small depth budget is a silent refusal.** `max_checks = 1` stops
  after the weather check, so no remedy is reached and the rainy outdoor
  plans are refused -- `shallow_budget` scores `3` against the tuned `7`.
- **Caveat.** Same as 5 and 6 (facts present, checks are derivation); and
  the branch depth here is two, only because level 2 has no sub-choice of
  its own -- the mechanism would recurse, but nothing exercises it.

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
- ~~**Experiment 3** — new island.~~ Done: `examples/acquisition.py`, see
  "What Experiment 3 found." What it does NOT settle: a second, differently
  shaped new behaviour (one whose decision is NOT a product-against-a-
  threshold), to test whether the `4x` is a property of the method or of
  this one relational family -- and a stronger flat learner than the
  axis-aligned tree, which might close more of the residual.
- **The sequential covariate shift Experiment 4 could not show.** Its probe
  is static, so it can only see the objective mismatch, not the way one
  rule's change alters the distribution of inputs a LATER rule meets. A
  multi-tick domain that changes what reaches an island mid-run is the
  honest next step for the "freeze islands, tune bridges" claim.

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
