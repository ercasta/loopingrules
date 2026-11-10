"""Q0 -- the recognize–act cycle over ACTIVATIONS: match -> resolve -> act.

Run: `python -m loopingrules_forge.q0`

`docs/plan-scheduler.md`'s first probe, in the M0-M2 / r0-r1 / i0 posture:
small, self-contained, and honest about what it does not settle. It tests
three claims and nothing else.

## The three claims

1. **Match is exact, and it is not the gate.** A rule reshaped to `LHS -> RHS`
   (a condition and an effect) matches with a *predicate*, so "would fire" is
   decidable without side effects -- unlike `analyze`'s derived gate, which is
   "the read-set is populated" and over-approximates. Shown on real `cards`
   code: `cards.decide_buy`'s guard is re-expressed as LHS data, and its match
   set equals the set of listings the actual rule buys.
2. **No ambiguity => identical to running everything.** When at most one
   activation is eligible in a tick, the recognize–act cycle (one activation
   per tick) produces the SAME `signature` as the ordinary loop (every match
   of every rule, per tick). The scheduler is a *conservative extension*: it
   only changes behaviour when there is a choice.
3. **Starvation is real, and refraction fixes it.** Several activations
   eligible every tick, resolved by the deterministic DEFAULT score, starve
   all but one; a controller whose score the effect itself moves
   (`refraction`) restores fairness. The default fallback is also the
   **novelty** path -- no controller has an opinion -> the frozen default
   score, and a `Doubt` recorded.

## What this is NOT

This does not touch the engine. `docs/plan-scheduler.md` leaves open whether
the tick becomes three phases in the loop core or whether activations are
materialised by a generic rule; this probe takes the *engine-lighter* path and
implements the cycle as a standalone scheduler over a `World`, to prove the
MECHANISM before any core change is earned. It does not partition activations
into conflict sets (the hazard graph the plan drops); it picks ONE activation
per tick, globally. The RHS is a small effect IR, not full `m0`; lowering an
effect to Python is M0's already-proven step, and is not redone here.

## What this does not settle

* **No-op activations.** A chosen activation that writes an equal value is not
  dropped-and-re-chosen here; every effect in this probe moves the world.
* **Fairness/stability, in general.** Refraction is demonstrated on one
  domain; it is a good practice, not a proof (`docs/plan-adaptation.md` offers
  none either). The budget breaker is the backstop.
* **Conflict sets, score persistence, one activation vs a maximal set.** All
  remain open in `docs/plan-scheduler.md`.
"""

from __future__ import annotations

import collections
import dataclasses

import loopingrules.analyze as analyze

from examples import cards
from loopingrules.world import World

from loopingrules_calibration.kit import _signature
from loopingrules_forge import m0


# =====================================================================
# 1. A tiny LHS/RHS IR -- the condition as DATA, and the effect as DATA
# =====================================================================

# -- LHS expressions ---------------------------------------------------
# A predicate over the bound entity (`ctx`/`get`/`has`), the singleton
# components (`single`), and literals. Closed and total: every tag is
# evaluable, so matching is decidable.
def p_lit(v):                 return ("lit", v)
def p_ctx(kind, name):        return ("ctx", kind, name)
def p_single(kind, name):     return ("single", kind, name)
def p_get(e, kind, name):     return ("get", e, kind, name)
def p_has(e, kind):           return ("has", e, kind)
def p_attr(e, name):          return ("attr", e, name)
def p_bin(op, a, b):          return ("bin", op, a, b)
def p_cmp(op, a, b):          return ("cmp", op, a, b)
def p_and(a, b):              return ("and", a, b)
def p_or(a, b):               return ("or", a, b)
def p_not(a):                 return ("not", a)
def p_isnone(e):              return ("isnone", e)
def p_notnone(e):             return ("notnone", e)


KNOWN_EXPR = frozenset({
    "lit", "ctx", "single", "get", "has", "attr", "bin", "cmp", "and", "or",
    "not", "isnone", "notnone",
})
_BIN = {"+": lambda a, b: a + b, "-": lambda a, b: a - b,
        "*": lambda a, b: a * b, "/": lambda a, b: a / b}
_CMP = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def expr_tags(e) -> set:
    """Every tag in an expression -- the totality check (no unknown node)."""
    if not isinstance(e, tuple):
        return set()
    found = {e[0]} if e[0] in KNOWN_EXPR else {e[0]}
    for child in e[1:]:
        found |= expr_tags(child)
    return found


