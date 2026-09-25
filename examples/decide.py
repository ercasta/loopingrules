"""`decide` -- one domain-oblivious rule, testing whether the "several
rivals, one winner" half of `DECISION_PATTERNS.md`'s vocabulary
(`candidate`/`ranked`/`winner`) generalizes past a single domain the way
`examples.judge`'s scalar-threshold half (`Risk`/`RiskTolerance` ->
`TooRisky`) already does.

## What this is testing

`world.py`'s own `Proposal`/`arbitrate` already resolve several rivals for
one `occasion` down to one winner -- but only by "first registered wins,"
because `arbitrate` is deliberately ignorant of which candidate is BETTER
(see `README.md`'s Scope section: "What is deliberately NOT here is the
arbiter -- which candidate wins, and on what grounds"). `DECISION_
PATTERNS.md` names the fuller shape a SCORED contest needs
(`ranked`/`winner`, Forced vs. Ambiguous), but its own generic engine
(`arbitration.py`) was built, proven inside `pystrider`, and still deleted
from `loopingrules` -- "a domain that wants that pattern writes its own
components and its own generic reader over them," the same line `judge.py`
already quotes for itself.

This module is that reader, narrowed the same way `judge.Risk` is: a domain
PROJECTS its own rivalry onto `Option`/`Score` -- "this entity is one way to
resolve occasion X, and here is how good it is" -- and `pick_winner` reads
only the projection, oblivious to what produced it. It imports nothing from
`examples.trip` and knows nothing about a `Frontier` or a `TripRequest` --
it would run unchanged over an `Option`/`Score` pair projected by a wholly
different domain's own rivalry.

## What this does NOT settle

Whether one `Option`/`Score` shape holds across two UNRELATED domains, or is
secretly two domains' different ideas of "rival" wearing one field name, is
exactly what handing this to a SECOND domain would test -- see `judge.py`'s
own docstring for the identical caveat about `Risk`. Today only
`examples.trip`'s own `nominate_itinerary` projects onto it. Also not
settled: what a BLOCKED occasion (no candidate at all, or every candidate
tied) should do beyond staying silent -- `DECISION_PATTERNS.md`'s `needs`/
Pending is real vocabulary for that and is not implemented here; see this
module's own `pick_winner` for the narrower Forced/Ambiguous split it does
implement.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient


@dataclass(frozen=True)
class Option:
    """A domain's own claim that this entity is one rival way to resolve
    decision `occasion` -- a plain entity id, the same untyped-occasion
    idiom `loopingrules.world.Proposal.occasion` already uses. Several
    `Option`s may name the same `occasion`; `pick_winner` is what compares
    them."""

    occasion: int


@dataclass(frozen=True)
class Score:
    """How good this `Option` is, on whatever scale the domain projecting
    it finds natural -- **higher is better**, by convention, the same
    normalization `judge.Risk` documents for its own `0..1` scale. A
    domain that scores "lower is better" (a cost, an elapsed time) negates
    on the way in rather than teaching this module a second convention."""

    value: float


@transient
@dataclass(frozen=True)
class Winner:
    """Attached by `pick_winner`, and only by `pick_winner`, to the
    `Option` carrying the unique top `Score` for its own `occasion`.
    Recomputed fresh every tick, both directions (attached to a new
    leader, detached from a former one), the same "no caching" posture
    `examples.cards`'s own tag rules already use -- `Score` itself is
    expected to keep moving while a domain's own search is still live."""


def pick_winner(w) -> None:
    """For every `occasion` named by at least one `Option`: attach
    `Winner` to the `Option` with the strictly highest `Score`, if exactly
    one holds that score; detach `Winner` from every other `Option` naming
    the same `occasion`, including a former unique leader a newer, better
    `Option` has since overtaken.

    An exact tie for the top `Score` attaches `Winner` to NOBODY -- refuse
    rather than guess between two rivals that scored identically, the same
    discipline `PRINCIPLES.md` calls non-negotiable ("a wrong conclusion is
    worse than a missing one") and the Forced/Ambiguous split in
    `DECISION_PATTERNS.md` exists to name. This rule never reads anything
    but `Option`/`Score` -- no import of, or reference to, any specific
    domain's own components.
    """
    by_occasion: "dict[int, list]" = {}
    for entity, option, score in w.each(Option, Score):
        by_occasion.setdefault(option.occasion, []).append((entity, score.value))

    for rows in by_occasion.values():
        best_value = max(value for _entity, value in rows)
        leaders = [entity for entity, value in rows if value == best_value]
        winner = leaders[0] if len(leaders) == 1 else None
        for entity, _value in rows:
            if entity is winner:
                w.attach(entity, Winner())
            else:
                w.detach(entity, Winner)
