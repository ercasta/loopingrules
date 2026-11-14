"""What the loop promises: every rule, in order, until nothing changes
-- called once a tick, writing to the world directly, with nothing in
between the write and the next rule seeing it.

Under the attribute substrate (D8) a former component with a field is a
plain ATTRIBUTE (`step` holds the number) and a fieldless tag is a FLAG
(`ping`, `pong`, `seen`).
"""

from __future__ import annotations

import pytest

from loopingrules.loop import Loop


@pytest.fixture
def loop():
    return Loop()


def _spawn_step(world, n):
    entity = world.spawn()
    world.set(entity, "step", n)
    return entity


def test_rules_run_in_registration_order_every_tick(loop):
    order = []
    loop.rule(lambda w: order.append("first"), name="first")
    loop.rule(lambda w: order.append("second"), name="second")
    loop.tick()
    loop.tick()
    assert order == ["first", "second", "first", "second"]


def test_a_rule_is_named_for_its_module_and_function(loop):
    @loop.rule
    def flag_big(w):
        pass

    @loop.rule(name="say hello")
    def _(w):
        pass

    assert [name for name, _ in loop.rules] == ["test_loop.flag_big", "say hello"]


def test_a_rule_fires_by_changing_something(loop):
    @loop.rule
    def marks(w):
        for e, _ in w.each("step"):
            w.mark(e, "seen")            # news once, and then never again

    _spawn_step(loop.world, 0)
    assert loop.tick() == ["test_loop.marks"]
    assert loop.tick() == []


def test_a_rule_that_writes_nothing_does_not_fire(loop):
    @loop.rule
    def idle(w):
        for entity, step in w.each("step"):
            pass   # reads, writes nothing

    _spawn_step(loop.world, 0)
    assert loop.tick() == []


def test_run_settles_when_a_whole_pass_changes_nothing(loop):
    @loop.rule
    def chain(w):
        for entity, step in w.each("step"):
            w.destroy(entity)
            if step < 3:
                _spawn_step(w, step + 1)

    _spawn_step(loop.world, 0)
    settled = loop.run()
    assert settled.hot == []
    assert settled.ticks == 5          # four steps, then the quiet pass
    assert len(loop.world) == 0


def test_a_spawn_is_a_real_entity_usable_the_same_call(loop):
    """`w.spawn()` hands back the real entity, not a placeholder -- usable
    immediately, in the rest of the SAME rule."""
    @loop.rule
    def make_and_mark(w):
        made = w.spawn()
        w.set(made, "step", 1)
        w.mark(made, "seen")

    loop.tick()
    entity, step = loop.world.each("step")[0]
    assert step == 1
    assert loop.world.has(entity, "seen")


def test_a_freshly_spawned_entity_s_id_is_usable_as_a_reference(loop):
    @loop.rule
    def make(w):
        made = w.spawn()
        w.set(made, "step", 1)
        holder = w.spawn()
        w.set(holder, "ref", made)

    loop.tick()
    w = loop.world
    target = w.each("step")[0][0]
    holder = w.each("ref")[0]
    # A reference is stored as a plain id, not a live handle.
    assert holder[1] == target.id
    assert w.entity(holder[1]) == target


def test_two_rules_feeding_each_other_stop_at_the_budget_and_are_named(loop):
    @loop.rule
    def ping(w):
        for entity, _ in w.each("pong"):
            w.destroy(entity)
            e = w.spawn()
            w.mark(e, "ping")

    @loop.rule
    def pong(w):
        for entity, _ in w.each("ping"):
            w.destroy(entity)
            e = w.spawn()
            w.mark(e, "pong")

    e = loop.world.spawn()
    loop.world.mark(e, "ping")
    settled = loop.run(budget=20)
    assert settled.ticks == 20
    assert sorted(set(settled.hot)) == ["test_loop.ping", "test_loop.pong"]


def test_a_rule_that_raises_is_recorded_and_the_others_still_run(loop):
    @loop.rule
    def explodes(w):
        raise ValueError("no")

    @loop.rule
    def carries_on(w):
        for e, _ in w.each("step"):
            w.mark(e, "seen")

    _spawn_step(loop.world, 0)
    settled = loop.run()
    assert loop.world.each("seen")
    assert [name for name, _ in loop.errors] == ["test_loop.explodes"]
    assert settled.hot == []


def test_install_hands_the_loop_to_a_domain(loop):
    def domain(lp, greeting="hi"):
        e = lp.world.spawn()
        lp.world.set(e, "step", greeting)
        lp.rule(lambda w: None, name="noop")

    loop.install(domain, greeting="hello")
    assert loop.world.the("step") == "hello"
    assert [name for name, _ in loop.rules] == ["noop"]


