"""S6 -- the train trip with a budget, selected PER STEP (Plan U, U8; ADR-13).

The deepest reading of ADR-13: **multi-step steering is "which application fires
next."** So the network does not pick a whole plan -- it picks **one move per
step**, and the trip is a *sequence* of selections, each made against the state
the last one produced. This is the probe for the claim the earlier cuts left
unexercised.

## One step, and the loop

Each step, by hand (the engine's stand-in, `step`):

1. **Materialize** the candidate **moves** -- one `move` entity per leg leaving
   the traveller's current stop -- as data, before any is chosen.
2. **The budget excludes**: `budget_exclude` marks any move whose fare exceeds
   the cash on hand `vetoed`. It reads the move's `fare` and the trip's `cash` at
   once -- a **cross-model operation**.
3. **The network selects**: a `Policy` -- a *distinct* artifact, not a rule --
   scores every surviving candidate and returns one (argmax; ties by id). It
   **writes nothing**.
4. **The train model applies**: `train_advance` walks the leg, spending the fare
   and moving the traveller.
5. **The engine records** the selection into world data (an `applied` entity),
   so the whole **trajectory** is ordinary, queryable state (`trajectory`).

The loop repeats until the goal is reached, no move survives, or a **step budget**
cuts a non-terminating policy (`loop` is the circuit breaker the engine's own
`budget` is -- a policy that strays can oscillate, and the budget is what catches
it).

## The two planning models, and what the network learns

A candidate move carries a rating from each planner:

* **`greedy`** (weak): `-fare` -- take the cheapest leg. Fast, and locally
  plausible -- but it strays (`stray`: it walks a cheap leg back and forth and
  never reaches the goal).
* **`lookahead`** (strong): `-(fare + remaining)`, where `remaining` is the
  cheapest cost from the move's destination on to the goal -- i.e. Dijkstra's
  value. Informed, and optimal.

The network is a **linear scorer over those ratings**, `w . ratings`, grown
offline (a small grid search) and frozen before it runs. Growth finds a policy
that relies on the strong planner's lookahead -- which reproduces the optimal
(Dijkstra) trip -- and the probe compares it against the weak planner alone and
against the oracle.

This is a *pipeline* probe, not a search result -- the same honest framing
`loopingrules_forge.evolve` and `s5` carry. The learner is **thin** (the objective
is mechanical, and the lookahead feature is exact), and named as such; what the
increment proves is the **mechanism**: a per-step materialized candidate set, a
pure per-step scorer, and a trajectory recorded as a sequence.
"""

from __future__ import annotations

import heapq

from loopingrules.world import World

REFS = {"start", "goal", "from", "to", "at", "leg"}

# Unreachable: a destination from which the goal cannot be reached.
INF = 10 ** 9

# The score when the goal is never reached (unreachable, unaffordable, or the
# step budget cut a straying policy).
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


def train_advance(w, trip, move):
    """The train model's operation: walk one move's leg -- spend the fare, move
    the traveller; mark the trip `done` at the goal. Returns whether it is done."""
    w.set(trip, "cash", w.get(trip, "cash") - w.get(move, "fare"))
    w.set(trip, "at", w.get(move, "to"))
    done = w.get(trip, "at") == w.get(trip, "goal")
    if done:
        w.mark(trip, "done")
    return done


# -- materialize the candidate moves, and the budget exclusion ----------

def materialize_moves(w, trip):
    """The candidate **moves**: one `move` entity per leg leaving the current
    stop, as data, before any is chosen (ADR-13's materialization, per step)."""
    at = w.get(trip, "at")
    moves = []
    for frm, to, fare, leg in _legs(w):
        if frm == at:
            m = w.spawn()
            w.mark(m, "move")
            w.set(m, "leg", leg)
            w.set(m, "from", frm)
            w.set(m, "to", to)
            w.set(m, "fare", fare)
            moves.append(m)
    return moves


def budget_exclude(w, trip, moves):
    """The budget model's operation: **exclude** (mark `vetoed`) any move whose
    fare exceeds the cash on hand -- a cross-model read of `move.fare` and
    `trip.cash`. Returns how many it excluded."""
    cash = w.get(trip, "cash")
    excluded = 0
    for m in moves:
        if w.get(m, "fare") > cash and not w.has(m, "vetoed"):
            w.mark(m, "vetoed")
            excluded += 1
    return excluded


# -- the two planning models: ratings of a move -------------------------

