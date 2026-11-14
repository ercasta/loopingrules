"""`market` -- a richer trading island than `examples.cards`: an agent that
buys AND sells, holds PRIORITIZED wants, and picks the best rival listing
through a second bridge. Kept in `examples/`.

## Under the attribute substrate (D8)

A card is a `card` entity carrying `name`/`value` plus its own `held` and
`want_qty`/`want_priority`; a `listing`/`offer` carries `card` (a reference)
and `price`; the purse carries `cash`; the policy singleton carries the three
risk knobs. Tags are flags.

## The bridges

`tag_risk` projects onto `loopingrules_patterns.judge`'s `risk_level`/
`risk_reason`; `nominate` projects onto `examples.decide`'s `occasion`/
`score` (score = `value - price`), and `decide.pick_winner` sets a `winner`
flag back. `decide_buy` reads four independently-produced flags.
"""

from __future__ import annotations

from examples.decide import pick_winner
from loopingrules.engine import reply
from loopingrules_patterns.judge import flag_too_risky, seed_tolerance


DEFAULT_CATALOG = (
    ("dragon", 40),
    ("phoenix", 100),
    ("goblin", 5),
    ("wolf", 8),
    ("griffin", 35),
)


def _find_card(w, name: str):
    """The `card` entity named `name`, case-insensitively, or `None`."""
    for entity, _tag, card_name in w.each("card", "name"):
        if card_name.lower() == name.lower():
            return entity
    return None


def _parse_int(text: str):
    try:
        return int(text)
    except ValueError:
        return None


def _bad(w, text: str, why: str) -> None:
    entity = w.spawn()
    w.mark(entity, "bad_command")
    w.set(entity, "text", text)
    w.set(entity, "why", why)


def _held(w, card) -> int:
    return w.get(card, "held", 0)


def _cash(w):
    row = w.first("purse")
    return (None, 0) if row is None else (row[0], w.get(row[0], "cash"))


# -- hearing ------------------------------------------------------------

def hear_list(w) -> None:
    """`list <card> <price>` -> a `listing`, or a `bad_command`."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "list":
            continue
        w.destroy(entity)
        if len(words) != 3:
            _bad(w, text, "usage: list <card> <price>")
            continue
        card = _find_card(w, words[1])
        if card is None:
            _bad(w, text, "unknown card %r" % words[1])
            continue
        price = _parse_int(words[2])
        if price is None:
            _bad(w, text, "not a price: %r" % words[2])
            continue
        listing = w.spawn()
        w.mark(listing, "listing")
        w.set(listing, "card", card)
        w.set(listing, "price", price)


def hear_want(w) -> None:
    """`want <card> [qty] [priority]` -> `want_qty`/`want_priority` on the
    card entity."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "want":
            continue
        w.destroy(entity)
        if len(words) not in (2, 3, 4):
            _bad(w, text, "usage: want <card> [qty] [priority]")
            continue
        card = _find_card(w, words[1])
        if card is None:
            _bad(w, text, "unknown card %r" % words[1])
            continue
        qty, priority = 1, 0
        if len(words) >= 3:
            qty = _parse_int(words[2])
            if qty is None or qty < 1:
                _bad(w, text, "not a quantity: %r" % words[2])
                continue
        if len(words) == 4:
            priority = _parse_int(words[3])
            if priority is None:
                _bad(w, text, "not a priority: %r" % words[3])
                continue
        w.set(card, "want_qty", qty)
        w.set(card, "want_priority", priority)


def hear_offer(w) -> None:
    """`offer <card> <price>` -> an `offer` to buy a held card at `price`."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "offer":
            continue
        w.destroy(entity)
        if len(words) != 3:
            _bad(w, text, "usage: offer <card> <price>")
            continue
        card = _find_card(w, words[1])
        if card is None:
            _bad(w, text, "unknown card %r" % words[1])
            continue
        price = _parse_int(words[2])
        if price is None:
            _bad(w, text, "not a price: %r" % words[2])
            continue
        offer = w.spawn()
        w.mark(offer, "offer")
        w.set(offer, "card", card)
        w.set(offer, "price", price)


def hear_status(w) -> None:
    """`status` -> cash, and per wanted card the held/goal and priority."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "status":
            continue
        w.destroy(entity)
        lines = ["cash: %d" % _cash(w)[1]]
        rows = sorted(w.each("card", "name", "want_qty", "want_priority"),
                      key=lambda row: row[2])
        if not rows:
            lines.append("no goal set")
        for card_entity, _ctag, card_name, qty, priority in rows:
            lines.append("%s: %d/%d (priority %d)"
                         % (card_name, _held(w, card_entity), qty, priority))
        reply(w, "user", "; ".join(lines))


