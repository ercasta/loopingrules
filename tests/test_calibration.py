"""`loopingrules_calibration` -- the calibration kit. These tests pin the
properties an experiment above it depends on: a replay is deterministic, a
knob writes the attribute a rule actually reads, a knob refuses to write an
attribute that was never seeded, the grid is what was declared, `search`
returns the values a scorer asks for, and `calibrate` reports held-out
scores, plateaus and sensitivity honestly.
"""

from __future__ import annotations

import pytest

from examples import cards
from loopingrules.engine import reply
from loopingrules.loop import Loop
from loopingrules_calibration import (
    Knob,
    Scenario,
    calibrate,
    declared,
    grid,
    knobs,
    reached,
    read_knobs,
    replay,
    replay_cached,
    reply_contains,
    runtime_knobs,
    search,
    settled,
    tunable,
    write_knobs,
)
from loopingrules_patterns import judge


def _level(world, name):
    return world.first(name)[1]


# -- replay and the trace -------------------------------------------------

def test_replay_is_deterministic():
    scenario = Scenario(kwargs=(("cash", 100),),
                        lines=("want dragon 1", "list dragon 40"))
    first = replay(scenario, cards.install)
    second = replay(scenario, cards.install)
    assert first.signature == second.signature
    assert first.fired == second.fired
    assert first.replies == second.replies
    assert first.hot == ()


def test_replay_records_which_rules_fired_per_tick():
    scenario = Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",))
    trace = replay(scenario, cards.install)
    fired = {name for tick in trace.fired for name in tick}
    assert "cards.hear_list" in fired       # the said was claimed
    assert "cards.tag_risk_level" in fired  # the risk was projected
    assert trace.ticks >= 1


def test_replay_observes_each_firing_tick():
    scenario = Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",))
    trace = replay(scenario, cards.install,
                   observe=lambda tick, world: (tick, len(world)))
    assert len(trace.observations) == trace.ticks
    ticks = [tick for tick, _size in trace.observations]
    assert ticks == list(range(1, trace.ticks + 1))


def test_replay_cached_returns_the_same_trace():
    cache = {}
    scenario = Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",))
    first = replay_cached(cache, cards.install, scenario, (), ())
    second = replay_cached(cache, cards.install, scenario, (), ())
    assert first is second


# -- knobs ----------------------------------------------------------------

def test_write_knobs_sets_the_attribute_the_rule_reads():
    knobs = (Knob("max_spend_per_trade", 10, 50, steps=1),)
    trace = replay(
        Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",)),
        cards.install, knobs, (10,))
    assert _level(trace.world, "max_spend_per_trade") == 10
    listing = trace.world.first("listing")[0]
    # price 40 is within the room (100) but over the tightened per-trade cap
    assert not trace.world.has(listing, "affordable")


def test_write_knobs_refuses_when_the_attribute_was_never_seeded():
    knobs = (Knob("max_premium", 0.0, 1.0),)
    with pytest.raises(ValueError):
        write_knobs(Loop().world, knobs, (0.5,))


def test_write_knobs_refuses_mismatched_lengths():
    knobs = (Knob("max_premium", 0.0, 1.0),)
    with pytest.raises(ValueError):
        write_knobs(Loop().world, knobs, (0.1, 0.2))


def test_read_knobs_reads_back_what_was_written():
    knobs = (Knob("max_level", 0.1, 0.9, steps=3),)
    trace = replay(Scenario(), cards.install, knobs, (0.3,))
    assert read_knobs(trace.world, knobs) == (0.3,)


def test_knob_values_are_the_declared_grid():
    float_knob = Knob("max_premium", 0.0, 0.4, steps=3)
    assert float_knob.values() == (0.0, 0.2, 0.4)
    int_knob = Knob("max_spend_per_trade", 0, 100, steps=3, integer=True)
    assert int_knob.values() == (0, 50, 100)


def test_knob_scope_defaults_to_offline():
    knob = Knob("max_premium", 0.0, 1.0)
    assert knob.scope == "offline"
    assert Knob("max_premium", 0.0, 1.0, scope="runtime").scope == "runtime"


def test_knob_refuses_an_unknown_scope():
    with pytest.raises(ValueError):
        Knob("max_premium", 0.0, 1.0, scope="sometimes")


def test_grid_is_the_cross_product_of_the_knobs():
    a = Knob("max_premium", 0.0, 0.2, steps=2)
    b = Knob("max_level", 0.1, 0.2, steps=2)
    assert list(grid((a, b))) == [
        (0.0, 0.1), (0.0, 0.2), (0.2, 0.1), (0.2, 0.2)]


# -- search ---------------------------------------------------------------

def test_search_finds_the_values_that_score_highest():
    knobs = (Knob("max_level", 0.1, 0.9, steps=9),)
    scenario = Scenario(kwargs=(("cash", 100),),
                        lines=("list dragon 40",))   # level 0.4

    def scorer(trace):
        listing = trace.world.first("listing")[0]
        return 1.0 if trace.world.has(listing, "too_risky") else 0.0

    best = search(cards.install, (scenario,), knobs, scorer)
    assert best.score == 1.0
    assert best.values[0] < 0.4      # only a tolerance under the level flags it


def test_search_returns_the_first_grid_point_on_a_tie():
    knobs = (Knob("max_level", 0.1, 0.3, steps=3),)

    def flat_scorer(_trace):
        return 1.0                    # every setting scores the same

    best = search(cards.install, (Scenario(),), knobs, flat_scorer)
    assert best.values == (0.1,)      # deterministic, not whichever came last


