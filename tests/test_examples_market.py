"""`examples.market` -- the richer trading island (rung 1 of
`docs/tuning.md`'s ladder). Convention mirrors `tests/test_examples_
cards.py`: a `say(loop, line)` helper spawns a `Said`, runs the loop to a
settle, and hands back every `Reply` text. Covers the three additions the
domain exists for -- selling, the `decide` ranking bridge, and the
cross-entity `Strands` condition -- plus the pieces it shares with `cards`.
"""

import pytest

from examples import decide, judge, market
from loopingrules.engine import Reply, Said
from loopingrules.loop import Loop


def say(loop, line):
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
            if w.destroy(entity) or True]


def say_all(loop, *lines):
    """Spawn every line, then settle ONCE -- so rules that need to see all
    of them at the same time (rival listings, for instance) actually do."""
    w = loop.world
    for line in lines:
        w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
            if w.destroy(entity) or True]


def card(w, name):
    for entity, definition in w.all(market.Card):
        if definition.name == name:
            return entity
    raise AssertionError("no such card in this world: %r" % name)


def held(w, name):
    component = w.get(card(w, name), market.Held)
    return component.count if component else 0


@pytest.fixture
def loop():
    lp = Loop()
    market.install(lp, cash=100)
    return lp


# -- install / seeding ---------------------------------------------------

def test_install_seeds_catalog_cash_policy_and_tolerance(loop):
    w = loop.world
    assert len(w.all(market.Card)) == len(market.DEFAULT_CATALOG)
    assert w.the(market.Cash) == market.Cash(100)
    assert w.the(market.Policy) is not None
    assert w.the(judge.RiskTolerance) is not None


def test_install_does_not_reseed_singletons_on_restore():
    lp = Loop()
    w = lp.world
    w.spawn(market.Cash(7))
    w.spawn(market.Policy(0.1, 2, 0.3))
    market.install(lp, cash=999)
    assert w.the(market.Cash) == market.Cash(7)
    assert w.the(market.Policy) == market.Policy(0.1, 2, 0.3)


# -- hearing -------------------------------------------------------------

def test_hear_list_spawns_a_listing(loop):
    say(loop, "list dragon 30")
    dragon = card(loop.world, "dragon")
    assert any(listing.card == dragon.id and listing.price == 30
               for _e, listing in loop.world.each(market.Listing))


def test_hear_list_refuses_a_bad_price(loop):
    assert say(loop, "list dragon many") == ["! not a price: 'many'"]


def test_hear_want_sets_qty_and_priority(loop):
    say(loop, "want dragon 3 7")
    assert loop.world.get(card(loop.world, "dragon"), market.Want) == market.Want(3, 7)


def test_hear_want_defaults_qty_one_priority_zero(loop):
    say(loop, "want dragon")
    assert loop.world.get(card(loop.world, "dragon"), market.Want) == market.Want(1, 0)


def test_hear_want_replaces_rather_than_adds(loop):
    say(loop, "want dragon 1 0")
    say(loop, "want dragon 2 5")
    assert loop.world.get_all(card(loop.world, "dragon"), market.Want) == [market.Want(2, 5)]


def test_hear_offer_spawns_an_offer(loop):
    say(loop, "offer dragon 60")
    dragon = card(loop.world, "dragon")
    assert any(offer.card == dragon.id and offer.price == 60
               for _e, offer in loop.world.each(market.Offer))


def test_status_reports_cash_and_prioritized_goals(loop):
    say(loop, "want dragon 2 5")
    assert say(loop, "status") == ["cash: 100; dragon: 0/2 (priority 5)"]


# -- buying, through both bridges ----------------------------------------

def test_decide_buy_buys_a_wanted_affordable_fair_listing(loop):
    result = say(loop, "want dragon 1 0") + say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1
    assert loop.world.the(market.Cash) == market.Cash(60)
    assert result == ["bought dragon for 40"]


def test_the_ranking_bridge_buys_the_best_rival_listing_only(loop):
    """Two listings for the SAME card are rivals onto `decide.Option`/
    `Score`; `pick_winner` tags the higher-scoring (cheaper) one, and only
    it is bought. This is the second bridge -- `cards` drove only
    `examples.judge`, this island drives `examples.decide` too."""
    say_all(loop, "want dragon 1 0", "list dragon 50", "list dragon 30")
    assert held(loop.world, "dragon") == 1
    assert loop.world.the(market.Cash) == market.Cash(70)
    remaining = [listing.price for _e, listing in loop.world.each(market.Listing)]
    assert remaining == [50]           # the loser is left standing


