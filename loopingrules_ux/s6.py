"""S6 -- the walking skeleton of the train trip with a budget (Plan U, U8).

The probe (`docs/plan-ux.md`, U8/S6; `docs/decisions.md`, ADR-13): the whole
**correction pass**, end to end, on the substrate that already exists. It is a
*reduced* train trip -- **two models** (planning + budget) and **two planners**
(a weak one and a stronger one) -- and it pins the four pieces of ADR-13 that
nothing has exercised:

1. **Materialized candidates.** The engine's stand-in (`run`) enumerates the
   candidate **applications** -- one `application` entity per planner -- *before*
   any is chosen. This is ADR-13's materialization, in its cheapest form: on the
   current substrate the engine cannot see a rule's bindings, so a planner is the
   unit of application, not a binding. (The IR-native engine that materializes
   *bindings* is U5, later.)
2. **A distinct evaluator.** The choice is made by a **decision tree** -- a
   standalone artifact, not a rule -- that reads the candidates and the context
   and returns a selection. It **writes nothing** (pinned by a test: the world's
   revision does not move across `Tree.decide`).
3. **Application memory.** The selection is recorded into world data (an
   `applied` entity), so an ordinary operation can reason over the trajectory the
   network produced -- the homoiconicity payoff, shown by `trajectory`.
4. **Subsumes `RuleControl` + `argmax`.** There is no `RuleControl` anywhere: the
   evaluator's choice *is* what fires.

## The two models, and the cross-model operation

* **planning** -- two planner operations. `plan_greedy` (the weak one) takes a
  **direct** leg if the request's endpoints are adjacent. `plan_pool` (the
  stronger one) searches a **pool** of simple paths and picks the cheapest.
* **budget** -- one operation, `budget_veto`, that **discards** any plan whose
  cost exceeds the request's budget. It reads the planning model's `cost` and the
  request's `budget` at once: a **joint operation** (ADR-9), a rule whose reads
  span two models -- exactly the note's *"the planning module evaluates candidate
  solutions and discards some of them because of the budget."*

## The choice, and why it is real

The planners trade off: `greedy` is **free** (effort `0`) but only ever proposes
a direct leg; `pool` finds the cheapest path but **costs** (`EFFORT['pool']`). So
the useful choice is context-dependent, and it is **not** simply "is there a
direct leg?" -- a direct leg *over budget* is useless (`h3`). The feature that
decides is `direct_in_budget`, and the tree grows it from examples alone.

This is a *pipeline* probe, not a search result -- the same honest framing
`loopingrules_forge.evolve` and `s5` carry: the tree is tiny and the question is
whether the **seam** holds, not whether the learner scales.
"""

from __future__ import annotations

from loopingrules.world import World

REFS = {"start", "goal", "from", "to", "request", "legs"}

# What a planner costs beyond the fare -- the trade-off that makes the choice
# real: `greedy` is free but can only propose a direct leg; `pool` searches and
# costs this much.
EFFORT = {"greedy": 0, "pool": 6}

# The score when no in-budget plan is produced at all.
PENALTY = -100.0


# -- the world ----------------------------------------------------------

def build(network):
    """One scenario's world: stops, legs (as entities carrying `from`/`to`/
    `fare`), and a `request`. A scenario is `{"stops", "legs", "start", "goal",
    "budget"}`; a leg is `(from, to, fare)` by stop NAME.
    """
    w = World()
    w.refs = set(REFS)
    stops = {}
    for name in network["stops"]:
        e = w.spawn()
        w.mark(e, "stop")
        w.set(e, "name", name)
        stops[name] = e
    for frm, to, fare in network["legs"]:
        e = w.spawn()
        w.mark(e, "leg")
        w.set(e, "from", stops[frm])
        w.set(e, "to", stops[to])
        w.set(e, "fare", fare)
    request = w.spawn()
    w.mark(request, "request")
    w.set(request, "start", stops[network["start"]])
    w.set(request, "goal", stops[network["goal"]])
    w.set(request, "budget", network["budget"])
    return w


def _legs(w):
    """Every leg as `(from_id, to_id, fare, leg_entity)`."""
    return [(frm, to, fare, leg) for leg, frm, to, fare
            in w.each("from", "to", "fare")]


