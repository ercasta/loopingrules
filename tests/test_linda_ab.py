"""The A/B's claims, as permanent verification points
(`docs/patterns-oblivious-composition.md` §7).

Pre-registered verdict: A wins M1 and M2; M3 is a wash (both explicit); M4 is a
model difference, not a power one. A test that cannot fail is not a check.
"""

from __future__ import annotations

from loopingrules_linda import ab


def test_m1_named_match_survives_a_new_field_positional_does_not():
    """A reader naming `verdict.ok` is unaffected when the writer adds
    `verdict.reason`; a positional template that grew an arity matches nothing."""
    m1 = ab.measure_m1()
    assert m1["substrate_stable"]
    assert m1["substrate_plain"] == ["a", "c"]      # b's worth is negative
    assert m1["linda_naive"] == []                  # arity grew -> 0 matches
    assert m1["linda_naive_breaks"]
    assert m1["linda_tagged_stable"]                # only with the convention


def test_m2_negation_is_one_match_but_a_scan_plus_probe_in_linda():
    m2 = ab.measure_m2()
    assert m2["substrate_marked"] == 3              # one `each(..., without=...)`
    assert m2["linda_marked"] == 3                  # same outcome ...
    assert m2["linda_calls"] == 6                   # ... a scan + a probe, each


def test_m3_the_read_set_is_derived():
    m3 = ab.measure_m3()
    assert ("verdict", "ok") in m3["substrate_reads"]   # the SHARED shape
    assert ("alpha", None) in m3["substrate_reads"]     # the reader's OWN component


def test_m4_substrate_settles_linda_blocks():
    m4 = ab.measure_m4()
    assert m4["substrate_settles"]
    assert m4["linda_rd_blocks"]


def test_run_all_agrees_with_itself():
    _m1, _m2, _m3, _m4, rows = ab.run_all()
    assert all(ok for _label, ok, _note in rows)
    assert [label for label, _ok, _note in rows] == [
        "M1 layout", "M2 conjunction", "M3 derived reads", "M4 blocking"]
