"""`loopingrules.analyze` -- exercised against `examples.cards`/`examples.
judge`'s REAL rules, not synthetic ones, wherever that's possible: the
whole point is whether this codebase's actual dialect is analyzable, not
whether some other, friendlier dialect would be."""

import functools

import pytest

from examples import cards, judge
from examples.cards import Wanted
from loopingrules import analyze
from loopingrules.world import Reply, World


# -- analyze(): the positive cases --------------------------------------

def test_a_rule_with_no_helper_call_reads_and_writes_are_exact():
    result = analyze.analyze(cards.tag_wanted)
    assert result.reads == {cards.Copies, cards.Listing, cards.Wants}
    assert result.writes == {cards.Wanted}
    assert result.destroys is False


def test_a_rule_that_destroys_is_marked_but_attributed_to_no_kind():
    """`hear_list` destroys the `Said` line it claims -- but `destroy`
    takes no component-type argument, so nothing here pretends to know
    which kind was destroyed; see the module docstring."""
    result = analyze.analyze(cards.hear_list)
    assert result.destroys is True


def test_follows_one_hop_into_a_same_module_helper():
    """`hear_list`/`hear_want` both call `_find_card(w, name)`, which
    calls `w.all(CardDef)` -- CardDef must show up in the RULE's own
    reads even though the rule's own body never mentions `CardDef`."""
    assert cards.CardDef in analyze.analyze(cards.hear_list).reads
    assert cards.CardDef in analyze.analyze(cards.hear_want).reads


def test_reply_is_special_cased_rather_than_left_opaque():
    """`reply(w, text)` lives in `loopingrules.world`, not `examples.
    cards` -- the "same module only" rule would make every `reply_*`
    rule Opaque for no reason that matters, so `reply`/`propose` are
    special-cased by identity (see the module docstring, "Two named
    exceptions"). This is the case that motivated it."""
    result = analyze.analyze(cards.reply_bought)
    assert result.writes == {Reply}
    assert result.reads == {cards.Bought, cards.CardDef}


def reply(w, text):   # module-level, so it shadows the NAME "reply" for
    w.attach(1, Wanted())   # `handle_helper_call`'s module lookup, while
                             # being a wholly different object than
                             # `loopingrules.world.reply`.


def _uses_a_different_reply(w):
    reply(w, "hi")


def test_an_unrelated_function_of_the_same_name_is_not_mistaken_for_reply():
    """The special case is keyed on IDENTITY, not the name `reply` --
    a domain's own function called `reply` that is not `loopingrules.
    world.reply` gets analyzed (or refused) like any other helper. This
    module's own `reply`, above, is that other function -- resolved by
    module-global lookup the same way `examples.cards._find_card` is."""
    result = analyze.analyze(_uses_a_different_reply)
    assert result.writes == {Wanted}


def test_component_map_over_every_real_rule_resolves_with_nothing_opaque():
    report = analyze.component_map(*cards.RULES, judge.flag_too_risky)
    assert report.opaque == {}
    assert report.writes[judge.Risk] == {"cards.tag_risk_level"}
    assert report.writes[judge.TooRisky] == {"judge.flag_too_risky"}
    assert report.reads[cards.Listing] == {
        "cards.tag_wanted", "cards.tag_affordable", "cards.tag_fair_priced",
        "cards.tag_risk_level", "cards.decide_buy"}


# -- analyze(): Opaque, refuse rather than guess ------------------------

def _aliases_w_before_calling_it(w):
    handle = w.attach          # a bound method, stashed in a variable
    handle(1, cards.Wanted())


def _forwards_w_into_an_unrelated_function(w):
    functools.reduce(lambda acc, x: acc, [w], None)


def test_aliasing_the_world_parameter_is_opaque_not_silently_under_reported():
    with pytest.raises(analyze.Opaque):
        analyze.analyze(_aliases_w_before_calling_it)


