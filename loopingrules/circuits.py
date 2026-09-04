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
learning is built yet -- see `README.md`'s own History for what this
module does and does not settle.

## Promoted from `examples/`, ahead of this repo's own usual bar

This lived in `examples/circuits.py` -- a prototype, not shipped, per
`TODO.md`'s own standing line ("stays a prototype until something real
needs it") -- through eight commits of restating real rules against it.
Every OTHER promotion this repo has made (`Proposal`, `arbitrate`,
`census`) waited for a second, independently-motivated domain to
actually depend on the thing at runtime; nothing does that here yet --
`pystrider` was read from and validated against, repeatedly, never
wired to import or install any of this. Promoted anyway, deliberately,
not by forgetting the bar: the cross-repo evidence accumulated instead
(`loopingrules.analyze` agreement on every spec, byte-identical
behavior against real rules from two independently-authored domains,
across twelve restated rules total -- seven of `examples.cards`'s own
thirteen, five of `pystrider.patterns`/`constraints`'s entire real
vocabulary) was judged sufficient on its own terms, without waiting for
a specific consumer to show up first. See
`README.md`'s own History for the entry this promotion landed in, and
`TODO.md` for what is still open.

## The shapes, closed

Reads, all missing-safe (a `Self`/`Via`/`World` whose target does not
exist evaluates to `MISSING`, not an exception):

- `Self(component, field)` -- a field of the entity being iterated.
- `Via(base, fk_field, component, field)` -- follow `base.fk_field` (an
  entity id living on the entity being iterated) to another entity, and
  read `component.field` there.
- `World(component, field)` -- a field of a world SINGLETON (`w.the`).
- `TheEntity(component)` -- `World`'s sibling: the SINGLETON'S OWN id,
  for an effect that needs to name an entity to act on, not read a
  value off it.
- `Const(value)` -- a literal.

Arithmetic and combination, `MISSING`-propagating unless noted:
`Add`/`Sub`/`Mul`, `Min`/`Max` (n-ary), `SafeDiv(numerator, denominator,
if_nonpositive)` -- divides, or evaluates `if_nonpositive` instead when
the denominator is not positive, rather than raising; this is the one
shape added FOR `tag_risk_level` specifically, because "a fraction of
remaining capacity, defined even when there is none left" is a recurring
enough idiom in a resource-flavored rule to earn a named primitive
rather than a general `If`. `Coalesce(expr, default)` -- `default` when
`expr` is `MISSING`, the one shape that does NOT propagate it. `If
(condition, then, else_)` IS the general one, added once a second rule
(`hear_want`, defaulting an omitted quantity to `1`) needed a default
that depends on WHICH CASE holds, not on whether a read came back
`MISSING` -- still a VALUE, not a spec author's `if` (see "No loop, no
`if`," below, for why that distinction is real).

Comparison, boundary where `MISSING` becomes an ordinary `False` rather
than propagating further (a condition can always be evaluated, even
about a fact that does not exist yet -- the same discipline `tag_wanted`
already applies by hand for a card nobody has asked for):
`Le`/`Lt`/`Ge`/`Gt`/`Eq`, and `And`/`Or`/`Not` (`And`/`Or` n-ary, over
already-resolved booleans).

`Exists(at, component)` -- whether the entity named by `at` (an
expression giving an id) carries `component` at all; `HasSelf(
component)` -- the same question about self, with no `at` to compute.
Neither reads a field, and neither ever yields `MISSING`.

Strings and lookup, added for `hear_list`'s own parsing -- a different
primitive AXIS than everything above: not arithmetic over already-
structured data, but turning raw TEXT into structured data at all.
`Lower(expr)`, `Split(expr)` (the one place a value here is a LIST, not
a scalar), `At(expr, index)`/`Len(expr)` (the only two things that ever
read a list back out, `index` a literal int -- `MISSING`, not an
`IndexError`, out of range), `ParseInt(expr)` (`MISSING`, not a
`ValueError`). `FindBy(component, field, value)` is a different KIND of
"reach a related entity" than `Via`: `Via` follows an id a field already
stores; `FindBy` scans for the entity whose field EQUALS a computed
value, the reverse lookup `examples.cards._find_card` already does by
hand.

