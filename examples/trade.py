"""`trade` -- the physics of owning and moving: who holds how much of what,
and one rule that moves amounts between holders, refusing to overdraw.

Under the attribute substrate (D8) a holding and a movement are RELATION
ENTITIES -- a `holding` tagged entity carrying `holder`/`thing`/`amount`
(opaque references this module never interprets), a `movement` tagged entity
carrying `holder`/`thing`/`delta`. A movement is inert until the domain marks
it `agreed`; a refused one deposits a `refused` entity. This module imports
nothing from `examples/`.
"""

from __future__ import annotations


def _holding(w, holder, thing):
    """The `holding` entity for this (holder, thing) pair, or `(None, 0)`."""
    for entity, _tag, h, t, amount in w.each("holding", "holder", "thing",
                                             "amount"):
        if h == holder and t == thing:
            return entity, amount
    return None, 0


def apply_movements(w) -> None:
    """Every `movement` the domain has `agreed` -> moved onto its `holding`,
    creating one first if the pair has never held anything, and consuming the
    movement. A movement that would go negative is refused (consumed, a
    `refused` spawned) rather than clamped.

    Re-reads the holding at the TOP of each iteration, so several movements
    against one holding in a single call cannot overdraw between them.
    """
    for row in w.each("movement", "agreed", "holder", "thing", "delta"):
        entity, _tag, _agreed, holder, thing, delta = row
        holding_entity, current = _holding(w, holder, thing)
        result = current + delta
        if result < 0:
            w.destroy(entity)
            refused = w.spawn()
            w.mark(refused, "refused")
            w.set(refused, "holder", holder)
            w.set(refused, "thing", thing)
            w.set(refused, "delta", delta)
            continue
        if holding_entity is not None:
            w.set(holding_entity, "amount", result)
        else:
            holding = w.spawn()
            w.mark(holding, "holding")
            w.set(holding, "holder", holder)
            w.set(holding, "thing", thing)
            w.set(holding, "amount", result)
        w.destroy(entity)


RULES = (apply_movements,)


def install(loop) -> None:
    """Register the one rule. No seeding: holdings are created on demand."""
    loop.rule(apply_movements)
