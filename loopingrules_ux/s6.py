"""S6 -- the walking skeleton of the train trip with a budget (Plan U, U8).

The probe (`docs/plan-ux.md`, U8/S6; `docs/decisions.md`, ADR-13): the whole
**correction pass**, end to end, on the substrate that already exists. It is a
*reduced* train trip -- **three models** (train, planning, budget) -- and it
exercises ADR-13's seam:

1. **Materialized candidates.** The engine's stand-in (`run`) enumerates the
   candidate **applications** as data, *before* any is chosen -- at two levels
   (see below). On the current substrate the engine cannot see a rule's bindings,
   so the units of application are the *planner* and the *plan*, not
   (rule, binding). The IR-native engine that materializes bindings is U5, later.
2. **A distinct evaluator.** The choice is made by an artifact that is not a
   rule: an **activation** decision tree (`Tree`) that picks *which planner to
   run*, and a **listwise** `rank` that scores the plan candidates and
   **eliminates the bottom**. Neither writes anything (pinned: the world's
   revision does not move across `Tree.decide`).
3. **Application memory.** The selection is recorded into world data (an
   `applied` entity -- the planner chosen, the cost, and how many candidates the
   scorers eliminated), so an ordinary operation can reason over the trajectory
   the network produced (the homoiconicity payoff; `trajectory`).
4. **Subsumes `RuleControl` + `argmax`.** There is no `RuleControl` anywhere: the
   activation choice *is* what fires, and `rank`'s elimination *is* the
   resolution.

## The three models

| Model | Operations | What it is |
|---|---|---|
| **train** | `train_execute` | the graph (stops, legs) and the trip itself: walking a plan advances the traveller and spends the fare |
| **planning** | `plan_greedy`, `plan_pool` | proposes **candidate plans** -- the weak one takes a direct leg, the strong one enumerates a pool of paths |
| **budget** | `budget_veto` | **discards** a plan whose cost exceeds the cash on hand -- a *cross-model* operation, reading `plan.cost` and `trip.cash` at once |

## Two levels of selection, and why both are real

* **Activation** (which planner) -- the tree, grown offline. The planners trade
  off: `greedy` is **free** but can only propose a direct leg; `pool` finds the
  cheapest path but **costs** (`EFFORT['pool']`). So the choice is
  context-dependent, and it is NOT "is there a direct leg?" -- a direct leg *over
  budget* is useless (`h3`). The feature that decides is `direct_in_budget`.
* **Candidate selection** (which plan) -- `rank`, a **listwise** scorer that
  scores every survivor and **eliminates the bottom**, then breaks ties on hops.
  `plan_pool` emits *several* candidates (`m1`), so this pass has real work.

This is a *pipeline* probe, not a search result -- the same honest framing
`loopingrules_forge.evolve` and `s5` carry. The learner here is **thin** (the
objective is mechanical, so the tree is small); the increment being proven is the
**mechanism**: materialized candidates, elimination, and a multi-step executed
trip. A *per-step* selection (the network choosing the next move each tick, the
deepest reading of ADR-13) and a learned listwise scorer are the next growth.
"""

from __future__ import annotations

from loopingrules.world import World

REFS = {"start", "goal", "from", "to", "at", "legs"}

# What a planner costs beyond the fare -- the trade-off that makes the activation
# choice real: `greedy` is free but can only propose a direct leg; `pool`
# searches and costs this much.
EFFORT = {"greedy": 0, "pool": 6}

# The score when no in-budget plan is produced (or the trip does not complete).
PENALTY = -100.0


# -- the train model: the graph and the trip ---------------------------