# -- generic scorer helpers ----------------------------------------------
#
# A tiny, self-contained domain so the helper/calibrate tests do not depend
# on the internals of `cards`: one threshold rule that reads `level`, one
# attribute (`inert`) that no rule ever reads, and a `spin` rule that never
# settles.

def _install_threshold(loop, x=0.0):
    world = loop.world
    threshold = world.spawn()
    world.set(threshold, "level", 0.5)
    inert = world.spawn()
    world.set(inert, "inert", 0.0)
    signal = world.spawn()
    world.mark(signal, "signal")
    world.set(signal, "x", x)

    @loop.rule
    def mark_over(w):
        ceiling = w.first("level")[1]
        for entity, _t, value in w.each("signal", "x"):
            if value > ceiling:
                w.mark(entity, "over")


def _over_scorer(trace):
    return 1.0 if trace.world.populated("over") else 0.0


def _install_echo(loop):
    @loop.rule
    def echo(w):
        for entity, _t, text in w.each("said", "text"):
            w.destroy(entity)
            reply(w, "user", "you said " + text)


def _install_spin(loop):
    @loop.rule
    def spin(w):
        marker = w.spawn()
        w.mark(marker, "spin")


def test_settled_helper_scores_a_clean_run():
    trace = replay(Scenario(kwargs=(("x", 1.0),)), _install_threshold)
    assert settled()(trace) == 1.0


def test_settled_helper_penalises_a_run_that_never_settles():
    trace = replay(Scenario(), _install_spin, budget=5)
    assert trace.hot            # it ran out of budget
    assert settled()(trace) == 0.0


def test_reply_contains_helper():
    trace = replay(Scenario(lines=("hi",)), _install_echo)
    assert reply_contains("you said")(trace) == 1.0
    assert reply_contains("goodbye")(trace) == 0.0


def test_reached_helper():
    trace = replay(Scenario(lines=("hi",)), _install_echo)
    assert reached("reply")(trace) == 1.0
    assert reached("spin")(trace) == 0.0


# -- calibrate / Report ---------------------------------------------------

def test_calibrate_reports_held_out_scores_and_shapes():
    knobs = (Knob("level", 0.2, 0.8, steps=4),
             Knob("inert", 0.0, 1.0, steps=3))
    cases = (Scenario(kwargs=(("x", 0.3),)),
             Scenario(kwargs=(("x", 0.7),)),
             Scenario(kwargs=(("x", 0.9),)))
    report = calibrate(_install_threshold, cases, knobs, _over_scorer, folds=3)

    assert report.best.values == (0.2, 0.0)     # first grid point on a tie
    assert report.eval_score == 1.0
    assert report.eval_std == 0.0
    assert len(report.fold_scores) == 3
    assert isinstance(report.signature, str)


def test_calibrate_finds_the_plateau_the_inert_knob_makes():
    knobs = (Knob("level", 0.2, 0.8, steps=4),
             Knob("inert", 0.0, 1.0, steps=3))
    cases = tuple(Scenario(kwargs=(("x", x),))
                  for x in (0.25, 0.45, 0.65, 0.85))
    report = calibrate(_install_threshold, cases, knobs, _over_scorer)

    assert report.plateaus
    assert all(len(group) == 3 for group in report.plateaus)


def test_calibrate_sensitivity_separates_a_flat_knob():
    knobs = (Knob("level", 0.2, 0.8, steps=4),
             Knob("inert", 0.0, 1.0, steps=3))
    cases = (Scenario(kwargs=(("x", 0.3),)), Scenario(kwargs=(("x", 0.9),)))
    report = calibrate(_install_threshold, cases, knobs, _over_scorer)

    moves = {name: moving for name, _distinct, moving in report.sensitivity}
    assert moves["level"] is True
    assert moves["inert"] is False


def test_calibrate_renders_markdown():
    knobs = (Knob("level", 0.2, 0.8, steps=2),)
    cases = (Scenario(kwargs=(("x", 0.9),)),)
    text = calibrate(_install_threshold, cases, knobs, _over_scorer).to_markdown()
    assert "# Calibration report" in text
    assert "Sensitivity" in text


# -- the declared tunable surface, collected from a real domain -----------

def test_knobs_collects_the_surface_a_domain_registers():
    loop = Loop()
    cards.install(loop)
    assert knobs(loop) == (Knob("max_level", 0.0, 1.0, steps=5),)


def test_declared_reads_back_what_tunable_attached():
    assert declared(judge.flag_too_risky) == (
        Knob("max_level", 0.0, 1.0, steps=5),)


def test_a_rule_with_no_declaration_has_an_empty_surface():
    assert declared(cards.hear_list) == ()


def test_tunable_refuses_a_non_knob():
    with pytest.raises(TypeError):
        @tunable("max_level")
        def _(w):
            pass


def test_tunable_needs_at_least_one_knob():
    with pytest.raises(ValueError):
        tunable()


def test_runtime_knobs_keeps_only_the_runtime_scope():
    offline = Knob("max_level", 0.0, 1.0, steps=5)
    live = Knob("max_level", 0.0, 1.0, steps=5, scope="runtime")
    assert runtime_knobs((offline, live)) == (live,)
    assert runtime_knobs((offline,)) == ()
