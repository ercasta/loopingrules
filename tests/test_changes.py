"""`loopingrules`' change log -- `World.changes` / `World.recent`. These
tests pin what the log is FOR: every real change is recorded with its kind,
target, deltas, tick and acting rule; a no-op is not; a rule reading the log
sees only changes from BEFORE its own tick; it is bounded only if asked; and
`analyze` attributes the `changed=` attribute name so a memory-reading rule
keeps a dormancy gate.
"""

from __future__ import annotations

from examples import cards
from loopingrules import Change, Loop, World, analyze
from loopingrules.world import MISSING
from loopingrules_calibration import Scenario, replay


# -- what gets logged ---------------------------------------------------

def test_spawn_and_a_set_are_logged():
    world = World()
    entity = world.spawn()
    world.set(entity, "a", 1)
    kinds = [(change.kind, change.target) for change in world.changes()]
    assert ("spawn", entity.id) in kinds
    assert ("set", entity.id) in kinds
    change = [c for c in world.changes() if c.kind == "set"][0]
    assert change.payload == (("a", MISSING, 1),)


def test_replace_unset_remove_destroy_are_logged():
    world = World()
    entity = world.spawn()
    world.set(entity, "a", 1)
    world.set(entity, "a", 9)              # replace
    world.set(entity, "b", 2)
    world.unset(entity, "b")               # detach
    world.set(entity, "tags", ["x"])       # a list
    world.remove(entity, "tags", "x")      # remove one item
    world.destroy(entity)
    by_kind = {change.kind: change for change in world.changes()}
    assert set(by_kind) >= {"spawn", "set", "unset", "remove", "destroy"}
    assert by_kind["remove"].payload[0][0] == "tags"     # the name that changed
    assert by_kind["destroy"].target == entity.id
    assert ("a", 9, MISSING) in by_kind["destroy"].payload


def test_a_no_op_set_is_not_logged():
    world = World()
    entity = world.spawn()
    world.set(entity, "a", 1)
    before = len(world.changes())
    world.set(entity, "a", 1)              # equal to what is already there
    assert len(world.changes()) == before


# -- provenance ---------------------------------------------------------

def test_install_writes_carry_no_rule_and_tick_zero():
    loop = Loop()
    loop.world.set(loop.world.spawn(), "a", 1)
    last = loop.world.changes()[-1]
    assert last.rule is None
    assert last.tick == 0


def _stamp_rule(w):
    for entity, a in w.each("a"):
        w.set(entity, "b", a)


def test_a_rules_change_carries_its_name_and_tick():
    loop = Loop()
    loop.world.set(loop.world.spawn(), "a", 1)
    loop.rule(_stamp_rule, name="stamp")
    loop.run()
    stamped = [c for c in loop.world.changes()
               if c.kind == "set" and c.payload[0][0] == "b"]
    assert stamped
    assert stamped[0].rule == "stamp"
    assert stamped[0].tick >= 1


# -- a rule sees only the past ------------------------------------------

def test_a_rule_sees_only_changes_before_its_own_tick():
    loop = Loop()
    loop.world.set(loop.world.spawn(), "a", 1)
    seen = []

    def watch(w):
        seen.append(w.changes())
        for entity, a in w.each("a"):
            w.set(entity, "b", a)

    loop.rule(watch, name="watch")
    loop.run()
    first = seen[0]
    assert first
    assert all(change.tick == 0 for change in first)
    assert all(change.rule is None for change in first)
    assert any(change.rule == "watch" for change in loop.world.changes())


# -- filters ------------------------------------------------------------

def test_filters_combine():
    world = World()
    entity = world.spawn()
    world.set(entity, "a", 1)
    world.set(entity, "b", 2)
    assert all(c.kind == "set" for c in world.changes(kind="set"))
    assert all(c.target == entity.id for c in world.changes(target=entity))
    on_a = world.changes(changed="a")
    assert on_a
    assert all(any(delta[0] == "a" for delta in c.payload) for c in on_a)
    first_seq = world.changes()[0].seq
    assert all(c.seq > first_seq for c in world.changes(since=first_seq))
    assert world.changes(kind="nonsense") == ()


def test_recent_returns_the_tail():
    world = World()
    world.set(world.spawn(), "a", 1)
    world.set(world.spawn(), "a", 2)
    assert world.recent(2) == world.changes()[-2:]
    assert world.recent(0) == ()


def test_capacity_bounds_the_log():
    loop = Loop(capacity=2)
    loop.world.set(loop.world.spawn(), "a", 1)
    loop.world.set(loop.world.spawn(), "a", 2)
    loop.world.set(loop.world.spawn(), "a", 3)
    assert len(loop.world.changes()) == 2


# -- analyze ------------------------------------------------------------

def _reads_changed(w):
    for change in w.changes(changed="a"):
        pass


def _reads_no_name(w):
    return w.recent(3)


def test_analyze_attributes_the_changed_name_as_a_read():
    analysis = analyze.analyze(_reads_changed)
    assert analysis.reads == {"a"}
    assert analysis.writes == set()
    assert not analysis.destroys


def test_analyze_treats_a_nameless_log_read_as_no_read():
    analysis = analyze.analyze(_reads_no_name)
    assert analysis.reads == set()


# -- the calibration kit sees the log -----------------------------------

def test_a_replay_carries_the_change_log():
    trace = replay(
        Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",)),
        cards.install)
    assert trace.changes
    by_rule = {change.rule for change in trace.changes if change.rule}
    assert any(name.startswith("cards.") for name in by_rule)
    assert any(change.rule is None for change in trace.changes)  # install
