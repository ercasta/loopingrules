"""`cards` -- one autonomous trading agent, reacting to a virtual card
market according to a goal (which cards it wants) and a risk profile (how
much it will spend, how much premium over fair value it will tolerate).

## Kept here, not shipped

`loopingrules`'s own README says the package ships no domain except
`help.py`. This module is not an exception to that -- it lives in
`examples/`, not in `loopingrules/`, is not in `pyproject.toml`'s
`packages=`, and nothing in the installed package imports it. It exists
for the same reason `harneskills.examples.fs` and `pystrider` exist, one
step closer to home: a worked domain, kept in this repo for
demonstration, importable from a checkout the same way this file's own
tests import it, never installed alongside `loopingrules` itself.

## One actor, no rivalry -- so no `Proposal`/`arbitrate`/`census`

Unlike `harneskills.examples.fs`'s `ParseRequest`/`propose_*`/
`arbitrate_parse` (several candidate READINGS of one line competing) or
`loopingrules.help`'s `HelpTopic` (several INSTALLED DOMAINS answering
one occasion), nothing here ever has two rivals for one decision: one
agent, its own goal, its own money. Every verb (`list`/`want`/`status`)
is this module's alone to recognize, so a `hear_*` rule just claims the
`Said` the moment it recognizes its own verb and never needs to arbitrate
against a second interpretation.

## The actual point: composing tags nobody wrote the composition of

The interesting mechanism here is not the market, it's `decide_buy`
reading three tags -- `Wanted`, `Affordable`, `FairPriced` -- attached to
one `Listing` by three rules that share no code and no awareness of each
other. This is `pystrider.patterns.LoopCount` -> `pystrider.constraints.
TooManyLoops` again (see `PRINCIPLES.md`, "the actual lever: a small
vocabulary, closed under what rules produce"): `constraints.max_loops`
reads a tag `patterns.loop_count` attached with zero idea a consumer
exists; `decide_buy` is the same shape, three tags deep instead of one.

⚠ One real difference from `LoopCount`, worth naming because it is the
one bug this design would have shipped with otherwise: `LoopCount` is
safe to derive ONCE per entity (`without=LoopCount` guards it) because a
`pystrider` re-read destroys and rebuilds the whole entity, so the fact
underneath it never changes out from under a live id. `Wanted`/
`Affordable`/`FairPriced` cannot use that guard -- `Purse.cash`,
`Wants.qty`, and `Copies.count` all change in place, on long-lived
entities, while a `Listing` sits on the market for many ticks. Each tag
rule below recomputes its boolean fresh every tick and goes BOTH
directions (`attach` when true, `detach` when false) -- see `tag_wanted`/
`tag_affordable`/`tag_fair_priced`. This costs nothing once settled
(`attach`/`detach` are already no-ops when nothing changed) and is
exactly the "recompute fresh, never cache" discipline `PRINCIPLES.md`
asks for anyway.

## Selling is a deliberate gap, not an oversight

This agent only ever buys. A `decide_sell` rule would follow the exact
same tag-then-act shape (`Surplus`/`NeedsCash` tags on an `Owned`-but-
unwanted card, composed the same way `decide_buy` composes its three) --
not built, per `DECISION_PATTERNS.md`'s "grow it only at the rule that
actually collides": there is no second scenario yet that needs it, and
guessing at the shape now would be exactly the speculative generality
that file argues against.

## Vocabulary

- `CardDef(name, rarity, value)` -- one entity per catalog card, the
  agent's own idea of what a card is worth. Seeded by `install`, one
  entity per catalog entry, by NAME -- an entry already present (by name)
  is never touched, the same policy `fs.py.install` gives `BigFloor`: a
  restored world's own value is a prior tick's conclusion, not something
  a later `install()` call has any business overwriting.
- `Copies(count)` -- how many of a card the agent holds, attached to that
  card's OWN `CardDef` entity (not a separate entity referencing it by
  id) -- `World.replace()` already keeps this singular for free, the
  same tool `fs.py` reaches for on `Session`/`BigFloor`.
- `Wants(qty)` -- how many the agent's goal calls for, attached the same
  way, created by `hear_want`, absent until then (a goal only exists once
  stated).
- `Purse(cash)` -- the agent's money, a singleton entity, seeded once
  (BigFloor-style: only if none exists yet).
- `RiskProfile(max_spend_per_trade, min_cash_reserve, max_premium)` -- the
  agent's tunable risk knobs, singleton, seeded the same way.
- `Listing(card, price)` -- a card for sale, `card` a `CardDef` entity id
  (or the live entity -- `attach()` lowers it, see `loopingrules.world`'s
  own module note). Arrives via `hear_list`; never seeded.
- `Wanted()` / `Affordable()` / `FairPriced()` -- `@transient` tags on a
  `Listing`, see above.
- `Bought(card, price)` / `BadCommand(text, why)` -- short-lived outcome
  facts, consumed same-or-next tick by a `reply_*` rule. Not
  `@transient` -- they're gone before a save would ever see them anyway,
  the same as `fs.py`'s own `Renamed`/`Failed`.
- `GoalMet()` / `Announced()` -- `GoalMet` is a durable singleton, spawned
  once every `Wants` is met and never destroyed again; `Announced`,
  attached to it, is what keeps `reply_goal_met` from saying so twice.
  Deliberately NOT `@transient`, and NEVER re-derived once true -- a
  domain that dropped and re-derived this every tick would re-announce
  "goal met" forever, exactly the hot loop `PRINCIPLES.md`'s "termination
  is a safety net" section warns a growing ruleset to watch for.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import Said, reply, transient


@dataclass(frozen=True)
class CardDef:
    name: str
    rarity: str
    value: int


@dataclass(frozen=True)
class Copies:
    count: int


@dataclass(frozen=True)
class Wants:
    qty: int


@dataclass(frozen=True)
class Purse:
    cash: int


@dataclass(frozen=True)
class RiskProfile:
    max_spend_per_trade: int
    min_cash_reserve: int
    max_premium: float


@dataclass(frozen=True)
class Listing:
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


@dataclass(frozen=True)
class Bought:
    card: int
    price: int


@dataclass(frozen=True)
class BadCommand:
    text: str
    why: str


@dataclass(frozen=True)
class GoalMet:
    pass


@dataclass(frozen=True)
class Announced:
    pass


DEFAULT_CATALOG = (
    CardDef("dragon", "rare", 40),
    CardDef("phoenix", "legendary", 100),
    CardDef("goblin", "common", 5),
    CardDef("wolf", "common", 8),
    CardDef("griffin", "rare", 35),
)


def _find_card(w, name: str):
    """The `CardDef` entity named `name`, case-insensitively, or `None`.
    Never guesses between two -- `install` never seeds a duplicate name,
    and nothing else here spawns a `CardDef` at all."""
    for entity, card_def in w.all(CardDef):
        if card_def.name.lower() == name.lower():
            return entity
    return None


def _parse_int(text: str):
    """`int(text)`, or `None` -- the refuse-rather-than-guess discipline
    `PRINCIPLES.md` asks for at every parse boundary, spelled out once
    rather than a bare `try/except` at each call site."""
    try:
        return int(text)
    except ValueError:
        return None


# -- hearing -----------------------------------------------------------

def hear_list(w) -> None:
    """`list <card> <price>` -> a `Listing`, or a `BadCommand` naming
    what was wrong. Claims (`destroy`s) the line the moment its own verb
    matches, whether or not what follows parses -- once claimed, it is
    never left standing for something else to trip over."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "list":
            continue
        w.destroy(entity)
        if len(words) != 3:
            w.spawn(BadCommand(said.text, "usage: list <card> <price>"))
            continue
        name, price_text = words[1], words[2]
        card = _find_card(w, name)
        if card is None:
            w.spawn(BadCommand(said.text, "unknown card %r" % name))
            continue
        price = _parse_int(price_text)
        if price is None:
            w.spawn(BadCommand(said.text, "not a price: %r" % price_text))
            continue
        w.spawn(Listing(card, price))