def remaining(w, trip, stop):
    """The cheapest cost from `stop` on to the goal -- Dijkstra -- or `INF` if
    the goal is unreachable from there. The strong planner's lookahead."""
    goal = w.get(trip, "goal")
    adjacency = {}
    for frm, to, fare, _leg in _legs(w):
        adjacency.setdefault(frm, []).append((to, fare))
    dist = {stop: 0}
    queue = [(0, stop)]
    while queue:
        cost, at = heapq.heappop(queue)
        if at == goal:
            return cost
        if cost > dist.get(at, INF):
            continue
        for to, fare in adjacency.get(at, ()):
            step = cost + fare
            if step < dist.get(to, INF):
                dist[to] = step
                heapq.heappush(queue, (step, to))
    return INF


def _greedy(w, trip, move):
    """The weak planner: take the cheapest leg."""
    return float(-w.get(move, "fare"))


def _lookahead(w, trip, move):
    """The strong planner: the cheapest leg *plus* the cheapest way on from where
    it lands -- Dijkstra's value."""
    rem = remaining(w, trip, w.get(move, "to"))
    if rem >= INF:
        return float(-INF)
    return float(-(w.get(move, "fare") + rem))


# name -> rating function. The network scores a move as `weights . ratings`.
RATINGS = {"greedy": _greedy, "lookahead": _lookahead}


# -- the network: a distinct scorer, per step ---------------------------

class Policy:
    """A linear scorer over the planners' ratings: `score(move) =
    weights . ratings(move)`. The **distinct evaluator** of ADR-13 -- it reads
    the candidates, returns a selection, and writes nothing. Grown offline and
    frozen before it runs."""

    def __init__(self, weights):
        self.weights = {name: float(value) for name, value in weights.items()}

    def score(self, w, trip, move):
        return sum(weight * RATINGS[name](w, trip, move)
                   for name, weight in self.weights.items())

    def decide(self, w, trip, moves):
        """The selection: argmax over the surviving candidates, ties by id.
        Pure -- nothing on the blackboard is touched. `None` if nothing survives
        the budget (give up)."""
        live = [m for m in moves if not w.has(m, "vetoed")]
        if not live:
            return None
        return max(live, key=lambda m: (self.score(w, trip, m), -m.id))

    def describe(self):
        return " + ".join("%+.0f*%s" % (self.weights[name], name)
                          for name in sorted(self.weights) if self.weights[name])


# The two fixed reference policies: one planner each.
WEAK = Policy({"greedy": 1})
STRONG = Policy({"lookahead": 1})


# -- the engine stand-in: materialize -> evaluate -> apply -> record ----

def _remember(w, step, move):
    """The engine records the **selection** into world data (ADR-13): the step,
    the leg chosen, and its fare -- the trajectory, as a sequence."""
    record = w.spawn()
    w.mark(record, "applied")
    w.set(record, "step", step)
    w.set(record, "leg", w.get(move, "leg"))
    w.set(record, "to", w.get(move, "to"))
    w.set(record, "fare", w.get(move, "fare"))
    return record


def step(w, trip, policy, n):
    """One recognize-act step: materialize the moves, exclude the unaffordable,
    select, apply, record. Returns the chosen move, or `None` if none survives."""
    moves = materialize_moves(w, trip)
    budget_exclude(w, trip, moves)
    chosen = policy.decide(w, trip, moves)
    if chosen is None:
        return None
    train_advance(w, trip, chosen)
    _remember(w, n, chosen)
    return chosen


def run(network, policy, max_steps=None):
    """Run one scenario step by step. Returns `(world, score)`. The score is the
    cash left on arrival, or `PENALTY` if the goal was never reached -- the
    **step budget** (default `2 * stops + 2`) cutting a policy that strays."""
    w = build(network)
    trip = _trip(w)
    if max_steps is None:
        max_steps = 2 * len(network["stops"]) + 2
    for n in range(1, max_steps + 1):
        if step(w, trip, policy, n) is None:
            break
        if w.has(trip, "done"):
            break
    reached = w.has(trip, "done")
    return w, (float(w.get(trip, "cash")) if reached else float(PENALTY))


def trajectory(w):
    """Read the application memory back, in order -- the sequence of selections
    the network made, as ordinary data an ordinary operation can reason over
    (the homoiconicity payoff; the note's 'system-2' role, which is just
    operations)."""
    return [{"step": w.get(record, "step"),
             "to": w.get(record, "to"),
             "fare": w.get(record, "fare")}
            for record, _applied, _step in sorted(
                w.each("applied", "step"), key=lambda row: row[2])]


