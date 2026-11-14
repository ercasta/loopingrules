"""The world: entities, the attributes they carry, and the log of every
change made to them.

An entity is identity, with no data of its own. An **attribute** is a
`(name, value)` slot on one -- `w.set(person, "telephone", ["555", "556"])`
-- and there is **at most one slot per name per entity**: multiplicity
lives INSIDE the value (a list), never in a second slot. There are only
entities and attributes here; a "component" is not a class this module
knows, only a **shape** -- a named attribute set -- that a **reference**
points at an entity expected to carry. This module stores names and
values and nothing else. See `docs/plan-attributes.md` (D8) for the shape
this replaces and why; this file is Phase S's seam.

## A value is a scalar, a reference, or a flat list

| Value | Meaning |
|---|---|
| `None` / `bool` / `int` / `float` / `str` | a scalar |
| another entity | a **reference**, stored as its plain `int` id |
| a **flat list** of the above | the multi-valued or ordered case |

**No dict, no tuple, no nesting.** Whatever looks like a structure is a
reference to an entity that carries the fields, not a value. `_lower`
enforces this at the one place a value enters the store, the way the
component engine enforced "a field holds no Python object" -- and it is
the only place, so every read sees exactly what was written.

## The kinds, and why this module is kind-agnostic

The schema (`docs/plan-attributes.md`) declares each name one of four
kinds, with the verbs a domain reaches for:

| Kind | Holds | Verbs | Settles? |
|---|---|---|---|
| **singular** | exactly one value | `set` / `unset` | re-`set` an equal value = no change |
| **set** | deduped, insertion-ordered | `add` / `remove` | `add` an equal value = no change |
| **sequence** | ordered, duplicates kept | `append` / `pop` | every `append` changes |
| **flag** | a unit marker | `mark` / `unmark` | re-`mark` = no change |

This module does not read the schema and does not enforce these kinds: it
enforces only the SHAPE (an `add`/`append`/`remove`/`pop` wants a list,
`set` stores whatever it is handed). The declared kind, and whether a use
agrees with it, is the offline half -- `analyze`, the linter and the
forge's gates -- exactly the "derived use, checked against a declared
schema" split `docs/plan-attributes.md` draws. Keeping the kinds out of
the store is what lets the engine stay a store.

`set` writes the WHOLE slot, so it REPLACES a collection;
`set(e, name, [])` is a present-but-empty collection while `unset` is
absence -- a distinction the dormancy gate (`populated`) can see. There
is no separate `clear`.

## Every write lands in the change log

The same write methods also append to a transient, in-memory CHANGE LOG
(`World.changes` / `World.recent`): what changed, on which tick, and
which rule made the change (or `None`, for an install or the engine). A
rule reads the log to condition on what HAS HAPPENED, not only on what is
true now -- see `docs/plan-memory.md`. A record's `payload` holds
attribute DELTAS `(name, old, new)`, where an absent side is spelled with
the `MISSING` sentinel rather than `None` (a slot may legitimately hold
`None`). The `changed=` filter on `changes()` names an **attribute**, not
a class. The log is never saved (`save.dump` walks entities and their
slots, and the log is neither) and is bounded only if a caller asks
(`Loop(capacity=...)`). `Loop.tick` sets `_actor` and `_tick` around each
rule call, which is the whole of the log's provenance.

## Transience is a NAME

The component engine marked a CLASS `@transient` to keep it out of
`save`. There are no classes now, so transience is a NAME: `world.transient`
is the set of names a domain does not want written down, and
`purge_transient()` drops every such slot on demand. `save`/`share` skip
them the same way they skipped a transient class.

## What this does not settle

The open questions `docs/plan-attributes.md` still carries -- the naming
convention for a link attribute and its shape, whether a schema-driven
constructor is the idiom, how the JSON schema is versioned and frozen,
cycles in the ref graph, and whether a rule may set a name no shape
declares -- are not answered here. This module only makes the substrate
the answer can be built on: names, values, refs, lists, the kinds' verbs,
and a log of deltas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


_MARKER = object()


class _Missing:
    """The sentinel an absent side of a delta (and an absent slot in a
    change record) is spelled with -- distinct from `None`, which is a
    value a slot may legitimately hold. `changes()` hands these out and
    `save` never sees one; compare with `MISSING` itself."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()


