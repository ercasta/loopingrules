"""`examples.circuits`, proven against the four real rules it was
extracted from: `examples.cards.tag_wanted`/`tag_affordable`/
`tag_fair_priced`/`tag_risk_level`. Each spec below is checked two ways
-- unit-level, evaluated directly against a bare `World` -- and
end-to-end, swapped in for the real rule on a fully-installed `cards`
`Loop`, replaying the exact scenarios `tests/test_examples_cards.py`
already pins, to show the compiled circuit produces IDENTICAL behavior
to the hand-written original, not just a plausible-looking one.
"""

import dataclasses

import pytest

from examples import cards, circuits, judge
from examples.cards import (Affordable, Bought, Copies, FairPriced, Listing,
                             Purse, Wanted)
from examples.judge import TooRisky
from loopingrules import analyze
from loopingrules.loop import Loop
from loopingrules.world import Reply, Said, World


# -- the four specs, restating the four real rules ----------------------

tag_wanted_spec = circuits.TagCircuit(
    for_each=cards.Listing,
    condition=circuits.Lt(
        circuits.Coalesce(
            circuits.Via(cards.Listing, "card", cards.Copies, "count"),
            circuits.Const(0)),
        circuits.Via(cards.Listing, "card", cards.Wants, "qty"),
    ),
    tag=cards.Wanted,
)

tag_affordable_spec = circuits.TagCircuit(
    for_each=cards.Listing,
    condition=circuits.And((
        circuits.Le(
            circuits.Self(cards.Listing, "price"),
            circuits.Sub(circuits.World(cards.Purse, "cash"),
                         circuits.World(cards.RiskProfile, "min_cash_reserve"))),
        circuits.Le(circuits.Self(cards.Listing, "price"),
                    circuits.World(cards.RiskProfile, "max_spend_per_trade")),
    )),
    tag=cards.Affordable,
)

tag_fair_priced_spec = circuits.TagCircuit(
    for_each=cards.Listing,
    condition=circuits.Le(
        circuits.Self(cards.Listing, "price"),
        circuits.Mul(
            circuits.Via(cards.Listing, "card", cards.CardDef, "value"),
            circuits.Add(circuits.Const(1),
                         circuits.World(cards.RiskProfile, "max_premium"))),
    ),
    tag=cards.FairPriced,
)

_room = circuits.Sub(circuits.World(cards.Purse, "cash"),
                      circuits.World(cards.RiskProfile, "min_cash_reserve"))
_level = circuits.Min((
    circuits.Const(1.0),
    circuits.SafeDiv(circuits.Self(cards.Listing, "price"), _room, circuits.Const(1.0)),
))
tag_risk_level_spec = circuits.ValueCircuit(
    for_each=cards.Listing,
    into=judge.Risk,
    fields=(
        _level,
        circuits.Format("would use %.0f%% of the %d cash still free to spend",
                        (circuits.Mul(_level, circuits.Const(100)),
                         circuits.Max((_room, circuits.Const(0))))),
    ),
)


# -- decide_buy, reduced: one action per tick, no in-rule loop ----------
#
# `decide_buy`'s own "wants is None or have >= wants.qty" / "price >
# room" guards are PROVABLY redundant once the match already requires
# Wanted/Affordable -- both tags are defined as exactly that condition,
# recomputed fresh every tick before this rule's own turn, so if the tag
# is present the guard already holds. What is NOT redundant, and what
# this circuit deliberately drops, is decide_buy's own multi-buy-per-
# tick optimization (a hand-rolled loop-and-reread over every currently
# qualifying listing) -- see README History, "decide_buy reduces further
# than a loop": one match, one action, per tick, and the tick loop's own
# retry-with-fresh-tags does the rest, the same mechanism a hand-written
# reread was reimplementing by hand inside one rule's body.

