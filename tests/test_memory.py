"""`loopingrules.memory` -- short-term memory: promoting selected changes
out of the transient change log into durable `remembered` entities, and
forgetting them again past a tuned policy.

These pin what the system is FOR: a change becomes a durable entity a later
rule can read; the memory rules never remember themselves (no runaway);
retention is enforced by destroying, not by hiding; a forgotten change is
not silently re-remembered; and the rules are analyzable.

The pattern/lint tests that used `loopingrules_patterns`/`_calibration` are
deferred until those packages are ported (they live in the old component
world).
"""

from __future__ import annotations

from loopingrules import Loop, World, analyze, memory, save


_FIELDS = ("seq", "tick", "rule", "kind", "target", "types")


def _entries(loop):
    w = loop.world
    out = []
    for entity, _ in w.each(memory.REMEMBERED):
        out.append({field: w.get(entity, field) for field in _FIELDS})
    return out


# -- promotion ------------------------------------------------------------

def test_a_change_is_promoted_into_a_durable_remembered_entry():
    loop = Loop()
    memory.install(loop)
    entity = loop.world.spawn()
    loop.world.set(entity, "mark", 1)
    loop.run()
    entries = _entries(loop)
    assert entries
    spawns = [r for r in entries if r["kind"] == "spawn"]
    assert spawns, "the spawn should be remembered"
    assert spawns[0]["types"] == []       # a spawn's payload is empty
    assert spawns[0]["rule"] is None      # made by the test, not a rule


def test_a_promoted_entry_is_ordinary_durable_data():
    loop = Loop()
    memory.install(loop)
    loop.world.set(loop.world.spawn(), "mark", 7)
    loop.run()
    records = save.dump(loop.world)
    fresh = World()
    assert save.load(fresh, records) == []
    assert fresh.populated(memory.REMEMBERED)
    assert fresh.populated(memory.CURSOR)


def test_remembering_settles_and_does_not_duplicate():
    loop = Loop()
    memory.install(loop)
    loop.world.set(loop.world.spawn(), "mark", 1)
    assert loop.run().hot == []
    first = len(_entries(loop))
    assert loop.run().hot == []
    assert len(_entries(loop)) == first


def test_the_memory_rules_never_remember_themselves():
    loop = Loop()
    memory.install(loop)
    loop.world.set(loop.world.spawn(), "mark", 1)
    loop.run()
    for entry in _entries(loop):
        assert entry["rule"] not in ("memory.remember", "memory.forget")
        assert "remembered" not in entry["types"]
        assert "memory_cursor" not in entry["types"]


def test_install_time_seeding_is_not_replayed_as_history():
    loop = Loop()
    memory.install(loop)
    loop.run()
    assert _entries(loop) == []


# -- policy filters -------------------------------------------------------

def test_policy_kinds_admits_only_those_kinds():
    loop = Loop()
    memory.install(loop, {"kinds": ["set"]})
    entity = loop.world.spawn()              # spawn: not admitted
    loop.world.set(entity, "mark", 1)        # set: admitted
    loop.run()
    assert {r["kind"] for r in _entries(loop)} == {"set"}


# -- forgetting -----------------------------------------------------------

def test_max_entries_forgets_the_oldest_and_keeps_the_newest():
    loop = Loop()
    memory.install(loop, {"max_entries": 2})
    marks = []
    for i in range(5):
        marks.append(loop.world.spawn())
        loop.world.set(marks[-1], "mark", i)
    assert loop.run().hot == []
    kept = sorted(r["seq"] for r in _entries(loop))
    assert len(kept) == 2
    mark_ids = {mark.id for mark in marks}
    mark_seqs = sorted(c.seq for c in loop.world.changes()
                       if c.target in mark_ids)
    assert len(mark_seqs) == 10              # each mark is a spawn + a set
    assert kept == mark_seqs[-2:]


def test_a_forgotten_change_is_not_remembered_again():
    loop = Loop()
    memory.install(loop, {"max_entries": 1})
    for i in range(4):
        loop.world.set(loop.world.spawn(), "mark", i)
    loop.run()
    assert len(_entries(loop)) == 1
    assert loop.run().hot == []              # and it stays settled
    assert len(_entries(loop)) == 1


def test_max_per_target_caps_entries_for_one_target():
    loop = Loop()
    memory.install(loop, {"max_per_target": 1})
    target = loop.world.spawn()
    loop.world.set(target, "mark", 0)
    loop.world.set(target, "mark", 1)
    loop.world.set(target, "mark", 2)
    loop.run()
    on_target = [r for r in _entries(loop) if r["target"] == target.id]
    assert len(on_target) == 1
    assert on_target[0]["seq"] == max(
        c.seq for c in loop.world.changes() if c.target == target.id)


# -- abstention -----------------------------------------------------------

def test_both_rules_abstain_without_the_marker_or_the_policy():
    loop = Loop()
    loop.world.set(loop.world.spawn(), "mark", 1)
    loop.rule(memory.remember)
    loop.rule(memory.forget)
    loop.run()
    assert _entries(loop) == []


# -- analysis -------------------------------------------------------------

def test_analyze_sees_the_memory_rules_rather_than_refusing_them():
    remembered = analyze.analyze(memory.remember)
    assert "memory_policy" in remembered.reads
    assert "memory" in remembered.reads
    assert "remembered" in remembered.writes
    forgetting = analyze.analyze(memory.forget)
    assert "remembered" in forgetting.reads
    assert forgetting.destroys
