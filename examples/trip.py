"""`trip` -- plan a multi-modal journey (train, taxi, subway) as a
forward-only expansion of ordinary rules, not a shortest-path
algorithm. Kept here, not shipped, the same as `examples.cards`/
`examples.shopping` -- see this repo's `README.md`, "Scope."

## Why heuristics, not Dijkstra

A real shortest-path solver keeps exactly the Pareto-optimal frontier
and proves it never misses a winner. `expand_frontier`, below, is
deliberately weaker: it prunes a candidate only when an EXISTING
frontier entry already dominates it outright (no better on cost, no
better on time), never re-examines a frontier entry once expanded, and
caps how many hops a plan may take. That is enough to find good
itineraries fast over a small network, and it is a genuine trade --
`README.md`'s "no vocabulary above entities and components" test
would call an actual optimizer a different kind of thing than this
package's own rules; this is what "forward-only rules, on purpose,
knowing an optimizer would search better" looks like as code, not a
disclaimer bolted onto one.

## `Leg`, one shape for three unrelated operators

A `Leg` doesn't know if it is a train, a taxi, or a subway ride --
`mode` is a label, nothing branches on it. A train's `depart` is a
real timetable slot; a taxi or a subway run is modeled as always
available (`depart=-1`, "leaves now, whenever `now` turns out to be"),
which is a simplification named here rather than hidden: a real subway
has headways, not zero wait, and this treats every on-demand mode as
if the average wait were already folded into `duration`.

## `dedupe_stops` is a function, not a rule -- on purpose

Three independently-authored networks name their own stops -- a train
timetable's "Downtown", a taxi service's "downtown", a subway map's
" DOWNTOWN " -- and `share.load_pack` has no idea, and no business
having an idea, that these denote the same place; see this package's
own `share.py`, "no merge/identity hook." Reconciling them is this
DOMAIN's call, and it is a one-shot cleanup over STATIC reference data,
not a standing concern: nothing here ever mints a new `Stop` once the
network is loaded, so there is nothing for a perpetual rule to keep
watching. Written as a plain function, called once after merging the
packs, the same way `save.py`/`share.py` operations are plain
functions rather than rules -- see the conversation this module came
out of, and `README.md`'s "a domain that wants that pattern writes its
own components and its own generic reader over them."

## What this does not attempt

No return legs, no timetables beyond one operating day (a `depart`
before midnight the previous day, or after this one, is not
represented), no fare rules that vary by demand or time of day, and no
actual Pareto-frontier maintenance -- a frontier entry that is later
made obsolete by a better one is only ever pruned going forward
(future candidates check against it), never retroactively removed.
"""

from __future__ import annotations

import dataclasses

from loopingrules import share
from loopingrules.world import Entity, World


@dataclasses.dataclass(frozen=True)
class Stop:
    """A named place -- a station, an address, a neighborhood. Identity
    is the `name`, not the entity id: two `Stop`s with the same
    (normalized) name denote the same place, reconciled by
    `dedupe_stops`, below."""

    name: str


@dataclasses.dataclass(frozen=True)
class Leg:
    """One way to get from `origin` to `destination` -- `mode` is a
    label a rule may report but never branches on. `depart=-1` means
    "on demand": always available, `front.time` is used as the
    departure instant, see `expand_frontier`."""

    mode: str
    origin: int = share.ref(default=0)
    destination: int = share.ref(default=0)
    depart: int = -1           # minutes after midnight, or -1 = on demand
    duration: int = 0          # minutes
    fare: float = 0.0


@dataclasses.dataclass(frozen=True)
class TripRequest:
    """One traveler's question: get from `origin` to `destination`, no
    earlier than `start_time`, spending no more than `budget`, in at
    most `max_hops` legs -- scored by `weight_cost`/`weight_time`, a
    heuristic trade rather than a normalized utility (see
    `best_itinerary`)."""

    origin: int = share.ref(default=0)
    destination: int = share.ref(default=0)
    start_time: int = 0
    budget: float = 0.0
    max_hops: int = 3
    weight_cost: float = 0.5
    weight_time: float = 0.5


@dataclasses.dataclass(frozen=True)
class Frontier:
    """One partial (or, once `Complete`, whole) itinerary: sitting at
    `stop`, at `time`, having spent `cost` over `hops` legs, `path` the
    `Leg` entity ids taken to get here, in order."""

    request: int = share.ref(default=0)
    stop: int = share.ref(default=0)
    time: int = 0
    cost: float = 0.0
    hops: int = 0
    path: tuple = share.ref(default=())


