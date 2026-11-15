"""`loopingrules_ux` -- probes for the user-experience plan (Plan U).

A spike package, deliberately **not** in `pyproject.toml`'s `packages=`, the
same posture `loopingrules_islands` and `loopingrules_forge` take. Each module
is a named probe from `docs/plan-ux.md`, pinned by its own `tests/test_ux_*`.

* `s5` -- the walking skeleton: a **grown controller** composes two independent
  islands into a multi-step, cross-island trajectory scored by a mechanical
  example.
* `s3` -- the ambiguity probe: **two** islands both handle one term; a controller
  resolves it by context via `RuleControl`.
* `s6` -- the correction pass's seam: the train trip with a budget, its candidate
  applications **materialized**, a **distinct** decision-tree evaluator that
  selects one and writes nothing, and the selection recorded to application
  memory (ADR-13).
"""
