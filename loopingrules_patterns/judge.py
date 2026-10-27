"""`judge` -- the threshold-judge pattern: a domain PROJECTS a normalized
`Risk` claim about an entity onto the world, and one oblivious rule flags
anything past a tolerance the judge itself owns.

A domain's own rule deposits `Risk(level, reason)` onto whatever it is
reasoning about -- "this is how concerning proceeding would be", `level` in
`[0.0, 1.0]`, `reason` a short human-readable account -- and `flag_too_
risky`, below, reads only that projection. It has never heard of a listing,
a purse, a deadline or a card, and imports nothing from any domain: it is
the narrow shape `DECISION_PATTERNS.md`'s deleted `arbitration.py` described,
one property wide. `RiskTolerance(max_level)` is the judge's own knob,
deliberately separate from any domain's own risk knobs
(`examples.cards.RiskProfile`, which feeds the PROJECTION, not the judgment)
-- the threshold a judge applies belongs to the judge, not to whichever
domain happened to install it first.

Promoted from `examples/judge.py` (see `docs/plan.md`, Phase 3) as the first
pattern in this library, because it already had what promotion asks for: a
second and third domain depending on it at RUNTIME (`examples.cards`,
`examples.market` and `examples.shopping` all install it), and a declared
tunable surface (`@tunable`). `cards` and `shopping` import these exact
objects, never same-shaped copies; `tests/test_examples_bridge.py` pins that
identity.

What this does NOT settle: whether one `Risk` shape fits a domain that wants
a genuinely different KIND of "how concerning". The evidence so far is two
projections sharing it without alteration -- resource exhaustion in `cards`,
time pressure in `shopping` -- which is real but not universal.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient
from loopingrules_calibration import Knob, tunable


@dataclass(frozen=True)
class Risk:
    """A domain's own claim about how risky proceeding with something is,
    normalized so an oblivious reader can compare it to a threshold it
    also did not derive: `level` in `[0.0, 1.0]`, `reason` a short,
    human-readable account of what drove the number """
    level: float
    reason: str


@dataclass(frozen=True)
class RiskTolerance:
    """The judge's own knob, singleton -- how much `Risk.level` it will
    tolerate before flagging something `TooRisky`. Deliberately separate
    from any domain's own risk knobs (`examples.cards.RiskProfile`, which
    feeds the PROJECTION, not the judgment) -- the threshold a judge
    applies belongs to the judge, not to whichever domain happened to
    install it first."""
    max_level: float


@transient
@dataclass(frozen=True)
class TooRisky:
    pass


@tunable(Knob(RiskTolerance, "max_level", 0.0, 1.0, steps=5))
def flag_too_risky(w) -> None:
    """`TooRisky` iff some entity's own `Risk.level` exceeds the judge's
    `RiskTolerance.max_level` -- both directions, every tick, the same
    "recompute fresh, never cache" discipline `examples.cards.tag_
    affordable` already uses, because `Risk` itself is expected to be
    recomputed fresh by whatever domain rule projects it, not derived
    once and left stale.

    Abstains -- touches nothing -- when no `RiskTolerance` has been
    seeded.

    `max_level` is this rule's DECLARED tunable surface
    (`@tunable(Knob(...))`, see `loopingrules_calibration.surface`), so
    `knobs(loop)` collects it from any domain that installs this rule, and
    `loopingrules_calibration.lint` holds the rule to it: the comparison
    below reads `tolerance.max_level`, never a literal, which is exactly
    what the linter is for.
    """
    tolerance = w.the(RiskTolerance)
    if tolerance is None:
        return
    for entity, risk in w.each(Risk):
        if risk.level > tolerance.max_level:
            w.attach(entity, TooRisky())
        else:
            w.detach(entity, TooRisky)
