"""`loopingrules_forge` -- the M0/M1 spikes (see `docs/plan-forge.md`, D5).

Nothing here is a commitment to a real package layout -- these exist to
answer D5's first two milestones *before* any LLM or corpus appears:

- `m0.py` -- can a small IR express a real domain (`cards`, all 12 rules),
  and lower back to Python with the same behaviour? **Yes** (same `signature`,
  driven by real command lines).
- `m1.py` -- are the gates strong enough to reject wrong structure and quiet
  enough to accept right structure? **Yes** (eight mutants each trip their
  gate; two right candidates trip nothing).
- `m2.py` -- is a frozen compiled catalog a well-defined artifact the
  calibration kit can tune reproducibly? **Yes** (deterministic freeze; version
  tracks structure, not knob values; frozen reproduces its source; plateaus).

Pinned by `tests/test_forge_m0.py`, `tests/test_forge_m1.py` and
`tests/test_forge_m2.py`. `fixtures.py` holds the components only the M1
mutants use.
"""
