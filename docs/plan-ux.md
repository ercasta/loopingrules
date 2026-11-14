# Plan U — the user experience: authored islands, resolved anchors, a grown control network

Status: **design.** This consolidates `docs/decisions.md` (ADR-1…ADR-8, the UX
discussion) into a plan. It builds on **Phase S** — the attribute substrate
(`plan-attributes.md`, largely built on the `attribute-substrate` branch) — and
on design docs D5 (the forge), D6 (islands), D7 (reflection), D9 (the control
network), D10 (mazes). It is the answer to `docs/ux.md` (the steering note) and
to `docs/handoff.md` §6. Nothing here is a commitment to code: **every phase is a
probe with a kill/reshape criterion**, in the repo's posture.

Read `docs/decisions.md` first — this plan is its execution, and the ADRs carry
the reasoning.

## 1. The thesis, stated once

> The engine is a tiny **fixpoint** kernel; the substance is a **library of
> islands** (clusters of rules keyed by terminology); structured input **anchors**
> onto islands; and a **grown control network** resolves the ambiguities
> (non-confluence) that a person cannot feasibly rule by hand.

Everything is entities (ADR-4): input, rules, and examples are the same kind of
thing over different entities. So **there is no separate authoring pipeline**
(ADR-1, ADR-8) — and no engine-level vocabulary of "registers" or "domains." What
exists is *structures*, the *islands* that read them, and the *network* that
composes the islands.

A term's definers decide what computation is needed (ADR-8):

| definers of a term in the input | what it is | mechanism |
|---|---|---|
| **none** | under-specified | a **gap** — D5's read-without-writer; ask, never induce |
| **one**, or several *confluent* | unambiguous | **fixpoint** — deterministic rules suffice |
| **several, non-confluent** | **ambiguous** | the **control network** resolves it |

The third row is the whole reason for the growth algorithm: the resolution is a
**policy over (context × ambiguity)**, whose space is combinatorial, so a human
"manually creating rules for the control network" is infeasible. Without
ambiguity the system is just fixpoint computation. And **ambiguity is
non-confluence** (`plan-scheduler.md`), so the control network matters exactly
where the fixpoint is order-sensitive.

## 2. What it revises

- **Locked 8** ("no LM in the runtime decision path") — **refined**: an LM may be
  a **tool at the edge**, called through the tool convention, its output coerced
  and verified before it enters the world (ADR-1).
- **Locked 11** ("stated rules write structure; examples fit values") — **split**:
  concepts are *declared*; wiring/conditions are *grown*; values are *fit*
  (ADR-2). The pattern/island library is the inductive bias that makes the
  growth tractable.
- **The handoff's Track A** ("finish the forge first") — **reordered**: under
  ADR-7 the forge IR *becomes the engine's rule form*, so "the forge" is the
  authoring/generation surface over that datum, not a spike to complete before
  the UX work. The port's red piece is therefore reframed, not merely finished.
- **D5 (forge)** — the IR moves toward the engine core; the forge keeps the
  catalogue, the human/DSL surface, and the generator (ADR-7).
- **D6 (islands)** — islands become the **terminology-indexed library** the whole
  design rests on (ADR-6); the "cross-island read graph" moves to the controller,
  one level up (ADR-5).
- **D9 (control network)** — its **motivation is now derived** (ambiguity =
  non-confluence; the policy space is combinatorial), rather than asserted. The
  algorithm stays open, to be chosen by a probe.

## 3. The shape, in one picture

```
input (structures)            islands (the library)              examples
  terms  ──enquiry──►  resolution ──► islands whose terms match  ──fitness──►
     │                     │ (no definer → gap)                        │
     │ anchors             │                                           │
     ▼                     ▼                                           ▼
  what must appear   compose rules + control  ◄── grown by the control network
                          │
                          ▼
                  a frozen trajectory over the fixpoint kernel
```

- **The kernel** (ADR-4): the thin, fixed set of rules that lower to primitives;
  the ground and the trusted computing base. **Everything above it lowers to
  concepts** — a term with no definer is a blocking gap.