def test_a_rule_gated_by_its_own_reads_is_not_even_called_while_dormant(loop):
    """No `watches=` to declare any more -- `analyze()` derives a rule's
    reads from its own body (here, `w.each("step")`) and `Loop.rule` uses
    them as the gate itself."""
    calls = []

    @loop.rule
    def counts_calls(w):
        for _entity, _step in w.each("step"):
            pass
        calls.append(None)

    loop.tick()
    loop.tick()
    assert calls == [], "step has never existed -- the body never ran"

    _spawn_step(loop.world, 0)
    loop.tick()
    assert len(calls) == 1, "a step exists now -- it runs"
    loop.tick()
    assert len(calls) == 2, "populated now, so it runs every tick again"


def test_a_rule_reading_several_names_wakes_on_any_one_of_them(loop):
    seen = []

    @loop.rule
    def either(w):
        for _entity, _step in w.each("step"):
            pass
        for _entity, _ping in w.each("ping"):
            pass
        seen.append("either")

    loop.tick()
    assert seen == []

    e = loop.world.spawn()
    loop.world.mark(e, "ping")
    loop.tick()
    assert seen == ["either"], "ping alone wakes it -- step was never populated"


def test_a_rule_reacting_to_absence_is_never_gated_dormant(loop):
    calls = []

    @loop.rule
    def replenish(w):
        if not w.each("step"):
            _spawn_step(w, 0)
        calls.append(None)

    loop.tick()
    assert len(calls) == 1, "step has never existed -- still called, and it fired"
    assert loop.world.each("step") != []
    loop.tick()
    assert len(calls) == 2, "step exists now, but this is not gated on it either"


def test_a_rule_that_reads_nothing_runs_every_tick_regardless(loop):
    seen = []

    @loop.rule
    def always(w):
        seen.append(None)

    loop.tick()
    loop.tick()
    assert len(seen) == 2, "the fallback: called whether or not anything exists"


# --- priority: the one deliberate override of registration order --------


def test_higher_priority_runs_first_regardless_of_registration_order(loop):
    order = []
    loop.rule(lambda w: order.append("low"), name="low", priority=1)
    loop.rule(lambda w: order.append("high"), name="high", priority=10)
    loop.tick()
    assert order == ["high", "low"]


def test_equal_priority_including_the_default_keeps_registration_order(loop):
    order = []
    loop.rule(lambda w: order.append("first"), name="first")
    loop.rule(lambda w: order.append("second"), name="second", priority=0)
    loop.rule(lambda w: order.append("third"), name="third", priority=5)
    loop.tick()
    assert order == ["third", "first", "second"]


def test_priority_does_not_reorder_the_registry_itself(loop):
    loop.rule(lambda w: None, name="low", priority=1)
    loop.rule(lambda w: None, name="high", priority=10)
    assert [name for name, _ in loop.rules] == ["low", "high"]


def test_a_late_registered_high_priority_rule_still_runs_first(loop):
    order = []
    loop.tick()                                    # nothing registered yet
    loop.rule(lambda w: order.append("first-installed"), name="a", priority=0)
    loop.rule(lambda w: order.append("installed-later-but-important"),
               name="b", priority=100)
    loop.tick()
    assert order == ["installed-later-but-important", "first-installed"]


def test_a_rule_reading_SEVERAL_names_still_fires_ONCE_per_tick(loop):
    calls = []

    @loop.rule
    def watcher(w):
        w.each("step")
        w.each("ping")
        w.each("pong")
        calls.append(None)

    _spawn_step(loop.world, 0)
    e = loop.world.spawn()
    loop.world.mark(e, "ping")
    f = loop.world.spawn()
    loop.world.mark(f, "pong")
    loop.tick()
    assert len(calls) == 1, "one entry in self.rules, called once, full stop"


# --- unique names -------------------------------------------------------


def test_a_second_rule_with_the_same_explicit_name_is_refused(loop):
    loop.rule(lambda w: None, name="dup")
    with pytest.raises(ValueError):
        loop.rule(lambda w: None, name="dup")
    assert len(loop.rules) == 1


def test_a_second_rule_with_the_same_inferred_name_is_refused(loop):
    def flag_big(w):
        pass

    loop.rule(flag_big)
    with pytest.raises(ValueError):
        loop.rule(flag_big)
    assert len(loop.rules) == 1


def test_an_inferred_name_colliding_with_an_explicit_one_is_refused(loop):
    loop.rule(lambda w: None, name="test_loop.flag_big")

    with pytest.raises(ValueError):
        @loop.rule
        def flag_big(w):
            pass

    assert len(loop.rules) == 1


def test_after_tick_runs_between_ticks_not_at_the_end(loop):
    seen = []

    @loop.rule
    def countdown(w):
        for entity, step in w.each("step"):
            w.destroy(entity)
            if step > 0:
                _spawn_step(w, step - 1)

    _spawn_step(loop.world, 3)
    loop.run(after_tick=lambda: seen.append(
        [s for _, s in loop.world.each("step")]))
    assert seen == [[2], [1], [0], []]
