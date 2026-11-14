"""`loopingrules_calibration.kit` -- the instrument for examples-driven
parameter search over a running world.

This is the Phase 1 promotion of the research instrument that used to live
in `examples/tuning.py` (see `docs/plan-calibration.md`). It knows nothing
about cards, shopping or trading -- it only knows how to seed a fresh world
from a `Scenario`, write declared `Knob` values into the world, run the loop
while recording which rules fired on which tick (and, optionally, an
observation per tick), and score the settled result.

## Why parameters, and not rules

The substrate stores tunable parameters as ATTRIBUTES the rules read -- a
singleton entity carrying `max_level`, another carrying `max_premium`.
`docs/tuning.md` states the resulting design rule: a tunable rule never
hard-codes its threshold; it reads an attribute. A `Knob` here is exactly
one such attribute NAME, with the range to search. That is the whole tunable
surface: the tuner may move values, never structure.

Under the attribute substrate (`docs/plan-attributes.md`, D8) a `Knob` names
an attribute, not a component class and a field: the value lives on whichever
entity carries that name, and `read_knobs`/`write_knobs` find it by name.

## The trajectory is the observable

`Loop.tick()` already returns the names of the rules that changed something,
and the tick loop, `each()` ordering and budget are all deterministic -- so
replaying one `Scenario` under one set of knob values reproduces the same
firing sequence and the same settled world every time. `Trace.signature`
hashes the firing sequence together with a canonical snapshot of the final
world, so two knob settings that produce the SAME behaviour collapse to one
signature.

Two corrections to what a naive `save.dump` hash would give, both
load-bearing: the snapshot EXCLUDES the knob attributes themselves (their
values are the input, not the behaviour), and it INCLUDES transient names
(which `save.dump` skips, but which are exactly where a rule records what it
concluded).

## What this module does not do

No search smarter than a grid. Nor does it know whether a trajectory is
GOOD: that is a `scorer`, supplied by whoever runs the experiment.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools

from loopingrules.engine import said
from loopingrules.loop import Loop


@dataclasses.dataclass(frozen=True)
class Knob:
    """One tunable attribute a rule reads.

    `name` is the attribute NAME (e.g. `"max_level"`), `low`/`high` the
    inclusive bounds, `steps` how many values to try across them. `integer`
    rounds the grid to whole numbers. The value lives on whichever singleton
    entity carries `name`; `read_knobs`/`write_knobs` find it by name and
    refuse to guess when nothing carries it.

    `scope` declares whether the knob may be moved ONLINE by a runtime
    controller (`docs/plan-adaptation.md`). It defaults to `"offline"`.
    """

    name: str
    low: float
    high: float
    steps: int = 5
    integer: bool = False
    scope: str = "offline"

    def __post_init__(self):
        if self.scope not in ("offline", "runtime"):
            raise ValueError(
                "Knob.scope must be 'offline' or 'runtime', not %r"
                % (self.scope,))

    def values(self) -> tuple:
        """The grid this knob contributes: `steps` values from `low` to
        `high` inclusive, de-duplicated and sorted."""
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
    """One episode to replay: the keyword arguments a domain's `install` is
    called with (e.g. `cash=100`), and the lines said to the settled world,
    in order."""

    kwargs: tuple = ()
    lines: tuple = ()

    def install_kwargs(self) -> dict:
        return dict(self.kwargs)


@dataclasses.dataclass(frozen=True)
class Trace:
    """The result of replaying one `Scenario`."""

    signature: str
    fired: tuple
    ticks: int
    hot: tuple
    replies: tuple
    world: object
    observations: tuple = ()
    changes: tuple = ()


@dataclasses.dataclass(frozen=True)
class Best:
    """`search`'s answer: the knob `values` that scored highest, and the
    `score` they scored. Ties keep the FIRST grid point."""

    values: tuple
    score: float


def _snapshot(world, exclude):
    """A canonical, order-stable view of the world's attributes, EXCLUDING
    the names in `exclude` (the knobs). Uses `repr` of each value, so it is
    deterministic; unlike `save.dump` it keeps transient names."""
    rows = []
    for entity in world.entities():
        carried = tuple(sorted(
            (name, repr(value))
            for name, value in world.attributes(entity).items()
            if name not in exclude))
        rows.append((entity.id, carried))
    return rows


def _signature(world, fired, exclude=frozenset()) -> str:
    material = repr((fired, _snapshot(world, exclude)))
    return hashlib.sha1(material.encode("utf-8")).hexdigest()


def read_knobs(world, knobs) -> tuple:
    """The current value of each knob's attribute, in `knobs` order. `None`
    where nothing carries it -- reading tolerates absence even though
    writing does not."""
    out = []
    for knob in knobs:
        row = world.first(knob.name)
        out.append(None if row is None else world.get(row[0], knob.name))
    return tuple(out)


def write_knobs(world, knobs, values) -> None:
    """Set each knob's attribute to its paired value, on whichever entity
    carries it. Refuses rather than guesses when nothing carries it: a tuner
    that silently skipped a missing knob would search a surface that is not
    the one the rules read. Raises `ValueError` naming the attribute."""
    if len(knobs) != len(values):
        raise ValueError("%d knobs but %d values" % (len(knobs), len(values)))
    for knob, value in zip(knobs, values):
        row = world.first(knob.name)
        if row is None:
            raise ValueError(
                "no entity carries %r -- cannot set %s"
                % (knob.name, knob.name))
        world.set(row[0], knob.name, value)


def replay(scenario, install, knobs=(), values=(), budget: int = 200,
           observe=None) -> Trace:
    """Replay `scenario` under `install` with the knob values written in,
    and return the `Trace`. Deterministic: same scenario, install and knob
    values give the same `signature` every time.
    """
    loop = Loop(budget=budget)
    install(loop, **scenario.install_kwargs())
    world = loop.world
    if knobs:
        write_knobs(world, knobs, values)
    for line in scenario.lines:
        said(world, "user", line)
    fired = []
    observations = []
    hot = ()
    for _ in range(budget):
        step = loop.tick()
        if not step:
            break
        fired.append(tuple(step))
        if observe is not None:
            observations.append(observe(loop.tick_count, world))
    else:
        hot = fired[-1] if fired else ()
    replies = tuple(world.get(entity, "text") for entity, _ in world.each("reply"))
    exclude = frozenset(knob.name for knob in knobs)
    return Trace(_signature(world, tuple(fired), exclude), tuple(fired),
                 len(fired), hot, replies, world, tuple(observations),
                 world.changes())


def grid(knobs) -> "itertools.product":
    """Every combination of the knobs' own `values()`, in a deterministic
    order (the last knob varies fastest)."""
    return itertools.product(*(knob.values() for knob in knobs))


def _cache_key(install, scenario, knobs, values, budget):
    return (install, scenario, tuple(knobs), tuple(values), budget)


def replay_cached(cache, install, scenario, knobs, values, budget: int = 200):
    """`replay`, memoised in `cache` by `(install, scenario, knobs, values,
    budget)` -- safe because a replay is deterministic."""
    key = _cache_key(install, scenario, knobs, values, budget)
    trace = cache.get(key)
    if trace is None:
        trace = replay(scenario, install, knobs, values, budget)
        cache[key] = trace
    return trace


def _score(cache, install, scenarios, knobs, values, scorer, budget) -> float:
    return sum(scorer(replay_cached(cache, install, s, knobs, values, budget))
               for s in scenarios)


def search(install, scenarios, knobs, scorer, budget: int = 200,
           cache=None) -> Best:
    """Walk the grid and return the values whose total `scorer(trace)`
    across `scenarios` is highest."""
    if cache is None:
        cache = {}
    best = None
    for values in grid(knobs):
        score = _score(cache, install, scenarios, knobs, values, scorer, budget)
        if best is None or score > best.score:
            best = Best(tuple(values), score)
    return best


# -- a few generic scorers, helpers not a framework -----------------------

def settled():
    """A scorer: 1.0 if the world settled inside the budget, else 0.0."""
    def score(trace):
        return 0.0 if trace.hot else 1.0
    return score


def reply_contains(text):
    """A scorer: 1.0 if any `Reply` on the trace contains `text`."""
    def score(trace):
        return 1.0 if any(text in reply for reply in trace.replies) else 0.0
    return score


def reached(name):
    """A scorer: 1.0 if the settled world carries the attribute `name`
    anywhere."""
    def score(trace):
        return 1.0 if trace.world.populated(name) else 0.0
    return score
