"""S6: the train trip with a budget, selected PER STEP
(`loopingrules_ux.s6`, Plan U U8; ADR-13).

The deepest reading of ADR-13 -- **multi-step steering is which application fires
next** -- pinned on the current substrate: per-step materialized candidate moves,
a cross-model budget exclusion, a distinct pure scorer, an executed trajectory,
and application memory.
"""

from __future__ import annotations

import pytest

from loopingrules_ux import s6
from loopingrules_ux.s6 import (PENALTY, STRONG, TEST, TRAIN, WEAK,
                                budget_exclude, build, grow, materialize_moves,
                                remaining, run, train_advance, trajectory)


def _trip(w):
    return w.first("trip")[0]


def _stops(w):
    return {name: stop.id for stop, name in w.each("name")}


# -- the train model ----------------------------------------------------

def test_train_advance_spends_the_fare_and_moves():
    w = build(TRAIN[0])                       # easy: A -> B, fare 5, cash 10
    trip = _trip(w)
    move = materialize_moves(w, trip)[0]
    assert train_advance(w, trip, move) is True
    assert w.get(trip, "cash") == 5 and w.has(trip, "done")


# -- materialized candidates, and the budget exclusion ------------------

def test_materialize_moves_lists_legs_from_the_current_stop():
    w = build(TRAIN[3])                       # multi: A -> B and A -> C
    moves = materialize_moves(w, _trip(w))
    assert len(moves) == 2


def test_budget_exclude_marks_unaffordable_moves():
    scenario = {"name": "dear", "stops": ["A", "B", "C"],
                "legs": [("A", "B", 3), ("A", "C", 30)], "start": "A",
                "goal": "C", "cash": 10}
    w = build(scenario)
    trip = _trip(w)
    moves = materialize_moves(w, trip)
    assert budget_exclude(w, trip, moves) == 1
    dear = [m for m in moves if w.get(m, "fare") == 30][0]
    assert w.has(dear, "vetoed")


# -- the two planning models --------------------------------------------

def test_remaining_is_the_cheapest_cost_to_the_goal():
    w = build(TRAIN[3])                       # multi: A->B->D (5) vs A->C->D (4)
    stops = _stops(w)
    assert remaining(w, _trip(w), stops["A"]) == 4
    assert remaining(w, _trip(w), stops["D"]) == 0


def test_lookahead_prefers_the_move_on_the_cheapest_path():
    w = build(TRAIN[3])                       # multi: A->C->D is cheaper
    trip = _trip(w)
    moves = materialize_moves(w, trip)
    chosen = STRONG.decide(w, trip, moves)
    assert w.get(chosen, "to") == _stops(w)["C"]


# -- the network: a distinct, pure scorer -------------------------------

def test_a_policy_writes_nothing_to_the_blackboard():
    w = build(TRAIN[3])
    trip = _trip(w)
    moves = materialize_moves(w, trip)
    before = w.revision
    WEAK.decide(w, trip, moves)               # the selection
    assert w.revision == before               # ADR-13: never alters the blackboard


def test_the_policy_returns_none_when_nothing_survives():
    scenario = {"name": "broke", "stops": ["A", "B"],
                "legs": [("A", "B", 30)], "start": "A", "goal": "B", "cash": 5}
    w = build(scenario)
    trip = _trip(w)
    moves = materialize_moves(w, trip)
    budget_exclude(w, trip, moves)
    assert STRONG.decide(w, trip, moves) is None


# -- the trajectory: a sequence of per-step selections ------------------

def test_the_trajectory_is_a_sequence_of_selections():
    w, _score = run(TRAIN[1], STRONG)         # chain: A -> B -> C
    assert [r["step"] for r in trajectory(w)] == [1, 2]
    assert [r["fare"] for r in trajectory(w)] == [1, 1]


def test_no_affordable_move_scores_the_penalty():
    scenario = {"name": "broke", "stops": ["A", "B"],
                "legs": [("A", "B", 30)], "start": "A", "goal": "B", "cash": 5}
    w, score = run(scenario, STRONG)
    assert score == PENALTY and trajectory(w) == []


# -- weak vs strong: the step budget is the circuit breaker -------------

def test_the_weak_policy_strays_and_the_budget_cuts_it():
    _w, score = run(TRAIN[2], WEAK)           # stray: greedy walks A <-> B
    assert score == PENALTY                   # never arrives


def test_the_strong_policy_reaches_the_goal():
    _w, score = run(TRAIN[2], STRONG)         # stray: lookahead goes A -> C
    assert score == 5.0                       # cash 10 - fare 5


# -- growth: the network learns which planner to rely on ----------------

def test_growth_learns_to_use_the_lookahead():
    policy = grow(TRAIN)
    assert policy.weights["lookahead"] != 0
    assert s6._total(TEST, policy) == s6._total(TEST, STRONG)


def test_grown_matches_the_oracle_and_beats_the_weak_policy():
    policy = grow(TRAIN)
    grown = s6._total(TEST, policy)
    assert grown == s6._oracle(TEST)
    assert grown > s6._total(TEST, WEAK)


# -- edges --------------------------------------------------------------

def test_run_is_deterministic():
    policy = grow(TRAIN)
    assert run(TRAIN[3], policy)[1] == run(TRAIN[3], policy)[1]


def test_a_scenario_with_no_route_scores_the_penalty():
    scenario = {"name": "nowhere", "stops": ["A", "B"],
                "legs": [], "start": "A", "goal": "B", "cash": 5}
    assert run(scenario, STRONG)[1] == PENALTY
