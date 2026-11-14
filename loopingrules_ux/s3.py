"""S3 -- growing a policy that resolves AMBIGUITY between two islands.

The probe (`docs/plan-ux.md`, Phase U3; `docs/decisions.md`, spike S3, and
ADR-8's trichotomy): when **two islands both handle the same term** -- here both
propose the trader's `want` -- a person cannot feasibly say, by hand, which to
use in which situation. That is exactly what the control network is *for*
(ADR-8: "ambiguity is non-confluence; without it the system is just fixpoint
computation").

It builds on S5's world and islands, and adds the ambiguity S5 lacked:

* **`choose_arbitrage`** -- island A: propose the highest-`spread` deal.
* **`choose_bargain`** -- island B: propose the cheapest deal.
* Both write `want`/`buy_city`/`sell_city` -- they **conflict**.
* **`route_strategy`** -- the controller: pick ONE of them per tick by context,
  via `RuleControl`. This is the *rule-level* choice `RuleControl` is exactly
  right for (which island), as opposed to S5's *binding-level* choice (which
  deal), which needed control attributes.

The grown policy is one of three strategies -- the context-independent
`arbitrage` or `bargain`, or the context-dependent `afford_first` (arbitrage iff
the best-spread deal is affordable, else bargain). Growth finds `afford_first`,
which beats every fixed choice and generalises to held-out scenarios.

## The two mechanisms, side by side

S5 and S3 together pin the design's grain: **which ISLAND** is a rule-level
choice (`RuleControl`); **which DEAL/CANDIDATE** inside an island is a binding,
needing control attributes (or, later, IR-native activations). Both are "the
network selects, never rewrites" (locked 8).

The controller calls `reflect.control`, so `analyze` refuses it (`Opaque`, the
documented D7 boundary); it runs ungated. The **islands and choosers** are
`analyze`-clean, and none of them reads the policy -- the ambiguity lives only
in the controller.
"""

from __future__ import annotations

from loopingrules import reflect
from loopingrules.loop import Loop

from loopingrules_ux import s5

STRATEGIES = ("arbitrage", "bargain", "afford_first")


# -- the two conflicting chooser islands --------------------------------

def _fare(w, frm, to):
    """The fare of a direct route `frm -> to`, or `None`. Local, so `analyze`
    follows it -- a cross-module call (`s5._fare`) would be `Opaque`."""
    for (_r, _tag, a, b, fare) in w.each("route", "from", "to", "fare"):
        if a == frm and b == to:
            return fare
    return None


def _all_deals(w):
    """Every reachable (card, listing, offer) as a deal dict -- the same
    arbitrage S5's controller computes, now shared by two islands."""
    deals = []
    for (_l, _ltag, card, bcity, bprice) in w.each("listing", "card", "city",
                                                   "price"):
        for (_o, _otag, ocard, scity, sprice) in w.each("offer", "card", "city",
                                                        "price"):
            if ocard != card:
                continue
            fare = _fare(w, bcity, scity)
            if fare is None:
                continue
            deals.append({"card": card, "buy_city": bcity, "buy_price": bprice,
                          "sell_city": scity, "sell_price": sprice,
                          "fare": fare, "spread": sprice - bprice - fare})
    return deals


def _propose(w, t, deal) -> None:
    w.set(t, "want", deal["card"])
    w.set(t, "buy_city", deal["buy_city"])
    w.set(t, "sell_city", deal["sell_city"])


def choose_arbitrage(w) -> None:
    """Island A: propose the highest-`spread` deal."""
    for (t, _tag, _at, _cash) in w.each("trader", "at", "cash"):
        if w.has(t, "done") or w.get(t, "held", 0):
            continue
        deals = _all_deals(w)
        if deals:
            _propose(w, t, max(deals, key=lambda d: d["spread"]))


def choose_bargain(w) -> None:
    """Island B: propose the CHEAPEST deal -- conflicting with A on `want`."""
    for (t, _tag, _at, _cash) in w.each("trader", "at", "cash"):
        if w.has(t, "done") or w.get(t, "held", 0):
            continue
        deals = _all_deals(w)
        if deals:
            _propose(w, t, min(deals, key=lambda d: d["buy_price"]))


# -- the controller: resolve the ambiguity by context -------------------

def route(w) -> None:
    """Set `route_target` from the trader's own state (held / chosen deal)."""
    for (t, _tag, at) in w.each("trader", "at"):
        if w.has(t, "done"):
            w.set(t, "route_target", at)
            continue
        if w.get(t, "held", 0):
            w.set(t, "route_target", w.get(t, "sell_city"))
            continue
        if w.has(t, "buy_city"):
            w.set(t, "route_target", w.get(t, "buy_city"))