def decide_buy_single(w):
    """The hand-written reference this circuit restates -- proven,
    empirically, to reach the identical final state as the real
    `cards.decide_buy` on every existing regression, just over possibly
    more ticks. Analyzed by `loopingrules.analyze` below as the fair
    comparison point for `decide_buy_spec`'s own `reads`/`writes` --
    not the shipped `cards.decide_buy`, which still does the batching
    this one deliberately does not. Uses bare names (`Listing`, not
    `cards.Listing`) on purpose -- `loopingrules.analyze` only resolves
    a component from a literal `Name`, the same dialect `examples.
    cards`'s own rules are already written in; a qualified reference
    would make this function `Opaque` for a reason that has nothing to
    do with what it actually does."""
    match = w.first(Listing, Wanted, Affordable, FairPriced, without=TooRisky)
    if match is None:
        return
    entity, listing, _wanted, _affordable, _fair = match
    purse_entity, purse = w.first(Purse)
    copies = w.get(listing.card, Copies)
    have = copies.count if copies else 0
    w.replace(purse_entity, Purse(purse.cash - listing.price))
    w.replace(listing.card, Copies(have + 1))
    w.destroy(entity)
    w.spawn(Bought(listing.card, listing.price))


decide_buy_spec = circuits.ActionCircuit(
    require=(cards.Listing, cards.Wanted, cards.Affordable, cards.FairPriced),
    without=(judge.TooRisky,),
    effects=(
        circuits.ReplaceWorld(
            cards.Purse,
            (circuits.Sub(circuits.World(cards.Purse, "cash"),
                          circuits.Self(cards.Listing, "price")),)),
        circuits.ReplaceVia(
            cards.Listing, "card", cards.Copies,
            (circuits.Add(
                circuits.Coalesce(
                    circuits.Via(cards.Listing, "card", cards.Copies, "count"),
                    circuits.Const(0)),
                circuits.Const(1)),)),
        circuits.Destroy(),
        circuits.Spawn(cards.Bought, (circuits.Self(cards.Listing, "card"),
                                       circuits.Self(cards.Listing, "price"))),
    ),
)


# -- unit-level: evaluate the condition directly against a bare World ----

def test_tag_wanted_condition_is_false_when_nobody_wants_the_card():
    w = World()
    dragon = w.spawn(cards.CardDef("dragon", "rare", 40), cards.Copies(0))
    listing = w.spawn(cards.Listing(dragon.id, 40))
    assert circuits.evaluate(tag_wanted_spec.condition, w, listing) is False


def test_tag_wanted_condition_defaults_missing_copies_to_zero():
    w = World()
    dragon = w.spawn(cards.CardDef("dragon", "rare", 40), cards.Wants(1))
    listing = w.spawn(cards.Listing(dragon.id, 40))
    assert circuits.evaluate(tag_wanted_spec.condition, w, listing) is True


def test_tag_risk_level_caps_at_one_when_room_is_exhausted():
    w = World()
    w.spawn(cards.Purse(0))
    w.spawn(cards.RiskProfile(50, 0, 0.25))
    dragon = w.spawn(cards.CardDef("dragon", "rare", 40))
    listing = w.spawn(cards.Listing(dragon.id, 40))
    assert circuits.evaluate(_level, w, listing) == 1.0


# -- structural reads/writes, no analysis needed, cross-checked ---------

def test_reads_and_writes_match_loopingrules_analyze_on_the_original():
    """The whole point: a circuit's own map is exact BY CONSTRUCTION.
    Cross-checked here against `loopingrules.analyze`'s AST-derived map
    for the hand-written rule it restates -- the two should agree."""
    pairs = [
        (tag_wanted_spec, cards.tag_wanted),
        (tag_affordable_spec, cards.tag_affordable),
        (tag_fair_priced_spec, cards.tag_fair_priced),
        (tag_risk_level_spec, cards.tag_risk_level),
    ]
    for spec, original in pairs:
        analyzed = analyze.analyze(original)
        assert circuits.reads(spec) == analyzed.reads, original.__name__
        assert circuits.writes(spec) == analyzed.writes, original.__name__


