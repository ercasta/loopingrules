"""`loopingrules_ux` -- probes for the user-experience plan (Plan U).

A spike package, deliberately **not** in `pyproject.toml`'s `packages=`, the
same posture `loopingrules_islands` and `loopingrules_forge` take. Each module
is a named probe from `docs/plan-ux.md`, pinned by its own `tests/test_ux_*`.

* `s5` -- the walking skeleton: a **grown controller** composes two independent
  islands into a multi-step, cross-island trajectory scored by a mechanical
  example.
* `s3` -- the ambiguity probe: **two** islands both handle one term; a controller
  resolves it by context via `RuleControl`.
* `s6` -- the correction pass's deepest claim, **per step**: the train trip with
  a budget, in three models (train, planning, budget). Each tick materializes the
  candidate **moves**, the budget excludes the unaffordable, a **distinct** pure
  scorer selects one and writes nothing, the trip is **executed**, and the
  selection is **recorded** -- so the trajectory is a sequence (ADR-13).
* `t1` -- trajectories and **coverage**: a fixed model set covers held-out
  **combinations** of its concepts with no per-case code, **gaps** an unknown
  concept, and buys several use cases per added rule (`docs/plan-scale-probe.md`
  §5, axis B).
"""
