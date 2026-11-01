"""The `items` island -- a foundation vocabulary, the rules over it, and its
own DECISION.

An island is CLOSED IN AUTHORSHIP, OPEN IN READS (`docs/plan-islands.md`):
nothing here imports a domain, and nothing here knows a `Candidate` came
from a card, an auction lot or a shopping list -- but every rule here is
written to be read and built on by rules that live elsewhere. That is what
`Item` is for: a role, conferred by this island's own decision, that turns
an entity into something any OTHER island's rules may act on.

The geometry is `loopingrules_patterns.judge`'s, one level up: a domain owns
the PROJECTION (it writes the thin `Candidate` shape), the island owns the
DECISION (it reads only that shape and confers the role). `judge` thresholds
a projected scalar into a tag; this confers a role. Same move.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient
from loopingrules_calibration import Knob, tunable


@dataclass(frozen=True)
class Candidate:
    """A domain's claim that some entity is a candidate for `Item`,
    normalized to ONE number so the island's decision never learns what
    produced it. `worth` is in the domain's own units; the island's
    `min_worth` is what is calibrated per domain (`@tunable`, below)."""
    worth: float


@transient
@dataclass(frozen=True)
class Item:
    """The role. Once attached, every rule over `Item` -- here, and in any
    other island -- may act on this entity, and neither this island nor the
    projecting domain had to know those rules exist. `@transient`: a
    conclusion, recomputed into existence rather than saved -- the same
    stance `judge.TooRisky` and `cards.Wanted` take."""
    worth: float


@dataclass(frozen=True)
class ItemsPolicy:
    """This island's own knob, singleton -- how much `Candidate.worth` it
    will accept before conferring `Item`. The threshold belongs to the
    island that applies it, not to whichever domain happened to install it
    first (`judge.RiskTolerance`'s own rule)."""
    min_worth: float


@dataclass(frozen=True)
class Inventory:
    """A conclusion THIS island derives from `Item` alone, kept in step with
    the roles present -- so any domain that promotes an entity is reflected
    here without this island ever hearing of the domain."""
    total: float
    count: int


@tunable(Knob(ItemsPolicy, "min_worth", 0.0, 100.0, steps=11))
def consider(w) -> None:
    """The island asking its OWN question: `Item` for every `Candidate`
    whose `worth` reaches the policy -- and only ever for entities that do
    not already carry `Item` (`without=Item`), which is what makes the rule
    IDEMPOTENT: once conferred, the entity leaves the loop and this rule
    contributes no further change, so the world settles.

    MONOTONE on purpose -- it never detaches. A revisable version is what
    lets a controller move the decision online; it is also where flicker
    lives, and this probe leaves that to a later one.

    Abstains when no `ItemsPolicy` is seeded, the same discipline `judge.
    flag_too_risky` takes: a role nobody configured a policy for is not
    conferred by default. `min_worth` is this rule's DECLARED surface, so
    `knobs(loop)` collects it and `lint` holds the rule to it -- no literal
    threshold ever hard-codes what reads a knob instead."""
    policy = w.the(ItemsPolicy)
    if policy is None:
        return
    for entity, candidate in w.each(Candidate, without=Item):
        if candidate.worth >= policy.min_worth:
            w.attach(entity, Item(candidate.worth))


def total_worth(w) -> None:
    """A rule over `Item` ALONE -- the payoff. It fires on any entity any
    domain promoted and has never heard of cards, lots or lists, the same
    obliviousness `judge.flag_too_risky` has for what produced a `Risk`."""
    total = 0.0
    count = 0
    for _entity, item in w.each(Item):
        total += item.worth
        count += 1
    found = w.first(Inventory)
    if found is None:
        w.spawn(Inventory(total, count))
    else:
        entity, current = found
        if (current.total, current.count) != (total, count):
            w.replace(entity, Inventory(total, count))


def seed(loop, min_worth: float = 0.0) -> None:
    """Seed this island's own policy, singleton -- the probe's stand-in for
    a domain seeding `judge.RiskTolerance` in its own `install`."""
    world = loop.world
    if world.first(ItemsPolicy) is None:
        world.spawn(ItemsPolicy(min_worth=min_worth))
