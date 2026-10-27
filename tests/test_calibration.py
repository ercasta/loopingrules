"""`loopingrules_calibration` -- the calibration kit. These tests pin the
properties an experiment above it depends on: a replay is deterministic, a
knob writes the field a rule actually reads, a knob refuses to write a
component that was never seeded, the grid is what was declared, `search`
returns the values a scorer asks for (not just a high score), and
`calibrate` reports held-out scores, plateaus and sensitivity honestly.
"""

import dataclasses

import pytest

from examples import cards
from loopingrules_patterns import judge
from loopingrules.engine import Reply, Said
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
    assert "cards.hear_list" in fired       # the Said was claimed
    assert "cards.tag_risk_level" in fired  # the Risk was projected
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

def test_write_knobs_sets_the_field_the_rule_reads():
    knobs = (Knob(cards.RiskProfile, "max_spend_per_trade", 10, 50, steps=1),)
    trace = replay(
        Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",)),
        cards.install, knobs, (10,))
    assert trace.world.the(cards.RiskProfile).max_spend_per_trade == 10
    listing, _component = trace.world.first(cards.Listing)
    # price 40 is within the room (100) but over the tightened per-trade cap
    assert not trace.world.has(listing, cards.Affordable)


def test_write_knobs_refuses_when_the_component_was_never_seeded():
    knobs = (Knob(cards.RiskProfile, "max_premium", 0.0, 1.0),)
    with pytest.raises(ValueError):
        write_knobs(Loop().world, knobs, (0.5,))


def test_write_knobs_refuses_mismatched_lengths():
    knobs = (Knob(cards.RiskProfile, "max_premium", 0.0, 1.0),)
    with pytest.raises(ValueError):
        write_knobs(Loop().world, knobs, (0.1, 0.2))


def test_read_knobs_reads_back_what_was_written():
    knobs = (Knob(judge.RiskTolerance, "max_level", 0.1, 0.9, steps=3),)
    trace = replay(Scenario(), cards.install, knobs, (0.3,))
    assert read_knobs(trace.world, knobs) == (0.3,)


def test_knob_values_are_the_declared_grid():
    float_knob = Knob(cards.RiskProfile, "max_premium", 0.0, 0.4, steps=3)
    assert float_knob.values() == (0.0, 0.2, 0.4)
    int_knob = Knob(cards.RiskProfile, "max_spend_per_trade", 0, 100,
                    steps=3, integer=True)
    assert int_knob.values() == (0, 50, 100)


def test_knob_scope_defaults_to_offline():
    knob = Knob(cards.RiskProfile, "max_premium", 0.0, 1.0)
    assert knob.scope == "offline"
    assert Knob(cards.RiskProfile, "max_premium", 0.0, 1.0,
                scope="runtime").scope == "runtime"


def test_knob_refuses_an_unknown_scope():
    with pytest.raises(ValueError):
        Knob(cards.RiskProfile, "max_premium", 0.0, 1.0, scope="sometimes")


def test_grid_is_the_cross_product_of_the_knobs():
    a = Knob(cards.RiskProfile, "max_premium", 0.0, 0.2, steps=2)
    b = Knob(judge.RiskTolerance, "max_level", 0.1, 0.2, steps=2)
    assert list(grid((a, b))) == [
        (0.0, 0.1), (0.0, 0.2), (0.2, 0.1), (0.2, 0.2)]


# -- search ---------------------------------------------------------------

def test_search_finds_the_values_that_score_highest():
    knobs = (Knob(judge.RiskTolerance, "max_level", 0.1, 0.9, steps=9),)
    scenario = Scenario(kwargs=(("cash", 100),),
                        lines=("list dragon 40",))   # level 0.4

    def scorer(trace):
        listing, _component = trace.world.first(cards.Listing)
        return 1.0 if trace.world.has(listing, judge.TooRisky) else 0.0

    best = search(cards.install, (scenario,), knobs, scorer)
    assert best.score == 1.0
    assert best.values[0] < 0.4      # only a tolerance under the level flags it


def test_search_returns_the_first_grid_point_on_a_tie():
    knobs = (Knob(judge.RiskTolerance, "max_level", 0.1, 0.3, steps=3),)

    def flat_scorer(_trace):
        return 1.0                    # every setting scores the same

    best = search(cards.install, (Scenario(),), knobs, flat_scorer)
    assert best.values == (0.1,)      # deterministic, not whichever came last


# -- generic scorer helpers ----------------------------------------------

# A tiny, self-contained domain so the helper/calibrate tests do not depend
# on the internals of `cards`: one threshold rule that reads `Threshold`,
# one component (`Inert`) that no rule ever reads, and a `spin` rule that
# never settles.

@dataclasses.dataclass(frozen=True)
class Signal:
    x: float


@dataclasses.dataclass(frozen=True)
class Threshold:
    level: float


