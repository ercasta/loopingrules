"""`examples.cards` -- one autonomous trading agent on a virtual market,
with no rivalry anywhere (see that module's own docstring for why no
`Proposal`/`arbitrate`/`census` appears below). Convention mirrors
`tests/test_help.py`: a `say(loop, line)` helper that spawns a `Said`,
runs the loop to a settle, and hands back every `Reply` text produced."""

import pytest

from examples import cards
from loopingrules.loop import Loop
from loopingrules.world import Reply, Said


def say(loop, line):
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
            if w.destroy(entity) or True]


def card(w, name):
    """The `CardDef` entity named `name` -- a test-local lookup, not
    `cards._find_card`, so these tests exercise public behaviour only."""
    for entity, card_def in w.all(cards.CardDef):
        if card_def.name == name:
            return entity
    raise AssertionError("no such card in this world: %r" % name)


@pytest.fixture
def loop():
    lp = Loop()
    cards.install(lp, cash=100)
    return lp


# -- install / seeding ------------------------------------------------------

def test_install_seeds_catalog_purse_and_risk_profile(loop):
    w = loop.world
    assert len(w.all(cards.CardDef)) == len(cards.DEFAULT_CATALOG)
    assert len(w.all(cards.Copies)) == len(cards.DEFAULT_CATALOG)
    assert w.the(cards.Purse) == cards.Purse(100)
    assert w.the(cards.RiskProfile) is not None


def test_install_does_not_overwrite_an_existing_card_def():
    lp = Loop()
    w = lp.world
    dragon = w.spawn(cards.CardDef("dragon", "rare", 999))
    w.attach(dragon, cards.Copies(3))
    cards.install(lp, catalog=cards.DEFAULT_CATALOG)
    assert w.get(dragon, cards.CardDef) == cards.CardDef("dragon", "rare", 999)
    assert w.get(dragon, cards.Copies) == cards.Copies(3)


def test_install_seeds_a_missing_catalog_entry_into_an_otherwise_seeded_world():
    lp = Loop()
    w = lp.world
    w.spawn(cards.CardDef("dragon", "rare", 999))
    cards.install(lp, catalog=(cards.CardDef("dragon", "rare", 40),
                               cards.CardDef("goblin", "common", 5)))
    names = sorted(cd.name for _e, cd in w.all(cards.CardDef))
    assert names == ["dragon", "goblin"]
    assert w.get(card(w, "dragon"), cards.CardDef).value == 999   # untouched
    assert w.get(card(w, "goblin"), cards.Copies) == cards.Copies(0)


def test_install_does_not_re_seed_purse_or_risk_profile_on_restore():
    lp = Loop()
    w = lp.world
    w.spawn(cards.Purse(7))
    w.spawn(cards.RiskProfile(1, 2, 0.1))
    cards.install(lp, cash=999)
    assert w.the(cards.Purse) == cards.Purse(7)
    assert w.the(cards.RiskProfile) == cards.RiskProfile(1, 2, 0.1)


# -- hearing ------------------------------------------------------------

def test_hear_list_spawns_a_listing_for_a_known_card(loop):
    say(loop, "list dragon 30")
    w = loop.world
    dragon = card(w, "dragon")
    assert any(listing.card == dragon.id and listing.price == 30
               for _e, listing in w.each(cards.Listing))


def test_hear_list_refuses_an_unknown_card_name_with_bad_command(loop):
    assert say(loop, "list unicorn 10") == ["! unknown card 'unicorn'"]


def test_hear_list_refuses_an_unparseable_price_with_bad_command(loop):
    assert say(loop, "list dragon many") == ["! not a price: 'many'"]


def test_hear_want_spawns_wants_for_a_first_ask(loop):
    say(loop, "want dragon")
    w = loop.world
    assert w.get(card(w, "dragon"), cards.Wants) == cards.Wants(1)


