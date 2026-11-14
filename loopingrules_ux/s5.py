"""S5 -- the walking skeleton: a grown controller composes two islands.

The probe (`docs/plan-ux.md`, Phase U1; `docs/decisions.md`, spike S5): **can a
controller, grown by search, compose two independent islands -- a routing
island and a trading island -- into a multi-step, cross-island trajectory that
maximises a MECHANICAL score, and does it generalise to held-out scenarios?**

It is the whole thesis, cheaply, and it uses only what already exists: the
rule-level scheduler (`Loop(schedule=True)` + `loop.rule(controller=True)`),
the attribute substrate, and `analyze`. No rule-as-entity, no kernel fold, no
import from the red forge.

## The two islands

* **`route`** -- one rule, `move_trader`: move the trader one hop along a
  `route` toward its `route_target`, paying the `fare`. It knows nothing about
  cards, prices or policies.
* **`trade`** -- two rules, `buy_here`/`sell_here`: buy the `want` card's
  `listing` at the trader's own city, and later sell it on the `offer` there.
  They know nothing about routes or the grown policy.

Neither island reads the policy. They compose only through the world.

## The controller, and the hole it leaves

`choose_deal` reads the **cross-island context** -- every `listing`/`offer`
(with its city and price) and every `route` fare -- picks the best arbitrage
`spread = sell_price - buy_price - fare`, and, **iff** the grown policy's
`condition` qualifies it, sets the control attributes `want`/`buy_city`/
`sell_city`/`route_target`. The trader's `held` then sequences the rest by
stigmergy: buy, move, sell.

So the **growth** is over the policy: a subset of three predicates
(`spread>0`, `spread>margin`, `affordable`) plus a `margin`. That policy is
**world data** (an entity the controller reads), not code -- which is what
keeps the controller `analyze`-clean and the pipeline honest (ADR-2's
"concepts declared, wiring/values grown").

## What the probe shows, and what it does not

It shows the **pipeline**: composed islands + a grown policy + a mechanical
fitness (final cash) + held-out generalisation. The search here is deliberately
trivial -- an exhaustive sweep of a tiny policy space, no GP -- exactly as
`evolve` first proved its pipeline on a toy. What it does **not** do: it does
not use the real `examples.trip`/`examples.market` (their models differ -- a
plan-search and a stationary market -- where the composite needs a *moving
trader*); and it routes by **control attributes**, not `RuleControl`, because
per-deal selection ("buy *this* card") is a *binding* choice a rule-level
switch cannot express -- the scheduler doc's own point. The anchor schema and
the island library are later phases (U2, U3).
"""

from __future__ import annotations

from itertools import combinations

from loopingrules.loop import Loop
from loopingrules.world import World

# The declared ref attribute names, so `share` could remap them (unused here,
# but the probe should be an honest attribute-substrate world).
REFS = {"from", "to", "card", "city", "at", "route_target", "want",
        "buy_city", "sell_city"}

# The predicates the grown policy may select, ANDed together. `affordable` is
# what generalises: without it, a tight-but-profitable deal is attempted and the
# trader strands itself (buys, then cannot pay the fare).
PREDICATES = ("spread>0", "spread>margin", "affordable")

_MARGINS = (-10 ** 9, 0.0, 5.0, 10.0, 20.0, 35.0)


def _spawn(w, tag, **attributes):
    entity = w.spawn()
    w.mark(entity, tag)
    for name, value in attributes.items():
        w.set(entity, name, value)
    return entity


# -- the world ----------------------------------------------------------

def build(scenario, condition=(), margin=0.0):
    """Build one scenario's world: cities, routes, per-card listing/offer, the
    trader, and the grown `policy`. Returns `(world, trader)`.

    A scenario is `{"cities", "routes", "cards", "cash", "start"}`; a card maps
    to `(buy_city, buy_price, sell_city, sell_price)`. This dict *is* the
    structured input the probe reads -- the full anchor schema is Phase U2.
    """
    w = World()
    w.refs = set(REFS)
    cities = {name: _spawn(w, "city", name=name) for name in scenario["cities"]}
    for (a, b, fare) in scenario["routes"]:
        _spawn(w, "route", **{"from": cities[a], "to": cities[b], "fare": fare})
    for _name, (bcity, bprice, scity, sprice) in scenario["cards"].items():
        card = _spawn(w, "card", name=_name, value=0)
        _spawn(w, "listing", card=card, city=cities[bcity], price=bprice)
        _spawn(w, "offer", card=card, city=cities[scity], price=sprice)
    start = cities[scenario["start"]]
    trader = _spawn(w, "trader", at=start, cash=scenario["cash"], held=0,
                    route_target=start)
    _spawn(w, "policy", margin=float(margin), condition=list(condition))
    return w, trader


