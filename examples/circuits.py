"""`circuits` -- a minimal, closed catalog of shapes for the ONE rule
family that already turned out to be data, not control flow: "for each
entity of a kind, compute something from arithmetic over a few fields,
and attach/detach a tag or replace a value" -- `examples.cards.
tag_wanted`/`tag_affordable`/`tag_fair_priced`/`tag_risk_level`, restated
here as plain dataclass specs instead of hand-written Python bodies.

## Why this, and why now

A conversation about this repo's rules asked, in order: should
`loopingrules` ship a vast shared vocabulary (no -- see `examples.judge`'s
own docstring); should it grow a general DSL for rule bodies (no -- see
`loopingrules.analyze`'s own docstring, which got a sound map out of
PLAIN Python instead); would a YAML/JSON syntax be a middle ground (no --
either it's a string-expression language with worse tooling than Python,
or a structural comparison tree that only covers the same narrow shape
this module covers, which `analyze.py` already covered for free). This
module is the answer that survived: not a general escape hatch, but a
DELIBERATELY small, closed set of shapes, motivated by something none of
the earlier options were -- a closed catalog is the thing a FUTURE search
or learning process over rules would need to be tractable at all, the
same reason genetic programming and program synthesis reach for a small
typed combinator set rather than arbitrary source code. No search or
learning is built here -- see the module's own History entry in
`README.md` for what this prototype does and does not settle.

## The shapes, closed

Reads, all missing-safe (a `Self`/`Via`/`World` whose target does not
exist evaluates to `MISSING`, not an exception):

- `Self(component, field)` -- a field of the entity being iterated.
- `Via(base, fk_field, component, field)` -- follow `base.fk_field` (an
  entity id living on the entity being iterated) to another entity, and
  read `component.field` there.
- `World(component, field)` -- a field of a world SINGLETON (`w.the`).
- `Const(value)` -- a literal.

Arithmetic and combination, `MISSING`-propagating unless noted:
`Add`/`Sub`/`Mul`, `Min`/`Max` (n-ary), `SafeDiv(numerator, denominator,
if_nonpositive)` -- divides, or evaluates `if_nonpositive` instead when
the denominator is not positive, rather than raising; this is the one
shape added FOR `tag_risk_level` specifically, because "a fraction of
remaining capacity, defined even when there is none left" is a recurring
enough idiom in a resource-flavored rule to earn a named primitive
rather than a general `If`. `Coalesce(expr, default)` -- `default` when
`expr` is `MISSING`, the one shape that does NOT propagate it.

Comparison, boundary where `MISSING` becomes an ordinary `False` rather
than propagating further (a condition can always be evaluated, even
about a fact that does not exist yet -- the same discipline `tag_wanted`
already applies by hand for a card nobody has asked for):
`Le`/`Lt`/`Ge`/`Gt`/`Eq`, and `And`/`Or` (n-ary, over already-resolved
booleans).

`Format(template, exprs)` -- `template % tuple(evaluated exprs)`, the one
non-arithmetic leaf, needed for `tag_risk_level`'s human-readable
`reason` field; `MISSING`-propagating like arithmetic.

## The two rule shapes

`TagCircuit(for_each, condition, tag)` compiles to: for each entity of
`for_each`, attach `tag()` if `condition` evaluates true, else detach
it -- both directions, every tick, the same discipline `tag_affordable`
&co. already hand-write. `ValueCircuit(for_each, into, fields)` compiles
to: `replace(entity, into(*evaluated fields))` -- skipped (not guessed
at) for one tick if any field evaluates `MISSING`.

## No loop, no `if`, by construction

Iteration is `for_each`'s own single `w.each()` walk, not a body a spec
author writes; branching is `condition`'s own boolean value deciding
attach-vs-detach, not a spec author's `if`. Nothing here is Turing
complete on purpose -- there is no recursion, no way to reference another
entity's kind not already named in `Via`, and no way to loop a variable
number of times. That is not a missing feature; it is the whole point,
per the module's own opening paragraph.

## Reads and writes come from the spec's own shape, not analysis

Because a spec is plain data, `reads(spec)`/`writes(spec)` do not need
`loopingrules.analyze`'s AST walk at all -- they just walk the
dataclass tree and collect every `component`/`base` a `Self`/`Via`/
`World` names, and the `tag`/`into` component the shape writes. Sound
BY CONSTRUCTION, not merely checked after the fact -- see
`tests/test_examples_circuits.py`'s own cross-check against
`loopingrules.analyze.analyze()` run on the hand-written original.
"""

from __future__ import annotations

import dataclasses
from typing import Set


MISSING = object()


# -- reads ---------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Self:
    component: type
    field: str


