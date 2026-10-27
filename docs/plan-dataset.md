# D2 — Dataset and scoring

The delicate one. Rules are easy to author; **obtaining the samples to tune
them is not.** This doc defines what a training example is, where it comes
from, how it is scored, and — importantly — the seam that lets the same checks
later drive online adaptation (D4).

## The two poles

An author has two ways to say "this behaviour is wanted / unwanted":

**(a) Black-box datapoints.** Input channel -> expected output channel.
- In this engine these are nearly free already: `Scenario.lines` are the
  inputs (`Said` per channel), `Replay.replies` are the outputs.
- Cheap to author, implementation-agnostic (the property that makes them fair
  for comparing systems — the experiment methodology in `docs/tuning.md`
  depends on this).
- No intermediate signal; weak credit assignment.

**(b) Checks that read the blackboard.** Read the world *midway* and score it.
- Expresses desired/undesired **process**: invariants, "no wasted calls",
  "the reserve was respected at every tick", "a question raised was answered".
- Strong, structural credit assignment — this substrate's stated model
  (`docs/tuning.md`: "credit assignment is structural, not temporal").
- Costlier to author and, if careless, couples the dataset to the
  implementation (see the hazard below).

They are not rivals. The honest default is **(a) for behaviour, (b) for
process**, with (b) restricted to robust *invariants* and (a) carrying the
bulk.

## The unifying object: the trace

Both poles read from one object, the **Trace**, produced by one deterministic
replay:

```
Trace(
  scenario,        # install kwargs + input lines (per channel)
  observations,    # per-tick snapshots captured via Loop.run(after_tick=...)
  changes,         # the D1 change log (provenance, deltas)
  replies,         # output channel traffic (Replay.replies today)
  final_world,     # save.dump of the settled world
  ticks, hot,      # settling facts (hot = budget ran out, already penalised)
)
```

Two existing seams build this with no engine change:

- `Loop.run(after_tick=...)` already calls a hook after every tick that
  changed something — the natural place for a **pure-reader observer** to
  snapshot mid-run state without perturbing it.
- `Loop.tick()`'s per-tick `fired` names, plus the D1 `changes`, give the
  trajectory.
- The **environment tape** (Phase 5) is a field of the scenario: recorded tool
  answers, so a trace reproduces offline.

The Trace is the dataset's unit, the scorer's input, and — later — the
controller's input. Getting this interface right is what makes D4 mostly
wiring.

## Checks: a pure vocabulary

A **Check** is a pure function `Trace -> score or observation` (plus the
ability to compose). Examples:

- black-box: output channel said X when input said Y, within N ticks;
- invariant: reserve never below zero at any observation;
- process: number of external calls; a raised question was answered;
- automatic ground-truth terms where the domain has them (goal met, overpaid).

Properties that matter:

- **Composition, not monolith.** A dataset entry = `(scenario, checks[])`;
  a scorer composes weighted terms. Keep the objective inspectable, per
  `docs/tuning.md`.
- **Ranking is first-class.** Prefer preference pairs `A ≻ B` over absolute
  labels (`docs/tuning.md`); the substrate already speaks it via
  `examples/decide`'s `Option`/`Score`/`Winner` and `Risk.level`'s free
  ranking. A preference pair is two traces with an ordering.
- **Penalties.** `hot`/non-settling (already named), external call count,
  irreversible effects, staleness.

### The hazard, stated plainly

A check that reads **internal vocabulary** (assumes a particular tag
structure) couples the dataset to the implementation. That is brittle, and it
can actively *defeat tuning*: you cannot calibrate a system toward a check
that presumes the very structure you may be trying to move. Rule of thumb:
black-box for behaviour; invariant checks for process; internal-vocabulary
checks are an exception that must state its reason.

## Evaluation vs. control (the seam that D4 needs)

Locked decision: checks are one vocabulary, wired twice.

- **Offline (evaluation):** an inert `scorer` over traces, used by calibration
  search. **It must not perturb the trajectory it scores** — the same standing
  a tool or channel has (`docs/tuning.md`), and the reason checks are pure.
- **Online (control, D4):** the *same* checks feed a controller that
  deliberately writes knobs. Perturbation is the point there.

If the two are collapsed, tuning is measured against a world its own
measurement moved. Keep them as two wirings of one vocabulary, in two
sandboxes. (For expressiveness, a domain may also author checks that run on a
scoring-only loop, the `examples/ablation.py` idiom — but that is a *label
generator*, not a live scorer, because it changes the trajectory.)

## Sample acquisition (the hard part)

Treat this as a first-class feature, not an afterthought. Levers, roughly in
order of value:

1. **Capture from live runs.** A recording channel logs a session as a
   `Scenario` (+ its Trace). This is where volume comes from. A channel is
   already the only external boundary (`engine.py`); it posts inputs and
   receives outputs, so recording both is a small channel, not an engine
   change.
2. **Structure-driven generation.** `examples/ablation.py`'s "depth dial" and
   `relevance` sweep already proved the method: generate samples so the
   composition is genuinely *binding*, reproducing the natural distribution
   rather than sampling where a convenient fixed rival set makes it look easy.
   Reuse it.
3. **Uncertainty-directed labelling.** Calibrate, then use D3's
   sensitivity/plateau report to request labels **exactly where knobs flip the
   trajectory** — never label where every setting agrees.
4. **Environment tapes.** A captured scenario replays offline against recorded
   tool answers (Phase 5), so a sample is cheap to re-score.
5. **Preference elicitation.** Ranking pairs are cheap for a human ("this run
   is better than that one") and match the substrate; raise them explicitly.

## The dataset as an artifact

- A dataset is a **versioned collection** of `(scenario, checks?, label?,
  preference?)`, with provenance: how each sample was obtained, by what, when.
- **Held-out by construction.** Training and evaluation sets are separated at
  creation, not after. `docs/tuning.md`'s learning-curve harness already asks
  for "held-out, and identical across every system under test — the scorer is
  itself a prior."
- **Reproducibility gate.** Before any score is trusted: replay twice, same
  trace hash (`docs/tuning.md`). With tools, the tape is part of the hash.

## What this does not settle

- The exact serialisation of a Trace (and whether a Trace is itself
  `save`-able).
- How labels and preferences are **elicited** from a human, in practice
  (a UI? a channel command? a review file?). This is probably its own doc.
- Noise statistics for a stochastic objective (repeats per grid point) — the
  shape of the estimator is D3's question.
- Whether checks may themselves be tuned (they are rules/terms too; recursive,
  deliberately left open).

## Open questions

1. Trace serialisation format; is a dataset a JSONL of traces or of scenarios
   plus checks?
2. Should the black-box "expected output" be an exact string, a set, or a
   checker predicate?
3. How does the recording channel decide where a session begins and ends?
4. Do preference pairs live in the same dataset object as scalar-label
   examples, or a separate one?
