# D3 — Calibration API, knob surface, and the tunability linter

Phase 1 (first build) plus the author surface of Phase 3. Lifts
`examples/tuning.py` from a research instrument into the author-facing
calibration kit, adds co-located knob declaration, and adds the mechanism that
makes the product thesis enforceable.

**Status: Phase 1 built; the author surface and the linter built.** A rule
declares its tunable surface with `@tunable(Knob(...))`
(`loopingrules_calibration.surface`), `knobs(loop)` collects it from the
rules a domain actually registered, and `loopingrules_calibration.lint`
holds those rules to it — flagging a numeric literal where the rule should
read a component, reporting a knobbed rule `analyze` cannot see as
`unlintable`, and excusing a literal only through `allow=(...)` with a
reason. The pattern library the phase also names is not built.

## The four-way contract

`examples/tuning.py`'s `search(install, scenarios, knobs, scorer)` already
implies the whole API, cleanly separated:

| Axis | What it is | Where it lives |
|---|---|---|
| **Domain** | `install(loop, **kwargs)` | the author's package |
| **Data** | scenarios + checks (D2) | a dataset artifact |
| **Tunables** | `Knob` declarations | co-located with the domain |
| **Objective** | `scorer(Trace) -> float` | outside the engine (D2) |

The calibration kit is the glue and the reporting; it owns none of the four.

## Package shape

Same repo, second package (locked): `loopingrules_calibration`, a sibling of
`loopingrules/`, imported the way `examples/` already is
(`pyproject.toml`'s `pythonpath = ["."]`). It must not import a domain and
`loopingrules/` must not import it.

Public surface (built on the existing `tuning.py`, promoted and extended):

```
Scenario, Knob, Trace, Replay, Best        # data
replay(scenario, install, knobs, values)   # deterministic replay (pluggable trace source)
read_knobs, write_knobs                    # refuse rather than guess (unchanged)
grid, search                               # optimizer-free baseline
calibrate(install, dataset, knobs, scorer, seeds=...) -> Report
Report: best, plateaus, sensitivity, train_score, eval_score, variance, signature
```

## Knobs: declaration, classification, ranges

Extend `examples/tuning.py`'s `Knob` (which already refuses to write a knob
whose component was never seeded — a tuner that silently skipped a missing
knob would search a surface that is not the one the rules read):

```
Knob(component, field, low, high, steps, integer=False, scope="offline")
```

**Co-located with the rule.** Built as a decorator: `@tunable(Knob(...))`
sits on the rule that reads the component, in the domain's own module, so
the declaration cannot drift from the rule. Explicit, never inferred
(`docs/tuning.md` point 1: the domain must declare its tunable surface). A
knob read by several rules may be declared on more than one of them;
`knobs(loop)` de-duplicates, because it is still one knob. The knob is parked
as a plain attribute on the rule function — the same trick `Loop.rule`
already uses for its derived gate — so the engine never learns about
calibration.

**Classification (`scope`) — locked default `offline-only`:**

- `scope="offline"` (default): tunable in the lab, **frozen at deploy**.
- `scope="runtime"`: may be moved by an online controller (D4). Requires
  explicit bounds **and** the controller's rate limit / hysteresis (D4).

This makes the runtime-tunable set small and auditable. The declaration is
where "which knobs are safe to move online" is decided once, by an author, not
guessed by a controller.

## The tunability linter

`analyze.py` already derives a rule's reads/writes by walking its own AST. The
same walk can flag the failure mode the product thesis is *against*: a rule
that compares against a **literal** where it should read a component knob.

- Design rule (`docs/tuning.md`): *a tunable rule never hard-codes its
  threshold; it reads a component.* The linter enforces it.
- Heuristic: a comparison (`<`, `<=`, `>`, `>=`, `==`) between a field read and
  a **numeric literal**, in a rule that is registered with a declared knob over
  the same component, is flagged with file/line and the suggested knob.
- Refuse-rather-than-guess: an analyzable rule lints; an opaque one is
  reported as unlintable, not passed silently — the same posture as `analyze`.
- Explicit suppression with a reason (some constants are genuinely structural,
  not calibration).

This is what turns "calibration matters" from a slogan into a check an author
runs.

