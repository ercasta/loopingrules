"""`judge` -- one domain-oblivious rule, testing whether a single shared
`Risk` shape can serve any domain's judge without the judge knowing what
domain it is.

## What this is testing

A chat about this repo asked whether `loopingrules` should ship a "vast
set of common components" (`good`/`bad`/`risk`/`evaluation`...) as a
lingua franca between domains. `README.md`'s own history already argues
against exactly that: a generic `fact`/`state`/`deny` vocabulary
(`facts.py`/`arbitration.py`) was built, proven inside `pystrider`, and
still deleted from this package -- "nothing in this repository ever
imported any of the three... a domain that wants that pattern writes its
own components." A NAME is cheap to agree on; a SHAPE (what fields, what
scale, probability or expected-loss or a category) is not, and two
domains that emit a same-named component with two different shapes is a
worse failure than two domains with two different names for the same
idea -- it is the wrong-conclusion-is-worse-than-a-missing-one failure
`PRINCIPLES.md` names, except silent, because nothing would ever notice
the mismatch.

But `DECISION_PATTERNS.md`'s deleted `arbitration.py` already carried a
narrower version of the same instinct that survived as an argument even
after the code left: a judge that reasons over `realizes(option,
property)` -- a domain-specific rule PROJECTS its own facts onto a
shared property, and the judge reads only the projection, oblivious to
what produced it (*"pizza realizes carbs, carbs realizes energy"*). This
module is that shape, narrowed to one property: `Risk` is what a domain
projects onto; `RiskTolerance` is the judge's own threshold; `flag_too_
risky` (below) is the whole judge. It imports nothing from `examples.
cards` and knows nothing about a `Listing` -- it would run unchanged over
an entity from a wholly different domain that also learned to project a
`Risk` onto something of its own.

## What this does NOT settle

Whether one `Risk` shape -- a `level: float`, expected on a 0..1 scale --
actually holds across two UNRELATED domains, or is secretly two domains'
different ideas wearing one field name, is exactly what handing this to
a SECOND domain would test. Today only `examples.cards`'s own `tag_risk_
level` projects onto it, so the honest status is "one domain's own
projection did not have to fight the shape," not "the shape is proven
general" -- see `examples.cards`'s module docstring for what it projects
and why. Per `DECISION_PATTERNS.md`'s "grow it only at the rule that
actually collides," this stays in `examples/`, not generalized further
and not promoted into `loopingrules/`, until a second,
independently-authored domain actually needs to feed the same judge.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient


@dataclass(frozen=True)
class Risk:
    """A domain's own claim about how risky proceeding with something is,
    normalized so an oblivious reader can compare it to a threshold it
    also did not derive: `level` in `[0.0, 1.0]`, `reason` a short,
    human-readable account of what drove the number -- named, not just
    numeric, the same discipline `DECISION_PATTERNS.md`'s `ruled_out`
    wants for a veto ("a *named* reason... not an opaque number")."""
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


def flag_too_risky(w) -> None:
    """`TooRisky` iff some entity's own `Risk.level` exceeds the judge's
    `RiskTolerance.max_level` -- both directions, every tick, the same
    "recompute fresh, never cache" discipline `examples.cards.tag_
    affordable` already uses, because `Risk` itself is expected to be
    recomputed fresh by whatever domain rule projects it, not derived
    once and left stale.

    Abstains -- touches nothing -- when no `RiskTolerance` has been
    seeded: refuse rather than guess which threshold applies, the same
    discipline `PRINCIPLES.md` asks of every rule that can be uncertain
    ("Any new rule that can be uncertain must be able to produce nothing,
    structurally"). This rule never reads anything but `Risk` and
    `RiskTolerance` -- no import of, or reference to, any specific
    domain's own components.
    """
    tolerance = w.the(RiskTolerance)
    if tolerance is None:
        return
    for entity, risk in w.each(Risk):
        if risk.level > tolerance.max_level:
            w.attach(entity, TooRisky())
        else:
            w.detach(entity, TooRisky)
