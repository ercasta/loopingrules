"""`loopingrules_linda.linda` -- the tuple space's own semantics, pinned.

A check that cannot fail is not a check: these pin matching (arity, formals,
repetition, wildcard), the four ops, and the blocking behaviour the A/B's M4
axis rests on.
"""

from __future__ import annotations

import pytest

from loopingrules_linda.linda import ANY, Blocked, TupleSpace, Var


def test_out_and_rdp_match_by_actuals():
    ts = TupleSpace().out("verdict", 1, True)
    found = ts.rdp("verdict", 1, True)
    assert found is not None
    assert found[0] == ("verdict", 1, True)
    assert found[1] == {}


def test_formals_bind_and_a_repeated_formal_must_be_equal():
    ts = TupleSpace().out("leg", "a", "b").out("leg", "b", "c")
    assert ts.rdp("leg", Var("x"), Var("x")) is None      # no tuple with a == b
    ts.out("leg", "d", "d")
    found = ts.rdp("leg", Var("x"), Var("x"))
    assert found is not None and found[1] == {"x": "d"}


def test_wildcard_matches_any_element():
    ts = TupleSpace().out("v", 7)
    assert ts.rdp("v", ANY) is not None


def test_arity_is_part_of_the_match():
    """The mechanism M1 turns on: a template does not match a longer tuple."""
    ts = TupleSpace().out("verdict", 1, True, "seen")
    assert ts.rdp("verdict", Var("i"), True) is None


def test_inp_removes_and_rdp_leaves():
    ts = TupleSpace().out("item", 3)
    assert ts.rdp("item", 3) is not None
    assert len(ts) == 1
    assert ts.inp("item", 3) is not None
    assert len(ts) == 0
    assert ts.rdp("item", 3) is None


def test_rd_blocks_then_raises():
    with pytest.raises(Blocked):
        TupleSpace().rd("nothing", timeout=0.005)


def test_in_blocks_then_raises():
    with pytest.raises(Blocked):
        TupleSpace().in_("nothing", timeout=0.005)


def test_all_scans_without_consuming():
    ts = TupleSpace()
    ts.out("candidate", 0, 5.0).out("candidate", 1, -1.0)
    rows = ts.all("candidate", Var("id"), Var("worth"))
    assert [bind["id"] for _tup, bind in rows] == [0, 1]
    assert len(ts) == 2                     # a scan, not a take
