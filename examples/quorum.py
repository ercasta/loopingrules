"""`quorum` -- a domain whose decision is a COUNT over a set, the ladder's
next rung after `market`'s conjunction. A motion passes iff at least
`Quorum.needed` of its own votes are `for`; nothing here can be flattened
into a per-row condition, because whether a vote matters depends on HOW
MANY others agree. Kept in `examples/`, not shipped -- see `README.md`'s
"Scope."

## Why this shape

`market.Strands` composes a conjunction over a FIXED number of rivals;
`trip`'s bridge composes a ranking. This composes a count: the verdict is
`#{for votes} >= needed`, and the count grows with the number of votes.
`docs/tuning.md`'s ladder expects the authored gap to widen with that
number, because a per-row learner has to reconstruct a cardinality it is
never handed. `ablation.counting` measures exactly that.

## Vocabulary

- `Motion(name)` -- one thing being voted on.
- `Vote(motion, choice)` -- one vote, `choice` `"for"` or `"against"`,
  `motion` a `Motion` entity id (or the live entity -- `attach` lowers it).
- `Quorum(needed)` -- the singleton threshold, seeded by `install`.
- `Passed()` -- `@transient` tag on a `Motion` whose `for` count cleared the
  quorum, both directions every tick, the same "recompute fresh" discipline
  every other tag in this repo uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient


@dataclass(frozen=True)
class Motion:
    name: str


@dataclass(frozen=True)
class Vote:
    motion: int
    choice: str


@dataclass(frozen=True)
class Quorum:
    needed: int


@transient
@dataclass(frozen=True)
class Passed:
    pass


def tally(w) -> None:
    """`Passed` iff a motion's own `for` votes number at least the quorum --
    a count over that motion's votes, both directions. Abstains (touches
    nothing) when no `Quorum` has been seeded, the same refuse-to-guess
    discipline `loopingrules_patterns.judge.flag_too_risky` applies to its threshold."""
    quorum = w.the(Quorum)
    if quorum is None:
        return
    for entity, _motion in w.each(Motion):
        votes_for = 0
        for _vote_entity, vote in w.each(Vote):
            if vote.motion == entity.id and vote.choice == "for":
                votes_for += 1
        if votes_for >= quorum.needed:
            w.attach(entity, Passed())
        else:
            w.detach(entity, Passed)


RULES = (tally,)


def install(loop, needed: int = 2) -> None:
    """Register `tally` and seed `Quorum` -- BigFloor-style, only if the
    world does not already carry one."""
    loop.rule(tally)
    if loop.world.first(Quorum) is None:
        loop.world.spawn(Quorum(needed))
