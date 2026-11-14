# Modeling: structure, behavior, and reified actions

The *modeling* half of the system — what the agent reasons over — as opposed
to the rules it executes. It is **background and design; not built**, except
where noted. Read alongside the [study guide](study-guide.md) and the
[study plan](study-plan.md).

The one-line answer: **the modeling layer is the executable world plus
reified actions, a planner and a belief representation — not a separate
ontology.**

## "Model" means five things

Most confusion here is one word doing five jobs.

| what | models | formalisms | in this repo |
|---|---|---|---|
| **Structure** | what exists: classes, attributes, relations | OWL/RDF, ER, JSON Schema | ECS components + declared connections |
| **Behavior** | what happens: transitions, inference | rules, production systems, Datalog, state machines | the rules |
| **World / dynamics** | what happens next, given state and action | MDPs, PDDL, Dyna, world models, simulators | the rules, *executed* (`replay`) |
| **Belief** | what the agent *thinks* is true | POMDPs, Bayesian nets, Markov logic | not built; beliefs-as-components is possible |
| **Objective** | what is wanted | cost/reward, preferences | checks + scorer |

## Why OWL/RDF cannot carry behavior

It is not merely "relations, not behavior" — four concrete things are missing,
and `plan-forge.md` already rejects OWL/RDF for three of them:

- **Open-world and monotone.** No negation-as-failure, no defaults, no
  retraction. But a tag is a *fluent*, not a class membership; the useful
  predicates are attach/detach.
- **No time and no change.** Descriptions are timeless; behavior is change.
  This is the **frame problem** (McCarthy and Hayes, 1969).
- **No actions or effects.** Nothing states "doing X makes Y true."
- **Global triples, not entity-attached components.** A relation is an edge in
  a graph, not something an entity carries.

The critique is old and standard: Brachman, *What's in a link?* (1975). The
gap is exactly **non-monotonicity + time + action** — and every formalism that
models behavior supplies them.

## Traditions that unify structure and behavior

The right move is not "ontology plus a rules engine"; it is one artifact:

- **Frames** (Minsky, 1974) — a structured object whose slots can hold
  *procedures* (if-needed, if-added). A frame *is* a component-with-rules; it
  is the ECS's direct ancestor.
- **Logic programming — Datalog, ASP** — a relation is *defined by rules*, so
  there is no separate ontology: the predicate set is the model and the clauses
  are the behavior. ASP adds the non-monotonicity OWL lacks.
- **Situation and event calculus** (McCarthy and Hayes 1969; Kowalski and
  Sergot 1986) — fluents, actions, and effects, over time.
- **PDDL** — state predicates plus actions with preconditions and effects; a
  modeling language for behavior, with a solver attached.
- **Frames plus production rules = the expert system** (OPS5, KEE, ART) — the
  classic ancestor of a blackboard: a frame system for structure, a production
  system for behavior, a blackboard joining them.

## The model is executable

In this substrate, **the rules are the model, and the model runs**:

- `replay` executes the world — the dynamics model is free, exact, and cheap.
- **`save`/`load` plus deterministic `replay` is world-cloning** — a plan is a
  search over forked futures. This is model-based RL with the model being the
  program, and it is something a learned world model cannot offer.
- The change log (`World.changes`) is a **temporal record** — fluent-style
  history, ready for invariants over time.
- Structure is **derived, not authored**: the forged catalog (derived
  components and connections) *is* the ontology, read off the rules rather than
  declared beside them. That is the whole difference from OWL, and it is why
  there is no second semantic layer to drift.

## Reified actions: a description that is also executable

The precise requirement: a rule must be **black-box executable**, *and* be
**describable by components**, *and* that description must itself be
**executable** — and therefore **reason-able**. Four properties, each with a
mechanism:

| property | mechanism |
|---|---|
| the action is a first-class object | reified action (situation-calculus term; PDDL schema; GOAP action) |
| effects are specified as component deltas | STRIPS add/delete lists; PDDL effects; event-calculus `initiates`/`terminates`; ECS effect/command entities |
| the description is executable | an *operational semantics*: an interpreter `run(schema, state) -> state'` |
| therefore it can be reasoned over | search, plan, and compose over the schemas |

The load-bearing property is the third: a description *plus* an executor. That
is the standard meaning of **operational semantics**, and it is what makes
"reason and execute on the same object" possible.

**The triad to adopt:** *(reified schema) + (effect deltas as components) +
(black-box executor)*.

### The Rubik's cube, concretely

- **Schema:** `Rotation(face, turns)` — a component.
- **Effects as deltas:** stickers on `Face` components change — an explicit
  add/remove list, as data.
