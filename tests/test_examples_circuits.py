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
from examples.cards import (Affordable, Bought, CardDef, Copies, FairPriced,
                             GoalMet, Listing, Purse, Wanted, Wants)
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


# -- check_goal: no per-entity match on the QUESTION, a quantifier over
# a completely different set -- and "don't fire twice" by CONSUMING a
# seeded marker, not by testing GoalMet's own absence
#
# check_goal is not a per-entity circuit -- "every wanted card is met" is
# a quantifier over a SET (Any/Forall, added for exactly this: Any(over)
# is false on an empty set, Forall(over, condition) is vacuously true on
# one -- combined with And, "at least one goal exists, and all of them
# are met"). A first attempt matched no entity at all (a WorldCircuit)
# and guarded "don't fire twice" with self-reference, Not(Any((GoalMet,
# ))), inside the condition -- correct, but the wrong idiom: `Wants`
# must never be destroyed (hear_status still reads it), yet the RIGHT
# answer to "don't fire twice" in this codebase is consuming an occasion
# (Said, Proposal), not testing an output's own absence. GoalCheck,
# below, is that occasion -- seeded once, matched by an ordinary
# ActionCircuit, consumed (Destroy()) the moment the goal turns out to
# be met. No self-reference to GoalMet needed at all: once GoalCheck is
# gone, the rule has structurally nothing left to match, ever again.

@dataclasses.dataclass(frozen=True)
class GoalCheck:
    """A seeded, one-shot marker -- not `cards.py`'s own vocabulary,
    invented here to give `check_goal`'s circuit something to CONSUME.
    Exists exactly once (seeded like `Purse`/`RiskProfile` are), and is
    destroyed the moment the goal is confirmed met."""


check_goal_spec = circuits.ActionCircuit(
    require=(GoalCheck,),
    without=(),
    condition=circuits.And((
        circuits.Any((cards.CardDef, cards.Wants)),
        circuits.Forall(
            (cards.CardDef, cards.Wants),
            circuits.Ge(
                circuits.Coalesce(circuits.Self(cards.Copies, "count"), circuits.Const(0)),
                circuits.Self(cards.Wants, "qty"))),
    )),
    effects=(circuits.Destroy(), circuits.Spawn(cards.GoalMet, ())),
)


def check_goal_consuming(w):
    """The hand-written reference `check_goal_spec` restates -- the fair
    comparison point for its own `reads`/`writes` (not the shipped
    `cards.check_goal`, which guards via `w.the(GoalMet) is not None`
    instead, a different idiom -- see the module-level note above).
    Bare names (`CardDef`, not `cards.CardDef`) on purpose -- see
    `decide_buy_single`'s own docstring for why."""
    for entity, _check in w.each(GoalCheck):
        wanted = w.each(CardDef, Wants)
        if not wanted:
            return
        for card_entity, _card_def, wants in wanted:
            copies = w.get(card_entity, Copies)
            have = copies.count if copies else 0
            if have < wants.qty:
                return
        w.destroy(entity)
        w.spawn(GoalMet())


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


def test_check_goal_spec_reads_writes_match_the_consuming_reference():
    """Checked against `check_goal_consuming`, not the shipped `cards.
    check_goal` -- the two guard "don't fire twice" with different
    idioms (consume `GoalCheck` vs. test `GoalMet`'s own absence), so
    their reads legitimately differ (`GoalCheck` here, not `GoalMet` as
    a read -- `GoalMet` is write-only once nothing tests its absence)."""
    analyzed = analyze.analyze(check_goal_consuming)
    assert circuits.reads(check_goal_spec) == analyzed.reads
    assert circuits.writes(check_goal_spec) == analyzed.writes
    assert circuits.destroys(check_goal_spec) == analyzed.destroys


def test_any_is_false_on_an_empty_match_and_true_once_something_qualifies():
    w = World()
    assert circuits.evaluate(circuits.Any(cards.GoalMet), w, None) is False
    w.spawn(cards.GoalMet())
    assert circuits.evaluate(circuits.Any(cards.GoalMet), w, None) is True


def test_forall_is_vacuously_true_on_an_empty_match():
    w = World()
    always_false = circuits.Forall(cards.GoalMet, circuits.Const(False))
    assert circuits.evaluate(always_false, w, None) is True


