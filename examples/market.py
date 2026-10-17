"""`market` -- a richer trading island than `examples.cards`: an agent that
buys AND sells, holds PRIORITIZED wants, and picks the best rival listing
through a second bridge. Kept in `examples/`, not shipped, the same as
`cards`/`shopping` -- see `README.md`'s "Scope."

## Why a second trading domain at all

`docs/tuning.md`'s plan says the argument for authored structure is a
SLOPE, not a point: examples-to-competence should grow more slowly with a
hand-authored structure than without one, and that only shows if the ladder
has more than one rung. `cards` is rung 0 -- three tags into one rule,
three knobs. This is rung 1, and it adds structure on purpose, but only
the three kinds the experiments need, each of them DOMAIN-NATURAL rather
than invented to win a comparison:

1. **Selling, the gap `cards`' own docstring names.** An `Offer` to buy a
   held card, and a `Surplus` tag (offer price past `value * (1 +
   sell_premium)`), is a whole second decision island sharing the same
   `Cash` and the same card values. It is also Experiment 3's target: a
   genuinely new behaviour to acquire.
2. **A SECOND bridge.** Every listing is projected onto `examples.decide`'s
   domain-oblivious `Option`/`Score` (score = `value - price`, "money left
   on the table"), and `decide.pick_winner` -- a rule that has never heard
   of a `Listing` -- tags the best RIVAL listing per card. `decide_buy`
   reads `Winner`. So this island drives both `examples.judge` and
   `examples.decide`, where `cards` drove only `judge`.
3. **A cross-entity condition.** `Strands` marks a listing whose purchase
   would drop cash below what a STRICTLY HIGHER-PRIORITY, still-unmet want
   needs at its fair price -- a join across listings, wants, held counts
   and cash that a flat learner cannot recover from a handful of labels.

## What this is not

Not a market SIMULATION: no clock, no drifting prices. `loopingrules.loop`
settles between inputs, so a rule that changed something every tick would
never settle -- the "trajectory" here is the bounded cascade after a line,
not a time series. Complexity is breadth and depth per cascade, never a
ticker.

Not a tuned comparison in disguise: the de novo baseline Experiment 2 will
be measured against gets the same raw features this domain reads (price,
value, held, want qty/priority, cash, the risk level) and its own capacity.
The structure is built because a market naturally has selling and
priorities, not because it makes the authored side look better.

## Vocabulary

- `Card(name, value)` -- one entity per catalog card; the agent's own idea
  of worth. Seeded by `install` by NAME, never overwriting one already
  there (a restored world's value is a prior conclusion).
- `Held(count)` -- copies held, on the card's own entity.
- `Want(qty, priority)` -- the goal for a card, singular on that card,
  `replace`d by a second `want`; priority is higher-is-more-important.
- `Cash(amount)` -- singleton purse. Selling adds, buying subtracts.
- `Policy(max_price_ratio, min_reserve, sell_premium)` -- the tunable risk
  knobs, singleton, seeded BigFloor-style. `docs/tuning.md`'s "a tunable
  rule reads a component" applies here exactly as in `cards`.
- `Listing(card, price)` -- a card for sale; `card` a `Card` entity id.
- `Offer(card, price)` -- someone will buy a held card at `price`.
- `Wanted()` / `Affordable()` / `FairPriced()` / `Strands()` / `Surplus()`
  -- `@transient` tags, both directions every tick, the same recompute-fresh
  discipline `cards`' own tag rules use.
- `examples.judge.Risk(level, reason)` -- resource exhaustion projection,
  `replace`d fresh, thresholded by the judge into `TooRisky`.
- `examples.decide.Option(occasion)` / `Score(value)` / `Winner()` -- the
  ranking bridge, `occurrence` = the listing's card id so rival listings
  for one card compete.
- `Bought(card, price)` / `Sold(card, price)` / `BadCommand(text, why)` --
  short-lived outcome facts, consumed same-or-next tick by a `reply_*`.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.decide import Option, Score, Winner, pick_winner
from examples.judge import Risk, RiskTolerance, TooRisky, flag_too_risky
from loopingrules.engine import Reply, Said
from loopingrules.world import transient


@dataclass(frozen=True)
class Card:
    name: str
    value: int


@dataclass(frozen=True)
class Held:
    count: int


@dataclass(frozen=True)
class Want:
    qty: int
    priority: int


@dataclass(frozen=True)
class Cash:
    amount: int


@dataclass(frozen=True)
class Policy:
    max_price_ratio: float
    min_reserve: int
    sell_premium: float


@dataclass(frozen=True)
class Listing:
    card: int
    price: int


@dataclass(frozen=True)
class Offer:
    card: int
    price: int


@transient
@dataclass(frozen=True)
class Wanted:
    pass


@transient
@dataclass(frozen=True)
class Affordable:
    pass


@transient
@dataclass(frozen=True)
class FairPriced:
    pass


@transient
@dataclass(frozen=True)
class Strands:
    pass


@transient
@dataclass(frozen=True)
class Surplus:
    pass


@dataclass(frozen=True)
class Bought:
    card: int
    price: int


@dataclass(frozen=True)
class Sold:
    card: int
    price: int


@dataclass(frozen=True)
class BadCommand:
    text: str
    why: str


DEFAULT_CATALOG = (
    Card("dragon", 40),
    Card("phoenix", 100),
    Card("goblin", 5),
    Card("wolf", 8),
    Card("griffin", 35),
)


def _find_card(w, name: str):
    """The `Card` entity named `name`, case-insensitively, or `None` --
    same refuse-to-guess lookup `cards._find_card` uses."""
    for entity, card in w.all(Card):
        if card.name.lower() == name.lower():
            return entity
    return None


def _parse_int(text: str):
    try:
        return int(text)
    except ValueError:
        return None


# -- hearing --------------------------------------------------------------

def hear_list(w) -> None:
    """`list <card> <price>` -> a `Listing`, or a `BadCommand`."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "list":
            continue
        w.destroy(entity)
        if len(words) != 3:
            w.spawn(BadCommand(said.text, "usage: list <card> <price>"))
            continue
        card = _find_card(w, words[1])
        if card is None:
            w.spawn(BadCommand(said.text, "unknown card %r" % words[1]))
            continue
        price = _parse_int(words[2])
        if price is None:
            w.spawn(BadCommand(said.text, "not a price: %r" % words[2]))
            continue
        w.spawn(Listing(card, price))