- **Executor:** one rule applies the schema.
- **Reasoning:** because the schema is data, the agent can *search* (a
  sequence of rotations is a plan), *inspect* (which faces does it touch), and
  *compose*. And rotations form a **group**, so the action algebra has
  composition, inverse and identity — the algebra is what makes actions
  reason-able rather than merely runnable.

### Existing systems

| group | systems | why it matters here |
|---|---|---|
| planning | **STRIPS/PDDL**, **action languages `A`/`B`/`C`/`C+`**, **situation calculus + Golog**, **event calculus** | action as data with an executable semantics; Golog adds a search operator |
| practical / game AI | **GOAP** (Orkin), **HTN** (SHOP2, PyHOP), **behavior trees** | the ECS-shaped realization: actions with preconditions/effects searched by a planner and run by an executor |
| agent architectures | **BDI / PRS / AgentSpeak / Jason**, **model-based programming** (Titan, Livingstone) | plans as data; an agent that runs a declarative model to plan, execute and *diagnose* |
| formal "the description is executable" | **rewriting logic / Maude** (reflection + `search`), **abstract state machines**, **SOS**, **homoiconicity** | one semantics where rules are data, meta-executable, and searchable |
| action composition | **process algebras** (CCS, CSP, pi-calculus) | the algebra for composed actions |

### What this repo already has, and the gap

Already present: `circuits.Call` to `ToolRequest` is action-as-data plus a
separate executor; `Bought`/`Reply` are results as components; `circuits.py` is
rules-as-data; `replay` plus `save`/`load` is forkable execution.

Missing, precisely:

1. **The effect specification as the source**, not a hand-written rule body —
   a declarative effect list the executor realizes.
2. **An action algebra** — composition, inverse, identity — so actions can be
   reasoned about, not only run.
3. **A planner** over schemas (GOAP/PDDL-shaped), where today `search` tunes
   knobs only.

### The anti-drift discipline

Do not add a schema that lives beside the rules. **Derive the effect
description from the executor** (the `analyze` introspector) and **check the
declared schema against the derived one** — a contradiction is *reported, never
merged*. That is how "described by components" avoids the drifting second layer
that sank ontology engineering.

## Uncertainty and belief

The world model is the rules; uncertainty is one of:

- **a component** — a belief or distribution is ordinary data on the
  blackboard, and `party`-style *investigation* rules are how it is reduced
  (Bayesian-ish, without a graphical model);
- **an environment tape** — recorded nondeterminism, so a stochastic model is a
  distribution over tapes and the run stays reproducible;
- **an explicit probabilistic layer**, only if needed — Markov logic
  (Richardson and Domingos 2006), ProbLog, PSL, or **POMDPs** (Kaelbling,
  Littman and Cassandra 1998) for belief dynamics.

The honest trade: probabilities buy principled uncertainty at the cost of the
determinism this repo treats as load-bearing, so that layer belongs *beside*
the deterministic core, never inside it.

## What to add, and what not to

Add: reified action schemas with effect deltas; derive/verify them; an action
algebra; a planner over schemas; beliefs as components.

Do **not** add an ontology, a value-type system, or a schema maintained beside
the rules — all three are second semantic layers that drift. Derive instead.

## Pointers

- Frames: Minsky, *A Framework for Representing Knowledge* (1974).
- What a representation *is*: Davis, Shrobe and Szolovits, *What is a Knowledge
  Representation?* (AI Magazine, 1993); Brachman, *What's in a link?* (1975).
- Structure and behavior in one: Brachman and Levesque, *Knowledge
  Representation and Reasoning* (2004); Gelfond and Lifschitz on ASP (1988).
- Actions over time: McCarthy and Hayes (1969); Kowalski and Sergot (1986);
  Levesque et al., Golog (1997).
- Planning: Fikes and Nilsson, STRIPS (1971); Fox and Long, PDDL (2003); Nau et
  al., SHOP2 (2003).
- Practical actions as data: Orkin, *Three States and a Plan* (GOAP, 2006);
  Colledanchise and Ögren, *Behavior Trees* (2018).
- Executable specifications: Meseguer, rewriting logic (1992); the Maude book;
  Gurevich, abstract state machines (1995).
- Model-based autonomy: Williams et al., Titan / Livingstone.
- Uncertainty: Kaelbling, Littman and Cassandra (1998); Richardson and Domingos
  (2006); De Raedt et al., ProbLog (2007).

## What this does not settle

- Whether the action schema is the *source* the executor realizes, or a
  *derived view* checked against it (the derive-vs-declare question).
- The action algebra for a domain whose actions do not form a group.
- Whether the planner is in-substrate (a rule) or an external search over the
  forked world.
- How a probabilistic layer can coexist with the determinism gate.
