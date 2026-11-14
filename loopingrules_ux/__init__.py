"""`loopingrules_ux` -- probes for the user-experience plan (Plan U).

A spike package, deliberately **not** in `pyproject.toml`'s `packages=`, the
same posture `loopingrules_islands` and `loopingrules_forge` take. Each module
is a named probe from `docs/plan-ux.md`, pinned by its own `tests/test_ux_*`.

* `s5` -- the walking skeleton: a **grown controller** composes two independent
  islands into a multi-step, cross-island trajectory scored by a mechanical
  example.
"""