def hear_want(w) -> None:
    """`want <card> [qty] [priority]` (defaults `qty=1`, `priority=0`) ->
    `Want(qty, priority)` on that card's own entity, replacing whatever
    `Want` it already carried. A second `want` updates the goal, the same
    as `cards.hear_want`."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "want":
            continue
        w.destroy(entity)
        if len(words) not in (2, 3, 4):
            w.spawn(BadCommand(said.text, "usage: want <card> [qty] [priority]"))
            continue
        card = _find_card(w, words[1])
        if card is None:
            w.spawn(BadCommand(said.text, "unknown card %r" % words[1]))
            continue
        qty, priority = 1, 0
        if len(words) >= 3:
            qty = _parse_int(words[2])
            if qty is None or qty < 1:
                w.spawn(BadCommand(said.text, "not a quantity: %r" % words[2]))
                continue
        if len(words) == 4:
            priority = _parse_int(words[3])
            if priority is None:
                w.spawn(BadCommand(said.text, "not a priority: %r" % words[3]))
                continue
        w.replace(card, Want(qty, priority))


def hear_offer(w) -> None:
    """`offer <card> <price>` -> an `Offer` to buy a held card at `price`."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "offer":
            continue
        w.destroy(entity)
        if len(words) != 3:
            w.spawn(BadCommand(said.text, "usage: offer <card> <price>"))
            continue
        card = _find_card(w, words[1])
        if card is None:
            w.spawn(BadCommand(said.text, "unknown card %r" % words[1]))
            continue
        price = _parse_int(words[2])
        if price is None:
            w.spawn(BadCommand(said.text, "not a price: %r" % words[2]))
            continue
        w.spawn(Offer(card, price))


