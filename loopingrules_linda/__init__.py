"""`loopingrules_linda` -- a SPIKE: a minimal Linda tuple space, and an A/B that
checks `docs/patterns-oblivious-composition.md` §7.

Not a shipped package: deliberately absent from `pyproject.toml`'s `packages=`,
the same posture `loopingrules_islands` and `loopingrules_forge` take. It exists
to *falsify* the doc's claim about keyed reads vs positional templates, not to be
folded in.
"""

from __future__ import annotations

from . import ab, linda
from .linda import ANY, Blocked, TupleSpace, Var

__all__ = ["ab", "linda", "ANY", "Blocked", "TupleSpace", "Var"]
