"""`cards` -- one autonomous trading agent, reacting to a virtual card
market according to a goal (which cards it wants) and a risk profile (how
much it will spend, how much premium over fair value it will tolerate).

## The actual point: composing tags nobody wrote the composition of

The interesting mechanism here is not the market, it's `decide_buy` reading
three flags -- `wanted`, `affordable`, `fair_priced` -- set on one `listing`
entity by three rules that share no code and no awareness of each other.

## Under the attribute substrate (D8)

There are no component classes. A card in the catalog is an entity tagged
`card_def`, carrying `name`/`rarity`/`value`; the agent's own holdings are
the `copies` attribute ON that same entity, and a stated goal is the `wants`
attribute on it. A `listing` is an entity carrying `card` (a reference) and
`price`. A tag is a flag; a short-lived outcome (`bought`, `bad_command`) is
its own tagged entity. See `docs/plan-attributes.md`.

## A fourth tag, projected onto a judge this domain does not own

`tag_risk_level` projects a fact this domain understands (how much of the
room to spend this purchase would use) onto `loopingrules_patterns.judge`'s
`risk_level`/`risk_reason`, a convention this domain does not define and a
threshold (`max_level`) it does not own. `judge.flag_too_risky` is the actual
judge, and it has never heard of a listing, a purse, or a card.
"""

from __future__ import annotations

from loopingrules.engine import reply
from loopingrules_patterns.judge import flag_too_risky, seed_tolerance

# Shape tags and attribute names (used as literals in the rules below, so
# `analyze` can attribute them; named here for readers and tests).
CARD_DEF = "card_def"
LISTING = "listing"
PURSE = "purse"
RISK_PROFILE = "risk_profile"
BOUGHT = "bought"
BAD_COMMAND = "bad_command"
GOAL_MET = "goal_met"

DEFAULT_CATALOG = (
    ("dragon", "rare", 40),
    ("phoenix", "legendary", 100),
    ("goblin", "common", 5),
    ("wolf", "common", 8),
    ("griffin", "rare", 35),
)


def _find_card(w, name: str):
    """The `card_def` entity named `name`, case-insensitively, or `None`.
    Never guesses between two -- `install` never seeds a duplicate name."""
    for entity, _tag, card_name in w.each("card_def", "name"):
        if card_name.lower() == name.lower():
            return entity
    return None


def _parse_int(text: str):
    """`int(text)`, or `None`."""
    try:
        return int(text)
    except ValueError:
        return None


def _bad(w, text: str, why: str) -> None:
    entity = w.spawn()
    w.mark(entity, "bad_command")
    w.set(entity, "text", text)
    w.set(entity, "why", why)


# -- hearing -----------------------------------------------------------

def hear_list(w) -> None:
    """`list <card> <price>` -> a `listing`, or a `bad_command` naming what
    was wrong. Claims (`destroy`s) the line the moment its own verb matches."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "list":
            continue
        w.destroy(entity)
        if len(words) != 3:
            _bad(w, text, "usage: list <card> <price>")
            continue
        name, price_text = words[1], words[2]
        card = _find_card(w, name)
        if card is None:
            _bad(w, text, "unknown card %r" % name)
            continue
        price = _parse_int(price_text)
        if price is None:
            _bad(w, text, "not a price: %r" % price_text)
            continue
        listing = w.spawn()
        w.mark(listing, "listing")
        w.set(listing, "card", card)
        w.set(listing, "price", price)


def hear_want(w) -> None:
    """`want <card> [qty]` (default `qty=1`) -> the `wants` attribute on that
    card's own `card_def` entity, replacing whatever it carried."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "want":
            continue
        w.destroy(entity)
        if len(words) not in (2, 3):
            _bad(w, text, "usage: want <card> [qty]")
            continue
        card = _find_card(w, words[1])
        if card is None:
            _bad(w, text, "unknown card %r" % words[1])
            continue
        qty = 1
        if len(words) == 3:
            qty = _parse_int(words[2])
            if qty is None or qty < 1:
                _bad(w, text, "not a quantity: %r" % words[2])
                continue
        w.set(card, "wants", qty)


def hear_status(w) -> None:
    """`status` -> cash, goal progress per wanted card, and whether the goal
    is met -- said directly, no outcome fact."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "status":
            continue
        w.destroy(entity)
        purse = w.first("purse")
        cash = w.get(purse[0], "cash") if purse else 0
        lines = ["cash: %d" % cash]
        wanted = sorted(((row[0], row[2], row[3])
                         for row in w.each("card_def", "name", "wants")),
                        key=lambda row: row[1])
        if not wanted:
            lines.append("no goal set")
        for card_entity, name, want in wanted:
            have = w.get(card_entity, "copies", 0)
            lines.append("%s: %d/%d" % (name, have, want))
        if w.populated("goal_met"):
            lines.append("goal met")
        reply(w, "user", "; ".join(lines))


# -- composing flags on a listing, independently -----------------------

def tag_wanted(w) -> None:
    """`wanted` iff this listing's card is still short of its `wants` --
    both directions, every tick."""
    for entity, _tag, card in w.each("listing", "card"):
        wants = w.get(card, "wants")
        if wants is None:
            w.unmark(entity, "wanted")
            continue
        have = w.get(card, "copies", 0)
        if have < wants:
            w.mark(entity, "wanted")
        else:
            w.unmark(entity, "wanted")


def tag_affordable(w) -> None:
    """`affordable` iff the price fits inside both the cash-minus-reserve
    room and the per-trade cap -- both directions, every tick."""
    purse = w.first("purse")
    risk = w.first("risk_profile")
    if purse is None or risk is None:
        return
    cash = w.get(purse[0], "cash")
    room = cash - w.get(risk[0], "min_cash_reserve")
    cap = w.get(risk[0], "max_spend_per_trade")
    for entity, _tag, price in w.each("listing", "price"):
        if price <= room and price <= cap:
            w.mark(entity, "affordable")
        else:
            w.unmark(entity, "affordable")


def tag_fair_priced(w) -> None:
    """`fair_priced` iff the price is within the risk profile's tolerated
    premium over the card's own catalog value."""
    risk = w.first("risk_profile")
    if risk is None:
        return
    premium = w.get(risk[0], "max_premium")
    for entity, _tag, card, price in w.each("listing", "card", "price"):
        value = w.get(card, "value")
        if value is None:
            w.unmark(entity, "fair_priced")
            continue
        if price <= value * (1 + premium):
            w.mark(entity, "fair_priced")
        else:
            w.unmark(entity, "fair_priced")


