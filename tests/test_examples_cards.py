"""`examples.cards` -- one autonomous trading agent on a virtual market.

Under the attribute substrate (D8): a card is a `card_def` entity carrying
`name`/`rarity`/`value` plus its own `copies` and `wants`; a `listing` entity
carries `card` (a reference) and `price`; tags are flags. A `say(loop, line)`
helper spawns a `said`, runs to a settle, and hands back every `Reply` text.
"""

from __future__ import annotations

import pytest

from examples import cards
from loopingrules.engine import said
from loopingrules.loop import Loop


def say(loop, line):
    w = loop.world
    said(w, "user", line)
    loop.run()
    out = [w.get(entity, "text") for entity, _ in w.each("reply")]
    for entity, _ in w.each("reply"):
        w.destroy(entity)
    return out


def card(w, name):
    """The `card_def` entity named `name` -- a test-local lookup, not
    `cards._find_card`, so these tests exercise public behaviour only."""
    for entity, _tag, card_name in w.each("card_def", "name"):
        if card_name == name:
            return entity
    raise AssertionError("no such card in this world: %r" % name)


def _first(w, name):
    row = w.first(name)
    return None if row is None else row[0]


@pytest.fixture
def loop():
    lp = Loop()
    cards.install(lp, cash=100)
    return lp


# -- install / seeding --------------------------------------------------

def test_install_seeds_catalog_purse_and_risk_profile(loop):
    w = loop.world
    assert len(w.each("card_def")) == len(cards.DEFAULT_CATALOG)
    assert all(w.has(entity, "copies") for entity, _ in w.each("card_def"))
    assert w.get(_first(w, "purse"), "cash") == 100
    assert w.populated("risk_profile")


def test_install_does_not_overwrite_an_existing_card_def():
    lp = Loop()
    w = lp.world
    dragon = w.spawn()
    w.mark(dragon, "card_def")
    w.set(dragon, "name", "dragon")
    w.set(dragon, "value", 999)
    w.set(dragon, "copies", 3)
    cards.install(lp, catalog=cards.DEFAULT_CATALOG)
    assert w.get(dragon, "value") == 999
    assert w.get(dragon, "copies") == 3


def test_install_seeds_a_missing_catalog_entry_into_an_otherwise_seeded_world():
    lp = Loop()
    w = lp.world
    dragon = w.spawn()
    w.mark(dragon, "card_def")
    w.set(dragon, "name", "dragon")
    w.set(dragon, "value", 999)
    cards.install(lp, catalog=(("dragon", "rare", 40), ("goblin", "common", 5)))
    names = sorted(name for _e, _tag, name in w.each("card_def", "name"))
    assert names == ["dragon", "goblin"]
    assert w.get(card(w, "dragon"), "value") == 999      # untouched
    assert w.get(card(w, "goblin"), "copies") == 0


def test_install_does_not_re_seed_purse_or_risk_profile_on_restore():
    lp = Loop()
    w = lp.world
    purse = w.spawn()
    w.mark(purse, "purse")
    w.set(purse, "cash", 7)
    risk = w.spawn()
    w.mark(risk, "risk_profile")
    w.set(risk, "max_spend_per_trade", 1)
    w.set(risk, "min_cash_reserve", 2)
    w.set(risk, "max_premium", 0.1)
    cards.install(lp, cash=999)
    assert w.get(_first(w, "purse"), "cash") == 7
    got = w.first("risk_profile")[0]
    assert (w.get(got, "max_spend_per_trade"), w.get(got, "min_cash_reserve"),
            w.get(got, "max_premium")) == (1, 2, 0.1)


# -- hearing ------------------------------------------------------------

def test_hear_list_spawns_a_listing_for_a_known_card(loop):
    say(loop, "list dragon 30")
    w = loop.world
    dragon = card(w, "dragon")
    assert any(card_id == dragon.id and price == 30
               for _e, _tag, card_id, price in w.each("listing", "card", "price"))


def test_hear_list_refuses_an_unknown_card_name_with_bad_command(loop):
    assert say(loop, "list unicorn 10") == ["! unknown card 'unicorn'"]


def test_hear_list_refuses_an_unparseable_price_with_bad_command(loop):
    assert say(loop, "list dragon many") == ["! not a price: 'many'"]


def test_hear_want_spawns_wants_for_a_first_ask(loop):
    say(loop, "want dragon")
    assert loop.world.get(card(loop.world, "dragon"), "wants") == 1