# -- growing the network: a search over the weights ---------------------

def _grid():
    """A small, deterministic grid of weight vectors, simplest first so a tie in
    total score keeps the simplest weights."""
    for greedy in (0, -1, 1):
        for lookahead in (0, -1, 1):
            yield {"greedy": greedy, "lookahead": lookahead}


def grow(networks):
    """Grow the network offline: score every weight vector on the scenarios and
    keep the best. Frozen before it runs (ADR-13)."""
    best = None
    for weights in _grid():
        policy = Policy(weights)
        total = sum(run(network, policy)[1] for network in networks)
        if best is None or total > best[0] + 1e-9:
            best = (total, weights, policy)
    return best[2]


# -- the oracle, and the comparison -------------------------------------

def _best_cost(w):
    """The cheapest simple path's cost to the goal, or `None` -- a brute-force
    oracle, independent of the planners."""
    trip = _trip(w)
    start = w.get(trip, "start")
    goal = w.get(trip, "goal")
    adjacency = {}
    for frm, to, fare, _leg in _legs(w):
        adjacency.setdefault(frm, []).append((to, fare))
    best = [None]

    def walk(at, cost, visited):
        if best[0] is not None and cost >= best[0]:
            return
        if at == goal:
            best[0] = cost
            return
        for to, fare in adjacency.get(at, ()):
            if to not in visited:
                walk(to, cost + fare, visited | {to})

    walk(start, 0, {start})
    return best[0]


def _oracle(networks):
    total = 0.0
    for network in networks:
        cost = _best_cost(build(network))
        total += (float(network["cash"] - cost)
                  if cost is not None and cost <= network["cash"] else float(PENALTY))
    return total


def _total(networks, policy):
    return sum(run(network, policy)[1] for network in networks)


# -- scenarios ----------------------------------------------------------

TRAIN = (
    # every move affordable; both planners reach the goal
    {"name": "easy", "stops": ["A", "B"], "legs": [("A", "B", 5)],
     "start": "A", "goal": "B", "cash": 10},
    {"name": "chain", "stops": ["A", "B", "C"], "legs": [("A", "B", 1), ("B", "C", 1)],
     "start": "A", "goal": "C", "cash": 10},
    # a cheap leg strays: greedy walks A<->B and never arrives; lookahead arrives
    {"name": "stray", "stops": ["A", "B", "C"],
     "legs": [("A", "B", 1), ("B", "A", 1), ("A", "C", 5)],
     "start": "A", "goal": "C", "cash": 10},
    # two routes: greedy takes the dearer one, lookahead the cheaper
    {"name": "multi", "stops": ["A", "B", "C", "D"],
     "legs": [("A", "B", 2), ("B", "D", 3), ("A", "C", 2), ("C", "D", 2)],
     "start": "A", "goal": "D", "cash": 20},
)

TEST = (
    {"name": "easy2", "stops": ["A", "C"], "legs": [("A", "C", 3)],
     "start": "A", "goal": "C", "cash": 10},
    {"name": "chain2", "stops": ["A", "B", "C", "D"],
     "legs": [("A", "B", 1), ("B", "C", 1), ("C", "D", 1)],
     "start": "A", "goal": "D", "cash": 10},
    {"name": "stray2", "stops": ["A", "B", "D"],
     "legs": [("A", "B", 2), ("B", "A", 2), ("A", "D", 3)],
     "start": "A", "goal": "D", "cash": 10},
    {"name": "multi2", "stops": ["A", "B", "C", "D", "E"],
     "legs": [("A", "B", 1), ("B", "E", 4), ("A", "C", 1), ("C", "D", 1),
              ("D", "E", 1)],
     "start": "A", "goal": "E", "cash": 20},
)


def main() -> int:
    policy = grow(TRAIN)
    print("grown network: %s" % policy.describe())
    for label, networks in (("train", TRAIN), ("test", TEST)):
        print("  %-5s grown %+7.1f   weak %+7.1f   strong %+7.1f   oracle %+7.1f"
              % (label, _total(networks, policy), _total(networks, WEAK),
                 _total(networks, STRONG), _oracle(networks)))
    w, _ = run(TRAIN[2], policy)               # stray: the per-step trajectory
    print("trajectory (stray):", trajectory(w))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
