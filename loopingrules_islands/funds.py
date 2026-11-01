"""The `funds` island -- a second foundation, deliberately independent of
`items`, so a composer can read BOTH (`docs/plan-islands.md`, the
conjunction). It has never heard of a role.

Kept minimal on purpose: its own vocabulary, one rule over it, and its own
declared knob -- so a probe can show a composition rule reading `items.Item`
and `funds.Spendable` at once, when neither island imports the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules_calibration import Knob, tunable


@dataclass(frozen=True)
class Funds:
    """The money the agent holds, a singleton."""
    cash: float


@dataclass(frozen=True)
class Reserve:
    """What must be kept back, a singleton -- this island's own knob."""
    amount: float


@dataclass(frozen=True)
class Spendable:
    """What is left to spend (`Funds.cash - Reserve.amount`), a singleton
    derived by this island's own rule."""
    amount: float


@tunable(Knob(Reserve, "amount", 0.0, 100.0, steps=11))
def spendable(w) -> None:
    """`Spendable(cash - reserve)`, kept in step. Reads only this island's
    OWN vocabulary -- it has never heard of `items.Item`, and no rule of
    `items` has heard of it. `amount` is this rule's declared surface, so
    `lint` holds it to a knob rather than a literal."""
    found = w.first(Funds)
    reserve = w.the(Reserve)
    if found is None or reserve is None:
        return
    amount = found[1].cash - reserve.amount
    current = w.first(Spendable)
    if current is None:
        w.spawn(Spendable(amount))
    else:
        entity, spend = current
        if spend.amount != amount:
            w.replace(entity, Spendable(amount))


def seed(loop, cash: float = 100.0, reserve: float = 0.0) -> None:
    """Seed this island's own singletons."""
    world = loop.world
    if world.first(Funds) is None:
        world.spawn(Funds(cash))
    if world.first(Reserve) is None:
        world.spawn(Reserve(reserve))
