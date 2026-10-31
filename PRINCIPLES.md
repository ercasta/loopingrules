# Principles — what makes the entity/component/rules substrate produce the RIGHT kind of emergent behaviour

## What kind of emergence this is actually for

"Emergent behaviour" hides at least two different things, and this substrate
is deliberately built for only one of them.

Rules here are oblivious of each other — no rule calls another, the only
channel between them is what gets deposited into the shared `World`. That
*is* real, structural stigmergy: `patterns.LoopCount` gets attached with zero
awareness that `constraints.max_loops` exists; `constraints.max_loops` fires
purely because `LoopCount` showed up. Nobody wrote that pipeline; it
assembles from independently-authored, mutually-ignorant rules the same way
a blackboard architecture's knowledge sources do (Hearsay-II is the direct
architectural ancestor of this shape). That is the kind of emergence this
repo wants, and gets: complex, composed conclusions arising from many small,
individually-legible rules, with the composition never explicitly written
by anyone.

## What is machine-derived, and at which layer

This repo used to say: **structure is authored; only the tuning knobs are
machine-derived** (`docs/tuning.md`, "tune values, never structure"). That
**scope is retired** — `docs/plan-forge.md` (D5) machine-*translates* a corpus
into components and rules. What is retired is the *scope*, not the
*discipline*: the reason the old rule existed — search over structure is
program synthesis, intractable to search and hard to verify — survives as the
*how* (frozen operators, verification gates, provenance, freeze-before-tune,
refuse-rather-than-guess). Discarding the reason along with the scope would
license exactly the drift this file exists to prevent.

Stated as layers, each with its own authority and its own verification:

| Layer | Was | Now | Authority |
|---|---|---|---|
| **Engine core** (`world`/`loop`/operators) | frozen, general | frozen, general — unchanged | this file |
| **Structure** (components/rules) | authored by hand only | machine-*translated* from the corpus, verified, **frozen before use** | the corpus |
| **Values** (knobs) | fitted by search | fitted by search — unchanged | examples/puzzles |
| **Edges** (NL channel / renderer) | (did not exist) | learned adapter, run time, grounded in the catalog, lossy, never authoritative | the catalog |
| **Domain facts** | the author's head | **the corpus, and only the corpus** | human |

Two honest consequences. First, there are now **two kinds of machine
contribution**, not one — a pretrained LM as a *translator* (its prior shapes
proposals) and search over *values*. Second, the machine's role is
**subordinate and build-time**: the LM *proposes*, the corpus and the gates
*dispose*, the artifact is *frozen* and deterministic, and the LM is **not in
the loop at deploy**. The old rule therefore still holds *at run time*; what
changed is *authoring*.

> Machine contribution is admitted at every layer, but each layer has its own
> authority and its own verification. The corpus is the sole source of domain
> facts; structure is machine-*translated* from it, gated, and frozen; values
> are fitted by search; the operator set stays frozen and general; NL is a
> lossy adapter at the edges; and **nothing learned sits in the runtime core's
> decision path.**

Two invariants this file already owns and that the change does **not** touch:
**values are primitives only** — there is no semantic value-type layer; a type
system over values is an ontology, and semantics lives in the component, not
in a catalog type system — and **the operator set stays frozen** ("operators
generalize; semantics do not").

