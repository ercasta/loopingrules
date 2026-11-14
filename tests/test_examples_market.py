"""`examples.market` -- the richer trading island (rung 1). Covers selling,
the `decide` ranking bridge, and the cross-entity `strands` condition."""

from __future__ import annotations

import pytest

from examples import decide, market
from loopingrules.engine import said
from loopingrules.loop import Loop
from loopingrules_patterns import judge


def say(loop, line):
    w = loop.world
    said(w, "user", line)
    loop.run()
    return _drain_replies(w)


def say_all(loop, *lines):
    """Spawn every line, then settle ONCE."""
    w = loop.world
    for line in lines:
        said(w, "user", line)
    loop.run()
    return _drain_replies(w)


def _drain_replies(w):
    out = [w.get(entity, "text") for entity, _ in w.each("reply")]
    for entity, _ in w.each("reply"):
        w.destroy(entity)
    return out


def card(w, name):
    for entity, _tag, card_name in w.each("card", "name"):
        if card_name == name:
            return entity
    raise AssertionError("no such card in this world: %r" % name)


def held(w, name):
    return w.get(card(w, name), "held", 0)


def cash(w):
    return w.get(w.first("purse")[0], "cash")


@pytest.fixture
def loop():
    lp = Loop()
    market.install(lp, cash=100)
    return lp


# -- install / seeding ---------------------------------------------------

def test_install_seeds_catalog_cash_policy_and_tolerance(loop):
    w = loop.world
    assert len(w.each("card")) == len(market.DEFAULT_CATALOG)
    assert cash(w) == 100
    assert w.populated("policy")
    assert w.populated("max_level")


def test_install_does_not_reseed_singletons_on_restore():
    lp = Loop()
    w = lp.world
    purse = w.spawn()
    w.mark(purse, "purse")
    w.set(purse, "cash", 7)
    policy = w.spawn()
    w.mark(policy, "policy")
    w.set(policy, "max_price_ratio", 0.1)
    w.set(policy, "min_reserve", 2)
    w.set(policy, "sell_premium", 0.3)
    market.install(lp, cash=999)
    assert cash(w) == 7
    pol = w.first("policy")[0]
    assert (w.get(pol, "max_price_ratio"), w.get(pol, "min_reserve"),
            w.get(pol, "sell_premium")) == (0.1, 2, 0.3)


# -- hearing -------------------------------------------------------------

def test_hear_list_spawns_a_listing(loop):
    say(loop, "list dragon 30")
    w = loop.world
    dragon = card(w, "dragon")
    assert any(c == dragon.id and p == 30
               for _e, _t, c, p in w.each("listing", "card", "price"))


def test_hear_list_refuses_a_bad_price(loop):
    assert say(loop, "list dragon many") == ["! not a price: 'many'"]


def test_hear_want_sets_qty_and_priority(loop):
    say(loop, "want dragon 3 7")
    w = loop.world
    assert (w.get(card(w, "dragon"), "want_qty"),
            w.get(card(w, "dragon"), "want_priority")) == (3, 7)


def test_hear_want_defaults_qty_one_priority_zero(loop):
    say(loop, "want dragon")
    w = loop.world
    assert (w.get(card(w, "dragon"), "want_qty"),
            w.get(card(w, "dragon"), "want_priority")) == (1, 0)


def test_hear_want_replaces_rather_than_adds(loop):
    say(loop, "want dragon 1 0")
    say(loop, "want dragon 2 5")
    w = loop.world
    assert (w.get(card(w, "dragon"), "want_qty"),
            w.get(card(w, "dragon"), "want_priority")) == (2, 5)


def test_hear_offer_spawns_an_offer(loop):
    say(loop, "offer dragon 60")
    w = loop.world
    dragon = card(w, "dragon")
    assert any(c == dragon.id and p == 60
               for _e, _t, c, p in w.each("offer", "card", "price"))


def test_status_reports_cash_and_prioritized_goals(loop):
    say(loop, "want dragon 2 5")
    assert say(loop, "status") == ["cash: 100; dragon: 0/2 (priority 5)"]


# -- buying, through both bridges ----------------------------------------

