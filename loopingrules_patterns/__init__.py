"""`loopingrules_patterns` -- the standard library of reusable patterns.

`docs/plan.md`: the engine ships no domain vocabulary by design, so the
shared vocabulary that IS worth shipping lives here -- curated patterns,
each exposing a DECLARED tunable surface (`loopingrules_calibration`), that
a domain installs and calibrates like any other rule.

    from loopingrules_patterns import judge

A pattern comes in one of two shapes, and both live in this one package:

* a **bridge** -- a domain-oblivious reader over a thin shape several
  domains PROJECT onto, so the reader never learns what produced it
  (`judge`); and
* a **shape** -- a component vocabulary a domain instantiates, plus the
  rules over it.

Only patterns with real users are promoted here, on `README.md`'s standing
bar: a second domain must depend on the pattern AT RUNTIME, not merely in a
test file written to feed it.

## Shipped

* `loopingrules_patterns.judge` -- the threshold judge:
  `Risk(level, reason)` / `RiskTolerance(max_level)` / `flag_too_risky` ->
  `TooRisky`. A domain projects a normalized `0..1` claim onto `Risk`; the
  oblivious rule flags anything past the tolerance. Three domains install
  it (`examples.cards`, `examples.market`, `examples.shopping`).
* `loopingrules_patterns.memory` -- the DECLARED tunable surface for
  `loopingrules.memory`: the short-term-memory mechanism stays in the
  engine (it reads the change log, an engine primitive), and this module
  attaches the `@tunable` knobs to its `remember`/`forget` rules so
  `knobs(loop)` and the linter can see them.

What is NOT here yet, named so it is not mistaken for settled: the other
candidates `docs/plan.md`'s Phase 3 lists -- a scored contest (`examples.
decide`), the shape patterns (catalog+inventory, wants/goal,
question/investigation, ...) -- are candidates, not shipped.
"""

from __future__ import annotations

from . import judge, memory

__all__ = ["judge", "memory"]
