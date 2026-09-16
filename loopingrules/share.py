"""A pack of entities and components, portable between STRANGERS'
worlds -- the thing `save.py` cannot be, because `save.py` only ever
restores into an EMPTY world with every id preserved, and a pack is
merged into one that already has its own entities occupying those
same id numbers.

    records = share.dump_pack(world, entities)
    problems, mapping = share.load_pack(target_world, records, registry)

Two problems `save.py` never had to solve, because restoring one
world into itself sidesteps both:

## 1. Ids must be REMAPPED, not preserved -- so a ref field must be
   told apart from an ordinary int

`save.py`'s own docstring: a component field never holds a live
`Entity`, only its plain id -- which means, structurally, an entity
reference and an ordinary integer (a price, a page count) are the
SAME shape on disk. That was fine for `save.py`: nothing there ever
renumbers an id, so a field that happens to hold one still points at
the right entity after restore, same as any other field holds the
same value it always did.

A pack cannot get away with that. Importing into a populated world
means every entity in the pack gets a FRESH id (the numbers it
arrived with may already belong to someone else's entities in the
target world) -- so any field that holds another pack entity's id has
to be rewritten to the new id, and any field that merely holds a
number must NOT be, on pain of a price silently turning into an
unrelated id. Nothing about a field's static type says which case it
is; `int` is `int`. `ref()`, below, is new metadata a component's own
author has to add -- there is no way to infer it from the field's
current shape, because both cases already have that shape today.

## 2. A ref field's claim about itself is not trusted from the file

The importing side decides which fields are references by asking the
CLASS it already has -- resolved through `registry`, a `{name: class}`
map the caller supplies explicitly, never `importlib` -- not by
reading a `"refs"` list out of the pack. A stranger's file gets to
name which entities exist and what data they carry; it does not get
to redefine, for the receiving domain's own component, which of that
component's fields mean "this is another entity." Letting the file's
own claim win would let a pack silently repoint a normal field as if
it were a reference (or hide a real reference from remapping,
smuggling a foreign, unmapped id into the target world) merely by
omitting or adding one word in a JSON record neither this module nor
the receiving domain wrote.

This is also why `registry` is a caller-supplied dict and not
`save.py`'s own `_kind()` (`module:Class` resolved by `importlib`):
`_kind()` is fine for a state file that only ever comes from THIS
process's own prior run, but resolving an arbitrary dotted name out of
a stranger's file is an import primitive, and importing a module
already runs its top-level code -- the exact class of hole
`circuits.py`'s own `Call` was built to close for tool dispatch,
reopened here if type names were ever resolved the same way `save.py`
resolves its own.

## What this sketch refuses rather than guesses

A ref field pointing OUTSIDE the pack -- at export time, if the target
id was never included in `entities`, `dump_pack` raises, naming the
component and field, rather than writing a reference `load_pack` could
never resolve. At import time, a ref field pointing at an id the pack
itself never defined (a hand-edited or corrupt file) is the same
refusal, but per-component and named rather than fatal: that one
component is skipped, the same "skip and name it" policy `save.py`
already has for a component whose class no longer exists.

## What this sketch deliberately does NOT do

No merge/identity hook. Two entities that denote "the same" real-world
thing (a city imported twice, once locally and once from a pack) come
in as two separate entities, on purpose -- deduplication is an
ordinary rule over ordinary components, written by whatever domain
cares, not something this module decides or even notices. See the
conversation this sketch came out of: a rule that enumerates `Book`
does not care where an entity came from, and nothing here should force
one that does to exist.

No transitive closure. `entities` is exactly what goes in the pack;
nothing here walks references outward to complete it. A caller that
wants "this book and everything it points to" computes that set
itself before calling `dump_pack`.

No circuits (rules-as-data) yet -- `circuits.py`'s specs are a
different shape entirely (a tree of expression dataclasses, several of
whose fields hold component CLASSES, not component instances) and have
no entity-id problem at all, since a spec never mentions an entity id.
They need their own, simpler serializer, not this one.
"""

from __future__ import annotations

import dataclasses

from .world import is_transient
from .save import SaveError, _field, _rebuild, _name_of

VERSION = 1

_REF_KEY = "loopingrules.share.ref"


class PackError(ValueError):
    """A pack this module will not write or cannot safely resolve."""


def ref(**kwargs):
    """Mark a component field as holding another PACK entity's id --
    the one thing that tells this module to rewrite it on import
    instead of passing it through as an opaque int. See the module
    docstring, part 1, for why this cannot be inferred from the
    field's own type.
    """
    metadata = dict(kwargs.pop("metadata", {}))
    metadata[_REF_KEY] = True
    kwargs["metadata"] = metadata
    return dataclasses.field(**kwargs)


def _ref_fields(kind) -> set:
    return {f.name for f in dataclasses.fields(kind) if f.metadata.get(_REF_KEY)}


def _id_of(entity) -> int:
    return entity.id if hasattr(entity, "id") else int(entity)


# -- writing --------------------------------------------------------------