# -- composing flags on a listing, independently ------------------------

def tag_wanted(w) -> None:
    """`wanted` iff this listing's card is still short of its want."""
    for entity, _tag, card in w.each("listing", "card"):
        if w.has(card, "want_qty") and _held(w, card) < w.get(card, "want_qty"):
            w.mark(entity, "wanted")
        else:
            w.unmark(entity, "wanted")


def tag_affordable(w) -> None:
    """`affordable` iff the price fits the cash-minus-reserve room."""
    row = w.first("policy")
    if row is None:
        return
    room = _cash(w)[1] - w.get(row[0], "min_reserve")
    for entity, _tag, price in w.each("listing", "price"):
        if price <= room:
            w.mark(entity, "affordable")
        else:
            w.unmark(entity, "affordable")


def tag_fair_priced(w) -> None:
    """`fair_priced` iff the price is within the tolerated premium over the
    card's own catalog value."""
    row = w.first("policy")
    if row is None:
        return
    ratio = w.get(row[0], "max_price_ratio")
    for entity, _tag, card, price in w.each("listing", "card", "price"):
        value = w.get(card, "value")
        if value is None:
            w.unmark(entity, "fair_priced")
            continue
        if price <= value * (1 + ratio):
            w.mark(entity, "fair_priced")
        else:
            w.unmark(entity, "fair_priced")


def tag_risk(w) -> None:
    """`risk_level`/`risk_reason`: how much of the free room the price would
    use."""
    row = w.first("policy")
    if row is None:
        return
    room = _cash(w)[1] - w.get(row[0], "min_reserve")
    for entity, _tag, price in w.each("listing", "price"):
        level = 1.0 if room <= 0 else min(1.0, price / room)
        w.set(entity, "risk_level", level)
        w.set(entity, "risk_reason",
              "would use %.0f%% of the %d cash still free to spend"
              % (level * 100, max(room, 0)))


def tag_strands(w) -> None:
    """`strands` iff buying this listing would leave cash below what a
    STRICTLY HIGHER-PRIORITY, still-unmet want needs at its fair price."""
    policy = w.first("policy")
    if policy is None:
        return
    ratio = w.get(policy[0], "max_price_ratio")
    cash = _cash(w)[1]
    wants = w.each("card", "want_qty", "want_priority", "value")
    for entity, _tag, card, price in w.each("listing", "card", "price"):
        if not w.has(card, "want_qty"):
            w.unmark(entity, "strands")
            continue
        mine = w.get(card, "want_priority")
        strands = False
        for other, _otag, qty, priority, value in wants:
            if priority <= mine:
                continue
            if _held(w, other) >= qty:
                continue
            needed = value * (1 + ratio)
            if cash - price < needed:
                strands = True
                break
        if strands:
            w.mark(entity, "strands")
        else:
            w.unmark(entity, "strands")


def tag_surplus(w) -> None:
    """`surplus` iff an `offer` for a held card clears the tolerated premium
    over value -- the sell-side mirror of `tag_fair_priced`."""
    row = w.first("policy")
    if row is None:
        return
    premium = w.get(row[0], "sell_premium")
    for entity, _tag, card, price in w.each("offer", "card", "price"):
        value = w.get(card, "value")
        if value is None:
            w.unmark(entity, "surplus")
            continue
        if price >= value * (1 + premium):
            w.mark(entity, "surplus")
        else:
            w.unmark(entity, "surplus")


# -- the ranking bridge -------------------------------------------------

def nominate(w) -> None:
    """Project every listing onto `examples.decide`'s `occasion`/`score`:
    `occasion` is the listing's own card, `score` = `value - price`."""
    for entity, _tag, card, price in w.each("listing", "card", "price"):
        value = w.get(card, "value")
        if value is None:
            continue
        w.set(entity, "occasion", card)
        w.set(entity, "score", float(value - price))