_PRIMITIVES = (type(None), bool, int, float, str)


def _lower(value: Any, where: str) -> Any:
    """`value`, with any `Entity` turned into its plain id, or a `TypeError`
    naming `where` if it is not a value this world can store: a scalar, an
    entity reference, or a **flat list** of those. No dict, no tuple, no
    nested list -- whatever looks like a structure is an entity, not a
    value. See the module note; this is the one place a value enters.
    """
    if isinstance(value, Entity):
        return value.id
    if isinstance(value, _PRIMITIVES):
        return value
    if isinstance(value, (list, tuple)):
        out = []
        for index, item in enumerate(value):
            if isinstance(item, Entity):
                out.append(item.id)
            elif isinstance(item, _PRIMITIVES):
                out.append(item)
            else:
                raise TypeError(
                    "%s[%d]: a list attribute must be a flat list of "
                    "scalars (None/bool/int/float/str) or entity references "
                    "-- got a %s; a structured value is an entity, not a "
                    "value" % (where, index, type(item).__name__))
        return out
    raise TypeError(
        "%s: an attribute must be a scalar (None/bool/int/float/str), "
        "another entity (stored as its plain id, not the handle), or a "
        "flat list of those -- got a %s, which is a Python object this "
        "world cannot store or compare by value"
        % (where, type(value).__name__))


class Entity:
    """A handle: which entity, and in which world. No data of its own.

    Compares and hashes by id, so a handle handed back by a query is the
    same one an attribute stored earlier, and a reference stored as `#7`
    goes on meaning `#7` however many times it is looked up.

    Important: never store one of these AS a value -- the store lowers it
    to its plain id (see the module note). Hold an entity to READ and
    WRITE through, not as data at rest.
    """

    __slots__ = ("id", "world")

    def __init__(self, world, id_: int) -> None:
        self.world = world
        self.id = id_

    def __eq__(self, other) -> bool:
        return (isinstance(other, Entity) and other.id == self.id
                and other.world is self.world)

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return "#%d" % self.id

    # Sugar, for the places a rule already holds the entity and wants one
    # thing off it. Everything here is `World`'s method with the entity
    # filled in -- there is no second way to do anything.
    def get(self, name, default=None):
        return self.world.get(self, name, default)

    def has(self, *names) -> bool:
        return self.world.has(self, *names)

    def set(self, name, value) -> "Entity":
        return self.world.set(self, name, value)

    def unset(self, name) -> bool:
        return self.world.unset(self, name)

    def add(self, name, item) -> bool:
        return self.world.add(self, name, item)

    def remove(self, name, item) -> bool:
        return self.world.remove(self, name, item)

    def append(self, name, item) -> "Entity":
        return self.world.append(self, name, item)

    def pop(self, name, index=-1):
        return self.world.pop(self, name, index)

    def mark(self, name) -> "Entity":
        return self.world.mark(self, name)

    def unmark(self, name) -> bool:
        return self.world.unmark(self, name)

    def attributes(self) -> "dict":
        return self.world.attributes(self)

    def destroy(self) -> bool:
        return self.world.destroy(self)

    @property
    def alive(self) -> bool:
        return self.world.alive(self)


