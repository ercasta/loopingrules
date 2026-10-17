"""`examples.tuning` -- the instrument for examples-driven parameter
search. These tests pin the properties the experiment above it depends
on: a replay is deterministic, a knob writes the field a rule actually
reads, a knob refuses to write a component that was never seeded, the
grid is what was declared, and `search` returns the values a scorer
asks for -- not just a high score."""

import pytest

from examples import cards, judge, tuning
from loopingrules.loop import Loop


def test_replay_is_deterministic():
    scenario = tuning.Scenario(kwargs=(("cash", 100),),
                               lines=("want dragon 1", "list dragon 40"))
    first = tuning.replay(scenario, cards.install)
    second = tuning.replay(scenario, cards.install)
    assert first.signature == second.signature
    assert first.fired == second.fired
    assert first.replies == second.replies
    assert first.hot == ()


def test_replay_records_which_rules_fired_per_tick():
    scenario = tuning.Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",))
    replay = tuning.replay(scenario, cards.install)
    fired = {name for tick in replay.fired for name in tick}
    assert "cards.hear_list" in fired       # the Said was claimed
    assert "cards.tag_risk_level" in fired  # the Risk was projected
    assert replay.ticks >= 1


def test_write_knobs_sets_the_field_the_rule_reads():
    knobs = (tuning.Knob(cards.RiskProfile, "max_spend_per_trade", 10, 50, steps=1),)
    replay = tuning.replay(
        tuning.Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",)),
        cards.install, knobs, (10,))
    assert replay.world.the(cards.RiskProfile).max_spend_per_trade == 10
    listing, _component = replay.world.first(cards.Listing)
    # price 40 is within the room (100) but over the tightened per-trade cap
    assert not replay.world.has(listing, cards.Affordable)


def test_write_knobs_refuses_when_the_component_was_never_seeded():
    knobs = (tuning.Knob(cards.RiskProfile, "max_premium", 0.0, 1.0),)
    with pytest.raises(ValueError):
        tuning.write_knobs(Loop().world, knobs, (0.5,))


def test_write_knobs_refuses_mismatched_lengths():
    knobs = (tuning.Knob(cards.RiskProfile, "max_premium", 0.0, 1.0),)
    with pytest.raises(ValueError):
        tuning.write_knobs(Loop().world, knobs, (0.1, 0.2))


def test_read_knobs_reads_back_what_was_written():
    knobs = (tuning.Knob(judge.RiskTolerance, "max_level", 0.1, 0.9, steps=3),)
    replay = tuning.replay(tuning.Scenario(), cards.install, knobs, (0.3,))
    assert tuning.read_knobs(replay.world, knobs) == (0.3,)


def test_knob_values_are_the_declared_grid():
    float_knob = tuning.Knob(cards.RiskProfile, "max_premium", 0.0, 0.4, steps=3)
    assert float_knob.values() == (0.0, 0.2, 0.4)
    int_knob = tuning.Knob(cards.RiskProfile, "max_spend_per_trade", 0, 100,
                           steps=3, integer=True)
    assert int_knob.values() == (0, 50, 100)


def test_grid_is_the_cross_product_of_the_knobs():
    a = tuning.Knob(cards.RiskProfile, "max_premium", 0.0, 0.2, steps=2)
    b = tuning.Knob(judge.RiskTolerance, "max_level", 0.1, 0.2, steps=2)
    assert list(tuning.grid((a, b))) == [
        (0.0, 0.1), (0.0, 0.2), (0.2, 0.1), (0.2, 0.2)]


def test_search_finds_the_values_that_score_highest():
    knobs = (tuning.Knob(judge.RiskTolerance, "max_level", 0.1, 0.9, steps=9),)
    scenario = tuning.Scenario(kwargs=(("cash", 100),),
                               lines=("list dragon 40",))   # level 0.4

    def scorer(replay):
        listing, _component = replay.world.first(cards.Listing)
        return 1.0 if replay.world.has(listing, judge.TooRisky) else 0.0

    best = tuning.search(cards.install, (scenario,), knobs, scorer)
    assert best.score == 1.0
    assert best.values[0] < 0.4      # only a tolerance under the level flags it


def test_search_returns_the_first_grid_point_on_a_tie():
    knobs = (tuning.Knob(judge.RiskTolerance, "max_level", 0.1, 0.3, steps=3),)

    def flat_scorer(_replay):
        return 1.0                    # every setting scores the same

    best = tuning.search(cards.install, (tuning.Scenario(),), knobs, flat_scorer)
    assert best.values == (0.1,)      # deterministic, not whichever came last
