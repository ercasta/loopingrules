"""Components used only by M1's mutants, kept in their own module.

They live here, not in `m1`, because `python -m loopingrules_forge.m1` loads
`m1` under the name `__main__` -- so a mutant importing `Orphan` from
`loopingrules_forge.m1` would get a SECOND class object, not the one the
catalog holds, and the shape gate would flag it as undeclared. A plain,
single-name import module has no such doubling.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Ghost:
    """Declared nowhere in the catalog -- the shape mutant's component."""
    n: int


@dataclasses.dataclass(frozen=True)
class Orphan:
    """Declared in the catalog as rule-produced, but no rule produces it --
    the coherence mutant reads it."""
    pass
