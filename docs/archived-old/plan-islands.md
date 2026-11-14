# D6 — Islands and bridges: the semantic-foundation layer

Status: **spike built** (`loopingrules_islands`, probe `i0`), pinned by
`tests/test_islands_i0.py`; **nothing folded in yet** (see `TODO.md`). This
doc records only what a probe holds up, on purpose: `DECISION_PATTERNS.md`
was deleted in `cdf98d6` because a prose design that nothing pins does not
survive. Every claim below names the probe or the shipped code that pins it.

This is the layer `docs/plan.md`'s product thesis calls *authorship handles
structure* — but it is not the engine (`loopingrules/`) and not the forge
(`docs/plan-forge.md`, which consumes it). It is the **reuse** layer: how
one domain's concepts become workable by another domain's rules without
either knowing the other exists.

## The problem, stated once

An author making a domain *like* `cards` should not rebuild owning, buying,
offering, budgeting and pricing. In a library they would: `cards` imports
the shape, so only the compositions `cards`' author **anticipated** can
exist. This substrate is built for the other thing — `PRINCIPLES.md`'s own
example, `patterns.LoopCount` attaching with zero awareness that
`constraints` exists, and `constraints` firing because `LoopCount` showed
up. The composition was never written by anyone.

## The shape

* **Island** — a vocabulary (components), the rules over it, and its **own
  decision process**. An island is **closed in authorship** (nothing in it
  imports a domain) and **open in reads** (any rule anywhere may read a role
  it confers). `loopingrules_islands/items.py` is one.
* **Role** — a component an island confers on an entity (`items.Item`),
  making it workable by every rule over that role, anywhere.
* **Bridge** — a **domain's own projection** of a fact onto the island's
  thin shape (`items.Candidate(worth)`), the geometry
  `loopingrules_patterns.judge` already ships: *the domain owns the
  projection, the island owns the decision*. `judge` thresholds a projected
  scalar into a tag; `items.consider` confers a role. Same move.
* **Composition** — a rule reading across islands and concluding something
  neither can. Two forms, both real:

  | Form | Shape | Instance |
  |---|---|---|
  | **Convergence** (many → one) | many islands project onto one thin shape; one oblivious reader | `judge.flag_too_risky` over `Risk` (`cards`, `shopping`, `market`) |
  | **Conjunction** (several → one) | one rule reads different islands' vocabularies | `i0.affordable_items` over `items.Item` + `funds.Spendable`; and `patterns.LoopCount` → `constraints` |

## Why this is not "a library where X uses Y"

Because the composition need not be **anticipated**. A third rule can read
`items` and `funds` and conclude `Affordable`, and neither island's author
foresaw it. Without conjunction, the substrate is a call graph with extra
steps and should be a plain program — which is the honest reason to build
this layer at all.

## Branch space and sample efficiency

The branch factor at an entity is **the number of bridges whose reads are
satisfied** — not the number of roles in the system. A bridge must read the
entity's precondition to be a candidate, so the reachable set is the closure
of a **sparse, typed transition relation** (the Hearsay-II property). The
`items.consider` guard makes it literal: it reads `Candidate` and
(`without=Item`) the absence of itself, so only projected candidates can
ever be asked, and only once.

The sharper claim is about **questions**, not states: to wonder "should this
be an `Item`?", the `items` island must *contain a rule that wonders it*.
The space of askable questions is **finite and authored**; only the answers
are calibrated. That is the sample-efficiency mechanism versus a next-token
predictor, which must also learn *which questions exist* and pays for it
across an unstructured `|V|^L` space. Measuring it is future work (see
`bridge_transfer.learning_curve`, which already does this for one decision).

## Patterns (pinned)

1. **Projection, island-owned decision** — domain writes the thin shape,
   island decides. `judge`; `i0` claims 2, 3.
2. **Question-as-read, idempotent** — `w.each(Precond, without=Role)`:
   once conferred, the entity leaves the loop, the world settles.
   `items.consider`; `i0` claim 1.
3. **Reuse with zero island rewrite** — a second domain writes only its own
   projection. `i0` claim 3; `tests/test_examples_bridge.py` (identity).
4. **Conjunction** — one rule across two islands. `i0` claim 4.
5. **Reach bounded by projections** — a role rule writes only where a
   domain projected. `i0` claim 5.

## Antipatterns (named; the instrument to catch them)

1. **Fabricating candidates** — the island scans the whole world instead of
   waiting for projections; reach becomes unbounded, and it invents a
   projection no domain made. Caught in `i0` claim 6.
2. **Unbounded reads** — reading the whole world / the log unfiltered. The
   transition stops being local. (Same family as 1; not yet probed.)
3. **Island confinement everywhere** — every rule reads only its own island.
   No bug, but no stigmergy either: the "why are we here" failure, and the
   default unless conjunction is actively enabled.
4. **Spooky coupling** — the *hazard* of conjunction: X and Y coupled
   through a Z invisible from either island. Not fixable inside an island;
   the strongest argument that a **derived cross-island read graph** is
   load-bearing, not documentation. Not yet built.

**The instrument:** `i0.reach(trace)` reads the D1 change log
(`trace.changes`) — the entities each rule actually wrote on — rather than
the AST. Reach is what the rule *touched*, so a rule that scans everything
is not made to look local by a declared read set.

## What this does not settle

* **Monotone vs. revisable promotion.** `items.consider` is monotone (never
  detaches) so `i0` settles trivially. A revisable role is what lets a
  controller move the decision online (`docs/plan-adaptation.md`) and is also
  where flicker lives — the next probe.
* **What a decision may read.** Only its subject, or history/the change log?
  This sets how much context a bridge gets; `i0` reads only its subject.
* **Cycles and ladders** — chained promotion A→B→A, terminal concepts,
  trait explosion. Unprobed.
* **Overlapping bridges** — two islands both claiming an entity. Traits are
  multi-role by default; exclusivity would need the regulator
  `DECISION_PATTERNS.md` argued for (now deleted; see `TODO.md`).
* **The catalog's role** — where the derived read graph, the declared
  connections and the composition-opportunity gaps live.

## Open questions

1. Is an island a `shape` (vocabulary + rules a domain instantiates) or
   something an engine affords structurally? `loopingrules_patterns` calls
   the first a *shape*; this doc does not merge the two yet.
2. Where do islands graduate to, and what is the promotion bar (today:
   `README.md`'s "a second domain depends on it at runtime")?
3. Does a role ever carry a value (`Item.worth`) or stay a bare marker, with
   the value read from the projection?
