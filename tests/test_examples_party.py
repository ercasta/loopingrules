"""`examples.party` -- Experiment 5: a chained investigation with no central
scheduler. Pins the mechanics (the chain runs to quiescence; a question is
deduped by existence) and the finding (scope decides correctness and cost:
too narrow silently skips a step, too broad wastes a check)."""

import pytest

from examples import party
from loopingrules.loop import Loop


@pytest.fixture(scope="module")
def report():
    return party.report()


# -- the chain runs itself, and terminates -------------------------------

def test_the_chain_settles_with_no_scheduler():
    result = party.run("scoped", **party._OUTDOOR)
    assert result["settled"] and result["hot"] == []


def test_scoped_reaches_a_valid_plan_via_the_weather_then_backup_chain():
    result = party.run("scoped", **party._OUTDOOR)
    assert result == {"planned": True, "valid": True, "asks": 2,
                      "settled": True, "hot": []}


def test_a_question_is_deduped_by_existence_not_by_a_queue():
    # Answering leaves a durable `Checked`, so the same question is never
    # asked twice however many ticks the world runs.
    loop = Loop()
    party.install(loop, scope="scoped", **party._OUTDOOR)
    loop.run()
    kinds = sorted(checked.kind for _e, checked in loop.world.all(party.Checked))
    assert kinds == ["backup", "weather"]


# -- scope: narrow skips a step, broad wastes one ------------------------

def test_narrow_misses_the_venue_that_matters_and_refuses():
    # The FIRST venue is the indoor hall, so the narrow raiser never checks
    # the weather -- and the cautious decision refuses the outdoor party.
    result = party.run("narrow", **party._OUTDOOR)
    assert result["planned"] is False
    assert result["valid"] is False


def test_broad_wastes_a_check_on_a_venue_nobody_books(report):
    indoor = report["indoor_chosen"]
    assert indoor["scoped"]["asks"] == 0
    assert indoor["broad"]["asks"] > indoor["scoped"]["asks"]
    assert indoor["broad"]["valid"] and indoor["scoped"]["valid"]


# -- the danger: a sub-scoped trigger and a trusting decision ------------

def test_a_subscoped_trigger_makes_a_confident_but_invalid_plan(report):
    trusting = report["trusting_narrow"]
    assert trusting["planned"] is True
    assert trusting["valid"] is False      # outdoor party, raining, no backup


# -- shape ----------------------------------------------------------------

def test_report_covers_both_scenarios_and_the_trusting_case(report):
    assert set(report) == {"outdoor_risky", "indoor_chosen", "trusting_narrow"}
    for scenario in ("outdoor_risky", "indoor_chosen"):
        assert set(report[scenario]) == {"narrow", "scoped", "broad"}
