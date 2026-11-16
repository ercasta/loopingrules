"""T1 -- trajectories and coverage: a fixed model set, many use cases, no per-case code.

Walking skeleton of `docs/plan-scale-probe.md` §5 (axis B). It implements only the
*mechanism* half -- the concept rules, the use-case family, and the one measurement
that can falsify the claim -- and leaves the four-baseline comparison for later.

## The claim, and the test that can falsify it

"Different input -> a different trajectory" is **trivially true** of any rule engine
with guards, and of any `if/elif` program. The claim worth a probe is narrower:

> A **fixed** set of one-concept rules covers **held-out combinations** of those
> concepts -- never authored together -- with **no per-case code**, while a new
> *concept* is a **gap** (not a guess); and **one added rule buys several use
> cases** (fan-out > 1).

A branch-per-case program (the `naive_choose` control) passes the seen cases and
**fails every combination**, because it only ever coded the singles.

## The fixed model set (three models, one shared vocabulary)

* **`items`** -- a `candidate` with a `worth` (and a `name`).
* **`funds`** -- `cash`/`reserve`, from which `spendable = cash - reserve` is derived.
* **the directive** -- the ANCHOR: `do{what, limit?, affordable?}`. `what` is the
  choose concept (`all`/`cheapest`); `limit` and `affordable` are scope concepts.

Every rule reads **exactly one** concept, so any *combination* of concepts composes
with no code that names the combination. `excluded` scopes, `chosen` is the answer,
`resolved` marks a directive some choose rule understood, and `unresolved{name}` is
the **gap** -- the structural "this term has no definer."
"""

from __future__ import annotations

from loopingrules.loop import Loop

# The world every use case is scored against. spendable = 30 - 10 = 20.
CARDS = (("goblin", 5.0), ("wand", 25.0), ("dragon", 40.0))
CASH = 30.0
RESERVE = 10.0


# -- the model set: one rule per concept ------------------------------------

def spendable(w) -> None:
    """`funds` derives the amount its owner can spend."""
    for entity, cash, reserve in w.each("funds", "cash", "reserve",
                                       without=("spendable",)):
        w.set(entity, "spendable", "amount", cash - reserve)


def scope_limit(w) -> None:
    """SCOPE concept `limit`: exclude anything dearer than `do.limit`."""
    row = w.first("do", "limit")
    if row is None:
        return
    limit = row[1]
    for entity, worth in w.each("candidate", "worth", without=("excluded",)):
        if worth > limit:
            w.mark(entity, "excluded")


def scope_affordable(w) -> None:
    """SCOPE concept `affordable`: exclude anything dearer than `spendable`."""
    if w.first("do", "affordable") is None:
        return
    amount = w.the("spendable", "amount")
    if amount is None:
        return
    for entity, worth in w.each("candidate", "worth", without=("excluded",)):
        if worth > amount:
            w.mark(entity, "excluded")


def choose_cheapest(w) -> None:
    """CHOOSE concept `cheapest`: the least dear in scope."""
    row = w.first("do", "what")
    if row is None or row[1] != "cheapest":
        return
    directive = row[0]
    best = None
    for entity, worth in w.each("candidate", "worth", without=("excluded",)):
        if best is None or worth < best[1]:
            best = (entity, worth)
    for entity, in w.each("chosen"):
        if best is None or entity != best[0]:
            w.unmark(entity, "chosen")
    if best is not None and not w.has(best[0], "chosen"):
        w.mark(best[0], "chosen")
    if not w.has(directive, "resolved"):
        w.mark(directive, "resolved")


def choose_all(w) -> None:
    """CHOOSE concept `all`: every in-scope candidate."""
    row = w.first("do", "what")
    if row is None or row[1] != "all":
        return
    directive = row[0]
    in_scope = []
    for entity, _worth in w.each("candidate", "worth", without=("excluded",)):
        in_scope.append(entity)
    for entity, in w.each("chosen"):
        if entity not in in_scope:
            w.unmark(entity, "chosen")
    for entity in in_scope:
        if not w.has(entity, "chosen"):
            w.mark(entity, "chosen")
    if not w.has(directive, "resolved"):
        w.mark(directive, "resolved")