def eval_expr(world, binding, e):
    tag = e[0]
    if tag not in KNOWN_EXPR:
        raise ValueError("unknown expression %r" % (tag,))
    if tag == "lit":
        return e[1]
    if tag == "ctx":
        c = world.get(binding, e[1])
        return getattr(c, e[2]) if c is not None else None
    if tag == "single":
        c = world.the(e[1])
        return getattr(c, e[2]) if c is not None else None
    if tag == "get":
        ent = eval_expr(world, binding, e[1])
        c = world.get(ent, e[2]) if ent is not None else None
        return getattr(c, e[3]) if c is not None else None
    if tag == "has":
        ent = eval_expr(world, binding, e[1])
        return ent is not None and world.get(ent, e[2]) is not None
    if tag == "attr":
        obj = eval_expr(world, binding, e[1])
        return getattr(obj, e[2])
    if tag == "bin":
        return _BIN[e[1]](eval_expr(world, binding, e[2]),
                          eval_expr(world, binding, e[3]))
    if tag == "cmp":
        return _CMP[e[1]](eval_expr(world, binding, e[2]),
                          eval_expr(world, binding, e[3]))
    if tag == "and":
        return bool(eval_expr(world, binding, e[1])
                    and eval_expr(world, binding, e[2]))
    if tag == "or":
        return bool(eval_expr(world, binding, e[1])
                    or eval_expr(world, binding, e[2]))
    if tag == "not":
        return not eval_expr(world, binding, e[1])
    if tag == "isnone":
        return eval_expr(world, binding, e[1]) is None
    if tag == "notnone":
        return eval_expr(world, binding, e[1]) is not None
    raise ValueError("unhandled %r" % (tag,))              # pragma: no cover


def match(world, lhs) -> list:
    """The ACTIVATIONS of one LHS: the bound entities whose guard holds.

    `lhs = ("each", kinds, without, guard)`. This is the exact "would fire"
    -- the guard, not the gate -- evaluated without applying any effect."""
    tag, kinds, without, guard = lhs
    assert tag == "each"
    rows = world.each(*kinds, without=without)
    out = [row[0].id for row in rows if eval_expr(world, row[0], guard)]
    return sorted(out)


# -- RHS effects -------------------------------------------------------
def e_replace(kind, **fields):  return ("replace", kind, fields)
def e_attach(kind):             return ("attach", kind)
def e_destroy():                return ("destroy",)


def apply(world, binding, effects) -> None:
    """Apply one activation's effects to the world -- the ACT phase."""
    for eff in effects:
        if eff[0] == "replace":
            world.replace(binding, eff[1](**{
                f: eval_expr(world, binding, e) for f, e in eff[2].items()}))
        elif eff[0] == "attach":
            world.attach(binding, eff[1]())
        elif eff[0] == "destroy":
            world.destroy(binding)
        else:                                              # pragma: no cover
            raise ValueError("unknown effect %r" % (eff[0],))


# =====================================================================
# 2. Claim 1 -- match is exact, on a real `cards` rule
# =====================================================================

# `cards.decide_buy`'s guard, re-expressed as LHS data. The pattern it already
# requires (three tags, not TooRisky) is the LHS's `kinds`/`without`; the two
# conditions it tests before acting are the `guard`.
LHS_DECIDE_BUY = (
    "each", (cards.Listing, cards.Wanted, cards.Affordable, cards.FairPriced),
    (cards.TooRisky,),
    p_and(
        p_has(p_ctx(cards.Listing, "card"), cards.Wants),
        p_and(
            p_cmp("<",
                  p_get(p_ctx(cards.Listing, "card"), cards.Copies, "count"),
                  p_get(p_ctx(cards.Listing, "card"), cards.Wants, "qty")),
            p_cmp("<=", p_ctx(cards.Listing, "price"),
                  p_bin("-", p_single(cards.Purse, "cash"),
                        p_single(cards.RiskProfile, "min_cash_reserve"))),
        ),
    ),
)


def cards_world():
    """A tiny world with exactly the shape claim 1 needs: two tagged
    listings, one affordable and one not. Returns `(world, {entity})`."""
    w = World()
    w.spawn(cards.Purse(100))
    w.spawn(cards.RiskProfile(max_spend_per_trade=50, min_cash_reserve=0,
                              max_premium=0.25))
    listings = set()
    for name, price in (("dragon", 10), ("goblin", 999)):
        card = w.spawn(cards.CardDef(name, "rare", 40))
        w.attach(card, cards.Copies(0))
        w.attach(card, cards.Wants(1))
        row = w.spawn(cards.Listing(card, price))
        w.attach(row, cards.Wanted())
        w.attach(row, cards.Affordable())
        w.attach(row, cards.FairPriced())
        listings.add(row.id)
    return w, listings


