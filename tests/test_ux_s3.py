"""S3: growing a policy that resolves ambiguity between two islands
(`loopingrules_ux.s3`).

Two islands both propose the trader's `want`; the control network picks which
one, by context. Pins that the ambiguity is real and that growth resolves it --
and that the *rule-level* choice (`RuleControl`) is the right grain for "which
island", next to S5's binding-level control attributes.
"""

from __future__ import annotations

import pytest

from loopingrules import analyze

from loopingrules_ux import s3
from loopingrules_ux.s3 import (SCENARIOS_TEST, SCENARIOS_TRAIN, _total,
                                choose_arbitrage, choose_bargain, evaluate,
                                grow, route_strategy)

GROWN_ATTRIBUTES = {"policy", "strategy", "margin", "condition"}


# -- the thesis: growth resolves the ambiguity --------------------------

def test_growth_learns_the_context_dependent_strategy():
    assert grow(list(SCENARIOS_TRAIN)) == "afford_first"


def test_the_strategy_generalises():
    assert _total(SCENARIOS_TEST, "afford_first") == 210


def test_it_beats_every_fixed_choice():
    assert _total(SCENARIOS_TEST, "afford_first") == 210
    assert _total(SCENARIOS_TEST, "arbitrage") == 175
    assert _total(SCENARIOS_TEST, "bargain") == 40


def test_the_choice_switches_with_context():
    # ample -> arbitrage (+85); tight -> bargain (+25), because the best-spread
    # deal is unaffordable.
    assert evaluate(SCENARIOS_TRAIN[0], "afford_first")[0] == 85
    assert evaluate(SCENARIOS_TRAIN[1], "afford_first")[0] == 25


# -- the mechanism: two islands, one conflict, one rule-level switch ----

def test_both_islands_write_the_same_term():
    assert "want" in analyze.analyze(choose_arbitrage).writes
    assert "want" in analyze.analyze(choose_bargain).writes


def test_the_islands_and_choosers_do_not_read_the_strategy():
    for rule in s3.ISLANDS:
        assert not (analyze.analyze(rule).reads & GROWN_ATTRIBUTES)


def test_the_controller_is_opaque_by_design():
    # It calls `reflect.control`, the documented `analyze` boundary; it runs
    # ungated, and writes only the control channel.
    with pytest.raises(analyze.Opaque):
        analyze.analyze(route_strategy)


def test_everything_settles():
    for scenario in SCENARIOS_TRAIN + SCENARIOS_TEST:
        _profit, settled = evaluate(scenario, "afford_first")
        assert not settled.hot