def choose_priciest(w) -> None:
    """CHOOSE concept `priciest` -- added LATER, for fan-out. One rule, three new
    use cases (it composes with both scopes and their combination)."""
    row = w.first("do", "what")
    if row is None or row[1] != "priciest":
        return
    directive = row[0]
    best = None
    for entity, worth in w.each("candidate", "worth", without=("excluded",)):
        if best is None or worth > best[1]:
            best = (entity, worth)
    for entity, in w.each("chosen"):
        if best is None or entity != best[0]:
            w.unmark(entity, "chosen")
    if best is not None and not w.has(best[0], "chosen"):
        w.mark(best[0], "chosen")
    if not w.has(directive, "resolved"):
        w.mark(directive, "resolved")


def unresolved(w) -> None:
    """The GAP: a `what` no choose rule understood is a question, never a guess."""
    for entity, what in w.each("do", "what", without=("resolved",)):
        if not w.has(entity, "unresolved"):
            w.set(entity, "unresolved", "name", what)


BASE_RULES = (spendable, scope_limit, scope_affordable,
              choose_all, choose_cheapest, unresolved)
FANOUT_RULE = choose_priciest


# -- the control: a branch per case (the ad-hoc baseline) -------------------

def naive_choose(w) -> None:
    """One branch per AUTHORED directive, no composition -- passes the seen cases
    and fails every combination, because the combinations were never coded."""
    row = w.first("do", "what")
    if row is None:
        return
    entity, what = row
    if w.first("do", "limit") is not None or w.first("do", "affordable") is not None:
        return                                   # combinations were never coded
    if what == "all":
        for candidate, _worth in w.each("candidate", "worth"):
            w.mark(candidate, "chosen")
        w.mark(entity, "resolved")
    elif what == "cheapest":
        best = None
        for candidate, worth in w.each("candidate", "worth"):
            if best is None or worth < best[1]:
                best = (candidate, worth)
        for candidate, in w.each("chosen"):
            if best is None or candidate != best[0]:
                w.unmark(candidate, "chosen")
        if best is not None and not w.has(best[0], "chosen"):
            w.mark(best[0], "chosen")
        w.mark(entity, "resolved")


NAIVE_RULES = (spendable, naive_choose, unresolved)


# -- the use-case family ----------------------------------------------------

# (label, directive, expected chosen set -- or None for "must be a gap")
USE_CASES = (
    ("all", dict(what="all"), frozenset({"goblin", "wand", "dragon"})),
    ("cheapest", dict(what="cheapest"), frozenset({"goblin"})),
    ("all+limit", dict(what="all", limit=20.0), frozenset({"goblin"})),
    ("cheapest+limit", dict(what="cheapest", limit=20.0), frozenset({"goblin"})),
    ("all+affordable", dict(what="all", affordable=True), frozenset({"goblin"})),
    ("cheapest+affordable", dict(what="cheapest", affordable=True), frozenset({"goblin"})),
    ("cheapest+limit+affordable",
     dict(what="cheapest", limit=20.0, affordable=True), frozenset({"goblin"})),
    ("underrated", dict(what="underrated"), None),
    ("priciest", dict(what="priciest"), frozenset({"dragon"})),
    ("priciest+limit", dict(what="priciest", limit=20.0), frozenset({"goblin"})),
    ("priciest+affordable", dict(what="priciest", affordable=True), frozenset({"goblin"})),
)

SEEN = ("all", "cheapest")
HELD_OUT_COMBINATIONS = ("all+limit", "cheapest+limit", "all+affordable",
                         "cheapest+affordable", "cheapest+limit+affordable")
HELD_OUT_CONCEPT = "underrated"
FANOUT_CASES = ("priciest", "priciest+limit", "priciest+affordable")
_EXPECTED = {label: expected for label, _directive, expected in USE_CASES}


# -- running one use case ---------------------------------------------------

def _seed(loop, directive) -> None:
    world = loop.world
    for name, worth in CARDS:
        entity = world.spawn()
        world.set(entity, "candidate", "worth", worth)
        world.set(entity, "candidate", "name", name)
    funds = world.spawn()
    world.set(funds, "funds", "cash", CASH)
    world.set(funds, "funds", "reserve", RESERVE)
    anchor = world.spawn()
    if directive.get("what") is not None:
        world.set(anchor, "do", "what", directive["what"])
    if directive.get("limit") is not None:
        world.set(anchor, "do", "limit", directive["limit"])
    if directive.get("affordable"):
        world.set(anchor, "do", "affordable", True)


