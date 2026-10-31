"""M1's claim, as permanent verification points (`docs/plan-forge.md`).

The gates must be strong enough to reject wrong structure and quiet enough to
accept right structure. Each mutant below is a deliberate breakage whose
*expected* gate must fire; the clean module and a benign variant must trip
nothing. If a gate ever stops firing, or starts firing on a right answer,
this fails -- which is the point: a check that cannot fail is not a check.
"""

from loopingrules_forge import m1


def test_right_candidates_trip_nothing():
    """No false positives: the clean module, and a semantically identical
    rewrite of it, pass every gate."""
    catalog = m1.cards_catalog()
    rights = [c for c in m1.candidates() if c.wanted == ""]
    assert len(rights) == 2
    for candidate in rights:
        assert m1.check(candidate, catalog) == [], candidate.label


def test_each_mutant_trips_its_gate():
    """No false negatives: every mutant is caught, by the gate meant to
    catch it."""
    catalog = m1.cards_catalog()
    mutants = [c for c in m1.candidates() if c.wanted]
    assert len(mutants) == 8
    for candidate in mutants:
        fired = {finding.gate for finding in m1.check(candidate, catalog)}
        assert candidate.wanted in fired, (candidate.label, fired)


def test_gate_set_is_the_spine():
    """The six gates M1 promises, and no quiet renaming."""
    assert set(m1.GATES) == {"shape", "coherence", "tunability", "provenance",
                             "determinism", "behaviour"}
