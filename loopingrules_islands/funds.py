"""The `funds` island -- a second foundation, deliberately independent of
`items`. It has never heard of a role.

Under the attribute substrate (D8): the money held is the singleton attribute
`cash`; the reserve is `reserve`; the derived amount is `spendable`.
"""

from __future__ import annotations

from loopingrules_calibration import Knob, tunable


@tunable(Knob("reserve", 0.0, 100.0, steps=11))
def spendable(w) -> None:
    """`spendable` (`cash - reserve`), kept in step. Reads only this island's
    OWN vocabulary. `reserve` is this rule's declared surface."""
    found = w.first("cash")
    reserve = w.first("reserve")
    if found is None or reserve is None:
        return
    amount = found[1] - reserve[1]
    current = w.first("spendable")
    if current is None:
        entity = w.spawn()
        w.mark(entity, "spendable")
        w.set(entity, "spendable", amount)
    elif w.get(current[0], "spendable") != amount:
        w.set(current[0], "spendable", amount)


def seed(loop, cash: float = 100.0, reserve: float = 0.0) -> None:
    """Seed this island's own singletons."""
    world = loop.world
    if not world.populated("cash"):
        entity = world.spawn()
        world.set(entity, "cash", cash)
    if not world.populated("reserve"):
        entity = world.spawn()
        world.set(entity, "reserve", reserve)