def _make_plan(w, planner, cost, legs, hops):
    plan = w.spawn()
    w.mark(plan, "plan")
    w.set(plan, "planner", planner)
    w.set(plan, "cost", cost)
    w.set(plan, "legs", list(legs))
    w.set(plan, "hops", hops)
    return plan


# -- the planning model -------------------------------------------------

def plan_greedy(w, request):
    """The weak planner: a **direct** leg, if the endpoints are adjacent. No
    search -- so it is free, and it fails when there is no direct leg (or
    proposes one over budget, which the budget model then vetoes)."""
    start = w.get(request, "start")
    goal = w.get(request, "goal")
    for frm, to, fare, leg in _legs(w):
        if frm == start and to == goal:
            return _make_plan(w, "greedy", fare, [leg], 1)
    return None


def plan_pool(w, request, max_expansions=500):
    """The stronger planner: enumerate a **pool** of simple paths and keep the
    cheapest. Bounded, so it is not unbounded work -- and it costs `EFFORT`."""
    start = w.get(request, "start")
    goal = w.get(request, "goal")
    adjacency = {}
    for frm, to, fare, leg in _legs(w):
        adjacency.setdefault(frm, []).append((to, fare, leg))
    best = {"cost": None, "legs": None}
    seen_count = [0]

    def walk(at, cost, path, visited):
        if seen_count[0] > max_expansions:
            return
        if at == goal and path:
            if best["cost"] is None or cost < best["cost"]:
                best["cost"] = cost
                best["legs"] = list(path)
            return
        for to, fare, leg in adjacency.get(at, ()):
            if to in visited:
                continue
            seen_count[0] += 1
            walk(to, cost + fare, path + [leg], visited | {to})

    walk(start, 0, [], {start})
    if best["cost"] is None:
        return None
    return _make_plan(w, "pool", best["cost"], best["legs"], len(best["legs"]))


PLANNERS = {"greedy": plan_greedy, "pool": plan_pool}


# -- the budget model (a cross-model operation) -------------------------

def budget_veto(w, request):
    """The budget model's one operation: **discard** (mark `vetoed`) any plan
    whose cost exceeds the request's budget. Reads the planning model's `cost`
    and the request's `budget` together -- a joint operation. Returns how many
    plans it discarded."""
    budget = w.get(request, "budget")
    discarded = 0
    for plan, _planner, cost in w.each("planner", "cost"):
        if w.has(plan, "plan") and cost > budget and not w.has(plan, "vetoed"):
            w.mark(plan, "vetoed")
            discarded += 1
    return discarded


# -- the engine stand-in: materialize -> evaluate -> apply -> record ----

def materialize(w, request):
    """Enumerate the candidate **applications** as data, before any is chosen:
    one `application` entity per planner. ADR-13's materialization, in its
    cheapest form."""
    apps = []
    for name in sorted(PLANNERS):
        a = w.spawn()
        w.mark(a, "application")
        w.set(a, "planner", name)
        w.set(a, "request", request)
        apps.append(a)
    return apps


def context(w, request):
    """The features the evaluator reads off the blackboard. `direct_in_budget`
    is the one the tree ends up choosing on: a direct leg is useless if it is
    over budget."""
    start = w.get(request, "start")
    goal = w.get(request, "goal")
    budget = w.get(request, "budget")
    legs = _legs(w)
    direct_fares = [fare for frm, to, fare, _leg in legs
                    if frm == start and to == goal]
    direct_fare = min(direct_fares) if direct_fares else None
    return {
        "direct": 1 if direct_fare is not None else 0,
        "direct_in_budget": 1 if (direct_fare is not None
                                  and direct_fare <= budget) else 0,
        "direct_fare": direct_fare if direct_fare is not None else -1,
        "budget": budget,
        "n_legs": len(legs),
    }


def _score(w, plan, request, choice):
    """The mechanical objective: an in-budget plan earns what is left of the
    budget, less the planner's effort; no plan (or a vetoed one) earns
    `PENALTY`."""
    if plan is None or w.has(plan, "vetoed"):
        return float(PENALTY)
    return float(w.get(request, "budget") - w.get(plan, "cost") - EFFORT[choice])