def test_forwarding_the_world_parameter_into_an_unrelated_call_is_opaque():
    with pytest.raises(analyze.Opaque):
        analyze.analyze(_forwards_w_into_an_unrelated_function)


def test_component_map_records_an_opaque_rule_by_name_and_reason_not_as_empty():
    report = analyze.component_map(_aliases_w_before_calling_it, cards.tag_wanted)
    assert "test_analyze._aliases_w_before_calling_it" in report.opaque
    assert cards.Wanted in report.writes   # the OTHER rule still resolved


# -- check_watches(): real value, and an honest limit -------------------

def test_check_watches_passes_an_exact_declaration():
    analyze.check_watches(cards.reply_bad_command, watches=(cards.BadCommand,))


def test_check_watches_flags_a_real_read_outside_watches_and_stable():
    with pytest.raises(ValueError):
        analyze.check_watches(cards.hear_list, watches=(cards.Said,))


def test_check_watches_stable_absorbs_install_time_singletons():
    """Bare (`stable=()`), this flags 12 of `cards.RULES`'s 13 rules --
    every one a false alarm, because `tag_affordable` &co. read
    `Purse`/`RiskProfile`, seeded once at `install()` and never removed,
    which can never be the reason a rule was wrongly dormant. Naming
    those as `stable=` clears the false alarm for the rules whose ONLY
    unwatched reads are that kind of permanent background fact."""
    stable = (cards.CardDef, cards.Purse, cards.RiskProfile,
              judge.RiskTolerance, cards.Copies)
    analyze.check_watches(cards.hear_list, watches=(cards.Said,), stable=stable)
    analyze.check_watches(cards.tag_affordable, watches=(cards.Listing,),
                           stable=stable)
    analyze.check_watches(cards.tag_risk_level, watches=(cards.Listing,),
                           stable=stable)
    analyze.check_watches(judge.flag_too_risky, watches=(judge.Risk,),
                           stable=stable)


def test_check_watches_still_flags_a_downstream_tag_even_with_stable():
    """The honest limit: `decide_buy` reads `Wanted`/`Affordable`/
    `FairPriced`/`TooRisky` without watching any of them, and
    `tests/test_examples_cards.py`'s own `test_watches_decide_buy_wakes_
    on_listing_then_notices_the_tags_alone` already PROVES that is safe
    -- those tags only ever land on a `Listing`, which `decide_buy`
    already watches. That is a SECOND legitimate reason a read needn't
    be watched (structural coupling to an already-watched type), and it
    is not the same thing `stable=` names (a permanent, install-seeded
    background fact) -- telling the two apart in general needs a
    cross-rule invariant ("X only ever gets attached to something that
    already has Y") this module cannot see from one rule's own source.
    `check_watches` still raises here, correctly warning about a rule it
    cannot itself prove safe. Pinned as a real, named limit -- not a bug
    to quietly "fix" by loosening the check until it stops noticing
    anything real."""
    stable = (cards.CardDef, cards.Purse, cards.RiskProfile,
              judge.RiskTolerance, cards.Copies)
    with pytest.raises(ValueError):
        analyze.check_watches(cards.decide_buy, watches=(cards.Listing,),
                               stable=stable)


# -- the dialect itself, pinned against a bare World --------------------

def test_analyzed_reads_and_writes_match_what_the_rule_does_at_runtime():
    """Not just a syntactic pin -- run `tag_wanted` for real and confirm
    the write `analyze` predicted is the write that actually happened."""
    w = World()
    dragon = w.spawn(cards.CardDef("dragon", "rare", 40), cards.Copies(0),
                      cards.Wants(1))
    listing = w.spawn(cards.Listing(dragon, 40))
    cards.tag_wanted(w)
    predicted = analyze.analyze(cards.tag_wanted)
    assert w.has(listing, cards.Wanted)              # the write happened
    assert cards.Wanted in predicted.writes           # ... and was predicted
