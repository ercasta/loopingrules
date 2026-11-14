"""`judge` -- the threshold-judge pattern: a domain PROJECTS a normalized
risk claim about an entity into the world, and one oblivious rule flags
anything past a tolerance the judge itself owns.

A domain's own rule writes `risk_level` (in `[0.0, 1.0]`) and `risk_reason`
(a short human-readable account) onto whatever it is reasoning about -- "this
is how concerning proceeding would be" -- and `flag_too_risky`, below, reads
only that projection. It has never heard of a listing, a purse, a deadline or
a card, and imports nothing from any domain: it is the narrow shape
`DECISION_PATTERNS.md`'s deleted `arbitration.py` described, one property
wide.

Under the attribute substrate (`docs/plan-attributes.md`, D8) the judge owns
two NAME conventions, not two classes: the projected `risk_level`/
`risk_reason`, and the singleton `max_level` (the judge's own knob,
deliberately separate from any domain's own risk knobs -- the threshold a
judge applies belongs to the judge). `too_risky` is the flag it writes back.

What this does NOT settle: whether one `risk_level` convention fits a domain
that wants a genuinely different KIND of "how concerning".
"""

from __future__ import annotations

from loopingrules_calibration import Knob, tunable


RISK_LEVEL = "risk_level"
RISK_REASON = "risk_reason"
TOLERANCE = "max_level"
TOO_RISKY = "too_risky"


def seed_tolerance(world, max_level: float):
    """Seed the judge's singleton knob -- the one entity carrying
    `max_level`. Idempotent: an existing tolerance is left alone."""
    row = world.first(TOLERANCE)
    if row is not None:
        return row[0]
    entity = world.spawn()
    world.set(entity, TOLERANCE, max_level)
    return entity


@tunable(Knob(TOLERANCE, 0.0, 1.0, steps=5))
def flag_too_risky(w) -> None:
    """`too_risky` iff some entity's own `risk_level` exceeds the judge's
    `max_level` -- both directions, every tick, the same "recompute fresh,
    never cache" discipline, because `risk_level` itself is expected to be
    recomputed fresh by whatever domain rule projects it.

    Abstains -- touches nothing -- when no `max_level` has been seeded.

    `max_level` is this rule's DECLARED tunable surface
    (`@tunable(Knob(...))`), so `knobs(loop)` collects it from any domain
    that installs this rule.
    """
    tolerance = w.first("max_level")
    if tolerance is None:
        return
    ceiling = tolerance[1]
    for entity, level in w.each("risk_level"):
        if level > ceiling:
            w.mark(entity, "too_risky")
        else:
            w.unmark(entity, "too_risky")
