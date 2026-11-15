"""S6: the walking skeleton of the train trip with a budget
(`loopingrules_ux.s6`, Plan U U8; ADR-13).

It pins the *seam* of the correction pass -- materialized candidates, a distinct
pure evaluator, application memory, and the evaluator's choice *being* what
fires -- not a search algorithm. Two models (planning + budget), two planners.
"""

from __future__ import annotations

import pytest

from loopingrules_ux import s6
from loopingrules_ux.s6 import (PENALTY, TEST, TRAIN, Tree, budget_veto, build,
                                context, grow, materialize, plan_greedy,
                                plan_pool, run, trajectory)


def _request(w):
    return w.first("request")[0]


# -- the two models -----------------------------------------------------

def test_greedy_takes_the_direct_leg():
    w = build(TRAIN[0])                       # e1: A -> B, fare 10
    plan = plan_greedy(w, _request(w))
    assert w.get(plan, "cost") == 10 and w.get(plan, "hops") == 1


def test_greedy_has_nothing_without_a_direct_leg():
    w = build(TRAIN[2])                       # h1: A -> B -> C, no direct leg
    assert plan_greedy(w, _request(w)) is None


def test_pool_finds_the_cheapest_path():
    w = build(TRAIN[3])                       # h3: direct A->C is 20; A->B->C is 2
    plan = plan_pool(w, _request(w))
    assert w.get(plan, "cost") == 2 and w.get(plan, "hops") == 2


def test_budget_veto_discards_an_over_budget_plan():
    w = build(TRAIN[3])                       # h3: budget 10, greedy's direct is 20
    request = _request(w)
    plan = plan_greedy(w, request)
    assert budget_veto(w, request) == 1
    assert w.has(plan, "vetoed")


def test_an_in_budget_plan_is_not_vetoed():
    w = build(TRAIN[0])                       # e1: fare 10, budget 50
    request = _request(w)
    plan = plan_greedy(w, request)
    assert budget_veto(w, request) == 0
    assert not w.has(plan, "vetoed")


# -- materialized candidates, and a pure evaluator ----------------------

def test_materialize_enumerates_one_application_per_planner():
    w = build(TRAIN[0])
    apps = materialize(w, _request(w))
    assert sorted(w.get(a, "planner") for a in apps) == ["greedy", "pool"]


def test_the_evaluator_writes_nothing_to_the_blackboard():
    w = build(TRAIN[0])
    request = _request(w)
    apps = [w.get(a, "planner") for a in materialize(w, request)]
    tree = grow(TRAIN)
    before = w.revision
    tree.decide(context(w, request), apps)    # the selection
    assert w.revision == before               # ADR-13: never alters the blackboard


def test_the_evaluator_refuses_a_candidate_it_was_not_given():
    w = build(TRAIN[0])
    ctx = context(w, _request(w))
    with pytest.raises(ValueError):
        grow(TRAIN).decide(ctx, candidates=["nothing"])


# -- the choice the growth finds ----------------------------------------

def _expected(network):
    w = build(network)
    return "greedy" if context(w, _request(w))["direct_in_budget"] else "pool"


def test_growth_learns_direct_in_budget():
    tree = grow(TRAIN)
    for network in TRAIN + TEST:
        w = build(network)
        assert tree.decide(context(w, _request(w))) == _expected(network)


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
    w, _score = run(TRAIN[0], tree)           # e1 -> greedy
    assert trajectory(w) == [{"planner": "greedy", "cost": 10, "vetoed": False}]


def test_memory_records_a_vetoed_selection():
    tree = grow(TRAIN)
    w, score = run(TRAIN[4], tree)            # imp -> hopeless, plan vetoed
    assert score == PENALTY
    recorded = trajectory(w)
    assert len(recorded) == 1 and recorded[0]["vetoed"] is True


# -- edges --------------------------------------------------------------

def test_run_is_deterministic():
    tree = grow(TRAIN)
    assert run(TRAIN[3], tree)[1] == run(TRAIN[3], tree)[1]


def test_a_hopeless_request_scores_the_penalty():
    tree = grow(TRAIN)
    assert run(TRAIN[4], tree)[1] == PENALTY