def hear_status(w) -> None:
    """`status` -> cash, and per wanted card the held/goal and priority."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "status":
            continue
        w.destroy(entity)
        cash = w.the(Cash)
        lines = ["cash: %d" % cash.amount]
        wanted = sorted(w.each(Card, Want), key=lambda row: row[1].name)
        if not wanted:
            lines.append("no goal set")
        for card_entity, card, want in wanted:
            held = w.get(card_entity, Held)
            have = held.count if held else 0
            lines.append("%s: %d/%d (priority %d)"
                         % (card.name, have, want.qty, want.priority))
        w.spawn(Reply("user", "; ".join(lines)))


# -- composing tags on a Listing, independently ---------------------------

def tag_wanted(w) -> None:
    """`Wanted` iff this listing's card is still short of its `Want`."""
    for entity, listing in w.each(Listing):
        want = w.get(listing.card, Want)
        held = w.get(listing.card, Held)
        have = held.count if held else 0
        if want is not None and have < want.qty:
            w.attach(entity, Wanted())
        else:
            w.detach(entity, Wanted)


def tag_affordable(w) -> None:
    """`Affordable` iff the price fits the cash-minus-reserve room."""
    cash = w.the(Cash)
    policy = w.the(Policy)
    room = cash.amount - policy.min_reserve
    for entity, listing in w.each(Listing):
        if listing.price <= room:
            w.attach(entity, Affordable())
        else:
            w.detach(entity, Affordable)


def tag_fair_priced(w) -> None:
    """`FairPriced` iff the price is within the tolerated premium over the
    card's own catalog value."""
    policy = w.the(Policy)
    for entity, listing in w.each(Listing):
        card = w.get(listing.card, Card)
        if card is None:
            w.detach(entity, FairPriced)
            continue
        limit = card.value * (1 + policy.max_price_ratio)
        if listing.price <= limit:
            w.attach(entity, FairPriced())
        else:
            w.detach(entity, FairPriced)


def tag_risk(w) -> None:
    """`examples.judge.Risk`, `replace`d fresh, of how much of the free room
    the price would use -- the same projection `cards.tag_risk_level`
    makes, onto the bridge this domain does not own."""
    cash = w.the(Cash)
    policy = w.the(Policy)
    room = cash.amount - policy.min_reserve
    for entity, listing in w.each(Listing):
        level = 1.0 if room <= 0 else min(1.0, listing.price / room)
        w.replace(entity, Risk(
            level,
            "would use %.0f%% of the %d cash still free to spend" % (
                level * 100, max(room, 0))))


def tag_strands(w) -> None:
    """`Strands` iff buying this listing would leave cash below what a
    STRICTLY HIGHER-PRIORITY, still-unmet want needs at its fair price.

    A genuine cross-entity join -- each listing checked against every other
    card's own `Want`/`Held`/value -- which is exactly the kind of
    condition a flat learner cannot recover from a few labels. An
    equal-priority want never strands: two wants of equal importance are
    rivals this rule refuses to rank, so it does not block either.
    """
    cash = w.the(Cash)
    policy = w.the(Policy)
    wants = w.each(Card, Want)
    for entity, listing in w.each(Listing):
        want = w.get(listing.card, Want)
        if want is None:
            w.detach(entity, Strands)
            continue
        strands = False
        for other_entity, other_card, other_want in wants:
            if other_want.priority <= want.priority:
                continue
            held = w.get(other_entity, Held)
            have = held.count if held else 0
            if have >= other_want.qty:
                continue
            needed = other_card.value * (1 + policy.max_price_ratio)
            if cash.amount - listing.price < needed:
                strands = True
                break
        if strands:
            w.attach(entity, Strands())
        else:
            w.detach(entity, Strands)


def tag_surplus(w) -> None:
    """`Surplus` iff an `Offer` for a held card clears the tolerated premium
    over value -- the SELL-side mirror of `tag_fair_priced`, using the same
    `Policy`."""
    policy = w.the(Policy)
    for entity, offer in w.each(Offer):
        card = w.get(offer.card, Card)
        if card is None:
            w.detach(entity, Surplus)
            continue
        limit = card.value * (1 + policy.sell_premium)
        if offer.price >= limit:
            w.attach(entity, Surplus())
        else:
            w.detach(entity, Surplus)


# -- the ranking bridge: nominate rival listings, pick the best -----------