def eligible_decide_buy(world) -> set:
    """The GATE's set: listings carrying the tags the rule reads, ignoring
    the rule's own conditions -- the over-approximation `analyze` gives."""
    return {row[0].id for row in world.each(
        cards.Listing, cards.Wanted, cards.Affordable, cards.FairPriced,
        without=cards.TooRisky)}


def fired_decide_buy(world) -> set:
    """The set the REAL rule acts on: run it once and see which listings it
    destroyed. This is the ground truth `LHS_DECIDE_BUY` must match."""
    before = {row[0].id for row in world.each(cards.Listing)}
    cards.decide_buy(world)
    after = {row[0].id for row in world.each(cards.Listing)}
    return before - after


def claim_1_match_is_exact() -> dict:
    world, _all = cards_world()
    eligible = eligible_decide_buy(world)
    exact = set(match(world, LHS_DECIDE_BUY))
    fired = fired_decide_buy(world)
    total = all(t in KNOWN_EXPR for t in expr_tags(LHS_DECIDE_BUY[3]))
    # the reshape introduces no new escape: the verbatim-helper set is the
    # one M0 declared, and `decide_buy` already analyzes clean.
    try:
        analyze.analyze(cards.decide_buy)
        opaque = False
    except analyze.Opaque:
        opaque = True
    return {
        "eligible": eligible, "exact": exact, "fired": fired,
        "guard_total": total, "opaque": opaque,
        "escapes": len(m0.VERBATIM),
        "ok": (exact == fired and exact < eligible and total
               and not opaque and len(m0.VERBATIM) == 2),
    }


# =====================================================================
# 3. Claim 2 -- no ambiguity => identical to running everything
# =====================================================================

@dataclasses.dataclass(frozen=True)
class Task:
    done: int = 0


@dataclasses.dataclass(frozen=True)
class Quota:
    """How many times a task must be served -- a singleton, not a literal, so
    a rule reads it (`docs/tuning.md`)."""

    n: int = 3


@dataclasses.dataclass(frozen=True)
class Production:
    """A rule as data: an LHS condition and an RHS effect. `meter` names the
    tally field its effect feeds, which the refraction score reads back."""

    key: str
    lhs: tuple
    rhs: tuple
    priority: int = 0
    meter: str = ""


LHS_SERVE = ("each", (Task,), (),
             p_cmp("<", p_ctx(Task, "done"), p_single(Quota, "n")))
RHS_SERVE = (e_replace(Task, done=p_bin("+", p_ctx(Task, "done"), p_lit(1))),)

SERVE = Production("serve", LHS_SERVE, RHS_SERVE)


def one_task_world():
    w = World()
    w.spawn(Quota(3))
    w.spawn(Task(0))
    return w


def run_baseline(world, productions, budget=200):
    """The ordinary loop, over produced rules: every rule, every tick, ALL of
    its matches, until a whole pass changes nothing. `fired` is one key per
    rule that matched. This is what the scheduler must agree with when there
    is no ambiguity."""
    fired = []
    for _ in range(budget):
        changed = False
        for prod in productions:
            bindings = match(world, prod.lhs)
            for binding in bindings:
                apply(world, binding, prod.rhs)
            if bindings:
                changed = True
                fired.append(prod.key)
        if not changed:
            return world, tuple(fired), False
    return world, tuple(fired), True


def claim_2_no_ambiguity() -> dict:
    base_w, base_fired, base_hot = run_baseline(one_task_world(), (SERVE,))
    sched_w, sched_fired, sched_hot, _d = run_schedule(
        one_task_world(), (SERVE,), budget=200)
    base_sig = _signature(base_w, base_fired)
    sched_sig = _signature(sched_w, sched_fired)
    return {
        "base_fired": base_fired, "sched_fired": sched_fired,
        "base_sig": base_sig, "sched_sig": sched_sig,
        "ok": (base_sig == sched_sig and not base_hot and not sched_hot),
    }


# =====================================================================
# 4. Claim 3 -- starvation, refraction, and the novelty fallback
# =====================================================================

@dataclasses.dataclass(frozen=True)
class Tally:
    a: int = 0
    b: int = 0


