"""Reflection: a rule's own structure, and the fact that it fired, reified
into the world so other rules can read them.

`world.py` already records every applied write as a `Change`, and `memory.py`
promotes selected changes into durable `remembered` entities keyed by the
rule that made them -- so "which rule fired" is already ordinary, queryable
world data. `analyze.py` already derives a rule's reads and writes from its
own source. What was missing is the join: nothing put a rule's OWN STRUCTURE
into the world, so no rule could read another rule and condition on it.

This module is that join, and it is small on purpose. Under the attribute
substrate (`docs/plan-attributes.md`, D8) a "component" is a SHAPE -- an
attribute set -- that an entity carries; so a `RuleCard` is an ordinary
entity tagged `rule_card`, whose attributes are the card's fields:

* a **card** entity: `rule_card` (flag) + `hash`, `name`, `reads` (a flat
  list of attribute names), `writes` (a flat list), `destroys`, `opaque`,
  `priority`. `reads`/`writes` are NAMES, derived by `analyze`, so a rule
  may ask "which rule writes `cash`?" without any import. `hash` is the
  rule's identity (see `rule_hash`), stable enough to key a control.
* a **control** entity: `rule_control` (flag) + `hash`, `enabled`,
  `priority` -- the shape the LOOP reads. A rule that deposits one changes
  the schedule: `enabled=False` skips the matching rule for the rest of
  the run, a non-default `priority` reorders it. This is the CONTROL
  CHANNEL, named as such rather than hidden: a second way rules affect each
  other, above the shared `World` (`PRINCIPLES.md`'s "the only channel
  between them is what gets deposited"). It stays stigmergic -- the
  controller deposits an entity, the loop is the single oblivious reader --
  but a controller never calls a rule, and a rule's own source is never
  edited to be controllable.
* `reify(loop)` -- deposit one card entity per registered rule. Idempotent,
  so calling it twice (or on a replayed loop) does not duplicate cards.

## Why this needed the engine at all

Because a rule cannot hold a reference to another rule -- rules are
functions, and `World` stores data, never callables or Python objects
(`world._lower` refuses them). The alternative to a hash-keyed control is
the stigmergic one: have each building-block rule read a control entity.
That was rejected on purpose: it requires EDITING every rule to be
controllable, which is exactly the coupling this module exists to avoid.
The hash keeps the rules untouched; the loop, which already knows every
rule, is the one reader.

## Precedence, which is the soundness rule

A control may only SUBTRACT or REORDER. A disabled rule is never called; a
reprioritised one is called in a different order. Neither can MANUFACTURE a
firing: `analyze`'s derived gate still decides dormancy, so an enabled rule
whose gate is closed stays skipped, and no controller can make a rule act on
reads it does not have. See `Loop._tick_order`.

## Homoiconicity

This is also locked decision 13 made literal: a rule is an entity whose
attributes *describe it*. Nothing here translates a rule into data it was
not already; the card's fields are the same names `analyze` reads off the
source.

## What this does not settle

* **The hash is provisional.** `rule_hash` hashes a rule's SOURCE (with a
  fallback to its qualified name). Two rules with identical source therefore
  share a hash. The intended identity, once rules are IR data
  (`docs/plan-reflection.md`), is a hash of the IR datum plus the attribute
  schema and operator version.
* **One control per hash is the contract.** Several are tolerated (the last
  in `each()` order wins, which is deterministic but not meaningful).
* **Runtime self-modification is deliberately absent.** A controller may
  select among the rules already registered; it may not add, remove or
  rewrite one. That is program synthesis, not control, and it belongs behind
  the forge's gates and a freeze (locked decision 8).
"""

from __future__ import annotations

import hashlib
import inspect

from . import analyze


# The flag that TAGS a card/control entity as that shape -- the attribute
# substrate's way of saying "this entity is a RuleCard", since there is no
# class to ask `isinstance` about.
CARD = "rule_card"
CONTROL = "rule_control"

_CARD_FIELDS = ("hash", "name", "reads", "writes", "destroys", "opaque",
                "priority")

_HASH_CACHE: "dict" = {}


def rule_name(fn) -> str:
    """`r0.bump` -- the name `Loop.rule` registers `fn` under, so reflection
    can match a card against a `remembered.rule` in the change log."""
    module = getattr(fn, "__module__", "") or ""
    return "%s.%s" % (module.rsplit(".", 1)[-1], getattr(fn, "__name__", "rule"))