def _ref_out(value, ids: set, where: str):
    """A ref field's value, checked against `ids` -- the pack's own
    entities -- rather than rewritten; export keeps the original id,
    since only IMPORT knows what it becomes. Raises `PackError` naming
    the field if the target is not in this pack at all.
    """
    if value is None:
        return None
    if isinstance(value, int):
        if value not in ids:
            raise PackError(
                "%s: references entity #%d, which is not in this pack -- "
                "a pack cannot hold a reference load_pack could never "
                "resolve" % (where, value))
        return value
    if isinstance(value, list):
        return [_ref_out(v, ids, where) for v in value]
    if isinstance(value, tuple):
        # `save._field`'s own convention: JSON cannot tell a tuple from a
        # list, so a ref field typed as a tuple needs the same `$tuple`
        # marker an ordinary field already gets, or it comes back as a
        # list and a frozen component holding one silently stops being
        # equal to (or hashable as) the tuple it started as.
        return {"$tuple": [_ref_out(v, ids, where) for v in value]}
    raise PackError("%s: a ref field must be an int (or a list/tuple of "
                     "ints), not %s" % (where, type(value).__name__))


def dump_pack(world, entities) -> "list[dict]":
    """`entities`, and every durable, non-transient component on them,
    as pack records -- a header first. Raises `PackError` for a ref
    field pointing outside `entities`, and `save.SaveError` (from
    `save._field`) for a field that is not JSON-shaped data at all --
    the same refusal `save.dump` already applies to a plain field,
    reused rather than restated.
    """
    ids = {_id_of(e) for e in entities}
    records = [{"version": VERSION}]
    for entity in entities:
        entity_id = _id_of(entity)
        components = world.components(entity)
        durable = [c for c in components if not is_transient(type(c))]
        if not components:
            records.append({"entity": entity_id})
            continue
        if not durable:
            continue
        for component in durable:
            kind = type(component)
            refs = _ref_fields(kind)
            fields = {}
            for f in dataclasses.fields(kind):
                value = getattr(component, f.name)
                where = "#%d %s.%s" % (entity_id, kind.__name__, f.name)
                if f.name in refs:
                    fields[f.name] = _ref_out(value, ids, where)
                else:
                    fields[f.name] = _field(value, where)
            records.append({"entity": entity_id, "type": _name_of(kind),
                            "fields": fields})
    return records


# -- reading ----------------------------------------------------------------

def _remap(value, mapping: dict, where: str, problems: "list[str]"):
    """A ref field's value, rewritten from a pack-local id to the
    entity that id became in the TARGET world. A reference the pack
    never defined an entity for is left as-is and named in `problems`
    -- the caller (`load_pack`) skips the whole component rather than
    attach one holding a dangling, unmapped id, the same "wrong data is
    worse than missing data" refusal `dump_pack` applies at export.
    """
    if value is None:
        return None, True
    if isinstance(value, int):
        target = mapping.get(value)
        if target is None:
            problems.append("%s: dangling reference to pack entity #%d "
                            "-- this component was not attached" % (where, value))
            return None, False
        return target.id, True
    if isinstance(value, dict) and "$tuple" in value:
        out = []
        for v in value["$tuple"]:
            resolved, ok = _remap(v, mapping, where, problems)
            if not ok:
                return None, False
            out.append(resolved)
        return tuple(out), True
    if isinstance(value, list):
        out = []
        for v in value:
            resolved, ok = _remap(v, mapping, where, problems)
            if not ok:
                return None, False
            out.append(resolved)
        return out, True
    problems.append("%s: a ref field held %r, not an int or list/tuple of "
                    "ints -- this component was not attached" % (where, value))
    return None, False


def load_pack(world, records: "list[dict]", registry: dict):
    """Merge `records` (`dump_pack`'s own shape) into `world`, which
    may already hold anything -- the opposite of `save.load`, which
    demands an empty world. Every pack entity is `world.spawn()`-ed
    under a FRESH id; `registry` (`{"module:Qualname": class}`, built
    by the CALLER, never by resolving the name from the file the way
    `save._kind` does) is consulted for both which class a `type` name
    means and -- via `ref()` -- which of its fields need remapping. A
    name not in `registry` is skipped and named, the same policy
    `save.load` already has for a class that no longer exists.

    Returns `(problems, mapping)` -- `mapping` is `{pack_id: new_id}`,
    for a caller that wants to know what an imported entity became.
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
        if "type" not in record:
            continue
        name = record["type"]
        kind = registry.get(name)
        if kind is None:
            problems.append("%s: not in the importing registry, skipped" % name)
            continue
        refs = _ref_fields(kind)
        entity = mapping[int(record["entity"])]
        fields = {}
        ok = True
        for field_name, value in record.get("fields", {}).items():
            where = "pack #%d %s.%s" % (int(record["entity"]), kind.__name__, field_name)
            if field_name in refs:
                resolved, field_ok = _remap(value, mapping, where, problems)
                if not field_ok:
                    ok = False
                    break
                fields[field_name] = resolved
            else:
                fields[field_name] = _rebuild(value, world)
        if not ok:
            continue
        component = object.__new__(kind)
        for field_name, value in fields.items():
            object.__setattr__(component, field_name, value)
        world.attach(entity, component)
    return problems, {old: e.id for old, e in mapping.items()}
