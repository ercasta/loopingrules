# Plan: engine + standard library + authoring/calibration workflow

Status: Phases 1-2 built, and Phase 3's author surface and linter with them;
the pattern library and the rest are design, apart from the reuse layer's
first spike (D6) and reflection's two probes (D7). This directory holds the
roadmap and seven design docs (D1-D7 — the sixth the reuse layer, the
seventh reflection and the control channel), plus `modeling.md` for the
modeling half.
Nothing beyond that is a commitment
to code; each doc ends with the open questions it does *not* settle, in the
same posture `docs/tuning.md` and `TODO.md` already take.

**Phase 2 status:** the change log is built -- `Change` + `World.changes`
(transient, never saved, `Loop(capacity=...)`-bounded), `Loop.tick`
provenance, `analyze` gating on `changes(changed=...)`, and `Trace.changes`
in the calibration kit. See `docs/plan-memory.md`.

**Phase 1 status:** the calibration kit is built as the package
`loopingrules_calibration` (`Knob`, `Scenario`, `Trace`, `replay`,
`search`, `calibrate`/`Report`), with replay caching, a pluggable per-tick
observer, held-out scoring, plateaus and sensitivity; `examples/tuning.py`
and `tests/test_examples_tuning.py` are gone, replaced by
`tests/test_calibration.py`, and the three experiments that used the old
module import the package. See `docs/plan-calibration.md`.

**Phase 3 status (partial):** the author surface and the linter are built, and
the pattern library has its first promoted pattern. `@tunable(Knob(...))`
declares a rule's tunable surface on the rule itself
(`loopingrules_calibration.surface`), collected by `knobs(loop)`; `lint` sits
over `analyze.literals` and flags a numeric literal where a tunable rule
should read a component, reports a knobbed rule `analyze` cannot see as
`unlintable`, and excuses a literal only through `allow=(...)` with a reason.
`loopingrules_patterns` ships `judge` (`docs/patterns.md`), promoted from
`examples/judge.py` because three domains already install it at runtime; the
remaining candidates are not shipped. See `docs/plan-calibration.md`.

**D6 status (partial):** the reuse layer -- islands, bridges, conjunction --
has a first spike, `loopingrules_islands` (`items`/`funds`, probe `i0`, pinned
by `tests/test_islands_i0.py`): it settles, reuses one island across two
domains, composes across two islands, and catches the fabricating-candidates
antipattern. **Nothing is folded in yet** -- `TODO.md` records that debt. The
open shape questions (monotone vs revisable promotion, what a decision may
read, cycles, overlapping bridges) are in `docs/plan-islands.md`.

**D7 status (probes built):** the reflection direction has its engine
primitive (`loopingrules.reflect`: `RuleCard`/`RuleControl`/`reify`/
`rule_hash`, and the `_tick_order` read that makes a control real) and two
probes, `loopingrules_reflect/{r0,r1}.py` (pinned by
`tests/test_reflect_r0.py`/`test_reflect_r1.py`). R0 shows a rule over memory
+ rule-cards tames a hot loop with the controlled rule unchanged, and an
oscillating controller stays hot; R1 shows the forge IR is analyzable without
the Python AST, totally, agreeing with `analyze` 12/12. **Nothing is folded
in** and the IR is not moved into the engine. See `docs/plan-reflection.md`.

**Phase 4 status (built):** checks as control, slow timescale.
`loopingrules_calibration.checks` is the pure `Check`/`total` vocabulary;
`loopingrules_calibration.adapt` is the between-episode `Adapter`/`adapt`
(`margin`/`every`/`window`); `examples/drift.py` (Experiment 8) measures it --
a frozen world degrades as the target ramps, the adapter tracks it, a
stationary world settles in one move. The SAME `Check` objects wire the
offline scorer and the online controller. The fast timescale (Phase 7) is not
built. See `docs/plan-adaptation.md`/`docs/plan-dataset.md`.

**Generator status (walking skeleton):** `loopingrules_forge.evolve` — GP over
the IR: `ir_hash` (identity over the DATUM, not the source), `random_expr`/
`mutate`/`crossover` operators, a controller-pattern genome with a condition
HOLE, the
Phase-4 checks as fitness, and a gate (analyze-clean and settles). On a toy
control domain (two runaway rules to disable) it finds a controller in five
generations, where a do-nothing controller scores `0.0` and the known-good
condition `1.0`. It proves the PIPELINE, not that GP scales. See
`docs/plan-forge.md`.

