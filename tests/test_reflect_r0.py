"""R0's claims, as permanent verification points (`docs/plan-reflection.md`).

A rule can read what other rules ARE (a `rule_card` entity) and what they
HAVE DONE (a `remembered` entity), and change the schedule with a
`rule_control` entity -- while the rules it controls stay unchanged."""

from __future__ import annotations

import inspect

import loopingrules.analyze as analyze
from loopingrules import reflect
from loopingrules.loop import Loop

from examples import cards
from loopingrules_reflect import r0


def test_a_reflection_controller_settles_a_loop_that_alone_is_hot():
    uncontrolled = r0.run(r0.install_uncontrolled)
    controlled = r0.run(r0.install)
    assert uncontrolled.hot, "the uncontrolled loop was expected to be hot"
    assert not controlled.hot, "the controller should have settled it"


def test_the_controlled_rule_is_never_edited():
    assert "rule_control" not in analyze.analyze(r0.bump).reads
    assert "rule_control" not in analyze.analyze(r0.bump).writes
    assert "rule_control" not in inspect.getsource(r0.bump)

    trace = r0.run(r0.install)
    cards_by_hash = {h: writes for _e, _t, h, _r, writes
                     in trace.world.each("rule_card", "hash", "reads", "writes")}
    controls = {h: en for _e, _t, h, en
                in trace.world.each("rule_control", "hash", "enabled")}
    targets = [h for h, writes in cards_by_hash.items() if "counter" in writes]
    assert len(targets) == 1
    assert controls[targets[0]] is False


def test_reify_is_idempotent_and_covers_every_rule():
    loop = Loop()
    loop.rule(r0.bump)
    first = reflect.reify(loop)
    second = reflect.reify(loop)
    assert len(first) == 1
    assert second == []
    assert len(list(loop.world.each("rule_card"))) == len(loop.rules) == 1


def test_a_rule_card_matches_analyze():
    """A card cannot drift from the rule it describes -- it is derived."""
    loop = Loop()
    loop.rule(r0.bump)
    reflect.reify(loop)
    entity = loop.world.first("rule_card")[0]
    analysis = analyze.analyze(r0.bump)
    assert loop.world.get(entity, "name") == "r0.bump"
    assert set(loop.world.get(entity, "reads")) == set(analysis.reads)
    assert set(loop.world.get(entity, "writes")) == set(analysis.writes)


def test_a_disabled_rule_is_never_called():
    loop = Loop()
    loop.rule(r0.bump)
    loop.world.set(loop.world.spawn(), "counter", 0)
    reflect.reify(loop)
    reflect.control(loop.world, r0.bump._loopingrules_hash, enabled=False)
    settled = loop.run(budget=10)
    assert not settled.hot
    assert loop.world.first("counter")[1] == 0


def test_enabling_a_rule_whose_gate_is_closed_does_nothing():
    loop = Loop()
    loop.rule(r0.bump)
    reflect.reify(loop)
    reflect.control(loop.world, r0.bump._loopingrules_hash, enabled=True)
    loop.run(budget=10)
    assert not loop.world.populated("counter")


def test_a_control_for_an_unknown_hash_changes_nothing():
    loop = Loop()
    loop.rule(r0.bump)
    reflect.reify(loop)
    reflect.control(loop.world, "not-a-real-hash", enabled=False)
    loop.world.set(loop.world.spawn(), "counter", 0)
    loop.run(budget=10)
    assert loop.world.first("counter")[1] > 0     # bump still ran


def test_an_oscillating_controller_stays_hot():
    trace = r0.run(r0.install_oscillating, budget=60)
    assert trace.hot


def test_reify_covers_a_real_domain():
    """Reflection is generic: it reifies every rule a real domain registers."""
    loop = Loop()
    cards.install(loop)
    reflect.reify(loop)
    cards_seen = list(loop.world.each("rule_card"))
    assert len(cards_seen) == len(loop.rules) == 13
    by_name = {loop.world.get(entity, "name"): entity
               for entity, _t in cards_seen}
    assert "cards.decide_buy" in by_name
    assert "listing" in loop.world.get(by_name["cards.decide_buy"], "reads")
