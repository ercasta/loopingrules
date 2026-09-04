"""`parts` -- a small prototype, not a domain: does a GENERIC tag,
attached alongside every SPECIFIC part-edge, let a generic walker stay
generic (never enumerating specific edge kinds, so a new one costs it
nothing) while staying analyzable by `loopingrules.analyze` (which
needs a literal component type at each call site, not a Python-level
list of them)?

## Where this came from

`pystrider.symbolic._parent_of`/`_reachable` walk `set(intake.PARTS.
values())` -- `PARTS`, a Python-level dict from edge-label to specific
component class (`Target`, `Iterated`, `Body`, `Left`, `Right`, ...).
`PRINCIPLES.md` names this exact pair as the model for "a generic walker
over a shared vocabulary" (`denotation.py`'s own `Step` reuses the same
`PARTS` rather than inventing a second one). It is also, structurally,
the one thing in that whole codebase `loopingrules.analyze` cannot see
into: `for cls in set(PARTS.values()): w.each(cls)` has no literal
`Name` at the call site for a static reader to point at -- `PARTS` is
metadata CONSULTED at call time, never data DEPOSITED in the world.

The fix tried here: keep every specific edge exactly as it is, and
ALSO attach one generic component, `Part(entity, label)`, through the
SAME call that mints the specific one -- `intake.py`'s own conclusion
re-entering the substrate as ordinary data, the same thing `PRINCIPLES.
md` already asks of every other derived fact. A generic reader then
walks `Part` alone, ONE literal type, sound by construction to
`loopingrules.analyze` the same way any of `examples.cards`'s rules
already are; a reader that needs to know WHICH kind of edge it found
still reads the specific component, unchanged.

## The one discipline this needs to actually be safe

If `Part` were attached by hand at every edge-producing call site, the
day someone adds a new edge kind and forgets the second `attach()` is
the day a generic walker silently stops seeing it -- a new, structural
version of the exact "watches too narrow, and nothing catches it" gap
`PRINCIPLES.md` already names elsewhere. `part_edge()`, below, is the
one choke point: every specific edge in this module is minted through
it, so there is no call site left that could omit the generic half.

## What this does and does not fix

`parent_of`/`reachable` (this module's restatement of `_parent_of`/
`_reachable`) analyze cleanly -- proven in `tests/test_examples_parts.
py`, including a regression that adds a BRAND NEW edge kind (`Otherwise`)
after both walkers are already written, and confirms neither needed a
single line changed to see it. `enclosing` (this module's restatement of
`_enclosing`) does NOT analyze cleanly, and it is worth being honest
about why: it is parameterized by WHICH ancestor kind to stop at
(`kind: type`, a plain parameter, not a literal at its own definition
site), the same "kind held in a variable" pattern the read-out of
`pystrider` already surfaced for `symbolic.known_value` and others --
`Part` fixes the TRAVERSAL half of `_enclosing`'s job, not the
STOPPING-CONDITION half, which is a separate, sibling instance of the
same already-named family, not something this prototype's fix reaches.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient


@dataclass(frozen=True)
class Part:
    """The generic part-of edge: `entity` is the child, `label` names
    WHICH specific relation this is (`"left"`, `"body"`, ...) -- carried
    so a generic reader can explain itself, not just enumerate results,
    the same "named reason, not an opaque fact" discipline
    `DECISION_PATTERNS.md` already asks of `ruled_out`. Never read for
    its `label` by `parent_of`/`reachable` below -- they only care THAT
    an edge exists, not what it is called."""
    entity: int
    label: str


@transient
@dataclass(frozen=True)
class Left:
    entity: int


@transient
@dataclass(frozen=True)
class Right:
    entity: int


@transient
@dataclass(frozen=True)
class Body:
    entity: int


@transient
@dataclass(frozen=True)
class Readable:
    pass


@transient
@dataclass(frozen=True)
class Add:
    pass


@transient
@dataclass(frozen=True)
class Block:
    pass


@transient
@dataclass(frozen=True)
class BothOperandsReadable:
    pass


def part_edge(w, parent, child, kind: type, label: str) -> None:
    """The one choke point every specific part-edge goes through --
    mints `kind(child)` (specific) and `Part(child, label)` (generic) in
    the same call, so a generic reader can never see less than a
    specific one already does. See the module docstring."""
    w.attach(parent, kind(child))
    w.attach(parent, Part(child, label))


def parent_of(w, child: int):
    """The one entity holding a `Part` edge to `child` -- generic over
    WHICHEVER specific kind that edge is. Reads exactly one component
    type, regardless of how many specific edge kinds exist -- the
    restatement of `pystrider.symbolic._parent_of`."""
    for parent, part in w.each(Part):
        if part.entity == child:
            return parent.id
    return None


def reachable(w, root: int):
    """Every entity reachable downward from `root` through ANY part
    edge -- generic, over `Part` alone, a plain forward walk, no
    caching (the same ethos `_reachable`'s own docstring states). The
    restatement of `pystrider.symbolic._reachable`."""
    seen = {root}
    frontier = [root]
    while frontier:
        node = frontier.pop()
        for entity, part in w.each(Part):
            if entity.id == node and part.entity not in seen:
                seen.add(part.entity)
                frontier.append(part.entity)
    return seen


def enclosing(w, entity: int, kind: type):
    """The nearest ANCESTOR of `entity` that carries `kind` -- the WALK
    is generic (`parent_of`, above); the STOPPING CONDITION is specific
    (`kind`, a parameter, not a literal). See the module docstring's
    closing paragraph for why this one is NOT analyzable the way
    `parent_of`/`reachable` are, even though it is built entirely out of
    them."""
    node = parent_of(w, entity)
    seen = set()
    while node is not None and node not in seen:
        if w.has(node, kind):
            return node
        seen.add(node)
        node = parent_of(w, node)
    return None


def both_operands_readable(w) -> None:
    """The HANDOFF: a rule that keys on the SPECIFIC edges (`Left`/
    `Right`), not `Part` -- it needs to know WHICH operand is which, not
    just that something is reachable, so it reads the specific
    component the same way `examples.cards`'s own rules always have.
    Nothing above this rule (`parent_of`/`reachable`) ever mentions
    `Add`/`Left`/`Right`/`Readable` at all; nothing here walks
    generically. Each stays exactly as legible on its own as if the
    other did not exist."""
    for entity, _add in w.each(Add):
        left, right = w.get(entity, Left), w.get(entity, Right)
        if left is None or right is None:
            continue
        if w.has(left.entity, Readable) and w.has(right.entity, Readable):
            w.attach(entity, BothOperandsReadable())
