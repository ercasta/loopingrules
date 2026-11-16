"""The world: entities, the components they carry, the fields in those
components, and the log of every change made to them.

An entity is identity, with no data of its own. Its data lives in **components**:
a component is a **named bag of fields** attached to an entity --
`w.set(person, "contact", "telephone", ["555", "556"])` -- and there is **at
most one component of each name per entity**, and **at most one field of each
name within a component**. Multiplicity lives INSIDE a field value (a list),
never in a second component or a second field. A component with no fields is a
**tag** (`w.mark(person, "active")`). This is ADR-10; the *declaration* (a
component's schema -- its name, its fields, their kinds) lives in
`loopingrules.schema`, and this module stores names and values and nothing else.

## A field value is a scalar, a reference, or a flat list

| Value | Meaning |
|---|---|
| `None` / `bool` / `int` / `float` / `str` | a scalar |
| another entity | a **reference**, stored as its plain `int` id |
| a **flat list** of the above | the multi-valued or ordered case |

**No dict, no tuple, no nesting.** Whatever looks like a structure is a
reference to an entity that carries the fields, not a value. `_lower` enforces
this at the one place a value enters the store.

## The kinds, and why this module is kind-agnostic

The schema declares each **field** one of four kinds (`loopingrules.schema`),
with the verbs a domain reaches for:

| Kind | Holds | Verbs | Settles? |
|---|---|---|---|
| **singular** | exactly one value | `set` / `unset` | re-`set` an equal value = no change |
| **set** | deduped, insertion-ordered | `add` / `remove` | `add` an equal value = no change |
| **sequence** | ordered, duplicates kept | `append` / `pop` | every `append` changes |
| **flag** | a unit marker within a component | `mark` / `unmark` | re-`mark` = no change |

This module does not read the schema and does not enforce these kinds: it
enforces only the SHAPE (an `add`/`append`/`remove`/`pop` wants a list, `set`
stores whatever it is handed). The declared kind, and whether a use agrees with
it, is the offline half -- `analyze`, the linter and the forge's gates. Keeping
the kinds out of the store is what lets the engine stay a store.

There is also a component-level `mark`/`unmark` for a **fieldless component** (a
tag): `w.mark(e, "done")` attaches the component `done` with no fields --
distinct from a *flag field* inside a component (`w.set(e, "trader", "done",
True)`), which this module stores the same way it stores any field.

## Every write lands in the change log

The same write methods also append to a transient, in-memory CHANGE LOG
(`World.changes` / `World.recent`): what changed, on which tick, and which rule
made the change (or `None`, for an install or the engine). A record's `payload`
holds field DELTAS `(component, field, old, new)`, where an absent side is spelled
with the `MISSING` sentinel rather than `None`; a component-level mark carries
`(component, None, old, new)`. The `changed=` filter on `changes()` names a
`(component, field)` SLOT. The log is never saved and is bounded only if a caller
asks (`Loop(capacity=...)`).

## Transience is a COMPONENT NAME

`world.transient` is the set of COMPONENT names a domain does not want written
down, and `purge_transient()` drops every such component, everywhere.
`save`/`share` skip them.

## What this does not settle

The naming convention for a reference field, how the JSON schema is versioned and
frozen, cycles in the ref graph, and whether a rule may set a field no component
declares -- are not answered here. This module only makes the substrate the
answer can be built on: names, components, fields, refs, lists, the kinds' verbs,
and a log of deltas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

_MARKER = object()


class _Missing:
    """The sentinel an absent side of a delta (and an absent slot in a change
    record) is spelled with -- distinct from `None`, which a value may
    legitimately hold. Compare with `MISSING` itself."""

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
    entity reference, or a **flat list** of those."""
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
                    "%s[%d]: a list field must be a flat list of scalars "
                    "(None/bool/int/float/str) or entity references -- got a "
                    "%s; a structured value is an entity, not a value"
                    % (where, index, type(item).__name__))
        return out
    raise TypeError(
        "%s: a field must be a scalar (None/bool/int/float/str), another "
        "entity (stored as its plain id, not the handle), or a flat list of "
        "those -- got a %s, which is a Python object this world cannot store "
        "or compare by value" % (where, type(value).__name__))