class Change:
    """One mutation the world applied, as the change log records it.

    `seq` is monotonic across the world's whole life; `tick` is the loop's
    tick count at the moment (`0` before the first tick, so install-time
    writes are `tick == 0`); `rule` names the rule that made it, or `None`
    for a write made outside any rule (an install, the engine draining a
    `Reply`); `kind` is one of `spawn`/`set`/`unset`/`add`/`remove`/
    `append`/`pop`/`mark`/`unmark`/`destroy`/`changed`/`purge`; `target`
    is the entity id touched (`None` for `purge`); and `payload` holds the
    attribute DELTAS `(name, old, new)` -- the slot's whole value BEFORE
    and AFTER the write, with an absent side spelled `MISSING` rather than
    `None` (a slot may legitimately hold `None`). `spawn`/`changed`/`purge`
    carry no delta; `destroy` carries one per slot that went with the
    entity.
    """

    __slots__ = ("seq", "tick", "rule", "kind", "target", "payload")

    def __init__(self, seq, tick, rule, kind, target, payload=()) -> None:
        self.seq = seq
        self.tick = tick
        self.rule = rule
        self.kind = kind
        self.target = target
        self.payload = tuple(payload)

    def __eq__(self, other) -> bool:
        return (isinstance(other, Change)
                and (self.seq, self.tick, self.rule, self.kind,
                     self.target, self.payload)
                == (other.seq, other.tick, other.rule, other.kind,
                    other.target, other.payload))

    def __repr__(self) -> str:
        return ("Change(seq=%r, tick=%r, rule=%r, kind=%r, target=%r, "
                "payload=%r)" % (self.seq, self.tick, self.rule, self.kind,
                                 self.target, self.payload))