def test_decide_buy_spec_reads_writes_match_the_reduced_reference():
    """`decide_buy_spec` is checked against `decide_buy_single` -- the
    REDUCED hand-written rule -- not the shipped `cards.decide_buy`,
    which still batches several purchases per tick; that batching, not
    the underlying logic, is the one thing this circuit does not
    restate. See `decide_buy_single`'s own docstring."""
    analyzed = analyze.analyze(decide_buy_single)
    assert circuits.reads(decide_buy_spec) == analyzed.reads
    assert circuits.writes(decide_buy_spec) == analyzed.writes
    assert circuits.destroys(decide_buy_spec) == analyzed.destroys


# -- end-to-end: swap the compiled circuit in for the real rule ---------

def _swap(loop, original, replacement):
    for i, (name, fn) in enumerate(loop.rules):
        if fn is original:
            loop.rules[i] = (name, replacement)
            return
    raise AssertionError("%r is not registered on this loop" % original)


@pytest.fixture
def circuit_loop():
    """`cards.install()`, then every one of the four hand-written rules
    this module restates is swapped for its compiled circuit -- the
    OTHER nine rules (parsing, judging, acting, replying) are untouched
    originals."""
    lp = Loop()
    cards.install(lp, cash=100)
    _swap(lp, cards.tag_wanted, circuits.compile_circuit(tag_wanted_spec))
    _swap(lp, cards.tag_affordable, circuits.compile_circuit(tag_affordable_spec))
    _swap(lp, cards.tag_fair_priced, circuits.compile_circuit(tag_fair_priced_spec))
    _swap(lp, cards.tag_risk_level, circuits.compile_circuit(tag_risk_level_spec))
    return lp


def _card(w, name):
    for entity, card_def in w.all(cards.CardDef):
        if card_def.name == name:
            return entity
    raise AssertionError("no such card: %r" % name)


def test_full_buy_flow_is_identical_to_the_hand_written_rules(circuit_loop):
    """Replays `tests/test_examples_cards.py`'s own
    `test_decide_buy_spends_purse_and_increments_copies_and_destroys_the_
    listing` and `test_goal_met_is_announced_exactly_once`, against the
    circuit-compiled tag rules instead of the hand-written ones."""
    w = circuit_loop.world
    w.spawn(Said("user", "want dragon 1"))
    w.spawn(Said("user", "list dragon 40"))
    settled = circuit_loop.run()
    assert settled.hot == []
    assert w.get(_card(w, "dragon"), cards.Copies) == cards.Copies(1)
    assert w.the(cards.Purse) == cards.Purse(60)
    replies = [r.text for _e, r in w.each(Reply)]
    assert "bought dragon for 40" in replies
    assert "goal met -- every wanted card is in the collection" in replies


def test_overspend_regression_holds_under_the_compiled_tags():
    """Replays `test_decide_buy_does_not_overspend_across_two_
    simultaneously_qualifying_listings_in_one_tick` -- the one
    regression this codebase already cared enough about to pin twice."""
    lp = Loop()
    cards.install(lp, cash=60)
    _swap(lp, cards.tag_wanted, circuits.compile_circuit(tag_wanted_spec))
    _swap(lp, cards.tag_affordable, circuits.compile_circuit(tag_affordable_spec))
    _swap(lp, cards.tag_fair_priced, circuits.compile_circuit(tag_fair_priced_spec))
    _swap(lp, cards.tag_risk_level, circuits.compile_circuit(tag_risk_level_spec))
    w = lp.world
    for line in ("want dragon 1", "want griffin 1", "list dragon 40", "list griffin 40"):
        w.spawn(Said("user", line))
    lp.run()
    assert w.get(_card(w, "dragon"), cards.Copies) == cards.Copies(1)
    assert w.get(_card(w, "griffin"), cards.Copies) == cards.Copies(0)
    assert w.the(cards.Purse) == cards.Purse(20)
    assert w.the(cards.Purse).cash >= 0