def tag_risk_level(w) -> None:
    """`risk_level`/`risk_reason`, set fresh onto a listing every tick --
    see the module docstring's "A fourth tag." `level` is how much of the
    room this trade may spend the price would use, capped at `1.0`."""
    purse = w.first("purse")
    risk = w.first("risk_profile")
    if purse is None or risk is None:
        return
    room = w.get(purse[0], "cash") - w.get(risk[0], "min_cash_reserve")
    for entity, _tag, price in w.each("listing", "price"):
        level = 1.0 if room <= 0 else min(1.0, price / room)
        w.set(entity, "risk_level", level)
        w.set(entity, "risk_reason",
              "would use %.0f%% of the %d cash still free to spend"
              % (level * 100, max(room, 0)))


# -- acting -------------------------------------------------------------

def decide_buy(w) -> None:
    """Every listing carrying all three flags, and not the judge's own
    `too_risky`, -> bought. Re-reads the purse/wants/copies fresh at the TOP
    of each iteration and skips a listing an earlier purchase made stale."""
    risk = w.first("risk_profile")
    if risk is None:
        return
    reserve = w.get(risk[0], "min_cash_reserve")
    for (entity, _tag, card, price, _w, _a, _f) in w.each(
            "listing", "card", "price", "wanted", "affordable", "fair_priced",
            without="too_risky"):
        wants = w.get(card, "wants")
        have = w.get(card, "copies", 0)
        if wants is None or have >= wants:
            continue
        purse = w.first("purse")
        if purse is None:
            return
        cash = w.get(purse[0], "cash")
        if price > cash - reserve:
            continue
        w.set(purse[0], "cash", cash - price)
        w.set(card, "copies", have + 1)
        w.destroy(entity)
        bought = w.spawn()
        w.mark(bought, "bought")
        w.set(bought, "card", card)
        w.set(bought, "price", price)


def check_goal(w) -> None:
    """Every stated `wants` met by its own `copies` -> a `goal_met`,
    spawned once and never again."""
    wanted = w.each("card_def", "wants")
    if not wanted or w.populated("goal_met"):
        return
    for card_entity, _tag, wants in wanted:
        if w.get(card_entity, "copies", 0) < wants:
            return
    entity = w.spawn()
    w.mark(entity, "goal_met")


# -- replying -----------------------------------------------------------

def reply_bought(w) -> None:
    for entity, _tag, card, price in w.each("bought", "card", "price"):
        w.destroy(entity)
        name = w.get(card, "name")
        reply(w, "user", "bought %s for %d"
              % (name if name else "card #%d" % card, price))


def reply_bad_command(w) -> None:
    for entity, _tag, why in w.each("bad_command", "why"):
        w.destroy(entity)
        reply(w, "user", "! %s" % why)


def reply_goal_met(w) -> None:
    """The winning `goal_met` -> a `Reply`, exactly once -- `without=
    "announced"` keeps this from firing again on a settled world."""
    for entity, _ in w.each("goal_met", without="announced"):
        w.mark(entity, "announced")
        reply(w, "user", "goal met -- every wanted card is in the collection")


RULES = (hear_list, hear_want, hear_status,
         tag_wanted, tag_affordable, tag_fair_priced, tag_risk_level,
         flag_too_risky,
         decide_buy, check_goal,
         reply_bought, reply_bad_command, reply_goal_met)


def install(loop, cash: int = 100, catalog=DEFAULT_CATALOG) -> None:
    """Register every rule above (each gated automatically on its own reads),
    then seed the catalog, the purse, the risk profile, and the judge's own
    tolerance."""
    loop.rule(hear_list)
    loop.rule(hear_want)
    loop.rule(hear_status)
    loop.rule(tag_wanted)
    loop.rule(tag_affordable)
    loop.rule(tag_fair_priced)
    loop.rule(tag_risk_level)
    loop.rule(flag_too_risky)
    loop.rule(decide_buy)
    loop.rule(check_goal)
    loop.rule(reply_bought)
    loop.rule(reply_bad_command)
    loop.rule(reply_goal_met)

    world = loop.world
    for name, rarity, value in catalog:
        if _find_card(world, name) is None:
            entity = world.spawn()
            world.mark(entity, "card_def")
            world.set(entity, "name", name)
            world.set(entity, "rarity", rarity)
            world.set(entity, "value", value)
            world.set(entity, "copies", 0)
    if not world.populated("purse"):
        purse = world.spawn()
        world.mark(purse, "purse")
        world.set(purse, "cash", cash)
    if not world.populated("risk_profile"):
        risk = world.spawn()
        world.mark(risk, "risk_profile")
        world.set(risk, "max_spend_per_trade", 50)
        world.set(risk, "min_cash_reserve", 0)
        world.set(risk, "max_premium", 0.25)
    seed_tolerance(world, 0.8)
