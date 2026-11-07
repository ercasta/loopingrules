"""R0's claims, as permanent verification points (`docs/plan-reflection.md`).

A rule can read what other rules ARE (`reflect.RuleCard`) and what they HAVE
DONE (`memory.Remembered`), and change the schedule with
`reflect.RuleControl` -- while the rules it controls stay byte-for-byte
unchanged. If the controller ever stops settling the hot loop, or control
ever stopped being data, or an oscillating controller stopped being caught,
this fails loudly.
"""

import inspect

import loopingrules.analyze as analyze
from loopingrules import reflect
from loopingrules.loop import Loop
from loopingrules.reflect import RuleCard, RuleControl

from examples import cards
from loopingrules_reflect import r0


def test_a_reflection_controller_settles_a_loop_that_alone_is_hot():
    """The whole point: `bump` alone never settles; the same `bump`, with a
    controller reading memory and rule-cards, does."""
    uncontrolled = r0.run(r0.install_uncontrolled)
    controlled = r0.run(r0.install)
    assert uncontrolled.hot, "the uncontrolled loop was expected to be hot"
    assert not controlled.hot, "the controller should have settled it"


def test_the_controlled_rule_is_never_edited():
    """Control is a component, not a gate: `bump` neither reads nor writes
    `RuleControl`, and the disable is visible as world data on its card's
    entity."""
    assert "RuleControl" not in analyze.analyze(r0.bump).reads
    assert "RuleControl" not in analyze.analyze(r0.bump).writes
    assert "RuleControl" not in inspect.getsource(r0.bump)

    trace = r0.run(r0.install)
    cards = {card.hash: card for _entity, card in trace.world.each(RuleCard)}
    controls = {c.hash: c for _entity, c in trace.world.each(RuleControl)}
    targets = [c for c in cards.values() if "Counter" in c.writes]
    assert len(targets) == 1
    assert controls[targets[0].hash].enabled is False


def test_reify_is_idempotent_and_covers_every_rule():
    loop = Loop()
    loop.rule(r0.bump)
    first = reflect.reify(loop)
    second = reflect.reify(loop)
    assert len(first) == 1
    assert second == []
    assert len(list(loop.world.each(RuleCard))) == len(loop.rules) == 1


def test_a_rule_card_matches_analyze():
    """A card cannot drift from the rule it describes -- it is derived."""
    loop = Loop()
    loop.rule(r0.bump)
    reflect.reify(loop)
    card = loop.world.the(RuleCard)
    analysis = analyze.analyze(r0.bump)
    assert card.name == "r0.bump"
    assert set(card.reads) == {k.__name__ for k in analysis.reads}
    assert set(card.writes) == {k.__name__ for k in analysis.writes}


def test_a_disabled_rule_is_never_called():
    loop = Loop()
    loop.rule(r0.bump)
    loop.world.spawn(r0.Counter(0))
    reflect.reify(loop)
    loop.world.spawn(RuleControl(r0.bump._loopingrules_hash, enabled=False))
    settled = loop.run(budget=10)
    assert not settled.hot
    assert loop.world.the(r0.Counter).value == 0


def test_enabling_a_rule_whose_gate_is_closed_does_nothing():
    """`RuleControl` may only subtract or reorder: with no `Counter`, `bump`'s
    derived gate is closed, and enabling it does not call it."""
    loop = Loop()
    loop.rule(r0.bump)
    reflect.reify(loop)
    loop.world.spawn(RuleControl(r0.bump._loopingrules_hash, enabled=True))
    loop.run(budget=10)
    assert not loop.world.populated(r0.Counter)


def test_a_control_for_an_unknown_hash_changes_nothing():
    loop = Loop()
    loop.rule(r0.bump)
    reflect.reify(loop)
    loop.world.spawn(RuleControl("not-a-real-hash", enabled=False))
    loop.world.spawn(r0.Counter(0))
    loop.run(budget=10)
    assert loop.world.the(r0.Counter).value > 0     # bump still ran


def test_an_oscillating_controller_stays_hot():
    """The hazard `docs/plan-adaptation.md` names: a controller whose own
    action flips the evidence it acts on never settles, and the budget
    breaker reports it rather than hanging."""
    trace = r0.run(r0.install_oscillating, budget=60)
    assert trace.hot


def test_reify_covers_a_real_domain():
    """Reflection is generic: it reifies every rule a real domain registers,
    reads derived rather than declared."""
    loop = Loop()
    cards.install(loop)
    reflect.reify(loop)
    cards_seen = list(loop.world.each(RuleCard))
    assert len(cards_seen) == len(loop.rules) == 13
    by_name = {card.name: card for _entity, card in cards_seen}
    assert "cards.decide_buy" in by_name
    assert "Listing" in by_name["cards.decide_buy"].reads