def _remember(w, choice, plan):
    """The engine records the **selected application** -- the selection only,
    never the candidates -- into world data (ADR-13)."""
    record = w.spawn()
    w.mark(record, "applied")
    w.set(record, "planner", choice)
    if plan is not None and w.has(plan, "plan"):
        w.set(record, "cost", w.get(plan, "cost"))
        if w.has(plan, "vetoed"):
            w.mark(record, "vetoed")
    return record


def run(network, tree):
    """One step of the recognize-act cycle, by hand: **materialize** the
    candidates, ask the **tree** for a selection, **apply** the chosen planner,
    let the **budget** model veto, and **record** the selection. Returns
    `(world, score)`."""
    w = build(network)
    request = w.first("request")[0]
    apps = materialize(w, request)
    candidates = [w.get(a, "planner") for a in apps]
    choice = tree.decide(context(w, request), candidates)
    plan = PLANNERS[choice](w, request)
    budget_veto(w, request)
    score = _score(w, plan, request, choice)
    _remember(w, choice, plan)
    return w, score


def trajectory(w):
    """Read the application memory back -- what the network HAS chosen, as
    ordinary data an ordinary operation can reason over (the homoiconicity
    payoff; the note's 'system-2' role, which is just operations)."""
    return [{"planner": planner,
             "cost": w.get(record, "cost"),
             "vetoed": w.has(record, "vetoed")}
            for record, _applied, planner in w.each("applied", "planner")]


# -- the evaluator: a distinct artifact, grown offline ------------------

class Tree:
    """A tiny decision tree: `feature >= threshold`? -> left : right, leaves a
    planner name. The **distinct evaluator** of ADR-13 -- it reads the context
    and the candidates, returns a selection, and writes nothing."""

    __slots__ = ("feature", "threshold", "left", "right", "action")

    def __init__(self, action=None, feature=None, threshold=None,
                 left=None, right=None):
        self.action = action
        self.feature = feature
        self.threshold = threshold
        self.left = left
        self.right = right

    def decide(self, ctx, candidates=()):
        """The selection. Pure: nothing on the blackboard is touched."""
        if self.action is not None:
            choice = self.action
        elif ctx[self.feature] >= self.threshold:
            choice = self.left.decide(ctx, candidates)
        else:
            choice = self.right.decide(ctx, candidates)
        if candidates and choice not in candidates:
            raise ValueError("chose %r, which is not a materialized candidate "
                             "(%r)" % (choice, list(candidates)))
        return choice

    def describe(self, indent=0):
        pad = "  " * indent
        if self.action is not None:
            return "%s-> %s" % (pad, self.action)
        return ("%s%s >= %s\n%s\n%s"
                % (pad, self.feature, self.threshold,
                   self.left.describe(indent + 1),
                   self.right.describe(indent + 1)))


def _outcomes(networks):
    """The offline evaluation of every candidate: for each scenario, the score
    each planner WOULD earn. Ground truth is mechanical (the objective above)."""
    rows = []
    for network in networks:
        w = build(network)
        request = w.first("request")[0]
        ctx = context(w, request)
        outcomes = {}
        for name in PLANNERS:
            w2 = build(network)
            r2 = w2.first("request")[0]
            plan = PLANNERS[name](w2, r2)
            budget_veto(w2, r2)
            outcomes[name] = _score(w2, plan, r2, name)
        rows.append((ctx, outcomes))
    return rows


def _best_action(rows):
    totals = {name: sum(outcomes[name] for _, outcomes in rows)
              for name in PLANNERS}
    return max(sorted(totals), key=lambda name: totals[name])


def _tree_total(tree, rows):
    return sum(outcomes[tree.decide(ctx)] for ctx, outcomes in rows)


def _leaf_count(tree):
    if tree.action is not None:
        return 1
    return _leaf_count(tree.left) + _leaf_count(tree.right)


