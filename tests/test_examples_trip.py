"""`examples.trip`: three independently-authored networks merged
through `share`, reconciled by `dedupe_stops`, and planned over with
two forward-only rules -- checked against numbers worked out by hand,
not just "a plan came back"."""

from loopingrules import Loop
from examples import decide, trip


def a_demo_loop():
    world, stops = trip.build_demo_world()
    loop = Loop(world=world)
    trip.install(loop)
    return loop, stops


def request_and_plan(loop, stops, weight_cost, weight_time,
                      budget=100.0, max_hops=3, start_time=530):
    w = loop.world
    request = w.spawn(trip.TripRequest(
        stops["airport"].id, stops["lakeside"].id, start_time, budget,
        max_hops, weight_cost, weight_time))
    trip.plan_trip(w, request)
    loop.run()
    return trip.best_itinerary(w, request)


# --- merging three sources into one, without a shared vocabulary -------

def test_the_three_networks_arrive_as_one_stop_per_place():
    _, stops = a_demo_loop()
    # "Downtown", "downtown", " Downtown " (three different spellings,
    # from three different authors) collapsed onto one entity, the same
    # for "Lakeside"/"lakeside"/"LAKESIDE" -- neither `share.load_pack`
    # nor anything in `loopingrules` knows what a "place" is; this is
    # `dedupe_stops`'s own, domain-owned reconciliation.
    assert set(stops) == {"downtown", "airport", "lakeside"}


def test_no_leg_is_left_pointing_at_a_destroyed_duplicate_stop():
    loop, stops = a_demo_loop()
    live_ids = {e.id for e in stops.values()}
    for _, leg in loop.world.each(trip.Leg):
        assert leg.origin in live_ids and leg.destination in live_ids


# --- the actual planning ------------------------------------------------

def test_the_winning_frontier_carries_the_bridges_own_components():
    # best_itinerary no longer recomputes a score -- it reads the answer
    # examples.decide's oblivious pick_winner attached back. This checks
    # the bridge's round trip directly, not just that SOME answer came
    # back: the winning Frontier itself was nominated (Option/Score) and
    # crowned (Winner) by a rule that has never heard of a Frontier.
    loop, stops = a_demo_loop()
    front, _legs = request_and_plan(loop, stops, weight_cost=0.9, weight_time=0.1)
    w = loop.world
    winner = next(e for e, f, _w in w.each(trip.Frontier, decide.Winner)
                 if f.request == front.request)
    assert w.get(winner, decide.Option).occasion == front.request
    assert w.get(winner, decide.Score).value == -_expected_score(front)


def _expected_score(front):
    return 0.9 * front.cost + 0.1 * (front.time - 530)


def test_a_cost_preferring_traveler_takes_the_cheaper_slower_route():
    loop, stops = a_demo_loop()
    front, legs = request_and_plan(loop, stops, weight_cost=0.9, weight_time=0.1)
    assert front.cost == 11.0 and front.time == 580
    assert [leg.mode for leg in legs] == ["train", "subway"]


def test_a_time_preferring_traveler_takes_the_pricier_direct_taxi():
    loop, stops = a_demo_loop()
    front, legs = request_and_plan(loop, stops, weight_cost=0.1, weight_time=0.9)
    assert front.cost == 45.0 and front.time == 550
    assert [leg.mode for leg in legs] == ["taxi"]


def test_a_tight_budget_rules_out_the_otherwise_fastest_option():
    loop, stops = a_demo_loop()
    front, legs = request_and_plan(loop, stops, weight_cost=0.1, weight_time=0.9,
                                    budget=40.0)
    # Same traveler, same preferences, as the direct-taxi test above --
    # only the budget changed, and it is what changes the winner: the
    # $45 direct taxi is now unaffordable, so time-preference falls back
    # to the next-fastest AFFORDABLE plan, not the cheapest overall.
    assert front.cost == 33.0 and front.time == 555
    assert [leg.mode for leg in legs] == ["taxi", "subway"]


def test_no_completed_itinerary_ever_exceeds_its_own_budget():
    loop, stops = a_demo_loop()
    request_and_plan(loop, stops, weight_cost=0.1, weight_time=0.9, budget=12.0)
    for _, front, _ in loop.world.each(trip.Frontier, trip.Complete):
        assert front.cost <= 12.0


def test_a_hop_cap_of_one_permits_only_the_direct_leg():
    loop, stops = a_demo_loop()
    result = request_and_plan(loop, stops, weight_cost=0.9, weight_time=0.1,
                               max_hops=1)
    front, legs = result
    assert len(legs) == 1 and legs[0].mode == "taxi"


def test_a_missed_scheduled_departure_is_infeasible_not_ignored():
    # The only train leaves the airport at 540 (9:00). Starting at 700
    # (after it has left) must never use it -- `expand_frontier`'s own
    # "already left" refusal, not this test guessing at silence.
    loop, stops = a_demo_loop()
    front, legs = request_and_plan(loop, stops, weight_cost=1.0, weight_time=0.0,
                                    start_time=700)
    assert all(leg.mode != "train" for leg in legs)


def test_no_itinerary_at_all_when_the_budget_cannot_afford_any_leg():
    loop, stops = a_demo_loop()
    result = request_and_plan(loop, stops, weight_cost=0.5, weight_time=0.5,
                               budget=1.0)
    assert result is None