@dataclasses.dataclass(frozen=True)
class Inert:
    value: float


@dataclasses.dataclass(frozen=True)
class Over:
    pass


@dataclasses.dataclass(frozen=True)
class Spin:
    pass


def _install_threshold(loop, x=0.0):
    world = loop.world
    world.spawn(Threshold(0.5))
    world.spawn(Inert(0.0))
    world.spawn(Signal(x))

    @loop.rule
    def mark_over(w):
        threshold = w.the(Threshold)
        for entity, signal in w.each(Signal):
            if signal.x > threshold.level:
                w.attach(entity, Over())


def _over_scorer(trace):
    return 1.0 if trace.world.populated(Over) else 0.0


def _install_echo(loop):
    @loop.rule
    def echo(w):
        for entity, said in w.each(Said):
            w.destroy(entity)
            w.spawn(Reply("user", "you said " + said.text))


def _install_spin(loop):
    @loop.rule
    def spin(w):
        w.spawn(Spin())


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
    assert reached(Reply)(trace) == 1.0
    assert reached(Spin)(trace) == 0.0


# -- calibrate / Report ---------------------------------------------------

def test_calibrate_reports_held_out_scores_and_shapes():
    knobs = (Knob(Threshold, "level", 0.2, 0.8, steps=4),
             Knob(Inert, "value", 0.0, 1.0, steps=3))
    cases = (Scenario(kwargs=(("x", 0.3),)),
             Scenario(kwargs=(("x", 0.7),)),
             Scenario(kwargs=(("x", 0.9),)))
    report = calibrate(_install_threshold, cases, knobs, _over_scorer, folds=3)

    # x=0.3, 0.7, 0.9 over levels 0.2, 0.4, 0.6, 0.8: level 0.2 flags all
    # three, so it is the best and the held-out score is 1.0.
    assert report.best.values == (0.2, 0.0)     # first grid point on a tie
    assert report.eval_score == 1.0
    assert report.eval_std == 0.0
    assert len(report.fold_scores) == 3
    assert isinstance(report.signature, str)


def test_calibrate_finds_the_plateau_the_inert_knob_makes():
    knobs = (Knob(Threshold, "level", 0.2, 0.8, steps=4),
             Knob(Inert, "value", 0.0, 1.0, steps=3))
    # Four `x` values offset from the level grid (0.25, 0.45, 0.65, 0.85)
    # so every level leaves a DIFFERENT set of `Over` tags, and the inert
    # knob never changes anything -- so each level is one behavioural class
    # of its three `Inert.value` settings.
    cases = tuple(Scenario(kwargs=(("x", x),))
                  for x in (0.25, 0.45, 0.65, 0.85))
    report = calibrate(_install_threshold, cases, knobs, _over_scorer)

    assert report.plateaus
    assert all(len(group) == 3 for group in report.plateaus)


def test_calibrate_sensitivity_separates_a_flat_knob():
    knobs = (Knob(Threshold, "level", 0.2, 0.8, steps=4),
             Knob(Inert, "value", 0.0, 1.0, steps=3))
    cases = (Scenario(kwargs=(("x", 0.3),)), Scenario(kwargs=(("x", 0.9),)))
    report = calibrate(_install_threshold, cases, knobs, _over_scorer)

    moves = {name: moving for name, _distinct, moving in report.sensitivity}
    assert moves["Threshold.level"] is True
    assert moves["Inert.value"] is False


def test_calibrate_renders_markdown():
    knobs = (Knob(Threshold, "level", 0.2, 0.8, steps=2),)
    cases = (Scenario(kwargs=(("x", 0.9),)),)
    text = calibrate(_install_threshold, cases, knobs, _over_scorer).to_markdown()
    assert "# Calibration report" in text
    assert "Sensitivity" in text


# -- the declared tunable surface, collected from a real domain -----------

def test_knobs_collects_the_surface_a_domain_registers():
    # `cards.install` registers `judge.flag_too_risky`, whose `RiskTolerance.
    # max_level` is a declared `@tunable` -- so the whole surface comes back
    # from the loop, with no hand-written knob list in the experiment.
    loop = Loop()
    cards.install(loop)
    assert knobs(loop) == (
        Knob(judge.RiskTolerance, "max_level", 0.0, 1.0, steps=5),)


def test_declared_reads_back_what_tunable_attached():
    assert declared(judge.flag_too_risky) == (
        Knob(judge.RiskTolerance, "max_level", 0.0, 1.0, steps=5),)


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
    offline = Knob(judge.RiskTolerance, "max_level", 0.0, 1.0, steps=5)
    live = Knob(judge.RiskTolerance, "max_level", 0.0, 1.0, steps=5,
                scope="runtime")
    assert runtime_knobs((offline, live)) == (live,)
    assert runtime_knobs((offline,)) == ()
