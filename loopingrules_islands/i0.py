"""I0 -- the islands/bridges/stigmergy SHAPE, and the first patterns.

Run: `python -m loopingrules_islands.i0`

`docs/plan-islands.md` (D6). Before any of this is folded into a real home,
the shape has to be shown to WORK and its failure modes shown to be
CATCHABLE. This probe puts two unrelated domains onto one foundation
(`items`), points a composition rule across two foundations (`items` and
`funds`), and checks the property the whole idea rests on with a mutant that
violates it.

Claims, each pinned by `tests/test_islands_i0.py`:

  1. the shape SETTLES, and replays to one signature;
  2. the island's decision is its OWN, declared (`@tunable`) and lint-clean;
  3. two domains reuse the SAME island objects -- zero island rules
     rewritten, and the island's own rule sees both;
  4. a composer reads `items` AND `funds` and decides something NEITHER
     island can -- the conjunction stigmergy exists for;
  5. a rule's REACH -- the entities it wrote on, read from the D1 change
     log -- is bounded by what some domain PROJECTED; an island never
     widens its own precondition;
  6. the antipattern that violates 5 -- an island FABRICATING its own
     candidates instead of domains projecting them -- is caught.

5 and 6 are the point: a check that cannot fail is not a check (`m1.py`,
`docs/plan-forge.md`).
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient
from loopingrules_calibration import Scenario, replay

from loopingrules_islands import funds, items


# ---------------------------------------------------------------------
# Two unrelated domains, each PROJECTING onto the same shape
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class Card:
    """Domain `cards`' own vocabulary. Nothing in `items` has ever heard
    of it."""
    name: str
    value: float


@dataclass(frozen=True)
class Lot:
    """Domain `lots`' own vocabulary. `lots` and `cards` import nothing
    from each other."""
    ref: str
    price: float


def propose_cards(w) -> None:
    """Domain `cards`' own bridge: a `Card` says how much it is worth, so
    it projects onto `items.Candidate`. The only thing this domain does for
    the foundation -- it never learns what `items` decided."""
    for entity, card in w.each(Card, without=items.Candidate):
        w.attach(entity, items.Candidate(card.value))


def propose_lots(w) -> None:
    """Domain `lots`' own bridge, onto the SAME shape. Writing a second
    projection is the whole of what a new domain owes the foundation."""
    for entity, lot in w.each(Lot, without=items.Candidate):
        w.attach(entity, items.Candidate(lot.price))


# ---------------------------------------------------------------------
# The conjunction: a rule reading across BOTH islands
# ---------------------------------------------------------------------

@transient
@dataclass(frozen=True)
class Affordable:
    pass


def affordable_items(w) -> None:
    """Reads `items.Item` (island A) and `funds.Spendable` (island B) and
    concludes something NEITHER island can: a promoted thing the agent can
    currently pay for. `items` has never heard of money; `funds` has never
    heard of a role; this rule imports the vocabulary of both and lives in
    neither -- the composition nobody wrote for either island."""
    spend = w.the(funds.Spendable)
    if spend is None:
        return
    for entity, item in w.each(items.Item):
        if item.worth <= spend.amount:
            w.attach(entity, Affordable())
        else:
            w.detach(entity, Affordable)


# ---------------------------------------------------------------------
# Install, and the scenarios
# ---------------------------------------------------------------------

RULES = (propose_cards, propose_lots, items.consider, items.total_worth,
         funds.spendable, affordable_items)

PROJECTION_RULES = ("propose_cards", "propose_lots")
MIN_WORTH = 10.0
CASH = 70.0
RESERVE = 10.0

SCENARIO = Scenario()


def _seed(loop) -> None:
    world = loop.world
    # One entity per component: `spawn(*components)` puts them all on ONE
    # entity, and each card is its own proposition here.
    for card in (Card("dragon", 40.0), Card("goblin", 5.0)):
        world.spawn(card)
    for lot in (Lot("lot-1", 30.0), Lot("lot-2", 90.0)):
        world.spawn(lot)
    items.seed(loop, min_worth=MIN_WORTH)
    funds.seed(loop, cash=CASH, reserve=RESERVE)


def install(loop) -> None:
    for rule in RULES:
        loop.rule(rule)
    _seed(loop)


def clean_trace():
    return replay(SCENARIO, install)


# ---------------------------------------------------------------------
# The instrument: REACH, from the D1 change log
# ---------------------------------------------------------------------

def _bare(name):
    return name.rsplit(".", 1)[-1] if isinstance(name, str) else name


def reach(trace):
    """rule (bare name) -> the set of entities it WROTE on, read from the
    D1 change log (`trace.changes`). `None`-ruled writes (an install, the
    engine draining a `Reply`) are skipped: this measures what a RULE did.

    Read from the log rather than the AST on purpose (`docs/plan-islands.md`
    open question): reach is what the rule actually TOUCHED, so a rule that
    scans everything is not made to look local by a declared read set."""
    out = {}
    for change in trace.changes:
        if change.rule is None or change.target is None:
            continue
        out.setdefault(_bare(change.rule), set()).add(change.target)
    return out


def confers_only_on_projected(trace, confer):
    """The property: the entity a role-CONFERRING rule wrote on is one some
    domain PROJECTED onto. An island never widens its own precondition --
    it decides only about what a domain offered it."""
    seen = reach(trace)
    projected = set().union(*(seen.get(name, set())
                              for name in PROJECTION_RULES))
    return seen.get(confer, set()) <= projected


# ---------------------------------------------------------------------
# The antipattern mutant
# ---------------------------------------------------------------------

def fabricating_consider(w) -> None:
    """ANTIPATTERN. Rather than wait for domains to PROJECT `Candidate`,
    this island scans the WHOLE world and invents a candidate for anything
    that lacks one -- its reach is unbounded, and it fabricates a projection
    no domain ever made. The check in claim 5 catches it; its settled world
    also differs from the clean one, because the fabricated `Candidate(0.0)`
    components stay."""
    policy = w.the(items.ItemsPolicy)
    if policy is None:
        return
    for entity in w.entities():
        if not w.has(entity, items.Candidate):
            w.attach(entity, items.Candidate(0.0))
    for entity, candidate in w.each(items.Candidate, without=items.Item):
        if candidate.worth >= policy.min_worth:
            w.attach(entity, items.Item(candidate.worth))


def fabricating_install(loop) -> None:
    for rule in (propose_cards, propose_lots, fabricating_consider,
                 items.total_worth, funds.spendable, affordable_items):
        loop.rule(rule)
    _seed(loop)


def fabricating_trace():
    return replay(SCENARIO, fabricating_install)


# ---------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------

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
    print("  %-13s %-6s %-7s %-12s %s"
          % ("RUN", "TICKS", "SETTLED", "REACH OK", "SIGNATURE"))
    for label, ticks, settled, bounded in rows:
        trace = clean if label == "clean" else fabricating
        print("  %-13s %-6d %-7s %-12s %s"
              % (label, ticks, settled, bounded, trace.signature[:12]))
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
    print("""
  Read it as: two unrelated domains land on one island with zero island
  rules rewritten; a composer reads across two islands; the role rule only
  ever touches what a domain projected -- and the FABRICATING mutant, which
  reaches everywhere, is caught. The shape works, and the check can fail.""")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
