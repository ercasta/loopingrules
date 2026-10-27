"""The world model: entities, the components they carry, and the log of
every change made to them.

Entities are identity, components are data, and `World` is the one place
both are read and written. Every write ALSO lands in a transient, in-memory
CHANGE LOG (`World.changes` / `World.recent`): what changed, on which tick,
and which rule made the change (or `None`, for an install or the engine).
A rule reads the log to condition on what HAS HAPPENED, not only on what is
true now -- see `docs/plan-memory.md`. The log is never saved (`save.dump`
walks entities and components, and the log is neither) and is bounded only
if a caller asks (`Loop(capacity=...)`); anything meant to survive is an
ordinary component a rule chose to attach. `Loop.tick` sets `_actor` and
`_tick` around each rule call, which is the whole of the log's provenance.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List


_PRIMITIVES = (type(None), bool, int, float, str)


class Entity:
    """A handle: which entity, and in which world. No data of its own.

    Compares and hashes by id, so a handle handed back by a query is the
    same one a component stored earlier, and a component holding `#7` goes
    on meaning `#7` however many times it is looked up.

    Important: never store one of these AS a component field -- see the module note.
    Hold its `.id` there instead; this class exists for the API surface a
    rule reads and writes through, not for data at rest.
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
    def get(self, kind):
        return self.world.get(self, kind)

    def get_all(self, kind) -> "list":
        return self.world.get_all(self, kind)

    def has(self, *kinds) -> bool:
        return self.world.has(self, *kinds)

    def attach(self, *components) -> "Entity":
        return self.world.attach(self, *components)

    def replace(self, *components) -> "Entity":
        return self.world.replace(self, *components)

    def detach(self, *kinds) -> bool:
        return self.world.detach(self, *kinds)

    def remove(self, component) -> bool:
        return self.world.remove(self, component)

    def destroy(self) -> bool:
        return self.world.destroy(self)

    @property
    def alive(self) -> bool:
        return self.world.alive(self)


def transient(cls):
    """Mark a component class TRANSIENT: real data, attachable and
    queryable exactly like any other component -- `attach`/`get`/`each`/...
    don't know or care -- but disposable, and known to be so. 
    `loopingrules.save.dump()` skips every instance of a
    transient kind, and `World.purge_transient()` (below) drops them all on
    demand. 

        @transient
        @dataclasses.dataclass(frozen=True)
        class Iteration:
            item: int
            sequence: int
            does: int
    """
    cls._transient = True
    return cls


def is_transient(kind) -> bool:
    """Whether `kind` (a component class) was marked `@transient`, above.
    `False` for anything that was not -- including a plain class that
    happens to define its own unrelated `_transient` attribute, the same
    risk any convention-based marker takes; no component in this codebase
    does that today."""
    return bool(getattr(kind, "_transient", False))

def _lower(value: Any, where: str) -> Any:
    """`value`, with any `Entity` turned into its plain id -- recursively,
    through `list`/`dict`/`tuple` -- or a `TypeError` naming `where` if
    what is left still is not data `attach()` can store. See the module
    note: this is the one place "a component holds no Python object
    references" is enforced rather than merely documented.
    """
    if isinstance(value, Entity):
        return value.id
    if isinstance(value, _PRIMITIVES):
        return value
    if isinstance(value, tuple):
        return tuple(_lower(v, where) for v in value)
    if isinstance(value, list):
        return [_lower(v, where) for v in value]
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError("%s: a dict key must be a string, not %s"
                                % (where, type(key).__name__))
        return {k: _lower(v, where) for k, v in value.items()}
    raise TypeError(
        "%s: a component field must be a primitive (None/bool/int/float/"
        "str), another entity (stored as its plain id, not the handle), "
        "or a list/dict/tuple of those -- got a %s, which is a reference "
        "to a Python object this world cannot store or compare by value"
        % (where, type(value).__name__))


def _normalize(component: Any) -> Any:
    """The same component, if none of its fields needed lowering; a FRESH
    one, built without calling `__init__` (so this works whether or not the
    dataclass is frozen), otherwise. Compared by value, not by identity, so
    a field that round-trips to something equal (a tuple rebuilt from
    already-plain ints, say) does not force a needless rebuild.
    """
    if not dataclasses.is_dataclass(component) or isinstance(component, type):
        raise TypeError(
            "attach() wants a component INSTANCE -- a plain @dataclass -- "
            "got %r" % (component,))
    name = type(component).__name__
    changed = False
    fields = {}
    for f in dataclasses.fields(component):
        value = getattr(component, f.name)
        lowered = _lower(value, "%s.%s" % (name, f.name))
        fields[f.name] = lowered
        if lowered != value:
            changed = True
    if not changed:
        return component
    fresh = object.__new__(type(component))
    for field_name, value in fields.items():
        object.__setattr__(fresh, field_name, value)
    return fresh