def test_hear_want_replaces_not_duplicates_on_a_second_ask_for_the_same_card(loop):
    say(loop, "want dragon 2")
    say(loop, "want dragon 5")
    assert loop.world.get(card(loop.world, "dragon"), "wants") == 5


def test_hear_status_replies_with_cash_and_progress(loop):
    say(loop, "want dragon 1")
    assert say(loop, "status") == ["cash: 100; dragon: 0/1"]


# -- composing flags on a listing, independently ------------------------

def test_tag_wanted_attaches_when_short_and_detaches_once_satisfied(loop):
    w = loop.world
    say(loop, "want dragon 1")
    say(loop, "list dragon 999999")   # far over cap: never bought, stays put
    listing_entity = _first(w, "listing")
    assert w.has(listing_entity, "wanted")
    w.set(card(w, "dragon"), "copies", 1)
    loop.tick()
    assert not w.has(listing_entity, "wanted")


def test_tag_affordable_attaches_and_detaches_as_cash_changes(loop):
    w = loop.world
    say(loop, "list dragon 40")       # not wanted, so it just sits there
    listing_entity = _first(w, "listing")
    assert w.has(listing_entity, "affordable")
    w.set(_first(w, "purse"), "cash", 10)
    loop.tick()
    assert not w.has(listing_entity, "affordable")


def test_tag_fair_priced_reads_the_referenced_card_def_by_id(loop):
    w = loop.world
    say(loop, "list dragon 40")       # value 40, premium .25 -> limit 50
    say(loop, "list dragon 51")       # over the limit
    fair = w.first("listing", "fair_priced")
    over = [e for e, _tag, price in w.each("listing", "price") if price == 51][0]
    assert fair is not None and w.get(fair[0], "price") == 40
    assert not w.has(over, "fair_priced")


def test_tag_risk_level_reflects_the_fraction_of_room_the_price_would_use(loop):
    w = loop.world
    say(loop, "list dragon 40")       # cash 100, reserve 0 -> room 100
    listing_entity = _first(w, "listing")
    assert w.get(listing_entity, "risk_level") == pytest.approx(0.4)


def test_tag_risk_level_recomputes_as_cash_changes(loop):
    w = loop.world
    say(loop, "list dragon 40")
    listing_entity = _first(w, "listing")
    w.set(_first(w, "purse"), "cash", 45)   # room shrinks to 45
    loop.tick()
    assert w.get(listing_entity, "risk_level") == pytest.approx(40 / 45)


def test_tag_risk_level_caps_at_one_when_no_room_is_left():
    lp = Loop()
    cards.install(lp, cash=0)
    w = lp.world
    said(w, "user", "list dragon 40")
    lp.run()
    assert w.get(_first(w, "listing"), "risk_level") == 1.0


# -- acting -------------------------------------------------------------

def test_decide_buy_requires_all_three_tags_present(loop):
    say(loop, "list dragon 40")       # never wanted
    w = loop.world
    assert w.each("listing") != []
    assert w.each("bought") == []


def test_decide_buy_spends_purse_and_increments_copies_and_destroys_the_listing(loop):
    w = loop.world
    say(loop, "want dragon 2")        # qty 2, so one purchase doesn't finish it
    result = say(loop, "list dragon 40")
    assert w.get(card(w, "dragon"), "copies") == 1
    assert w.get(_first(w, "purse"), "cash") == 60
    assert w.each("listing") == []
    assert result == ["bought dragon for 40"]


def test_decide_buy_does_not_overspend_across_two_listings_in_one_tick():
    lp = Loop()
    cards.install(lp, cash=60)
    w = lp.world
    for line in ("want dragon 1", "want griffin 1",
                 "list dragon 40", "list griffin 40"):
        said(w, "user", line)
    lp.run()
    assert w.get(card(w, "dragon"), "copies") == 1
    assert w.get(card(w, "griffin"), "copies") == 0
    assert w.get(_first(w, "purse"), "cash") == 20    # only ONE purchase happened


def test_decide_buy_skips_a_listing_the_judge_marks_too_risky():
    lp = Loop()
    cards.install(lp, cash=45)
    w = lp.world
    said(w, "user", "want dragon 1")
    said(w, "user", "list dragon 40")
    lp.run()
    listing_entity = _first(w, "listing")
    assert w.has(listing_entity, "too_risky")
    assert w.has(listing_entity, "wanted")
    assert w.has(listing_entity, "affordable")
    assert w.has(listing_entity, "fair_priced")
    assert w.each("bought") == []
    assert w.get(_first(w, "purse"), "cash") == 45


