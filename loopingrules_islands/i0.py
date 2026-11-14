"""I0 -- the islands/bridges/stigmergy SHAPE, and the first patterns.

Under the attribute substrate (D8): a `card`/`lot` is a tagged entity; a
domain PROJECTS by setting a `candidate` worth; `item` is the role flag;
`spendable`/`affordable` are a singleton and a flag. Reach is read from the
change log, unchanged.
"""

from __future__ import annotations

from loopingrules_calibration import Scenario, replay

from loopingrules_islands import funds, items


# -- two unrelated domains, each PROJECTING onto the same shape ---------

def propose_cards(w) -> None:
    """Domain `cards`' bridge: a card's `value` projects onto `candidate`."""
    for entity, _t, value in w.each("card", "value", without="candidate"):
        w.set(entity, "candidate", value)


def propose_lots(w) -> None:
    """Domain `lots`' bridge, onto the SAME shape."""
    for entity, _t, price in w.each("lot", "price", without="candidate"):
        w.set(entity, "candidate", price)


# -- the conjunction: a rule reading across BOTH islands ----------------

def affordable_items(w) -> None:
    """Reads the `item` role (island A) and the `spendable` amount (island
    B) and concludes something NEITHER island can."""
    spend = w.first("spendable")
    if spend is None:
        return
    amount = spend[1]
    for entity, _t, worth in w.each("item", "candidate"):
        if worth <= amount:
            w.mark(entity, "affordable")
        else:
            w.unmark(entity, "affordable")


# -- install, and the scenarios -----------------------------------------

RULES = (propose_cards, propose_lots, items.consider, items.total_worth,
         funds.spendable, affordable_items)

PROJECTION_RULES = ("propose_cards", "propose_lots")
MIN_WORTH = 10.0
CASH = 70.0
RESERVE = 10.0

SCENARIO = Scenario()


def _seed(loop) -> None:
    world = loop.world
    for name, value in (("dragon", 40.0), ("goblin", 5.0)):
        entity = world.spawn()
        world.mark(entity, "card")
        world.set(entity, "name", name)
        world.set(entity, "value", value)
    for ref, price in (("lot-1", 30.0), ("lot-2", 90.0)):
        entity = world.spawn()
        world.mark(entity, "lot")
        world.set(entity, "ref", ref)
        world.set(entity, "price", price)
    items.seed(loop, min_worth=MIN_WORTH)
    funds.seed(loop, cash=CASH, reserve=RESERVE)


def install(loop) -> None:
    for rule in RULES:
        loop.rule(rule)
    _seed(loop)


def clean_trace():
    return replay(SCENARIO, install)


# -- the instrument: REACH, from the D1 change log ----------------------

def _bare(name):
    return name.rsplit(".", 1)[-1] if isinstance(name, str) else name


def reach(trace):
    """rule (bare name) -> the set of entities it WROTE on, read from the
    change log. `None`-ruled writes are skipped: this measures what a RULE
    did."""
    out = {}
    for change in trace.changes:
        if change.rule is None or change.target is None:
            continue
        out.setdefault(_bare(change.rule), set()).add(change.target)
    return out


def confers_only_on_projected(trace, confer):
    """The property: the entity a role-CONFERRING rule wrote on is one some
    domain PROJECTED onto."""
    seen = reach(trace)
    projected = set().union(*(seen.get(name, set())
                              for name in PROJECTION_RULES))
    return seen.get(confer, set()) <= projected


# -- the antipattern mutant ---------------------------------------------

def fabricating_consider(w) -> None:
    """ANTIPATTERN. Rather than wait for domains to PROJECT `candidate`, this
    island scans the WHOLE world and invents one for anything that lacks it
    -- its reach is unbounded."""
    policy = w.first("min_worth")
    if policy is None:
        return
    for entity in w.entities():
        if not w.has(entity, "candidate"):
            w.set(entity, "candidate", 0.0)
    floor = policy[1]
    for entity, worth in w.each("candidate", without="item"):
        if worth >= floor:
            w.mark(entity, "item")


def fabricating_install(loop) -> None:
    for rule in (propose_cards, propose_lots, fabricating_consider,
                 items.total_worth, funds.spendable, affordable_items):
        loop.rule(rule)
    _seed(loop)


def fabricating_trace():
    return replay(SCENARIO, fabricating_install)


# -- run ----------------------------------------------------------------

def run_all():
    clean = clean_trace()
    fabricating = fabricating_trace()
    rows = [
        ("clean", clean.ticks, not clean.hot,
         confers_only_on_projected(clean, "consider")),
        ("fabricating", fabricating.ticks, not fabricating.hot,
         confers_only_on_projected(fabricating, "fabricating_consider")),
    ]
    return clean, fabricating, rows


def main():
    clean, fabricating, rows = run_all()
    print("== i0: the islands/bridges shape", "=" * 34)
    print("  domains: cards, lots  ->  island: items  <-  island: funds")
    print()
    seen = reach(clean)
    print("  reach (entities a rule wrote on), clean run:")
    for name in sorted(seen):
        print("    %-22s %s" % (name, sorted(seen[name])))
    print()
    print("  two different signatures:",
          clean.signature != fabricating.signature)
    ok = (not clean.hot and not fabricating.hot
          and confers_only_on_projected(clean, "consider")
          and not confers_only_on_projected(fabricating, "fabricating_consider")
          and clean.signature != fabricating.signature)
    print("  ALL AS EXPECTED:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