def build(network):
    """One scenario's world: stops, legs (entities carrying `from`/`to`/`fare`),
    and a `trip` (start, goal, cash, position). A scenario is `{"stops", "legs",
    "start", "goal", "cash"}`; a leg is `(from, to, fare)` by stop NAME.
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
    trip = w.spawn()
    w.mark(trip, "trip")
    w.set(trip, "start", stops[network["start"]])
    w.set(trip, "goal", stops[network["goal"]])
    w.set(trip, "cash", network["cash"])
    w.set(trip, "at", stops[network["start"]])
    return w


def _trip(w):
    return w.first("trip")[0]


def _legs(w):
    """Every leg as `(from_id, to_id, fare, leg_entity)`."""
    return [(frm, to, fare, leg) for leg, frm, to, fare
            in w.each("from", "to", "fare")]


def train_execute(w, trip, plan):
    """The train model's operation: **walk** a plan's legs, advancing the
    traveller and spending each fare. Returns whether it reached the goal."""
    at = w.get(trip, "at")
    cash = w.get(trip, "cash")
    goal = w.get(trip, "goal")
    for leg_id in w.get(plan, "legs"):
        leg = w.entity(leg_id)
        cash -= w.get(leg, "fare")
        at = w.get(leg, "to")
    w.set(trip, "cash", cash)
    w.set(trip, "at", at)
    done = at == goal
    if done:
        w.mark(trip, "done")
    return done


# -- the planning model: candidate plans -------------------------------

def _make_plan(w, planner, cost, legs, hops):
    plan = w.spawn()
    w.mark(plan, "plan")
    w.set(plan, "planner", planner)
    w.set(plan, "cost", cost)
    w.set(plan, "legs", list(legs))
    w.set(plan, "hops", hops)
    return plan


def plan_greedy(w, trip):
    """The weak planner: a **direct** leg, if the endpoints are adjacent. No
    search -- so it is free, and it proposes nothing when there is no direct leg
    (or proposes one over budget, which the budget model then vetoes)."""
    start = w.get(trip, "start")
    goal = w.get(trip, "goal")
    for frm, to, fare, leg in _legs(w):
        if frm == start and to == goal:
            return [_make_plan(w, "greedy", fare, [leg], 1)]
    return []


def plan_pool(w, trip, max_candidates=200):
    """The stronger planner: enumerate a **pool** of simple paths and propose
    each as a candidate. Bounded, so it is not unbounded work -- and it costs
    `EFFORT`. Returns the candidate plans (possibly several)."""
    start = w.get(trip, "start")
    goal = w.get(trip, "goal")
    adjacency = {}
    for frm, to, fare, leg in _legs(w):
        adjacency.setdefault(frm, []).append((to, fare, leg))
    plans = []

    def walk(at, cost, path, visited):
        if len(plans) >= max_candidates:
            return
        if at == goal and path:
            plans.append(_make_plan(w, "pool", cost, path, len(path)))
            return
        for to, fare, leg in adjacency.get(at, ()):
            if to in visited:
                continue
            walk(to, cost + fare, path + [leg], visited | {to})

    walk(start, 0, [], {start})
    return plans


PLANNERS = {"greedy": plan_greedy, "pool": plan_pool}


# -- the budget model (a cross-model operation) -------------------------

def budget_veto(w, trip):
    """The budget model's one operation: **discard** (mark `vetoed`) any plan
    whose cost exceeds the cash on hand. Reads the planning model's `cost` and
    the train model's `cash` together -- a joint operation. Returns how many
    plans it discarded."""
    cash = w.get(trip, "cash")
    discarded = 0
    for plan, _planner, cost in w.each("planner", "cost"):
        if w.has(plan, "plan") and cost > cash and not w.has(plan, "vetoed"):
            w.mark(plan, "vetoed")
            discarded += 1
    return discarded


# -- the engine stand-in: materialize -> evaluate -> apply -> record ----

def materialize_planners(w, trip):
    """Enumerate the candidate **applications** -- one `application` entity per
    planner -- as data, before any is chosen (ADR-13's materialization)."""
    apps = []
    for name in sorted(PLANNERS):
        a = w.spawn()
        w.mark(a, "application")
        w.set(a, "planner", name)
        w.set(a, "trip", trip)
        apps.append(a)
    return apps


def context(w, trip):
    """The features the activation evaluator reads off the blackboard.
    `direct_in_budget` is the one the tree ends up choosing on: a direct leg is
    useless if it is over budget."""
    start = w.get(trip, "start")
    goal = w.get(trip, "goal")
    cash = w.get(trip, "cash")
    legs = _legs(w)
    direct_fares = [fare for frm, to, fare, _leg in legs
                    if frm == start and to == goal]
    direct_fare = min(direct_fares) if direct_fares else None
    return {
        "direct": 1 if direct_fare is not None else 0,
        "direct_in_budget": 1 if (direct_fare is not None
                                  and direct_fare <= cash) else 0,
        "direct_fare": direct_fare if direct_fare is not None else -1,
        "cash": cash,
        "n_legs": len(legs),
    }


def rank(w, plans):
    """The **listwise** candidate evaluator: score every candidate, **eliminate
    the bottom**, and select the best -- `None` (exclude) if none survived the
    budget. Progressive by construction: a coarse pass prunes on cost, a finer
    pass breaks ties on hops. (Whether the elimination *saves* anything is
    unmeasured; what it pins is that scoring every candidate and pruning is the
    selection mechanism, not a single context lookup.)"""
    live = [p for p in plans if not w.has(p, "vetoed")]
    if not live:
        return None
    best_cost = min(w.get(p, "cost") for p in live)
    survivors = [p for p in live if w.get(p, "cost") == best_cost]   # eliminate
    return min(survivors, key=lambda p: (w.get(p, "hops"), p.id))


def _remember(w, choice, proposed, selected):
    """The engine records the **selection** into world data (ADR-13): the planner
    chosen, the selected cost, and -- the probe's own question -- how many
    candidates were **proposed** and how many the scorers **eliminated**."""
    record = w.spawn()
    w.mark(record, "applied")
    w.set(record, "planner", choice)
    w.set(record, "proposed", proposed)
    w.set(record, "eliminated", proposed - (1 if selected is not None else 0))
    if selected is not None:
        w.set(record, "cost", w.get(selected, "cost"))
    return record


def _pipeline(w, trip, choice):
    """One scenario, given the activated planner: **materialize** the candidate
    plans, let the **budget** veto, **rank** the survivors, **execute** the
    chosen plan, and **record** the selection. Returns the score."""
    plans = PLANNERS[choice](w, trip)
    budget_veto(w, trip)
    selected = rank(w, plans)
    done = selected is not None and train_execute(w, trip, selected)
    score = (w.get(trip, "cash") - EFFORT[choice]) if done else float(PENALTY)
    _remember(w, choice, len(plans), selected)
    return score


def run(network, tree):
    """The recognize-act cycle, by hand: **materialize** the planner candidates,
    ask the **tree** which to activate, then run the pipeline. Returns
    `(world, score)`."""
    w = build(network)
    trip = _trip(w)
    apps = materialize_planners(w, trip)
    choice = tree.decide(context(w, trip), [w.get(a, "planner") for a in apps])
    return w, _pipeline(w, trip, choice)


def trajectory(w):
    """Read the application memory back -- what the network HAS chosen, as
    ordinary data an ordinary operation can reason over (the homoiconicity
    payoff; the note's 'system-2' role, which is just operations)."""
    return [{"planner": planner,
             "cost": w.get(record, "cost"),
             "proposed": w.get(record, "proposed"),
             "eliminated": w.get(record, "eliminated")}
            for record, _applied, planner in w.each("applied", "planner")]


# -- the activation evaluator: a distinct artifact, grown offline -------

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
    """The offline evaluation of every candidate planner: for each scenario, the
    score each planner WOULD earn, through the whole pipeline. Ground truth is
    mechanical (the objective above)."""
    rows = []
    for network in networks:
        w = build(network)
        ctx = context(w, _trip(w))
        outcomes = {}
        for name in PLANNERS:
            w2 = build(network)
            outcomes[name] = _pipeline(w2, _trip(w2), name)
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
    """Grow the activation evaluator offline, over scenarios evaluated
    automatically. Frozen before it runs (ADR-13)."""
    return _fit(_outcomes(networks), depth)


# -- scenarios ----------------------------------------------------------

# `direct_in_budget` is the feature that decides activation: `greedy` when a
# direct leg fits the cash, `pool` otherwise. The `m*` scenarios have no direct
# leg and SEVERAL paths, so `pool` emits a real candidate set for `rank`.
TRAIN = (
    {"name": "e1", "stops": ["A", "B"], "legs": [("A", "B", 10)],
     "start": "A", "goal": "B", "cash": 50},
    {"name": "e2", "stops": ["A", "B"], "legs": [("A", "B", 5)],
     "start": "A", "goal": "B", "cash": 30},
    {"name": "h1", "stops": ["A", "B", "C"], "legs": [("A", "B", 3), ("B", "C", 4)],
     "start": "A", "goal": "C", "cash": 50},
    {"name": "h3", "stops": ["A", "B", "C"],
     "legs": [("A", "B", 1), ("B", "C", 1), ("A", "C", 20)],
     "start": "A", "goal": "C", "cash": 10},
    {"name": "m1", "stops": ["A", "B", "C", "D"],
     "legs": [("A", "B", 2), ("B", "D", 3), ("A", "C", 2), ("C", "D", 2)],
     "start": "A", "goal": "D", "cash": 20},
    {"name": "imp", "stops": ["A", "B"], "legs": [("A", "B", 100)],
     "start": "A", "goal": "B", "cash": 5},
)

TEST = (
    {"name": "e3", "stops": ["A", "B"], "legs": [("A", "B", 4)],
     "start": "A", "goal": "B", "cash": 20},
    {"name": "h4", "stops": ["A", "B", "C", "D"],
     "legs": [("A", "B", 2), ("B", "C", 3), ("C", "D", 4)],
     "start": "A", "goal": "D", "cash": 40},
    {"name": "h5", "stops": ["A", "B", "C"],
     "legs": [("A", "B", 2), ("A", "C", 30), ("B", "C", 3)],
     "start": "A", "goal": "C", "cash": 10},
    {"name": "e4", "stops": ["A", "C"], "legs": [("A", "C", 7)],
     "start": "A", "goal": "C", "cash": 20},
    {"name": "m3", "stops": ["A", "B", "C", "D"],
     "legs": [("A", "B", 1), ("B", "D", 1), ("A", "C", 1), ("C", "D", 5)],
     "start": "A", "goal": "D", "cash": 10},
    {"name": "imp2", "stops": ["A", "B"], "legs": [("A", "B", 50)],
     "start": "A", "goal": "B", "cash": 10},
)


def _total_fixed(networks, planner):
    tree = Tree(action=planner)
    return sum(run(net, tree)[1] for net in networks)


def _oracle(networks):
    return sum(max(outcomes.values())
               for _ctx, outcomes in _outcomes(networks))


def main() -> int:
    tree = grow(TRAIN)
    print("grown activation:")
    print(tree.describe(1))
    for label, networks in (("train", TRAIN), ("test", TEST)):
        grown = sum(run(net, tree)[1] for net in networks)
        print("  %-5s grown %+7.1f   greedy %+7.1f   pool %+7.1f   oracle %+7.1f"
              % (label, grown, _total_fixed(networks, "greedy"),
                 _total_fixed(networks, "pool"), _oracle(networks)))
    w, _ = run(TRAIN[4], tree)                      # m1: several candidates
    print("application memory (m1):", trajectory(w))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
