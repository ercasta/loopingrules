"""`loopingrules.analyze` -- exercised against `examples.cards`/`examples.
judge`'s REAL rules, not synthetic ones, wherever that's possible: the
whole point is whether this codebase's actual dialect is analyzable, not
whether some other, friendlier dialect would be."""

import functools

import pytest

from examples import cards, judge
from examples.cards import Wanted
from loopingrules import analyze, help as help_
from loopingrules.world import Proposal, Reply, World


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


# -- arbitrate()/census(): the two other special-cased helpers ----------
#
# `check_watches()` -- comparing a hand-written `watches=` against
# `analyze()`'s own reads -- is gone along with the hand-written
# declaration it was auditing: `Loop.rule` calls `analyze()` itself now
# and uses its reads AS the gate, so there is nothing left for a second
# declaration to drift out of sync with (see `loop.py`'s own module
# note, "A rule wakes only when something it reads exists"). What is
# still worth pinning here is the other half of that change: `arbitrate`/
# `census`, `loopingrules.help`'s own chokepoint, had to join `reply`/
# `propose` as special-cased-by-identity, or `arbitrate_help`/
# `close_census` -- the only two rules in this whole codebase that call
# either -- would resolve `Opaque` and silently lose their gate, called
# every tick regardless of whether their own occasion type exists.

def test_arbitrate_is_special_cased_rather_than_left_opaque():
    """`arbitrate_help`'s own body never mentions `Proposal` at all, yet
    it must be attributed as a read AND a write, the same as `reply`
    being attributed to `reply_bought`'s writes even though `Reply`
    never appears as a literal in that rule's own source."""
    result = analyze.analyze(help_.arbitrate_help)
    assert result.reads == {help_.HelpTopic, Proposal}
    assert result.writes == {Proposal, Reply}
    assert result.destroys is True


def test_census_is_special_cased_rather_than_left_opaque():
    result = analyze.analyze(help_.close_census)
    assert help_.HelpCommandCensus in result.reads
    assert Proposal in result.reads
    assert Proposal in result.writes
    assert result.destroys is True


def test_component_map_over_help_resolves_with_nothing_opaque():
    """The case that motivated the special-casing above: before it,
    `component_map(*help_.RULES)` had two `Opaque` entries, and
    `Loop.rule` would have installed `arbitrate_help`/`close_census`
    with no gate at all."""
    report = analyze.component_map(*help_.RULES)
    assert report.opaque == {}


# -- negated_reads: a type tested for ABSENCE never gates a rule --------
#
# Found by `tests/test_engine.py`'s own `pong` (`if not w.each(Ping):
# w.spawn(Ping())`): gating that rule on `Ping` would skip it exactly
# when `Ping` is gone, which is the one moment it needs to run. See
# `Analysis.negated_reads`'s own docstring.

def _spawns_when_absent(w):
    if not w.each(Wanted):
        w.attach(1, Wanted())


def _spawns_when_none(w):
    if w.first(Wanted) is None:
        w.attach(1, Wanted())


def _spawns_when_empty_by_len(w):
    if len(w.each(Wanted)) == 0:
        w.attach(1, Wanted())


def _reads_the_same_type_both_ways(w):
    for _entity, _wanted in w.each(Wanted):
        pass
    if not w.each(Wanted):
        w.attach(1, Wanted())


@pytest.mark.parametrize("fn", [
    _spawns_when_absent, _spawns_when_none, _spawns_when_empty_by_len])
def test_a_type_tested_for_absence_is_read_but_excluded_from_the_gate(fn):
    result = analyze.analyze(fn)
    assert Wanted in result.reads
    assert Wanted in result.negated_reads


def test_a_type_read_both_positively_and_negatively_is_excluded_everywhere():
    """Conservative on purpose: this module cannot tell, from source
    alone, whether the two occurrences are independent branches or
    entangled, so BOTH lose the gate, not just the negated one."""
    result = analyze.analyze(_reads_the_same_type_both_ways)
    assert Wanted in result.negated_reads


def test_a_positive_read_alone_is_never_marked_negated():
    result = analyze.analyze(cards.tag_wanted)
    assert result.negated_reads == set()


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
