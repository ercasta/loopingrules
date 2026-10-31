# Plan: engine + standard library + authoring/calibration workflow

Status: Phases 1-2 built, and Phase 3's author surface and linter with them;
the pattern library and the rest are design. This directory holds the
roadmap and five design docs (D1-D5, the fifth being the forge in D5).
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
| **Dataset kit** | Missing. No format, no capture, no labels/rankings, no train/eval split, no reporting. |
| **Memory / change log** | **Built (Phase 2)**: `Change` + `World.changes`/`recent`/`clear_changes`, transient and never saved, `Loop(capacity=...)`-bounded, with `Loop.tick` provenance and `analyze` gating on `changes(changed=...)`. |
| **Tools / external world** | Missing. Only the channel seam exists; no tape/cache, no effect fencing. |

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
| 0 | The five design docs, reviewed | — | D1-D5 |
| 1 | **Calibration kit**: `Scenario`/`Knob`/`replay`/`search` promoted to `loopingrules_calibration`, with pluggable trace source, replay caching, train/eval split, mean +/- variance, plateau/sensitivity report | — | D3 |
| 2 | **Memory**: instrumented change log, read API, `analyze` exception, sharpened signatures | — | D1 |
| 3 | **Author surface + patterns**: co-located knob declaration + classification, tunability linter, curated patterns each exposing its tunable surface | 1, 2 | D3, D2 |
| 4 | **Checks as control** (slow timescale): observe the completed episode, adjust knobs between runs (incremental re-calibration) | 2, 3 | D4 |
| 5 | **Tools / external world**: tool-channel stdlib, environment tape/cache, effect fencing, calls-to-competence axis | 2, 3 | (separate doc) |
| 6 | **Descriptors** (optional): rules return change-lists; atomicity, validation, rules-as-data | 2 | (separate doc) |
| 7 | **Fast-timescale adaptation + end-to-end exemplar**: in-run controller rules, plus one non-toy agentic domain calibrated end to end and a written author walkthrough | 4, 5 | D4 |
| 8 | **The forge**: corpus → catalog, verified and frozen, with NL-in/NL-out at the edges; ordered risk-first so the structural half (no LM) is proven before translation is attempted | 1, 3 | D5 |

Phase 1 is the first build (the choice made in discussion). Phases 2 and 3 are
the ones that make the workflow real; 4-7 are the payoff.

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

## How success is judged

1. An author can take a new domain from zero to a calibrated, deployable tuned
   world without reading `docs/tuning.md` — the workflow itself is the doc.
2. The linter catches the "uncalibratable rule" (a hard-coded threshold) the
   way `analyze` catches an un-derivable read.
3. The same checks that tune offline can be wired as a controller without
   rewriting them (D4), demonstrating calibration-as-drift-response.
4. The tuned artifact is data (a saved world), versioned and reproducible.

## Open questions carried across docs

- Log retention/size policy for a long-lived session (D1).
- Trace serialisation format and whether a trace is itself `save`-able (D2).
- How preferences/labels are elicited from a human, practically (D2).
- Whether the controller is authored as rules (in-substrate) or as an external
  service reading the trace (D4).
- Whether `circuits`-style rules-as-data is revived, and if so when (Phase 6).
