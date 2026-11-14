"""`Loop(schedule=True)`: the recognize-act cycle, in the engine.

The opt-in scheduler (`docs/plan-scheduler.md`, probe `q0`): controller rules
run first, the order is recomputed so their control lands THIS tick, and then
ONE eligible rule fires. Under the attribute substrate a counter is a flat
attribute (`a`, `b`), a quota is a flat attribute, and a card/control is a
tagged entity read through `reflect`.
"""

from __future__ import annotations

from loopingrules import reflect
from loopingrules.loop import Loop


def inc_a(w) -> None:
    q = w.the("quota")
    if q is None:
        return
    for entity, a in w.each("a"):
        if a < q:
            w.set(entity, "a", a + 1)


def inc_b(w) -> None:
    q = w.the("quota")
    if q is None:
        return
    for entity, b in w.each("b"):
        if b < q:
            w.set(entity, "b", b + 1)


def serve_wish(w) -> None:
    for entity, _ in w.each("wish"):
        w.destroy(entity)


def disable_b(w) -> None:
    """A controller: hold `inc_b` back by disabling it."""
    for entity, _ in w.each("rule_card"):
        if "b" in w.get(entity, "writes"):
            reflect.control(w, w.get(entity, "hash"), enabled=False)


def balance(w) -> None:
    """A controller that gives the tie to whichever counter is BEHIND, so the
    schedule is fair -- the rule-level analogue of `q0`'s refraction."""
    a, b = w.the("a"), w.the("b")
    if a is None or b is None or w.the("quota") is None:
        return
    for entity, _ in w.each("rule_card"):
        wrote = w.get(entity, "writes")
        key = w.get(entity, "hash")
        if "a" in wrote:
            reflect.control(w, key, True, 1 if a <= b else 0)
        elif "b" in wrote:
            reflect.control(w, key, True, 1 if b < a else 0)


def _seeded(**kw):
    loop = Loop(**kw)
    w = loop.world
    w.set(w.spawn(), "a", 0)
    w.set(w.spawn(), "b", 0)
    w.set(w.spawn(), "quota", 3)
    return loop


# -- the default loop is unchanged --------------------------------------

def test_schedule_defaults_off():
    assert Loop().schedule is False


def test_default_loop_runs_every_rule_in_one_tick():
    loop = _seeded()
    loop.rule(inc_a)
    loop.rule(inc_b)
    fired = loop.tick()
    assert len(fired) == 2                      # both ran, this tick
    assert loop.world.the("a") == 1 and loop.world.the("b") == 1


# -- one rule per tick --------------------------------------------------

def test_schedule_fires_exactly_one_rule_per_tick():
    loop = _seeded(schedule=True)
    loop.rule(inc_a)
    loop.rule(inc_b)
    counts = [len(loop.tick()) for _ in range(6)]
    assert counts == [1, 1, 1, 1, 1, 1]         # never two, never zero
    assert loop.world.the("a") == 3 and loop.world.the("b") == 3


# -- control lands within the tick --------------------------------------

def test_a_controller_lands_within_the_tick_under_schedule():
    loop = _seeded(schedule=True)
    loop.rule(disable_b, priority=100, controller=True)
    loop.rule(inc_a)
    loop.rule(inc_b)
    reflect.reify(loop)
    fired = loop.tick()
    assert not any(n.endswith("inc_b") for n in fired)   # held back THIS tick
    assert loop.world.the("a") == 1 and loop.world.the("b") == 0


def test_default_loop_lags_by_a_tick_so_the_control_does_not_land():
    loop = _seeded()                            # schedule=False
    loop.rule(disable_b, priority=100, controller=True)
    loop.rule(inc_a)
    loop.rule(inc_b)
    reflect.reify(loop)
    fired = loop.tick()
    assert any(n.endswith("inc_b") for n in fired)       # ran anyway: next tick


# -- fairness and settling ----------------------------------------------

def test_schedule_with_a_controller_settles_and_is_fair():
    loop = _seeded(schedule=True, budget=100)
    loop.rule(balance, priority=100, controller=True)
    loop.rule(inc_a)
    loop.rule(inc_b)
    reflect.reify(loop)
    settled = loop.run()
    assert not settled.hot
    assert loop.world.the("a") == 3 and loop.world.the("b") == 3


# -- no ambiguity matches the default loop ------------------------------

def test_no_ambiguity_matches_the_default_loop():
    def build(schedule):
        loop = Loop(schedule=schedule)
        e = loop.world.spawn()
        loop.world.mark(e, "wish")
        loop.rule(serve_wish)
        return loop

    sched, plain = build(True), build(False)
    assert sched.run().ticks == plain.run().ticks == 2
    assert not sched.world.populated("wish")
    assert not plain.world.populated("wish")