def test_an_exact_tie_for_the_best_listing_buys_neither(loop):
    # `decide.pick_winner` refuses to break a tie; `decide_buy` then finds
    # no `Winner` and buys nothing -- refuse rather than guess, same as the
    # bridge itself.
    say_all(loop, "want dragon 1 0", "list dragon 40", "list dragon 40")
    assert held(loop.world, "dragon") == 0
    assert loop.world.the(market.Cash) == market.Cash(100)


# -- the cross-entity stranding condition --------------------------------

def test_a_higher_priority_unmet_want_strands_a_low_priority_buy(loop):
    say(loop, "want dragon 1 0")
    say(loop, "want phoenix 1 10")     # higher priority, needs 125 cash
    say(loop, "list dragon 40")        # 100 - 40 = 60 < 125 -> Strands
    listing, _component = loop.world.first(market.Listing)
    assert loop.world.has(listing, market.Strands)
    assert held(loop.world, "dragon") == 0
    assert loop.world.the(market.Cash) == market.Cash(100)


def test_an_equal_priority_want_does_not_strand(loop):
    # Equal priorities are rivals this rule refuses to rank, so neither
    # blocks the other.
    say(loop, "want dragon 1 5")
    say(loop, "want phoenix 1 5")
    say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1


def test_a_lower_priority_want_does_not_strand(loop):
    say(loop, "want dragon 1 10")
    say(loop, "want phoenix 1 0")      # lower priority than dragon
    say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1


def test_a_satisfied_higher_priority_want_does_not_strand(loop):
    say(loop, "want phoenix 1 10")
    say(loop, "want dragon 1 0")
    # phoenix already held, so its want is met and cannot strand dragon
    loop.world.replace(card(loop.world, "phoenix"), market.Held(1))
    say(loop, "list dragon 40")
    assert held(loop.world, "dragon") == 1


# -- selling, the second decision island ---------------------------------

def test_decide_sell_sells_a_held_card_when_the_offer_clears_the_premium(loop):
    say(loop, "want dragon 1 0")
    say(loop, "list dragon 40")        # held = 1, cash = 60
    result = say(loop, "offer dragon 60")   # 60 >= 40 * 1.25 = 50 -> Surplus
    assert held(loop.world, "dragon") == 0
    assert loop.world.the(market.Cash) == market.Cash(120)
    assert result == ["sold dragon for 60"]


def test_decide_sell_refuses_an_offer_below_the_premium(loop):
    say(loop, "want dragon 1 0")
    say(loop, "list dragon 40")
    say(loop, "offer dragon 45")       # 45 < 50 -> no Surplus
    assert held(loop.world, "dragon") == 1
    assert loop.world.the(market.Cash) == market.Cash(60)


def test_decide_sell_refuses_when_nothing_is_held(loop):
    say(loop, "offer dragon 100")      # Surplus, but held = 0
    assert loop.world.the(market.Cash) == market.Cash(100)
    assert loop.world.each(market.Sold) == []


# -- the judge bridge, honored -------------------------------------------

def test_a_too_risky_listing_is_not_bought(loop):
    lp = Loop()
    market.install(lp, cash=45)        # room 45; dragon at 40 uses 89%
    w = lp.world
    for line in ("want dragon 1 0", "list dragon 40"):
        w.spawn(Said("user", line))
    lp.run()
    listing, _component = w.first(market.Listing)
    assert w.has(listing, judge.TooRisky)
    assert w.has(listing, market.Wanted)
    assert held(w, "dragon") == 0
    assert w.the(market.Cash) == market.Cash(45)


# -- settling ------------------------------------------------------------

def test_settling_after_a_buy_leaves_no_transient_tags_behind(loop):
    say(loop, "want dragon 1 0")
    say(loop, "list dragon 40")
    w = loop.world
    for kind in (market.Wanted, market.Affordable, market.FairPriced,
                 market.Strands, market.Winner, judge.TooRisky):
        assert w.each(kind) == [], kind.__name__
    assert w.each(Said) == []


def test_settling_leaves_no_hot_rules(loop):
    w = loop.world
    w.spawn(Said("user", "want dragon 2 0"))
    w.spawn(Said("user", "list dragon 40"))
    settled = loop.run()
    assert settled.hot == []


# -- the two bridges are the same objects, unmodified --------------------

def test_market_imports_both_bridges_rather_than_reinventing_them():
    assert market.flag_too_risky is judge.flag_too_risky
    assert market.pick_winner is decide.pick_winner
    assert market.Risk is judge.Risk
    assert market.Option is decide.Option