- **Islands** (ADR-6, D6): a cluster of rules + vocabulary that *manages* a
  concept ("underrated", "a graph", "a procedure"). Indexed by **signature** —
  lexical (terms) and structural (shape patterns) — so retrieval is a lookup, not
  a search over all agents.
- **Anchors** (ADR-8): a term in the input is a *requirement* (the trajectory
  must use it) and an *index* (it retrieves the island that manages it). An
  explicit hint ("model this as a graph") is a *hard* anchor; a term is a *soft*
  one.
- **Growth** (ADR-2, D9): composes islands — wiring and conditions — **guided by
  the anchors** and **scored by the examples**. It searches **wiring and values,
  never concepts** (no L1 induction).
- **The anchor for training** (ADR-4): a **frozen-judge tower** — a mechanical
  base (the `checks` / a maze's ground truth / profit), with learned judges as
  dense proxies validated against the base.
- **Bundles** (ADR-5): an agent is a capability bundle — vocabulary + rules +
  **declared interfaces (terminology + shapes)** + examples + knobs — so it
  composes obliviously and can be trained jointly.

## 4. The phases

Order is **dependency- and risk-driven** ("prove the seam below before building
above"). Phases are independent enough to ship and test on their own.

| Phase | Deliverable | Depends | Design |
|---|---|---|---|
| **U0** | The decisions (ADR-1…8) + this plan + prose reconciliation | S | `decisions.md` |
| **U1** | **Walking skeleton**: a grown rule-level controller composing two real islands, guided by a structured anchor, scored by a mechanical example | U0 | this doc |
| **U2** | **The anchor schema + resolution**: structured input; term → island; gaps | U1 | ADR-8 |
| **U3** | **The island library**: evaluation/ranking, scoping, procedure-following, graph — each terminology-indexed | U1 | D6, ADR-6 |
| **U4** | **Tools**: the calling convention + render/parse adapters (external data; the LM's home) | U2 | ADR-1, circuits.Call |
| **U5** | **The rule-as-entity + kernel fold**: rules as term entities; staged execution | U1 | ADR-7, D7 |
| **U6** | **Bundles & packaging**: declared interfaces + terminology; joint examples | U3, U4 | ADR-5 |
| **U7** | **The NL edge**: the statistical coercion, LM as last-resort tool | U2, U4 | ADR-1/3, D5 |

### U0 — The decisions *(design)*

`docs/decisions.md` (ADR-1…8) and this plan; reconcile the prose that still says
"components," and reconcile D5/D6/D9 and `plan.md`'s locked 8/11. **Not a code
phase.** Probe: a review that the ADRs are coherent and the revisions in §2 are
accepted.

### U1 — The walking skeleton *(the thesis, cheapest)* — **probe built**

**Deliverable.** `loopingrules_ux.s5` (pinned by `tests/test_ux_s5.py`): a
**rule-level** grown controller — `Loop(schedule=True)` + `loop.rule(...,
controller=True)` — composing two independent islands (a **route** island and a
**trade** island), scored by a **mechanical** example (final cash). The
controller reads the cross-island context (listings, offers, fares, the trader)
and routes by **control attributes**; the grown policy is **world data** the
controller reads, so the controller itself stays `analyze`-clean. No
rule-as-entity, no kernel fold — it uses what exists.

**The seam it tests.** *Can growth compose two islands into a correct multi-step
trajectory and generalise?* **Result:** it grows `['spread>0', 'affordable']` — a
policy that beats a do-nothing and an always-trade policy, and generalises to
held-out scenarios the search never saw (train +70, held-out +95). **Pins:** the
islands do not read the policy (unchanged — selected, not rewritten); the
controller writes only control attributes; every rule is `analyze`-clean; every
scenario settles.

**Two findings, acted on.** (1) The *literal* `examples.trip` / `examples.market`
do not compose: their models are a plan-search and a stationary market, where the
composite needs a *moving trader* — so U1 uses minimal islands of the same shape;
the real islands' reuse is U3's bar. (2) Per-deal selection ("buy *this* card") is
a **binding** choice a rule-level `RuleControl` cannot express (the scheduler
doc's own point), so the controller routes by **control attributes** — a concrete
instance of "activation-level control needs IR-native rules."

### U2 — The anchor schema + resolution

**Deliverable.** The **anchor schema**: what a structured directive is —
`do`/`buy`/`step`/… as entities with named attributes (`#1.buy.what =
"underrated"`); **resolution** (a term → the island that manages it; a term with
no definer is a **gap**); and the first **"batteries"** — the metarules that read
anchors.

**The seam.** *Does structured input resolve and drive a trajectory, and is an
unresolvable term an honest gap?* **Probe (S1):** a structured directive drives a
deterministic trajectory; an unknown term abstains. **Kill/reshape:** if the
schema cannot express the `ux.md` examples without ad-hoc shapes, reshape it.

### U3 — The island library — **S3 probe built**

**Deliverable.** Shipped islands, each with a **terminology index**: an
evaluation/ranking island (generalising `judge`/`decide`), a **scoping** island
(which candidates), a **procedure-following** island (a cursor over steps), and a
**graph** island (paths, dominance — `trip` already *is* one). **Still to
build:** the terminology index and the shipped islands themselves (only the
ambiguity probe has landed).

**The seam.** *Reuse across two domains* (the D6 bar) *and* a grown policy
resolving ambiguity among islands. **Probes:** S2 (calibrate a lexicon;
held-out generalises) + S3 (grow the disambiguation policy among ambiguous
islands) — **S3 built**. **Kill/reshape:** if islands do not reuse across
domains, the reuse layer (D6) is wrong.

**S3 result** (`loopingrules_ux.s3`, pinned by `tests/test_ux_s3.py`): two
chooser islands both write `want` (a real conflict); the controller picks one by
context via `RuleControl`; growth finds the context-dependent `afford_first`
(arbitrage iff the best-spread deal is affordable, else bargain), beating every
fixed choice and generalising (held-out +210 vs +175 / +40). **Finding (the
grain):** *which ISLAND* is a **rule-level** choice (`RuleControl`); *which
DEAL* — S5's choice — is a **binding**, needing control attributes. The two
probes together pin both mechanisms.

### U4 — Tools

**Deliverable.** The **tool convention** — a rule deposits a `ToolRequest`, a
shipped answerer calls the tool on a later tick (no rule blocks; the
`circuits.Call` seed) — plus a **render/parse adapter manifest** and a small
standard library (CLI/JSON/HTTP). An **LLM call is just another tool** at the
last rung (ADR-1).

**The seam.** *An island reaches the external world without blocking, and the
mapping is declared.* **Probe:** an island reads a file / calls an API through the
convention; an unanswered request is a gap. **Kill/reshape:** if the convention
cannot confine the free Python and keep the rules analyzable, reshape it.

### U5 — The rule-as-entity + the kernel fold

**Deliverable.** Rules as **term entities** (ADR-7): a rule entity = identity +
derived projections + a **body** (a flat instruction list with expression trees);
**derived** `reads`/`writes` and the **production view** (`lhs`/`rhs`); a
structural hash over the datum + `version`. **Staged execution:** render Python
first (today's engine), fold to interpreting the datum (the kernel) later.

**The seam.** *Rules are data all the way down, totally analyzable, with a
structural hash.* **Probe:** `r1`-style — analysis over the datum is total and
agrees with `analyze` on Python; a rendered rule reproduces `signature`.
**Kill/reshape:** if the datum needs verbatim escapes beyond lexing/formatting,
reshape the term language (as M0 did). **Unlocks:** activation-level control
(D9's second half) and homoiconic meta-rules (ADR-6).

### U6 — Bundles & packaging

**Deliverable.** An **agent bundle** = vocabulary + rules/islands + **declared
interfaces (terminology + shapes)** + examples + knobs (ADR-5); a format on
`share`; **joint examples** at two tiers (contract-level + rollout/DAgger).

**The seam.** *Bundles compose and joint training transfers.* **Probe:** two
bundles compose with interfaces declared; a **held-out joint** split (train the
pair, evaluate on an unseen partner). **Kill/reshape:** if joint examples do not
transfer, the interface is too loose — narrow it, or add rollouts.

### U7 — The NL edge

**Deliverable.** The **statistical coercion**: user text → the anchor schema,
through the **ladder** — schema-constrained input → metarules → tools → an LM as
last-resort tool — with **round-trip verification**.

**The seam.** *Text → structures is a separate, gate-checked edge.* **Probe
(S4):** the LM as last-resort tool on the residual; the dumped structure
round-trips exactly; an NL round-trip is judged. **Kill/reshape:** if the edge's
output cannot be verified structurally, narrow it — the structured mode bypasses
NL entirely.

## 5. Probes (cheap, falsifiable)

Each is a milestone, not a feature; each has a kill/reshape criterion (above).

- **S1 — coercion as rules, no LM.** A structured directive drives a trajectory
  deterministically; an unparseable one abstains.
- **S2 — calibrate the lexicon.** Fit token → attribute constants with `search`;
  held-out generalises; a wrong lexicon degrades.
- **S3 — the disambiguation policy** *(built: `loopingrules_ux.s3`)*. Two islands
  both handle a term; the controller picks one by context via `RuleControl`;
  growth finds `afford_first`, beating every fixed choice (held-out +210 vs
  +175 / +40). Pins that *which island* is a **rule-level** choice.
- **S4 — the LM as last-resort tool.** Only the residual; output coerced and
  round-trip-checked before entering the world.
- **S5 — the cross-island controller** *(built: `loopingrules_ux.s5`)*. Two
  islands (route + trade) composed by a grown controller that reads a
  cross-island context and routes by control attributes; ground truth = final
  cash; grows `['spread>0', 'affordable']` and generalises (train +70, held-out
  +95).

## 6. Cross-cutting invariants (CI fitness functions)

The guards that keep the design from eroding — each a test that can fail:

- **The kernel stays thin.** A size budget on the kernel: if it grows, both the
  well-foundedness and the trusted-computing-base argument weaken (ADR-4).
- **The bootstrap base case.** The *fixed* kernel processes input and examples; a
  **trained** component is never required to process training data.
- **Resolution gaps are blocking.** A used-but-undefined term is a gap, never
  guessed (D5, ADR-8).
- **Anchors constrain; they never synthesize.** No L1 pattern induction; growth
  searches wiring and values only (ADR-2).
- **Select, never rewrite.** The network composes and gates; it never edits a
  domain or island rule (locked 8).
- **Freeze before run; determinism.** Replay twice, same `signature`; the network
  is frozen before it runs (D5/M2, D9).
- **The concession ledger.** Any escape (verbatim helpers, an LM tool) is declared
  with a reason and reported, never silent (D5).

## 7. How success is judged

1. A non-coder gives **structures + examples**; the system grows a controller; the
   agent solves held-out cases it was not shown.
2. **Islands are reused**: a second domain depends on a shipped island at runtime
   (the standing D6 bar), not a copy.
3. A term with no definer produces a **gap** (a question), never a guess.
4. The **islands are unchanged** by the network — it selects, it does not rewrite.
5. The same evaluated **checks** drive offline calibration and the online
   controller (the product thesis's existing criterion, kept).

## 8. Open questions, and what this does not settle

- **The growth algorithm** — D9's crux, deliberately left to a probe (GP/GE over
  the IR with XCS-style credit plus library learning, or another). This plan does
  not choose it.
- **The exact anchor schema** and the *island* taxonomy (which islands exist, how
  each declares its signature). The register table in ADR-8 is a description of
  outcomes, not a fixed set.
- **Confluence detection** — not cheaply decidable, so the plan assumes ambiguity
  and treats confluence as an optimization.
- **Credit assignment across independently-authored islands** (ADR-5) — harder
  than within one.
- **Cost** — the tension between the island library's breadth and the growth
  search.
- **The NL layer's model**, and how much structure a UI enforces (schema-driven
  autocompletion vs free text) — ADR-1's ladder leaves it open.
- **The name** — `plan-ux.md` / "Plan U" is provisional, as `loopingrules_forge`
  and `loopingrules_islands` are.