def test_forall_checks_every_match_not_just_the_first():
    w = World()
    dragon = w.spawn(cards.CardDef("dragon", "rare", 40), cards.Wants(1), cards.Copies(1))
    griffin = w.spawn(cards.CardDef("griffin", "rare", 35), cards.Wants(1), cards.Copies(0))
    condition = circuits.Ge(circuits.Self(cards.Copies, "count"), circuits.Self(cards.Wants, "qty"))
    assert circuits.evaluate(
        circuits.Forall((cards.CardDef, cards.Wants), condition), w, None) is False
    w.replace(griffin, cards.Copies(1))
    assert circuits.evaluate(
        circuits.Forall((cards.CardDef, cards.Wants), condition), w, None) is True


def test_check_goal_circuit_never_fires_a_second_time():
    """"Don't fire twice" is structural, not logical -- GoalCheck is
    consumed the first time the rule fires, so the SECOND call has
    nothing left to match at all, checked directly rather than assumed
    from the design argument."""
    w = World()
    w.spawn(cards.CardDef("dragon", "rare", 40), cards.Wants(1), cards.Copies(1))
    check = w.spawn(GoalCheck())
    rule = circuits.compile_circuit(check_goal_spec)
    rule(w)
    assert w.each(cards.GoalMet) != []
    assert not check.alive    # consumed, not just guarded
    rule(w)
    assert len(w.each(cards.GoalMet)) == 1    # still exactly one, not two


def test_check_goal_circuit_does_not_fire_while_a_want_is_unmet():
    w = World()
    w.spawn(cards.CardDef("dragon", "rare", 40), cards.Wants(2), cards.Copies(1))
    w.spawn(GoalCheck())
    circuits.compile_circuit(check_goal_spec)(w)
    assert w.each(cards.GoalMet) == []


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


# -- end-to-end again, this time with decide_buy and check_goal ALSO
# circuits -- six of cards.py's thirteen rules, all restated as data

def _all_circuits_loop(cash):
    lp = Loop()
    cards.install(lp, cash=cash)
    _swap(lp, cards.tag_wanted, circuits.compile_circuit(tag_wanted_spec))
    _swap(lp, cards.tag_affordable, circuits.compile_circuit(tag_affordable_spec))
    _swap(lp, cards.tag_fair_priced, circuits.compile_circuit(tag_fair_priced_spec))
    _swap(lp, cards.tag_risk_level, circuits.compile_circuit(tag_risk_level_spec))
    _swap(lp, cards.decide_buy, circuits.compile_circuit(decide_buy_spec))
    _swap(lp, cards.check_goal, circuits.compile_circuit(check_goal_spec))
    lp.world.spawn(GoalCheck())    # check_goal_spec's own occasion to consume
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


def test_goal_met_reply_still_fires_exactly_once_with_check_goal_a_circuit():
    """Replays `test_examples_cards.py`'s own `test_goal_met_is_announced_
    exactly_once` against the circuit-compiled check_goal -- the guard
    against re-announcing lives in `reply_goal_met` (untouched, real
    Python, `without=Announced`), not in `check_goal` itself; this pins
    that the two still compose correctly when one of them is a circuit."""
    lp = _all_circuits_loop(cash=100)
    w = lp.world
    w.spawn(Said("user", "want dragon 1"))
    w.replace(_card(w, "dragon"), cards.Copies(1))
    lp.run()
    first = [r.text for _e, r in w.each(Reply)]
    for e, _r in w.each(Reply):
        w.destroy(e)
    assert first == ["goal met -- every wanted card is in the collection"]
    lp.tick()
    assert w.each(Reply) == []


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


# -- Count/Children/HasSelf, added for pystrider.patterns.loop_count ---
#
# loop_count is a THIRD aggregate shape, distinct from both check_goal's
# Any/Forall (a boolean, over a GLOBAL join) and everything else in this
# file (one entity's own fields): "how many of a Function's Stmts are
# ForStmts" needs a NUMBER, and the Stmts to count are not a world-wide
# join at all -- they are reached by following THIS Function's own Body
# to one specific entity, then reading every Stmt THERE (get_all,
# plural -- the one-to-many hop Via cannot reach). Children names that
# scope; Count is Any/Forall's sibling that counts instead of asking
# yes/no; HasSelf answers "does the entity currently being counted carry
# this" without needing an expression to name it (it just IS self).
#
# Tried for real against a live pystrider checkout (not committed here,
# same as the monotonic mode and the generic Part tag before it):
# restated exactly as below (Function/Body/Stmt/ForStmt in place of the
# synthetic Box/Item/Flagged here), reads/writes matched
# loopingrules.analyze.analyze(patterns.loop_count) exactly, and the
# compiled circuit -- swapped in for loop_count alongside the three
# already-restated descriptions -- produced a byte-identical LoopCount,
# with constraints.max_loops (itself already a circuit) still composing
# correctly on top of it. See README History, "loop_count's aggregate."