# -- acting -------------------------------------------------------------

def decide_buy(w) -> None:
    """Every listing Wanted, Affordable, FairPriced, the judge's `winner`
    among its rivals, and neither `too_risky` nor `strands` -> bought."""
    policy = w.first("policy")
    if policy is None:
        return
    reserve = w.get(policy[0], "min_reserve")
    for row in w.each("listing", "card", "price", "wanted", "affordable",
                      "fair_priced", "winner",
                      without=("too_risky", "strands")):
        entity, _tag, card, price = row[0], row[1], row[2], row[3]
        if not w.has(card, "want_qty"):
            continue
        have = _held(w, card)
        if have >= w.get(card, "want_qty"):
            continue
        purse, cash = _cash(w)
        if purse is None or price > cash - reserve:
            continue
        w.set(purse, "cash", cash - price)
        w.set(card, "held", have + 1)
        w.destroy(entity)
        bought = w.spawn()
        w.mark(bought, "bought")
        w.set(bought, "card", card)
        w.set(bought, "price", price)


def decide_sell(w) -> None:
    """Every offer carrying `surplus` for a card the agent holds -> sold."""
    for entity, _tag, card, price, _surplus in w.each("offer", "card", "price",
                                                      "surplus"):
        have = _held(w, card)
        if have < 1:
            continue
        w.set(card, "held", have - 1)
        purse, cash = _cash(w)
        if purse is not None:
            w.set(purse, "cash", cash + price)
        w.destroy(entity)
        sold = w.spawn()
        w.mark(sold, "sold")
        w.set(sold, "card", card)
        w.set(sold, "price", price)


# -- replying -----------------------------------------------------------

def reply_bought(w) -> None:
    for entity, _tag, card, price in w.each("bought", "card", "price"):
        w.destroy(entity)
        name = w.get(card, "name")
        reply(w, "user", "bought %s for %d"
              % (name if name else "card #%d" % card, price))


def reply_sold(w) -> None:
    for entity, _tag, card, price in w.each("sold", "card", "price"):
        w.destroy(entity)
        name = w.get(card, "name")
        reply(w, "user", "sold %s for %d"
              % (name if name else "card #%d" % card, price))


def reply_bad_command(w) -> None:
    for entity, _tag, why in w.each("bad_command", "why"):
        w.destroy(entity)
        reply(w, "user", "! %s" % why)


RULES = (hear_list, hear_want, hear_offer, hear_status,
         tag_wanted, tag_affordable, tag_fair_priced, tag_risk,
         tag_strands, nominate, pick_winner, flag_too_risky, tag_surplus,
         decide_buy, decide_sell,
         reply_bought, reply_sold, reply_bad_command)


def install(loop, cash: int = 100, catalog=DEFAULT_CATALOG) -> None:
    """Register every rule (including the two bridge rules, unmodified),
    then seed catalog, purse, policy and the judge's tolerance."""
    loop.rule(hear_list)
    loop.rule(hear_want)
    loop.rule(hear_offer)
    loop.rule(hear_status)
    loop.rule(tag_wanted)
    loop.rule(tag_affordable)
    loop.rule(tag_fair_priced)
    loop.rule(tag_risk)
    loop.rule(tag_strands)
    loop.rule(nominate)
    loop.rule(pick_winner)
    loop.rule(flag_too_risky)
    loop.rule(tag_surplus)
    loop.rule(decide_buy)
    loop.rule(decide_sell)
    loop.rule(reply_bought)
    loop.rule(reply_sold)
    loop.rule(reply_bad_command)

    world = loop.world
    for name, value in catalog:
        if _find_card(world, name) is None:
            entity = world.spawn()
            world.mark(entity, "card")
            world.set(entity, "name", name)
            world.set(entity, "value", value)
            world.set(entity, "held", 0)
    if not world.populated("purse"):
        purse = world.spawn()
        world.mark(purse, "purse")
        world.set(purse, "cash", cash)
    if not world.populated("policy"):
        policy = world.spawn()
        world.mark(policy, "policy")
        world.set(policy, "max_price_ratio", 0.25)
        world.set(policy, "min_reserve", 0)
        world.set(policy, "sell_premium", 0.25)
    seed_tolerance(world, 0.8)