class World:
    """Entities, the attributes on them, and the queries rules ask."""

    def __init__(self) -> None:
        # entity id -> handle, in spawn order; entity id -> {name: value},
        # in the order names were first set on it; and name -> {entity id},
        # the index a query runs on: a query for three names is three set
        # lookups and a walk of the smallest.
        self._entities: Dict[int, Entity] = {}
        self._slots: Dict[int, Dict[str, Any]] = {}
        self._by_name: Dict[str, Set[int]] = {}
        self._next = 0
        # Bumped by every spawn/destroy, every set that changed something,
        # and every add/remove/append/pop/mark/unmark that did. The loop
        # reads it to tell a rule that did something from one that did
        # not, which is the whole of how it knows the world has settled.
        self.revision = 0
        # The names a domain does not want written down (`save`/`share`
        # skip them; `purge_transient` drops them). Transience is a NAME
        # now that there is no class to mark -- see the module note.
        self.transient: Set[str] = set()
        # The names whose value is an entity REFERENCE rather than an
        # ordinary number -- the schema's ref declaration, carried here so
        # `share` can remap a pack id without trusting the file. `save`
        # does not need it (it preserves ids); `share` does. See
        # `docs/plan-attributes.md` on refs and `share.py`.
        self.refs: Set[str] = set()
        # The change log: transient, in-memory, never saved. `_seq` counts
        # every record so `changes(since=...)` stays stable even when
        # `_log_capacity` drops old entries; `_actor`/`_tick` are set by
        # the Loop around each rule call, which is the log's provenance.
        self._changes: List[Change] = []
        self._seq = 0
        self._actor = None
        self._tick = 0
        self._log_capacity = None

    def _record(self, kind: str, target, payload) -> None:
        """Append one `Change` -- called by every write below that actually
        moved `revision`, never for a no-op (a re-set equal value is not a
        change and must not be in the log, same guarantee settling rests
        on)."""
        self._changes.append(Change(seq=self._seq, tick=self._tick,
                                    rule=self._actor, kind=kind,
                                    target=target, payload=payload))
        self._seq += 1
        capacity = self._log_capacity
        if capacity is not None and len(self._changes) > capacity:
            del self._changes[:len(self._changes) - capacity]

    def clear_changes(self) -> None:
        """Drop the whole log. The log is not the world: nothing about the
        entities or the fixpoint depends on it, so a long session may prune
        it freely."""
        self._changes.clear()

    # -- entity ids, handles, either -----------------------------------

    def _id(self, entity) -> int:
        """An entity id, whether handed a live handle or the plain int
        already -- what lets every method below take either, which is what
        lets a reference stored as a plain id be passed straight back into
        `get`/`has`/`set`/... without a caller converting it first."""
        return entity.id if isinstance(entity, Entity) else int(entity)

    def entity(self, entity_id) -> Entity:
        """The handle for this id -- the other direction from a stored
        reference's plain int back to something `.get()`/`.set()`/... work
        on. No existence check: the same trust level constructing `Entity`
        directly always had."""
        return Entity(self, int(entity_id))

    def _restore(self, entity_id: int, name: str, value) -> None:
        """Put a slot back WITHOUT logging a `Change` -- what `save.load`
        uses. Restoring is not something that happened to the world, it IS
        the world, so unlike `set` it records nothing; it still adopts the
        entity and moves `revision`, because a restored world has moved
        from empty. Not part of the rule-facing API.
        """
        entity = self._adopt(entity_id)
        self._write_slot(entity.id, name, _lower(value,
                                                 "restore #%d.%s"
                                                 % (entity.id, name)))
        self.revision += 1

    def _slots_of(self, entity_id: int) -> "dict":
        return self._slots.get(entity_id, {})

    def _write_slot(self, entity_id: int, name: str, value) -> None:
        """Store `value` under `name`, keeping the name index in step.
        The one place a slot is written; every write verb funnels here."""
        self._slots.setdefault(entity_id, {})[name] = value
        self._by_name.setdefault(name, set()).add(entity_id)

    def _drop_slot(self, entity_id: int, name: str):
        """Remove the slot and return its old value, keeping the index in
        step. The caller has already checked it is present."""
        slots = self._slots[entity_id]
        old = slots.pop(name)
        if not slots:
            del self._slots[entity_id]
        bucket = self._by_name.get(name)
        if bucket is not None:
            bucket.discard(entity_id)
            if not bucket:
                del self._by_name[name]
        return old

    # -- writing -----------------------------------------------------

    def spawn(self) -> Entity:
        """A new, bare entity. The only way to make one -- there is no such
        thing as an entity that never existed here. Give it attributes with
        `set`/`add`/`mark`; a "component" is not attached, it is a name."""
        self._next += 1
        entity = Entity(self, self._next)
        self._entities[entity.id] = entity
        self.revision += 1
        self._record("spawn", entity.id, [])
        return entity

    def _adopt(self, entity_id: int) -> Entity:
        """The handle for this id, making the entity if it is not here.

        The one thing that exists for `loopingrules.save`, and the only way
        an entity ever gets an id it did not just take from the counter. It
        keeps the counter above whatever it has seen, so a restored world
        cannot hand a new entity an id some stored reference still points
        at -- and it does NOT move `revision`, because restoring is not
        something that happened to the world, it IS the world.
        """
        entity = self._entities.get(entity_id)
        if entity is None:
            entity = self._entities[entity_id] = Entity(self, entity_id)
            self._next = max(self._next, entity_id)
        return entity

    def destroy(self, entity) -> bool:
        """It is not here any more, and neither is anything on it. True if
        it was. What a rule calls on an occasion it has finished with."""
        entity_id = self._id(entity)
        if self._entities.pop(entity_id, None) is None:
            return False
        slots = self._slots.pop(entity_id, {})
        payload = [(name, value, MISSING) for name, value in slots.items()]
        for name in slots:
            bucket = self._by_name.get(name)
            if bucket is not None:
                bucket.discard(entity_id)
                if not bucket:
                    del self._by_name[name]
        self.revision += 1
        self._record("destroy", entity_id, payload)
        return True

    def set(self, entity, name, value) -> Entity:
        """Write the WHOLE slot `name` to `value` -- a scalar for a
        singular, a list for a `set`/`sequence`. Re-setting a value equal to
        what is already there is not a change: `revision` does not move,
        which is what lets a rule recompute the same answer every tick and
        still let the world settle.

        A live `Entity` as `value` (or inside the list) is lowered to its
        plain id before storing -- see the module note; anything else that
        is not a scalar, a reference, or a flat list of those raises,
        naming the attribute.
        """
        entity_id = self._id(entity)
        if entity_id not in self._entities:
            raise ValueError("%r is not in this world" % (entity,))
        if not isinstance(name, str):
            raise TypeError("an attribute name must be a str, not %s"
                            % type(name).__name__)
        lowered = _lower(value, "%s.%s" % (entity, name))
        old = self._slots_of(entity_id).get(name, MISSING)
        if old is not MISSING and old == lowered:
            return self._entities[entity_id]
        self._write_slot(entity_id, name, lowered)
        self.revision += 1
        self._record("set", entity_id, [(name, old, lowered)])
        return self._entities[entity_id]

    def unset(self, entity, name) -> bool:
        """Remove the slot `name` entirely. True if it was there. See `set`
        with an empty list to leave a collection present but empty."""
        entity_id = self._id(entity)
        if name not in self._slots_of(entity_id):
            return False
        old = self._drop_slot(entity_id, name)
        self.revision += 1
        self._record("unset", entity_id, [(name, old, MISSING)])
        return True

    def add(self, entity, name, item) -> bool:
        """Add `item` to the list held under `name`, deduped (insertion
        order kept) -- the `set`-kind verb. `True` if it was not already
        there. A name that does not exist yet starts an empty list; a name
        holding a non-list raises (the kind is the schema's, but the SHAPE
        is enforced here)."""
        entity_id = self._id(entity)
        item = _lower(item, "%s.%s[]" % (entity, name))
        current = self._slots_of(entity_id).get(name, MISSING)
        if current is MISSING:
            fresh = [item]
        elif isinstance(current, list):
            if item in current:
                return False
            fresh = current + [item]
        else:
            raise TypeError("add() wants a list-valued attribute; %s.%s holds "
                            "a %s" % (entity, name, type(current).__name__))
        self._write_slot(entity_id, name, fresh)
        self.revision += 1
        self._record("add", entity_id, [(name, current, fresh)])
        return True

    def remove(self, entity, name, item) -> bool:
        """Remove ONE occurrence of `item` from the list held under `name`,
        leaving the rest standing -- the `set`-kind remover. True if it was
        there."""
        entity_id = self._id(entity)
        item = _lower(item, "%s.%s[]" % (entity, name))
        current = self._slots_of(entity_id).get(name, MISSING)
        if current is MISSING:
            return False
        if not isinstance(current, list):
            raise TypeError("remove() wants a list-valued attribute; %s.%s "
                            "holds a %s" % (entity, name,
                                            type(current).__name__))
        if item not in current:
            return False
        kept = list(current)
        kept.remove(item)
        self._write_slot(entity_id, name, kept)
        self.revision += 1
        self._record("remove", entity_id, [(name, current, kept)])
        return True

    def append(self, entity, name, item) -> Entity:
        """Append `item` to the list held under `name`, duplicates kept --
        the `sequence`-kind verb. Every call changes something (there is
        nothing to dedupe against), so a non-settling sequence is a `hot`
        loop the budget catches."""
        entity_id = self._id(entity)
        item = _lower(item, "%s.%s[]" % (entity, name))
        current = self._slots_of(entity_id).get(name, MISSING)
        if current is MISSING:
            fresh = [item]
        elif isinstance(current, list):
            fresh = current + [item]
        else:
            raise TypeError("append() wants a list-valued attribute; %s.%s "
                            "holds a %s" % (entity, name,
                                            type(current).__name__))
        self._write_slot(entity_id, name, fresh)
        self.revision += 1
        self._record("append", entity_id, [(name, current, fresh)])
        return self._entities[entity_id]

    def pop(self, entity, name, index=-1):
        """Remove and return the item at `index` (last by default) from the
        list held under `name`. `None` if the name is not there; `IndexError`
        if the list is empty."""
        entity_id = self._id(entity)
        current = self._slots_of(entity_id).get(name, MISSING)
        if current is MISSING:
            return None
        if not isinstance(current, list):
            raise TypeError("pop() wants a list-valued attribute; %s.%s "
                            "holds a %s" % (entity, name,
                                            type(current).__name__))
        if not current:
            raise IndexError("pop() from an empty list: %s.%s"
                             % (entity, name))
        item = current[index]
        kept = list(current)
        del kept[index]
        self._write_slot(entity_id, name, kept)
        self.revision += 1
        self._record("pop", entity_id, [(name, current, kept)])
        return item

    def mark(self, entity, name) -> Entity:
        """Set the unit marker on `name` -- the `flag` verb. Re-marking is
        not a change."""
        entity_id = self._id(entity)
        if entity_id not in self._entities:
            raise ValueError("%r is not in this world" % (entity,))
        if not isinstance(name, str):
            raise TypeError("an attribute name must be a str, not %s"
                            % type(name).__name__)
        old = self._slots_of(entity_id).get(name, MISSING)
        if old is True:
            return self._entities[entity_id]
        self._write_slot(entity_id, name, True)
        self.revision += 1
        self._record("mark", entity_id, [(name, old, True)])
        return self._entities[entity_id]

    def unmark(self, entity, name) -> bool:
        """Remove the unit marker on `name` -- the `flag` verb's other
        direction. True if it was marked."""
        entity_id = self._id(entity)
        if self._slots_of(entity_id).get(name, MISSING) is not True:
            return False
        old = self._drop_slot(entity_id, name)
        self.revision += 1
        self._record("unmark", entity_id, [(name, old, MISSING)])
        return True

    def purge_transient(self) -> int:
        """Drop every slot whose NAME is in `world.transient`, everywhere.
        Returns how many slots were dropped -- `0` if none were set."""
        dropped = 0
        for name in list(self.transient):
            bucket = self._by_name.get(name)
            if not bucket:
                continue
            for entity_id in list(bucket):
                slots = self._slots.get(entity_id)
                if slots and name in slots:
                    slots.pop(name)
                    dropped += 1
                    if not slots:
                        del self._slots[entity_id]
            del self._by_name[name]
        if dropped:
            self.revision += 1
            self._record("purge", None, [])
        return dropped

    def changed(self, entity=None) -> None:
        """Something changed that no write said -- a cache a domain keeps
        by hand, mutated in place."""
        self.revision += 1
        self._record("changed",
                     None if entity is None else self._id(entity), [])

    # -- reading -----------------------------------------------------

    def alive(self, entity) -> bool:
        return self._id(entity) in self._entities

    def get(self, entity, name, default=None):
        """The value of `name` on this entity, or `default` if the slot is
        absent. There is at most one slot per name, so unlike the component
        engine's `get`/`get_all` there is nothing to refuse to guess
        between; `has` is how a caller tells an absent slot from one that
        holds `None`."""
        value = self._slots_of(self._id(entity)).get(name, MISSING)
        return default if value is MISSING else value

    def has(self, entity, *names) -> bool:
        slots = self._slots_of(self._id(entity))
        return bool(slots) and all(name in slots for name in names)

    def populated(self, *names) -> bool:
        """Whether ANY entity carries at least one of these attribute
        names -- the dormancy gate's own test."""
        return any(self._by_name.get(name) for name in names)

    def each(self, *names, without=()) -> "list":
        """Every entity carrying ALL of these attributes, oldest first::

            for entity, tele in w.each("telephone"):
            for entity, card, tags in w.each("card", "tags")

        ONE tuple per entity: the entity, then its values in the order
        asked for. There is at most one slot per name, so there is no cross
        product and no `get_all` -- a multi-valued attribute is a list, and
        the row's value for it IS that list.

        `without` excludes any entity carrying one of those names.
        Materialised, not lazy -- a rule is expected to spawn and destroy
        while it walks what it found.
        """
        if not names:
            raise TypeError("each() needs at least one attribute name")
        if isinstance(without, str):
            without = (without,)
        buckets = [self._by_name.get(name) or set() for name in names]
        excluded = [self._by_name.get(name) or set() for name in without]
        out = []
        # Walk the rarest name and check the rest: a query is as cheap as
        # its most specific term, not as its widest.
        for entity_id in sorted(min(buckets, key=len)):
            if any(entity_id not in bucket for bucket in buckets):
                continue
            if any(entity_id in bucket for bucket in excluded):
                continue
            slots = self._slots[entity_id]
            out.append((self._entities[entity_id],)
                       + tuple(slots[name] for name in names))
        return out

    def first(self, *names, without=()):
        """The first match of `each`, or None."""
        found = self.each(*names, without=without)
        return found[0] if found else None

    def the(self, name):
        """The value of `name` on the oldest entity carrying it -- the
        singleton idiom (the clock, the session, a policy), and the closest
        this API has to the component engine's `the(Kind)`. `None` if no
        entity carries it. Note a name whose value is a reference returns
        the id; walk it with `get` on `entity(id)` to read the shape."""
        bucket = self._by_name.get(name)
        if not bucket:
            return None
        entity_id = min(bucket)
        return self._slots[entity_id][name]

    def all(self, name) -> "list":
        """Every `(entity, value)` for one attribute, anywhere, oldest
        first -- the world-wide counterpart to `get`."""
        bucket = self._by_name.get(name)
        if not bucket:
            return []
        return [(self._entities[entity_id], self._slots[entity_id][name])
                for entity_id in sorted(bucket)]

    def attributes(self, entity) -> "dict":
        """Everything on it, as `{name: value}`, in the order the names were
        first set on it."""
        return dict(self._slots_of(self._id(entity)))

    def entities(self) -> "list":
        """Every entity, in the order it was spawned."""
        return [self._entities[i] for i in sorted(self._entities)]

    def changes(self, since=None, by=None, kind=None, changed=None,
                target=None) -> tuple:
        """The change log -- what has happened, oldest first.

        Filters, all optional and ANDed: `since` a `seq` (return only
        changes AFTER it), `by` a rule name, `kind` one of the kinds on
        `Change`, `changed` an attribute NAME (changes whose delta
        mentions it), and `target` an entity (handle or id).

        Called while a rule is running, it sees only changes made BEFORE
        the current tick: a rule never sees its own writes, nor another
        rule's from the same tick, so a rule cannot trigger on itself and
        drive an endless loop. Outside a rule (an install, a replay that
        has finished) it sees the whole log.
        """
        current_tick = self._tick if self._actor is not None else None
        target_id = None if target is None else self._id(target)
        out = []
        for change in self._changes:
            if current_tick is not None and change.tick >= current_tick:
                continue
            if since is not None and change.seq <= since:
                continue
            if by is not None and change.rule != by:
                continue
            if kind is not None and change.kind != kind:
                continue
            if target_id is not None and change.target != target_id:
                continue
            if changed is not None and not any(
                    delta[0] == changed for delta in change.payload):
                continue
            out.append(change)
        return tuple(out)

    def recent(self, n) -> tuple:
        """The last `n` changes `changes()` would return (`()` if `n <= 0`)."""
        if n <= 0:
            return ()
        return self.changes()[-n:]

    def show(self, entity) -> str:
        """`#7  cash=100  name='todo.txt'  tags=['urgent']`"""
        handle = entity if isinstance(entity, Entity) else self.entity(entity)
        body = "  ".join("%s=%r" % (name, value)
                         for name, value in self.attributes(entity).items())
        return "%-5s %s" % (handle, body)

    def __len__(self) -> int:
        return len(self._entities)

    def __contains__(self, entity) -> bool:
        if isinstance(entity, Entity):
            return entity.id in self._entities
        if isinstance(entity, int):
            return entity in self._entities
        return False
