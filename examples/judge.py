"""`judge` -- one domain-oblivious rule, testing whether a single shared
`Risk` shape can serve any domain's judge without the judge knowing what
domain it is.

A judge that reasons over `realizes(option,
property)` -- a domain-specific rule PROJECTS its own facts onto a
shared property, and the judge reads only the projection, oblivious to
what produced it (*"pizza realizes carbs, carbs realizes energy"*). This
module is that shape, narrowed to one property: `Risk` is what a domain
projects onto; `RiskTolerance` is the judge's own threshold; `flag_too_
risky` (below) is the whole judge. 

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