@dataclasses.dataclass(frozen=True)
class Box:
    body: int


@dataclasses.dataclass(frozen=True)
class Item:
    entity: int


@dataclasses.dataclass(frozen=True)
class Flagged:
    pass


@dataclasses.dataclass(frozen=True)
class ItemTally:
    count: int


item_tally_spec = circuits.ValueCircuit(
    for_each=(Box,),
    into=ItemTally,
    monotonic=True,
    fields=(circuits.Count(
        circuits.Children(Box, "body", Item), circuits.HasSelf(Flagged)),),
)


def item_tally_reference(w):
    """The hand-written reference `item_tally_spec` restates -- the same
    shape as `pystrider.patterns.loop_count`, with `Box`/`Item`/`Flagged`
    standing in for `Function`/`Stmt`/`ForStmt`."""
    for entity, box in w.each(Box, without=ItemTally):
        count = sum(1 for item in w.get_all(box.body, Item)
                    if w.has(item.entity, Flagged))
        w.attach(entity, ItemTally(count))


def test_count_is_zero_on_an_empty_children_scope():
    w = World()
    body = w.spawn()
    box = w.spawn(Box(body.id))
    assert circuits.evaluate(
        circuits.Count(circuits.Children(Box, "body", Item), circuits.HasSelf(Flagged)),
        w, box) == 0


def test_count_counts_only_the_children_satisfying_the_condition():
    w = World()
    body = w.spawn()
    box = w.spawn(Box(body.id))
    flagged_child = w.spawn(Flagged())
    plain_child = w.spawn()
    w.attach(body, Item(flagged_child.id), Item(plain_child.id))
    assert circuits.evaluate(
        circuits.Count(circuits.Children(Box, "body", Item), circuits.HasSelf(Flagged)),
        w, box) == 1


def test_has_self_is_false_with_no_entity_in_scope():
    w = World()
    assert circuits.evaluate(circuits.HasSelf(Flagged), w, None) is False


def test_item_tally_spec_matches_the_hand_written_reference():
    """Unit-level AND structural: same final value on a real world, and
    the same reads/writes as `loopingrules.analyze` derives from the
    hand-written reference."""
    w = World()
    body = w.spawn()
    box = w.spawn(Box(body.id))
    w.attach(body, Item(w.spawn(Flagged()).id), Item(w.spawn(Flagged()).id),
              Item(w.spawn().id))
    circuits.compile_circuit(item_tally_spec)(w)
    assert w.get(box, ItemTally) == ItemTally(2)

    analyzed = analyze.analyze(item_tally_reference)
    assert circuits.reads(item_tally_spec) == analyzed.reads
    assert circuits.writes(item_tally_spec) == analyzed.writes


# -- recursion, flattened into propagation across ticks ------------------
#
# `pystrider.symbolic.fold` recurses in Python over a Left/Right tree --
# named, at the time, as "irreducible: real computation, not
# composition." That claim was too strong. Production/term-rewriting
# systems (what this substrate structurally is) are Turing-complete; a
# recursive call can always be flattened into "compute the leaves now,
# then whatever depends only on already-computed values, then whatever
# depends on THAT," which is exactly a `ValueCircuit` reading its own
# output via `Exists`/`Via` on related entities, run to a fixpoint. No
# new primitive was needed to prove it -- `Add`/`Mul`/`Via`/`Exists`/`Eq`
# already existed. `pystrider.effects.transitive`'s own docstring already
# names this same idea for a different propagation ("a call graph five
# deep needs no more code than a call graph one deep -- the loop just
# runs a few more ticks"); `pystrider.symbolic`'s own module docstring
# records that `fold` ITSELF used to work this way and was deliberately
# rewritten to recurse in Python instead, "a side benefit" of a change
# made for a different reason (a repair mutating a `Constant` in place
# needs `fold` to recompute from scratch, not trust a per-tick cache).
#
# So both directions are real, working, and already chosen at least
# once in this project's own history. What this section pins is the
# actual cost of the propagation direction, not just that it exists:
# ticks-to-settle depends on registration order (dependency order lets
# a whole tree resolve within ONE productive tick, thanks to `Loop.
# tick`'s own same-tick write visibility; the adversarial order costs
# one tick per nesting level instead) -- correctness never does.