def test_too_risky_regression_holds_under_the_compiled_tags():
    """Replays `test_decide_buy_skips_a_listing_the_domain_oblivious_
    judge_marks_too_risky` -- confirms the compiled `tag_risk_level`
    still feeds `judge.flag_too_risky` correctly."""
    lp = Loop()
    cards.install(lp, cash=45)
    _swap(lp, cards.tag_wanted, circuits.compile_circuit(tag_wanted_spec))
    _swap(lp, cards.tag_affordable, circuits.compile_circuit(tag_affordable_spec))
    _swap(lp, cards.tag_fair_priced, circuits.compile_circuit(tag_fair_priced_spec))
    _swap(lp, cards.tag_risk_level, circuits.compile_circuit(tag_risk_level_spec))
    w = lp.world
    w.spawn(Said("user", "want dragon 1"))
    w.spawn(Said("user", "list dragon 40"))
    lp.run()
    listing_entity, _listing = w.first(cards.Listing)
    assert w.has(listing_entity, judge.TooRisky)
    assert w.each(cards.Bought) == []
    assert w.the(cards.Purse) == cards.Purse(45)


# -- end-to-end again, this time with decide_buy ALSO a circuit --------

def _all_circuits_loop(cash):
    lp = Loop()
    cards.install(lp, cash=cash)
    _swap(lp, cards.tag_wanted, circuits.compile_circuit(tag_wanted_spec))
    _swap(lp, cards.tag_affordable, circuits.compile_circuit(tag_affordable_spec))
    _swap(lp, cards.tag_fair_priced, circuits.compile_circuit(tag_fair_priced_spec))
    _swap(lp, cards.tag_risk_level, circuits.compile_circuit(tag_risk_level_spec))
    _swap(lp, cards.decide_buy, circuits.compile_circuit(decide_buy_spec))
    return lp


def test_full_buy_flow_holds_with_decide_buy_also_a_circuit():
    lp = _all_circuits_loop(cash=100)
    w = lp.world
    w.spawn(Said("user", "want dragon 1"))
    w.spawn(Said("user", "list dragon 40"))
    settled = lp.run()
    assert settled.hot == []
    assert w.get(_card(w, "dragon"), cards.Copies) == cards.Copies(1)
    assert w.the(cards.Purse) == cards.Purse(60)
    replies = [r.text for _e, r in w.each(Reply)]
    assert "bought dragon for 40" in replies
    assert "goal met -- every wanted card is in the collection" in replies


def test_overspend_regression_holds_with_decide_buy_also_a_circuit():
    """The one that matters most: `decide_buy_spec` never batches, so
    this MUST take more than one tick to resolve both listings compared
    to the hand-written original -- and it must still never overspend."""
    lp = _all_circuits_loop(cash=60)
    w = lp.world
    for line in ("want dragon 1", "want griffin 1", "list dragon 40", "list griffin 40"):
        w.spawn(Said("user", line))
    settled = lp.run()
    assert settled.hot == []
    assert settled.ticks > 1    # confirms the batching really is gone
    assert w.get(_card(w, "dragon"), cards.Copies) == cards.Copies(1)
    assert w.get(_card(w, "griffin"), cards.Copies) == cards.Copies(0)
    assert w.the(cards.Purse) == cards.Purse(20)
    assert w.the(cards.Purse).cash >= 0


def test_too_risky_regression_holds_with_decide_buy_also_a_circuit():
    lp = _all_circuits_loop(cash=45)
    w = lp.world
    w.spawn(Said("user", "want dragon 1"))
    w.spawn(Said("user", "list dragon 40"))
    lp.run()
    listing_entity, _listing = w.first(cards.Listing)
    assert w.has(listing_entity, judge.TooRisky)
    assert w.each(cards.Bought) == []
    assert w.the(cards.Purse) == cards.Purse(45)


