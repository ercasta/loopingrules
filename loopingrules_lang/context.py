"""YAML context (the ANCHOR) -> seeded entities.

The "goal" input, in the substrate's own terms (ADR-8): a context is a set of
entities and the components they carry, *not* state the domain computes. Author
it as a list, one mapping per entity::

    entities:
      - candidate: {worth: 5.0, name: goblin}
      - funds: {cash: 30.0, reserve: 10.0}
      - do: {what: cheapest, limit: 20}     # the directive -- just another entity
      - done: {}                            # a tag

A value is a scalar or a flat list; no references yet (a `{ref: ...}` form is the
next step).
"""

from __future__ import annotations


def seed(world, doc):
    """Spawn and populate the context's entities. Returns the new entities."""
    spawned = []
    for item in (doc or {}).get("entities", ()):
        entity = world.spawn()
        spawned.append(entity)
        for component, body in item.items():
            if not body:
                world.mark(entity, component)
            else:
                for field, value in body.items():
                    world.set(entity, component, field, value)
    return spawned
