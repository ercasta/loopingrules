"""`tuning` -- the instrument for examples-driven parameter search over a
running world.

This module is deliberate infrastructure, not a domain: it turns "tune the
parameter components the rules read" (see `docs/tuning.md`) into something
you can actually run. It knows nothing about cards, shopping or trading --
it only knows how to seed a fresh world from a `Scenario`, write declared
`Knob` values into the parameter components a domain has already seeded,
run the loop while recording which rules fired on which tick, and score
the settled result.

## Why parameters, and not rules

The substrate stores tunable parameters as COMPONENTS the rules read, not
as literals inside the rules -- `cards.RiskProfile`, `judge.RiskTolerance`.
`docs/tuning.md` states the resulting design rule: a tunable rule never
hard-codes its threshold; it reads a component. A `Knob` here is exactly
one field of one such singleton component, with the range to search. That
is the whole tunable surface: the tuner may move values, never structure
(adding or removing a rule is program synthesis, not tuning).

## The trajectory is the observable

`Loop.tick()` already returns the names of the rules that changed
something, and the tick loop, `each()` ordering and budget are all
deterministic -- so replaying one `Scenario` under one set of knob values
reproduces the same firing sequence and the same settled world every time.
`Replay.fired` is `[(rule, ...) per tick]`; `Replay.signature` hashes that
together with `save.dump`'s own record of the final world, so two knob
settings that produce the SAME behaviour collapse to one signature. That
hash is the behavioural-equivalence class `docs/tuning.md` warns you will
find many of: many settings, one trajectory. Report them; do not treat
them as noise.

## What this module does not do

No search smarter than a grid (`search` walks the cross product). The
objective is piecewise-constant in the knobs -- a threshold crossing flips
a tag and switches branches -- so gradients are meaningless and a grid is
an honest, optimizer-free baseline for a small surface. Nor does it know
whether a trajectory is GOOD: that is a `scorer`, supplied by whoever runs
the experiment, and it belongs outside this module the same way a tool or
a channel does. Nothing here runs inside the engine.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools

from loopingrules import save
from loopingrules.engine import Reply, Said
from loopingrules.loop import Loop


@dataclasses.dataclass(frozen=True)
class Knob:
    """One tunable field of one singleton component a rule reads.

    `component` is the dataclass type (e.g. `cards.RiskProfile`), `field`
    the attribute to vary, `low`/`high` the inclusive bounds, `steps` how
    many values to try across them. `integer` rounds the grid to whole
    numbers, for a field like `max_spend_per_trade`. Refuses to guess a
    value the component cannot hold -- see `write_knobs`.
    """

    component: object
    field: str
    low: float
    high: float
    steps: int = 5
    integer: bool = False

    @property
    def name(self) -> str:
        return "%s.%s" % (self.component.__name__, self.field)

    def values(self) -> tuple:
        """The grid this knob contributes: `steps` values from `low` to
        `high` inclusive, de-duplicated and sorted (so a range too small
        to hold `steps` distinct integers yields fewer)."""
        if self.steps <= 1:
            raw = [self.low]
        else:
            step = (self.high - self.low) / (self.steps - 1)
            raw = [self.low + i * step for i in range(self.steps)]
        if self.integer:
            return tuple(sorted({int(round(v)) for v in raw}))
        return tuple(sorted({round(v, 6) for v in raw}))


@dataclasses.dataclass(frozen=True)
class Scenario:
    """One episode to replay: the keyword arguments a domain's `install`
    is called with (e.g. `cash=100`), and the lines said to the settled
    world, in order. Frozen and hashable so a list of scenarios can be
    written down literally."""

    kwargs: tuple = ()
    lines: tuple = ()

    def install_kwargs(self) -> dict:
        return dict(self.kwargs)


@dataclasses.dataclass(frozen=True)
class Replay:
    """The result of replaying one `Scenario`: the per-tick firing
    sequence, how many ticks it took, whether it was still firing when the
    budget ran out (`hot`, a tuple of the last tick's rules, or empty),
    every `Reply` text produced, the settled world itself, and the
    `signature` that collapses identical behaviour together."""

    signature: str
    fired: tuple
    ticks: int
    hot: tuple
    replies: tuple
    world: object


@dataclasses.dataclass(frozen=True)
class Best:
    """`search`'s answer: the knob `values` that scored highest, and the
    `score` they scored. Ties keep the FIRST grid point, so the answer is
    deterministic."""

    values: tuple
    score: float


def _signature(world, fired) -> str:
    material = repr((fired, save.dump(world)))
    return hashlib.sha1(material.encode("utf-8")).hexdigest()


def read_knobs(world, knobs) -> tuple:
    """The current value of each knob's field, in `knobs` order.
    `None` where the component is absent -- reading tolerates absence even
    though writing does not, so a caller can inspect before it seeds."""
    out = []
    for knob in knobs:
        component = world.the(knob.component)
        out.append(None if component is None else getattr(component, knob.field))
    return tuple(out)


def write_knobs(world, knobs, values) -> None:
    """Set each knob's field to its paired value, by `replace`-ing the
    singleton component it lives on. The knob and value lists are parallel
    and must be the same length.

    Refuses rather than guesses when the component is not seeded: a tuner
    that silently skipped a missing knob would search a surface that is
    not the one the rules read, and report a score for a value that was
    never applied. Raises `ValueError` naming the component and field.
    """
    if len(knobs) != len(values):
        raise ValueError("%d knobs but %d values" % (len(knobs), len(values)))
    for knob, value in zip(knobs, values):
        found = world.first(knob.component)
        if found is None:
            raise ValueError(
                "no %s is seeded -- cannot set %s"
                % (knob.component.__name__, knob.name))
        entity, component = found
        world.replace(entity, dataclasses.replace(component, **{knob.field: value}))


def replay(scenario, install, knobs=(), values=(), budget: int = 200) -> Replay:
    """Replay `scenario` under `install` with the knob values written in,
    and return the `Replay`.

    Spawns every line as a `Said` up front, then ticks the loop by hand --
    instead of calling `Loop.run()` -- so the per-tick firing sequence is
    captured. Deterministic: same scenario, install and knob values give
    the same `signature` every time.
    """
    loop = Loop(budget=budget)
    install(loop, **scenario.install_kwargs())
    world = loop.world
    if knobs:
        write_knobs(world, knobs, values)
    for line in scenario.lines:
        world.spawn(Said("user", line))
    fired = []
    hot = ()
    for _ in range(budget):
        step = loop.tick()
        if not step:
            break
        fired.append(tuple(step))
    else:
        hot = fired[-1] if fired else ()
    replies = tuple(reply.text for _entity, reply in world.each(Reply))
    return Replay(_signature(world, tuple(fired)), tuple(fired), len(fired),
                  hot, replies, world)


def grid(knobs) -> "itertools.product":
    """Every combination of the knobs' own `values()`, in a deterministic
    order (the last knob varies fastest)."""
    return itertools.product(*(knob.values() for knob in knobs))


def search(install, scenarios, knobs, scorer, budget: int = 200) -> Best:
    """Walk the grid and return the values whose total `scorer(replay)`
    across `scenarios` is highest.

    `scorer` takes a `Replay` and returns a float -- higher is better. The
    sum, not the mean, so a scenario set of different sizes is not
    accidentally re-weighted; the caller can normalize if it wants a mean.
    No caching: a grid over a handful of knobs is small, and the point
    here is an honest optimizer-free baseline, not throughput.
    """
    best = None
    for values in grid(knobs):
        score = sum(scorer(replay(s, install, knobs, values, budget))
                    for s in scenarios)
        if best is None or score > best.score:
            best = Best(tuple(values), score)
    return best
