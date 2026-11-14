"""S5: a grown controller composes two islands (`loopingrules_ux.s5`).

The walking skeleton of Plan U (Phase U1). It pins the *pipeline* -- composed
islands + a grown policy + a mechanical fitness + held-out generalisation --
not a search algorithm.
"""

from __future__ import annotations

from loopingrules import analyze

from loopingrules_ux import s5
from loopingrules_ux.s5 import (SCENARIOS_TEST, SCENARIOS_TRAIN, buy_here,
                                choose_deal, evaluate, grow, move_trader,
                                sell_here)

CONTROL_ATTRIBUTES = {"want", "buy_city", "sell_city", "route_target"}
GROWN_ATTRIBUTES = {"policy", "margin", "condition"}


def _total(scenarios, condition, margin):
    return sum(evaluate(s, condition, margin)[0] for s in scenarios)


# -- the thesis: growth generalises to held-out scenarios ---------------

def test_grown_controller_profits_on_held_out():
    condition, margin = grow(list(SCENARIOS_TRAIN))
    # +60 (big) + 0 (loss2) + 35 (edge) + 0 (unafford2)
    assert _total(SCENARIOS_TEST, condition, margin) == 95


def test_growth_learns_the_affordability_predicate():
    condition, _margin = grow(list(SCENARIOS_TRAIN))
    # Without it, a tight-but-unaffordable deal strands the trader.
    assert "affordable" in condition


def test_grown_beats_a_do_nothing_and_an_always_trade_policy():
    condition, margin = grow(list(SCENARIOS_TRAIN))
    grown = _total(SCENARIOS_TEST, condition, margin)
    always = _total(SCENARIOS_TEST, [], 0.0)      # qualifies every deal
    assert grown == 95 and always == 60 and grown > always


def test_a_lossy_deal_is_skipped():
    condition, margin = grow(list(SCENARIOS_TRAIN))
    profit, settled = evaluate(SCENARIOS_TRAIN[1], condition, margin)  # "loss"
    assert profit == 0 and not settled.hot


# -- the mechanism: islands unchanged, acts by control attributes -------

def test_the_islands_do_not_read_the_grown_policy():
    for rule in (move_trader, buy_here, sell_here):
        assert not (analyze.analyze(rule).reads & GROWN_ATTRIBUTES)


def test_the_controller_only_writes_control_attributes():
    assert analyze.analyze(choose_deal).writes <= CONTROL_ATTRIBUTES


def test_every_rule_is_analyze_clean():
    for rule in (choose_deal, move_trader, buy_here, sell_here):
        analyze.analyze(rule)                      # raises Opaque if not


# -- edges --------------------------------------------------------------

def test_no_reachable_deal_means_no_trajectory():
    scenario = {"name": "no_route", "cities": ["A", "B"], "start": "A",
                "cash": 100, "routes": [],
                "cards": {"w": ("A", 10, "B", 50)}}
    profit, settled = evaluate(scenario, ["spread>0", "affordable"], 0.0)
    assert profit == 0 and not settled.hot


def test_the_grown_condition_settles_every_scenario():
    condition, margin = grow(list(SCENARIOS_TRAIN))
    for scenario in SCENARIOS_TRAIN + SCENARIOS_TEST:
        _profit, settled = evaluate(scenario, condition, margin)
        assert not settled.hot