@dataclasses.dataclass(frozen=True)
class Lit:
    value: int


@dataclasses.dataclass(frozen=True)
class BinOp:
    op: str
    left: int
    right: int


@dataclasses.dataclass(frozen=True)
class Folded:
    value: int


fold_lit = circuits.ValueCircuit(for_each=Lit, into=Folded,
                                  fields=(circuits.Self(Lit, "value"),))

fold_add = circuits.ValueCircuit(
    for_each=BinOp, into=Folded,
    condition=circuits.And((
        circuits.Eq(circuits.Self(BinOp, "op"), circuits.Const("add")),
        circuits.Exists(circuits.Self(BinOp, "left"), Folded),
        circuits.Exists(circuits.Self(BinOp, "right"), Folded))),
    fields=(circuits.Add(circuits.Via(BinOp, "left", Folded, "value"),
                          circuits.Via(BinOp, "right", Folded, "value")),),
)

fold_mul = circuits.ValueCircuit(
    for_each=BinOp, into=Folded,
    condition=circuits.And((
        circuits.Eq(circuits.Self(BinOp, "op"), circuits.Const("mul")),
        circuits.Exists(circuits.Self(BinOp, "left"), Folded),
        circuits.Exists(circuits.Self(BinOp, "right"), Folded))),
    fields=(circuits.Mul(circuits.Via(BinOp, "left", Folded, "value"),
                          circuits.Via(BinOp, "right", Folded, "value")),),
)


def _expression_tree():
    """`(2 + 3) * (4 + 5)` -- two levels of nesting on BOTH operands of
    the top node, so a single-level propagation could not fake the
    right answer by accident."""
    w = World()
    two, three, four, five = (w.spawn(Lit(v)) for v in (2, 3, 4, 5))
    add1 = w.spawn(BinOp("add", two.id, three.id))
    add2 = w.spawn(BinOp("add", four.id, five.id))
    top = w.spawn(BinOp("mul", add1.id, add2.id))
    return w, top.id, add1.id, add2.id


def test_recursive_fold_flattens_into_propagation_with_no_new_primitives():
    w, top, add1, add2 = _expression_tree()
    lp = Loop()
    lp.rule(circuits.compile_circuit(fold_lit), name="fold_lit", watches=(Lit,))
    lp.rule(circuits.compile_circuit(fold_add), name="fold_add", watches=(BinOp,))
    lp.rule(circuits.compile_circuit(fold_mul), name="fold_mul", watches=(BinOp,))
    lp.world = w
    settled = lp.run()
    assert settled.hot == []
    assert w.get(top, Folded) == Folded(45)
    assert w.get(add1, Folded) == Folded(5)
    assert w.get(add2, Folded) == Folded(9)


def test_fold_propagation_settles_regardless_of_registration_order():
    """The one real cost, pinned rather than asserted in prose: ticks-to-
    settle depends on registration order (same-tick write visibility
    lets a dependency-ordered registration resolve a whole tree in ONE
    productive tick); CORRECTNESS does not."""
    w, top, _add1, _add2 = _expression_tree()
    lp = Loop()
    lp.rule(circuits.compile_circuit(fold_mul), name="fold_mul", watches=(BinOp,))
    lp.rule(circuits.compile_circuit(fold_add), name="fold_add", watches=(BinOp,))
    lp.rule(circuits.compile_circuit(fold_lit), name="fold_lit", watches=(Lit,))
    lp.world = w
    settled = lp.run()
    assert w.get(top, Folded) == Folded(45)
    assert settled.ticks > 2    # strictly more ticks than the dependency-ordered case


def test_fold_circuits_are_fully_sound_unlike_the_recursive_original():
    """The genuine win: `fold`/`_fold_binary` (arbitrary Python recursion)
    is opaque to `loopingrules.analyze` in a way this restatement is not
    -- every read/write is exact and structural, self-referential
    `Folded` (both read, via a sibling's own output, and written)
    included."""
    assert circuits.reads(fold_add) == {BinOp, Folded}
    assert circuits.writes(fold_add) == {Folded}
