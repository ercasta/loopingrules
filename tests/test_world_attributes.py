"""The attribute seam (D8, Phase S): `loopingrules.world`, pinned.

This is the new core in isolation -- entities and attributes, the four
kinds' verbs, references and flat lists, the change log of deltas. It does
not touch `loop`, `analyze` or any example; those are ported onto this
seam in the order `docs/plan-attributes.md` gives, and get their own tests
as they land.
"""

from __future__ import annotations

import pytest

from loopingrules.world import MISSING, World


# -- entity and attribute -------------------------------------------------

def test_spawn_gives_a_bare_entity():
    w = World()
    e = w.spawn()
    assert e.alive
    assert len(w) == 1
    assert w.entities() == [e]
    assert w.attributes(e) == {}


def test_set_then_get_a_scalar():
    w = World()
    e = w.spawn()
    w.set(e, "cash", 100)
    assert w.get(e, "cash") == 100
    assert w.has(e, "cash")
    assert not w.has(e, "debt")
    assert w.attributes(e) == {"cash": 100}


def test_get_default_distinguishes_absent_from_none():
    w = World()
    e = w.spawn()
    assert w.get(e, "mood") is None          # absent
    assert not w.has(e, "mood")
    w.set(e, "mood", None)                    # present, holds None
    assert w.get(e, "mood") is None
    assert w.has(e, "mood")
    assert w.get(e, "mood", "?") is None      # present, so the default is not used
    w.unset(e, "mood")
    assert w.get(e, "mood", "?") == "?"       # absent, so it is


def test_natural_reference_is_stored_as_a_plain_id():
    w = World()
    a, b = w.spawn(), w.spawn()
    w.set(a, "friend", b)
    assert w.get(a, "friend") == b.id        # a plain int, not a handle
    assert w.entity(w.get(a, "friend")) == b


def test_reference_inside_a_list_is_lowered_too():
    w = World()
    a, b, c = w.spawn(), w.spawn(), w.spawn()
    w.set(a, "friends", [b, c])
    assert w.get(a, "friends") == [b.id, c.id]


# -- the value model: no dict, no nesting ---------------------------------

def test_a_dict_is_not_a_value():
    w = World()
    e = w.spawn()
    with pytest.raises(TypeError):
        w.set(e, "size", {"bytes": 17})


def test_a_list_may_not_hold_a_list():
    w = World()
    e = w.spawn()
    with pytest.raises(TypeError):
        w.set(e, "grid", [[1, 2], [3, 4]])


def test_a_tuple_is_accepted_and_stored_as_a_list():
    w = World()
    e = w.spawn()
    w.set(e, "tags", ("a", "b"))
    assert w.get(e, "tags") == ["a", "b"]


# -- the verbs, and idempotence (what settling rests on) ------------------

def test_re_set_an_equal_value_is_not_a_change():
    w = World()
    e = w.spawn()
    w.set(e, "cash", 100)
    before = w.revision
    w.set(e, "cash", 100)
    assert w.revision == before
    w.set(e, "cash", 90)
    assert w.revision == before + 1


def test_set_replaces_the_whole_collection():
    w = World()
    e = w.spawn()
    w.set(e, "tags", ["a", "b"])
    w.set(e, "tags", ["c"])
    assert w.get(e, "tags") == ["c"]


def test_add_is_deduped_and_idempotent():
    w = World()
    e = w.spawn()
    assert w.add(e, "tags", "a") is True
    before = w.revision
    assert w.add(e, "tags", "a") is False
    assert w.revision == before
    w.add(e, "tags", "b")
    assert w.get(e, "tags") == ["a", "b"]    # insertion order kept


def test_append_keeps_duplicates_and_always_changes():
    w = World()
    e = w.spawn()
    w.append(e, "log", "x")
    before = w.revision
    w.append(e, "log", "x")
    assert w.revision == before + 1
    assert w.get(e, "log") == ["x", "x"]


def test_remove_takes_one_occurrence_and_pop_returns_the_item():
    w = World()
    e = w.spawn()
    w.set(e, "tags", ["a", "b", "a"])
    assert w.remove(e, "tags", "a") is True
    assert w.get(e, "tags") == ["b", "a"]    # only the first occurrence went
    assert w.remove(e, "tags", "z") is False
    assert w.pop(e, "tags") == "a"           # last by default
    assert w.get(e, "tags") == ["b"]


