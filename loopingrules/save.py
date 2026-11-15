"""The world, on disk, so a restart is not an amnesia.

    save.write(world, "~/.local/state/harneskills/world.json")
    save.read(world, path)          # into an EMPTY world, before any domain

Under the component substrate (ADR-10) there is nothing here but an entity id
and its COMPONENTS -- a named bag of fields each -- one JSON object PER LINE
(JSONL). The first line is a header; every line after it is either an entity's
components or a bare, component-less entity::

    {"version": 4, "next": 23}
    {"entity": 3, "components": {"listing": {"price": 10, "tags": ["a", "b"]}}}
    {"entity": 5, "components": {"done": {}}}      # a tag
    {"entity": 7}

## A value is already JSON

`World.set` already guarantees a stored value is a scalar, an entity reference
(a plain int id), or a **flat list** of those -- never a dict, a tuple or a live
handle. So a reference is already exactly the JSON-native int this format wants.
`_field` refuses anything that somehow is not JSON.

## Ids are preserved, and so is the counter

Restoring `#3` as `#3` is the whole point: every reference is that number. And
`next` comes back too.

## What is NOT saved

The RULES: a domain registers those in `install()`, from code, every time.

Also not saved: any COMPONENT whose NAME is in `world.transient` -- skipped
component by component. An entity whose ONLY components were transient is
skipped too, entirely, rather than written back as bare -- a bare
`{"entity": id}` record means "this entity is real but carries nothing YET",
which is not what "everything it had was disposable" means. A TAG (a component
with no fields) IS durable data: it is written as `{"component": {}}`.

## Version 4, deliberately not silent about it

Version 3 was one record per entity's flat attribute set; version 2 was one
record per typed component. This is components-as-named-bags. A version that
does not match is refused by name rather than guessed at.
"""

from __future__ import annotations

import json
import os

VERSION = 4


class SaveError(ValueError):
    """A value this module will not pretend it can write."""


def _field(value, where: str):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_field(v, where) for v in value]
    raise SaveError("%s: cannot save a %s" % (where, type(value).__name__))


def dump(world) -> "list[dict]":
    """The whole world, as a list of records -- a header first, then one record
    per entity carrying at least one durable component, then a bare
    `{"entity": id}` for any entity that carries none. Raises `SaveError` naming
    the entity and field if anything will not go.
    """
    records = [{"version": VERSION, "next": world._next}]
    for entity in world.entities():
        components = world.components(entity)
        if not components:
            records.append({"entity": entity.id})
            continue
        durable = {component: bag for component, bag in components.items()
                   if component not in world.transient}
        if not durable:
            # Everything it carried was disposable -- not the same as never
            # having carried anything, so no bare record either.
            continue
        records.append({"entity": entity.id, "components": {
            component: {field: _field(value, "%s.%s.%s"
                                      % (entity, component, field))
                        for field, value in bag.items()}
            for component, bag in durable.items()}})
    return records


def write(world, path: str) -> None:
    """Save it, atomically. The directory is made if it is not there."""
    path = os.path.abspath(os.path.expanduser(path))
    records = dump(world)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=False))
            fh.write("\n")
    os.replace(temporary, path)


def load(world, records: "list[dict]") -> "list[str]":
    """Put it all back, into a world that is empty. Returns problems.

    Restoring writes through `World._restore`/`_restore_tag`, which do NOT log a
    `Change` -- a restore is not something that happened, it IS the world.
    """
    if len(world) or world._next:
        raise ValueError("load() wants an empty world")
    if not records or records[0].get("version") != VERSION:
        got = records[0].get("version") if records else None
        return ["state file is version %r, this is version %d"
                % (got, VERSION)]
    header, body = records[0], records[1:]
    problems: "list[str]" = []
    # Adopt every id FIRST: a value may hold a reference to an entity that
    # appears later in the file.
    for record in body:
        world._adopt(int(record["entity"]))
    for record in body:
        entity_id = int(record["entity"])
        components = record.get("components", {})
        for component, bag in components.items():
            if not bag:
                world._restore_tag(entity_id, component)
                continue
            for field, value in bag.items():
                try:
                    world._restore(entity_id, component, field, value)
                except (TypeError, ValueError) as e:
                    problems.append("#%d.%s.%s: %s"
                                    % (entity_id, component, field, e))
    world._next = max(world._next, int(header.get("next", 0)))
    return problems


def read(world, path: str) -> "list[str]":
    """`load` what is at `path`. Returns problems -- and a file that is not
    there is not one: it is the ordinary case for a first run."""
    path = os.path.abspath(os.path.expanduser(path))
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []
    except OSError as e:
        return ["%s: %s" % (path, e)]
    try:
        records = [json.loads(line) for line in lines if line.strip()]
    except ValueError as e:
        return ["%s: %s" % (path, e)]
    return load(world, records)