class Entity:
    """A handle: which entity, and in which world. No data of its own.

    Compares and hashes by id. Never store one AS a value -- the store lowers it
    to its plain id. Hold an entity to READ and WRITE through, not as data at
    rest.
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

    # Sugar, for the places a rule already holds the entity. Everything here is
    # `World`'s method with the entity filled in.
    def get(self, component, field, default=None):
        return self.world.get(self, component, field, default)

    def has(self, component, *fields) -> bool:
        return self.world.has(self, component, *fields)

    def set(self, component, field, value) -> "Entity":
        return self.world.set(self, component, field, value)

    def unset(self, component, field) -> bool:
        return self.world.unset(self, component, field)

    def add(self, component, field, item) -> bool:
        return self.world.add(self, component, field, item)

    def remove(self, component, field, item) -> bool:
        return self.world.remove(self, component, field, item)

    def append(self, component, field, item) -> "Entity":
        return self.world.append(self, component, field, item)

    def pop(self, component, field, index=-1):
        return self.world.pop(self, component, field, index)

    def mark(self, component) -> "Entity":
        return self.world.mark(self, component)

    def unmark(self, component) -> bool:
        return self.world.unmark(self, component)

    def components(self) -> "dict":
        return self.world.components(self)

    def destroy(self) -> bool:
        return self.world.destroy(self)

    @property
    def alive(self) -> bool:
        return self.world.alive(self)


class Change:
    """One mutation the world applied, as the change log records it.

    `seq` is monotonic across the world's whole life; `tick` is the loop's tick
    count at the moment (`0` before the first tick); `rule` names the rule that
    made it, or `None`; `kind` is one of
    `spawn`/`set`/`unset`/`add`/`remove`/`append`/`pop`/`mark`/`unmark`/
    `destroy`/`changed`/`purge`; `target` is the entity id touched (`None` for
    `purge`); and `payload` holds field DELTAS `(component, field, old, new)`,
    with an absent side spelled `MISSING` and `field=None` for a component-level
    mark. `spawn`/`changed`/`purge` carry no delta.
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


# A slot is `(component, field)`; `field` is `None` for a component-level
# reference (a tag, or a component-only read).
Slot = Tuple[str, Optional[str]]