def hear_want(w) -> None:
    """`want <card> [qty]` (default `qty=1`) -> `Wants(qty)` on that
    card's own `CardDef` entity, replacing whatever `Wants` it already
    carried -- a second `want` for the same card updates the goal, it
    does not add a rival one."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "want":
            continue
        w.destroy(entity)
        if len(words) not in (2, 3):
            w.spawn(BadCommand(said.text, "usage: want <card> [qty]"))
            continue
        card = _find_card(w, words[1])
        if card is None:
            w.spawn(BadCommand(said.text, "unknown card %r" % words[1]))
            continue
        qty = 1
        if len(words) == 3:
            qty = _parse_int(words[2])
            if qty is None or qty < 1:
                w.spawn(BadCommand(said.text, "not a quantity: %r" % words[2]))
                continue
        w.replace(card, Wants(qty))


def hear_status(w) -> None:
    """`status` -> cash, goal progress per wanted card, and whether the
    goal is met -- said directly, no outcome fact: nothing else in this
    world ever needs to know status was asked."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "status":
            continue
        w.destroy(entity)
        purse = w.the(Purse)
        lines = ["cash: %d" % purse.cash]
        wanted = sorted(w.each(CardDef, Wants), key=lambda row: row[1].name)
        if not wanted:
            lines.append("no goal set")
        for card_entity, card_def, want in wanted:
            copies = w.get(card_entity, Copies)
            have = copies.count if copies else 0
            lines.append("%s: %d/%d" % (card_def.name, have, want.qty))
        if w.the(GoalMet) is not None:
            lines.append("goal met")
        reply(w, "; ".join(lines))


