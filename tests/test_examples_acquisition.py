"""`examples.acquisition` -- Experiment 3 from `docs/tuning.md`: acquiring a
genuinely NEW behaviour (selling) authored vs de novo, and whether the new
decision is reachable without the projection.

The learner is small and seeded, so the full-data numbers are stable; the
learning CURVE is noisy by design and pinned as SHAPE, not as one snapshot:
the tag recovers the sell decision from far fewer examples than raw facts,
and the raw learner CONVERGES toward the tag without closing on it at a
feasible budget. Findings live in `acquisition.py`'s own docstring."""

import pytest

from examples import acquisition as ac
from examples import cards, market


@pytest.fixture(scope="module")
def report():
    return ac.report()


# -- the new behaviour is genuinely absent from the base -----------------

def test_cards_cannot_sell_so_the_behaviour_is_absent_from_the_base():
    for name in ("Offer", "Surplus", "tag_surplus", "decide_sell"):
        assert not hasattr(cards, name)
    assert hasattr(market, "tag_surplus") and hasattr(market, "decide_sell")


# -- the observation harness ---------------------------------------------

def test_a_sell_sample_is_labelled_by_surplus_and_stock():
    _primitive, tags, label = ac._sell_sample(value=100, held=1, offer=150)
    assert tags == {"Surplus": True, "Stock": True}
    assert label is True


def test_a_sell_sample_needs_both_the_surplus_and_a_held_copy():
    _primitive, tags, label = ac._sell_sample(value=100, held=0, offer=150)
    assert tags["Surplus"] is True and tags["Stock"] is False
    assert label is False
    _primitive, tags, label = ac._sell_sample(value=100, held=1, offer=80)
    assert tags["Surplus"] is False and tags["Stock"] is True
    assert label is False


def test_the_premium_is_what_moves_the_surplus_line():
    # The same offer is a surplus at premium 0 and not at premium 0.5 --
    # the knob the new behaviour reads, exercised.
    assert ac._sell_sample(value=100, held=1, offer=110, premium=0.0)[2] is True
    assert ac._sell_sample(value=100, held=1, offer=110, premium=0.5)[2] is False


def test_sell_dataset_is_reproducible_for_a_seed():
    assert ac.sell_dataset(50, seed=7) == ac.sell_dataset(50, seed=7)
    assert ac.sell_dataset(50, seed=7) != ac.sell_dataset(50, seed=8)


# -- the acquisition curves ----------------------------------------------

def test_the_structure_arm_reaches_the_decision_cheaply(report):
    structure = dict(report["curve"]["structure"])
    assert structure[16] > 0.9
    assert structure[64] == 1.0


def test_the_primitive_learner_needs_more_data_than_the_projection(report):
    novelty = report["novelty"]
    assert novelty["n_to_structure"] is not None
    assert novelty["n_to_primitive"] is not None
    assert novelty["n_to_primitive"] > novelty["n_to_structure"]
    assert novelty["gaps"][8] > 0.1          # the cost bites at small N


def test_the_primitive_learner_converges_toward_but_not_past_the_tag(report):
    _sizes, rows = report["converge"]
    primitive = [p for _size, p, _structure in rows]
    structure = [s for _size, _p, s in rows]
    assert primitive == sorted(primitive)     # rises with the budget
    assert primitive[-1] < 1.0                # a residual never closed
    assert all(s == 1.0 for s in structure)   # the tag is exact throughout
    assert primitive[0] < structure[0]


def test_report_states_the_result_honestly(report):
    novelty = report["novelty"]
    assert novelty["structure_at_largest_N"] == 1.0
    assert 0.0 < novelty["gap_at_largest_N"] < 0.1
    assert novelty["reaches_the_tag"] is True   # representable, at a price


# -- the authored price ---------------------------------------------------

def test_authored_acquisition_is_a_couple_of_rules_and_a_knob(report):
    assert report["authored_cost"] == {
        "rules": 2, "knobs": 1, "labels": 0, "base_has_it": False}