def nominate(w) -> None:
    """Project every listing onto `examples.decide`'s `Option`/`Score`:
    `occasion` is the listing's own card id, so rival listings FOR ONE CARD
    compete, and `score` is `value - price` (higher is better -- money left
    on the table). `replace`, not `attach`, so the projection stays singular
    on the listing the same way `Risk` does. This domain computes no winner
    itself; `decide.pick_winner` does, oblivious to what a `Listing` is."""
    for entity, listing in w.each(Listing):
        card = w.get(listing.card, Card)
        if card is None:
            continue
        w.replace(entity, Option(listing.card), Score(float(card.value - listing.price)))


# -- acting ---------------------------------------------------------------

def decide_buy(w) -> None:
    """Every listing that is Wanted, Affordable, FairPriced, the judge's
    own `Winner` among its rivals, and neither `TooRisky` nor `Strands` ->
    bought. Reads FOUR independently-produced tags -- three of this module's
    own, one from `examples.judge`, one from `examples.decide` -- the same
    composition idiom `cards.decide_buy` uses, two bridges deep. Re-reads
    `Cash`/`Want`/`Held` at the top of each iteration and skips (never
    destroys) a listing an earlier purchase this call made stale."""
    for entity, listing, _wanted, _affordable, _fair, _winner in w.each(
            Listing, Wanted, Affordable, FairPriced, Winner,
            without=(TooRisky, Strands)):
        want = w.get(listing.card, Want)
        held = w.get(listing.card, Held)
        have = held.count if held else 0
        if want is None or have >= want.qty:
            continue
        cash_entity, cash = w.first(Cash)
        policy = w.the(Policy)
        if listing.price > cash.amount - policy.min_reserve:
            continue
        w.replace(cash_entity, Cash(cash.amount - listing.price))
        w.replace(listing.card, Held(have + 1))
        w.destroy(entity)
        w.spawn(Bought(listing.card, listing.price))


def decide_sell(w) -> None:
    """Every offer carrying `Surplus` for a card the agent actually holds ->
    sold: one copy off `Held`, the price onto `Cash`, the offer consumed."""
    for entity, offer, _surplus in w.each(Offer, Surplus):
        held = w.get(offer.card, Held)
        have = held.count if held else 0
        if have < 1:
            continue
        w.replace(offer.card, Held(have - 1))
        cash_entity, cash = w.first(Cash)
        w.replace(cash_entity, Cash(cash.amount + offer.price))
        w.destroy(entity)
        w.spawn(Sold(offer.card, offer.price))


# -- replying -------------------------------------------------------------

def reply_bought(w) -> None:
    for entity, bought in w.each(Bought):
        w.destroy(entity)
        card = w.get(bought.card, Card)
        name = card.name if card else "card #%d" % bought.card
        w.spawn(Reply("user", "bought %s for %d" % (name, bought.price)))


def reply_sold(w) -> None:
    for entity, sold in w.each(Sold):
        w.destroy(entity)
        card = w.get(sold.card, Card)
        name = card.name if card else "card #%d" % sold.card
        w.spawn(Reply("user", "sold %s for %d" % (name, sold.price)))


def reply_bad_command(w) -> None:
    for entity, bad in w.each(BadCommand):
        w.destroy(entity)
        w.spawn(Reply("user", "! %s" % bad.why))


RULES = (hear_list, hear_want, hear_offer, hear_status,
         tag_wanted, tag_affordable, tag_fair_priced, tag_risk,
         tag_strands, nominate, pick_winner, flag_too_risky,
         tag_surplus,
         decide_buy, decide_sell,
         reply_bought, reply_sold, reply_bad_command)


def install(loop, cash: int = 100, catalog=DEFAULT_CATALOG) -> None:
    """Register every rule above -- including the two bridge rules from
    `examples.judge` and `examples.decide`, unmodified -- then seed the
    catalog, `Cash`, `Policy` and the judge's own `RiskTolerance`.
    BigFloor-style: a singleton already present is never reseeded."""
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
    for card in catalog:
        if _find_card(world, card.name) is None:
            entity = world.spawn(card)
            world.attach(entity, Held(0))
    if world.first(Cash) is None:
        world.spawn(Cash(cash))
    if world.first(Policy) is None:
        world.spawn(Policy(max_price_ratio=0.25, min_reserve=0, sell_premium=0.25))
    if world.first(RiskTolerance) is None:
        world.spawn(RiskTolerance(max_level=0.8))