# -- the monotonic mode and Exists, added for ../pystrider's OWN idiom --
#
# `examples.cards`'s tag rules all recompute and go BOTH directions every
# tick; `pystrider.patterns`/`constraints` (`LoopCount` -> `TooManyLoops`,
# the exact idiom `PRINCIPLES.md` cites as the model for this whole
# catalog) do the opposite -- derive AT MOST ONCE, guarded by `without=
# self`, never retract. Tried for real against a live `pystrider`
# checkout (not committed here -- `loopingrules` does not depend on
# `pystrider`, the same as it does not depend on `harneskills`, per
# README's own Scope section): `iteration`/`conditional`/`application`/
# `max_loops`, restated as `ValueCircuit(monotonic=True, condition=...)`
# using the new `Exists` primitive, matched `loopingrules.analyze`'s
# reads/writes on the originals exactly, and produced byte-identical
# `Iteration`/`Choice`/`Applies`/`TooManyLoops` components end-to-end
# against a real intake of a real Python snippet with three loops (over
# `MAX_LOOPS=2`) and a conditional call. See README History, "the
# monotonic mode." The tests below pin the same two primitives
# self-containedly, against synthetic components, so this suite does not
# need a `pystrider` checkout to verify them.

@dataclasses.dataclass(frozen=True)
class Count:
    value: int


@dataclasses.dataclass(frozen=True)
class TooMany:
    value: int
    limit: int


@dataclasses.dataclass(frozen=True)
class Ref:
    target: int


@dataclasses.dataclass(frozen=True)
class Marker:
    pass


too_many_spec = circuits.ValueCircuit(
    for_each=Count,
    into=TooMany,
    fields=(circuits.Self(Count, "value"), circuits.Const(3)),
    condition=circuits.Gt(circuits.Self(Count, "value"), circuits.Const(3)),
    monotonic=True,
)


def test_monotonic_value_circuit_does_not_derive_when_condition_is_false():
    w = World()
    entity = w.spawn(Count(1))
    circuits.compile_circuit(too_many_spec)(w)
    assert w.get(entity, TooMany) is None


def test_monotonic_value_circuit_derives_once_and_never_retracts():
    w = World()
    entity = w.spawn(Count(5))
    rule = circuits.compile_circuit(too_many_spec)
    rule(w)
    assert w.get(entity, TooMany) == TooMany(5, 3)
    w.replace(entity, Count(1))    # back under the limit
    rule(w)
    assert w.get(entity, TooMany) == TooMany(5, 3)    # unchanged -- monotonic


def test_monotonic_value_circuits_reads_include_the_implicit_without_gate():
    assert TooMany in circuits.reads(too_many_spec)


def test_exists_is_false_for_an_id_naming_no_such_component():
    w = World()
    ref = w.spawn(Ref(999999))    # points at nothing
    assert circuits.evaluate(
        circuits.Exists(circuits.Self(Ref, "target"), Marker), w, ref) is False


def test_exists_is_true_when_the_related_entity_carries_the_component():
    w = World()
    target = w.spawn(Marker())
    ref = w.spawn(Ref(target.id))
    assert circuits.evaluate(
        circuits.Exists(circuits.Self(Ref, "target"), Marker), w, ref) is True


def test_value_circuit_for_each_accepts_a_multi_component_join():
    """`for_each` as a TUPLE -- `pystrider.patterns.iteration`'s own
    `(ForStmt, Target, Iterated, Body)` shape -- not just one type."""
    spec = circuits.ValueCircuit(
        for_each=(Count, Ref),
        into=TooMany,
        fields=(circuits.Self(Count, "value"), circuits.Self(Ref, "target")),
    )
    w = World()
    entity = w.spawn(Count(5), Ref(9))
    w.spawn(Count(1))    # no Ref -- must not match the join
    circuits.compile_circuit(spec)(w)
    assert w.get(entity, TooMany) == TooMany(5, 9)
    assert circuits.reads(spec) == {Count, Ref}