`Any(over)`/`Forall(over, condition)`/`Count(over, condition)` -- three
quantifiers over `over` (a GLOBAL join -- a type or several, the same
shape `w.each(*over)` takes -- or a `Children(base, fk_field, component)`
SCOPE: self's own `base.fk_field` names a parent, and every `component`
there contributes its own `.entity`, the one-to-many hop `Via` cannot
reach). `Any` is `False` on an empty match set; `Forall` is vacuously
`True` on one (combined with `And` wherever a rule needs "at least one
exists, and all of them satisfy...", `examples.cards.check_goal`'s own
shape); `Count` is a definite integer, `0` on one (`pystrider.patterns.
loop_count`'s own shape: how many of a `Function`'s `Stmt`s are
`ForStmt`s).

`Format(template, exprs)` -- `template % tuple(evaluated exprs)`, the one
non-arithmetic leaf, needed for `tag_risk_level`'s human-readable
`reason` field; `MISSING`-propagating like arithmetic.

`Join(over, expr, sep, sort_by=None)` -- every entity matching `over`,
`expr`-ed (with THAT entity as self) and joined with `sep`, sorted by
`sort_by` first if given; an entity whose own `expr`/`sort_by` is
`MISSING` is DROPPED, not fatal to the whole join. `examples.cards.
hear_status`'s own `sorted(w.each(CardDef, Wants), key=...)` restated as
data -- the one place this catalog produces a variable-length, ordered
piece of TEXT from an unbounded set, where `Any`/`Forall`/`Count` only
ever reduce one to a boolean or a number. `Optional(condition, expr)` --
`expr` if `condition`, else a segment that does not exist at all (not
`If`'s question -- there is no `else_`, just "include this, or don't").
`JoinStrings(sep, exprs)` is `Join`'s fixed-arity sibling: a handful of
KNOWN pieces to assemble (`hear_status`'s "cash: ...", the wanted-cards
report or "no goal set", optionally "goal met"), dropping any that
evaluate `MISSING` (an `Optional` that didn't apply) rather than joining
an empty string in their place.

## The three rule shapes

`TagCircuit(for_each, condition, tag)` compiles to: for each entity of
`for_each`, attach `tag()` if `condition` evaluates true, else detach
it -- both directions, every tick, the same discipline `tag_affordable`
&co. already hand-write. `ValueCircuit(for_each, into, fields, condition=
None, monotonic=False)` compiles to: `replace(entity, into(*evaluated
fields))` -- skipped (not guessed at) for one tick if any field
evaluates `MISSING`, or, if `monotonic=True`, an implicit `without=into`
guard and `attach` instead of `replace` (derive AT MOST ONCE, matching
`pystrider.patterns`' idiom rather than `examples.cards`'s). `Action
Circuit(require, without, condition=None, effects)` picks the single
FIRST entity matching `require`/`without` (never several), checks
`condition` against it if given, and -- read phase, then write phase,
never interleaved -- applies `ReplaceAt`/`Destroy`/`Spawn` effects in
order.

## "Don't fire twice" is two different idioms, not one

`ValueCircuit.monotonic`'s `without=into` guards a STANDING property of
PERSISTENT data (a `Function`, a `CardDef`) that must never be
re-derived once settled -- the data itself is never consumed, only the
CONCLUSION about it is guarded, by testing its own absence.
`ActionCircuit`'s `Destroy` effect is the other idiom: consuming the
MATCHED entity itself, the same way `Said`/`Proposal` are claimed and
destroyed the instant a rule acts on them, so there is structurally
nothing left to match a second time -- no self-reference to an output
needed at all. The two are not interchangeable: `examples.cards.
check_goal`'s own `Wants` set must never be destroyed (`hear_status`
still reads it), so its "don't fire twice" needs a SEPARATE, seeded,
one-shot marker entity to consume instead of consuming the data the
question is about -- see `tests/test_circuits.py`'s own
`check_goal_spec` and `GoalCheck`. A third idiom -- `WorldCircuit`, no
per-entity match at all, "don't fire twice" as a self-referential
condition -- was tried first, for exactly this rule, and removed: it
turned out to be a narrower special case of what `ActionCircuit` with a
seeded marker and a `condition` already covers, so keeping both would
have been two ways to say the same thing. See README History, "don't
fire twice is consuming a component, not testing an absence."

## No loop, no `if`, by construction

Iteration is `for_each`/`require`'s own single `w.each()` walk, not a
body a spec author writes; branching a RULE does (attach-vs-detach,
which `ActionCircuit` fires) is a `condition`'s own boolean value, not a
spec author's `if`. `If` itself does not contradict this: it picks
between two already-evaluated VALUES, the same way `SafeDiv` already
silently does for one specific case -- there is no way to reach a
different EFFECT, a different `for_each`, or a different RULE through
it, only a different number or string inside one field. Nothing here is
Turing complete on purpose -- there is no recursion, no way to reference
another entity's kind not already named in `Via`, and no way to loop a
variable number of times (`Join`'s own iteration is `w.each()`'s, fixed
in shape, not a spec author's loop either). That is not a missing
feature; it is the whole point, per the module's own opening paragraph.

## Reads and writes come from the spec's own shape, not analysis

Because a spec is plain data, `reads(spec)`/`writes(spec)` do not need
`loopingrules.analyze`'s AST walk at all -- they just walk the
dataclass tree and collect every `component`/`base` a `Self`/`Via`/
`World` names, and the `tag`/`into` component the shape writes. Sound
BY CONSTRUCTION, not merely checked after the fact -- see
`tests/test_circuits.py`'s own cross-check against
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
class TheEntity:
    """The id of the world's own singleton entity carrying `component`
    (`w.first`) -- `MISSING` if none. `World`'s own sibling: `World`
    reads a FIELD off the singleton; this reaches the singleton's id
    itself, for an effect that needs to name WHICH entity to act on
    (`ReplaceAt`, most often) rather than read a value from it."""
    component: type


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


@dataclasses.dataclass(frozen=True)
class If:
    """`then` if `condition` else `else_` -- a VALUE, not a spec
    author's `if`: still ordinary data, evaluated by the interpreter,
    the same way `SafeDiv`'s "use this instead when the denominator
    isn't positive" already is a named special case of exactly this
    shape. Only the CHOSEN branch is evaluated -- the other's `MISSING`,
    or anything else about it, never counts. Added for `examples.cards.
    hear_want`'s own "default the quantity to 1 when it was omitted,
    otherwise parse what was typed" -- a default that depends on WHICH
    case holds, not on whether a read came back `MISSING` (`Coalesce`'s
    own, narrower question)."""
    condition: object
    then: object
    else_: object


# -- strings and lookup -- added for hear_list's own parsing -------------
#
# A different primitive AXIS than everything above: not arithmetic over
# already-structured data, but the process of turning raw text INTO
# structured data at all. `Split` is the one place a value flowing
# through this algebra is a LIST rather than a scalar -- `At`/`Len` are
# the only two things that ever read one back out. `FindBy` is a
# different kind of "reach a related entity" than `Via`: `Via` follows
# an ID a field already stores; `FindBy` scans for the entity whose
# field EQUALS a computed value, the reverse-lookup `examples.cards.
# _find_card` already does by hand.

@dataclasses.dataclass(frozen=True)
class Lower:
    expr: object


@dataclasses.dataclass(frozen=True)
class Split:
    expr: object


@dataclasses.dataclass(frozen=True)
class At:
    """`expr[index]` -- `index` a literal int, not itself an expression
    (the same reasoning `Via`'s `fk_field` being a plain string is:
    WHICH field/position to read is part of the shape, not data the
    shape computes). `MISSING`, not an `IndexError`, out of range."""
    expr: object
    index: int


@dataclasses.dataclass(frozen=True)
class Len:
    expr: object


@dataclasses.dataclass(frozen=True)
class ParseInt:
    """`int(expr)`, or `MISSING` -- the same refuse-rather-than-guess
    discipline `examples.cards._parse_int` already spells out by hand,
    restated as a primitive instead of a helper function."""
    expr: object


@dataclasses.dataclass(frozen=True)
class FindBy:
    """The id of the (first) entity whose `component.field` equals
    `value` (an expression) -- `MISSING` if none. Case-sensitive, unlike
    `examples.cards._find_card`, which lowers both sides -- a named
    simplification: lower `value` yourself (`Lower(...)`) and rely on
    the catalog's own names already being stored lowercase, true of
    every `DEFAULT_CATALOG` entry today, rather than have this primitive
    guess which field deserves case-folding on the STORED side too."""
    component: type
    field: str
    value: object


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
class HasSelf:
    """Whether the entity CURRENTLY being evaluated (self) carries
    `component` at all -- `Exists`'s own sibling, for when the id to ask
    about is not reached by any expression at all, it just IS self
    (`pystrider.patterns.loop_count`'s "is this statement a `ForStmt`"
    check, asked of each of a `Function`'s own `Stmt`s in turn -- see
    `Count`, below, for how `self` gets to mean one of those rather than
    the `Function` a `loop_count`-shaped circuit iterates). `False` if
    there is no self in scope (`entity=None`) -- never `MISSING`, the
    same existence-not-a-read posture `Exists` already has."""
    component: type


@dataclasses.dataclass(frozen=True)
class And:
    exprs: tuple


@dataclasses.dataclass(frozen=True)
class Or:
    exprs: tuple


@dataclasses.dataclass(frozen=True)
class Not:
    expr: object


@dataclasses.dataclass(frozen=True)
class Any:
    """Whether at least one entity carries ALL of `over` (a type, or a
    tuple of them -- the same join `w.each(*over)` already takes) --
    boolean, and an EMPTY match set makes this `False`. The complement
    of `Forall`, below, which is vacuously `True` on an empty set --
    the two are combined with `And` wherever a rule needs "at least one
    exists, AND all of them satisfy..." (`examples.cards.check_goal`'s
    own shape: no goal is ever "met" if none was stated)."""
    over: object


@dataclasses.dataclass(frozen=True)
class Forall:
    """Whether EVERY entity carrying all of `over` satisfies `condition`
    -- `condition` is evaluated with THAT entity as "self," never
    whatever entity `Forall` itself is being evaluated for. Vacuously
    `True` on an empty match set, the classical convention; see `Any`'s
    own docstring for why a rule that also cares whether the set is
    non-empty checks both."""
    over: object
    condition: object


@dataclasses.dataclass(frozen=True)
class Children:
    """A SCOPED alternative to `Any`/`Forall`/`Count`'s plain `over`: the
    entities reached by following self's own `base.fk_field` to a
    parent, then reading every `component` THERE (`get_all`, plural --
    the one-to-many case `Via` cannot reach, because `Via` reads a
    single field off a single related entity) and quantifying over each
    one's own `.entity`. `pystrider.patterns.loop_count`'s own shape:
    a `Function`'s `Body` names ONE entity, but that entity carries MANY
    `Stmt`s, and it is those `Stmt`s -- not the `Body` itself -- that
    `loop_count` asks a question about, one at a time."""
    base: type
    fk_field: str
    component: type


@dataclasses.dataclass(frozen=True)
class Count:
    """How many entities matching `over` (a type/tuple -- a global join,
    like `Any`/`Forall` -- or a `Children` scope) satisfy `condition`,
    evaluated with each match as self. Always a definite integer, `0` on
    an empty match set. `Any`/`Forall` are not rewritten in terms of
    this -- neither ever needed a NUMBER, only a boolean, and keeping
    them separate keeps each one's own docstring about what it actually
    answers."""
    over: object
    condition: object


@dataclasses.dataclass(frozen=True)
class Format:
    template: str
    exprs: tuple


@dataclasses.dataclass(frozen=True)
class Join:
    """Join every entity matching `over` (a global join, or a `Children`
    scope) into ONE string: `expr` (evaluated with each matching entity
    as self, NOT whatever entity `Join` itself is being evaluated for --
    the same rebinding `Forall`/`Count` already do) gives each entity's
    own text, `sep` joins them, and `sort_by` (also evaluated per
    entity, optional) orders them first. `examples.cards.hear_status`'s
    own `sorted(w.each(CardDef, Wants), key=lambda row: row[1].name)`
    restated as data -- the one place this catalog produces a variable-
    length, ordered piece of text from an unbounded set, rather than a
    number or a boolean. An entity whose own `expr`/`sort_by` evaluates
    `MISSING` is DROPPED, not `MISSING` for the whole join -- one broken
    line missing from a report is more useful than no report at all."""
    over: object
    expr: object
    sep: str
    sort_by: object = None


@dataclasses.dataclass(frozen=True)
class Optional:
    """`expr` if `condition`, else a segment that does not exist at all
    -- only meaningful inside `JoinStrings`, where a dropped segment is
    OMITTED, not joined as an empty string in its place. Not the same
    question `If` answers (`If` always has an `else_`); this is "include
    this piece, or don't," which is what an optional trailing "goal met"
    needs, not a substitute value for when it is absent."""
    condition: object
    expr: object


@dataclasses.dataclass(frozen=True)
class JoinStrings:
    """`sep.join(evaluated exprs)`, dropping any that evaluate `MISSING`
    entirely -- `Join`'s fixed-arity sibling: a handful of KNOWN pieces
    to assemble (`examples.cards.hear_status`'s "cash: ...", the wanted-
    cards report or "no goal set", optionally "goal met"), not a
    dynamic collection to iterate."""
    sep: str
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
class ReplaceAt:
    """Replace `component` on the entity named by `at` (an expression,
    evaluated once, in the same read phase every other effect's fields
    are) with a freshly computed value. `at` is usually `Self(base,
    fk_field)` (the RELATED entity a stored id names -- `decide_buy`'s
    own `Copies` update, on the card a `Listing` names) or `TheEntity
    (component)` (the world's own singleton -- `decide_buy`'s `Purse`
    update) or `FindBy(...)` (a dynamically LOOKED-UP entity -- `hear_
    want`'s own `Wants` update, on whichever card was typed by name).
    One effect covers what used to be two (`ReplaceVia`/`ReplaceWorld`,
    removed): both were this shape with a specific `at` expression
    already baked in, and neither could reach a `FindBy`-found entity
    at all -- caught while `hear_want` needed exactly that and neither
    old effect could express it. See README History, "one Replace
    effect, not three.\""""
    at: object
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
    qualify, never several at once. `condition`, if given, is checked
    AFTER the match (evaluated with the matched entity as self, so it
    may use `Any`/`Forall` over an entirely different, world-wide join
    the match itself says nothing about -- `examples.cards.check_goal`'s
    own restatement is exactly this: `require` finds a seeded, one-shot
    marker entity, `condition` asks a question about a completely
    different set, `CardDef`/`Wants`). `None` (the default) means
    "always," the behaviour before `condition` existed.

    `effects`, in order, are the only three things an action may do:
    `ReplaceAt` (write a freshly computed value onto an entity an
    expression names), `Destroy` (the match itself), `Spawn` (a new
    entity). Every effect's
    OWN fields are evaluated against the matched entity BEFORE any
    effect commits -- a read phase, then a write phase, never
    interleaved -- so no effect can see another effect's write from the
    same action, the same "read into locals, then write" shape
    `decide_buy`'s own hand-written body already has. If any field
    evaluates `MISSING`, the WHOLE action is skipped, not applied
    halfway -- refuse rather than guess, same as `ValueCircuit`.

    Only ONE action per tick, on purpose -- see this module's own
    docstring, "No loop, no `if`, and no batching either,"
    for why a rule that could once act on N matches per tick does not
    need to here: the tick loop retrying with freshly recomputed tags is
    what a hand-written loop-and-reread would otherwise have to do by
    hand.

    ## "Don't fire twice" is `Destroy`ing the match, not testing an
    output's absence

    `Destroy()` in `effects` -- consuming the matched entity as PART OF
    acting on it -- is this shape's own answer to "don't fire twice,"
    the same idiom `loopingrules.world.Said`/`Proposal` already use (a
    rule claims and destroys the occasion the moment it acts, so there
    is structurally nothing left to match a second time). This is a
    DIFFERENT idiom from `ValueCircuit.monotonic`'s `without=into` (a
    standing property of PERSISTENT data -- `Function`s, `CardDef`s --
    that keeps existing and must never be re-derived once settled), and
    the two are not interchangeable: a `Wants` set must never be
    destroyed (`hear_status` still needs to read it), so "goal met"
    cannot be guarded by consuming the thing it is a question ABOUT --
    it needs its own, separate, one-shot marker entity to consume
    instead. See History, "the monotonic mode," and the correction that
    replaced this shape's first `check_goal` restatement, for the
    argument in full.
    """
    require: tuple
    without: tuple
    condition: object = None
    effects: tuple = ()


# -- the interpreter -------------------------------------------------------

def _matches(w, over, entity):
    """Every entity id `Any`/`Forall`/`Count` should quantify over --
    either a GLOBAL join (`over` a type or tuple, `w.each(*over)`, self
    plays no part), or a `Children` SCOPE (self's own `base.fk_field`
    names a parent, and every `component` on THAT parent contributes its
    own `.entity`). Plain ids either way -- `w.get`/`w.has` already
    normalize an `Entity` handle or a bare int the same way."""
    if isinstance(over, Children):
        base = None if entity is None else w.get(entity, over.base)
        if base is None:
            return []
        parent = getattr(base, over.fk_field)
        return [component.entity for component in w.get_all(parent, over.component)]
    return [row[0] for row in w.each(*_kinds(over))]


def evaluate(expr, w, entity):
    """One expression, evaluated against one entity -- or against NO
    entity (`entity=None`): `Self`/`Via` return `MISSING` rather than
    raise when asked to read off nothing, which is what lets `Any`/
    `Forall`-rooted conditions (built from no `Self`/`Via` at all) be
    evaluated standalone, with nothing bound as "self." `MISSING`
    elsewhere is where a read's target does not exist -- see the module
    docstring for which shapes propagate it and which resolve it
    (`Coalesce`) or collapse it to an ordinary `False` (every
    comparison)."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, Self):
        comp = None if entity is None else w.get(entity, expr.component)
        return getattr(comp, expr.field) if comp is not None else MISSING
    if isinstance(expr, Via):
        base = None if entity is None else w.get(entity, expr.base)
        if base is None:
            return MISSING
        related = w.get(getattr(base, expr.fk_field), expr.component)
        return getattr(related, expr.field) if related is not None else MISSING
    if isinstance(expr, World):
        comp = w.the(expr.component)
        return getattr(comp, expr.field) if comp is not None else MISSING
    if isinstance(expr, TheEntity):
        found = w.first(expr.component)
        return found[0].id if found is not None else MISSING
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
    if isinstance(expr, If):
        branch = expr.then if evaluate(expr.condition, w, entity) else expr.else_
        return evaluate(branch, w, entity)
    if isinstance(expr, Lower):
        value = evaluate(expr.expr, w, entity)
        return value.lower() if isinstance(value, str) else MISSING
    if isinstance(expr, Split):
        value = evaluate(expr.expr, w, entity)
        return value.split() if isinstance(value, str) else MISSING
    if isinstance(expr, At):
        value = evaluate(expr.expr, w, entity)
        if not isinstance(value, list) or not (0 <= expr.index < len(value)):
            return MISSING
        return value[expr.index]
    if isinstance(expr, Len):
        value = evaluate(expr.expr, w, entity)
        return len(value) if isinstance(value, list) else MISSING
    if isinstance(expr, ParseInt):
        value = evaluate(expr.expr, w, entity)
        if not isinstance(value, str):
            return MISSING
        try:
            return int(value)
        except ValueError:
            return MISSING
    if isinstance(expr, FindBy):
        value = evaluate(expr.value, w, entity)
        if value is MISSING:
            return MISSING
        for candidate, component in w.all(expr.component):
            if getattr(component, expr.field) == value:
                return candidate.id
        return MISSING
    if isinstance(expr, Exists):
        at = evaluate(expr.at, w, entity)
        return at is not MISSING and w.get(at, expr.component) is not None
    if isinstance(expr, HasSelf):
        return entity is not None and w.get(entity, expr.component) is not None
    if isinstance(expr, (Le, Lt, Ge, Gt, Eq)):
        left, right = evaluate(expr.left, w, entity), evaluate(expr.right, w, entity)
        if left is MISSING or right is MISSING:
            return False    # a condition about a fact that isn't there yet is false
        return _COMPARE[type(expr)](left, right)
    if isinstance(expr, And):
        return all(evaluate(e, w, entity) for e in expr.exprs)
    if isinstance(expr, Or):
        return any(evaluate(e, w, entity) for e in expr.exprs)
    if isinstance(expr, Not):
        return not evaluate(expr.expr, w, entity)
    if isinstance(expr, Any):
        return bool(_matches(w, expr.over, entity))
    if isinstance(expr, Forall):
        return all(evaluate(expr.condition, w, m) for m in _matches(w, expr.over, entity))
    if isinstance(expr, Count):
        return sum(1 for m in _matches(w, expr.over, entity)
                   if evaluate(expr.condition, w, m))
    if isinstance(expr, Format):
        values = [evaluate(e, w, entity) for e in expr.exprs]
        if any(v is MISSING for v in values):
            return MISSING
        return expr.template % tuple(values)
    if isinstance(expr, Join):
        rows = []
        for m in _matches(w, expr.over, entity):
            text = evaluate(expr.expr, w, m)
            if text is MISSING:
                continue    # drop just this one entity, not the whole join
            key = evaluate(expr.sort_by, w, m) if expr.sort_by is not None else None
            rows.append((key, text))
        if expr.sort_by is not None:
            rows.sort(key=lambda row: row[0])
        return expr.sep.join(text for _key, text in rows)
    if isinstance(expr, Optional):
        return evaluate(expr.expr, w, entity) if evaluate(expr.condition, w, entity) else MISSING
    if isinstance(expr, JoinStrings):
        values = [evaluate(e, w, entity) for e in expr.exprs]
        return expr.sep.join(v for v in values if v is not MISSING)
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
            if spec.condition is not None and not evaluate(spec.condition, w, entity):
                return
            planned = []    # read phase: every effect's fields (and, for
            for effect in spec.effects:   # ReplaceAt, its own target), pre-write
                if isinstance(effect, Destroy):
                    planned.append((effect, None, None))
                    continue
                target = None
                if isinstance(effect, ReplaceAt):
                    target = evaluate(effect.at, w, entity)
                    if target is MISSING:
                        return    # refuse the WHOLE action, not half of it
                values = [evaluate(f, w, entity) for f in effect.fields]
                if any(v is MISSING for v in values):
                    return    # refuse the WHOLE action, not half of it
                planned.append((effect, target, values))
            for effect, target, values in planned:    # write phase
                if isinstance(effect, ReplaceAt):
                    w.replace(target, effect.component(*values))
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
    `Via`/`World`/`TheEntity` (and `Via`'s own `base`) reached while
    walking its expression tree -- `ReplaceAt`'s own `at` is just
    another expression in that tree, so a `TheEntity(component)` or
    `Self(base, fk_field)` naming its target is already picked up here,
    the same as anywhere else one appears; no separate case is needed
    for it. Structural, not inferred: a node's `component`/`base` field
    IS the read -- there is nothing here to get wrong the way a general
    analyzer could."""
    if isinstance(spec, ActionCircuit):
        kinds: Set[type] = set(spec.require) | set(spec.without)
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
        elif isinstance(node, TheEntity):
            kinds.add(node.component)
        elif isinstance(node, Exists):
            kinds.add(node.component)
        elif isinstance(node, HasSelf):
            kinds.add(node.component)
        elif isinstance(node, Children):
            kinds.update((node.base, node.component))
        elif isinstance(node, FindBy):
            kinds.add(node.component)
        elif isinstance(node, (Any, Forall, Count, Join)):
            if not isinstance(node.over, Children):
                kinds.update(_kinds(node.over))    # a Children scope is its own leaf, above
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
            if isinstance(effect, (ReplaceAt, Spawn))}


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