# -- the islands --------------------------------------------------------

def move_trader(w) -> None:
    """The ROUTE island: one hop toward `route_target`, if a direct `route`
    exists and the fare is affordable. Oblivious to cards and policies."""
    for (t, _tag, at, target, cash) in w.each("trader", "at", "route_target",
                                              "cash", without=("done",)):
        if at == target:
            continue
        for (_r, _rtag, frm, to, fare) in w.each("route", "from", "to", "fare"):
            if frm == at and to == target and cash >= fare:
                w.set(t, "at", to)
                w.set(t, "cash", cash - fare)
                break


def buy_here(w) -> None:
    """The TRADE island, buy half: the `want` card's `listing` at the trader's
    own city, if affordable. Oblivious to routes and policies."""
    for (t, _tag, at, cash, want, buy_city) in w.each(
            "trader", "at", "cash", "want", "buy_city", without=("done",)):
        if at != buy_city or w.get(t, "held", 0):
            continue
        for (_l, _ltag, card, city, price) in w.each("listing", "card", "city",
                                                     "price"):
            if card != want or city != at or cash < price:
                continue
            w.set(t, "cash", cash - price)
            w.set(t, "held", 1)
            outcome = w.spawn()
            w.mark(outcome, "bought")
            w.set(outcome, "card", card)
            w.set(outcome, "price", price)
            break


def sell_here(w) -> None:
    """The TRADE island, sell half: the held `want` card on the `offer` at the
    trader's own city, then mark the trader `done`."""
    for (t, _tag, at, cash, want, sell_city) in w.each(
            "trader", "at", "cash", "want", "sell_city", without=("done",)):
        if at != sell_city or not w.get(t, "held", 0):
            continue
        for (_o, _otag, card, city, price) in w.each("offer", "card", "city",
                                                     "price"):
            if card != want or city != at:
                continue
            w.set(t, "cash", cash + price)
            w.set(t, "held", 0)
            w.mark(t, "done")
            outcome = w.spawn()
            w.mark(outcome, "sold")
            w.set(outcome, "card", card)
            w.set(outcome, "price", price)
            break


# -- the controller (the grown part) ------------------------------------

def _fare(w, frm, to):
    """The fare of a direct route `frm -> to`, or `None`. A same-module helper
    the controller passes `w` into, so `analyze` follows it."""
    for (_r, _tag, a, b, fare) in w.each("route", "from", "to", "fare"):
        if a == frm and b == to:
            return fare
    return None


def _best_deal(w):
    """The highest-`spread` arbitrage across every (card, listing, offer)
    reachable by a direct route, or `None`."""
    best = None
    for (_l, _ltag, card, bcity, bprice) in w.each("listing", "card", "city",
                                                   "price"):
        for (_o, _otag, ocard, scity, sprice) in w.each("offer", "card", "city",
                                                        "price"):
            if ocard != card:
                continue
            fare = _fare(w, bcity, scity)
            if fare is None:
                continue
            spread = sprice - bprice - fare
            if best is None or spread > best["spread"]:
                best = {"card": card, "buy_city": bcity, "buy_price": bprice,
                        "sell_city": scity, "sell_price": sprice,
                        "fare": fare, "spread": spread}
    return best


def _qualifies(condition, spread, margin, cash, buy_price, fare) -> bool:
    """Every predicate in `condition` holds. A PURE helper (no `w`), so
    `analyze` does not follow the controller into it -- the condition is the
    grown *data*, not code."""
    for predicate in condition:
        if predicate == "spread>0" and not spread > 0:
            return False
        if predicate == "spread>margin" and not spread > margin:
            return False
        if predicate == "affordable" and not cash >= buy_price + fare:
            return False
    return True


