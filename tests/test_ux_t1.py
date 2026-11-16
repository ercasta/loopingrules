"""T1's claims, as permanent verification points (`docs/plan-scale-probe.md` §5).

A fixed model set covers **held-out combinations** of its concepts with no per-case
code, **gaps** an unknown concept, and buys several use cases per added rule -- and
a branch-per-case control fails every combination. A test that cannot fail is not a
check.
"""

from __future__ import annotations

from loopingrules_ux import t1


def test_seen_cases_are_covered():
    assert t1.coverage(labels=t1.SEEN) == (2, 2)


def test_held_out_combinations_are_covered():
    """The claim: concepts never authored together still compose, with no code."""
    assert t1.coverage(labels=t1.HELD_OUT_COMBINATIONS) == (5, 5)


def test_an_unknown_concept_is_a_gap_not_a_guess():
    sound = t1.measure_soundness()
    assert sound["is_gap"]
    assert sound["gaps"] == ["underrated"]
    assert sound["chosen"] == []


def test_the_naive_control_passes_seen_and_fails_combinations():
    naive = t1.measure_naive()
    assert naive["seen"] == (2, 2)          # it coded the singles ...
    assert naive["held_out"] == (0, 5)      # ... and only the singles


def test_one_added_rule_buys_three_use_cases():
    fan = t1.measure_fanout()
    assert fan["base"] == 0                 # `priciest` undefined -> three gaps
    assert fan["with"] == 3
    assert fan["new"] == 3
    assert fan["rules_added"] == 1


def test_different_directives_take_different_trajectories():
    trajectories = t1.measure_trajectories()["trajectories"]
    assert trajectories["all"] != trajectories["cheapest"]     # a different choose
    assert trajectories["all"] != trajectories["all+limit"]    # the scope also fires
    assert t1.measure_trajectories()["distinct"] >= 4


def test_run_all_agrees_with_itself():
    rows = t1.run_all()
    assert all(ok for _label, ok, _note in rows)