@dataclasses.dataclass(frozen=True)
class Via:
    base: type
    fk_field: str
    component: type
    field: str


@dataclasses.dataclass(frozen=True)
class World:
    component: type
    field: str


@dataclasses.dataclass(frozen=True)
class Const:
    value: object


# -- arithmetic and combination -------------------------------------------

@dataclasses.dataclass(frozen=True)
class Add:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Sub:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Mul:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Min:
    exprs: tuple


@dataclasses.dataclass(frozen=True)
class Max:
    exprs: tuple


@dataclasses.dataclass(frozen=True)
class SafeDiv:
    numerator: object
    denominator: object
    if_nonpositive: object


@dataclasses.dataclass(frozen=True)
class Coalesce:
    expr: object
    default: object


# -- comparison and boolean combination -----------------------------------

@dataclasses.dataclass(frozen=True)
class Le:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Lt:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Ge:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Gt:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Eq:
    left: object
    right: object


@dataclasses.dataclass(frozen=True)
class Exists:
    """Whether the entity named by `at` (an expression giving an entity
    id, evaluated first) carries `component` AT ALL -- existence, not a
    field read, so this needs no field name and never yields `MISSING`:
    an id that names no such entity, or no such component, is simply
    `False`. Added for `pystrider.patterns.iteration`'s own `Readable`
    checks on three INDEPENDENTLY-named related entities (`target.
    entity`, `iterated.entity`, `body.entity`) -- `Via` reaches ONE hop
    from a NAMED field on a component already on self; this reaches an
    id already computed some other way, most often `Self(SomeComponent,
    "entity")`, to ask a yes/no question about it rather than read a
    value off it."""
    at: object
    component: type


@dataclasses.dataclass(frozen=True)
class And:
    exprs: tuple


@dataclasses.dataclass(frozen=True)
class Or:
    exprs: tuple


@dataclasses.dataclass(frozen=True)
class Format:
    template: str
    exprs: tuple


_ARITH = {Add: lambda a, b: a + b, Sub: lambda a, b: a - b, Mul: lambda a, b: a * b}
_COMPARE = {Le: lambda a, b: a <= b, Lt: lambda a, b: a < b,
            Ge: lambda a, b: a >= b, Gt: lambda a, b: a > b,
            Eq: lambda a, b: a == b}


# -- the two rule shapes ---------------------------------------------------

def _kinds(for_each) -> tuple:
    """`for_each` is one component type or several (a JOIN, the same
    shape `w.each(*kinds)` already takes) -- this is the one place that
    distinction is resolved, so every other reader of `for_each` can
    just iterate it."""
    return for_each if isinstance(for_each, tuple) else (for_each,)


@dataclasses.dataclass(frozen=True)
class TagCircuit:
    for_each: type
    condition: object
    tag: type


@dataclasses.dataclass(frozen=True)
class ValueCircuit:
    """`for_each` -> `into(*fields)`, `replace`d fresh every tick, UNLESS
    `monotonic=True`.

    `condition`, if given, gates whether this entity is derived AT ALL
    this tick -- separate from a field simply evaluating `MISSING`,
    because a condition can be about something OTHER than what the
    fields themselves need (`pystrider.patterns.iteration`'s `Readable`
    checks are not needed to COMPUTE `item`/`sequence`/`does`, only to
    decide whether the derivation is trusted yet). `None` (the default)
    means "always," the original behaviour.

    `monotonic=True` -- the mode `pystrider.patterns`/`constraints`
    actually use, throughout, and `examples.cards` never does: derive
    AT MOST ONCE per entity (an implicit `without=into` on the query),
    then never touch it again, rather than recomputing and `replace`ing
    fresh every tick. The two are genuinely different contracts, not two
    spellings of one idea -- see README History, "the monotonic mode,"
    for why `cards`'s bidirectional rules and `pystrider`'s monotonic
    ones cannot share one flag with a single default.
    """
    for_each: type
    into: type
    fields: tuple
    condition: object = None
    monotonic: bool = False


# -- the third shape: one action, on one match, per tick ------------------

@dataclasses.dataclass(frozen=True)
class ReplaceWorld:
    """Replace the world's own singleton of `component` with a freshly
    computed value -- `examples.cards.decide_buy`'s `Purse` update."""
    component: type
    fields: tuple


@dataclasses.dataclass(frozen=True)
class ReplaceVia:
    """Replace `base.fk_field`'s own `component` (on the RELATED entity,
    reached the same way `Via` reads it) with a freshly computed value --
    `decide_buy`'s `Copies` update, on the card a `Listing` names."""
    base: type
    fk_field: str
    component: type
    fields: tuple


@dataclasses.dataclass(frozen=True)
class Destroy:
    """Destroy the matched entity itself."""


