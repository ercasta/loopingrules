"""Q0 (`loopingrules_forge.q0`): the recognize-act cycle over activations.

The claims: a reshaped rule's LHS predicate matches EXACTLY the entities the
real rule acts on (and is narrower than `analyze`'s gate), with no widening of
the declared escape; with no ambiguity the schedule reproduces the run-all
signature and settles; the deterministic default score starves all but one
activation; refraction fixes it; and novelty falls back to the frozen score
while recording a `Doubt` as world data. If any of these stopped holding, the
scheduler plan's first three claims would be unproven.
"""

from loopingrules_forge import q0


# -- claim 1: match is exact, not the gate ------------------------------

def test_match_is_exact_not_the_gate():
    c1 = q0.claim_1_match_is_exact()
    assert c1["exact"] == c1["fired"]          # the predicate == what the rule does
    assert c1["exact"] < c1["eligible"]        # and narrower than the gate
    assert len(c1["exact"]) == 1               # only the affordable listing


def test_the_reshape_widens_no_escape():
    c1 = q0.claim_1_match_is_exact()
    assert c1["guard_total"]                   # every node is evaluable (total)
    assert not c1["opaque"]                    # decide_buy still analyzes clean
    assert c1["escapes"] == 2                  # M0's declared verbatim helpers, unchanged


# -- claim 2: no ambiguity => identical to running everything -----------

def test_no_ambiguity_reproduces_the_run_all_signature():
    c2 = q0.claim_2_no_ambiguity()
    assert c2["base_sig"] == c2["sched_sig"]
    assert c2["base_fired"] == c2["sched_fired"] == ("serve", "serve", "serve")


def test_the_schedule_settles():
    c2 = q0.claim_2_no_ambiguity()
    assert c2["ok"]
    # and the conflicted board settles too, under refraction
    c3 = q0.claim_3_starvation_and_novelty()
    assert not c3["fair_hot"]


# -- claim 3: starvation, refraction, novelty fallback ------------------

def test_the_default_score_starves_the_second_production():
    c3 = q0.claim_3_starvation_and_novelty()
    assert c3["starved_tally"] == (6, 0)       # serve_b never spent a use
    assert c3["eligible_b_ticks"] > 0          # ...though it was eligible
    assert not c3["starved_hot"]               # the world still settled


def test_refraction_restores_fairness():
    c3 = q0.claim_3_starvation_and_novelty()
    assert c3["fair_tally"] == (3, 3)
    assert c3["fair_fired"][0] == "serve_a" and "serve_b" in c3["fair_fired"]


def test_novelty_falls_back_to_the_frozen_score_and_records_a_doubt():
    c3 = q0.claim_3_starvation_and_novelty()
    assert c3["world_doubts"] > 0              # a Doubt was deposited as data
    assert c3["starved_doubts"]                # ...one per novel decision
    # the frozen default reproduces the novelty outcome exactly...
    assert c3["frozen_tally"] == c3["starved_tally"]
    # ...and an explicit controller means it is NOT novelty (no doubts)
    assert c3["frozen_doubts"] == ()


def test_the_default_is_deterministic():
    first = q0.claim_3_starvation_and_novelty()
    second = q0.claim_3_starvation_and_novelty()
    assert first["starved_fired"] == second["starved_fired"]
    assert first["fair_fired"] == second["fair_fired"]
    assert first["ok"] and second["ok"]