def test_decide_buy_buys_a_wanted_affordable_fair_listing(loop):
    result = say(loop, "want dragon 1 0") + say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1
    assert cash(loop.world) == 60
    assert result == ["bought dragon for 40"]


def test_the_ranking_bridge_buys_the_best_rival_listing_only(loop):
    say_all(loop, "want dragon 1 0", "list dragon 50", "list dragon 30")
    assert held(loop.world, "dragon") == 1
    assert cash(loop.world) == 70
    remaining = [p for _e, _t, p in loop.world.each("listing", "price")]
    assert remaining == [50]           # the loser is left standing


def test_an_exact_tie_for_the_best_listing_buys_neither(loop):
    say_all(loop, "want dragon 1 0", "list dragon 40", "list dragon 40")
    assert held(loop.world, "dragon") == 0
    assert cash(loop.world) == 100


# -- the cross-entity stranding condition --------------------------------

def test_a_higher_priority_unmet_want_strands_a_low_priority_buy(loop):
    say(loop, "want dragon 1 0")
    say(loop, "want phoenix 1 10")     # higher priority, needs 125 cash
    say(loop, "list dragon 40")        # 100 - 40 = 60 < 125 -> strands
    w = loop.world
    listing = w.first("listing")[0]
    assert w.has(listing, "strands")
    assert held(w, "dragon") == 0
    assert cash(w) == 100


def test_an_equal_priority_want_does_not_strand(loop):
    say(loop, "want dragon 1 5")
    say(loop, "want phoenix 1 5")
    say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1


def test_a_lower_priority_want_does_not_strand(loop):
    say(loop, "want dragon 1 10")
    say(loop, "want phoenix 1 0")
    say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1


def test_a_satisfied_higher_priority_want_does_not_strand(loop):
    say(loop, "want phoenix 1 10")
    say(loop, "want dragon 1 0")
    loop.world.set(card(loop.world, "phoenix"), "held", 1)
    say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1


# -- selling, the second decision island ---------------------------------

def test_decide_sell_sells_a_held_card_when_the_offer_clears_the_premium(loop):
    say(loop, "want dragon 1 0")
    say(loop, "list dragon 40")        # held = 1, cash = 60
    result = say(loop, "offer dragon 60")   # 60 >= 40 * 1.25 -> surplus
    assert held(loop.world, "dragon") == 0
    assert cash(loop.world) == 120
    assert result == ["sold dragon for 60"]


def test_decide_sell_refuses_an_offer_below_the_premium(loop):
    say(loop, "want dragon 1 0")
    say(loop, "list dragon 40")
    say(loop, "offer dragon 45")       # 45 < 50 -> no surplus
    assert held(loop.world, "dragon") == 1
    assert cash(loop.world) == 60


def test_decide_sell_refuses_when_nothing_is_held(loop):
    say(loop, "offer dragon 100")      # surplus, but held = 0
    assert cash(loop.world) == 100
    assert loop.world.each("sold") == []


# -- the judge bridge, honored -------------------------------------------

def test_a_too_risky_listing_is_not_bought():
    lp = Loop()
    market.install(lp, cash=45)        # room 45; dragon at 40 uses 89%
    w = lp.world
    for line in ("want dragon 1 0", "list dragon 40"):
        said(w, "user", line)
    lp.run()
    listing = w.first("listing")[0]
    assert w.has(listing, "too_risky")
    assert w.has(listing, "wanted")
    assert held(w, "dragon") == 0
    assert cash(w) == 45


# -- settling ------------------------------------------------------------

def test_settling_after_a_buy_leaves_no_transient_tags_behind(loop):
    say(loop, "want dragon 1 0")
    say(loop, "list dragon 40")
    w = loop.world
    for name in ("wanted", "affordable", "fair_priced", "strands", "winner",
                 "too_risky"):
        assert w.each(name) == [], name
    assert w.each("said") == []


def test_settling_leaves_no_hot_rules(loop):
    w = loop.world
    said(w, "user", "want dragon 2 0")
    said(w, "user", "list dragon 40")
    assert loop.run().hot == []


# -- the two bridges are the same objects, unmodified --------------------

def test_market_imports_both_bridges_rather_than_reinventing_them():
    assert market.flag_too_risky is judge.flag_too_risky
    assert market.pick_winner is decide.pick_winner
