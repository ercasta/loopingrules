"""`quorum` -- a domain whose decision is a COUNT over a set.

A motion passes iff at least `needed` of its own votes are `for`. Under the
attribute substrate (D8) a `motion`/`vote` is a tagged entity, the vote's
`motion` is a reference, and `need`/`passed` are a singleton attribute and a
flag.
"""

from __future__ import annotations


def tally(w) -> None:
    """`passed` iff a motion's own `for` votes number at least the quorum --
    a count over that motion's votes, both directions. Abstains when no
    quorum has been seeded."""
    row = w.first("needed")
    if row is None:
        return
    needed = row[1]
    for entity, _tag in w.each("motion"):
        votes_for = 0
        for _v, _vtag, motion, choice in w.each("vote", "motion", "choice"):
            if motion == entity.id and choice == "for":
                votes_for += 1
        if votes_for >= needed:
            w.mark(entity, "passed")
        else:
            w.unmark(entity, "passed")


RULES = (tally,)


def install(loop, needed: int = 2) -> None:
    """Register `tally` and seed the quorum singleton -- only if the world
    does not already carry one."""
    loop.rule(tally)
    world = loop.world
    if not world.populated("needed"):
        entity = world.spawn()
        world.mark(entity, "quorum")
        world.set(entity, "needed", needed)
