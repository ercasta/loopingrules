"""`examples.hierarchy` -- Experiment 4: freeze the local islands, tune only
the bridge. The numbers are pinned as SHAPE, not as one snapshot: the
bridge beats equal weighting, freezing costs more when local tasks misalign
with the global one, and conditioning the data does not move a
well-specified local optimum (shift needs misspecification)."""

import pytest

from examples import hierarchy as h
from loopingrules.loop import Loop


@pytest.fixture(scope="module")
def report():
    return h.report()


# -- the rule world is the same computation as the fast path -------------

def test_the_rule_world_and_the_fast_path_agree():
    situations = h.dataset(40, seed=3)
    loop = Loop()
    h.install(loop, alpha_bias=0.4, beta_bias=0.7,
              w_alpha=1.0, w_beta=0.5, theta=0.8)
    world_verdicts = h.run_world(loop, situations)
    fast = h.verdicts(*h.opinions(situations, 0.4, 0.7), 1.0, 0.5, 0.8)
    assert [int(v) for v in world_verdicts] == fast


# -- stage 1: the islands tune their own local tasks ---------------------

def test_inner_tuning_recovers_the_local_boundary():
    situations = h.dataset(400, seed=4)
    assert h.inner_tune(situations, "alpha", 0.5) == 0.5
    assert h.inner_tune(situations, "alpha", 0.2) == 0.2


# -- stage 2: the bridge, with the islands frozen -------------------------

def test_the_bridge_beats_equal_weights(report):
    assert report["aligned"]["global"] > report["aligned"]["equal_weight"]
    assert report["misaligned"]["global"] > report["misaligned"]["equal_weight"]


def test_the_joint_ceiling_is_at_least_the_staged(report):
    assert report["joint"] >= report["aligned"]["global"]
    assert report["joint"] >= report["misaligned"]["global"]


def test_freezing_costs_more_when_local_tasks_misalign(report):
    # Aligned local tasks are good proxies for the global objective; the
    # misaligned ones are not, so the freeze costs more.
    assert report["freeze_cost"]["misaligned"] > report["freeze_cost"]["aligned"]
    assert report["freeze_cost"]["aligned"] >= 0.0


# -- covariate shift: the lever is the objective, not the data ------------

def test_conditioning_does_not_move_a_well_specified_optimum(report):
    ds = report["distribution_shift"]
    assert (ds["threshold_task"]["uniform"]
            == ds["threshold_task"]["conditioned"])
    assert (ds["calibration_wellspecified"]["uniform"]
            == ds["calibration_wellspecified"]["conditioned"])


def test_shift_appears_only_under_misspecification(report):
    ds = report["distribution_shift"]
    assert (ds["calibration_misspecified"]["uniform"]
            != ds["calibration_misspecified"]["conditioned"])


def test_report_shape(report):
    assert set(report) == {
        "aligned", "misaligned", "joint", "freeze_cost", "distribution_shift"}
    for branch in (report["aligned"], report["misaligned"]):
        assert set(branch) == {
            "frozen_biases", "bridge", "global", "equal_weight"}
