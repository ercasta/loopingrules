"""`examples.planning` -- Experiment 6: (b) a finding that raises a choice
among next questions, resolved locally by the `decide` bridge; (c) tuning
the investigation's thresholds against a TRAJECTORY score.

Pins the mechanics (both remedies proposed, the cheaper wins) and the
finding (a too-high rain threshold books an unprotected venue; a too-small
check budget cuts the chain; tuning beats both naive settings)."""

import pytest

from examples import planning as p
from loopingrules.loop import Loop


@pytest.fixture(scope="module")
def report():
    return p.report()


# -- the choice point: several remedies, one winner ----------------------

def test_the_choice_point_proposes_both_remedies_and_picks_the_cheaper():
    loop = Loop()
    p.install(loop, rain=0.9, rain_threshold=0.5, max_checks=4)
    loop.run()
    world = loop.world
    kinds = sorted(remedy.kind for _e, remedy in world.all(p.Remedy))
    assert kinds == ["backup", "tent"]
    winners = [world.get(entity, p.Remedy).kind for entity, _w in world.all(p.Winner)]
    assert winners == ["tent"]                      # cost 30 beats the hall's 50
    assert [t.cost for _e, t in world.all(p.TentUsed)] == [30]


def test_the_chain_still_settles_with_no_scheduler():
    loop = Loop()
    p.install(loop, rain=0.9)
    settled = loop.run()
    assert settled.hot == []


# -- the knobs: thresholds are the trajectory ----------------------------

def test_a_high_threshold_calls_a_drizzle_clear_and_books_unprotected():
    loop = Loop()
    p.install(loop, rain=0.4, rain_threshold=0.9, max_checks=4)
    loop.run()
    # The agent saw `Clear`, so it booked -- but it drizzled and the outdoor
    # venue has no remedy: a confident, invalid plan.
    assert any(True for _e, _pl in loop.world.all(p.Planned))
    assert p.is_valid(loop.world) is False


def test_a_small_check_budget_cuts_the_chain_before_the_remedy():
    loop = Loop()
    p.install(loop, rain=0.9, rain_threshold=0.5, max_checks=1)
    loop.run()
    world = loop.world
    assert world.all(p.Remedy) == []                # never got to the choice
    assert not any(True for _e, _pl in world.all(p.Planned))


# -- tuning beats the naive settings -------------------------------------

def test_tuning_beats_both_naive_settings(report):
    assert report["tuned"] > report["default"]
    assert report["tuned"] > report["naive_high_threshold"]
    assert report["tuned"] > report["naive_shallow_budget"]


def test_the_tuned_threshold_catches_the_lightest_rain(report):
    threshold, _max_checks = report["tuned_values"]
    assert threshold <= 0.4                          # the lightest rain seen


def test_report_shape(report):
    assert set(report) == {
        "default_values", "default", "tuned_values", "tuned",
        "naive_high_threshold", "naive_shallow_budget"}
