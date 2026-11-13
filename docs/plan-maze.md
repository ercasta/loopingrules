# D10 — Knowledge mazes: a benchmark for the control network

Status: **design only.** This doc defines the benchmark the
[control network](plan-control-network.md) (D9) is to be grown against, and
proposes a first probe. Nothing is built: no maze, no domain, no test. It is
written down so the shape is not lost, in the posture the rest of the plan
takes.

## The problem, stated once

D9 needs a **fitness with ground truth**. A control network is grown against
something; if that something is a single domain's settled state, the search
learns *that domain* and there is no way to tell good control from a lucky
constant. The discussion named the wanted thing precisely: a **knowledge maze**
— a problem whose correct answer is found only by applying a set of rules
**whose application has not been coded**, but steered by the control network.

So a maze has to give two things at once:

- **ground truth** — there is a right answer, so a network can be scored (and
  credited) without a human judging each trajectory;
- **no coded solution** — no rule says "go left here"; the *moves* are generic
  and always available, and only the control network's attribute-setting
  decisions choose among them. A rule set that already encodes the path is a
  program, not a maze.

## What a maze is

A maze is a **family**, not a puzzle:

- a **world** — entities and attributes forming a graph of states or facts;
- a **goal** — a state, or a derived fact, that is the right answer;
- a set of **moves** — domain rules that are individually legal from many
  states and *collectively* under-determined (each move is available, none says
  which is right); the moves read **control attributes** the network sets;
- a **solution** — a trajectory of rule applications that reaches the goal,
  possibly the shortest one;
- a **score** — `checks` over the trace (goal reached, ticks, moves), so the
  Phase-4 vocabulary scores a maze with no new machinery.

The navigation is over **rule applications**, not only over space: the state
graph is explored by firing rules, and choosing *which* application to fire is
the whole difficulty. That is the activation the scheduler (extends D7)
resolves, so a maze is the natural end-to-end test of D9.

The first shape is deliberately small and spatial — a graph of `Node` entities,
a `Move` rule legal to any neighbour, a goal node, a network that must gate
moves by control attributes — because a spatial maze is the cheapest place to
see the mechanism. A second shape is a **derivation** maze: each node is a fact
to establish, each move derives a fact from another, and the answer is the
derivation — the case the note's "applying a set of rules" is literally about.

## Why mazes — and the XCS connection

This is the benchmark the study guide already names. The XCS entry's toy is
**Wilson's "woods" maze**: a classifier system learns to navigate a maze of
percepts, and it is chosen there because it exercises exactly what D9 needs —
*per-rule credit assignment over a multi-step trajectory*. A knowledge maze is
that toy lifted onto this substrate: states are attribute configurations,
actions are rule applications, and `World.changes` is the firing context.

Three properties make a maze family, rather than a single domain, the right
instrument:

1. **Ground truth without an oracle.** Solved / shortest-path / moves-used are
   mechanical, so fitness needs no human.
2. **Shared sub-structure.** A family can be generated so that mazes share
   branches. A control split that solves one branch solves it in every maze that
   contains it — which is exactly the **sharing** D9 is built for, and makes the
   claim (does a shared split buy sample efficiency?) measurable rather than
   asserted.
3. **Held-out generalization.** Generate a training family and a held-out
   family with the same generator, and a network that *generalizes* is
   distinguishable from one that memorized. `examples/bridge_transfer.py`'s
   `learning_curve` already does this for one decision; a maze suite scales it.

## The first probe (proposed, not built)

Cheap, deterministic, and each claim falsifiable — the M0/Q0 idiom:

- **A maze family.** One generator, a small parameter (graph size, branching,
  shared sub-branches), a goal, and generic `Move` rules gated by control
  attributes. No rule hard-codes a path.
- **The claims to pin:**
  1. **Without control, the goal is not reliably reached** — the generic moves
     alone do not solve it (or solve it only by a documented accident), which is
     what makes "the application was not coded" true rather than assumed.
  2. **With a hand-written control network, the goal is reached** — a small
     authored network (a few scoring/control rules) solves the maze, so the
     mechanism is real before any search runs.
  3. **Determinism** — the same maze and network replay to the same trace
     (`plan.md`'s reproducibility gate).
  4. **Sharing** — two mazes that share a sub-branch are solved by a network
     that reuses one split for both, and the reuse is visible (the shared
     scoring rule fires in both) rather than inferred.
  5. **Only then**: `evolve`-style search grows a network that solves the
     *training* family and generalizes to the **held-out** family.
- **What it must not do:** ship a maze whose moves already encode the answer, or
  score with internal-vocabulary checks that presume the network's own split
  structure (D2's hazard — the check would reward the very structure being
  searched for).

## How a maze trains the network

The maze is the **training signal** for D9, and it closes a loop the plan
already has in pieces:

- the **fitness** is `checks` over the maze trace (goal, ticks, moves);
- the **novelty signal** is the scheduler's `Doubt` — a state no scoring rule
  covers, on which the offline generator grows a control rule (the runtime
  cousin of the forge's compile-time *gap*);
- the **generator** is the forge's (D5) — `evolve`'s GP over the IR, extended
  to a network, or whichever algorithm D9 settles on;
- the **proof** is held-out generalization: a network grown on one maze family
  and scored on another it never saw.

A maze family is therefore also a **dataset** in D2's sense — a versioned
collection of `(scenario, checks)` with a held-out split — which is why this doc
belongs beside `plan-dataset.md` rather than replacing it.

## What this does not settle

- **The maze generator.** Graph size, branching, shared-branch structure, and
  whether mazes are authored, generated, or both — undecided.
- **The scoring function.** Shortest path, moves-used, ticks, or a `checks`
  composition — and how to penalize a non-settling run without making the maze
  about settling rather than solving.
- **Spatial vs derivation mazes** as the *first* one. The spatial maze is
  cheaper; the derivation maze is closer to "applying a set of rules."
- **How hard a maze should be.** Too easy and a constant wins; too hard and the
  search never gets signal — the difficulty schedule is unaddressed.
- **Whether the moves are one rule or many**, and whether a maze may vary the
  move set (which would test the network against a *changing* rule set, a
  different and harder thing).
- **The relationship to the `examples/` domains.** Whether a maze is its own
  `loopingrules_maze` package, an `examples/` family, or a forge fixture.

## Open questions

1. Is a maze a new package (`loopingrules_maze`), an `examples/` module, or a
   forge fixture, in the layout the other spikes already chose?
2. Is the goal checked from the trace (`checks.world_has`) or by a domain rule
   that attaches a `Solved` attribute — and does that rule count as a move?
3. Does the maze suite reuse `checks`, or does it need a goal/optimality term
   `checks` does not have?
4. Does the first probe grow the network with the existing `evolve` (GP over one
   controller), or wait for D9's network genome?
5. Should the maze family ship with its **ground-truth solutions** (so credit
   assignment can be checked against the optimal path, not only the outcome)?
