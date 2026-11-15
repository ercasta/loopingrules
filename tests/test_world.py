"""The world on the component substrate (ADR-10): entities carry named
components; a component is a bag of fields; a fieldless component is a tag.
"""

from __future__ import annotations

import pytest

from loopingrules.world import MISSING, World


def _world():
    return World()


# -- entity, and the value model ------------------------------------------

def test_spawn_gives_a_bare_entity():
    w = _world()
    e = w.spawn()
    assert e.alive and len(w) == 1 and w.entities() == [e]
    assert w.components(e) == {}


def test_a_tuple_is_accepted_and_stored_as_a_list():
    w = _world()
    e = w.spawn()
    w.set(e, "listing", "tags", ("a", "b"))
    assert w.get(e, "listing", "tags") == ["a", "b"]


def test_remove_takes_one_occurrence():
    w = _world()
    e = w.spawn()
    w.set(e, "listing", "tags", ["a", "b", "a"])
    assert w.remove(e, "listing", "tags", "a") is True
    assert w.get(e, "listing", "tags") == ["b", "a"]     # only the first went
    assert w.remove(e, "listing", "tags", "z") is False


def test_pop_from_empty_raises_and_from_absent_returns_none():
    w = _world()
    e = w.spawn()
    assert w.pop(e, "log", "line") is None
    w.set(e, "log", "line", [])
    with pytest.raises(IndexError):
        w.pop(e, "log", "line")


def test_a_no_op_is_in_neither_the_log_nor_the_revision():
    w = _world()
    e = w.spawn()
    w.set(e, "trader", "cash", 1)
    before_rev, before_seq = w.revision, len(w.changes())
    w.set(e, "trader", "cash", 1)
    assert w.revision == before_rev and len(w.changes()) == before_seq


def test_re_mark_is_not_a_change():
    w = _world()
    e = w.spawn()
    w.mark(e, "done")
    before = w.revision
    w.mark(e, "done")
    assert w.revision == before


# -- a component is a named bag of fields ---------------------------------

def test_set_and_get_a_field():
    w = _world()
    e = w.spawn()
    w.set(e, "listing", "price", 10)
    assert w.get(e, "listing", "price") == 10
    assert w.components(e) == {"listing": {"price": 10}}


def test_a_field_absent_is_the_default_and_has_distinguishes():
    w = _world()
    e = w.spawn()
    assert w.get(e, "listing", "price", 0) == 0
    assert not w.has(e, "listing", "price")
    w.set(e, "listing", "price", None)
    assert w.get(e, "listing", "price", 0) is None
    assert w.has(e, "listing", "price")


def test_one_component_per_name_and_one_field_per_name():
    w = _world()
    e = w.spawn()
    w.set(e, "listing", "price", 10)
    w.set(e, "listing", "price", 20)              # same slot, second write wins
    assert w.components(e) == {"listing": {"price": 20}}


def test_resetting_an_equal_value_is_not_a_change():
    w = _world()
    e = w.spawn()
    w.set(e, "listing", "price", 10)
    before = w.revision
    w.set(e, "listing", "price", 10)
    assert w.revision == before


def test_a_tag_is_a_fieldless_component():
    w = _world()
    e = w.spawn()
    w.mark(e, "done")
    assert w.has(e, "done")
    assert w.components(e) == {"done": {}}
    assert w.unmark(e, "done") is True
    assert not w.has(e, "done")


# -- kinds, enforced as SHAPE only ---------------------------------------

def test_add_is_deduped_and_insertion_ordered():
    w = _world()
    e = w.spawn()
    assert w.add(e, "listing", "tags", "a") is True
    assert w.add(e, "listing", "tags", "b") is True
    assert w.add(e, "listing", "tags", "a") is False
    assert w.get(e, "listing", "tags") == ["a", "b"]
    assert w.remove(e, "listing", "tags", "a") is True
    assert w.get(e, "listing", "tags") == ["b"]


def test_append_keeps_duplicates_and_always_changes():
    w = _world()
    e = w.spawn()
    w.append(e, "log", "line", "x")
    before = w.revision
    w.append(e, "log", "line", "x")
    assert w.get(e, "log", "line") == ["x", "x"] and w.revision != before


def test_pop_removes_and_returns():
    w = _world()
    e = w.spawn()
    w.set(e, "log", "line", [1, 2, 3])
    assert w.pop(e, "log", "line") == 3
    assert w.pop(e, "log", "line", 0) == 1
    assert w.get(e, "log", "line") == [2]


