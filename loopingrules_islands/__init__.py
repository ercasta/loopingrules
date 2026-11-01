"""`loopingrules_islands` -- a SPIKE for the islands/bridges/stigmergy shape.

Not a shipped package and deliberately absent from `pyproject.toml`'s
`packages=` (the same posture `loopingrules_forge` takes): this exists to
*discover* the good patterns and antipatterns of the semantic-foundation
layer before any of it is folded into a real home.

The shape under test (`docs/plan-islands.md`, D6):

* an **island** is a vocabulary + the rules over it + its own decision
  process. It is CLOSED IN AUTHORSHIP (nothing here imports a domain) and
  OPEN IN READS (any rule anywhere may read a role it confers);
* a **bridge** is a domain's own projection of a fact onto the island's
  thin shape -- the geometry `loopingrules_patterns.judge` already ships;
* **stigmergy** is a rule firing because a role appeared, nobody having
  called anyone -- and, at its sharpest, a **composition** rule reading
  across two islands and concluding something neither can.

`i0.py` is the first probe. The fold-in obligation is tracked in `TODO.md`
on purpose: `DECISION_PATTERNS.md` was deleted in `cdf98d6` because a prose
design that nothing pins does not survive. So every claim here is pinned by
`tests/test_islands_i0.py`, and `docs/plan-islands.md` records only what a
probe holds up.
"""

from __future__ import annotations

from . import funds, items

__all__ = ["funds", "items"]