def test_hear_want_replaces_not_duplicates_on_a_second_ask_for_the_same_card(loop):
    say(loop, "want dragon 2")
    say(loop, "want dragon 5")
    w = loop.world
    assert w.get_all(card(w, "dragon"), cards.Wants) == [cards.Wants(5)]


def test_hear_status_replies_with_cash_and_progress(loop):
    say(loop, "want dragon 1")
    assert say(loop, "status") == ["cash: 100; dragon: 0/1"]


# -- composing tags on a Listing, independently --------------------------

def test_tag_wanted_attaches_when_short_and_detaches_once_satisfied(loop):
    w = loop.world
    say(loop, "want dragon 1")
    say(loop, "list dragon 999999")   # far over cap: never bought, stays put
    listing_entity, _listing = w.first(cards.Listing)
    assert w.has(listing_entity, cards.Wanted)
    w.replace(card(w, "dragon"), cards.Copies(1))
    loop.tick()
    assert not w.has(listing_entity, cards.Wanted)


def test_tag_affordable_attaches_and_detaches_as_cash_changes(loop):
    w = loop.world
    say(loop, "list dragon 40")       # not wanted, so it just sits there
    listing_entity, _listing = w.first(cards.Listing)
    assert w.has(listing_entity, cards.Affordable)
    purse_entity, _purse = w.first(cards.Purse)
    w.replace(purse_entity, cards.Purse(10))
    loop.tick()
    assert not w.has(listing_entity, cards.Affordable)


def test_tag_fair_priced_reads_the_referenced_card_def_by_id(loop):
    w = loop.world
    say(loop, "list dragon 40")       # value 40, default premium 0.25 -> limit 50
    say(loop, "list dragon 51")       # over the limit
    fair = w.first(cards.Listing, cards.FairPriced)
    over = [e for e, listing in w.each(cards.Listing) if listing.price == 51][0]
    assert fair is not None and fair[1].price == 40
    assert not w.has(over, cards.FairPriced)


# -- acting ---------------------------------------------------------------

def test_decide_buy_requires_all_three_tags_present(loop):
    say(loop, "list dragon 40")       # never wanted -- no Wants asked for it
    w = loop.world
    assert w.each(cards.Listing) != []
    assert w.each(cards.Bought) == []


def test_decide_buy_spends_purse_and_increments_copies_and_destroys_the_listing(loop):
    w = loop.world
    say(loop, "want dragon 2")        # qty 2, so one purchase doesn't finish it
    result = say(loop, "list dragon 40")
    assert w.get(card(w, "dragon"), cards.Copies) == cards.Copies(1)
    assert w.the(cards.Purse) == cards.Purse(60)
    assert w.each(cards.Listing) == []
    assert result == ["bought dragon for 40"]


def test_decide_buy_does_not_overspend_across_two_simultaneously_qualifying_listings_in_one_tick():
    lp = Loop()
    cards.install(lp, cash=60)
    w = lp.world
    for line in ("want dragon 1", "want griffin 1",
                 "list dragon 40", "list griffin 40"):
        w.spawn(Said("user", line))
    lp.run()
    assert w.get(card(w, "dragon"), cards.Copies) == cards.Copies(1)
    assert w.get(card(w, "griffin"), cards.Copies) == cards.Copies(0)
    assert w.the(cards.Purse) == cards.Purse(20)   # only ONE purchase happened
    assert w.the(cards.Purse).cash >= 0


def test_a_freshly_listed_card_can_be_bought_the_same_settle(loop):
    w = loop.world
    say(loop, "want dragon 5")
    w.spawn(Said("user", "list dragon 40"))
    settled = loop.run()
    assert settled.hot == []
    assert w.get(card(w, "dragon"), cards.Copies) == cards.Copies(1)


def test_check_goal_fires_once_every_want_is_met_and_not_before(loop):
    w = loop.world
    say(loop, "want dragon 1")
    assert w.the(cards.GoalMet) is None
    w.replace(card(w, "dragon"), cards.Copies(1))
    loop.tick()
    assert w.the(cards.GoalMet) is not None