def _fit(rows, depth):
    action = _best_action(rows)
    if depth <= 0 or len(rows) < 2:
        return Tree(action=action)
    leaf = Tree(action=action)
    leaf_total = _tree_total(leaf, rows)
    # Among equal-scoring splits prefer the one with FEWER leaves, so a split
    # that only separates a tie (and adds a node) is not taken.
    best = None                                 # (key, feature, threshold, l, r)
    for feature in sorted(rows[0][0]):
        values = sorted({ctx[feature] for ctx, _ in rows})
        thresholds = [(a + b) / 2.0 for a, b in zip(values, values[1:])]
        for threshold in thresholds:
            left_rows = [(c, o) for c, o in rows if c[feature] >= threshold]
            right_rows = [(c, o) for c, o in rows if c[feature] < threshold]
            if not left_rows or not right_rows:
                continue
            left = _fit(left_rows, depth - 1)
            right = _fit(right_rows, depth - 1)
            total = (_tree_total(left, left_rows)
                     + _tree_total(right, right_rows))
            key = (total, -(_leaf_count(left) + _leaf_count(right)))
            if best is None or key > best[0]:
                best = (key, feature, threshold, left, right)
    if best is None or best[0][0] <= leaf_total + 1e-9:
        return leaf
    _, feature, threshold, left, right = best
    return Tree(feature=feature, threshold=threshold, left=left, right=right)


def grow(networks, depth=2):
    """Grow the evaluator offline, over scenarios evaluated automatically.
    Frozen before it runs (ADR-13)."""
    return _fit(_outcomes(networks), depth)


# -- scenarios ----------------------------------------------------------

TRAIN = (
    # direct leg, in budget -> greedy is free and as cheap as pool
    {"name": "e1", "stops": ["A", "B"], "legs": [("A", "B", 10)],
     "start": "A", "goal": "B", "budget": 50},
    {"name": "e2", "stops": ["A", "B"], "legs": [("A", "B", 5)],
     "start": "A", "goal": "B", "budget": 30},
    # no direct leg -> only pool can plan
    {"name": "h1", "stops": ["A", "B", "C"], "legs": [("A", "B", 3), ("B", "C", 4)],
     "start": "A", "goal": "C", "budget": 50},
    # a direct leg, but OVER budget -> greedy proposes it and the budget vetoes it
    {"name": "h3", "stops": ["A", "B", "C"],
     "legs": [("A", "B", 1), ("B", "C", 1), ("A", "C", 20)],
     "start": "A", "goal": "C", "budget": 10},
    # no plan in budget at all -> both fail
    {"name": "imp", "stops": ["A", "B"], "legs": [("A", "B", 100)],
     "start": "A", "goal": "B", "budget": 5},
)

TEST = (
    {"name": "e3", "stops": ["A", "B"], "legs": [("A", "B", 4)],
     "start": "A", "goal": "B", "budget": 20},
    {"name": "h4", "stops": ["A", "B", "C", "D"],
     "legs": [("A", "B", 2), ("B", "C", 3), ("C", "D", 4)],
     "start": "A", "goal": "D", "budget": 40},
    {"name": "h5", "stops": ["A", "B", "C"],
     "legs": [("A", "B", 2), ("A", "C", 30), ("B", "C", 3)],
     "start": "A", "goal": "C", "budget": 10},
    {"name": "e4", "stops": ["A", "C"], "legs": [("A", "C", 7)],
     "start": "A", "goal": "C", "budget": 20},
    {"name": "imp2", "stops": ["A", "B"], "legs": [("A", "B", 50)],
     "start": "A", "goal": "B", "budget": 10},
)


def _total_fixed(networks, planner):
    tree = Tree(action=planner)
    return sum(run(net, tree)[1] for net in networks)


def _oracle(networks):
    total = 0.0
    for network in networks:
        rows = _outcomes([network])[0][1]
        total += max(rows.values())
    return total


def main() -> int:
    tree = grow(TRAIN)
    print("grown evaluator:")
    print(tree.describe(1))
    for label, networks in (("train", TRAIN), ("test", TEST)):
        grown = sum(run(net, tree)[1] for net in networks)
        print("  %-5s grown %+7.1f   greedy %+7.1f   pool %+7.1f   oracle %+7.1f"
              % (label, grown, _total_fixed(networks, "greedy"),
                 _total_fixed(networks, "pool"), _oracle(networks)))
    w, _ = run(TRAIN[2], tree)
    print("application memory (h1):", trajectory(w))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