def test_a_freshly_listed_card_can_be_bought_the_same_settle(loop):
    w = loop.world
    say(loop, "want dragon 5")
    said(w, "user", "list dragon 40")
    settled = loop.run()
    assert settled.hot == []
    assert w.get(card(w, "dragon"), "copies") == 1


def test_check_goal_fires_once_every_want_is_met_and_not_before(loop):
    w = loop.world
    say(loop, "want dragon 1")
    assert not w.populated("goal_met")
    w.set(card(w, "dragon"), "copies", 1)
    loop.tick()
    assert w.populated("goal_met")


def test_goal_met_is_announced_exactly_once(loop):
    w = loop.world
    say(loop, "want dragon 1")
    w.set(card(w, "dragon"), "copies", 1)
    loop.run()
    first = [w.get(e, "text") for e, _ in w.each("reply")]
    for e, _ in w.each("reply"):
        w.destroy(e)
    assert first == ["goal met -- every wanted card is in the collection"]
    loop.tick()
    assert w.each("reply") == []


def test_settling_after_goal_met_reports_no_hot_rules(loop):
    w = loop.world
    say(loop, "want dragon 1")
    w.set(card(w, "dragon"), "copies", 1)
    assert loop.run().hot == []


def test_settling_leaves_nothing_transient_behind_but_keeps_goal_met(loop):
    w = loop.world
    say(loop, "want dragon 1")
    say(loop, "list dragon 40")       # bought, and meets the goal in one settle
    assert w.each("bought") == []
    assert w.each("bad_command") == []
    assert w.each("listing") == []
    assert w.each("said") == []
    assert w.each("goal_met") != []
    assert w.each("announced") != []


# -- the auto-derived gate: reads, not a hand-written watches= ----------

def test_tag_affordable_wakes_on_a_purse_only_change():
    lp = Loop()
    w = lp.world
    purse = w.spawn()
    w.mark(purse, "purse")
    w.set(purse, "cash", 10)
    risk = w.spawn()
    w.mark(risk, "risk_profile")
    w.set(risk, "max_spend_per_trade", 50)
    w.set(risk, "min_cash_reserve", 0)
    w.set(risk, "max_premium", 0.25)
    listing = w.spawn()
    w.mark(listing, "listing")
    w.set(listing, "card", 1)
    w.set(listing, "price", 40)
    lp.rule(cards.tag_affordable)
    lp.tick()
    assert not w.has(listing, "affordable")
    w.set(purse, "cash", 100)
    lp.tick()
    assert w.has(listing, "affordable")


def test_check_goal_wakes_on_wants_then_notices_a_copies_only_change():
    lp = Loop()
    w = lp.world
    dragon = w.spawn()
    w.mark(dragon, "card_def")
    w.set(dragon, "name", "dragon")
    w.set(dragon, "value", 40)
    w.set(dragon, "copies", 0)
    w.set(dragon, "wants", 1)
    lp.rule(cards.check_goal)
    lp.tick()
    assert not w.populated("goal_met")
    w.set(dragon, "copies", 1)
    lp.tick()
    assert w.populated("goal_met")


def test_decide_buy_wakes_on_listing_then_notices_the_tags_alone():
    lp = Loop()
    w = lp.world
    dragon = w.spawn()
    w.mark(dragon, "card_def")
    w.set(dragon, "name", "dragon")
    w.set(dragon, "value", 40)
    w.set(dragon, "copies", 0)
    w.set(dragon, "wants", 5)
    purse = w.spawn()
    w.mark(purse, "purse")
    w.set(purse, "cash", 100)
    risk = w.spawn()
    w.mark(risk, "risk_profile")
    w.set(risk, "max_spend_per_trade", 50)
    w.set(risk, "min_cash_reserve", 0)
    w.set(risk, "max_premium", 0.25)
    listing = w.spawn()
    w.mark(listing, "listing")
    w.set(listing, "card", dragon)
    w.set(listing, "price", 40)
    lp.rule(cards.decide_buy)
    lp.tick()
    assert w.each("bought") == []               # tags never attached yet
    w.mark(listing, "wanted")
    w.mark(listing, "affordable")
    w.mark(listing, "fair_priced")
    lp.tick()
    assert w.each("bought") != []