# -- composing tags on a Listing, independently -------------------------

def tag_wanted(w) -> None:
    """`Wanted` iff this listing's card is still short of its `Wants` --
    both directions, every tick: see the module docstring's ⚠ on why
    `LoopCount`'s monotonic `without=` guard is wrong here."""
    for entity, listing in w.each(Listing):
        wants = w.get(listing.card, Wants)
        if wants is None:
            w.detach(entity, Wanted)
            continue
        copies = w.get(listing.card, Copies)
        have = copies.count if copies else 0
        if have < wants.qty:
            w.attach(entity, Wanted())
        else:
            w.detach(entity, Wanted)


def tag_affordable(w) -> None:
    """`Affordable` iff the price fits inside both the cash-minus-reserve
    room and the per-trade cap -- both directions, every tick, same
    reasoning as `tag_wanted`."""
    purse = w.the(Purse)
    risk = w.the(RiskProfile)
    for entity, listing in w.each(Listing):
        room = purse.cash - risk.min_cash_reserve
        if listing.price <= room and listing.price <= risk.max_spend_per_trade:
            w.attach(entity, Affordable())
        else:
            w.detach(entity, Affordable)


def tag_fair_priced(w) -> None:
    """`FairPriced` iff the price is within the risk profile's tolerated
    premium over the card's own catalog value -- both directions, every
    tick, same reasoning as `tag_wanted`."""
    risk = w.the(RiskProfile)
    for entity, listing in w.each(Listing):
        card_def = w.get(listing.card, CardDef)
        if card_def is None:
            w.detach(entity, FairPriced)
            continue
        limit = card_def.value * (1 + risk.max_premium)
        if listing.price <= limit:
            w.attach(entity, FairPriced())
        else:
            w.detach(entity, FairPriced)


# -- acting --------------------------------------------------------------

def decide_buy(w) -> None:
    """Every listing carrying all three tags -> bought. `w.each()` below
    is materialized once, up front -- so this re-reads `Purse`/`Wants`/
    `Copies` fresh at the TOP of each iteration and skips (never destroys)
    a listing this same call has already made stale by an earlier
    purchase, rather than trusting the snapshot. Two listings that are
    each affordable ALONE but not TOGETHER do not both buy in one tick --
    see the module's own history for why that matters (`DECISION_PATTERNS.
    md`'s "composability is a structural test": two candidates writing the
    same `Purse` do not have disjoint footprints, so nothing may treat
    them as free to compose)."""
    for entity, listing, _wanted, _affordable, _fair in w.each(
            Listing, Wanted, Affordable, FairPriced):
        wants = w.get(listing.card, Wants)
        copies = w.get(listing.card, Copies)
        have = copies.count if copies else 0
        if wants is None or have >= wants.qty:
            continue    # satisfied by an earlier purchase this same call
        purse_entity, purse = w.first(Purse)
        risk = w.the(RiskProfile)
        if listing.price > purse.cash - risk.min_cash_reserve:
            continue    # spent by an earlier purchase this same call
        w.replace(purse_entity, Purse(purse.cash - listing.price))
        w.replace(listing.card, Copies(have + 1))
        w.destroy(entity)
        w.spawn(Bought(listing.card, listing.price))