@dataclasses.dataclass(frozen=True)
class Uses:
    """Total servings left. Both productions stop matching at zero, so the
    world SETTLES -- the conflict is only over which production spends each
    use."""

    n: int = 6


@dataclasses.dataclass(frozen=True)
class Doubt:
    """A novelty record, deposited as ordinary world data (`docs/
    plan-scheduler.md`): no controller had an opinion, so the frozen default
    was used and the situation was written down for the forge."""

    activation: str = ""


BOARD_LHS = ("each", (Tally, Uses), (),
             p_cmp(">", p_ctx(Uses, "n"), p_lit(0)))


def _board_rhs(meter):
    other = "b" if meter == "a" else "a"
    # a replace rebuilds the WHOLE component, so the other tally must be
    # carried across -- otherwise it resets to its default each time.
    return (e_replace(Tally,
                      **{meter: p_bin("+", p_ctx(Tally, meter), p_lit(1)),
                         other: p_ctx(Tally, other)}),
            e_replace(Uses, n=p_bin("-", p_ctx(Uses, "n"), p_lit(1))))


BOARD = (Production("serve_a", BOARD_LHS, _board_rhs("a"), meter="a"),
         Production("serve_b", BOARD_LHS, _board_rhs("b"), meter="b"))


def board_world():
    w = World()
    board = w.spawn(Tally(0, 0))       # one board carrying both the tallies
    w.attach(board, Uses(6))           # and the uses left to spend
    return w


# -- the control network: controllers that score activations -------------
Controller = collections.namedtuple("Controller", "name score")


def default_score(prod, binding, world) -> float:
    """The FROZEN default: a production's declared priority. Deterministic,
    learned from nothing, in the runtime path on purpose (`docs/plan-
    scheduler.md`'s novelty fallback)."""
    return float(prod.priority)


def refraction(prod, binding, world):
    """A controller score the EFFECT itself moves: a production's own tally
    (what it has already done) counts AGAINST it, so serving drops your score
    and hands the next tick to the other activation. OPS5's refraction, as a
    component -- no separate fairness bookkeeping."""
    tally = world.get(binding, Tally)
    return -float(getattr(tally, prod.meter)) if tally is not None else 0.0


FROZEN = Controller("frozen", lambda prod, binding, world: prod.priority)
REFRACT = Controller("refraction", refraction)


def resolve(activations, world, controllers):
    """Conflict resolution: `argmax` over each activation's score, with a
    deterministic tie-break. Novelty -- NO controller had an opinion -- falls
    back to `default_score` and is returned as a doubt."""
    scored = []
    opined = False
    for prod, binding in activations:
        total = None
        for controller in controllers:
            value = controller.score(prod, binding, world)
            if value is not None:
                total = value if total is None else total + value
                opined = True
        if total is None:
            total = default_score(prod, binding, world)
        scored.append((total, prod.key, binding, prod))
    # deterministic: best score, then key, then entity
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    _score, _key, binding, prod = scored[0]
    doubts = [] if opined else [prod.key]
    return prod, binding, doubts


def run_schedule(world, productions, controllers=(), budget=200,
                 write_doubts=False):
    """The recognize-act cycle: match -> resolve -> act, one activation per
    tick, until nothing matches (settle) or the budget runs out (`hot`)."""
    fired = []
    doubts = []
    for _ in range(budget):
        activations = [(prod, binding)
                       for prod in productions
                       for binding in match(world, prod.lhs)]
        if not activations:
            return world, tuple(fired), False, tuple(doubts)
        prod, binding, new_doubts = resolve(activations, world, controllers)
        if write_doubts:
            for key in new_doubts:
                world.spawn(Doubt(key))
        doubts.extend(new_doubts)
        apply(world, binding, prod.rhs)
        fired.append(prod.key)
    return world, tuple(fired), True, tuple(doubts)


def tallies(world):
    tally = world.the(Tally)
    return (tally.a, tally.b)


def eligible_b_ticks(world, productions=BOARD, budget=200):
    """How many ticks `serve_b` was a live activation -- so "starved" means
    eligible-but-never-chosen, not absent."""
    ticks = 0
    for _ in range(budget):
        activations = [(prod, binding) for prod in productions
                       for binding in match(world, prod.lhs)]
        if not activations:
            break
        if any(prod.key == "serve_b" for prod, _binding in activations):
            ticks += 1
        # advance with the FROZEN default, the case being demonstrated
        prod, binding, _d = resolve(activations, world, ())
        apply(world, binding, prod.rhs)
    return ticks