class World:
    """Entities, the components on them, and the queries rules ask."""

    def __init__(self) -> None:
        self._entities: Dict[int, Entity] = {}
        # entity id -> {component: {field: value}}, in declaration order; a
        # component is PRESENT iff its name is a key, and a tag is a key with an
        # empty bag.
        self._slots: Dict[int, Dict[str, Dict[str, Any]]] = {}
        # component -> {entity id}; (component, field) -> {entity id}: the
        # indexes a query runs on.
        self._by_component: Dict[str, Set[int]] = {}
        self._by_field: Dict[Tuple[str, str], Set[int]] = {}
        self._next = 0
        self.revision = 0
        # The COMPONENT names a domain does not want written down.
        self.transient: Set[str] = set()
        # The (component, field) slots whose value is an entity REFERENCE rather
        # than an ordinary value -- the schema's ref declaration, carried here so
        # `share` can remap a pack id without trusting the file.
        self.refs: Set[Tuple[str, str]] = set()
        self._changes: List[Change] = []
        self._seq = 0
        self._actor = None
        self._tick = 0
        self._log_capacity = None

    def _record(self, kind: str, target, payload) -> None:
        self._changes.append(Change(seq=self._seq, tick=self._tick,
                                    rule=self._actor, kind=kind,
                                    target=target, payload=payload))
        self._seq += 1
        capacity = self._log_capacity
        if capacity is not None and len(self._changes) > capacity:
            del self._changes[:len(self._changes) - capacity]

    def clear_changes(self) -> None:
        self._changes.clear()

    # -- entity ids, handles, either -----------------------------------

    def _id(self, entity) -> int:
        return entity.id if isinstance(entity, Entity) else int(entity)

    def entity(self, entity_id) -> Entity:
        return Entity(self, int(entity_id))

    # -- component/field index maintenance -----------------------------

    def _bag(self, entity_id: int, component: str) -> Dict[str, Any]:
        """The component's bag, creating it (and the component's presence) if it
        is not there. The one place a component is added."""
        comps = self._slots.setdefault(entity_id, {})
        bag = comps.get(component)
        if bag is None:
            bag = comps[component] = {}
            self._by_component.setdefault(component, set()).add(entity_id)
        return bag

    def _write_field(self, entity_id: int, component: str, field: str,
                     value: Any) -> None:
        self._bag(entity_id, component)[field] = value
        self._by_field.setdefault((component, field), set()).add(entity_id)

    def _drop_field(self, entity_id: int, component: str, field: str) -> Any:
        bag = self._slots[entity_id][component]
        old = bag.pop(field)
        bucket = self._by_field.get((component, field))
        if bucket is not None:
            bucket.discard(entity_id)
            if not bucket:
                del self._by_field[(component, field)]
        return old

    def _drop_component(self, entity_id: int, component: str) -> Dict[str, Any]:
        comps = self._slots[entity_id]
        bag = comps.pop(component)
        for field in bag:
            bucket = self._by_field.get((component, field))
            if bucket is not None:
                bucket.discard(entity_id)
                if not bucket:
                    del self._by_field[(component, field)]
        bucket = self._by_component.get(component)
        if bucket is not None:
            bucket.discard(entity_id)
            if not bucket:
                del self._by_component[component]
        if not comps:
            del self._slots[entity_id]
        return bag

    def _slots_of(self, entity_id: int) -> Dict[str, Dict[str, Any]]:
        return self._slots.get(entity_id, {})

    def _field(self, entity_id: int, component: str, field: str) -> Any:
        return self._slots.get(entity_id, {}).get(component, {}).get(field, MISSING)

    # -- writing -------------------------------------------------------

    def spawn(self) -> Entity:
        """A new, bare entity. The only way to make one."""
        self._next += 1
        entity = Entity(self, self._next)
        self._entities[entity.id] = entity
        self.revision += 1
        self._record("spawn", entity.id, [])
        return entity

    def _adopt(self, entity_id: int) -> Entity:
        entity = self._entities.get(entity_id)
        if entity is None:
            entity = self._entities[entity_id] = Entity(self, entity_id)
            self._next = max(self._next, entity_id)
        return entity

    def _restore_tag(self, entity_id: int, component: str) -> None:
        """Put a tag back WITHOUT logging a `Change` -- what `save.load` uses.
        Not part of the rule-facing API."""
        self._adopt(entity_id)
        self._bag(entity_id, component)
        self.revision += 1

    def _restore(self, entity_id: int, component: str, field: str,
                 value: Any) -> None:
        """Put a field back WITHOUT logging a `Change` -- what `save.load` uses.
        Not part of the rule-facing API."""
        entity = self._adopt(entity_id)
        self._write_field(entity.id, component, field,
                          _lower(value, "restore #%d.%s.%s"
                                 % (entity.id, component, field)))
        self.revision += 1

    def destroy(self, entity) -> bool:
        entity_id = self._id(entity)
        if self._entities.pop(entity_id, None) is None:
            return False
        comps = self._slots.pop(entity_id, {})
        payload = []
        for component, bag in comps.items():
            for field, value in bag.items():
                payload.append((component, field, value, MISSING))
            bucket = self._by_component.get(component)
            if bucket is not None:
                bucket.discard(entity_id)
                if not bucket:
                    del self._by_component[component]
            for field in bag:
                field_bucket = self._by_field.get((component, field))
                if field_bucket is not None:
                    field_bucket.discard(entity_id)
                    if not field_bucket:
                        del self._by_field[(component, field)]
        self.revision += 1
        self._record("destroy", entity_id, payload)
        return True

    def set(self, entity, component, field, value) -> Entity:
        """Write the WHOLE field `(component, field)` to `value`. Re-setting an
        equal value is not a change."""
        entity_id = self._id(entity)
        if entity_id not in self._entities:
            raise ValueError("%r is not in this world" % (entity,))
        if not isinstance(component, str):
            raise TypeError("a component name must be a str, not %s"
                            % type(component).__name__)
        if not isinstance(field, str):
            raise TypeError("a field name must be a str, not %s"
                            % type(field).__name__)
        lowered = _lower(value, "%s.%s.%s" % (entity, component, field))
        old = self._field(entity_id, component, field)
        if old is not MISSING and old == lowered:
            return self._entities[entity_id]
        self._write_field(entity_id, component, field, lowered)
        self.revision += 1
        self._record("set", entity_id, [(component, field, old, lowered)])
        return self._entities[entity_id]

    def unset(self, entity, component, field) -> bool:
        """Remove the field `(component, field)`. True if it was there. The
        component stays present (possibly empty) -- see `unmark` to remove a
        whole tag."""
        entity_id = self._id(entity)
        if self._field(entity_id, component, field) is MISSING:
            return False
        old = self._drop_field(entity_id, component, field)
        self.revision += 1
        self._record("unset", entity_id, [(component, field, old, MISSING)])
        return True

    def add(self, entity, component, field, item) -> bool:
        """Add `item` to the list held at `(component, field)`, deduped
        (insertion order kept). True if it was not already there."""
        entity_id = self._id(entity)
        item = _lower(item, "%s.%s.%s[]" % (entity, component, field))
        current = self._field(entity_id, component, field)
        if current is MISSING:
            fresh = [item]
        elif isinstance(current, list):
            if item in current:
                return False
            fresh = current + [item]
        else:
            raise TypeError("add() wants a list-valued field; %s.%s.%s holds a "
                            "%s" % (entity, component, field,
                                    type(current).__name__))
        self._write_field(entity_id, component, field, fresh)
        self.revision += 1
        self._record("add", entity_id, [(component, field, current, fresh)])
        return True

    def remove(self, entity, component, field, item) -> bool:
        """Remove ONE occurrence of `item` from the list at `(component,
        field)`. True if it was there."""
        entity_id = self._id(entity)
        item = _lower(item, "%s.%s.%s[]" % (entity, component, field))
        current = self._field(entity_id, component, field)
        if current is MISSING or not isinstance(current, list) or item not in current:
            return False
        kept = list(current)
        kept.remove(item)
        self._write_field(entity_id, component, field, kept)
        self.revision += 1
        self._record("remove", entity_id, [(component, field, current, kept)])
        return True

    def append(self, entity, component, field, item) -> Entity:
        """Append `item` to the list at `(component, field)`, duplicates kept.
        Every call changes something."""
        entity_id = self._id(entity)
        item = _lower(item, "%s.%s.%s[]" % (entity, component, field))
        current = self._field(entity_id, component, field)
        if current is MISSING:
            fresh = [item]
        elif isinstance(current, list):
            fresh = current + [item]
        else:
            raise TypeError("append() wants a list-valued field; %s.%s.%s "
                            "holds a %s" % (entity, component, field,
                                            type(current).__name__))
        self._write_field(entity_id, component, field, fresh)
        self.revision += 1
        self._record("append", entity_id, [(component, field, current, fresh)])
        return self._entities[entity_id]

    def pop(self, entity, component, field, index=-1):
        """Remove and return the item at `index` (last by default) from the list
        at `(component, field)`. `None` if the field is not there; `IndexError`
        if the list is empty."""
        entity_id = self._id(entity)
        current = self._field(entity_id, component, field)
        if current is MISSING:
            return None
        if not isinstance(current, list):
            raise TypeError("pop() wants a list-valued field; %s.%s.%s holds a "
                            "%s" % (entity, component, field,
                                    type(current).__name__))
        if not current:
            raise IndexError("pop() from an empty list: %s.%s.%s"
                             % (entity, component, field))
        item = current[index]
        kept = list(current)
        del kept[index]
        self._write_field(entity_id, component, field, kept)
        self.revision += 1
        self._record("pop", entity_id, [(component, field, current, kept)])
        return item

    def mark(self, entity, component) -> Entity:
        """Attach the **tag** `component` -- a fieldless component. Re-marking is
        not a change."""
        entity_id = self._id(entity)
        if entity_id not in self._entities:
            raise ValueError("%r is not in this world" % (entity,))
        if component in self._slots_of(entity_id):
            return self._entities[entity_id]
        self._bag(entity_id, component)
        self.revision += 1
        self._record("mark", entity_id, [(component, None, MISSING, True)])
        return self._entities[entity_id]

    def unmark(self, entity, component) -> bool:
        """Remove the tag (or component) `component` entirely, with its fields.
        True if it was present."""
        entity_id = self._id(entity)
        if component not in self._slots_of(entity_id):
            return False
        bag = self._drop_component(entity_id, component)
        payload = [(component, field, value, MISSING)
                   for field, value in bag.items()]
        if not payload:
            payload = [(component, None, True, MISSING)]
        self.revision += 1
        self._record("unmark", entity_id, payload)
        return True

    def purge_transient(self) -> int:
        """Drop every COMPONENT whose name is in `world.transient`, everywhere.
        Returns how many components were dropped."""
        dropped = 0
        for component in list(self.transient):
            bucket = self._by_component.get(component)
            if not bucket:
                continue
            for entity_id in list(bucket):
                self._drop_component(entity_id, component)
                dropped += 1
        if dropped:
            self.revision += 1
            self._record("purge", None, [])
        return dropped

    def changed(self, entity=None) -> None:
        """Something changed that no write said -- a cache a domain keeps by
        hand, mutated in place."""
        self.revision += 1
        self._record("changed", None if entity is None else self._id(entity), [])

    # -- reading -------------------------------------------------------

    def alive(self, entity) -> bool:
        return self._id(entity) in self._entities

    def get(self, entity, component, field, default=None):
        """The value at `(component, field)`, or `default` if absent. `has` is
        how a caller tells an absent field from one that holds `None`."""
        value = self._field(self._id(entity), component, field)
        return default if value is MISSING else value

    def has(self, entity, component, *fields) -> bool:
        """Whether the entity carries `component` and (if any are named) all of
        these `fields`."""
        bag = self._slots_of(self._id(entity)).get(component)
        if bag is None:
            return False
        return all(field in bag for field in fields)

    def populated(self, *slots) -> bool:
        """Whether ANY entity carries at least one of these -- the dormancy
        gate's own test. A slot is `(component, field)`, or a bare component
        name (or `(component, None)`) for a component-level read."""
        for slot in slots:
            if isinstance(slot, str):
                if self._by_component.get(slot):
                    return True
                continue
            component, field = slot
            if field is None:
                if self._by_component.get(component):
                    return True
            elif self._by_field.get((component, field)):
                return True
        return False

    def each(self, component, *fields, without=()) -> "list":
        """Every entity carrying `component` and ALL of these `fields`, oldest
        first::

            for entity, tele in w.each("contact", "telephone"):
            for entity, card, price in w.each("listing", "card", "price")

        ONE tuple per entity: the entity, then its values in the order asked
        for. No `fields` asks only that the COMPONENT is present (a tag). A
        multi-valued field is a list, and the row's value for it IS that list.

        `without` excludes any entity carrying one of those COMPONENTS. A single
        name may be given bare (`without="done"`) or as an iterable
        (`without=("done",)`); a bare str is one component, NOT its characters.
        """
        if isinstance(without, str):
            without = (without,)
        if fields:
            buckets = [self._by_field.get((component, f)) or set()
                       for f in fields]
        else:
            buckets = [self._by_component.get(component) or set()]
        excluded = [self._by_component.get(c) or set() for c in without]
        out = []
        for entity_id in sorted(min(buckets, key=len)):
            if any(entity_id not in b for b in buckets):
                continue
            if any(entity_id in b for b in excluded):
                continue
            bag = self._slots[entity_id][component]
            out.append((self._entities[entity_id],)
                       + tuple(bag[f] for f in fields))
        return out

    def first(self, component, *fields, without=()):
        """The first match of `each`, or None."""
        found = self.each(component, *fields, without=without)
        return found[0] if found else None

    def the(self, component, field):
        """The value at `(component, field)` on the oldest entity carrying it --
        the singleton idiom. `None` if no entity does."""
        bucket = self._by_field.get((component, field))
        if not bucket:
            return None
        entity_id = min(bucket)
        return self._slots[entity_id][component][field]

    def all(self, component, field) -> "list":
        """Every `(entity, value)` for one field, anywhere, oldest first."""
        bucket = self._by_field.get((component, field))
        if not bucket:
            return []
        return [(self._entities[entity_id],
                 self._slots[entity_id][component][field])
                for entity_id in sorted(bucket)]

    def components(self, entity) -> "dict":
        """Everything on it, as `{component: {field: value}}`, in the order the
        components were first attached."""
        return {component: dict(bag)
                for component, bag in self._slots_of(self._id(entity)).items()}

    def entities(self) -> "list":
        """Every entity, in the order it was spawned."""
        return [self._entities[i] for i in sorted(self._entities)]

    def changes(self, since=None, by=None, kind=None, changed=None,
                target=None) -> tuple:
        """The change log -- what has happened, oldest first.

        Filters, all optional and ANDed: `since` a `seq`, `by` a rule name,
        `kind` one of the kinds on `Change`, `changed` a `(component, field)`
        slot, and `target` an entity. Called while a rule is running, it sees
        only changes made BEFORE the current tick.
        """
        current_tick = self._tick if self._actor is not None else None
        target_id = None if target is None else self._id(target)
        if changed is not None and isinstance(changed, str):
            changed = (changed, None)
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
            if changed is not None and not self._mentions(change, changed):
                continue
            out.append(change)
        return tuple(out)

    @staticmethod
    def _mentions(change, slot) -> bool:
        """Whether a change's payload touches `slot` -- `(component, field)`, or
        `(component, None)` for any field of that component."""
        component, field = slot
        for delta in change.payload:
            if delta[0] != component:
                continue
            if field is None or delta[1] == field:
                return True
        return False

    def recent(self, n) -> tuple:
        """The last `n` changes `changes()` would return (`()` if `n <= 0`)."""
        if n <= 0:
            return ()
        return self.changes()[-n:]

    def show(self, entity) -> str:
        """`#7  trader{cash=100, at=#3}  done`"""
        handle = entity if isinstance(entity, Entity) else self.entity(entity)
        parts = []
        for component, bag in self.components(handle).items():
            if bag:
                body = ", ".join("%s=%r" % (f, v) for f, v in bag.items())
                parts.append("%s{%s}" % (component, body))
            else:
                parts.append(component)
        return "%-5s %s" % (handle, "  ".join(parts))

    def __len__(self) -> int:
        return len(self._entities)

    def __contains__(self, entity) -> bool:
        if isinstance(entity, Entity):
            return entity.id in self._entities
        if isinstance(entity, int):
            return entity in self._entities
        return False
