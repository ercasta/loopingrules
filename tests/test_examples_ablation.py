"""`examples.ablation` -- Experiment 2 from `docs/tuning.md`. The learner
is small and seeded, so the FULL-data numbers are stable; the learning
CURVE is not pinned to a snapshot (it is noisy by design) but the
qualitative finding is: at a fixed small data budget, the authored tags
recover the buy decision from far fewer examples than primitive features.
"""

import pytest

from examples import ablation as ab
from examples import cards, decide, market
from loopingrules_patterns import judge


# -- the observation harness ---------------------------------------------

def test_a_cards_sample_is_labelled_by_the_tag_conjunction():
    _primitive, tags, label = ab._cards_sample(cash=100, value=40, qty=1,
                                               held=0, price=40)
    assert tags == {"Wanted": True, "Affordable": True, "FairPriced": True,
                    "TooRisky": False}
    assert label is True


def test_a_satisfied_cards_want_is_not_wanted():
    _primitive, tags, label = ab._cards_sample(cash=100, value=40, qty=1,
                                               held=1, price=40)
    assert tags["Wanted"] is False
    assert label is False


def test_a_market_sample_yields_two_rival_listings_and_one_winner():
    samples = ab._market_sample(
        cash=100, value=40, qty=1, held=0, price=30, priority=0, price_rival=35,
        other_value=5, other_qty=0, other_held=0, other_priority=0)
    assert len(samples) == 2
    winners = [tags["Winner"] for _primitive, tags, _label in samples]
    assert winners.count(True) == 1        # the cheaper rival (30) wins
    buyer = [primitive["price"] for primitive, _t, label in samples if label]
    assert buyer == [30]


def test_the_ranking_bridge_discriminates_in_the_dataset():
    # If every sample's single listing always won, the `decide` bridge
    # would be inert and Experiment 2 would not test it at all.
    pool = ab.dataset("market", 500, seed=1)
    lost = sum(1 for _p, tags, _l in pool if not tags["Winner"])
    assert lost > 0.2 * len(pool)


def test_dataset_is_deterministic_for_a_seed():
    assert ab.dataset("cards", 20, seed=1) == ab.dataset("cards", 20, seed=1)
    assert ab.dataset("market", 20, seed=1) == ab.dataset("market", 20, seed=1)


def test_balanced_returns_equal_classes():
    pool = ab.balanced(ab.dataset("cards", 400, seed=1), seed=2)
    positives = sum(1 for _p, _t, label in pool if label)
    assert positives * 2 == len(pool)


# -- the learner ---------------------------------------------------------

def test_the_tree_learns_the_authored_structure_from_the_tags():
    pool = ab.balanced(ab.dataset("cards", 600, seed=1), seed=3)
    test = ab.balanced(ab.dataset("cards", 250, seed=2), seed=4)
    tree = ab.fit_tree(pool, "tags")
    assert ab.balanced_accuracy(tree, test, "tags") > 0.95


def test_authored_structure_needs_fewer_examples_than_primitive_features():
    pool = ab.balanced(ab.dataset("cards", 800, seed=1), seed=3)
    test = ab.balanced(ab.dataset("cards", 250, seed=2), seed=4)
    structure = ab.curve(pool, test, "tags", sizes=(16,), repeats=8)[0][1]
    primitive = ab.curve(pool, test, "primitive", sizes=(16,), repeats=8)[0][1]
    assert structure > primitive + 0.1


def test_the_curve_is_seeded_and_reproducible():
    pool = ab.balanced(ab.dataset("cards", 300, seed=1), seed=3)
    test = ab.balanced(ab.dataset("cards", 100, seed=2), seed=4)
    first = ab.curve(pool, test, "tags", sizes=(8,), repeats=5, seed=0)
    second = ab.curve(pool, test, "tags", sizes=(8,), repeats=5, seed=0)
    assert first == second


# -- earning the slope: the controlled depth dial ------------------------
#
# Feature vectors drawn from market's own distribution, the target a
# conjunction of `depth` conditions: single-feature ("axis") vs
# feature-comparing ("relational"). The claim is that the authored
# advantage is about RELATIONS, not depth as such -- so the axis gap stays
# near zero while the relational gap grows with depth. The two slopes are
# computed once, module-scoped (they are the expensive part of this file).