def test_add_wants_a_list_field():
    w = _world()
    e = w.spawn()
    w.set(e, "listing", "price", 10)
    with pytest.raises(TypeError):
        w.add(e, "listing", "price", 1)


def test_a_value_must_be_a_scalar_a_ref_or_a_flat_list():
    w = _world()
    e = w.spawn()
    with pytest.raises(TypeError):
        w.set(e, "listing", "meta", {"a": 1})
    with pytest.raises(TypeError):
        w.set(e, "listing", "meta", [["nested"]])


def test_a_reference_is_stored_as_its_plain_id():
    w = _world()
    a, b = w.spawn(), w.spawn()
    w.set(a, "listing", "card", b)
    assert w.get(a, "listing", "card") == b.id


# -- queries --------------------------------------------------------------

def test_each_over_a_component_and_its_fields():
    w = _world()
    a, b = w.spawn(), w.spawn()
    w.set(a, "card", "name", "x")
    w.set(a, "card", "value", 1)
    w.set(b, "card", "name", "y")               # no value
    rows = w.each("card", "name", "value")
    assert rows == [(a, "x", 1)]


def test_each_without_excludes_a_component():
    w = _world()
    a, b = w.spawn(), w.spawn()
    w.set(a, "trader", "cash", 10)
    w.set(b, "trader", "cash", 20)
    w.mark(b, "done")
    assert w.each("trader", "cash", without=("done",)) == [(a, 10)]


def test_each_with_no_fields_asks_only_for_the_component():
    w = _world()
    a, b = w.spawn(), w.spawn()
    w.set(a, "trader", "cash", 10)
    w.mark(b, "done")
    assert [e for e, in w.each("done")] == [b]


def test_has_a_component_or_a_field():
    w = _world()
    e = w.spawn()
    w.set(e, "trader", "cash", 10)
    assert w.has(e, "trader") and w.has(e, "trader", "cash")
    assert not w.has(e, "trader", "goal")


def test_populated_takes_slots():
    w = _world()
    e = w.spawn()
    assert not w.populated(("trader", "cash"))
    w.set(e, "trader", "cash", 10)
    assert w.populated(("trader", "cash"))
    assert w.populated("trader") and w.populated(("trader", None))


def test_the_and_all():
    w = _world()
    a, b = w.spawn(), w.spawn()
    w.set(a, "clock", "tick", 1)
    w.set(b, "clock", "tick", 2)
    assert w.the("clock", "tick") == 1
    assert w.all("clock", "tick") == [(a, 1), (b, 2)]


# -- the change log -------------------------------------------------------

def test_set_records_a_field_delta():
    w = _world()
    e = w.spawn()
    w.set(e, "trader", "cash", 10)
    change = w.changes(kind="set")[-1]
    assert change.target == e.id
    assert change.payload == (("trader", "cash", MISSING, 10),)


def test_changed_filter_names_a_slot():
    w = _world()
    e = w.spawn()
    w.set(e, "trader", "cash", 10)
    w.set(e, "trader", "goal", 3)
    assert len(w.changes(changed=("trader", "cash"))) == 1
    assert len(w.changes(changed=("trader", None))) == 2


def test_a_tag_change_carries_a_component_delta():
    w = _world()
    e = w.spawn()
    w.mark(e, "done")
    assert w.changes(kind="mark")[-1].payload == (("done", None, MISSING, True),)


def test_destroy_records_a_delta_per_field():
    w = _world()
    e = w.spawn()
    w.set(e, "trader", "cash", 10)
    w.set(e, "trader", "goal", 3)
    w.destroy(e)
    payload = w.changes(kind="destroy")[-1].payload
    assert sorted(payload) == [("trader", "cash", 10, MISSING),
                               ("trader", "goal", 3, MISSING)]


# -- transience, and the queries around it -------------------------------

def test_purge_transient_drops_a_whole_component():
    w = _world()
    w.transient = {"cache"}
    e = w.spawn()
    w.set(e, "cache", "hits", 3)
    w.set(e, "trader", "cash", 10)
    assert w.purge_transient() == 1
    assert not w.has(e, "cache") and w.get(e, "trader", "cash") == 10


def test_show_prints_components():
    w = _world()
    e = w.spawn()
    w.set(e, "trader", "cash", 10)
    w.mark(e, "done")
    assert w.show(e) == "#1    trader{cash=10}  done"