def test_a_collection_verb_refuses_a_scalar_slot():
    w = World()
    e = w.spawn()
    w.set(e, "cash", 5)
    with pytest.raises(TypeError):
        w.add(e, "cash", 1)


def test_pop_from_empty_raises_and_from_absent_returns_none():
    w = World()
    e = w.spawn()
    assert w.pop(e, "log") is None
    w.set(e, "log", [])
    with pytest.raises(IndexError):
        w.pop(e, "log")


def test_mark_and_unmark_are_a_flag():
    w = World()
    e = w.spawn()
    w.mark(e, "stale")
    before = w.revision
    w.mark(e, "stale")
    assert w.revision == before              # re-mark is not a change
    assert w.has(e, "stale")
    assert w.get(e, "stale") is True
    assert w.unmark(e, "stale") is True
    assert w.unmark(e, "stale") is False
    assert not w.has(e, "stale")


# -- queries: one row per entity, never a cross product -------------------

def test_each_is_one_row_per_entity_and_a_list_is_the_row_value():
    w = World()
    a, b = w.spawn(), w.spawn()
    w.set(a, "card", "dragon")
    w.set(a, "tags", ["mine", "rare"])
    w.set(b, "card", "phoenix")
    rows = w.each("card", "tags")
    assert rows == [(a, "dragon", ["mine", "rare"])]


def test_each_without_excludes_carriers():
    w = World()
    a, b = w.spawn(), w.spawn()
    w.set(a, "wish", 1)
    w.set(b, "wish", 2)
    w.mark(b, "approved")
    assert w.each("wish", without="approved") == [(a, 1)]


def test_the_and_all_read_by_name_across_the_world():
    w = World()
    a, b = w.spawn(), w.spawn()
    w.set(a, "policy", 0.1)
    w.set(b, "policy", 0.2)
    assert w.the("policy") == 0.1            # oldest carrier
    assert w.all("policy") == [(a, 0.1), (b, 0.2)]
    assert w.populated("policy")
    assert not w.populated("missing")


# -- the change log: kinds and attribute deltas ---------------------------

def test_a_write_records_a_delta_naming_the_attribute():
    w = World()
    e = w.spawn()
    w.set(e, "cash", 100)
    change = w.changes(kind="set")[-1]
    assert change.target == e.id
    assert change.payload == (("cash", MISSING, 100),)


def test_changes_filters_by_attribute_name():
    w = World()
    e = w.spawn()
    w.set(e, "cash", 1)
    w.set(e, "debt", 2)
    assert len(w.changes(changed="cash")) == 1
    assert w.changes(changed="cash")[0].payload[0][0] == "cash"
    assert w.changes(changed="nothing") == ()


def test_destroy_records_every_slot_that_went_with_the_entity():
    w = World()
    e = w.spawn()
    w.set(e, "cash", 1)
    w.set(e, "name", "x")
    assert w.destroy(e) is True
    assert not e.alive
    assert not w.has(e.id, "cash")
    change = w.changes(kind="destroy")[-1]
    assert ("cash", 1, MISSING) in change.payload
    assert ("name", "x", MISSING) in change.payload


def test_a_no_op_is_in_neither_the_log_nor_the_revision():
    w = World()
    e = w.spawn()
    w.set(e, "cash", 1)
    before_rev, before_seq = w.revision, len(w.changes())
    w.set(e, "cash", 1)
    assert w.revision == before_rev
    assert len(w.changes()) == before_seq


# -- transience is a name -------------------------------------------------

def test_purge_transient_drops_only_the_named_slots():
    w = World()
    w.transient = {"scratch"}
    a, b = w.spawn(), w.spawn()
    w.set(a, "scratch", 1)
    w.set(b, "scratch", 2)
    w.set(a, "keep", 3)
    assert w.purge_transient() == 2
    assert not w.populated("scratch")
    assert w.get(a, "keep") == 3
    assert w.purge_transient() == 0
    assert w.changes(kind="purge")
