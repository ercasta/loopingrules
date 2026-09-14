"""`loopingrules.memory` -- `Focus`/`Memory`/`MemoryEntry` and the one
rule that connects them, `track_focus`. What's pinned: the trail only
grows while a `Memory` singleton exists at all; a genuine gain of
`Focus` is recorded once, not once per tick it stays attached; a
detach-then-reattach (even back to an identical value) is a SECOND
gain, not silently skipped; and `most_recent`/`most_intense` read that
trail the way this module's own docstring claims they do.
"""

from loopingrules import memory
from loopingrules.world import World


def test_track_focus_does_nothing_without_a_memory_singleton():
    w = World()
    entity = w.spawn()
    w.attach(entity, memory.Focus())
    memory.track_focus(w)
    assert memory.trail(w) == []


def test_a_fresh_focus_is_recorded_once():
    w = World()
    w.spawn(memory.Memory())
    entity = w.spawn()
    w.attach(entity, memory.Focus(intensity=0.5))
    memory.track_focus(w)
    memory.track_focus(w)   # a second tick, nothing changed -- still one entry
    trail = memory.trail(w)
    assert len(trail) == 1
    assert trail[0] == memory.MemoryEntry(entity.id, 0.5, 0)


def test_two_different_entities_focused_in_turn_both_land_in_the_trail_in_order():
    w = World()
    w.spawn(memory.Memory())
    first = w.spawn()
    second = w.spawn()
    w.attach(first, memory.Focus())
    memory.track_focus(w)
    w.attach(second, memory.Focus())
    memory.track_focus(w)
    trail = memory.trail(w)
    assert [entry.entity for entry in trail] == [first.id, second.id]
    assert [entry.seq for entry in trail] == [0, 1]


def test_losing_and_regaining_focus_records_a_second_entry_even_at_the_same_value():
    w = World()
    w.spawn(memory.Memory())
    entity = w.spawn()
    w.attach(entity, memory.Focus(intensity=0.9))
    memory.track_focus(w)
    w.detach(entity, memory.Focus)
    memory.track_focus(w)   # the loss itself: no new entry, just clears bookkeeping
    assert len(memory.trail(w)) == 1
    w.attach(entity, memory.Focus(intensity=0.9))   # identical value, but a fresh gain
    memory.track_focus(w)
    trail = memory.trail(w)
    assert len(trail) == 2
    assert trail[1] == memory.MemoryEntry(entity.id, 0.9, 1)


def test_most_recent_is_none_on_an_empty_trail():
    w = World()
    w.spawn(memory.Memory())
    assert memory.most_recent(w) is None


def test_most_recent_is_the_last_gain_not_the_last_tick():
    w = World()
    w.spawn(memory.Memory())
    first = w.spawn()
    second = w.spawn()
    w.attach(first, memory.Focus())
    memory.track_focus(w)
    w.attach(second, memory.Focus())
    memory.track_focus(w)
    assert memory.most_recent(w).entity == second.id


def test_most_intense_excludes_entries_with_no_intensity_and_breaks_ties_by_recency():
    w = World()
    w.spawn(memory.Memory())
    quiet = w.spawn()
    tied_early = w.spawn()
    tied_late = w.spawn()
    w.attach(quiet, memory.Focus())               # intensity=None -- never a candidate
    memory.track_focus(w)
    w.attach(tied_early, memory.Focus(intensity=0.7))
    memory.track_focus(w)
    w.attach(tied_late, memory.Focus(intensity=0.7))
    memory.track_focus(w)
    winner = memory.most_intense(w)
    assert winner.entity == tied_late.id


def test_most_intense_is_none_when_nothing_in_range_ever_carried_one():
    w = World()
    w.spawn(memory.Memory())
    entity = w.spawn()
    w.attach(entity, memory.Focus())
    memory.track_focus(w)
    assert memory.most_intense(w) is None


def test_most_intense_within_limits_how_far_back_it_looks():
    w = World()
    w.spawn(memory.Memory())
    strong_but_old = w.spawn()
    weak_but_recent = w.spawn()
    w.attach(strong_but_old, memory.Focus(intensity=0.9))
    memory.track_focus(w)
    w.attach(weak_but_recent, memory.Focus(intensity=0.1))
    memory.track_focus(w)
    assert memory.most_intense(w).entity == strong_but_old.id
    assert memory.most_intense(w, within=1).entity == weak_but_recent.id
