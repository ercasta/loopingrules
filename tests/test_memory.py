"""`loopingrules.memory` -- short-term memory: promoting selected changes
out of the transient change log into durable `Remembered` components, and
forgetting them again past a tuned `MemoryPolicy`.

These pin what the system is FOR: a change becomes a durable component a
later rule can read; the memory rules never remember themselves (no
runaway); retention is enforced by destroying, not by hiding; a forgotten
change is not silently re-remembered; the rules are analyzable and the
declared tunable surface (in `loopingrules_patterns.memory`) is collected by
`knobs` and lints clean.
"""

import dataclasses

from loopingrules import Loop, World, analyze, memory, save
from loopingrules_calibration import declared, knobs, lint
from loopingrules_patterns import memory as memory_pattern


@dataclasses.dataclass(frozen=True)
class Mark:
    n: int


def _entries(loop):
    return loop.world.all(memory.Remembered)


# -- promotion ------------------------------------------------------------

def test_a_change_is_promoted_into_a_durable_remembered_entry():
    loop = Loop()
    memory.install(loop)
    loop.world.spawn(Mark(1))
    loop.run()
    entries = _entries(loop)
    assert entries
    spawns = [r for _entity, r in entries if r.kind == "spawn"]
    assert spawns, "the Mark spawn should be remembered"
    assert spawns[0].types == ()          # a spawn's payload is empty
    assert spawns[0].rule is None         # made by the test, not a rule


def test_a_promoted_entry_is_ordinary_durable_data():
    loop = Loop()
    memory.install(loop)
    loop.world.spawn(Mark(7))
    loop.run()
    records = save.dump(loop.world)
    fresh = World()
    assert save.load(fresh, records) == []
    assert fresh.populated(memory.Remembered)
    assert fresh.populated(memory.MemoryCursor)


def test_remembering_settles_and_does_not_duplicate():
    loop = Loop()
    memory.install(loop)
    loop.world.spawn(Mark(1))
    assert loop.run().hot == []
    first = len(_entries(loop))
    assert loop.run().hot == []
    assert len(_entries(loop)) == first


def test_the_memory_rules_never_remember_themselves():
    loop = Loop()
    memory.install(loop)
    loop.world.spawn(Mark(1))
    loop.run()
    for _entity, entry in _entries(loop):
        assert entry.rule not in ("memory.remember", "memory.forget")
        assert "Remembered" not in entry.types
        assert "MemoryCursor" not in entry.types


def test_install_time_seeding_is_not_replayed_as_history():
    loop = Loop()
    memory.install(loop)
    loop.run()
    assert _entries(loop) == []


# -- policy filters -------------------------------------------------------

def test_policy_kinds_admits_only_those_kinds():
    loop = Loop()
    memory.install(loop, memory.MemoryPolicy(kinds=("attach",)))
    entity = loop.world.spawn(Mark(0))       # spawn: not admitted
    loop.world.attach(entity, Mark(1))       # attach: admitted
    loop.run()
    assert {r.kind for _entity, r in _entries(loop)} == {"attach"}


# -- forgetting -----------------------------------------------------------

def test_max_entries_forgets_the_oldest_and_keeps_the_newest():
    loop = Loop()
    memory.install(loop, memory.MemoryPolicy(max_entries=2))
    marks = [loop.world.spawn(Mark(i)) for i in range(5)]
    assert loop.run().hot == []
    kept = sorted(r.seq for _entity, r in _entries(loop))
    assert len(kept) == 2
    # the two newest of the changes the five spawns produced survive -- a
    # `spawn(Mark(...))` records both a spawn and an attach, so there are
    # ten such changes, not five.
    mark_ids = {mark.id for mark in marks}
    mark_seqs = sorted(c.seq for c in loop.world.changes()
                       if c.target in mark_ids)
    assert len(mark_seqs) == 10
    assert kept == mark_seqs[-2:]


def test_a_forgotten_change_is_not_remembered_again():
    loop = Loop()
    memory.install(loop, memory.MemoryPolicy(max_entries=1))
    for i in range(4):
        loop.world.spawn(Mark(i))
    loop.run()
    assert len(_entries(loop)) == 1
    assert loop.run().hot == []              # and it stays settled
    assert len(_entries(loop)) == 1


def test_max_per_target_caps_entries_for_one_target():
    loop = Loop()
    memory.install(loop, memory.MemoryPolicy(max_per_target=1))
    target = loop.world.spawn(Mark(0))
    loop.world.attach(target, Mark(1))
    loop.world.attach(target, Mark(2))
    loop.run()
    on_target = [r for _entity, r in _entries(loop) if r.target == target.id]
    assert len(on_target) == 1
    assert on_target[0].seq == max(
        c.seq for c in loop.world.changes() if c.target == target.id)


# -- abstention -----------------------------------------------------------

def test_both_rules_abstain_without_the_marker_or_the_policy():
    loop = Loop()
    loop.world.spawn(Mark(1))
    loop.rule(memory.remember)
    loop.rule(memory.forget)
    loop.run()
    assert _entries(loop) == []


# -- analysis and the declared surface ------------------------------------

def test_analyze_sees_the_memory_rules_rather_than_refusing_them():
    remembered = analyze.analyze(memory.remember)
    assert memory.MemoryPolicy in remembered.reads
    assert memory.Memory in remembered.reads
    assert memory.Remembered in remembered.writes
    forgetting = analyze.analyze(memory.forget)
    assert memory.Remembered in forgetting.reads
    assert forgetting.destroys


def test_the_pattern_layer_declares_the_surface_on_the_core_rules():
    assert memory_pattern.remember is memory.remember
    assert memory_pattern.forget is memory.forget
    names = {knob.name for knob in declared(memory.remember)}
    assert names == {"MemoryPolicy.max_entries", "MemoryPolicy.max_per_target"}


def test_knobs_collects_the_surface_from_an_installed_loop():
    loop = Loop()
    memory_pattern.install(loop)
    collected = {knob.name for knob in knobs(loop)}
    assert {"MemoryPolicy.max_entries", "MemoryPolicy.max_per_target"} <= collected


def test_the_memory_rules_lint_clean():
    report = lint((memory.remember, memory.forget))
    assert report.clean
    assert report.checked
    assert not report.findings
    assert not report.unlintable
