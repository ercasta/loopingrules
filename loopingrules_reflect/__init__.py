"""`loopingrules_reflect` -- the reflection probes (see
`docs/plan-reflection.md`, D7).

These exist to answer the two load-bearing questions of the IR-native /
control-channel direction *before* anything is built on them:

- `r0.py` -- RUNTIME: can a rule read what other rules ARE and what they HAVE
  DONE, and change the schedule with `reflect.RuleControl`, while the rules it
  controls stay unchanged? **Yes** (it tames a hot loop that nothing else
  could settle, and an oscillating controller is caught by the budget).
- `r1.py` -- STATIC: can the forge IR be analyzed WITHOUT the Python AST,
  totally, agreeing with `analyze` on the lowered Python? **Yes** (12/12
  rules agree; a verbatim helper must DECLARE its reads, or the analysis
  refuses rather than under-reports).

Pinned by `tests/test_reflect_r0.py` and `tests/test_reflect_r1.py`.
"""