def rule_hash(fn) -> str:
    """A content hash of `fn`'s own source -- its identity, independent of
    where it was registered. Falls back to the qualified name when no source
    is available (an interactive definition, a compiled module). See the
    module note: this is provisional, and the IR datum is the target.

    Memoised BY FUNCTION OBJECT, the same way `analyze.analyze` is.
    """
    cached = _HASH_CACHE.get(fn)
    if cached is not None:
        return cached
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = rule_name(fn)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    _HASH_CACHE[fn] = digest
    return digest


def identity(fn) -> str:
    """A rule's identity: a hash it already carries (a generator stamped an
    IR-datum hash on it -- see `loopingrules_forge.evolve`), else
    `rule_hash(fn)` from its source. `Loop.rule` and `card_for` both use this,
    so a generated rule is identified by its STRUCTURE, a hand-written one by
    its source, consistently."""
    return getattr(fn, "_loopingrules_hash", None) or rule_hash(fn)


def card_for(fn) -> dict:
    """The fields of one rule's card, derived by `analyze` (never
    hand-declared, so a card cannot drift from the rule it describes). A
    plain dict -- a card's canonical home is an ENTITY (`write_card`), and
    this is only the values that go into it."""
    try:
        analysis = analyze.analyze(fn)
    except analyze.Opaque:
        return {"hash": identity(fn), "name": rule_name(fn), "reads": (),
                "writes": (), "destroys": False, "opaque": True,
                "priority": getattr(fn, "_loopingrules_priority", 0)}
    return {
        "hash": identity(fn), "name": rule_name(fn),
        "reads": tuple(sorted(analysis.reads)),
        "writes": tuple(sorted(analysis.writes)),
        "destroys": analysis.destroys, "opaque": False,
        "priority": getattr(fn, "_loopingrules_priority", 0)}


def write_card(world, card: dict):
    """Deposit `card` (a `card_for` dict) as a tagged entity. Returns it."""
    entity = world.spawn()
    world.mark(entity, CARD)
    for field in _CARD_FIELDS:
        world.set(entity, field, list(card[field])
                  if isinstance(card[field], tuple) else card[field])
    return entity


def read_card(world, entity) -> dict:
    """The card fields off a card entity, as the same dict `card_for`
    returns -- so a rule reading a card and a rule describing one speak the
    same shape."""
    return {field: world.get(entity, field) for field in _CARD_FIELDS}


def cards(world) -> "list":
    """Every `(entity, fields)` for a card in the world, oldest first."""
    return [(entity, read_card(world, entity))
            for entity, _ in world.each(CARD)]


def reify(loop) -> list:
    """Deposit one card entity per rule registered on `loop`, keyed by hash.

    Idempotent: a hash already carrying a card is left alone, so calling this
    once per install, or again after a restore, does not duplicate. Call it
    after every rule the domain wants visible is registered and before the
    loop runs. Returns `[(entity, card)]`.
    """
    world = loop.world
    seen = {h for _e, _t, h in world.each(CARD, "hash")}
    placed = []
    for _name, fn in loop.rules:
        card = card_for(fn)
        if card["hash"] in seen:
            continue
        seen.add(card["hash"])
        placed.append((write_card(world, card), card))
    return placed


# -- the control channel --------------------------------------------------

def control(world, hash: str, enabled: bool = True, priority: int = 0):
    """Ensure a control entity for the rule named by `hash` exists with
    these fields -- find-or-create, so a controller that re-emits the SAME
    control every tick changes nothing and the world settles. The one shape
    `Loop._tick_order` reads; a rule with no control runs exactly as it
    always did, so this is opt-in."""
    existing = None
    for entity, _ in world.each(CONTROL):
        if world.get(entity, "hash") == hash:
            existing = entity
            break
    if existing is None:
        existing = world.spawn()
        world.mark(existing, CONTROL)
        world.set(existing, "hash", hash)
    world.set(existing, "enabled", bool(enabled))
    world.set(existing, "priority", int(priority))
    return existing


def control_map(world) -> dict:
    """`{hash: (enabled, priority)}` for every control in the world, last in
    `each()` order winning -- the contract is one control per hash; several
    are tolerated deterministically, not meaningfully."""
    out = {}
    for entity, _ in world.each(CONTROL):
        key = world.get(entity, "hash")
        out[key] = (world.get(entity, "enabled", True),
                    world.get(entity, "priority", 0))
    return out