@dataclasses.dataclass(frozen=True)
class Expanded:
    """This `Frontier` has already tried every `Leg` out of its own
    stop -- `expand_frontier`'s own "don't fire twice" guard, the
    consuming idiom `README.md`'s History already prefers over
    testing a conclusion's absence, restated for a tag that is never
    detached rather than a component that is destroyed."""


@dataclasses.dataclass(frozen=True)
class Complete:
    """This `Frontier` has reached its own request's destination."""


# -- setup: reconciling independently-authored data, once ---------------

def dedupe_stops(w) -> int:
    """Unify every `Stop` sharing a normalized name (stripped, cased
    down) onto the first one seen, rewriting every `Leg`/`TripRequest`/
    `Frontier` field that pointed at a duplicate -- see the module
    docstring for why this is a function, run once after merging packs,
    not a `Loop.rule`. Returns how many duplicates were removed.
    """
    canonical: "dict[str, int]" = {}
    removed = 0
    for entity, stop in sorted(w.each(Stop), key=lambda pair: pair[0].id):
        key = stop.name.strip().lower()
        if key not in canonical:
            canonical[key] = entity.id
            continue
        _redirect_stop(w, entity.id, canonical[key])
        w.destroy(entity)
        removed += 1
    return removed


def _redirect_stop(w, old_id: int, new_id: int) -> None:
    for entity, leg in w.each(Leg):
        changed = {}
        if leg.origin == old_id:
            changed["origin"] = new_id
        if leg.destination == old_id:
            changed["destination"] = new_id
        if changed:
            w.replace(entity, dataclasses.replace(leg, **changed))
    for entity, request in w.each(TripRequest):
        changed = {}
        if request.origin == old_id:
            changed["origin"] = new_id
        if request.destination == old_id:
            changed["destination"] = new_id
        if changed:
            w.replace(entity, dataclasses.replace(request, **changed))
    for entity, front in w.each(Frontier):
        if front.stop == old_id:
            w.replace(entity, dataclasses.replace(front, stop=new_id))


def plan_trip(w, request: "Entity") -> "Entity":
    """Seed the one `Frontier` every plan starts from: sitting at the
    request's own origin, at its own start time, having spent nothing
    over zero legs. Call once per `TripRequest`, before `loop.run()`."""
    req = w.get(request, TripRequest)
    return w.spawn(Frontier(request.id, req.origin, req.start_time, 0.0, 0, ()))


# -- the two forward-only rules -------------------------------------------

def _dominated(w, candidate: Frontier) -> bool:
    """Whether an existing `Frontier`, for the same request and at the
    same stop, is already at least as good on BOTH cost and time --
    the one pruning rule this module applies. Not a Pareto frontier:
    an existing entry worse than `candidate` is never removed, only a
    future candidate is ever compared against what is here already."""
    for _, front in w.each(Frontier):
        if front.request != candidate.request or front.stop != candidate.stop:
            continue
        if front.cost <= candidate.cost and front.time <= candidate.time:
            return True
    return False


def expand_frontier(w) -> None:
    """For every not-yet-`Expanded` `Frontier`, try every `Leg` out of
    its own stop -- feasible only if a scheduled `depart` has not
    already passed and the resulting cost stays within the request's
    `budget` -- and spawn the extension, unless an existing `Frontier`
    already dominates it. Marks itself `Expanded` regardless, even if
    nothing came of it (hop cap reached, no affordable leg): the guard
    is "tried once," not "produced a child."
    """
    for entity, front in w.each(Frontier, without=Expanded):
        request = w.get(w.entity(front.request), TripRequest)
        w.attach(entity, Expanded())
        if request is None or front.hops >= request.max_hops:
            continue
        for leg_entity, leg in w.each(Leg):
            if leg.origin != front.stop:
                continue
            depart = front.time if leg.depart < 0 else leg.depart
            if depart < front.time:
                continue                      # already left
            cost = front.cost + leg.fare
            if cost > request.budget:
                continue
            candidate = Frontier(front.request, leg.destination,
                                 depart + leg.duration, cost,
                                 front.hops + 1, front.path + (leg_entity.id,))
            if not _dominated(w, candidate):
                w.spawn(candidate)


