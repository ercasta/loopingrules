"""`adapters` -- a probe: can a domain keep its OWN ownership representation
and still take part in a shared exchange, through an explicit adapter?

Under the attribute substrate (D8): `Agent`/`Coin` are flags the adapter
invents; `Holding`/`Movement` are `trade`'s tagged entities; `cards`'
ownership is the purse's `cash` and each card's `copies`.
"""

from __future__ import annotations

from examples import cards, trade
from loopingrules.loop import Loop


# -- the seam: cards <-> trade -------------------------------------------

def _agent(w):
    row = w.first("agent")
    return None if row is None else row[0]


def _coin(w):
    row = w.first("coin")
    return None if row is None else row[0]


def _holding(w, holder, thing):
    for entity, _tag, h, t, amount in w.each("holding", "holder", "thing",
                                             "amount"):
        if h == holder and t == thing:
            return entity, amount
    return None, None


def _amount(w, holder, thing):
    _entity, amount = _holding(w, holder, thing)
    return amount


def _seed_holding(w, holder, thing, amount):
    """Create a `holding` for this pair ONLY if none exists -- a one-shot
    projection, never overwriting, so it cannot fight `absorb_holdings`."""
    if _holding(w, holder, thing)[0] is None:
        entity = w.spawn()
        w.mark(entity, "holding")
        w.set(entity, "holder", holder)
        w.set(entity, "thing", thing)
        w.set(entity, "amount", amount)


def project_ownership(w) -> None:
    """cards -> trade, SEED-ONLY: for the purse and every card's own copies,
    make sure a `holding` exists for (agent, thing). Idempotent."""
    agent = _agent(w)
    coin = _coin(w)
    if agent is None or coin is None:
        return
    purse = w.first("purse")
    if purse is not None:
        _seed_holding(w, agent.id, coin.id, w.get(purse[0], "cash", 0))
    for entity, _tag, _name, copies in w.each("card_def", "name", "copies"):
        _seed_holding(w, agent.id, entity.id, copies)


def absorb_holdings(w) -> None:
    """trade -> cards, AUTHORITATIVE: write the canonical amounts back into
    cards' own shapes -- the purse's `cash` and each card's `copies`."""
    agent = _agent(w)
    coin = _coin(w)
    if agent is None or coin is None:
        return
    cash = _amount(w, agent.id, coin.id)
    if cash is not None:
        found = w.first("purse")
        if found is not None:
            w.set(found[0], "cash", cash)
    for entity, _tag in w.each("card_def"):
        held = _amount(w, agent.id, entity.id)
        if held is not None:
            w.set(entity, "copies", held)


RULES = (project_ownership, absorb_holdings)


def install(loop) -> None:
    """Compose both adapter rules with `trade`'s own, then seed the two
    handles the adapter invents."""
    loop.rule(project_ownership)
    trade.install(loop)
    loop.rule(absorb_holdings)
    world = loop.world
    if _agent(world) is None:
        world.mark(world.spawn(), "agent")
    if _coin(world) is None:
        world.mark(world.spawn(), "coin")


# -- driving it ----------------------------------------------------------

def propose_buy(w, thing, price) -> None:
    """Describe a purchase as a pair of movements and agree to them."""
    agent = _agent(w)
    coin = _coin(w)
    for holder, subject, delta in ((agent.id, coin.id, -price),
                                   (agent.id, thing.id, +1)):
        movement = w.spawn()
        w.mark(movement, "movement")
        w.set(movement, "holder", holder)
        w.set(movement, "thing", subject)
        w.set(movement, "delta", delta)
        w.mark(movement, "agreed")


def _card_entity(w, name):
    for entity, _tag, card_name in w.each("card_def", "name"):
        if card_name == name:
            return entity
    raise AssertionError("no such card: %r" % name)


def _copies_of(w, name):
    return w.get(_card_entity(w, name), "copies", 0)


def snapshot(w):
    """cards' own view of ownership, in its own shapes."""
    purse = w.first("purse")
    return {
        "cash": w.get(purse[0], "cash") if purse is not None else None,
        "copies": {name: w.get(entity, "copies", 0)
                   for entity, _tag, name in w.each("card_def", "name")},
    }


def cards_world(cash=100, held=None):
    loop = Loop()
    cards.install(loop, cash=cash)
    w = loop.world
    for name, count in (held or {}).items():
        w.set(_card_entity(w, name), "copies", count)
    return loop, w


def round_trip(cash=100, held=None):
    """cards -> trade -> cards, with NO movement: is it the identity?"""
    loop, w = cards_world(cash, held)
    before = snapshot(w)
    install(loop)
    loop.run()
    after = snapshot(w)
    return before, after


def demo_purchase(card_name="dragon", price=40, cash=100):
    """A purchase performed entirely in `trade`'s canonical shape -- two
    movements, agreed -- then absorbed back into cards."""
    loop, w = cards_world(cash)
    install(loop)
    loop.run()                                 # seed holdings from cards
    propose_buy(w, _card_entity(w, card_name), price)
    loop.run()                                 # move, then absorb
    return w


def residual():
    """Everything in cards' own representation that has NO counterpart in
    `trade`'s shape."""
    return {
        "value": "card value -- worth, not amount",
        "wants": "wants -- a goal, not a holding",
        "max_premium": "risk max_premium -- policy",
        "max_spend_per_trade": "risk max_spend_per_trade -- policy",
        "min_cash_reserve": "risk min_cash_reserve -- policy",
        "decision": "wanted/affordable/fair_priced, too_risky -- decision",
    }


def report():
    """The whole probe in one dict: does ownership round-trip, what the
    adapter had to invent, where the purchase landed, and the verdict."""
    before, after = round_trip(held={"dragon": 2, "goblin": 1})
    purchased = demo_purchase()
    _bare_loop, bare = cards_world()

    ownership_round_trips = before == after
    purchase_landed = (_copies_of(purchased, "dragon") == 1
                       and purchased.get(purchased.first("purse")[0], "cash") == 60)
    return {
        "ownership_round_trips": ownership_round_trips,
        "purchase_landed_in_cards": purchase_landed,
        "adapter_invents": ("Agent", "Coin"),
        "cards_alone_counts": {
            "holdings": len(bare.each("holding")),
            "holders": len(bare.each("agent")),
        },
        "no_home_in_trade": tuple(sorted(residual())),
        "verdict": ("split: ownership adapts losslessly; policy stays island"
                    if ownership_round_trips and purchase_landed
                    else "representations differ in magnitude too"),
    }