@dataclasses.dataclass(frozen=True)
class Change:
    """One mutation the world applied, as the change log records it.

    `seq` is monotonic across the world's whole life; `tick` is the loop's
    tick count at the moment (`0` before the first tick, so install-time
    writes are `tick == 0`); `rule` names the rule that made it, or `None`
    for a write made outside any rule (an install, the engine draining a
    `Reply`); `kind` is one of `spawn`/`attach`/`replace`/`detach`/
    `remove`/`destroy`/`changed`/`purge`; `target` is the entity id touched
    (`None` for `purge`); and `payload` holds the affected component
    INSTANCES -- those added for spawn/attach/replace, those removed for
    detach/remove/destroy, and empty where there is nothing to name.
    """

    seq: int
    tick: int
    rule: object
    kind: str
    target: object
    payload: tuple = ()


class World:
    """Entities, the components on them, and the queries rules ask."""

    def __init__(self) -> None:
        # entity id -> handle, in spawn order; and component type -> {entity
        # id: [components, in attach order]}. The second is the index every
        # query runs on: a query for three types is three dict lookups and
        # a walk of the smallest of them.
        self._entities: Dict[int, Entity] = {}
        self._by_type: Dict[type, Dict[int, List[Any]]] = {}
        self._next = 0
        # Bumped by every spawn, destroy, attach/replace that changed
        # something, and detach/remove that removed something. The loop
        # reads it to tell a rule that did something from one that did
        # not, which is the whole of how it knows the world has settled.
        self.revision = 0
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
        moved `revision`, never for a no-op (a re-attached equal value is
        not a change and must not be in the log, same guarantee settling
        rests on)."""
        self._changes.append(Change(seq=self._seq, tick=self._tick,
                                    rule=self._actor, kind=kind,
                                    target=target, payload=tuple(payload)))
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
        lets a component field holding a plain id (see the module note) be
        passed straight back into `get`/`has`/`attach`/... without a
        caller converting it to a handle first."""
        return entity.id if isinstance(entity, Entity) else int(entity)

    def entity(self, entity_id) -> Entity:
        """The handle for this id -- the other direction from a component
        field's plain int back to something `.get()`/`.attach()`/... work
        on. No existence check: the same trust level constructing `Entity`
        directly always had."""
        return Entity(self, int(entity_id))

    # -- writing -----------------------------------------------------

    def spawn(self, *components) -> Entity:
        """A new entity carrying these components. The only way to make one
        -- there is no such thing as an entity that never existed here."""
        self._next += 1
        entity = Entity(self, self._next)
        self._entities[entity.id] = entity
        self.revision += 1
        self._record("spawn", entity.id, [])
        if components:
            self.attach(entity, *components)
        return entity

    def _adopt(self, entity_id: int) -> Entity:
        """The handle for this id, making the entity if it is not here.

        The one thing that exists for `loopingrules.save`, and the only way
        an entity ever gets an id it did not just take from the counter. It
        keeps the counter above whatever it has seen, so a restored world
        cannot hand a new entity an id some component still points at --
        and it does NOT move `revision`, because restoring is not something
        that happened to the world, it IS the world.
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
        carried = []
        for bucket in self._by_type.values():
            carried.extend(bucket.pop(entity_id, None) or ())
        self.revision += 1
        self._record("destroy", entity_id, carried)
        return True

    def attach(self, entity, *components) -> Entity:
        """Add these components to whatever entity already carries of
        their own type -- deduped against what is already there, so
        re-attaching a value equal to one already present is not a
        change: it is not stored again and `revision` does not move,
        which is what lets a rule recompute the same answer every tick
        and still let the world settle.

        A live `Entity` inside a component field is lowered to its plain
        id before storing -- see the module note; anything else that is
        not JSON-shaped data raises, naming the field.
        """
        entity_id = self._id(entity)
        if entity_id not in self._entities:
            raise ValueError("%r is not in this world" % (entity,))
        added = []
        for component in components:
            component = _normalize(component)
            cls = type(component)
            values = self._by_type.setdefault(cls, {}).setdefault(entity_id, [])
            if component in values:
                continue
            values.append(component)
            self.revision += 1
            added.append(component)
        if added:
            self._record("attach", entity_id, added)
        return self._entities[entity_id]

    def replace(self, entity, *components) -> Entity:
        """Each given component replaces every existing component of ITS
        OWN type on this entity -- the tool for a kind meant to stay
        singular (`Session`, `Contents`, a folder's `Size`).

        Still idempotent: replacing with a value equal to what is already
        the sole component of that type is not a change, same guarantee as
        `attach`. Two components of the SAME type passed to one call each
        replace in turn, so only the last survives -- meant for one
        component per type per call, the way every call site that needs
        this reaches for it.
        """
        entity_id = self._id(entity)
        if entity_id not in self._entities:
            raise ValueError("%r is not in this world" % (entity,))
        replaced = []
        for component in components:
            cls = type(component)
            normalized = _normalize(component)
            bucket = self._by_type.setdefault(cls, {})
            if bucket.get(entity_id) == [normalized]:
                continue
            bucket[entity_id] = [normalized]
            self.revision += 1
            replaced.append(normalized)
        if replaced:
            self._record("replace", entity_id, replaced)
        return self._entities[entity_id]

    def detach(self, entity, *kinds) -> bool:
        """Take EVERY component of these types off it. True if any were
        there. See `remove` to take off one specific value and leave the
        rest of that type standing."""
        entity_id = self._id(entity)
        gone = False
        removed = []
        for kind in kinds:
            bucket = self._by_type.get(kind)
            popped = bucket.pop(entity_id, None) if bucket else None
            if popped is not None:
                self.revision += 1
                gone = True
                removed.extend(popped)
        if removed:
            self._record("detach", entity_id, removed)
        return gone

    def remove(self, entity, component) -> bool:
        """Take ONE component equal to this value off it, leaving any other
        instances of the same type standing. True if it was there."""
        entity_id = self._id(entity)
        component = _normalize(component)
        cls = type(component)
        bucket = self._by_type.get(cls)
        values = bucket.get(entity_id) if bucket else None
        if not values or component not in values:
            return False
        values.remove(component)
        if not values:
            del bucket[entity_id]
        self.revision += 1
        self._record("remove", entity_id, [component])
        return True

    def purge_transient(self) -> int:
        """Detach every component of every `@transient`-marked kind,
        everywhere in the world. Returns how many component INSTANCES were
        dropped -- `0` if nothing marked transient was ever attached.
        """
        dropped = 0
        for kind, bucket in list(self._by_type.items()):
            if not bucket or not is_transient(kind):
                continue
            for _, values in bucket.items():
                dropped += len(values)
                bucket.clear()
            self.revision += 1
        if dropped:
            self._record("purge", None, [])
        return dropped

    def changed(self, entity=None) -> None:
        """Something changed that no attach said -- an index a domain keeps
        by hand, mutated in place."""
        self.revision += 1
        self._record("changed",
                     None if entity is None else self._id(entity), [])

    # -- reading -----------------------------------------------------

    def alive(self, entity) -> bool:
        return self._id(entity) in self._entities

    def get(self, entity, kind):
        """The one component of this kind on this entity, or `None`.
        Refuses to guess between several -- `ValueError` naming how many
        there are; the caller wants `get_all()`."""
        values = self._by_type.get(kind, {}).get(self._id(entity), ())
        if not values:
            return None
        if len(values) > 1:
            raise ValueError(
                "%r carries %d %s components -- get() refuses to guess; "
                "the caller wants get_all()" % (entity, len(values), kind.__name__))
        return values[0]

    def get_all(self, entity, kind) -> "list":
        """Every component of this kind on this entity, in attach order.
        `[]` if none -- the plural counterpart to `get()`."""
        return list(self._by_type.get(kind, {}).get(self._id(entity), ()))

    def has(self, entity, *kinds) -> bool:
        entity_id = self._id(entity)
        return all(self._by_type.get(k, {}).get(entity_id) for k in kinds)

    def populated(self, *kinds) -> bool:
        """Whether ANY entity carries at least one of these component
        types """
        return any(self._by_type.get(k) for k in kinds)

    def each(self, *kinds, without=()) -> "list":
        """Every entity carrying all of these components, oldest first::

            for entity, entry, size in w.each(Entry, Size):
            for entity, wish in w.each(RenameWish, without=NeedsApproval):

        One tuple per match: the entity, then its components in the order
        asked for. An entity carrying SEVERAL of an intersecting kind
        yields one row per combination -- the cross product across the
        kinds asked for, degenerating to today's one-row-per-entity the
        moment every matched kind is single-valued there, which is every
        case this codebase has today.

        Materialised, not lazy -- a rule is expected to spawn and
        destroy while it walks what it found.
        """
        if not kinds:
            raise TypeError("each() needs at least one component type")
        if isinstance(without, type):
            without = (without,)
        buckets = [self._by_type.get(kind) or {} for kind in kinds]
        excluded = [self._by_type.get(kind) or {} for kind in without]
        out = []
        # Walk the rarest component and check the rest: a query is as
        # cheap as its most specific term, not as its widest.
        for entity_id in sorted(min(buckets, key=len)):
            if any(entity_id not in bucket for bucket in buckets):
                continue
            if any(entity_id in bucket for bucket in excluded):
                continue
            entity = self._entities[entity_id]
            per_kind = [bucket[entity_id] for bucket in buckets]
            for combo in _product(per_kind):
                out.append((entity,) + combo)
        return out

    def first(self, *kinds, without=()):
        """The first match of `each`, or None."""
        found = self.each(*kinds, without=without)
        return found[0] if found else None

    def the(self, kind):
        """The one component of a kind the world keeps exactly one of --
        the clock, the session. None if nothing carries it."""
        bucket = self._by_type.get(kind) or {}
        for entity_id in sorted(bucket):
            values = bucket[entity_id]
            if values:
                return values[0]
        return None

    def all(self, kind) -> "list":
        """Every component of this kind, anywhere -- `(entity, component)`
        per instance, entity first so a caller can trace it back without a
        component having to carry its own owner. World-wide counterpart to
        `get_all()`."""
        bucket = self._by_type.get(kind) or {}
        out = []
        for entity_id in sorted(bucket):
            entity = self._entities[entity_id]
            for component in bucket[entity_id]:
                out.append((entity, component))
        return out

    def components(self, entity) -> "list":
        """Everything on it, in the order the types were first seen, and
        within a type, the order it was attached in."""
        entity_id = self._id(entity)
        out = []
        for bucket in self._by_type.values():
            out.extend(bucket.get(entity_id, ()))
        return out

    def entities(self) -> "list":
        """Every entity, in the order it was spawned."""
        return [self._entities[i] for i in sorted(self._entities)]

    def changes(self, since=None, by=None, kind=None, changed=None,
                target=None) -> tuple:
        """The change log -- what has happened, oldest first.

        Filters, all optional and ANDed: `since` a `seq` (return only
        changes AFTER it), `by` a rule name, `kind` one of the kinds on
        `Change`, `changed` a component TYPE (changes whose payload
        mentions it -- added for attach/spawn/replace, removed for
        detach/remove/destroy), and `target` an entity (handle or id).

        Called while a rule is running, it sees only changes made BEFORE
        the current tick: a rule never sees its own writes, nor another
        rule's from the same tick, so a rule cannot trigger on itself and
        drive an endless loop. Outside a rule (an install, a replay that
        has finished) it sees the whole log. The `_record` call keeps the
        log in step with `revision` -- a no-op is in neither.
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
                    isinstance(c, changed) for c in change.payload):
                continue
            out.append(change)
        return tuple(out)

    def recent(self, n) -> tuple:
        """The last `n` changes `changes()` would return (`()` if `n <= 0`)."""
        if n <= 0:
            return ()
        return self.changes()[-n:]

    def show(self, entity) -> str:
        """`#7  Entry(folder=1, name='todo.txt')  Size(bytes=17)`"""
        handle = entity if isinstance(entity, Entity) else self.entity(entity)
        return "%-5s %s" % (handle, "  ".join(
            repr(c) for c in self.components(entity)))

    def __len__(self) -> int:
        return len(self._entities)

    def __contains__(self, entity) -> bool:
        if isinstance(entity, Entity):
            return entity.id in self._entities
        if isinstance(entity, int):
            return entity in self._entities
        return False


def _product(sequences: "list") -> "list":
    """The cross product of several lists, as a list of tuples --
    `itertools.product` spelled out so this module has no import beyond
    the standard library it already needed. `_product([[a], [b, c]])` is
    `[(a, b), (a, c)]`; `_product([[a]])` is `[(a,)]`, which is `each()`'s
    entire behaviour when every matched kind is single-valued.
    """
    out: "list" = [()]
    for sequence in sequences:
        out = [combo + (item,) for combo in out for item in sequence]
    return out