@pytest.fixture(scope="module")
def slope_result():
    return ab.slope(depths=(1, 5), sizes=(32, 64), vectors=3000, repeats=8)


def _gap(result, family, depth, size):
    for candidate, rows in result[family]:
        if candidate != depth:
            continue
        for n, primitive, structure in rows:
            if n == size:
                return structure - primitive
    raise AssertionError("no such depth/size: %s d=%s N=%s" % (family, depth, size))


def test_relational_composition_costs_more_than_axis_aligned_composition(slope_result):
    axis = _gap(slope_result, "axis", 5, 32)
    relational = _gap(slope_result, "relational", 5, 32)
    assert axis < 0.08                    # axis alignment is nearly free
    assert relational > axis + 0.1        # relations are where structure pays


def test_the_authored_tags_stay_flat_however_deep_the_composition(slope_result):
    for _depth, rows in slope_result["relational"]:
        for _size, _primitive, structure in rows:
            assert structure > 0.85


def test_the_gap_widens_with_relational_depth(slope_result):
    shallow = _gap(slope_result, "relational", 1, 64)
    deep = _gap(slope_result, "relational", 5, 64)
    assert deep > shallow + 0.03


# -- generalizing: the slope on the REAL verdict -------------------------
#
# The controlled dial above composes a synthetic target. This one dials the
# domain itself -- how many competing higher-priority wants exist -- and
# measures the gap on the real authored verdict. The cross-entity condition
# can only matter where a listing is otherwise buyable, so the curve is
# measured INSIDE that governed region, and `reach` records how small it is.


@pytest.fixture(scope="module")
def relevance_result():
    return ab.relevance(competitors=(1, 3), vectors=2000, size=32, repeats=8)


def test_the_cross_entity_region_is_substantially_reached(relevance_result):
    # With the market-natural parameterisation (cash just above price) a
    # listing is otherwise buyable often enough that the cross-entity
    # condition is exercised on the NATURAL distribution, not only inside a
    # contrived slice.
    for _competitors, data in relevance_result.items():
        assert data["reach"] > 0.15


def test_the_cross_entity_condition_binds_more_with_more_competing_wants(relevance_result):
    assert relevance_result[3]["binding"] > relevance_result[1]["binding"]
    assert relevance_result[1]["binding"] > 0.15


def test_the_authored_gap_widens_with_competing_wants_on_the_real_verdict(relevance_result):
    one = relevance_result[1]["structure"] - relevance_result[1]["primitive"]
    three = relevance_result[3]["structure"] - relevance_result[3]["primitive"]
    assert three > one + 0.03


def test_the_tags_stay_near_perfect_as_competitors_grow(relevance_result):
    for _competitors, data in relevance_result.items():
        assert data["structure"] > 0.9


# -- the ladder's other rungs: ranking and counting ----------------------
#
# `market` composes a conjunction; `trip`'s bridge composes a RANKING and
# `quorum` composes a COUNT. Each is a different kind of composition, and
# the flat learner's deficit behaves differently in each -- which is the
# point of climbing the ladder, not repeating one rung.

@pytest.fixture(scope="module")
def ranking_result():
    return ab.ranking(rivals=(2, 6), vectors=600, size=256, repeats=6)


def test_ranking_is_solved_exactly_by_the_winner_tag(ranking_result):
    for _rivals, data in ranking_result.items():
        assert data["structure"] > 0.95


def test_the_flat_learner_cannot_rank_from_per_row_features(ranking_result):
    # argmax needs every rival's score; a per-row tree has to reconstruct
    # the comparison, and the gap does not close by this budget.
    for _rivals, data in ranking_result.items():
        assert data["structure"] - data["primitive"] > 0.1


@pytest.fixture(scope="module")
def counting_result():
    return ab.counting(votes=(2, 8), vectors=700, size=32, repeats=8)


def test_counting_composition_costs_more_as_arity_grows(counting_result):
    small_gap = counting_result[2]["structure"] - counting_result[2]["primitive"]
    large_gap = counting_result[8]["structure"] - counting_result[8]["primitive"]
    assert large_gap > small_gap + 0.05


def test_counting_is_solved_exactly_by_the_passed_tag(counting_result):
    for _votes, data in counting_result.items():
        assert data["structure"] > 0.95
