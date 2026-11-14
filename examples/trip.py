"""`trip` -- plan a multi-modal journey (train, taxi, subway) as a
forward-only expansion of ordinary rules, not a shortest-path algorithm.

## Under the attribute substrate (D8)

A `Stop` is a `stop` entity carrying `name`; a `Leg` is a `leg` entity
carrying `mode`/`origin`(ref)/`destination`(ref)/`depart`/`duration`/`fare`; a
`TripRequest` is a `trip_request` entity; a `Frontier` is a `frontier` entity
whose `path` is a flat list of leg ids. `expanded`/`complete` are flags.
Refs (`origin`, `destination`, `request`, `stop`, `path`) are declared in
`World.refs` so `share` remaps them.

## `dedupe_stops` is a function, not a rule -- on purpose

`share.load_pack` has no idea that "Downtown"/"downtown"/" DOWNTOWN " denote
the same place; reconciling them is this DOMAIN's call, a one-shot cleanup
over static reference data, written as a plain function.

## The winner is read back through a bridge, not recomputed in place

`nominate_itinerary` projects each `Complete` `Frontier`'s own score onto
`examples.decide`'s oblivious `occasion`/`score` (negated, since this domain
minimizes), and `decide.pick_winner` attaches `winner` back.
"""

from __future__ import annotations

from examples import decide
from loopingrules import share
from loopingrules.world import World


# The declared ref attribute names, so `share` remaps them. (The frontier's
# stop reference is `at`, not `stop` -- `stop` is the Stop tag flag.)
REFS = {"origin", "destination", "request", "at", "path"}


def _spawn(w, tag, **attributes):
    entity = w.spawn()
    w.mark(entity, tag)
    for name, value in attributes.items():
        w.set(entity, name, value)
    return entity


# -- setup: reconciling independently-authored data, once ---------------

def dedupe_stops(w) -> int:
    """Unify every `stop` sharing a normalized name onto the first one seen,
    rewriting every leg/trip_request/frontier ref that pointed at a
    duplicate. Returns how many duplicates were removed."""
    canonical: "dict[str, int]" = {}
    removed = 0
    for entity, _tag, name in sorted(w.each("stop", "name"),
                                     key=lambda row: row[0].id):
        key = name.strip().lower()
        if key not in canonical:
            canonical[key] = entity.id
            continue
        _redirect_stop(w, entity.id, canonical[key])
        w.destroy(entity)
        removed += 1
    return removed


def _redirect_stop(w, old_id: int, new_id: int) -> None:
    for entity, _tag, origin, destination in w.each("leg", "origin",
                                                    "destination"):
        if origin == old_id:
            w.set(entity, "origin", new_id)
        if destination == old_id:
            w.set(entity, "destination", new_id)
    for entity, _tag, origin, destination in w.each("trip_request", "origin",
                                                    "destination"):
        if origin == old_id:
            w.set(entity, "origin", new_id)
        if destination == old_id:
            w.set(entity, "destination", new_id)
    for entity, _tag, stop in w.each("frontier", "at"):
        if stop == old_id:
            w.set(entity, "at", new_id)


def plan_trip(w, request) -> "object":
    """Seed the one `frontier` every plan starts from: at the request's own
    origin, at its start time, having spent nothing over zero legs."""
    q = request.id if hasattr(request, "id") else int(request)
    origin = w.get(q, "origin")
    start = w.get(q, "start_time")
    return _spawn(w, "frontier", request=q, at=origin, time=start,
                  cost=0.0, hops=0, path=[])


# -- the two forward-only rules -----------------------------------------

def _dominated(w, request, stop, cost, time) -> bool:
    """Whether an existing `frontier`, for the same request and stop, is
    already at least as good on BOTH cost and time."""
    for _entity, _tag, req, st, c, t in w.each("frontier", "request", "at",
                                               "cost", "time"):
        if req != request or st != stop:
            continue
        if c <= cost and t <= time:
            return True
    return False


def expand_frontier(w) -> None:
    """For every not-yet-`expanded` frontier, try every `leg` out of its own
    stop -- feasible only if a scheduled `depart` has not passed and the cost
    stays within budget -- and spawn the extension unless dominated. Marks
    itself `expanded` regardless."""
    for row in w.each("frontier", "request", "at", "time", "cost", "hops",
                      "path", without="expanded"):
        entity, _tag, request, stop, time, cost, hops, path = row
        w.mark(entity, "expanded")
        req = w.entity(request)
        if not w.has(req, "max_hops"):
            continue
        if hops >= w.get(req, "max_hops"):
            continue
        budget = w.get(req, "budget")
        for leg_row in w.each("leg", "origin", "destination", "depart",
                              "duration", "fare"):
            leg_entity, _ltag, origin, destination, depart, duration, fare = leg_row
            if origin != stop:
                continue
            leave = time if depart < 0 else depart
            if leave < time:
                continue                      # already left
            new_cost = cost + fare
            if new_cost > budget:
                continue
            if not _dominated(w, request, destination, new_cost,
                              leave + duration):
                _spawn(w, "frontier", request=request, at=destination,
                       time=leave + duration, cost=new_cost, hops=hops + 1,
                       path=list(path) + [leg_entity.id])


