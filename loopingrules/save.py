"""The world, on disk, so a restart is not an amnesia.

    save.write(world, "~/.local/state/harneskills/world.json")
    save.read(world, path)          # into an EMPTY world, before any domain

Under the attribute substrate (`docs/plan-attributes.md`, D8) there is
nothing here but an entity id and a dict of its attributes -- one JSON object
PER LINE (JSONL). The first line is a header; every line after it is either
an entity's attribute set or a bare, attribute-less entity::

    {"version": 3, "next": 23}
    {"entity": 3, "attributes": {"path": "/tmp/notes", "tags": ["a", "b"]}}
    {"entity": 7}

## A value is already JSON

`World.set` already guarantees a stored value is a scalar, an entity
reference (a plain int id), or a **flat list** of those -- never a dict, a
tuple or a live handle. So there is no `$tuple` wrapper any more and no
nested rebuild: a reference to another entity is already exactly the
JSON-native int this format wants. `_field` remains a second, cheaper line
of defence that refuses anything that somehow is not JSON.

## Ids are preserved, and so is the counter

Restoring `#3` as `#3` is the whole point: every reference is that number.
And `next` comes back too -- a world that resumed its counter at 1 would
hand a new entity an id some attribute is still pointing at.

## What is NOT saved

The RULES: a domain registers those in `install()`, from code, every time.

Also not saved: any attribute whose NAME is in `world.transient` -- skipped
name by name, the same as a rule. An entity whose ONLY attributes were
transient is skipped too, entirely, rather than written back as bare -- a
bare `{"entity": id}` record means "this entity is real but carries nothing
YET", which is not what "every attribute it had was disposable" means. The
two cases look identical from `world.attributes(entity)` returning `{}`
either way, and this module tells them apart before that point, not after.

## Version 3, deliberately not silent about it

Version 2 was one record per typed component; this is one record per
entity's attribute set. The two cannot be mis-read as each other, so a
version that does not match is refused by name rather than guessed at.
"""

from __future__ import annotations

import json
import os

VERSION = 3


class SaveError(ValueError):
    """A value this module will not pretend it can write."""


def _field(value, where: str):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_field(v, where) for v in value]
    raise SaveError("%s: cannot save a %s" % (where, type(value).__name__))


def dump(world) -> "list[dict]":
    """The whole world, as a list of records -- a header first, then one
    record per entity carrying at least one durable attribute, then a bare
    `{"entity": id}` for any entity that carries none. Raises `SaveError`
    naming the entity and attribute if anything will not go.
    """
    records = [{"version": VERSION, "next": world._next}]
    for entity in world.entities():
        attributes = world.attributes(entity)
        if not attributes:
            records.append({"entity": entity.id})
            continue
        durable = {name: value for name, value in attributes.items()
                   if name not in world.transient}
        if not durable:
            # Everything it carried was marked disposable -- not the same as
            # never having carried anything, so no bare record either.
            continue
        records.append({"entity": entity.id, "attributes": {
            name: _field(value, "%s.%s" % (entity, name))
            for name, value in durable.items()}})
    return records


def write(world, path: str) -> None:
    """Save it, atomically. The directory is made if it is not there.

    Written to a temporary file beside the real one and then renamed,
    because the thing most likely to interrupt this is the restart it
    exists to survive -- and a half-written world is worse than an old one.
    """
    path = os.path.abspath(os.path.expanduser(path))
    records = dump(world)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    # `newline=""` so text mode does not turn every `\n` into `\r\n` on
    # Windows. A state file that is different bytes depending on which
    # machine wrote it is a file you cannot compare.
    with open(temporary, "w", encoding="utf-8", newline="") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=False))
            fh.write("\n")
    os.replace(temporary, path)


def load(world, records: "list[dict]") -> "list[str]":
    """Put it all back, into a world that is empty. Returns problems.

    Restoring writes slots through `World._restore`, which does NOT log a
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
        world._adopt(entity_id)
        for name, value in record.get("attributes", {}).items():
            try:
                world._restore(entity_id, name, value)
            except (TypeError, ValueError) as e:
                problems.append("#%d.%s: %s" % (entity_id, name, e))
    # After the entities, never before: `_adopt` keeps the counter above
    # every id it has seen, and the file's own `next` is what a world that
    # destroyed its highest entity before saving needs to come back to.
    world._next = max(world._next, int(header.get("next", 0)))
    return problems


def read(world, path: str) -> "list[str]":
    """`load` what is at `path`. Returns problems -- and a file that is not
    there is not one: it is the ordinary case for a first run, and it means
    an empty world, exactly as if it held nothing."""
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
