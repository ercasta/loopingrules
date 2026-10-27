# D4 — Level-2 memory and online adaptation

Phases 4 and 7. The strongest form of the product thesis: **authorship handles
structure; calibration handles drift.** Offline tuning answers "is this
configured well for the world I sampled?"; online adaptation keeps it
configured as the world moves. Locked: design for it now, build offline first.

## Why it fits the architecture

Knobs are **singleton components the rules read** (`docs/tuning.md`'s design
rule). So "change a knob" is just `w.replace(knob_entity, KnobComp(new))` —
an **ordinary write an ordinary rule makes**. Therefore:

> An adapter is just a rule whose output is a knob, consuming checks as its
> input.

No new mechanism. The same stigmergic move as everything else: the controller
is oblivious, it fires because its condition became true, and the world
re-settles around the new value. `analyze` already handles its read/write sets;
gating already works.

This is the end-state the earlier discussion named: **calibration stops being a
one-off lab step and becomes continuous.**

## Evaluation vs. control (recap of the D2 seam)

One check vocabulary, two wirings:

- **Scorer (offline):** inert, over recorded traces. Must not perturb.
- **Controller (online):** effectful, consumes checks' outputs, writes knobs.
  Perturbation is the point.

Do not merge them. Reusing the checks is the win; collapsing the sandboxes is
the bug.

## Timescale separation

Two designs, in build order.

### Slow timescale (Phase 4) — adapt between episodes

Run -> observe the completed trace -> adjust knobs -> next run. This is
incremental re-calibration: literally `search` applied to the latest trace,
keeping the inner world deterministic given the knobs. Safest, closest to the
offline kit already built, and it already delivers "the system keeps itself
configured."

### Fast timescale (Phase 7) — adapt within a run

"Perform an action, evaluate the effect, change a knob to avoid further
undesirable consequences." This can still **settle**, because the loop's own
`revision` mechanism is the discipline: a controller that re-emits the *same*
knob value moves nothing and the world settles. Adaptation is therefore
naturally event-driven and bounded — it fires on new evidence, settles, fires
again on the next new evidence.

Named failure mode: an **oscillating** controller (change A -> evidence flips
-> change back -> evidence flips...) keeps firing -> budget exhausted -> `hot`
-> error (`loop.py`). That is a detectable failure, and it is why fast
adaptation requires, from day one:

- **Hysteresis**: change only past a margin; ignore small excursions.
- **Rate limit**: at most one adjustment per N ticks/episodes.
- **Bounds**: the `low`/`high` already on the `Knob`.
- **Idempotence**: re-emit equal -> no-op -> settle.

Those controller hyperparameters (margin, rate) are themselves **knobs** — so
the adapter can be **meta-calibrated offline**, against trajectories in a
mutating environment. Recursion is deliberate: calibration all the way down.

## Safety

- **Only `scope="runtime"` knobs may be moved online** (D3's locked default is
  offline-only). The runtime set is small and auditable.
- **The offline-calibrated world is the controller's baseline and its
  pull-back.** The controller starts there and reverts there if adaptation
  drives the system out of bounds. Adaptation augments calibration; it never
  replaces the floor.
- **Irreversible actions stay fenced.** A controller must never be the thing
  that authorises an irreversible effect (Phase 5's effect fencing). It may
  adjust the knobs that *lead to* a decision; it does not perform the effect.

## Level-2 memory: promotion and consolidation

The transient log (D1) is the look-back window; **promotion rules** make some
of it durable:

- Consolidation is a decision, and therefore tunable: *what* to promote, *how
  much*, *when* (e.g. promote only lessons seen twice).
- Promotion rules are ordinary rules, tunable offline like any other.
- Durable memory is ordinary components — queryable, `save`-able, shareable.

A controller may also *read* promoted memory (durable lessons) as an input, so
adaptation can be informed by what the system learned in past sessions. Keep
the direction clean: the controller reads memory and writes knobs; it never
writes memory directly (that is the promote rules' job).

## Reproducibility

With adaptation, a run is deterministic only if the checks, the controller,
**and** the environment are accounted for. So the **trace grows a field**: the
controller's decisions, or the observations that drove them (D1/D2). Consequence
named honestly: the faster the adaptation, the fatter the trace. That is a real
cost and an argument for shipping slow-timescale adaptation first.

Assert the gate before trusting anything (D2): replay twice, same trace hash.

## Risks, named not hidden

- **Masks bad authorship.** A jittery controller can paper over a misspecified
  rule. Mitigation: offline calibration is the baseline; the linter (D3) still
  holds the author to a correct structure; adaptation is optional and declared,
  never the default mode.
- **Debuggability.** The trajectory now depends on the controller, so debugging
  requires the controller's decisions in the trace (above).
- **Instability.** No stability guarantee is offered; only bounds, hysteresis,
  rate limits, and the budget's circuit breaker. A full stability argument
  (fixed points, oscillation detection) is real, separate work, not claimed
  here.

## What this does not settle

- Whether the controller is authored as **rules in the substrate** (consistent
  with everything else) or as an **external service** reading the trace. The
  in-substrate version is more "pure" to this architecture; the external one is
  easier to bound and audit. Undecided.
- Multi-knob coupling: adapting two knobs at once can interact; no policy here.
- Whether adaptation is per-domain, per-island, or global.
- Stability analysis (fixed points, oscillation detection) as a property of the
  controller.

## Open questions

1. In-substrate controller vs. external service?
2. Fast-timescale controller: one rule per runtime knob, or one rule managing a
   group?
3. Where do the controller's own hyperparameters' bounds live — a second knob
   declaration surface, or the same one?
4. Does an adaptation decision itself get promoted to memory when it proves
   good (so a later session starts pre-adapted)?