def mark_complete(w) -> None:
    """Tag every `Frontier` that has reached its own request's
    destination -- `best_itinerary` reads this rather than re-deriving
    it, the same "compose a tag nobody wrote the composition of" idiom
    `examples.cards.decide_buy` already uses."""
    for entity, front in w.each(Frontier, without=Complete):
        request = w.get(w.entity(front.request), TripRequest)
        if request is not None and front.stop == request.destination:
            w.attach(entity, Complete())


def install(loop) -> None:
    """Register both rules. Nothing is seeded here -- unlike
    `examples.cards.install`, there is no fixed catalog this domain
    ships; a caller builds its own network (see `build_demo_world`,
    below, for a worked one) and calls `plan_trip` per request."""
    loop.rule(expand_frontier)
    loop.rule(mark_complete)


# -- reading the answer ----------------------------------------------------

def best_itinerary(w, request: "Entity"):
    """The `Complete` `Frontier` for this request minimizing
    `weight_cost * cost + weight_time * elapsed` -- a heuristic trade,
    not a normalized utility: a `weight_cost`/`weight_time` pair only
    means what it says when cost (currency) and elapsed (minutes) are
    read as comparable raw numbers, which they are not, on purpose left
    for whoever calls this to pick weights that make sense for their
    own numbers. Returns `(frontier, [Leg, ...])`, legs in travel
    order, or `None` if nothing reached the destination at all.
    """
    req = w.get(request, TripRequest)
    candidates = [(e, f) for e, f, _ in w.each(Frontier, Complete)
                 if f.request == request.id]
    if not candidates:
        return None

    def score(front: Frontier) -> float:
        elapsed = front.time - req.start_time
        return req.weight_cost * front.cost + req.weight_time * elapsed

    _, winner = min(candidates, key=lambda pair: score(pair[1]))
    legs = [w.get(w.entity(leg_id), Leg) for leg_id in winner.path]
    return winner, legs


# -- a worked, multi-source network, to run this against -------------------

def _train_network():
    w = World()
    downtown = w.spawn(Stop("Downtown"))
    airport = w.spawn(Stop("Airport"))
    lakeside = w.spawn(Stop("Lakeside"))
    w.spawn(Leg("train", airport.id, downtown.id, 540, 30, 8.0))
    w.spawn(Leg("train", downtown.id, lakeside.id, 620, 25, 6.0))
    return w, [downtown, airport, lakeside]


def _taxi_network():
    w = World()
    downtown = w.spawn(Stop("downtown"))
    airport = w.spawn(Stop("airport"))
    lakeside = w.spawn(Stop("lakeside"))
    w.spawn(Leg("taxi", airport.id, downtown.id, -1, 15, 30.0))
    w.spawn(Leg("taxi", downtown.id, lakeside.id, -1, 12, 25.0))
    w.spawn(Leg("taxi", airport.id, lakeside.id, -1, 20, 45.0))
    return w, [downtown, airport, lakeside]


def _subway_network():
    w = World()
    downtown = w.spawn(Stop(" Downtown "))
    lakeside = w.spawn(Stop("LAKESIDE"))
    w.spawn(Leg("subway", downtown.id, lakeside.id, -1, 10, 3.0))
    return w, [downtown, lakeside]


def build_demo_world():
    """Three independently-authored networks (a train operator, a taxi
    service, a subway line -- each its own `World`, its own `Stop`
    spellings), packed with `share.dump_pack` and merged into one
    traveler's `World` with `share.load_pack`, then reconciled with
    `dedupe_stops`. Returns `(world, stops)` -- `stops` a `{name:
    Entity}` map keyed by the CANONICAL (lower, stripped) name, for a
    caller that wants to build a `TripRequest` without knowing which
    source first minted the `Stop` it ended up with.
    """
    registry = {share._name_of(Stop): Stop, share._name_of(Leg): Leg}
    world = World()
    for build in (_train_network, _taxi_network, _subway_network):
        source, entities = build()
        legs = [e for e, _ in source.each(Leg)]
        pack = share.dump_pack(source, entities + legs)
        problems, _ = share.load_pack(world, pack, registry)
        assert not problems, problems

    dedupe_stops(world)
    stops = {stop.name.strip().lower(): entity
            for entity, stop in world.each(Stop)}
    return world, stops