**Modeling status:** design only (`docs/modeling.md`). The model is the
executable world plus *reified actions* -- schema + effect deltas + executor --
reasoned over by a planner; **not** an ontology, because OWL/RDF cannot carry
behavior. `circuits.Call`/`ToolRequest` is already two-thirds of the triad.

**Learning status:** the EA is a walking skeleton (`loopingrules_forge.
evolve`); otherwise design only (prior art in `docs/study-guide.md`). No ILP
induction, no three-source adjudication.

## Goal

Turn this repository from a substrate plus a research program into a product
with three parts:

1. **Engine** — `loopingrules/` unchanged: entities, components, rules, one
   thread, channels. Ships no domain vocabulary.
2. **Standard library of reusable patterns** — importable, curated patterns,
   each shipping a *declared tunable surface*.
3. **Authoring + calibration workflow** — a practical way for an author to
   write a domain, declare its knobs, build a training dataset, calibrate,
   and deploy.

The product thesis, stated once and used to judge everything below:

> Authorship handles **structure**; calibration handles **drift**. The value
> is in the part an author does not fully determine — the trajectory that the
> knobs choose. Therefore **a pattern is not "reusable" until it exposes a
> declared tunable surface**, and **calibration must be a first-class author
> activity, not a research afterthought.**

## Where the repo stands

| Piece | State |
|---|---|
| Engine (`world`/`loop`/`engine`/`save`/`share`/`analyze`) | Complete, stable, no domain vocabulary. Little to do. |
| Design theory | `docs/tuning.md` — rich, but framed as a research program (Experiments 1-7). |
| Calibration instrument | **Built (Phase 1)** as the package `loopingrules_calibration`: `Knob`/`Scenario`/`Trace`/`replay`/`search` plus `calibrate`/`Report`, replay caching, a per-tick observer, held-out scoring, plateaus/sensitivity. |
| Worked domains + bridges | `examples/` (`decide`, `cards`, `market`, `quorum`, `trip`, `party`, `planning`, `branching`...) — the material to distil a stdlib from. |
| **Standard library** | **Built (Phase 3, partial)**: `loopingrules_patterns` ships `judge` (`docs/patterns.md`); the rest of the candidate set is not promoted yet. |
| **Author surface** | **Built (Phase 3)**: `@tunable(Knob(...))` co-located on the rule, collected by `knobs(loop)`; `lint` holds those rules to it. |
| **Dataset kit** | **Partial (Phase 4)**: the checks vocabulary is built (`checks`: `Check`/`total` + generic terms); the format, capture channel, labels/rankings and train/eval split are still missing. |
| **Memory / change log** | **Built (Phase 2)**: `Change` + `World.changes`/`recent`/`clear_changes`, transient and never saved, `Loop(capacity=...)`-bounded, with `Loop.tick` provenance and `analyze` gating on `changes(changed=...)`. |
| **Checks as control (slow adaptation)** | **Built (Phase 4)**: `loopingrules_calibration.checks` (the pure `Check`/`total` vocabulary) + `adapt` (the between-episode `Adapter`) + Experiment 8 (`examples/drift.py`); a frozen world degrades as the target drifts and the adapter tracks it, using the SAME checks. Fast timescale (Phase 7) not built. |
| **Structure generator (EA)** | **Walking skeleton (D5)**: `loopingrules_forge.evolve` — GP over the IR finds a controller (gated, hashed over the IR datum) on a toy control domain; scaling to real controllers is open. |
| **Tools / external world** | Missing. Only the channel seam exists; no tape/cache, no effect fencing. |
| **Reuse layer** | **Spike built (D6)**: `loopingrules_islands` (`items`/`funds`, probe `i0`) — settles, reuses across two domains, composes across two islands, catches the fabricating antipattern; not folded in yet. |
| **Reflection / control channel** | **Probe built (D7)**: `loopingrules.reflect` + `r0`/`r1` — a rule over memory + rule-cards changes the schedule with the controlled rules unchanged, and an oscillator is caught; IR analysis is total. Not folded in. |
| **IR-native rules** | **Probe built (D7)**: `r1` proves the forge IR is analyzable without the Python AST, agreeing with `analyze` 12/12; the IR is not yet an engine core and `analyze`-on-Python is not yet demoted to an audit. |
| **Modeling** | Missing. No reified actions, no action algebra, no planner; design in `docs/modeling.md`. |
| **Hybrid learning** | Missing. No three-source loop (rules/examples/feedback), no EA/ILP induction; prior art in `docs/study-guide.md`. |

## Decisions already locked

These came out of the design discussion and are assumed by D1-D4:

