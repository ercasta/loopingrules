"""`Loop(schedule=True)`: the recognize-act cycle, in the engine.

The opt-in scheduler (`docs/plan-scheduler.md`, probe `q0`): controller rules
run first, the order is recomputed so their `RuleControl` lands THIS tick, and
then ONE eligible rule fires. The claims pinned here:

* the default loop is unchanged -- `schedule=False` still runs every rule;
* under `schedule=True`, exactly one rule fires per tick;
* a controller's control lands within the tick (unlike the default loop's
  one-tick lag), so it can hold a rule back *this* tick;
* with a balancing controller the schedule is FAIR and still SETTLES;
* with no ambiguity it matches the default loop.

It is rule-level, not activation-level: the engine cannot see bindings (the
IR-native question the plan leaves open). These tests pin the rule-level half.
"""

import dataclasses

from loopingrules import reflect
from loopingrules.loop import Loop
from loopingrules.reflect import RuleControl


@dataclasses.dataclass(frozen=True)
class A:
    v: int = 0


@dataclasses.dataclass(frozen=True)
class B:
    v: int = 0


@dataclasses.dataclass(frozen=True)
class Quota:
    n: int = 3


@dataclasses.dataclass(frozen=True)
class Wish:
    pass


def inc_a(w) -> None:
    q = w.the(Quota)
    if q is None:
        return
    for entity, a in w.each(A):
        if a.v < q.n:
            w.replace(entity, A(a.v + 1))


def inc_b(w) -> None:
    q = w.the(Quota)
    if q is None:
        return
    for entity, b in w.each(B):
        if b.v < q.n:
            w.replace(entity, B(b.v + 1))


def serve_wish(w) -> None:
    for entity, _wish in w.each(Wish):
        w.destroy(entity)


def disable_b(w) -> None:
    """A controller: hold `inc_b` back by disabling it."""
    for entity, card in w.each(reflect.RuleCard):
        if "B" in card.writes:
            w.replace(entity, RuleControl(card.hash, enabled=False))


def balance(w) -> None:
    """A controller that gives the tie to whichever counter is BEHIND, so the
    schedule is fair -- the rule-level analogue of `q0`'s refraction."""
    a, b = w.the(A), w.the(B)
    if a is None or b is None or w.the(Quota) is None:
        return
    for entity, card in w.each(reflect.RuleCard):
        if "A" in card.writes:
            w.replace(entity, RuleControl(card.hash, True, 1 if a.v <= b.v else 0))
        elif "B" in card.writes:
            w.replace(entity, RuleControl(card.hash, True, 1 if b.v < a.v else 0))


def _seeded(**kw):
    loop = Loop(**kw)
    loop.world.spawn(A(0))
    loop.world.spawn(B(0))
    loop.world.spawn(Quota(3))
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
    assert loop.world.the(A).v == 1 and loop.world.the(B).v == 1


# -- one rule per tick --------------------------------------------------

def test_schedule_fires_exactly_one_rule_per_tick():
    loop = _seeded(schedule=True)
    loop.rule(inc_a)
    loop.rule(inc_b)
    counts = [len(loop.tick()) for _ in range(6)]
    assert counts == [1, 1, 1, 1, 1, 1]         # never two, never zero
    # and sequential: inc_a to quota, then inc_b
    assert loop.world.the(A).v == 3 and loop.world.the(B).v == 3


# -- control lands within the tick --------------------------------------

def test_a_controller_lands_within_the_tick_under_schedule():
    loop = _seeded(schedule=True)
    loop.rule(disable_b, priority=100, controller=True)
    loop.rule(inc_a)
    loop.rule(inc_b)
    reflect.reify(loop)
    fired = loop.tick()
    assert not any(n.endswith("inc_b") for n in fired)   # held back THIS tick
    assert loop.world.the(A).v == 1 and loop.world.the(B).v == 0


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
    assert loop.world.the(A).v == 3 and loop.world.the(B).v == 3


# -- no ambiguity matches the default loop ------------------------------

def test_no_ambiguity_matches_the_default_loop():
    def build(schedule):
        loop = Loop(schedule=schedule)
        loop.world.spawn(Wish())
        loop.rule(serve_wish)
        return loop

    sched, plain = build(True), build(False)
    assert sched.run().ticks == plain.run().ticks == 2
    assert not sched.world.populated(Wish)
    assert not plain.world.populated(Wish)
