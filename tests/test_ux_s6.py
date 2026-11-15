"""S6: the walking skeleton of the train trip with a budget
(`loopingrules_ux.s6`, Plan U U8; ADR-13).

It pins the *seam* of the correction pass -- materialized candidates, a distinct
pure evaluator, a listwise `rank` that eliminates, an executed trip, and
application memory -- not a search algorithm. Three models: train, planning,
budget.
"""

from __future__ import annotations

import pytest

from loopingrules_ux import s6
from loopingrules_ux.s6 import (PENALTY, TEST, TRAIN, Tree, budget_veto, build,
                                context, grow, materialize_planners, plan_greedy,
                                plan_pool, rank, run, train_execute, trajectory)


def _trip(w):
    return w.first("trip")[0]


# -- the train model ----------------------------------------------------

def test_train_execute_walks_a_plan_and_completes_the_trip():
    w = build(TRAIN[0])                       # e1: A -> B, fare 10, cash 50
    trip = _trip(w)
    plan = plan_greedy(w, trip)[0]
    assert train_execute(w, trip, plan) is True
    assert w.get(trip, "cash") == 40
    assert w.get(trip, "at") == w.get(trip, "goal")
    assert w.has(trip, "done")


# -- the planning model -------------------------------------------------

def test_greedy_proposes_the_direct_leg():
    w = build(TRAIN[0])
    plans = plan_greedy(w, _trip(w))
    assert len(plans) == 1 and w.get(plans[0], "cost") == 10


def test_greedy_proposes_nothing_without_a_direct_leg():
    w = build(TRAIN[2])                       # h1: A -> B -> C, no direct leg
    assert plan_greedy(w, _trip(w)) == []


def test_pool_proposes_several_paths():
    w = build(TRAIN[4])                       # m1: A->B->D and A->C->D
    plans = plan_pool(w, _trip(w))
    assert sorted(w.get(p, "cost") for p in plans) == [4, 5]


# -- the budget model (cross-model) -------------------------------------

def test_budget_veto_discards_an_over_budget_candidate():
    w = build(TRAIN[3])                       # h3: cash 10, greedy's direct is 20
    trip = _trip(w)
    plan = plan_greedy(w, trip)[0]
    assert budget_veto(w, trip) == 1
    assert w.has(plan, "vetoed")


# -- the listwise evaluator, and its elimination ------------------------

def test_rank_selects_the_cheapest_and_eliminates_the_rest():
    w = build(TRAIN[4])                       # m1: costs 4 and 5
    trip = _trip(w)
    plans = plan_pool(w, trip)
    assert w.get(rank(w, plans), "cost") == 4


def test_rank_breaks_a_tie_on_hops():
    scenario = {"name": "tie", "stops": ["A", "B", "C"],
                "legs": [("A", "C", 4), ("A", "B", 2), ("B", "C", 2)],
                "start": "A", "goal": "C", "cash": 20}
    w = build(scenario)                       # A->C (1 hop) vs A->B->C (2 hops)
    plans = plan_pool(w, _trip(w))
    assert w.get(rank(w, plans), "hops") == 1


def test_rank_excludes_when_every_candidate_is_vetoed():
    w = build(TRAIN[3])                       # h3
    trip = _trip(w)
    plans = plan_greedy(w, trip)
    budget_veto(w, trip)
    assert rank(w, plans) is None


# -- materialized candidates, and a pure evaluator ----------------------

def test_materialize_enumerates_one_application_per_planner():
    w = build(TRAIN[0])
    apps = materialize_planners(w, _trip(w))
    assert sorted(w.get(a, "planner") for a in apps) == ["greedy", "pool"]


def test_the_evaluator_writes_nothing_to_the_blackboard():
    w = build(TRAIN[0])
    trip = _trip(w)
    apps = [w.get(a, "planner") for a in materialize_planners(w, trip)]
    tree = grow(TRAIN)
    before = w.revision
    tree.decide(context(w, trip), apps)       # the selection
    assert w.revision == before               # ADR-13: never alters the blackboard


def test_the_evaluator_refuses_a_candidate_it_was_not_given():
    w = build(TRAIN[0])
    with pytest.raises(ValueError):
        grow(TRAIN).decide(context(w, _trip(w)), candidates=["nothing"])


# -- the activation the growth finds ------------------------------------

def _expected(network):
    w = build(network)
    return "greedy" if context(w, _trip(w))["direct_in_budget"] else "pool"


def test_growth_learns_direct_in_budget():
    tree = grow(TRAIN)
    for network in TRAIN + TEST:
        w = build(network)
        assert tree.decide(context(w, _trip(w))) == _expected(network)


def test_grown_beats_every_fixed_choice_and_matches_the_oracle():
    tree = grow(TRAIN)
    grown = sum(run(n, tree)[1] for n in TEST)
    greedy = sum(run(n, Tree(action="greedy"))[1] for n in TEST)
    pool = sum(run(n, Tree(action="pool"))[1] for n in TEST)
    assert grown == s6._oracle(TEST)
    assert grown > pool > greedy


# -- the trajectory: the selection, recorded as world data --------------

def test_application_memory_records_the_selection():
    tree = grow(TRAIN)
    w, _score = run(TRAIN[0], tree)           # e1 -> greedy, one candidate
    assert trajectory(w) == [{"planner": "greedy", "cost": 10,
                              "proposed": 1, "eliminated": 0}]


def test_memory_records_the_ranking_elimination():
    tree = grow(TRAIN)
    w, _score = run(TRAIN[4], tree)           # m1 -> pool, two candidates
    recorded = trajectory(w)[0]
    assert recorded["planner"] == "pool" and recorded["cost"] == 4
    assert recorded["proposed"] == 2 and recorded["eliminated"] == 1


# -- edges --------------------------------------------------------------

def test_run_is_deterministic():
    tree = grow(TRAIN)
    assert run(TRAIN[4], tree)[1] == run(TRAIN[4], tree)[1]


def test_a_hopeless_request_scores_the_penalty():
    tree = grow(TRAIN)
    w, score = run(TRAIN[5], tree)            # imp -> no in-budget plan
    assert score == PENALTY
    assert trajectory(w)[0]["cost"] is None