def test_goal_met_is_announced_exactly_once(loop):
    w = loop.world
    say(loop, "want dragon 1")
    w.replace(card(w, "dragon"), cards.Copies(1))
    loop.run()
    first = [r.text for _e, r in w.each(Reply)]
    for e, _r in w.each(Reply):
        w.destroy(e)
    assert first == ["goal met -- every wanted card is in the collection"]
    loop.tick()
    assert w.each(Reply) == []


def test_settling_after_goal_met_reports_no_hot_rules(loop):
    w = loop.world
    say(loop, "want dragon 1")
    w.replace(card(w, "dragon"), cards.Copies(1))
    settled = loop.run()
    assert settled.hot == []


def test_settling_leaves_nothing_transient_behind_but_keeps_goal_met(loop):
    w = loop.world
    say(loop, "want dragon 1")
    say(loop, "list dragon 40")       # bought, and meets the goal in one settle
    assert w.each(cards.Bought) == []
    assert w.each(cards.BadCommand) == []
    assert w.each(cards.Wanted) == []
    assert w.each(cards.Affordable) == []
    assert w.each(cards.FairPriced) == []
    assert w.each(Said) == []
    assert w.each(cards.GoalMet) != []
    assert w.each(cards.Announced) != []


# -- watches= correctness (PRINCIPLES.md: mutate something NOT watched) ---
#
# Each of these registers exactly the one rule under test on a bare Loop,
# so nothing else installed alongside it could be why the rule fired --
# only its own `watches=` declaration and its own body could be.

def test_watches_tag_affordable_wakes_on_listing_then_notices_a_purse_only_change():
    lp = Loop()
    w = lp.world
    w.spawn(cards.Purse(10))
    w.spawn(cards.RiskProfile(max_spend_per_trade=50, min_cash_reserve=0,
                               max_premium=0.25))
    entity = w.spawn(cards.Listing(1, 40))
    lp.rule(cards.tag_affordable, watches=(cards.Listing,))
    lp.tick()
    assert not w.has(entity, cards.Affordable)
    purse_entity, _p = w.first(cards.Purse)
    w.replace(purse_entity, cards.Purse(100))   # Purse, not Listing
    lp.tick()
    assert w.has(entity, cards.Affordable)


def test_watches_check_goal_wakes_on_wants_then_notices_a_copies_only_change():
    lp = Loop()
    w = lp.world
    dragon = w.spawn(cards.CardDef("dragon", "rare", 40), cards.Copies(0),
                      cards.Wants(1))
    lp.rule(cards.check_goal, watches=(cards.Wants,))
    lp.tick()
    assert w.the(cards.GoalMet) is None
    w.replace(dragon, cards.Copies(1))          # Copies, not Wants
    lp.tick()
    assert w.the(cards.GoalMet) is not None


def test_watches_decide_buy_wakes_on_listing_then_notices_the_tags_alone():
    lp = Loop()
    w = lp.world
    dragon = w.spawn(cards.CardDef("dragon", "rare", 40), cards.Copies(0),
                      cards.Wants(5))
    w.spawn(cards.Purse(100))
    w.spawn(cards.RiskProfile(max_spend_per_trade=50, min_cash_reserve=0,
                               max_premium=0.25))
    listing = w.spawn(cards.Listing(dragon, 40))
    lp.rule(cards.decide_buy, watches=(cards.Listing,))
    lp.tick()
    assert w.each(cards.Bought) == []           # tags never attached yet
    w.attach(listing, cards.Wanted(), cards.Affordable(), cards.FairPriced())
    lp.tick()
    assert w.each(cards.Bought) != []           # fires: Listing already
                                                  # populated this entity's
                                                  # whole life, so dormancy
                                                  # never re-gates on the tags