def _resolve(strategy, w):
    """Which chooser to enable, given the strategy and the context."""
    trader = w.first("trader")
    if trader is None:
        return (False, False)
    t = trader[0]
    if w.has(t, "done") or w.get(t, "held", 0):
        return (False, False)
    if strategy == "arbitrage":
        return (True, False)
    if strategy == "bargain":
        return (False, True)
    deals = _all_deals(w)                       # afford_first
    if not deals:
        return (False, False)
    best = max(deals, key=lambda d: d["spread"])
    affordable = w.get(t, "cash") >= best["buy_price"] + best["fare"]
    return (True, False) if affordable else (False, True)


def route_strategy(w) -> None:
    """The controller: read the policy, enable exactly one chooser via
    `RuleControl`. It never writes a domain attribute -- selects, never
    rewrites (locked 8)."""
    policy = w.first("policy")
    strategy = w.get(policy[0], "strategy", "arbitrage") if policy else "arbitrage"
    enable_arb, enable_bargain = _resolve(strategy, w)
    reflect.control(w, reflect.rule_hash(choose_arbitrage), enabled=enable_arb)
    reflect.control(w, reflect.rule_hash(choose_bargain), enabled=enable_bargain)


ISLANDS = (choose_arbitrage, choose_bargain, s5.move_trader, s5.buy_here,
           s5.sell_here)


# -- running one scenario ----------------------------------------------

def evaluate(scenario, strategy):
    """`(profit, settled)` under `strategy`."""
    w, trader = s5.build(scenario)
    w.set(w.first("policy")[0], "strategy", strategy)
    loop = Loop(world=w, schedule=True, budget=200)
    loop.rule(route_strategy, priority=100, controller=True)
    loop.rule(route, priority=90, controller=True)
    for rule in ISLANDS:
        loop.rule(rule)
    settled = loop.run()
    return w.get(trader, "cash") - scenario["cash"], settled


def grow(train):
    """Find the strategy with the best total profit on `train` (gated by
    settling). Deliberately trivial: this probe proves the AMBIGUITY is real
    and resolvable by growth, not that the search scales."""
    best = None
    for strategy in STRATEGIES:
        total = 0.0
        for scenario in train:
            profit, settled = evaluate(scenario, strategy)
            if settled.hot:
                total = None
                break
            total += profit
        if total is not None and (best is None or total > best[0] + 1e-9):
            best = (total, strategy)
    return best[1]


# -- scenarios: two cards, so the two islands disagree ------------------

SCENARIOS_TRAIN = (
    # ample: the big-spread card is affordable -> arbitrage wins
    {"name": "ample", "cities": ["A", "B"], "start": "A", "cash": 100,
     "routes": [("A", "B", 5)],
     "cards": {"big": ("A", 10, "B", 100), "small": ("A", 5, "B", 20)}},
    # tight: the big-spread card is NOT affordable -> bargain wins
    {"name": "tight", "cities": ["A", "B"], "start": "A", "cash": 30,
     "routes": [("A", "B", 5)],
     "cards": {"big": ("A", 50, "B", 200), "small": ("A", 10, "B", 40)}},
)

SCENARIOS_TEST = (
    {"name": "ample2", "cities": ["A", "B"], "start": "A", "cash": 100,
     "routes": [("A", "B", 5)],
     "cards": {"big": ("A", 20, "B", 200), "small": ("A", 5, "B", 15)}},
    {"name": "tight2", "cities": ["A", "B"], "start": "A", "cash": 40,
     "routes": [("A", "B", 5)],
     "cards": {"big": ("A", 60, "B", 300), "small": ("A", 10, "B", 50)}},
)


def _total(scenarios, strategy):
    return sum(evaluate(s, strategy)[0] for s in scenarios)


def main() -> int:
    strategy = grow(list(SCENARIOS_TRAIN))
    print("grown strategy: %r" % strategy)
    for label, scenarios in (("train", SCENARIOS_TRAIN), ("test", SCENARIOS_TEST)):
        for s in scenarios:
            print("  %-5s %-7s profit %+6.1f" % (label, s["name"],
                                                 evaluate(s, strategy)[0]))
    for fixed in STRATEGIES:
        print("  fixed %-12s held-out total %+.1f" % (fixed, _total(SCENARIOS_TEST, fixed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
