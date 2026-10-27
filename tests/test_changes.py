"""`loopingrules`' change log -- `World.changes` / `World.recent`. These
tests pin what the log is FOR: every real change is recorded with its kind,
target, payload, tick and acting rule; a no-op is not; a rule reading the
log sees only changes from BEFORE its own tick (so it cannot react to
itself); it is bounded only if asked; and `analyze` attributes the
`changed=` type so a memory-reading rule keeps a dormancy gate.
"""

import dataclasses

from examples import cards
from loopingrules import Change, Loop, World
from loopingrules import analyze
from loopingrules_calibration import Scenario, replay


@dataclasses.dataclass(frozen=True)
class A:
    n: int


@dataclasses.dataclass(frozen=True)
class B:
    n: int


# -- what gets logged -----------------------------------------------------

def test_spawn_and_attach_are_logged():
    world = World()
    entity = world.spawn(A(1))
    kinds = [(change.kind, change.target) for change in world.changes()]
    assert ("spawn", entity.id) in kinds
    assert ("attach", entity.id) in kinds
    attach = [c for c in world.changes() if c.kind == "attach"][0]
    assert attach.payload == (A(1),)


def test_replace_detach_remove_destroy_are_logged():
    world = World()
    entity = world.spawn(A(1), B(2))
    world.replace(entity, A(9))
    world.detach(entity, B)
    world.remove(entity, A(9))
    world.destroy(entity)
    by_kind = {change.kind: change for change in world.changes()}
    assert set(by_kind) >= {"spawn", "attach", "replace", "detach",
                            "remove", "destroy"}
    assert by_kind["replace"].payload == (A(9),)   # the value that replaced
    assert by_kind["detach"].payload == (B(2),)    # the value removed
    assert by_kind["remove"].payload == (A(9),)
    assert by_kind["destroy"].target == entity.id


def test_a_no_op_attach_is_not_logged():
    world = World()
    entity = world.spawn(A(1))
    before = len(world.changes())
    world.attach(entity, A(1))          # equal to what is already there
    assert len(world.changes()) == before


# -- provenance -----------------------------------------------------------

def test_install_writes_carry_no_rule_and_tick_zero():
    loop = Loop()
    loop.world.spawn(A(1))
    last = loop.world.changes()[-1]
    assert last.rule is None
    assert last.tick == 0


def _stamp_rule(w):
    for entity, a in w.each(A):
        w.attach(entity, B(a.n))


def test_a_rules_change_carries_its_name_and_tick():
    loop = Loop()
    loop.world.spawn(A(1))
    loop.rule(_stamp_rule, name="stamp")
    loop.run()
    stamped = [c for c in loop.world.changes()
               if c.kind == "attach" and isinstance(c.payload[0], B)]
    assert stamped
    assert stamped[0].rule == "stamp"
    assert stamped[0].tick >= 1


# -- a rule sees only the past -------------------------------------------

def test_a_rule_sees_only_changes_before_its_own_tick():
    loop = Loop()
    loop.world.spawn(A(1))
    seen = []

    def watch(w):
        seen.append(w.changes())
        for entity, a in w.each(A):
            w.attach(entity, B(a.n))

    loop.rule(watch, name="watch")
    loop.run()
    first = seen[0]
    assert first                                  # it saw the install writes
    assert all(change.tick == 0 for change in first)   # ... and nothing later
    assert all(change.rule is None for change in first)
    # the rule's own write IS in the settled log, just not visible to it
    assert any(change.rule == "watch" for change in loop.world.changes())


# -- filters --------------------------------------------------------------

def test_filters_combine():
    world = World()
    entity = world.spawn(A(1))
    world.attach(entity, B(2))
    assert all(c.kind == "attach" for c in world.changes(kind="attach"))
    assert all(c.target == entity.id for c in world.changes(target=entity))
    attaches_on_a = world.changes(changed=A)
    assert attaches_on_a
    assert all(any(isinstance(p, A) for p in c.payload)
               for c in attaches_on_a)
    first_seq = world.changes()[0].seq
    assert all(c.seq > first_seq for c in world.changes(since=first_seq))
    assert world.changes(kind="nonsense") == ()


def test_recent_returns_the_tail():
    world = World()
    world.spawn(A(1))
    world.spawn(A(2))
    assert world.recent(2) == world.changes()[-2:]
    assert world.recent(0) == ()


def test_capacity_bounds_the_log():
    loop = Loop(capacity=2)
    loop.world.spawn(A(1))
    loop.world.spawn(A(2))
    loop.world.spawn(A(3))
    assert len(loop.world.changes()) == 2


# -- analyze --------------------------------------------------------------

def _reads_changed(w):
    for change in w.changes(changed=A):
        pass


def _reads_no_type(w):
    return w.recent(3)


def test_analyze_attributes_the_changed_type_as_a_read():
    analysis = analyze.analyze(_reads_changed)
    assert analysis.reads == {A}
    assert analysis.writes == set()
    assert not analysis.destroys


def test_analyze_treats_a_typeless_log_read_as_no_read():
    analysis = analyze.analyze(_reads_no_type)
    assert analysis.reads == set()


# -- the calibration kit sees the log ------------------------------------

def test_a_replay_carries_the_change_log():
    trace = replay(Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",)),
                   cards.install)
    assert trace.changes
    by_rule = {change.rule for change in trace.changes if change.rule}
    assert any(name.startswith("cards.") for name in by_rule)
    assert any(change.rule is None for change in trace.changes)  # install