@dataclasses.dataclass(frozen=True)
class Spawn:
    """Spawn a new entity carrying one freshly computed `component`."""
    component: type
    fields: tuple


@dataclasses.dataclass(frozen=True)
class ActionCircuit:
    """The one match this tick gets to act on, and what happens to it.

    `require`/`without` pick exactly one entity the same way `w.first(
    *require, without=without)` already would -- the FIRST if several
    qualify, never several at once. `effects`, in order, are the only
    four things an action may do: `ReplaceWorld`/`ReplaceVia` (write a
    freshly computed value), `Destroy` (the match itself), `Spawn` (a new
    entity). Every effect's OWN fields are evaluated against the matched
    entity BEFORE any effect commits -- a read phase, then a write
    phase, never interleaved -- so no effect can see another effect's
    write from the same action, the same "read into locals, then write"
    shape `decide_buy`'s own hand-written body already has. If any
    field evaluates `MISSING`, the WHOLE action is skipped, not applied
    halfway -- refuse rather than guess, same as `ValueCircuit`.

    Only ONE action per tick, on purpose -- see `examples.circuits`'s
    own module docstring, "No loop, no `if`, and no batching either,"
    for why a rule that could once act on N matches per tick does not
    need to here: the tick loop retrying with freshly recomputed tags is
    what a hand-written loop-and-reread would otherwise have to do by
    hand.
    """
    require: tuple
    without: tuple
    effects: tuple


# -- the interpreter -------------------------------------------------------