def mark_complete(w) -> None:
    """Tag every frontier that has reached its own request's destination."""
    for entity, _tag, request, at in w.each("frontier", "request", "at",
                                            without="complete"):
        req = w.entity(request)
        if w.has(req, "destination") and at == w.get(req, "destination"):
            w.mark(entity, "complete")


def _score(w, front) -> float:
    """`weight_cost * cost + weight_time * elapsed` -- this domain's ONE
    score, shared with `nominate_itinerary`."""
    req = w.entity(w.get(front, "request"))
    elapsed = w.get(front, "time") - w.get(req, "start_time")
    return (w.get(req, "weight_cost") * w.get(front, "cost")
            + w.get(req, "weight_time") * elapsed)


def nominate_itinerary(w) -> None:
    """The bridge's outbound half: project every `complete` frontier's own
    score onto `decide`'s oblivious `occasion`/`score`, negated (this domain
    minimizes; `decide` maximizes). Idempotent for free (`set`'s own dedup)."""
    for entity, _tag, _complete in w.each("frontier", "complete"):
        w.set(entity, "occasion", w.get(entity, "request"))
        w.set(entity, "score", -_score(w, entity))


def install(loop) -> None:
    """Register every rule, including the bridge's two halves."""
    loop.rule(expand_frontier)
    loop.rule(mark_complete)
    loop.rule(nominate_itinerary)
    loop.rule(decide.pick_winner)


# -- reading the answer -------------------------------------------------

def best_itinerary(w, request):
    """The `complete` frontier for this request that `decide.pick_winner`
    crowned `winner`. Returns `(frontier, [leg, ...])`, legs in travel order,
    or `None` if nothing reached the destination, OR if the best score tied
    and `pick_winner` refused to guess."""
    q = request.id if hasattr(request, "id") else int(request)
    for entity, _tag, _complete, _winner in w.each("frontier", "complete",
                                                   "winner"):
        if w.get(entity, "request") != q:
            continue
        legs = [w.entity(leg_id) for leg_id in w.get(entity, "path")]
        return entity, legs
    return None


# -- a worked, multi-source network -------------------------------------

def _stop(w, name):
    return _spawn(w, "stop", name=name)


def _leg(w, mode, origin, destination, depart, duration, fare):
    return _spawn(w, "leg", mode=mode, origin=origin, destination=destination,
                  depart=depart, duration=duration, fare=fare)


def _train_network():
    w = World()
    w.refs = set(REFS)
    downtown = _stop(w, "Downtown")
    airport = _stop(w, "Airport")
    lakeside = _stop(w, "Lakeside")
    _leg(w, "train", airport, downtown, 540, 30, 8.0)
    _leg(w, "train", downtown, lakeside, 620, 25, 6.0)
    return w, [downtown, airport, lakeside]


def _taxi_network():
    w = World()
    w.refs = set(REFS)
    downtown = _stop(w, "downtown")
    airport = _stop(w, "airport")
    lakeside = _stop(w, "lakeside")
    _leg(w, "taxi", airport, downtown, -1, 15, 30.0)
    _leg(w, "taxi", downtown, lakeside, -1, 12, 25.0)
    _leg(w, "taxi", airport, lakeside, -1, 20, 45.0)
    return w, [downtown, airport, lakeside]


def _subway_network():
    w = World()
    w.refs = set(REFS)
    downtown = _stop(w, " Downtown ")
    lakeside = _stop(w, "LAKESIDE")
    _leg(w, "subway", downtown, lakeside, -1, 10, 3.0)
    return w, [downtown, lakeside]


def build_demo_world():
    """Three independently-authored networks, packed and merged into one
    traveller's world with `share`, then reconciled with `dedupe_stops`.
    Returns `(world, stops)` -- `stops` keyed by canonical name."""
    world = World()
    world.refs = set(REFS)
    for build in (_train_network, _taxi_network, _subway_network):
        source, entities = build()
        legs = [e for e, _ in source.each("leg")]
        pack = share.dump_pack(source, entities + legs)
        problems, _ = share.load_pack(world, pack)
        assert not problems, problems

    dedupe_stops(world)
    stops = {name.strip().lower(): entity
             for entity, _tag, name in world.each("stop", "name")}
    return world, stops
