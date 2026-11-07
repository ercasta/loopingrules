"""Reflection: a rule's own structure, and the fact that it fired, reified
into the blackboard so other rules can read them.

`world.py` already records every applied write as a `Change`, and `memory.py`
promotes selected changes into durable `Remembered` components keyed by the
rule that made them -- so "which rule fired" is already ordinary, queryable
world data. `analyze.py` already derives a rule's reads and writes from its
own source. What was missing is the join: nothing put a rule's OWN STRUCTURE
into the world, so no rule could read another rule and condition on it.

This module is that join, and it is small on purpose:

* `RuleCard(hash, name, reads, writes, destroys, opaque, priority)` -- one
  per registered rule, a durable component. `reads`/`writes` are component
  class NAMES (a component field holds primitives only), derived by
  `analyze`, so a rule may ask "which rule writes `Counter`?" without any
  import. `hash` is the rule's identity (see `rule_hash`), stable enough to
  key a control reference.
* `RuleControl(hash, enabled, priority)` -- the shape the LOOP reads. A rule
  that attaches one changes the schedule: `enabled=False` skips the matching
  rule for the rest of the run, a non-default `priority` reorders it. This is
  the CONTROL CHANNEL, named as such rather than hidden: it is a second way
  rules affect each other, above the shared `World` (`PRINCIPLES.md`'s "the
  only channel between them is what gets deposited"). It stays stigmergic --
  the controller deposits a component, the loop is the single oblivious
  reader -- but a controller never calls a rule, and a rule's own source is
  never edited to be controllable.
* `reify(loop)` -- deposit one `RuleCard` per registered rule. Idempotent, so
  calling it twice (or on a replayed loop) does not duplicate cards.

## Why this needed the engine at all

Because a rule cannot hold a reference to another rule -- rules are functions,
and `World` stores data, never callables or Python objects (`world._lower`
refuses them). The alternative to a hash-keyed `RuleControl` is the stigmergic
one: have each building-block rule read a control component. That was
rejected on purpose: it requires EDITING every rule to be controllable, which
is exactly the coupling this module exists to avoid. The hash keeps the rules
untouched; the loop, which already knows every rule, is the one reader.

## Precedence, which is the soundness rule

`RuleControl` may only SUBTRACT or REORDER. A disabled rule is never called; a
reprioritised one is called in a different order. Neither can MANUFACTURE a
firing: `analyze`'s derived gate still decides dormancy, so an enabled rule
whose gate is closed stays skipped, and no controller can make a rule act on
reads it does not have. See `Loop._tick_order`.

## What this does not settle

* **The hash is provisional.** `rule_hash` hashes a rule's SOURCE (with a
  fallback to its qualified name). Two rules with identical source therefore
  share a hash -- they are, behaviourally, the same rule, which is the
  intended reading, but a factory returning same-source closures over
  different values would collide, and it is named here rather than hit later.
  The intended identity, once rules are IR data (`docs/plan-reflection.md`),
  is a hash of the IR datum plus the component schema and operator version --
  a per-rule projection of `loopingrules_forge.m2.Frozen.version`.
* **One `RuleControl` per hash is the contract.** Several are tolerated (the
  last in `each()` order wins, which is deterministic but not meaningful); a
  rule that wants to both disable and reprioritise should write one.
* **Runtime self-modification is deliberately absent.** A controller may
  select among the rules already registered; it may not add, remove or
  rewrite one. That is program synthesis, not control, and it belongs behind
  the forge's gates and a freeze (locked decision 8). See the self-reference
  hazard in `docs/plan-reflection.md`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect

from . import analyze


_HASH_CACHE: "dict" = {}


def rule_name(fn) -> str:
    """`r0.bump` -- the name `Loop.rule` registers `fn` under, so reflection
    can match a `RuleCard` against a `Remembered.rule` in the change log."""
    module = getattr(fn, "__module__", "") or ""
    return "%s.%s" % (module.rsplit(".", 1)[-1], getattr(fn, "__name__", "rule"))


def rule_hash(fn) -> str:
    """A content hash of `fn`'s own source -- its identity, independent of
    where it was registered. Falls back to the qualified name when no source
    is available (an interactive definition, a compiled module). See the
    module note: this is provisional, and the IR datum is the target.

    Memoised BY FUNCTION OBJECT, the same way `analyze.analyze` is and for the
    same reason: a replay harness registers the same rule thousands of times,
    and `inspect.getsource` is not cheap. The hash depends only on `fn`'s own
    source, so caching it is safe.
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


@dataclasses.dataclass(frozen=True)
class RuleControl:
    """The loop's scheduling input, keyed by a rule's `hash`.

    `enabled=False` skips the matching rule for the rest of the run;
    `priority` overrides the rule's own `Loop.rule(priority=...)` while the
    control stands. A rule with no `RuleControl` runs exactly as it always
    did, so this is opt-in and changes nothing until a controller writes one.
    """

    hash: str
    enabled: bool = True
    priority: int = 0


@dataclasses.dataclass(frozen=True)
class RuleCard:
    """A rule's declared structure, reified as world data.

    `name` is what the loop registered it as and what `Remembered.rule`
    records; `reads`/`writes` are component class NAMES (sorted), so a rule
    reasons over another rule's vocabulary without importing it; `hash` is
    `RuleControl`'s key. `opaque` is True when `analyze` refused the rule --
    the same "unknown, never silently empty" discipline `analyze` itself
    applies, and the card is still deposited so the rule is at least visible.
    """

    hash: str
    name: str
    reads: tuple = ()
    writes: tuple = ()
    destroys: bool = False
    opaque: bool = False
    priority: int = 0


def card_for(fn) -> RuleCard:
    """The `RuleCard` for one rule, derived by `analyze` (never hand-declared,
    so a card cannot drift from the rule it describes)."""
    try:
        analysis = analyze.analyze(fn)
    except analyze.Opaque:
        return RuleCard(rule_hash(fn), rule_name(fn), (), (),
                        False, True, getattr(fn, "_loopingrules_priority", 0))
    return RuleCard(
        rule_hash(fn), rule_name(fn),
        tuple(sorted(k.__name__ for k in analysis.reads)),
        tuple(sorted(k.__name__ for k in analysis.writes)),
        analysis.destroys, False, getattr(fn, "_loopingrules_priority", 0))


def reify(loop) -> list:
    """Deposit one `RuleCard` per rule registered on `loop`, keyed by hash.

    Idempotent: a hash already carrying a card is left alone, so calling this
    once per install, or again after a restore, does not duplicate. Call it
    after every rule the domain wants visible is registered (including
    `memory`'s, if that is installed) and before the loop runs -- a card
    spawned mid-run is a change like any other, and the loop settles around
    it, but there is no reason to pay that tick. Returns `[(entity, card)]`.
    """
    world = loop.world
    seen = {card.hash for _entity, card in world.each(RuleCard)}
    placed = []
    for _name, fn in loop.rules:
        card = card_for(fn)
        if card.hash in seen:
            continue
        seen.add(card.hash)
        placed.append((world.spawn(card), card))
    return placed
