"""`examples.trip`: three independently-authored networks merged through
`share`, reconciled by `dedupe_stops`, and planned over with two forward-only
rules -- checked against numbers worked out by hand."""

from __future__ import annotations

from examples import trip
from loopingrules import Loop


def a_demo_loop():
    world, stops = trip.build_demo_world()
    loop = Loop(world=world)
    trip.install(loop)
    return loop, stops


def request_and_plan(loop, stops, weight_cost, weight_time,
                     budget=100.0, max_hops=3, start_time=530):
    w = loop.world
    request = w.spawn()
    w.mark(request, "trip_request")
    w.set(request, "origin", stops["airport"].id)
    w.set(request, "destination", stops["lakeside"].id)
    w.set(request, "start_time", start_time)
    w.set(request, "budget", budget)
    w.set(request, "max_hops", max_hops)
    w.set(request, "weight_cost", weight_cost)
    w.set(request, "weight_time", weight_time)
    trip.plan_trip(w, request)
    loop.run()
    return trip.best_itinerary(w, request)


# --- merging three sources into one ------------------------------------

def test_the_three_networks_arrive_as_one_stop_per_place():
    _, stops = a_demo_loop()
    assert set(stops) == {"downtown", "airport", "lakeside"}


def test_no_leg_is_left_pointing_at_a_destroyed_duplicate_stop():
    loop, stops = a_demo_loop()
    live_ids = {e.id for e in stops.values()}
    for _e, _tag, origin, destination in loop.world.each("leg", "origin",
                                                         "destination"):
        assert origin in live_ids and destination in live_ids


# --- the actual planning -----------------------------------------------

def test_the_winning_frontier_carries_the_bridges_own_attributes():
    loop, stops = a_demo_loop()
    front, _legs = request_and_plan(loop, stops, weight_cost=0.9,
                                    weight_time=0.1)
    w = loop.world
    winner = next(e for e, _tag, _w in w.each("frontier", "winner")
                  if w.get(e, "request") == w.get(front, "request"))
    assert w.get(winner, "occasion") == w.get(front, "request")
    assert w.get(winner, "score") == -_expected_score(w, front)


def _expected_score(w, front):
    return 0.9 * w.get(front, "cost") + 0.1 * (w.get(front, "time") - 530)


def test_a_cost_preferring_traveler_takes_the_cheaper_slower_route():
    loop, stops = a_demo_loop()
    w = loop.world
    front, legs = request_and_plan(loop, stops, weight_cost=0.9,
                                   weight_time=0.1)
    assert w.get(front, "cost") == 11.0 and w.get(front, "time") == 580
    assert [w.get(leg, "mode") for leg in legs] == ["train", "subway"]


def test_a_time_preferring_traveler_takes_the_pricier_direct_taxi():
    loop, stops = a_demo_loop()
    w = loop.world
    front, legs = request_and_plan(loop, stops, weight_cost=0.1,
                                   weight_time=0.9)
    assert w.get(front, "cost") == 45.0 and w.get(front, "time") == 550
    assert [w.get(leg, "mode") for leg in legs] == ["taxi"]


def test_a_tight_budget_rules_out_the_otherwise_fastest_option():
    loop, stops = a_demo_loop()
    w = loop.world
    front, legs = request_and_plan(loop, stops, weight_cost=0.1,
                                   weight_time=0.9, budget=40.0)
    assert w.get(front, "cost") == 33.0 and w.get(front, "time") == 555
    assert [w.get(leg, "mode") for leg in legs] == ["taxi", "subway"]


def test_no_completed_itinerary_ever_exceeds_its_own_budget():
    loop, stops = a_demo_loop()
    request_and_plan(loop, stops, weight_cost=0.1, weight_time=0.9,
                     budget=12.0)
    for entity, _tag, _complete in loop.world.each("frontier", "complete"):
        assert loop.world.get(entity, "cost") <= 12.0


def test_a_hop_cap_of_one_permits_only_the_direct_leg():
    loop, stops = a_demo_loop()
    front, legs = request_and_plan(loop, stops, weight_cost=0.9,
                                   weight_time=0.1, max_hops=1)
    assert len(legs) == 1 and loop.world.get(legs[0], "mode") == "taxi"


def test_a_missed_scheduled_departure_is_infeasible_not_ignored():
    loop, stops = a_demo_loop()
    _front, legs = request_and_plan(loop, stops, weight_cost=1.0,
                                    weight_time=0.0, start_time=700)
    assert all(loop.world.get(leg, "mode") != "train" for leg in legs)


def test_no_itinerary_at_all_when_the_budget_cannot_afford_any_leg():
    loop, stops = a_demo_loop()
    result = request_and_plan(loop, stops, weight_cost=0.5, weight_time=0.5,
                              budget=1.0)
    assert result is None