def run(*, rules=BASE_RULES, **directive) -> dict:
    """Replay one directive and return what happened: the chosen set, the gaps, the
    trajectory (the rules that fired, per tick), and whether it settled."""
    loop = Loop()
    _seed(loop, directive)
    # `unresolved` must see every choose rule's verdict, so it always runs last --
    # a gap must be decided AFTER the concepts have had their turn.
    ordered = [rule for rule in rules if rule is not unresolved]
    ordered.append(unresolved)
    for rule in ordered:
        loop.rule(rule)
    fired = []
    hot = ()
    for _ in range(loop.budget):
        step = loop.tick()
        if not step:
            break
        fired.append(tuple(step))
    else:
        hot = fired[-1] if fired else ()
    world = loop.world
    chosen = frozenset(world.get(entity, "candidate", "name")
                       for entity, in world.each("chosen"))
    gaps = frozenset(world.get(entity, "unresolved", "name")
                     for entity, in world.each("unresolved"))
    return {"chosen": chosen, "gaps": gaps, "trajectory": tuple(fired), "hot": hot}


def correct(result, expected) -> bool:
    """A covered case matches its expected set; a held-out CONCEPT must be a gap."""
    if expected is None:
        return bool(result["gaps"]) and not result["chosen"]
    return not result["gaps"] and result["chosen"] == expected


# -- the measurements -------------------------------------------------------

def coverage(*, rules=BASE_RULES, labels=None) -> tuple:
    labels = set(_EXPECTED if labels is None else labels)
    ok = 0
    total = 0
    for label, directive, _expected in USE_CASES:
        if label not in labels:
            continue
        total += 1
        if correct(run(rules=rules, **directive), _EXPECTED[label]):
            ok += 1
    return ok, total


def measure_fanout() -> dict:
    """One added rule, `choose_priciest`, and how many use cases it buys."""
    base_ok, base_n = coverage(rules=BASE_RULES, labels=FANOUT_CASES)
    with_ok, with_n = coverage(rules=BASE_RULES + (FANOUT_RULE,), labels=FANOUT_CASES)
    return {"base": base_ok, "with": with_ok, "total": base_n,
            "new": with_ok - base_ok, "rules_added": 1}


def measure_trajectories() -> dict:
    trajectories = {}
    for label, directive, expected in USE_CASES:
        if expected is None:
            continue
        trajectories[label] = run(**directive)["trajectory"]
    return {"distinct": len(set(trajectories.values())),
            "of": len(trajectories), "trajectories": trajectories}


def measure_soundness() -> dict:
    result = run(**dict(what="underrated"))
    return {"gaps": sorted(result["gaps"]), "chosen": sorted(result["chosen"]),
            "is_gap": bool(result["gaps"]) and not result["chosen"]}


def measure_naive() -> dict:
    seen_ok, seen_n = coverage(rules=NAIVE_RULES, labels=SEEN)
    held_ok, held_n = coverage(rules=NAIVE_RULES, labels=HELD_OUT_COMBINATIONS)
    return {"seen": (seen_ok, seen_n), "held_out": (held_ok, held_n)}


def run_all():
    combos = coverage(labels=HELD_OUT_COMBINATIONS)
    seen = coverage(labels=SEEN)
    sound = measure_soundness()
    naive = measure_naive()
    fan = measure_fanout()
    trajs = measure_trajectories()
    rows = [
        ("seen cases", seen[0] == seen[1], "%d/%d" % seen),
        ("held-out combinations", combos[0] == combos[1], "%d/%d" % combos),
        ("held-out concept is a gap", sound["is_gap"],
         "gaps=%s chosen=%s" % (sound["gaps"], sound["chosen"])),
        ("naive: seen", naive["seen"][0] == naive["seen"][1], "%d/%d" % naive["seen"]),
        ("naive: combinations", naive["held_out"][0] == 0, "%d/%d" % naive["held_out"]),
        ("fan-out (1 rule)", fan["new"] > 1, "+%d use cases" % fan["new"]),
        ("distinct trajectories", trajs["distinct"] >= 4,
         "%d/%d" % (trajs["distinct"], trajs["of"])),
    ]
    return rows


def main() -> int:
    print("== t1: a fixed model set, many use cases, no per-case code", "=" * 12)
    for label, ok, note in run_all():
        print("  %-26s %-5s %s" % (label, "ok" if ok else "NO", note))
    return 0 if all(ok for _label, ok, _note in run_all()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