def choose_deal(w) -> None:
    """The controller: read the cross-island context, and set the control
    attributes that route the trajectory. It only ever WRITES control
    attributes (`want`/`buy_city`/`sell_city`/`route_target`); the islands do
    the acting -- selects, never rewrites (locked 8)."""
    policy = w.first("policy")
    margin = w.get(policy[0], "margin") if policy else 0.0
    condition = w.get(policy[0], "condition", []) if policy else []
    for (t, _tag, at, cash) in w.each("trader", "at", "cash"):
        if w.has(t, "done"):
            w.set(t, "route_target", at)
            continue
        if w.get(t, "held", 0):
            w.set(t, "route_target", w.get(t, "sell_city"))
            continue
        deal = _best_deal(w)
        if deal is None or not _qualifies(condition, deal["spread"], margin,
                                          cash, deal["buy_price"],
                                          deal["fare"]):
            w.set(t, "route_target", at)
            continue
        w.set(t, "want", deal["card"])
        w.set(t, "buy_city", deal["buy_city"])
        w.set(t, "sell_city", deal["sell_city"])
        w.set(t, "route_target", deal["buy_city"])


ISLANDS = (move_trader, buy_here, sell_here)


# -- running one scenario ----------------------------------------------

def evaluate(scenario, condition, margin):
    """Run one scenario under `condition`/`margin`. Returns `(profit, settled)`
    where `profit` is final cash minus starting cash."""
    w, trader = build(scenario, condition, margin)
    loop = Loop(world=w, schedule=True, budget=200)
    loop.rule(choose_deal, priority=100, controller=True)
    for rule in ISLANDS:
        loop.rule(rule)
    settled = loop.run()
    return w.get(trader, "cash") - scenario["cash"], settled


# -- the growth: a tiny, exhaustive search over the policy --------------

def _candidates():
    for size in range(len(PREDICATES) + 1):
        for subset in combinations(PREDICATES, size):
            for margin in _MARGINS:
                yield list(subset), margin


def grow(train):
    """Grow a policy `(condition, margin)` by exhaustive search over a tiny
    space, scored by total profit on `train` and gated by settling. The
    algorithm is deliberately trivial -- the probe proves the PIPELINE, not a
    search; D9 chooses the real one by a later probe."""
    best = None
    for condition, margin in _candidates():
        total = 0.0
        for scenario in train:
            profit, settled = evaluate(scenario, condition, margin)
            if settled.hot:
                total = None
                break
            total += profit
        if total is not None and (best is None or total > best[0] + 1e-9):
            best = (total, condition, margin)
    return best[1], best[2]


# -- scenarios ----------------------------------------------------------

# The same two cities and one route; the difference is the spread and the cash.
SCENARIOS_TRAIN = (
    {"name": "profit",         "cities": ["A", "B"], "start": "A", "cash": 100,
     "routes": [("A", "B", 5)], "cards": {"w": ("A", 10, "B", 50)}},   # +35
    {"name": "loss",           "cities": ["A", "B"], "start": "A", "cash": 100,
     "routes": [("A", "B", 5)], "cards": {"w": ("A", 60, "B", 50)}},   # -15
    {"name": "tight_afford",   "cities": ["A", "B"], "start": "A", "cash": 20,
     "routes": [("A", "B", 5)], "cards": {"w": ("A", 10, "B", 50)}},   # +35
    {"name": "tight_unafford", "cities": ["A", "B"], "start": "A", "cash": 12,
     "routes": [("A", "B", 5)], "cards": {"w": ("A", 10, "B", 50)}},   # skip
)

SCENARIOS_TEST = (
    {"name": "big",       "cities": ["A", "B"], "start": "A", "cash": 100,
     "routes": [("A", "B", 10)], "cards": {"w": ("A", 20, "B", 90)}},  # +60
    {"name": "loss2",     "cities": ["A", "B"], "start": "A", "cash": 100,
     "routes": [("A", "B", 5)], "cards": {"w": ("A", 70, "B", 50)}},   # -25
    {"name": "edge",      "cities": ["A", "B"], "start": "A", "cash": 15,
     "routes": [("A", "B", 5)], "cards": {"w": ("A", 10, "B", 50)}},   # +35
    {"name": "unafford2", "cities": ["A", "B"], "start": "A", "cash": 14,
     "routes": [("A", "B", 5)], "cards": {"w": ("A", 10, "B", 50)}},   # skip
)


def main() -> int:
    condition, margin = grow(list(SCENARIOS_TRAIN))
    print("grown condition: %r   margin: %r" % (condition, margin))
    for name, scenarios in (("train", SCENARIOS_TRAIN), ("test", SCENARIOS_TEST)):
        total = 0.0
        for scenario in scenarios:
            profit, settled = evaluate(scenario, condition, margin)
            total += profit
            print("  %-5s %-14s profit %+6.1f  settled=%s  hot=%r"
                  % (name, scenario["name"], profit, not settled.hot,
                     list(settled.hot)))
        print("  %-5s total %+.1f" % (name, total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