def claim_3_starvation_and_novelty() -> dict:
    # no controller -> novelty -> frozen default: one production starves.
    starved_w, starved_fired, starved_hot, starved_doubts = run_schedule(
        board_world(), BOARD, controllers=(), write_doubts=True)
    eligible_b = eligible_b_ticks(board_world())
    starved_tally = tallies(starved_w)
    starved_world_doubts = len(starved_w.each(Doubt))

    # an explicit frozen controller: the SAME schedule, but not "novelty".
    frozen_w, frozen_fired, _hot, frozen_doubts = run_schedule(
        board_world(), BOARD, controllers=(FROZEN,))

    # refraction: the effect moves the score, so the other activation wins.
    fair_w, fair_fired, fair_hot, _d = run_schedule(
        board_world(), BOARD, controllers=(REFRACT,))
    fair_tally = tallies(fair_w)

    return {
        "starved_fired": starved_fired, "starved_tally": starved_tally,
        "starved_hot": starved_hot, "eligible_b_ticks": eligible_b,
        "starved_doubts": starved_doubts, "world_doubts": starved_world_doubts,
        "frozen_tally": tallies(frozen_w), "frozen_fired": frozen_fired,
        "frozen_doubts": frozen_doubts,
        "fair_fired": fair_fired, "fair_tally": fair_tally,
        "fair_hot": fair_hot,
        "ok": (starved_tally == (6, 0) and eligible_b > 0       # starvation
               and starved_world_doubts > 0                     # doubt: data
               and tallies(frozen_w) == starved_tally           # frozen == default
               and frozen_doubts == ()                          # not "novel"
               and fair_tally == (3, 3) and not fair_hot),      # refraction
    }


# =====================================================================
# 5. The probe
# =====================================================================

def report():
    c1 = claim_1_match_is_exact()
    c2 = claim_2_no_ambiguity()
    c3 = claim_3_starvation_and_novelty()
    return {"match": c1, "noambiguity": c2, "starvation": c3,
            "ok": c1["ok"] and c2["ok"] and c3["ok"]}


def main():
    r = report()
    print("== Q0: match -> resolve -> act over activations", "=" * 20)

    c1 = r["match"]
    print("\n1. match is exact, not the gate (cards.decide_buy)")
    print("   eligible (gate): %s" % sorted(c1["eligible"]))
    print("   exact (LHS):     %s" % sorted(c1["exact"]))
    print("   fired (real):    %s" % sorted(c1["fired"]))
    print("   guard total: %s   escapes: %d   opaque: %s"
          % (c1["guard_total"], c1["escapes"], c1["opaque"]))

    c2 = r["noambiguity"]
    print("\n2. no ambiguity => identical signature")
    print("   baseline fired: %s" % (c2["base_fired"],))
    print("   schedule fired: %s" % (c2["sched_fired"],))
    print("   signatures equal: %s" % (c2["base_sig"] == c2["sched_sig"]))

    c3 = r["starvation"]
    print("\n3. starvation, refraction, novelty")
    print("   frozen/default tally: %s   fired: %s   doubts: %d"
          % (c3["starved_tally"], c3["starved_fired"], c3["world_doubts"]))
    print("   serve_b eligible for %d ticks, chosen 0 (starved)"
          % c3["eligible_b_ticks"])
    print("   refraction tally:     %s   fired: %s"
          % (c3["fair_tally"], c3["fair_fired"]))

    checks = [
        ("match is exact and narrower than the gate",
         c1["exact"] == c1["fired"] and c1["exact"] < c1["eligible"]),
        ("the reshape widens no escape (total, no new verbatim helper)",
         c1["guard_total"] and not c1["opaque"] and c1["escapes"] == 2),
        ("no ambiguity: the schedule reproduces the run-all signature",
         c2["ok"]),
        ("the deterministic default starves the second production",
         c3["starved_tally"] == (6, 0) and c3["eligible_b_ticks"] > 0),
        ("novelty falls back to the frozen score and records a Doubt",
         c3["world_doubts"] > 0
         and c3["frozen_tally"] == c3["starved_tally"]
         and c3["frozen_doubts"] == ()),
        ("refraction restores fairness and still settles",
         c3["fair_tally"] == (3, 3) and not c3["fair_hot"]),
    ]
    print()
    for label, passed in checks:
        print("  [%s] %s" % ("ok" if passed else "XX", label))
    print("  ALL AS EXPECTED:", r["ok"])
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
