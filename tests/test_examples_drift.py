"""Experiment 8 (`examples/drift.py`): slow-timescale adaptation tracks a
world that moves, using the SAME checks the offline tuner used.

The load-bearing claims: a frozen world degrades as the target drifts, the
adapter keeps up and lands near the target, a stationary world settles after
one move, and the D4 guards (a rate limit) are honoured. If adaptation ever
peeked at the episode it was tuning for, the drift curve would be a lie --
so that leak is the first thing pinned.
"""

import pytest

from examples import drift


@pytest.fixture(scope="module")
def report():
    return drift.report()


def test_a_frozen_world_degrades_under_drift(report):
    assert report["frozen_cut"] == 0.3          # tuned on the early episodes
    assert report["frozen_tail"] < report["adaptive_tail"] - 0.1


def test_adaptation_tracks_the_target(report):
    assert abs(report["adaptive_cut"] - report["final_target"]) <= 0.1


def test_a_stationary_world_settles_after_one_move(report):
    assert report["still_moves"] == 1
    assert report["still_final"] == 0.6


def test_the_rate_limit_bounds_adjustments(report):
    assert report["slow_moves"] <= (24 - 1) // 12   # one adjustment at most
    assert report["slow_moves"] < report["fast_moves"]


def test_the_first_episode_never_tunes_itself():
    episodes = drift.stream(count=5)
    start = drift.frozen_values(episodes, train=2)
    _, steps = drift.adapt(episodes, drift.install,
                           drift.Adapter(knobs=drift.KNOBS, checks=drift.CHECKS,
                                         window=2), start=start)
    assert steps[0].moved is False
    assert steps[0].values == start


def test_adapt_is_deterministic():
    episodes = drift.stream(count=8)
    adapter = drift.Adapter(knobs=drift.KNOBS, checks=drift.CHECKS, window=2)
    assert drift.adapt(episodes, drift.install, adapter) == \
        drift.adapt(episodes, drift.install, adapter)


def test_the_scorer_is_the_same_vocabulary_both_wirings():
    """The Phase-4 seam: the adapter's objective IS the offline scorer --
    built from the same Check objects, not a same-shaped copy."""
    adapter = drift.Adapter(knobs=drift.KNOBS, checks=drift.CHECKS, window=1)
    assert tuple(adapter.checks) == tuple(drift.CHECKS)
    trace = drift.replay(drift.stream(count=1)[0], drift.install)
    assert adapter.scorer()(trace) == drift.SCORER(trace)
