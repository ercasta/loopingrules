"""`loopingrules_calibration.kit` -- the instrument for examples-driven
parameter search over a running world.

This is the Phase 1 promotion of the research instrument that used to live
in `examples/tuning.py` (see `docs/plan-calibration.md`). It knows nothing
about cards, shopping or trading -- it only knows how to seed a fresh world
from a `Scenario`, write declared `Knob` values into the parameter
components a domain has already seeded, run the loop while recording which
rules fired on which tick (and, optionally, an observation per tick), and
score the settled result.

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
`Trace.fired` is `[(rule, ...) per tick]`; `Trace.signature` hashes that
together with a canonical snapshot of the final world, so two knob settings
that produce the SAME behaviour collapse to one signature. That hash is the
behavioural-equivalence class `docs/tuning.md` warns you will find many of:
many settings, one trajectory. Report them; do not treat them as noise.

Two corrections to what a naive `save.dump` hash would give, both
load-bearing for that claim: the snapshot EXCLUDES the knob components
themselves (their values are the input, not the behaviour -- otherwise every
distinct setting has a distinct signature and no plateau could ever exist),
and it INCLUDES `@transient` tags (which `save.dump` skips, but which are
exactly where a rule records what it concluded -- so the snapshot sees them
and the difference is real).

## What this module does not do

No search smarter than a grid (`search` walks the cross product). The
objective is piecewise-constant in the knobs -- a threshold crossing flips
a tag and switches branches -- so gradients are meaningless and a grid is
an honest, optimizer-free baseline for a small surface. Nor does it know
whether a trajectory is GOOD: that is a `scorer`, supplied by whoever runs
the experiment, and it belongs outside this module the same way a tool or
a channel does. Nothing here runs inside the engine.

`Trace.observations` and `Trace.changes` are both filled now: a per-tick
observation hook (`replay(..., observe=...)`) for checks that read the
blackboard mid-run (`docs/plan-dataset.md`), and the world's own change log
(`docs/plan-memory.md`) for what each rule changed and when. Neither feeds
the signature, which stays `(fired, canonical snapshot)` so plateaus keep
their meaning (two runs that reach the same outcome by different paths are
equivalent); the log is a separate, richer field for a scorer or a check to
read.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools

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

    `scope` declares whether the knob may be moved ONLINE by a runtime
    controller (`docs/plan-adaptation.md`). It defaults to `"offline"` --
    tunable in the lab, frozen at deploy -- so the runtime-tunable set is a
    small, auditable one an author opts into. Phase 1 records the
    declaration but nothing consumes `"runtime"` yet; it exists so the
    surface is stable when the controller arrives.
    """

    component: object
    field: str
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
    written down literally -- and so a replay can be cached by it."""

    kwargs: tuple = ()
    lines: tuple = ()

    def install_kwargs(self) -> dict:
        return dict(self.kwargs)


@dataclasses.dataclass(frozen=True)
class Trace:
    """The result of replaying one `Scenario`: the per-tick firing
    sequence, how many ticks it took, whether it was still firing when the
    budget ran out (`hot`, a tuple of the last tick's rules, or empty),
    every `Reply` text produced, the settled world itself, and the
    `signature` that collapses identical behaviour together.

    `observations` holds one value per FIRING tick, in order, when a caller
    passes `replay(..., observe=...)` -- the seam `docs/plan-dataset.md`
    uses for checks that read the blackboard mid-run. `changes` is the
    world's change log for this replay (`docs/plan-memory.md`): what each
    rule changed, on which tick -- the full history, where `signature`
    keeps only the settled outcome. Both default empty, so a call site
    need not know about them to use a `Trace`.
    """

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
    `score` they scored. Ties keep the FIRST grid point, so the answer is
    deterministic."""

    values: tuple
    score: float


def _snapshot(world, exclude):
    """A canonical, order-stable view of the world's components, EXCLUDING
    the types in `exclude` (the knob components). Uses `repr` of each
    frozen component, so it is deterministic; unlike `save.dump` it keeps
    `@transient` tags, because those are where a rule records what it
    concluded and a behavioural hash must see them."""
    rows = []
    for entity in world.entities():
        carried = tuple(sorted(
            repr(component) for component in world.components(entity)
            if type(component) not in exclude))
        rows.append((entity.id, carried))
    return rows


def _signature(world, fired, exclude=frozenset()) -> str:
    material = repr((fired, _snapshot(world, exclude)))
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


def replay(scenario, install, knobs=(), values=(), budget: int = 200,
           observe=None) -> Trace:
    """Replay `scenario` under `install` with the knob values written in,
    and return the `Trace`.

    Spawns every line as a `Said` up front, then ticks the loop by hand --
    instead of calling `Loop.run()` -- so the per-tick firing sequence is
    captured. Deterministic: same scenario, install and knob values give
    the same `signature` every time.

    `observe(tick, world)`, if given, is called after every tick that
    changed something, and its return value is appended to
    `Trace.observations` in order. It must READ the world, not write it:
    the observation is a measurement of the trajectory, and a measurement
    that moves what it measures is not one (`docs/plan-dataset.md`).
    """
    loop = Loop(budget=budget)
    install(loop, **scenario.install_kwargs())
    world = loop.world
    if knobs:
        write_knobs(world, knobs, values)
    for line in scenario.lines:
        world.spawn(Said("user", line))
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
    replies = tuple(reply.text for _entity, reply in world.each(Reply))
    exclude = frozenset(knob.component for knob in knobs)
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
    budget)` -- safe because a replay is deterministic. `cache` is a plain
    dict a caller may share across grid points, folds or a whole
    calibration; pass the same one and repeated work is done once.

    The returned `Trace` is SHARED, so a scorer must not mutate
    `trace.world`: a scorer is a measurement, and a measurement that
    changes what it measures corrupts every later read of the same cache
    entry.
    """
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
    across `scenarios` is highest.

    `scorer` takes a `Trace` and returns a float -- higher is better. The
    sum, not the mean, so a scenario set of different sizes is not
    accidentally re-weighted; the caller can normalize if it wants a mean.
    Replays are cached (`replay_cached`), so a caller passing the same
    `cache` across calls pays for each `(scenario, values)` once.
    """
    if cache is None:
        cache = {}
    best = None
    for values in grid(knobs):
        score = _score(cache, install, scenarios, knobs, values, scorer, budget)
        if best is None or score > best.score:
            best = Best(tuple(values), score)
    return best


# -- a few generic scorers, helpers not a framework -----------------------
#
# Domain scoring belongs in the author's own code; these are the terms that
# are true of any domain, and compose in ordinary Python (sum, weights).

def settled():
    """A scorer: 1.0 if the world settled inside the budget, else 0.0.
    Penalising `hot` runs is `docs/tuning.md`'s own advice."""
    def score(trace):
        return 0.0 if trace.hot else 1.0
    return score


def reply_contains(text):
    """A scorer: 1.0 if any `Reply` on the trace contains `text`."""
    def score(trace):
        return 1.0 if any(text in reply for reply in trace.replies) else 0.0
    return score


def reached(component):
    """A scorer: 1.0 if the settled world carries `component` anywhere."""
    def score(trace):
        return 1.0 if trace.world.populated(component) else 0.0
    return score
