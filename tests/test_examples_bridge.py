"""`examples.bridge_transfer` -- Experiment 1 from `docs/tuning.md`.

These tests pin both the experiment's mechanics (the harvested points are
the real projections, the fit recovers a separable threshold) and its
findings (form is one shared object at zero cost; a value transfers
exactly when the two islands' policies agree and degrades as they
diverge). The findings are pinned as behaviour, not as a frozen number
list, so the experiment stays honest if a domain default changes -- what
must hold is the SHAPE of the result, not one snapshot of it."""

from examples import bridge_transfer as bt
from examples import cards, shopping
from loopingrules_patterns import judge


# -- form: one object, reused, at zero cost -----------------------------

def test_the_shared_vocabulary_is_the_same_object_across_islands():
    form = bt.form_reuse()
    assert form["same_judge"]
    assert form["same_risk_shape"]
    assert form["same_tolerance_shape"]
    assert form["same_flag_shape"]
    assert form["new_rules_or_data"] == 0


def test_the_identities_are_real_imports_not_same_shaped_copies():
    # `cards`/`shopping` each import these from `loopingrules_patterns.
    # judge`; if either ever defined its own, the bridge would be a name,
    # not a bridge.
    assert cards.flag_too_risky is judge.flag_too_risky
    assert shopping.flag_too_risky is judge.flag_too_risky
    assert cards.Risk is shopping.Risk is judge.Risk


# -- the harvested points are the domains' own projections --------------

def test_cards_points_are_the_real_projected_levels():
    points = bt.cards_points()
    assert len(points) == len(range(5, 105, 5))
    assert all(0.0 <= level <= 1.0 for level, _label in points)
    for level, label in points:
        assert label == (1 if level > bt.TAU_CARDS else 0)


def test_shopping_points_span_the_urgency_range():
    points = bt.shopping_points()
    levels = sorted(level for level, _label in points)
    assert levels[0] == 0.0
    assert levels[-1] == 1.0


def test_only_items_carrying_a_projected_risk_are_counted():
    # One `needby milk` sets a deadline on milk alone; the other four
    # catalog items were never given one, so no `Risk` was projected for
    # them and they contribute no point -- an island that abstains has
    # made no claim to score.
    points = bt.shopping_points(days=(0,))
    assert len(points) == 1


# -- fit and accuracy ---------------------------------------------------

def test_fit_recovers_a_separable_threshold():
    points = bt.cards_points()
    threshold = bt.fit_threshold(points)
    assert abs(threshold - bt.TAU_CARDS) < 0.05
    assert bt.accuracy(points, threshold) == 1.0


def test_fit_ties_keep_the_conservative_smaller_threshold():
    # A genuinely inseparable pair: the smallest-error threshold is not
    # unique -- just under 0.4 and just over 0.6 both make exactly one
    # mistake. The refusal-to-guess choice is the smaller (flag-less) one.
    points = [(0.4, 1), (0.6, 0)]
    threshold = bt.fit_threshold(points)
    assert threshold < 0.5


# -- value: transfers only while the policies agree ---------------------

def test_value_transfers_exactly_when_the_two_policies_agree():
    _threshold, rows = bt.value_transfer()
    by_delta = dict(rows)
    assert by_delta[0.0] == 1.0


def test_value_transfer_degrades_as_the_policies_diverge():
    _threshold, rows = bt.value_transfer()
    by_delta = dict(rows)
    assert by_delta[0.0] == 1.0
    assert by_delta[0.4] < 1.0
    assert by_delta[-0.4] < 1.0


def test_value_transfer_is_symmetric_in_the_divergence():
    _threshold, rows = bt.value_transfer()
    by_delta = dict(rows)
    assert by_delta[0.3] == by_delta[-0.3]


def test_a_single_threshold_beats_nothing_but_is_not_always_right():
    # The honest middle: even when it fails, it is above the trivial
    # all-one-class baseline -- a value that is wrong is still information,
    # which is exactly why the bridge is worth having and not sufficient.
    _threshold, rows = bt.value_transfer()
    worst = min(accuracy for _delta, accuracy in rows)
    assert worst > 0.5


# -- sample efficiency and the no-bridge baseline -----------------------

def test_learning_curve_improves_with_more_examples():
    rows = bt.learning_curve(sizes=(1, 5, 21), repeats=50)
    assert rows[-1][1] >= rows[0][1]
    assert rows[-1][1] > 0.9


def test_learning_curve_is_seeded_and_reproducible():
    first = bt.learning_curve(sizes=(3,), repeats=25, seed=0)
    second = bt.learning_curve(sizes=(3,), repeats=25, seed=0)
    assert first == second


def test_without_the_bridge_the_raw_axes_do_not_intersect():
    axes = bt.raw_axes()
    assert axes["shared"] == ()
    assert not (set(axes["cards"]) & set(axes["shopping"]))
