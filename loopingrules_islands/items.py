"""The `items` island -- a foundation vocabulary, the rules over it, and its
own DECISION.

Under the attribute substrate (D8): an entity a domain PROJECTS onto carries
a `candidate` (a normalized worth); this island confers the `item` role as a
flag, and derives an `inventory` singleton. The island's own knob is the
singleton `min_worth`.
"""

from __future__ import annotations

from loopingrules_calibration import Knob, tunable


@tunable(Knob("min_worth", 0.0, 100.0, steps=11))
def consider(w) -> None:
    """`item` for every entity whose `candidate` worth reaches the policy --
    and only ever for entities that do not already carry `item`
    (`without="item"`), which makes the rule IDEMPOTENT: once conferred, the
    entity leaves the loop and the world settles.

    MONOTONE on purpose -- it never detaches. Abstains when no `min_worth` is
    seeded. `min_worth` is this rule's DECLARED surface."""
    policy = w.first("min_worth")
    if policy is None:
        return
    floor = policy[1]
    for entity, worth in w.each("candidate", without="item"):
        if worth >= floor:
            w.mark(entity, "item")


def total_worth(w) -> None:
    """A rule over `item` ALONE -- the payoff. It fires on any entity any
    domain promoted and has never heard of cards or lots."""
    total = 0.0
    count = 0
    for _entity, _t, worth in w.each("item", "candidate"):
        total += worth
        count += 1
    found = w.first("inventory")
    if found is None:
        entity = w.spawn()
        w.mark(entity, "inventory")
        w.set(entity, "total", total)
        w.set(entity, "count", count)
    else:
        entity = found[0]
        if (w.get(entity, "total"), w.get(entity, "count")) != (total, count):
            w.set(entity, "total", total)
            w.set(entity, "count", count)


def seed(loop, min_worth: float = 0.0) -> None:
    """Seed this island's own policy, singleton."""
    world = loop.world
    if not world.populated("min_worth"):
        entity = world.spawn()
        world.set(entity, "min_worth", min_worth)
