"""`analyze` on the component substrate (ADR-10): reads and writes are
`(component, field)` slots, derived from the rule's own source.
"""

from __future__ import annotations

import pytest

from loopingrules import analyze


def _reads_writes(fn):
    a = analyze.analyze(fn)
    return a.reads, a.writes


def rule_get_set(w):
    for t, cash in w.each("trader", "cash"):
        if w.has(t, "done"):
            continue
        w.set(t, "trader", "route", cash)


def rule_negated(w):
    if not w.populated(("trader", "cash")):
        e = w.spawn()
        w.mark(e, "seed")


def rule_destroys(w):
    for t, in w.each("done"):
        w.destroy(t)


def rule_without(w):
    for t, cash in w.each("trader", "cash", without=("done",)):
        w.set(t, "trader", "cash", cash - 1)


def rule_changed(w):
    for change in w.changes(changed=("trader", "cash")):
        e = w.spawn()
        w.set(e, "seen", "tick", change.tick)


def rule_opaque(w):
    name = "cash"
    w.get(w.first("trader")[0], "trader", name)


def test_reads_and_writes_are_slots():
    reads, writes = _reads_writes(rule_get_set)
    assert ("trader", "cash") in reads and ("done", None) in reads
    assert writes == {("trader", "route")}


def test_a_negated_read_is_recorded_separately():
    a = analyze.analyze(rule_negated)
    assert ("trader", "cash") in a.reads
    assert ("trader", "cash") in a.negated_reads
    assert a.writes == {("seed", None)}


def test_destroy_is_a_flag():
    a = analyze.analyze(rule_destroys)
    assert a.destroys and a.reads == {("done", None)}


def test_without_names_component_slots():
    reads, _writes = _reads_writes(rule_without)
    assert ("done", None) in reads


def test_changed_names_a_slot():
    reads, writes = _reads_writes(rule_changed)
    assert ("trader", "cash") in reads
    assert writes == {("seen", "tick")}


def test_a_non_literal_name_is_opaque():
    with pytest.raises(analyze.Opaque):
        analyze.analyze(rule_opaque)
