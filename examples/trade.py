"""`trade` -- the physics of owning and moving: who holds how much of
what, and one rule that moves amounts between holders, refusing to
overdraw.

## What this module knows: nothing about cards, prices or markets

`Holding(holder, thing, amount)` names a holder and a thing as OPAQUE
entity ids, plus an amount; `Movement(holder, thing, delta)` is a signed
change to one (holder, thing) pair. A domain that wants to use this
projects its OWN ownership onto those shapes from its own side -- the
direction every bridge in this repo runs (see `examples.judge`) -- and
this module never learns what a holder or a thing is. It imports nothing
from `examples/`, pinned by a test the same way `examples.judge`'s own
obliviousness is: `trade` is the content-free operator "move," in the
sense `world.each` is "enumerate" and `decide.pick_winner` is "choose."

## Why a holding is its own entity, not a component on the holder

`world.get(entity, Holding)` refuses to guess when several coexist, and a
holder with three things holds three `Holding`s. So a holding is a
RELATION ENTITY, one per (holder, thing) pair -- the same "a relation is
an entity" shape `examples.market.Listing` already uses -- and
`apply_movements` finds one by scanning, not by `get`.

## Agreed: the domain keeps the policy, this module keeps the move

A `Movement` is inert until the domain attaches `Agreed` to it -- the
proposed/approved idiom restated. Deciding WHETHER to move is island
policy; moving is this module's. `apply_movements` reads only
`Movement`/`Agreed`/`Holding` and writes only `Holding`/`Refused`.

## The one shareable mechanism: never double-spend

`apply_movements` re-reads the holding it touches at the TOP of every
iteration, so a batch of movements against one holding cannot overdraw
between them -- the exact discipline `examples.cards.decide_buy` had to
hand-write for its own purse, solved once here for every island. A
movement that would take a holding negative is REFUSED, not clamped:
consumed, and a `Refused(holder, thing, delta)` spawned naming what was
declined -- "a wrong conclusion is worse than a missing one."

## Named gap: an exchange is not atomic

Movements are applied one at a time. A two-sided trade whose first
movement succeeds and whose second would overdraw ends up half-applied:
`apply_movements` does not group movements into an all-or-nothing
exchange. Named here rather than hidden -- a caller that needs atomicity
must pre-check it, or a future `Exchange` entity must group the pair.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient


@dataclass(frozen=True)
class Holding:
    """One holder's amount of one thing -- a RELATION ENTITY (see the
    module note), not a component on the holder. `holder` and `thing` are
    opaque entity ids this module never interprets."""
    holder: int
    thing: int
    amount: int


@dataclass(frozen=True)
class Movement:
    """A proposed signed change to one (holder, thing) pair: `+delta` to
    gain, `-delta` to lose. Inert until the domain attaches `Agreed` to
    the SAME entity -- see the module note."""
    holder: int
    thing: int
    delta: int


@transient
@dataclass(frozen=True)
class Agreed:
    """The domain's own claim that a `Movement` it built may go through;
    a transient gate, the same shape as `judge.TooRisky`."""
    pass


@dataclass(frozen=True)
class Refused:
    """A movement that would have taken a holding negative: consumed, not
    applied, and named here so a caller can see what was declined. Durable
    (not `@transient`) the same way `cards.BadCommand` is -- a short-lived
    outcome fact a real domain's own `reply_*` rule would consume."""
    holder: int
    thing: int
    delta: int


def _holding(w, holder, thing):
    """The `Holding` entity for this (holder, thing) pair, or `(None,
    None)`. A scan, because holdings are relation entities -- see the
    module note on why not `get`."""
    for entity, holding in w.all(Holding):
        if holding.holder == holder and holding.thing == thing:
            return entity, holding
    return None, None


def apply_movements(w) -> None:
    """Every `Movement` the domain has `Agreed` -> moved onto its
    `Holding`, creating one first if the pair has never held anything, and
    consuming the movement. A movement that would go negative is refused
    (consumed, `Refused` spawned) rather than clamped -- see the module
    note.

    Re-reads the holding at the TOP of each iteration, so several
    movements against one holding in a single call cannot overdraw between
    them -- the same "never trust the snapshot" discipline
    `examples.cards.decide_buy` uses for its purse."""
    for entity, movement, _agreed in w.each(Movement, Agreed):
        holding_entity, holding = _holding(w, movement.holder, movement.thing)
        current = holding.amount if holding is not None else 0
        result = current + movement.delta
        if result < 0:
            w.destroy(entity)
            w.spawn(Refused(movement.holder, movement.thing, movement.delta))
            continue
        if holding_entity is not None:
            w.replace(holding_entity,
                      Holding(movement.holder, movement.thing, result))
        else:
            w.spawn(Holding(movement.holder, movement.thing, result))
        w.destroy(entity)


RULES = (apply_movements,)


def install(loop) -> None:
    """Register the one rule. No seeding: holdings are created on demand,
    by the movement that first touches a (holder, thing) pair."""
    loop.rule(apply_movements)
