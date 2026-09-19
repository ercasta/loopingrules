# Core concepts

## Entity

An entity is an identity with no data: `#7`. It is a small handle
(`world.Entity`) holding an integer id and the world it belongs to. Handles
compare and hash by id. Ids count up from `1` and are never reused within a
world's lifetime.

You make one with `world.spawn(*components)`. There is no other way.

## Component

A component is data with no identity: `Size(bytes=4300)`. It is any instance
of a `@dataclasses.dataclass`. That is the only requirement `attach` checks.

What a field may hold, enforced by `attach`:

| Allowed | Notes |
|---|---|
| `None`, `bool`, `int`, `float`, `str` | primitives |
| `list`, `tuple`, `dict` of the above | dict keys must be `str` |
| another entity | lowered to its plain `int` id on the way in |

Anything else raises `TypeError` naming the field. A live `Entity` handle is
never stored: `Entry(folder, "a.txt")` is accepted and stored as
`Entry(folder=1, name="a.txt")`. A relationship is an int id. That keeps
every component something `json.dumps` could write down, which is what makes
[saving](persistence.md) simple.

!!! warning "Never mutate a component in place"
    `revision` (see below) does not move when you edit a component's field, so
    the loop can declare the world settled while it is not. Attach a fresh
    component instead, and prefer `frozen=True` so Python stops you.

### Tags

A component with no fields (`Stale()`, `Big()`) is a **tag**: a claim some rule
made about an entity. Removing the tag with `detach` unmakes the claim. This
is the idiom for state. A rename waiting for approval is the same entity as
one about to happen, plus one component:

```python
w.each(RenameWish, NeedsApproval)             # ask about these
w.each(RenameWish, without=NeedsApproval)     # do these
```

## An entity carries a *list* of each type

`attach(e, X(...))` appends to what `e` already carries of `X`'s type. Equal
values are deduplicated, so re-attaching the same value is a no-op. Different
values of one type coexist.

| Method | Meaning |
|---|---|
| `attach(e, *cs)` | add (deduplicated) |
| `replace(e, *cs)` | clear every component of that type on `e`, then add. Use for kinds meant to be singular |
| `detach(e, *kinds)` | remove **every** component of those types |
| `remove(e, c)` | remove one component equal to `c`, leave the rest of that type |
| `get(e, Kind)` | `None` if none, the value if exactly one, `ValueError` if several |
| `get_all(e, Kind)` | every one, in attach order |

`get` refuses to guess between several. A query written for "the" value of a
naturally singular kind fails loudly the moment two coexist.

## Queries

```python
w.each(A, B)                    # [(entity, a, b), ...] oldest entity first
w.each(A, without=B)            # entities with A and without B
w.first(A)                      # first row of each(), or None
w.the(Clock)                    # the one component of a singleton kind
w.all(A)                        # [(entity, a)] for every instance anywhere
w.has(e, A, B)                  # bool
w.populated(A, B)               # does ANY entity carry any of these? cheap
w.components(e)                 # everything on one entity
w.entities()                    # every entity, in spawn order
```

`each` returns a materialised list, so a rule can spawn and destroy while it
walks the result. It walks the rarest component's bucket and checks the rest,
so a query costs about as much as its most specific term.

If an entity carries several components of an intersecting kind, `each`
yields one row per combination (a cross product).

## Revision: how the loop knows anything happened

`world.revision` is an integer bumped by every `spawn`, `destroy`, and any
`attach`/`replace`/`detach`/`remove` that **actually changed something**. The
loop compares it before and after each rule. That is the *entire* mechanism
for deciding whether a rule "fired", and so whether the world has settled.

This is why idempotence matters. A rule that recomputes the same answer every
tick and re-attaches an equal value does not move `revision`, so the world can
settle.

If you keep an index by hand and mutate it in place, call `world.changed()`
so the loop notices.

## Rule

A rule is a function of one argument, the `World`. It queries, then writes
directly through the six write methods (`spawn`, `attach`, `replace`,
`detach`, `remove`, `destroy`). Nothing stands between the write and the next
rule seeing it. Rules never call each other. The only channel between them is
what they deposit in the world.

## Settled

The loop calls every rule once (a **tick**) and repeats until a whole tick
changes nothing. That state is *settled*, and it is when the world has
something to say. `Loop.run()` returns `Settled(ticks, hot)`. `hot` is empty
on a clean settle, and names the rules still firing if the tick `budget`
(default 200) ran out first.

## Transient components

`@transient` marks a component class as disposable. It behaves normally,
but `save.dump()` skips it and `world.purge_transient()` drops all of it.
Use it for intermediate findings and scratch entities that mean nothing
across a restart.

```python
from loopingrules.world import transient

@transient
@dataclasses.dataclass(frozen=True)
class Scratch:
    n: int
```
