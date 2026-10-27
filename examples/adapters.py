"""`adapters` -- a probe, not a shipped bridge: can a domain keep its OWN
ownership representation and still take part in a shared exchange, through
an explicit, one-directional adapter?

## The question, and why an adapter and not a bridge

`loopingrules_patterns.judge` and `examples.decide` are bridges: a thin shared shape
BOTH islands project onto, and an oblivious rule that reads only that
shape and attaches its OWN tag back (`TooRisky`, `Winner`). A bridge can
ANNOTATE; it cannot APPLY, because applying an effect means writing a
domain's own components (`Purse.cash -= price` knows what a purse is). So
`examples.trade`'s movement -- an EFFECT, not a claim -- is exactly where
the oblivious-bridge pattern runs out. An adapter is the other answer: a
rule that knows BOTH representations and maps one onto the other. It is
the one sanctioned place two domains meet.

## The hypothesis this measures (form vs. value, again)

Experiment 1 (`examples.bridge_transfer`) found a bridge's SHAPE transfers
at zero cost while its THRESHOLD does not. Carried to representation:

    ownership STRATIFIES (an adapter maps `cards.Purse`/`cards.Copies` onto
    `trade.Holding` losslessly), while POLICY does not (cards' `value`,
    `RiskProfile`, `Wants` and decision tags have no counterpart in
    `trade`'s shape at all).

If ownership round-trips, the two representations were the same idea and
unification would have been fine; if it does not, the lost piece is
`examples.decide`'s "two domains' different ideas wearing one field name,"
made concrete. Either way the adapter is the INSTRUMENT, and `report()`
returns which way it went -- the verdict comes from the run, not from us.

## What it found

Ownership round-trips on MAGNITUDE but the adapter must INVENT two things
`cards`' own representation elides: a HOLDER (`cards` has none -- `Purse`
is a singleton, `Copies` sits on the card's own entity) and a MONEY-THING
(`cards` has no entity for money, only a `Purse` singleton). So the two
representations are NOT the same idea: they differ by exactly the holder
dimension `trade` exists to add. The split holds -- ownership adapts,
policy has nowhere to go. `report()` returns every number behind that;
the tests pin the shape, not one snapshot.

## Stated cost, matching the earlier design discussion

An adapter is O(A*B) coupling, not O(A+B) shared vocabulary, and a wrong
mapping is SILENT where a bridge cannot mistranslate. It is worth writing
exactly because it is falsifiable: `round_trip` is the fidelity pin.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples import cards, trade
from examples.cards import CardDef, Copies, Purse
from examples.trade import Agreed, Holding, Movement
from loopingrules.loop import Loop


@dataclass(frozen=True)
class Agent:
    """The HOLDER the adapter invents -- `cards`' own representation has no
    holder entity at all (see the module docstring). One per world."""
    pass


@dataclass(frozen=True)
class Coin:
    """The MONEY-THING the adapter invents -- `cards` has no entity for its
    money, only a `Purse` singleton, so an opaque `thing` for the currency
    must be supplied here. One per world."""
    pass


# -- the seam: cards <-> trade -------------------------------------------

def _agent(w):
    for entity, _component in w.all(Agent):
        return entity
    return None


def _coin(w):
    for entity, _component in w.all(Coin):
        return entity
    return None


def _holding(w, holder, thing):
    for entity, holding in w.all(Holding):
        if holding.holder == holder and holding.thing == thing:
            return entity, holding
    return None, None


def _amount(w, holder, thing):
    _entity, holding = _holding(w, holder, thing)
    return holding.amount if holding is not None else None


def _seed_holding(w, holder, thing, amount):
    """Create a `Holding` for this pair ONLY if none exists -- a one-shot
    projection. It never overwrites an existing holding, which is what
    keeps `project_ownership` from fighting `absorb_holdings` once the
    canonical world has moved an amount (see the module docstring on
    dual authority)."""
    if _holding(w, holder, thing)[0] is None:
        w.spawn(Holding(holder, thing, amount))


def project_ownership(w) -> None:
    """cards -> trade, SEED-ONLY: for the purse and for every card's own
    `Copies`, make sure a `trade.Holding` exists for (agent, thing). Never
    rewrites an existing holding -- the hand-off to `absorb_holdings`,
    which is authoritative afterwards. Idempotent: a second pass finds
    every holding already there and changes nothing."""
    agent = _agent(w)
    coin = _coin(w)
    if agent is None or coin is None:
        return
    purse = w.the(Purse)
    if purse is not None:
        _seed_holding(w, agent.id, coin.id, purse.cash)
    for entity, _card_def, copies in w.each(CardDef, Copies):
        _seed_holding(w, agent.id, entity.id, copies.count)


def absorb_holdings(w) -> None:
    """trade -> cards, AUTHORITATIVE: write the canonical amounts back into
    cards' OWN shapes -- the purse's cash and each card's `Copies`. This is
    the direction that lets a domain keep its representation and still
    have an exchange apply to it: the effect lands in `Holding`, and this
    rule is what makes `cards.Purse`/`cards.Copies` reflect it. Idempotent
    (replacing an equal value moves no revision)."""
    agent = _agent(w)
    coin = _coin(w)
    if agent is None or coin is None:
        return
    cash = _amount(w, agent.id, coin.id)
    if cash is not None:
        found = w.first(Purse)
        if found is not None:
            w.replace(found[0], Purse(cash))
    for entity, _card_def in w.all(CardDef):
        held = _amount(w, agent.id, entity.id)
        if held is not None:
            w.replace(entity, Copies(held))


RULES = (project_ownership, absorb_holdings)


def install(loop) -> None:
    """Compose both adapter rules with `trade`'s own, then seed the two
    handles the adapter invents. Registration order puts `project` before
    `trade.apply_movements` before `absorb`, so a purchase spawned before a
    settle lands in `cards`' own shapes within the SAME tick it is applied."""
    loop.rule(project_ownership)
    trade.install(loop)
    loop.rule(absorb_holdings)
    world = loop.world
    if _agent(world) is None:
        world.spawn(Agent())
    if _coin(world) is None:
        world.spawn(Coin())