1. **Memory first, descriptors later.** Revive the change log by instrumenting
   `World`'s six write methods (the `tracing`/`changes` the simplification
   removed). *Do not* change the rule API now. Rules returning a change-list
   descriptor is deferred; its real payoff is atomicity, a validation
   boundary, and the bridge to rules-as-data (see D1's "descriptors" note and
   `loop.py`'s own recorded objection).
2. **Memory lives loop-side, transient, not in `save`.** Long-term memory
   enters `save` only via authored **promotion rules** that read the transient
   log and attach ordinary durable components (D1, D4).
3. **Checks are a pure vocabulary over a trace; evaluation and control are two
   wirings of it.** The offline scorer must not perturb the world it scores;
   the online controller deliberately does. Same checks, two sandboxes (D2, D4).
4. **Design for online adaptation now, build offline first.** The calibration
   kit, the trace, the check vocabulary, and the knob surface must not
   foreclose real-time adaptation (D2, D3, D4).
5. **Knobs are `offline-only` by default**, runtime-tunable only when the
   author explicitly marks them (with bounds and rate limits) (D3, D4).
6. **Same repo, second package.** New top-level packages, siblings of
   `loopingrules/`, imported the way `examples/` already is via
   `pyproject.toml`'s `pythonpath = ["."]`. Names provisional:
   `loopingrules_calibration` and `loopingrules_patterns`.
7. **The artifact of calibration is a saved world** (`save.dump`), not
   generated code — parameters are components, so a tuned result is data.

Locked in discussion since D1-D5 (assumed by D6, `modeling.md`, and the
learning direction):

8. **The runtime is non-LLM and the I/O is structured.** The first goal is an
   agentic system whose inputs and outputs are components, not natural
   language; an LLM may *help authoring* but never sits in the run-time
   decision path.
9. **The reuse layer is the priority, and it is semantic.** Islands, bridges
   and conjunction (D6) — a graph of foundational concepts, not a flat library
   — are what make a domain's concepts reusable. Highest uncertainty, so it is
   probed before anything is built on it.
10. **The model is executable, not declared.** The model is the world (its
    rules) plus reified actions; structure is *derived* from the code, never
    maintained beside it. No ontology (`modeling.md`).
11. **Three learning sources, three artifacts.** Stated rules write
    **structure**; examples fit **values**; feedback refines values and makes
    new examples. Sources are *adjudicated*, never averaged; a conflict is a
    first-class gap.
12. **One grammar, many generators.** Structure may be proposed by an LM, an
    evolutionary search, or a human; it is verified by the gates and frozen
    before tuning, so the generator is swappable.
13. **Rules are data, and the loop reads one control channel** (D7). A rule
    is identified by a content hash and reified as a `RuleCard`; a
    `RuleControl` component — read by the loop at the top of each tick — may
    DISABLE or REPRIORITISE a rule without editing it, and may only subtract
    or reorder (the derived gate still decides dormancy). Structure is
    IR-native: a closed semantics whose analysis is TOTAL, which is what makes
    an EA safe to admit. The runtime selects among a FROZEN rule set; it never
    rewrites one.

## Principles carried forward (not up for re-litigation here)

- **No rule may block** (`architecture.md`): external I/O is a deposited
  request answered later, never a call in place.
- **Abstention must be structural** (`PRINCIPLES.md`): a wrong conclusion is
  worse than a missing one.
- **Declare, never infer** (`docs/tuning.md` point 1; `analyze.py`'s
  refuse-rather-than-guess).
- **Derive from the AST** (`analyze.py`): reads/writes and, later, the
  tunability lint come from walking the rule's own source, not from a person's
  declaration that can drift.
- **Tune values, never structure** (`docs/tuning.md`) — **scope retired by
  D5**: structure may now be machine-*translated* from a corpus and frozen,
  but the discipline the rule protected (frozen operators, verification gates,
  freeze-before-tune) is preserved. See `PRINCIPLES.md`, "What is
  machine-derived, and at which layer," and `docs/plan-forge.md`.

## Phase roadmap

Order is dependency-driven. Each phase is independently shippable and testable.

| Phase | Deliverable | Depends on | Design doc |
|---|---|---|---|
| 0 | The design docs, reviewed | — | D1-D6 |
| 1 | **Calibration kit**: `Scenario`/`Knob`/`replay`/`search` promoted to `loopingrules_calibration`, with pluggable trace source, replay caching, train/eval split, mean +/- variance, plateau/sensitivity report | — | D3 |
| 2 | **Memory**: instrumented change log, read API, `analyze` exception, sharpened signatures | — | D1 |
| 3 | **Author surface + patterns**: co-located knob declaration + classification, tunability linter, curated patterns each exposing its tunable surface | 1, 2 | D3, D2 |
| 4 | **Checks as control** (slow timescale) — **built**: `checks` (the pure vocabulary) + `adapt` (the between-episode adapter) + Experiment 8 (`examples/drift.py`) | 2, 3 | D4 |
| 5 | **Tools / external world**: tool-channel stdlib, environment tape/cache, effect fencing, calls-to-competence axis | 2, 3 | (separate doc) |
| 6 | **Descriptors** (optional): rules return change-lists; atomicity, validation, rules-as-data | 2 | (separate doc) |
| 7 | **Fast-timescale adaptation + end-to-end exemplar**: in-run controller rules, plus one non-toy agentic domain calibrated end to end and a written author walkthrough | 4, 5 | D4 |
| 8 | **The forge**: corpus → catalog — **partial**: M0-M2 (IR/gates/freeze) and the EA generator (`evolve`) built; the corpus and LM not | 1, 3 | D5 |
| 9 | **Reuse layer (D6)**: islands/bridges/conjunction promoted and *folded in*; the spike's debt paid; the cross-island read graph that catches spooky coupling | 3 | D6 |
| 10 | **Modeling**: reified actions (schema + deltas + executor), an action algebra, and a planner over schemas against the forked world | 9 | `modeling.md` |
| 11 | **Hybrid learning**: the three-source loop (stated rules / examples / feedback), with structure, values and refinement kept on separate artifacts | 7, 10 | `study-guide.md` (D8 pending) |
| 12 | **Reflection + IR-native**: rule hash and `RuleCard` reification folded in, the control channel (`RuleControl` read by the loop), and the IR moved into a frozen engine core with `analyze` re-targeted onto it and `analyze`-on-Python kept as an audit | 6 | D7 |

Phase 1 is the first build (the choice made in discussion). Phases 2 and 3 are
the ones that make the workflow real; 4-7 are the payoff; 8 is the structure
authoring layer; 9-11 are the semantic/agentic layer the product thesis finally
rests on.

## Cross-cutting work

- **The tunability linter** (D3): reuses `analyze`'s AST walk to flag a rule
  that hard-codes a threshold where it should read a knob. This is what makes
  the product thesis *enforceable* rather than advisory.
- **The reproducibility gate** (D1, D3): replay twice, same trace hash, before
  any score is trusted (`docs/tuning.md` already asks for this).
- **Documentation**: every pattern and every knob surface gets a docstring in
  the repo's existing style — what it does, and *what it does not settle*.
- **Tests**: the repo's suite is the contract. Each phase adds its own
  `tests/test_*` and keeps the whole suite green.
- **One grammar, many generators** (locked 12): the forge IR is the interface;
  an LM, an evolutionary search, and a human all *propose* into it, and the
  gates dispose. Nothing is trusted because of who proposed it.

## How success is judged

1. An author can take a new domain from zero to a calibrated, deployable tuned
   world without reading `docs/tuning.md` — the workflow itself is the doc.
2. The linter catches the "uncalibratable rule" (a hard-coded threshold) the
   way `analyze` catches an un-derivable read.
3. The same checks that tune offline can be wired as a controller without
   rewriting them (D4), demonstrating calibration-as-drift-response.
4. The tuned artifact is data (a saved world), versioned and reproducible.
5. The agent's model is *executable and reasoned over* — reified actions plus a
   planner — not merely run (`modeling.md`).
6. Learning mixes stated rules, a few examples, and live feedback, with
   conflicts surfaced rather than smoothed (`study-guide.md`).

## Open questions carried across docs

- Log retention/size policy for a long-lived session (D1).
- Trace serialisation format and whether a trace is itself `save`-able (D2).
- How preferences/labels are elicited from a human, practically (D2).
- Whether the controller is authored as rules (in-substrate) or as an external
  service reading the trace (D4).
- Whether `circuits`-style rules-as-data is revived, and if so when (Phase 6).
- Whether the scheduler read lives in the loop core or a `scheduler` module,
  and whether a `RuleCard` is one component per rule or a single catalog (D7).
- Whether the IR becomes an engine core with `analyze` re-targeted onto it,
  and what the rule hash is over the IR datum rather than the source (D7).
- Whether an action schema is the *source* the executor realizes, or a
  *derived view* checked against it; and whether the planner is in-substrate or
  an external search over the forked world (`modeling.md`).
- How the three learning sources adjudicate a conflict, and how confidence is
  attached to each (`study-guide.md`).
- Whether an evolutionary or ILP learner *replaces* the forge's translation or
  *complements* it, and where the two share the grammar (`study-guide.md`).
- Whether a probabilistic / belief layer can coexist with the determinism gate.
