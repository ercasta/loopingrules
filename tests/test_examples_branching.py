"""`examples.branching` -- Experiment 7: a finding raises a choice, and the
chosen remedy raises ANOTHER choice (a branch). Pins the mechanics (two
levels resolved by the same `pick_winner`, keyed by question entity) and the
finding (depth costs; tuning picks the shallow branch; too small a depth
budget silently refuses)."""

import pytest

from examples import branching as b
from examples.decide import Winner
from loopingrules.loop import Loop


@pytest.fixture(scope="module")
def report():
    return b.report()


def _run(**kwargs):
    loop = Loop()
    b.install(loop, **kwargs)
    settled = loop.run()
    return loop.world, settled


def _asked(world):
    return sorted(checked.kind for _e, checked in world.all(b.Checked))


# -- the branch is two levels --------------------------------------------

def test_the_tent_branch_opens_a_second_choice():
    world, _settled = _run(guests=4, rain=0.9, prefer_relocate=0.0, max_checks=4)
    assert _asked(world) == ["cover", "tent_size", "weather"]   # depth 2
    assert [t.name for _e, t in world.all(b.TentUsed)] == ["popup"]
    assert b.is_valid(world) is True


def test_the_same_pick_winner_resolves_both_levels():
    world, _settled = _run(guests=4, rain=0.9, prefer_relocate=0.0, max_checks=4)
    kinds = sorted(world.get(entity, b.Remedy).kind
                   for entity, _w in world.all(Winner))
    assert kinds == ["tent", "tent_option"]        # one winner per question


def test_the_relocate_branch_is_shallow():
    world, _settled = _run(guests=4, rain=0.9, prefer_relocate=40.0, max_checks=4)
    assert _asked(world) == ["cover", "weather"]   # depth 1
    assert [x for _e, x in world.all(b.Backup)]     # the hall
    assert world.all(b.TentUsed) == []
    assert b.is_valid(world) is True


def test_the_branch_settles_with_no_scheduler():
    _world, settled = _run(guests=4, rain=0.9)
    assert settled.hot == []


# -- depth is the tunable trajectory -------------------------------------

def test_a_too_small_depth_budget_refuses():
    world, _settled = _run(guests=4, rain=0.9, prefer_relocate=40.0, max_checks=1)
    # The weather check used the whole budget, no remedy was reached.
    assert _asked(world) == ["weather"]
    assert world.all(b.Planned) == []
    assert b.is_valid(world) is False


def test_tuning_prefers_the_shallow_branch(report):
    assert report["tuned"] > report["default"]
    prefer_relocate, max_checks = report["tuned_values"]
    assert prefer_relocate >= 40.0
    assert max_checks >= 2
    assert report["shallow_budget"] < report["tuned"]   # depth 1 breaks it


def test_report_shape(report):
    assert set(report) == {
        "default_values", "default", "tuned_values", "tuned", "shallow_budget"}