# -- driving it ----------------------------------------------------------

def propose_buy(w, thing, price) -> None:
    """Describe a purchase as a pair of movements and agree to them -- the
    domain's own act of deciding to buy, expressed in `trade`'s shape
    without `cards` ever naming a `Holding` itself."""
    agent = _agent(w)
    coin = _coin(w)
    w.spawn(Movement(agent.id, coin.id, -price), Agreed())
    w.spawn(Movement(agent.id, thing.id, +1), Agreed())


def _card_entity(w, name):
    for entity, card_def in w.all(CardDef):
        if card_def.name == name:
            return entity
    raise AssertionError("no such card: %r" % name)


def _copies_of(w, name):
    copies = w.get(_card_entity(w, name), Copies)
    return copies.count if copies else 0


def snapshot(w):
    """cards' own view of ownership, in its own shapes -- the thing a
    round-trip must leave unchanged."""
    purse = w.the(Purse)
    return {
        "cash": purse.cash if purse is not None else None,
        "copies": {card_def.name: _copies_of(w, card_def.name)
                   for _entity, card_def in w.all(CardDef)},
    }


def cards_world(cash=100, held=None):
    loop = Loop()
    cards.install(loop, cash=cash)
    w = loop.world
    for name, count in (held or {}).items():
        w.replace(_card_entity(w, name), Copies(count))
    return loop, w


def round_trip(cash=100, held=None):
    """cards -> trade -> cards, with NO movement: is it the identity on
    cards' own representation? Returns `(before, after)` snapshots."""
    loop, w = cards_world(cash, held)
    before = snapshot(w)
    install(loop)
    loop.run()
    after = snapshot(w)
    return before, after


def demo_purchase(card_name="dragon", price=40, cash=100):
    """A purchase performed entirely in `trade`'s canonical shape -- two
    `Movement`s, `Agreed` -- then absorbed back into cards. No card rule
    decided OR executed it: only the adapter and `trade` did. Returns the
    settled world."""
    loop, w = cards_world(cash)
    install(loop)
    loop.run()                                 # seed holdings from cards
    propose_buy(w, _card_entity(w, card_name), price)
    loop.run()                                 # move, then absorb
    return w


def residual():
    """Everything in cards' own representation that has NO counterpart in
    `trade`'s shape -- the "value" half of the form/value split, named
    rather than left implicit."""
    return {
        "value": "CardDef.value -- worth, not amount",
        "wants": "Wants.qty -- a goal, not a holding",
        "max_premium": "RiskProfile.max_premium -- policy",
        "max_spend_per_trade": "RiskProfile.max_spend_per_trade -- policy",
        "min_cash_reserve": "RiskProfile.min_cash_reserve -- policy",
        "decision": "Wanted/Affordable/FairPriced, judge.TooRisky -- decision",
    }


def report():
    """The whole probe in one dict, so a caller can print or assert on all
    of it: does ownership round-trip, what the adapter had to invent, where
    the purchase landed, and what has no home -- plus the verdict."""
    before, after = round_trip(held={"dragon": 2, "goblin": 1})
    purchased = demo_purchase()
    _bare_loop, bare = cards_world()

    ownership_round_trips = before == after
    purchase_landed = (purchased.the(Purse) == Purse(60)
                       and _copies_of(purchased, "dragon") == 1)
    return {
        "ownership_round_trips": ownership_round_trips,
        "purchase_landed_in_cards": purchase_landed,
        "adapter_invents": ("Agent", "Coin"),
        "cards_alone_counts": {
            "holdings": len(bare.all(Holding)),
            "holders": len(bare.all(Agent)),
        },
        "no_home_in_trade": tuple(sorted(residual())),
        "verdict": ("split: ownership adapts losslessly; policy stays island"
                    if ownership_round_trips and purchase_landed
                    else "representations differ in magnitude too"),
    }
