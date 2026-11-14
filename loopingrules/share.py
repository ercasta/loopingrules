"""A pack of entities and their attributes, portable between STRANGERS'
worlds -- the thing `save.py` cannot be, because `save.py` only ever
restores into an EMPTY world with every id preserved, and a pack is merged
into one that already has its own entities occupying those same id numbers.

    records = share.dump_pack(world, entities)
    problems, mapping = share.load_pack(target_world, records)

Two problems `save.py` never had to solve, because restoring one world into
itself sidesteps both:

## 1. Ids must be REMAPPED, not preserved -- so a ref value must be told
   apart from an ordinary int

`save.py`'s own docstring: a value is already JSON-native, so an entity
reference and an ordinary integer (a price, a page count) are the SAME shape
on disk. That was fine for `save.py`: nothing there renumbers an id. A pack
cannot get away with it. Importing into a populated world means every entity
in the pack gets a FRESH id, so any attribute holding another pack entity's
id has to be rewritten, and any attribute merely holding a number must NOT
be -- on pain of a price silently turning into an unrelated id.

Under the attribute substrate (`docs/plan-attributes.md`, D8) ref-ness is
DECLARED in the schema and carried at runtime in `World.refs`, a set of
attribute NAMES whose values are references. That is the one thing this
module consults. It replaces the old `share.ref()` field metadata: a name is
a ref, or it is not, and nothing about a value's shape says which.

## 2. A ref name's claim is not trusted from the file

The importing side decides which attributes are references by asking the
TARGET WORLD's own `refs` set -- not by reading a `"refs"` list out of the
pack. A stranger's file gets to name which entities exist and what values
they carry; it does not get to redefine, for the receiving domain, which
attributes mean "this is another entity." Letting the file's own claim win
would let a pack silently repoint a normal attribute as if it were a
reference (or hide a real reference from remapping, smuggling a foreign,
unmapped id into the target world) merely by omitting or adding one word in
a JSON record neither this module nor the receiving domain wrote.

## What this refuses rather than guesses

A ref attribute pointing OUTSIDE the pack -- at export time, if the target
id was never included in `entities`, `dump_pack` raises, naming the entity
and attribute. At import time, a ref pointing at an id the pack itself never
defined is the same refusal, but per-entity and named rather than fatal:
that one attribute is skipped, the same "skip and name it" policy
`save.load` already has.

## What this deliberately does NOT do

No merge/identity hook (two entities denoting "the same" thing come in as
two; deduplication is an ordinary rule a domain writes). No transitive
closure (`entities` is exactly what goes in). No circuits.
"""

from __future__ import annotations

from .save import SaveError, _field

VERSION = 1


class PackError(ValueError):
    """A pack this module will not write or cannot safely resolve."""


def _id_of(entity) -> int:
    return entity.id if hasattr(entity, "id") else int(entity)


# -- writing --------------------------------------------------------------

def _ref_out(value, ids: set, where: str):
    """A ref attribute's value, checked against `ids` -- the pack's own
    entities -- rather than rewritten; export keeps the original id, since
    only IMPORT knows what it becomes. Raises `PackError` naming the
    attribute if the target is not in this pack at all.
    """
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        if value not in ids:
            raise PackError(
                "%s: references entity #%d, which is not in this pack -- "
                "a pack cannot hold a reference load_pack could never "
                "resolve" % (where, value))
        return value
    if isinstance(value, list):
        return [_ref_out(v, ids, where) for v in value]
    raise PackError("%s: a ref attribute must be an int (or a list of "
                    "ints), not %s" % (where, type(value).__name__))


def dump_pack(world, entities) -> "list[dict]":
    """`entities`, and every durable, non-transient attribute on them, as
    pack records -- a header first. Raises `PackError` for a ref attribute
    pointing outside `entities`, and `save.SaveError` for a value that is
    not JSON-shaped at all.
    """
    ids = {_id_of(e) for e in entities}
    records = [{"version": VERSION}]
    for entity in entities:
        entity_id = _id_of(entity)
        attributes = world.attributes(entity)
        if not attributes:
            records.append({"entity": entity_id})
            continue
        durable = {name: value for name, value in attributes.items()
                   if name not in world.transient}
        if not durable:
            continue
        fields = {}
        for name, value in durable.items():
            where = "#%d.%s" % (entity_id, name)
            if name in world.refs:
                fields[name] = _ref_out(value, ids, where)
            else:
                fields[name] = _field(value, where)
        records.append({"entity": entity_id, "attributes": fields})
    return records


# -- reading --------------------------------------------------------------

def _remap(value, mapping: dict, where: str, problems: "list[str]"):
    """A ref attribute's value, rewritten from a pack-local id to the entity
    that id became in the TARGET world. A reference the pack never defined
    an entity for is left as-is and named in `problems` -- the caller skips
    that attribute rather than write a dangling, unmapped id.
    """
    if value is None:
        return None, True
    if isinstance(value, int) and not isinstance(value, bool):
        target = mapping.get(value)
        if target is None:
            problems.append("%s: dangling reference to pack entity #%d -- "
                            "this attribute was not set" % (where, value))
            return None, False
        return target.id, True
    if isinstance(value, list):
        out = []
        for v in value:
            resolved, ok = _remap(v, mapping, where, problems)
            if not ok:
                return None, False
            out.append(resolved)
        return out, True
    problems.append("%s: a ref attribute held %r, not an int or list of "
                    "ints -- this attribute was not set" % (where, value))
    return None, False


def load_pack(world, records: "list[dict]"):
    """Merge `records` (`dump_pack`'s own shape) into `world`, which may
    already hold anything -- the opposite of `save.load`, which demands an
    empty world. Every pack entity is `world.spawn()`-ed under a FRESH id;
    `world.refs` is consulted for which attribute names need remapping.

    Returns `(problems, mapping)` -- `mapping` is `{pack_id: new_id}`.
    """
    if not records or records[0].get("version") != VERSION:
        got = records[0].get("version") if records else None
        return (["pack is version %r, this module is version %d"
                % (got, VERSION)], {})
    body = records[1:]
    problems: "list[str]" = []
    mapping: "dict[int, object]" = {}
    for record in body:
        old_id = int(record["entity"])
        if old_id not in mapping:
            mapping[old_id] = world.spawn()
    for record in body:
        entity = mapping[int(record["entity"])]
        for name, value in record.get("attributes", {}).items():
            where = "pack #%d.%s" % (int(record["entity"]), name)
            if name in world.refs:
                resolved, ok = _remap(value, mapping, where, problems)
                if not ok:
                    continue
                world.set(entity, name, resolved)
            else:
                world.set(entity, name, value)
    return problems, {old: e.id for old, e in mapping.items()}