def check_goal(w) -> None:
    """Every stated `Wants` met by its own `Copies` -> a `GoalMet`,
    spawned once and never again -- `w.the(GoalMet) is not None` is the
    guard, not a `without=` on some entity, because `GoalMet` has none of
    its own to sit beside."""
    wanted = w.each(CardDef, Wants)
    if not wanted or w.the(GoalMet) is not None:
        return
    for card_entity, _card_def, wants in wanted:
        copies = w.get(card_entity, Copies)
        have = copies.count if copies else 0
        if have < wants.qty:
            return
    w.spawn(GoalMet())


# -- replying --------------------------------------------------------------

def reply_bought(w) -> None:
    for entity, bought in w.each(Bought):
        w.destroy(entity)
        card_def = w.get(bought.card, CardDef)
        name = card_def.name if card_def else "card #%d" % bought.card
        reply(w, "bought %s for %d" % (name, bought.price))


def reply_bad_command(w) -> None:
    for entity, bad in w.each(BadCommand):
        w.destroy(entity)
        reply(w, "! %s" % bad.why)


def reply_goal_met(w) -> None:
    """The winning `GoalMet` -> a `Reply`, exactly once -- `without=
    Announced` is what keeps this from firing again on a settled world
    that never changes again, the same discipline `reply_help_answer`
    needs `without=Proposal` for, for an analogous reason (never act on a
    still-contested/still-unannounced candidate twice)."""
    for entity, _goal in w.each(GoalMet, without=Announced):
        w.attach(entity, Announced())
        reply(w, "goal met -- every wanted card is in the collection")


RULES = (hear_list, hear_want, hear_status,
         tag_wanted, tag_affordable, tag_fair_priced,
         decide_buy, check_goal,
         reply_bought, reply_bad_command, reply_goal_met)


def install(loop, cash: int = 100, catalog=DEFAULT_CATALOG) -> None:
    """Register every rule above, each with its own `watches=` (unlike
    `fs.py`'s `RULES` loop, which declares none), then seed the catalog,
    `Purse`, and `RiskProfile`.

    `CardDef`/`Copies` are seeded per catalog entry, by NAME -- a name
    already present is never touched (see the module docstring); this is
    what lets a catalog grow across versions without a restored world
    losing a since-added card, unlike a single `world.first(CardDef) is
    None` check would. `Purse`/`RiskProfile` are true singletons, seeded
    BigFloor-style: only if the world does not already carry one.
    """
    loop.rule(hear_list, watches=(Said,))
    loop.rule(hear_want, watches=(Said,))
    loop.rule(hear_status, watches=(Said,))
    loop.rule(tag_wanted, watches=(Listing, Wants))
    loop.rule(tag_affordable, watches=(Listing,))
    loop.rule(tag_fair_priced, watches=(Listing,))
    loop.rule(decide_buy, watches=(Listing,))
    loop.rule(check_goal, watches=(Wants,))
    loop.rule(reply_bought, watches=(Bought,))
    loop.rule(reply_bad_command, watches=(BadCommand,))
    loop.rule(reply_goal_met, watches=(GoalMet,))

    world = loop.world
    for card_def in catalog:
        if _find_card(world, card_def.name) is None:
            entity = world.spawn(card_def)
            world.attach(entity, Copies(0))
    if world.first(Purse) is None:
        world.spawn(Purse(cash))
    if world.first(RiskProfile) is None:
        world.spawn(RiskProfile(max_spend_per_trade=50, min_cash_reserve=0,
                                 max_premium=0.25))
    world.learn("list", "want", "status", *(c.name for c in catalog))