def evaluate(expr, w, entity):
    """One expression, evaluated against one entity. `MISSING` where a
    read's target does not exist -- see the module docstring for which
    shapes propagate it and which resolve it (`Coalesce`) or collapse it
    to an ordinary `False` (every comparison)."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, Self):
        comp = w.get(entity, expr.component)
        return getattr(comp, expr.field) if comp is not None else MISSING
    if isinstance(expr, Via):
        base = w.get(entity, expr.base)
        if base is None:
            return MISSING
        related = w.get(getattr(base, expr.fk_field), expr.component)
        return getattr(related, expr.field) if related is not None else MISSING
    if isinstance(expr, World):
        comp = w.the(expr.component)
        return getattr(comp, expr.field) if comp is not None else MISSING
    if isinstance(expr, (Add, Sub, Mul)):
        left, right = evaluate(expr.left, w, entity), evaluate(expr.right, w, entity)
        if left is MISSING or right is MISSING:
            return MISSING
        return _ARITH[type(expr)](left, right)
    if isinstance(expr, (Min, Max)):
        values = [evaluate(e, w, entity) for e in expr.exprs]
        if any(v is MISSING for v in values):
            return MISSING
        return (min if isinstance(expr, Min) else max)(values)
    if isinstance(expr, SafeDiv):
        denom = evaluate(expr.denominator, w, entity)
        if denom is MISSING:
            return MISSING
        if denom <= 0:
            return evaluate(expr.if_nonpositive, w, entity)
        num = evaluate(expr.numerator, w, entity)
        return MISSING if num is MISSING else num / denom
    if isinstance(expr, Coalesce):
        value = evaluate(expr.expr, w, entity)
        return evaluate(expr.default, w, entity) if value is MISSING else value
    if isinstance(expr, Exists):
        at = evaluate(expr.at, w, entity)
        return at is not MISSING and w.get(at, expr.component) is not None
    if isinstance(expr, (Le, Lt, Ge, Gt, Eq)):
        left, right = evaluate(expr.left, w, entity), evaluate(expr.right, w, entity)
        if left is MISSING or right is MISSING:
            return False    # a condition about a fact that isn't there yet is false
        return _COMPARE[type(expr)](left, right)
    if isinstance(expr, And):
        return all(evaluate(e, w, entity) for e in expr.exprs)
    if isinstance(expr, Or):
        return any(evaluate(e, w, entity) for e in expr.exprs)
    if isinstance(expr, Format):
        values = [evaluate(e, w, entity) for e in expr.exprs]
        if any(v is MISSING for v in values):
            return MISSING
        return expr.template % tuple(values)
    raise TypeError("not a circuit expression: %r" % (expr,))


def compile_circuit(spec):
    """A `TagCircuit`/`ValueCircuit` -> a plain function of one `World`,
    installable on `Loop.rule` exactly like any hand-written rule --
    nothing downstream of this needs to know a rule came from a spec
    rather than a `def`."""
    if isinstance(spec, TagCircuit):
        def rule(w):
            for row in w.each(*_kinds(spec.for_each)):
                entity = row[0]
                if evaluate(spec.condition, w, entity):
                    w.attach(entity, spec.tag())
                else:
                    w.detach(entity, spec.tag)
        return rule
    if isinstance(spec, ValueCircuit):
        def rule(w):
            without = (spec.into,) if spec.monotonic else ()
            for row in w.each(*_kinds(spec.for_each), without=without):
                entity = row[0]
                if spec.condition is not None and not evaluate(spec.condition, w, entity):
                    continue
                values = [evaluate(f, w, entity) for f in spec.fields]
                if any(v is MISSING for v in values):
                    continue    # refuse rather than guess -- see the docstring
                if spec.monotonic:
                    w.attach(entity, spec.into(*values))
                else:
                    w.replace(entity, spec.into(*values))
        return rule
    if isinstance(spec, ActionCircuit):
        def rule(w):
            match = w.first(*spec.require, without=spec.without)
            if match is None:
                return
            entity = match[0]
            planned = []    # read phase: every effect's fields, pre-write
            for effect in spec.effects:
                if isinstance(effect, Destroy):
                    planned.append((effect, None))
                    continue
                values = [evaluate(f, w, entity) for f in effect.fields]
                if any(v is MISSING for v in values):
                    return    # refuse the WHOLE action, not half of it
                planned.append((effect, values))
            for effect, values in planned:    # write phase
                if isinstance(effect, ReplaceWorld):
                    target, _ = w.first(effect.component)
                    w.replace(target, effect.component(*values))
                elif isinstance(effect, ReplaceVia):
                    base = w.get(entity, effect.base)
                    w.replace(getattr(base, effect.fk_field), effect.component(*values))
                elif isinstance(effect, Destroy):
                    w.destroy(entity)
                elif isinstance(effect, Spawn):
                    w.spawn(effect.component(*values))
        return rule
    raise TypeError("not a circuit spec: %r" % (spec,))


# -- reads/writes, from the spec's own shape, no analysis needed ----------

def reads(spec) -> Set[type]:
    """Every component type `spec` could read -- `for_each` (or
    `require`/`without`, for an `ActionCircuit`), plus every `Self`/
    `Via`/`World` (and `Via`'s own `base`) reached while walking its
    expression tree, plus, for an `ActionCircuit`, `ReplaceVia`'s own
    `base` and `ReplaceWorld`'s own `component` -- `ReplaceWorld` has to
    read the singleton it targets (`w.first(component)`) before it can
    replace it. Structural, not inferred: a node's `component`/`base`
    field IS the read -- there is nothing here to get wrong the way a
    general analyzer could."""
    if isinstance(spec, ActionCircuit):
        kinds: Set[type] = set(spec.require) | set(spec.without)
        for effect in spec.effects:
            if isinstance(effect, ReplaceWorld):
                kinds.add(effect.component)
            elif isinstance(effect, ReplaceVia):
                kinds.add(effect.base)
    else:
        kinds = set(_kinds(spec.for_each))
        if isinstance(spec, ValueCircuit) and spec.monotonic:
            kinds.add(spec.into)    # the implicit without=into gate is a read too
    for node in _leaves(spec):
        if isinstance(node, Self):
            kinds.add(node.component)
        elif isinstance(node, Via):
            kinds.update((node.base, node.component))
        elif isinstance(node, World):
            kinds.add(node.component)
        elif isinstance(node, Exists):
            kinds.add(node.component)
    return kinds


def writes(spec) -> Set[type]:
    """Every component type `spec` writes. For an `ActionCircuit`,
    `Destroy` is a deliberate, named exception, the same one
    `loopingrules.analyze`'s own docstring names for a bare
    `destroy(entity)`: it destroys the matched entity WHOLE, so nothing
    here claims to know every component type that entity happened to
    carry -- see `destroys()` for the flag that records only that the
    action CAN destroy, not what it destroys."""
    if isinstance(spec, TagCircuit):
        return {spec.tag}
    if isinstance(spec, ValueCircuit):
        return {spec.into}
    return {effect.component for effect in spec.effects
            if isinstance(effect, (ReplaceWorld, ReplaceVia, Spawn))}


def destroys(spec: ActionCircuit) -> bool:
    return any(isinstance(effect, Destroy) for effect in spec.effects)


def _leaves(spec):
    found = []

    def walk(node):
        # `dataclasses.is_dataclass` answers yes for both a dataclass
        # INSTANCE (an expression node, worth recursing into) and the
        # dataclass CLASS itself (a `component`/`base` reference, e.g.
        # `Listing` -- a leaf here, not something with field VALUES to
        # walk) -- the `isinstance(node, type)` guard tells them apart.
        if isinstance(node, type):
            return
        if dataclasses.is_dataclass(node):
            found.append(node)
            for f in dataclasses.fields(node):
                walk(getattr(node, f.name))
        elif isinstance(node, (tuple, list)):
            for item in node:
                walk(item)

    walk(spec)
    return found