**Built** as `loopingrules_calibration.lint(rules, allow=(), strict=False)`,
over `analyze.literals` — the same AST walk, reporting each numeric-literal
comparison with its real file/line and the rule's declared knobs as the
candidates it should have read. Only a rule that declares a surface is
linted at all; a knobbed rule `analyze` refuses is recorded `unlintable`,
never passed as clean. There is **no silent auto-exclusion** — even a `== 0`
sentinel is flagged until excused through `allow` with a reason, and every
excuse is reported back. The default is to report; `strict=True` raises
`LintError` on a finding or an unlintable knobbed rule, for a CI gate.

## replay: caching and the pluggable trace source

Two changes to `replay`, both necessary for real (not research) use:

1. **Caching.** `tuning.py` deliberately has none ("a grid over a handful of
   knobs is small"). Real authors replay expensive domains, and a grid over
   several knobs is not small. Memoise `replay` by `(install, scenario,
   knobs, values)` — safe because replay is deterministic (asserted below).
   This is the offline analogue of the environment-tape cache.
2. **Pluggable trace source.** Today the trace is `(fired, final world,
   replies)`. It must be constructible today and **sharpen** automatically when
   D1 lands (change log) without changing the kit's call sites. `_signature`
   hashes whatever the trace source provides.

## search: baseline, then noise-aware

- **Grid is the honest baseline** (an optimizer confound must not sit on the
  parameter axis; `docs/tuning.md`). Keep it.
- The objective is **step-shaped** (piecewise-constant: a threshold crossing
  flips a tag and switches branches) so **gradients are meaningless**; use
  derivative-free search and *report plateaus*.
- With tools (Phase 5) the objective also becomes **stochastic**: one knob
  setting scores differently across runs. Then a grid point needs **repeats**,
  and comparison needs an error bar. Add a racing/stopping rule so real calls
  are not spent separating noise. Never gradient, still — the shape is
  unchanged, only noisy on top.
- **Damping the search**: replay caching makes the offline inner loop cheap;
  the outer loop stays deterministic per `(knobs, scenario)`.

## The report: making calibration legible

The author-facing payoff, built on the trace signature:

- **Plateaus / behavioural equivalence classes**: many settings, one
  trajectory — report them, do not treat them as noise (`docs/tuning.md`).
- **Sensitivity**: which knobs actually move the trajectory-equivalence class,
  and which are flat (a knob that does nothing is a finding).
- **Train vs. eval** scores, **mean +/- variance** over repeats (the
  learning-curve harness already asks for "mean ± variance, not just the
  mean").
- **Mismatch warning**: when a per-island/local objective disagrees with the
  trajectory-level score (the covariate-shift hazard `docs/tuning.md` names,
  and the load-bearing assumption of Experiment 4). Support island-local
  datasets *and* trajectory scoring, and report the gap.

## Deployment

Locked: the artifact of calibration is a **saved world** (`save.dump`), not
generated code — parameters are components. Deployment = load the domain code
plus the tuned parameter world. Version it with:

- the knob values,
- the **trace signature** (reproducibility),
- the dataset/scorer version it was tuned against (the scorer is a prior).

Re-calibration is expected as the dataset grows or the world drifts (D4).

## What this does not settle

- Search beyond grid + racing (randomised/multi-start; Bayesian optimisation is
  plausible but not decided).
- Multi-objective calibration (cost vs. success vs. safety) — likely needed,
  not designed here.
- How tuned-world versions are stored and rolled back.
- Whether the linter is a hard error or a warning by default.

## Open questions

1. Does `scope="runtime"` belong on `Knob`, or on a separate runtime-surface
   declaration? **Settled: on `Knob`** — it already is, and
   `runtime_knobs(knobs)` selects the subset.
2. Should the linter be wired into `Loop.rule` (registration-time) or run as
   an explicit tool/CI step? **Settled: an explicit tool** — the engine must
   not import calibration, and `lint(..., strict=True)` gives a CI step its
   hard failure.
3. How many repeats per grid point before an error bar is trustworthy — fixed
   K, or adaptive racing?
4. Does the report live in the package, or is it generated as a Markdown
   artifact an author reads? **Settled: both** — `LintReport` is the
   structured artifact and `LintReport.to_markdown()` is for reading.
