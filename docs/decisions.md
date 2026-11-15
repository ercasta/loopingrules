# Architectural decisions (discussion draft)

A short, living record of the decisions the UX discussion settles — each with
its rationale and what it revises, in the repo's habit of ending a doc with what
it does *not* settle, kept as we go. This is a **draft**: entries are numbered,
marked **proposed** or **settled**, and revised freely — this repository is a
stratification of experiments, and revising an earlier decision is normal.

Status: **consolidated into [`plan-ux.md`](plan-ux.md).** ADR-1…ADR-4, ADR-9,
ADR-10 and ADR-13 are **settled**; ADR-5…ADR-8, ADR-11 and ADR-12 stay
**proposed** until a probe disagrees. Nothing here is a commitment to code. The
design docs the ADRs reference (D5–D10, `plan-*.md`, `modeling.md`,
`comparison-soar.md`) now live under `archived-old/`.

ADR-10…ADR-13 are a **correction pass** over ADR-1…ADR-9, from the steering note
kept at `archived-old/components and control network.md` (discussed, not
transcribed: the note mixed the *operation language* with *engine seams*, and
each was sorted before anything was written). They revisit the substrate (D8) and
the control network (D9); where they revise a *settled* decision, that decision
is marked revised in its own entry, not left to drift.

---

## ADR-1 — The schema is the coordinate system; the rules are the model; text is coerced into it

Status: **settled** (the frame the rest hangs off).

**Context.** The system's user experience is: a non-coder authors an agent
(rules + examples), trains a control network, and deploys it; users then
interact with it (text, and possibly a richer UI). Today every domain is a
Python module. The attribute substrate (D8) was simplified *precisely* so that
structure need not be Python — but no authoring surface exists yet, and no
surface exists for turning a user's text into something an agent can act on.

**Decision.** The agent's "language" is not a bespoke syntax; it is its
**entity-attribute schema** — the *coordinate system* of the models it speaks
(ADR-9). A piece of text is understood exactly insofar as
it can be **coerced** into that schema — into entities and attributes the agent
knows. Both kinds of text are coercions of the same kind:

| | free text is… | coerced into… | level |
|---|---|---|---|
| **Authoring** | a description of a domain | the vocabulary: shapes + rules | meta |
| **Use** | a request | an *instance* (see ADR-3) | object |

They are **one mechanism at two targets**, not two languages.

**Rationale.** What an agent can understand is exactly what fits its model, and
its model is the set of entities and attributes it knows. Any text that does
not coerce is, by construction, *not understood* — which makes the failure mode
honest (a gap/question, never a guess) and makes "no-code authoring" tractable
without a grammar per domain. It also keeps the substrate's invariant
(semantics lives in the name), and aligns with the forge's pivot (NL ↔ catalog,
no NL↔NL shortcut) and with locked decision 8 (structured I/O, no LM in the
runtime decision path).

**Consequences.**

- The **schema** (shapes, attributes, kinds, ref targets) is a first-class
  artifact, declared (D8) and cross-checked against derived use (D5).
- **Coercion failure is structural**: an uncoercible text is a *gap* — a
  question — never a guess (`PRINCIPLES.md`: abstention must be structural).
  This is the forge's gap taxonomy, reused at run time.
- One **ladder**, used at both targets, **deterministic-first**:
  1. schema-constrained input (autocompletion / a form);
  2. shipped **metarules** (the "batteries");
  3. **tools** (CLI / API / files);
  4. an **LLM/SLM as a last-resort tool**, called through the tool convention,
     its output coerced and verified like any other tool.
- The **unification**: tool calling, ingestion, authoring, and the forge are
  one pipeline — *render (attributes → input) + parse (output → attributes)* —
  aimed at four targets, verified the same way (round-trip + "does it fit the
  schema").
- **Asymmetry, named now:** run-time input is deterministic-first; authoring
  (meta-level) is the harder coercion, because it must produce *rules*, so it
  may legitimately lean on a proposer (LM or human) with the gates disposing —
  D5's Agenda, as the authoring rung of the ladder.
- **Locked decision 8 is refined, not repealed:** the LM is a *tool at the
  edge*; it is never in the runtime decision path, and its output must pass
  coercion before it enters the world. (Same move `circuits.Call` made for
  tools.)

**Revises.** Frames the forge's "vertical axis" (NL → catalog) and the
run-time "NL channel" as one mechanism; refines locked decision 8 to admit an
LM-as-tool at the edge.

**Open.** Is the schema declared or derived (or both with a cross-check) —
queued 7? What exactly does a rule look like as data — queued 6? Where do the
batteries live (engine vs sibling package) — queued 8?

---

## ADR-2 — Declare the vocabulary and patterns; fit the values; grow the holes

Status: **settled** (the worked sentence is agreed).

**Decision.** Every piece of an agent has exactly **one** source:

| # | Level | What it is | Source |
|---|---|---|---|
| 0 | **Vocabulary** | shapes, attributes, kinds, ref targets | **authored** (from text, or proposed by an LM and gated) |
| 1 | **Pattern** | a rule's skeleton: what it reads/writes, its control-flow and effect shape | **authored** (text → IR, gated) |
| 2 | **Hole — value** | a constant the pattern reads | **fit** from examples |
| 3 | **Hole — condition/policy** | a boolean over *declared* attributes; a disambiguation choice | **grown** from examples/fitness |
| 4 | **Hole — lexicon** | token → attribute/value | **fit** from examples |

The rule that keeps `declare, never infer` alive: **examples can never invent
level 0.** They fit functions over an authored vocabulary; inference is
confined to typed holes inside a declared frame.

**The worked sentence.** `"book the cheapest taxi from Downtown to the Airport
before 9am"` → `taxi_request{origin=#d, destination=#a, deadline=540,
objective='cheapest'}` (an instruction entity, *not* state), by a level-1 chart
kernel + level-4 lexicon (`"9am"→540`) + level-3 policy (deadline vs depart).
The *same* levels produce this for an author's text and a user's request —
ADR-1's "one mechanism, two targets."

**Revises locked 11** (*stated rules write structure; examples fit values*): by
admitting that a *hole* may be **grown** from examples, not only values fitted.
Precedent: `loopingrules_forge.evolve` grows a condition hole inside a
hand-supplied controller pattern, gated by `analyze`-clean + settles.

**The boundary: the pattern library.** "Level-1 induction" — inventing a
*pattern* from examples with no text naming it — is the rabbit hole: ill-posed
(infinitely many programs fit any finite examples), enormous prior needed, and
it cannot bootstrap level 0. It is the ILP / program-synthesis / grammar-
induction class. Its **tractable form** is **pattern selection from a curated
library** (threshold, ranking, matching, aggregation, …) plus hole-filling: the
library *is* the inductive bias, and it is exactly `loopingrules_patterns` /
the D6 islands. So the scope of grown structure is set by the library — grow
holes in any pattern it offers; do not invent patterns.

**Consequence.** The reuse layer (D6) and the pattern library are not only
ergonomics — they are the **prior** that makes any examples-driven structure
tractable. A richer library is a stronger inductive bias.

**Open.** How large must the library be before examples-only (no text) is
usable? Ship a handful of new patterns, or reuse `judge`/`decide`/the islands?
(And: is "lexicon" really level 4, or just level 2 — a token→value map is a
value?)

---

## ADR-3 — Input coerces through instruction entities, by a computation, not a grammar

Status: **settled** (schema-driven; stages agreed).

**Stages.** Run-time text is coerced in stages: text → token entities →
**typed instruction entities** (a command vocabulary) → domain **state**. Only
the domain's own rules write state; **the parser never writes domain state**,
however it is built (ADR-1's consequence).

**The bold half.** The coercion is not a grammar written once; it is a
**computation**: a fixed set of **meta-rules** — domain-independent rules that
read the raw instruction *and the schema as data* (homoiconicity) — whose firing
is a trajectory over the tokens, resolved by a control network. The rule set is
**assembled (structure) and calibrated (values) from the examples**.

**Decomposition (the answer to "what is the algorithm").** Three learnable
things, each with a home — deliberately *not* "induce a parser from nothing":

| Layer | What | Built by | Home |
|---|---|---|---|
| **Kernel** | domain-independent meta-rules + the intermediate structures (a chart/stack of candidate parses, as entities) | **hand-written**, fixed, small | new |
| **Lexicon** | token → attribute/value, thresholds, normalization | **calibrated** from examples | `calibration.search` (held-out) |
| **Policy** | which candidate / which meta-rule wins (disambiguation) | **grown** offline, frozen | D9 control network |

This is ADR-2's levels pointed at parsing: kernel = level 1, lexicon = level 4,
policy = level 3.

**Settled: schema-driven, tokens steer.** The parse is **seeded by the
instruction shape** (an Earley/chart-flavoured kernel); **tokens steer** — they
set control attributes and resolve disambiguation — but they do **not** discover
the schema. ("Tokens drive the trajectory" was the bottom-up reading; the
counter-proposal — schema drives, tokens steer — is adopted.)

**Two timescales.** The **parse** is runtime over a *frozen* policy (locked 8
holds: the network selects, never rewrites, and is frozen before it runs); the
**growth** is offline across examples. One mechanism, two timescales.

**Why homoiconicity is load-bearing.** The meta-rules must read the model
(shapes/attributes, kinds, ref targets) *and* assemble rules. Three homoiconic
layers are required: schema-as-entities, rules-as-entities, input-as-entities —
then both reading and assembling are ordinary `each`/`get`.

**Abstention is the correctness criterion.** Ambiguous or unparseable text is a
**gap** (spawn a question; `party.py`'s investigate idiom), never a guess;
held-out examples are the generalisation check.

**Revises.** Locked 11 — see **ADR-2** for the split (author the vocabulary and
patterns; fit values and lexicon; grow holes), where the boundary is the
pattern library.

**Open.**

- Markers alone cannot express unbounded nesting: the blackboard must carry an
  explicit **parse state** (chart/stack) as entities. Confirm the shape.
- Where the growth algorithm lives (D9), and whether the first growth target is
  the D10 maze or a parse-ambiguity benchmark.

---

## ADR-4 — One mechanism: a thin ground; everything else lowers to concepts

Status: **settled** (the "close the loop" move).

**Decision.** There is a **thin, fixed kernel** of built-in rules — the only
things that lower to primitives (`spawn`/`destroy`, `set`/`add`/`append`/
`mark`/…). Everything else — **authored rules, input, examples, and agents
alike** — is expressed as entities that **lower to concepts defined by other
rules**, resolved stigmergically (the control network). A rule does **not**
compile to a formal primitive language; its meaning is *realized by other rules
depositing and reading attributes* on the blackboard. "Lowering" therefore means
**derivation**, not a compile step.

**Same move as ADR-1/2/3, completed.** ADR-1: input coerces into a schema.
ADR-3: the coercion is a computation over meta-rules. ADR-4: the meta-rules
*themselves* — and authored rules, and examples — get the same treatment. The
system is **one mechanism**, not "a language plus a runtime." (Reflective tower,
ground = kernel; Maude's operators-are-rules; bootstrapped compilers.)

**Three payoffs.**

1. **A trusted computing base.** The kernel is the only trusted code; every
   authored rule, input, and example is *data* it interprets. An untrusted
   author (a person, an LM) cannot turn a rule into arbitrary code — the
   `circuits.Call` motive ("confine free Python to tools; keep rules as data"),
   promoted to the whole architecture.
2. **Grounded explanations for free.** `World.changes` already records which
   rule produced which attribute at which tick; lowering *is* a trajectory, so
   "why" is the trace — no separate instrumentation.
3. **Homoiconicity completed** — schema, rules, input, examples, agents: all
   entities, all `each`/`get`.

**Well-foundedness (the realism).** A tower needs a ground and a progress
measure:

- **The kernel is finite and fixed** (the ground). A concept with **no definer**
  is a **blocking gap** — the forge's coherence gate ("read but never written"),
  doing exactly this job.
- **Progress is a gate**: the budget catches non-termination (`hot`);
  determinism is a gate; MDL prioritization prefers reusing an existing
  definition (cost 0).

**The ground is the kernel — not the example pipeline.** It is tempting to say
"examples are processed by a fixed machine," but **example interpretation is
domain-dependent**: which span is input, which is target, and what the target
*means* is a concept like any other, lowered by other rules (ADR-2: authored
pattern + grown holes). What must be fixed is only the **kernel** at the
bottom; *anything above it — including the interpreter of examples — may be
authored or grown*. The regress stays well-founded because the kernel grounds
the bottom, not because every layer is frozen.

**The anchor, concretely: a frozen-judge tower.** Joint growth needs a judge,
and the judge may itself be trained — but never all at once. Training
**alternates**: one part is trained while a **frozen judge** verifies it; then
that judge may be unfrozen and trained, while **another** fixed judge anchors
it. Two conditions make this well-founded rather than circular:

- **It bottoms out in a *mechanical* judge.** The base is the `checks`
  vocabulary / held-out examples / a mechanical benchmark (D10) — **never
  learned**. A learned judge is a *dense proxy* for it, not a replacement.
- **Every learned judge is validated against the *base*, not its parent.**
  Imitation across generations is a game of telephone: a judge trained to match
  the previous judge drifts one generation per step. The parent supplies
  *density*; the base supplies *truth*; each judge is re-scored against the base
  (a drift check) and **abstains where the base is silent** (ADR-3).

The freeze is the runtime discipline applied to training: at any moment, the
thing being *changed* is anchored by something *not being changed*, and only a
**frozen tuple** is ever deployed — which is why the alternation is offline.

**Prior art / mapping.** RLHF-shaped (a learned reward model over a fixed
human/mechanical anchor; iterated = reward-model iteration), iterated
amplification, and bootstrapping compilers (stage0 trusted). The pieces already
exist here: `calibration.checks`/`scorer` **is** the mechanical base judge; D9's
**scoring rules are the learned judges**; D5's `Frozen` (M2) is the freeze
mechanism. (D5's corpus — clauses + worked examples + clarification layer — *is*
a grown example interpreter; the Agenda is its loop.)

**Boundary.** Where the base cannot judge, a learned judge has no anchor and
must **abstain** rather than invent. A domain with no mechanical ground truth at
all cannot use joint/learned-judge training for that part — it falls back to
authored controllers + judged examples.

**Caution.** "Thin" is load-bearing: if the kernel grows, the TCB erodes. Put a
size budget on the kernel in the plan, not only in prose.

**Revises.** Subsumes "rules as data": a rule is an entity like everything else
(the *exact shape* — reads/writes/lhs/rhs — is still open, queued). Extends D7/D9
(rules over rules) from *control* to *definition*.

**Open.** The kernel's exact size and contents (what is primitive?); the
progress measure; how a "no definer" gap is surfaced to the author (the forge's
Agenda).

---

## ADR-5 — Agents are interface-declaring bundles; examples train jointly

Status: **proposed.**

**Context (the covariate-shift argument).** A user-defined agent rarely does
anything useful alone: it works in composition, where its inputs are the
*outputs of other agents*. Training it in isolation sees the marginal input
distribution; composing shifts the inputs to an **induced distribution** →
**covariate shift** → degradation. So a bundle should ship **examples for joint
training**, not only for standalone fitting.

**Decision.** An **agent is a capability bundle**: vocabulary + rules + **the
interfaces (bridges) it reads and writes** + examples + knobs. The interfaces
are **declared and load-bearing** — they are the contract that *bounds* the
shift (an agent's input distribution is mostly what its bridge says), so
contract-level training transfers. Examples ship at **two tiers**:

- **contract-level** — the input distribution the declared interface implies
  (transfers under oblivious composition);
- **joint / rollout** — the *induced* distribution under composition
  (DAgger-style: roll out the composed system, gather the states this agent
  actually sees, relabel). Opt-in coupling.

**Where the shift actually lives: the controller, not the domain agent.** Two
different "interfaces" are in play. A **domain bridge** (D6) is narrow and
oblivious — that is the composition bet, and contract-level examples transfer. A
**controller's context** (D9) is a *different level* ("one level of
reflection") and is deliberately **cross-cutting**: a combination of facts in
different islands calls for a specific trajectory, so a controller must read
**across** islands. That read set *is* its context — and it is exactly a rule's
derived `reads`, which `analyze` already computes. So "context" is a
first-class, derivable object, not new machinery. Consequence: **the
covariate-shift concern lands primarily on the controller** (its input is the
combined cross-island state), so *controllers* are what must be trained
jointly; domain agents can still train on contract-level examples when their
bridge is narrow.

**D6's warning and D9's split, reconciled.** The cross-island read graph D6
forbids at the **domain** grain is the **legitimate content** of a controller,
one level up. Domains stay oblivious; the controller is the single point that
holds the global context — the composition bet preserved and the larger context
admitted at once.

**Why the interface, not co-adaptation.** The repo has already bet on
**oblivious composition** (D6: rules communicate only through the world; a rule
need not know who else is installed) and "freeze each structure before it
runs." Joint co-adaptation would weaken both. A **declared, narrow interface**
keeps the bet while bounding the shift — at the domain grain; the controller is
where cross-island coupling is *wanted*, and it is bounded by its derived read
set and D9's one-level discipline.

**Machinery we already have.** `calibration`'s `Scenario`/`replay`/`Trace` *is*
an example-as-data; a **rollout trace is a scenario**. D6's bridge is the
interface; D6's cross-island read-graph antipattern is the coupling warning, at
training grain. Binds D6 + D2 + D9 into one statement.

**Consequence / open.** "Agent" now means the **unit of sharing** (a capability
bundle), subsuming pattern/island/bridge — worth a naming split from a running
instance. Open: how a bundle **declares** its interfaces; how joint examples
are represented (`Scenario` sequences vs a trace); whether composition is
validated by a **held-out joint** split (train the pair, eval on an unseen
partner); how a controller's **context** is bounded (it is *derived* — must it
also be capped?); and **credit assignment across independently-authored
islands** (harder than within one, and the anchor for joint growth, ADR-4).

---

## ADR-6 — Thinking modes: a library indexed by signature, activated by inference or hint

Status: **proposed.**

**The idea.** Beyond value patterns, the library holds **thinking modes** —
reusable *reasoning* patterns (graph, ranking, search, planning, matching, …). A
mode **contributes concepts**, not a call: graph contributes `node`/`edge`/
`path`/`dominance`. A domain that says "train X goes from A to B" never says
"graph", yet solving it needs graph reasoning — the mode supplies it.

**Refined (ADR-9).** A thinking mode is not a separate kind of thing: it *is* a
**model** (a coordinate system + the operations that act in it), distinguished
only by **generality** — a narrow, domain-independent interface that opens a
broad gate. So "which modes exist" is a *derived* property of the library, not a
declared category, and the "structural key" below is the rule's derived
**model-span**.

**Activation = the dormancy gate.** A mode is **resident**; its rules fire when
the world carries the shapes they read, so activation *is* `analyze`'s gate
opening. No call is made; concepts compose on the blackboard. This is the line
that separates the design from **function calling**: no caller/callee, no
return — a resident, **steerable**, interleaved mode.

**Retrieval is by signature — two keys, not brute force.**

- **lexical** — the domain's terms ("goes from", "cheapest") map via the lexicon
  (ADR-2 level 4) to a mode;
- **structural** — the domain's *shape pattern* matches (e.g. `leg` references
  `stop` twice — a self-relation ⇒ a graph signature), independent of words. The
  robust key, because the schema is the coordinate system (ADR-1/ADR-9); its
  precise content is the rule's derived **model-span**.

So the library is **indexed**, and a domain retrieves the modes whose signatures
match — never "explore all possible agents".

**Hints.** A user may *name* the mode: "model this as a graph." Coerced (ADR-1)
into a `modeling_directive{target, mode}`; **rules about modeling** read it and
activate. A hint is a **human prior** that *prunes* the search — it constrains
the library, it does not replace it. It is D5's Agenda human channel: "which
modeling approach?" is a **gap**, routed to the human, whose answer is a corpus
event, not a code edit.

**Freeze tension, resolved.** Runtime rewrites nothing (locked 8/13). Two
readings:

- **closed world over the library** — the union of every mode's vocabulary is
  the frozen **catalog** (D5); modes are *rule bundles* over it; activation is
  rules + control attributes only, so a runtime hint merely **steers**
  (`mode=graph`) — runtime-safe; **or**
- **activation loads vocabulary** — a structural change, admissible only at
  **authoring/training** time (the hint shapes the frozen bundle).

The combination (which modes, how wired) is **grown offline and frozen** (D9).
(Recommended: the closed-world reading — the catalog *is* the union schema; modes
are rule bundles; activation never mutates structure. Cost: schema size.)

**A hint is not a bypass.** It is admissible only if the resulting network passes
the gates (settles, reaches the target) — a *declared* prior, *verified* by
derivation: the repo's derive-beats-declared posture, with the human allowed to
*propose*.

**Consequences.** The pattern library (ADR-2/D6) becomes a **signature-indexed
library of thinking modes**; its index is the prior that makes composition
tractable, and a hint is a human entry into that index. The travelling trader
(S5) demonstrates it: `trip` already *is* graph thinking, and a hint would seed
it directly.

**Open.** Whether the closed-world catalog is practical at library scale (size
vs purity); how a mode *declares* its signature (terms + shape patterns);
whether a runtime hint may ever load a mode (not under the freeze); how hints are
provenanced (D5's Ledger).

---

## ADR-7 — A rule is a production made of entities; the IR is its canonical form

Status: **proposed.**

**Scope (see ADR-8).** This defines the **production** artifact — the lowered
form of the **policy** register, and of each step/effect inside the other
registers. It is the **atom**, not the authoring surface.

**What already exists.** `reflect.RuleCard` reifies a rule as an entity carrying
`hash`/`name`/`reads`/`writes`/`destroys`/`opaque`/`priority`, all **derived by
`analyze`**. So "a rule is an entity" is already committed; what is missing is
the **body** as data — today it is a Python callable the engine invokes, which is
exactly what ADR-4 says must not be the story.

**Decision.** A rule is an entity (`rule` flag) with two parts:

1. **Identity + derived projections** (what a `RuleCard` already is): `name`,
   `hash`, `version`, `priority`, `controller`; and derived (never authored)
   `reads`, `writes`, `destroys`.
2. **The body as data**: a **graph of term entities** — the IR, homoiconic, so a
   meta-rule can *read* a rule's condition and effects (ADR-4/6). Not a Python
   callable.

**The IR's role (decided).** The term graph **is** the canonical rule form;
**Python is a rendering** of it — used today to execute and as the `analyze`
audit, the target being the thin kernel **interpreting** the datum. So the forge
is **upstream** (surface + generator over the datum), and the **engine owns the
datum + its interpreter**. This is D7's "IR becomes an engine core" fold.

**Concretely** — `tag_affordable` as entities:

```
rule #100:  name="cards.tag_affordable"  version=1  hash=...  body=[#101]
#101 match: names=["listing","price"]  bind=("entity","listing","price")  body=[#102]
#102 if:    cond=#110  then=[#103]  else=[#104]
#110 cmp:   op="<="  left=#111  right=#112
#111 var:   name="price"          #112 var: name="room"
#103 mark:  target=var(entity)    name="affordable"
#104 unmark: target=var(entity)   name="affordable"
```

Derived `reads={"listing","price","purse","risk_profile"}` (the analyzer walks
`let`s and helpers as `analyze` walks Python), `writes={"affordable"}`.

**The scheduler's LHS/RHS is a derived view.** `plan-scheduler.md` wants a
production (`lhs` → `rhs`); that is the **projection** the matcher reads: the
leading `match` is the LHS binding, its guard the condition, the effect
statements the RHS (`q0` already did this for `decide_buy`). One canonical body,
several **derived views** — `reads`/`writes` and the production.

**Sub-decisions (recommended).**

- **Terms as entities, not a serialized blob** — ADR-4/6 require meta-rules to
  *read* rules. Cost: entity count (rules are few).
- **Body = a flat instruction list** (a sequence of instruction entities, control
  flow by index) with **expressions as small term-entity trees** — fits the
  substrate's flat-list rule, stays light and readable.
- **Stage execution**: canonical datum = the IR; execute by *rendering Python*
  first, fold to *interpreting the datum* (the thin kernel) later.
- **The production view is derived, not stored** (so it cannot drift).
- **Hash over the datum + `version`** — fixes `rule_hash`'s source collision;
  identity becomes structural (D7's target).

**Buys / costs.** A rule is data all the way down (ADR-4), read by meta-rules
(ADR-6), with a structural hash and a derived production view. Costs: the engine
grows a term interpreter; every rule needs a migration (Python → entities),
another clean-break pass.

**Open.** Where the term entities live (engine vs forge); how `analyze` splits
into datum (total) and Python (audit); `version`/operator-set governance (D5's
`Frozen`).

---

## ADR-8 — Agents, not a register classifier: structured input is grown into a trajectory

Status: **revised** — an earlier draft imposed a "classify the register first"
*stage*, an engine-level typology that ADR-4 forbids. Corrected here.

**The mistake.** Treating "registers" (procedure, preference, definition, …) as
an engine-level classification step imposed a workflow and reintroduced an engine
vocabulary. But **registers are not engine concepts**: a kind of input is
meaningful only because the system ships **agents** (rule bundles) that handle
it. So "register" ≡ "a cluster of shipped agents" (ADR-6's library) — not a
pipeline step.

**The corrected picture.** The input is already **structures** (entities/
attributes) — whether a human wrote them or a statistical NL encoder produced
them. NL is a *separate, lossy layer* (humans converge on expressions that
*usually* disambiguate); ADR-1/3's coercion is that **edge**, not the core. What
matters is **what happens next**:

- the input's attributes **open agents' gates** (ADR-6) — structural activation;
- the **examples** supply *fitness*;
- **growth composes** the shipped agents + control into a **trajectory** that
  satisfies both — and this is where agents *not named in the input* are pulled
  in ("which cards? all or a subset?" ⇒ a scoping agent; "underrated" ⇒ an
  evaluation agent).

So there is **no classification step**: the composition is *grown against the
examples*, not decided upfront. An input structure no shipped agent can handle is
a **gap** (ADR-3's abstention).

**The observation, kept (minus the pipeline).** Different input *structures*
grow different control nets — the same domain yields a pipeline or a chain, and
each pulls in agents the input never named. That divergence is a fact about
*grown outcomes*, not a stage:

| Input structure says | Grows toward | Implied agents | Control net |
|---|---|---|---|
| `buy.what = "underrated"` (a preference) | a scoring + a choice | evaluation, **scoping** | pipeline (scope→score→rank→act) |
| `step(#i)`, `step.next = #j` (a procedure) | a sequence | **procedure-following** + each step's | chain / state machine |
| a derived name (`underrated = f(...)`) | a computed attribute | — | dataflow |
| a bare condition (`cash < floor → forbid`) | a gate | — | gate |

**Worked, structured (no NL).**

```
do(#1)                  # a directive entity
#1.always    = True
#1.buy.what  = "underrated"
```

Nothing classifies this. The agent whose gate reads `buy.what` opens; whether the
trajectory satisfies the examples decides if an **evaluation agent** (resolve
"underrated") and a **scoping agent** (which cards) must be composed in. A
*procedural* input (`step(#i)`, `step.next = #j`) would grow a **different**
control net — the divergence the earlier table described, but produced by
**growth**, not by a classifier.

**Consequence.** ADR-6's library **is** the "register set": ship an agent for
procedures, and procedural input becomes handleable; don't, and it is a gap. The
library's richness widens the space of handleable input — the same "library is
the prior" point as ADR-2. And because input, rules, and examples are all just
entities (ADR-4), **authoring and use are the same mechanism** over different
entities (ADR-1), not two pipelines.

**Anchors: how a term guides the growth.** A term in the input (`"underrated"`)
is an **anchor** — two things at once:

- a **requirement** — the trajectory must *use* the `underrated` concept; and
- an **index** — it retrieves the **island** (D6) / agent that *manages*
  `underrated` (the cluster of rules that compute it, compare it, act on it), so
  growth "taps into whatever rules we have" for it. This is ADR-6's terminology
  retrieval, as an **implicit, soft hint**; an explicit "model this as a graph"
  is a **hard hint**. Same mechanism, different strength.

**Resolution, and the gap.** Each term must **resolve** to an existing concept
(island). Resolution is a *lookup*, not a stage — the same discipline `share`
uses for refs and `analyze` uses for names. A term that resolves to nothing is
D5's **read-without-writer gap**, exactly: the input *uses* `underrated` and no
rule *defines* it ⇒ a blocking gap ("how is `underrated` computed?"), routed to
the human/LM proposer, **never induced**. So "a mentioned term must be defined
somewhere" is not a new rule — it is the forge's coherence gate.

**Growth searches over WIRING and VALUES, not over concepts.** The concept set is
fixed (authored/shipped); growth composes it — which island rules fire, in what
order, under which control attributes — **guided by the anchors** (what must
appear) and by the **examples** (fitness). ADR-2 again: concepts *declared*,
wiring/conditions *grown*, values *fit*. Growth never synthesizes a concept and
never invents structure — a missing concept is a gap.

**The trichotomy: gap / fixpoint / control.** A term's *definers* decide what
kind of computation is required:

| definers of the term | case | mechanism |
|---|---|---|
| **none** | under-specified | a **gap** (D5 read-without-writer; ask, never induce) |
| **one** (or several, *confluent*) | unambiguous | **fixpoint** — deterministic rules suffice |
| **several, non-confluent** | **ambiguous** | the **control network** resolves it |

*(ADR-9 refines this: the mechanism is uniform — the kernel **enumerates**
candidate applications and the network **scores/selects one** — so the trichotomy
describes where the scores are non-trivial, not three engine modes.)*

**Ambiguity is non-confluence** (`plan-scheduler.md`: where rules settle, order
does not change the fixpoint; where they conflict, order *is* semantic). So the
control network is needed **exactly** where the fixpoint is order-sensitive — and
this is the *reason* the network is **grown** rather than authored: the
resolution is a policy over *(context × ambiguity)*, whose space is
combinatorial, so a person cannot feasibly write the control rules. **Ambiguity
is the motivation for the growth algorithm; without it the system is just
fixpoint computation.**

*Caveat:* confluence is not cheaply decidable, so the safe default is "assume
ambiguous; let the frozen control network resolve it" — confluence is an
*optimization*, not a precondition. And non-confluence is where the stability
question lives (D9's open): the network *reduces* oscillation, it does not prove
it away.

**Open.** How a *new* agent/island is admitted (gates + a probe); whether anchors
are per-bundle or global; and the **growth algorithm itself** (D9, deliberately
chosen by a probe).

---

## ADR-9 — Models, rules, and sequential application

Status: **settled** (the view the plan presupposes, stated). *(The selecting
network's mechanism is revised by ADR-13: it is a pure evaluator, not control
rules; and a rule is an **operation** — ADR-11.)*

**Context.** `ADR-1` asserts "the schema is the model" but never defines *model*
or *rule*; `ADR-7` fixes a rule's *form* but not its *meaning*; and `ADR-8`'s
trichotomy (gap / fixpoint / control) frames the engine as a **fixpoint** with a
controller for the exceptional ambiguous case. The discussion this consolidates
(`docs/model_spaces.md`, the working notes) forces the underlying view: what a
model is, what a rule is, and why composition needs a control network at all.
Stating it revises the engine's identity.

**Decision.**

1. **A model is a coordinate system plus the operations and relations that act in
   it.** The schema is the *coordinate system*; the *model* is the rules over it.
   This retires ADR-1's slogan "the schema is the model" (the schema is where a
   model is *expressed*, not what a model *is*).

2. **A rule is an operation**: identity + the *derived* projections
   (`reads`/`writes`/`destroys`, and `models`) + a body (ADR-7). A **joint
   operation** is a rule whose reads span **≥2 models** — a *derived* property
   (`models`), never authored. So "rule" is one noun; "joint" is a descriptor of
   its model-span.

3. **Rules are authored; so are the examples.** The author declares the vocabulary
   and the patterns *and* supplies the examples; the system fits values and grows
   conditions over them (ADR-2). Cross-model operations are authored, because
   their existence is a human claim that two imperfect models interact — and
   growth never invents concepts (ADR-8). A word that spans several models is
   therefore not a defect: it **names** a joint operation, and mapping it to that
   operation is coercion (ADR-1).

4. **The rule language is first-order over entities; composition is temporal.** A
   rule binds entities (LHS), guards, and writes entities (RHS) — no term is a
   rule. Apparent higher-order structure is *stigmergic*: an output entity a
   later rule reads (ADR-4's lowering-as-derivation). Recursion is **deferred
   re-firing** — a pending entity the next step consumes (the `circuits.Call` /
   `ToolRequest` idiom) — not nesting.

5. **The engine is an enumerating kernel plus a selecting network; it is
   sequential, not a fixpoint.** Each step: **enumerate** candidate applications
   (rules whose authored `guard` holds, instantiated over the entities present) →
   **score** each — the network's verdict is `score ∈ ℝ ∪ {exclude}` → **select**
   the non-excluded maximum, ties by canonical precedence → **apply** it. **Order
   is semantic.** The fixpoint is the degenerate case where all candidates
   commute — i.e. where the scores do not matter.

**Rationale.** Models are imperfect and overlap. A single universal operation
set — a group or a vector space — requires totality, type-consistency, and
consistency; heterogeneous models fail all three, so cross-model operations are
*authored bridges*, not derivations. What replaces orthogonality is **declared
overlap**: make the interferences explicit (as joint operations / interfaces)
rather than accidental. Selection among **applications** unifies ADR-8's two
mechanisms — "which rule" (S3's `RuleControl`) and "which binding" (S5's control
attributes) are both "which application" — so the grain the probes "pinned apart"
is an implementation detail, not a design law. **Exclusion** has two sources and
needs no second mechanism: the authored `guard` (structural, frozen) and the
learned scorer verdict (contextual). "Select, never rewrite" holds — excluding is
selecting, and both sources are frozen before run.

**The trichotomy survives as content, not mechanism.** No candidate ⇒ gap;
trivial scores ⇒ fixpoint-equivalent; contested scores ⇒ learned. The mechanism
is uniform — **score every candidate** — and the network drives *every* step, not
an exception handler for ambiguity. This is a *stronger* justification for D9
than ADR-8's: order mattering (non-confluence) is the normal case, and learning
is needed only where the scores are non-trivial.

**Consequences.**

- **ADR-1** (slogan, above): schema = coordinate system; rules = the model.
- **ADR-6**: a "thinking mode" is just a model, distinguished only by *derived*
  generality; the "structural key" is the rule's derived **model-span**.
- **The engine's identity** changes from "a tiny **fixpoint** kernel" to "an
  **enumerating** kernel plus a **selecting** network" (revises `plan-ux.md` §1
  and `handoff.md` §2).
- **Versioning** of the interfaces a rule spans stays **optional** — identity is
  name + structural hash; a version only if an author wants one.

**Open.** The cost of **join enumeration** (a two-frame rule is the cross-product
of matching entities — grounded and finite, but a real cost center); the
canonical **tie-break** precedence; the network's exact **features** (a function
of application × context); and whether a "step" is **one** application or a
selected **set fired to closure** (ADR-9 takes one; a selected set is the
confluence optimization).

**Revises.** ADR-1 (slogan), ADR-4 (the kernel is an *enumerator*, not a
fixpoint), ADR-6 (mode = model), ADR-8 (the trichotomy is content); `plan-ux.md`
§1 and `handoff.md` §2.

---

## ADR-10 — Components return: named, declared, model-qualified bags

Status: **settled** (a correction to D8's representation; the substrate's
invariants are kept).

**Context.** D8 retired the typed `@dataclass` component and re-founded on
**entity + attribute**, and Phase S shipped it as `entity → {name: value}` —
flat names, one slot per name. Two things were lost. First, **the declaration**:
the note names it precisely — *"components were the only way to declare schemas...
we need them back."* Phase S has no first-class component in the running system;
a "shape" is prose, and `world.refs` is the only declared set. Second, the
**namespace**: with flat names, every field name is global, so two models'
vocabularies collide (`purse`, `policy` — the collision the travelling-trader
composite already named).

**Decision.**

1. A **component** is a **declared schema**: a name, and a set of **field**
   declarations (field name; kind `singular`/`set`/`sequence`/`flag`; scalar or
   a **reference**; and a reference's target component). It is **not a Python
   class**, and it declares **no value types** (`PRINCIPLES.md`: values are
   primitives only).
2. Data is a **named bag of fields on the entity**: `entity → {component →
   {field → value}}`. A component is **both** its schema and its instance (the
   container). *(Confirmed in discussion, against D8's "a component is an
   entity.")*
3. **Model-qualified names.** A component's name is scoped by its **model**
   (ADR-12): `market.purse`, `cards.purse`. **The model IS the namespace**, so
   two models may each declare `purse` and never collide — structurally, not by
   convention.
4. **One slot per name, at both levels**: at most one component of a given name
   per entity, at most one field of a given name per component. Multiplicity
   lives *inside* a field as a **flat list** — D8's rule, applied twice, so B is
   not a return to classic ECS multiplicity.
5. A field value is a scalar, a **reference** (to an entity), or a **flat list**
   of those. **No structured value**; structure deeper than one level goes
   through references — the invariant "values are primitives only" holds: a
   component is a *namespace*, not a value.
6. A **tag** is a component with no fields.

**What this revises, and what it deliberately keeps.** It reverses D8's *one*
representation choice — a component instance is **not** an entity. It has no
independent identity, its lifetime is the holder's, and nothing references a
component instance (references point at **entities**). The simplification that
falls out is real and worth stating: **only entities have identity.** Kept
unchanged: D8's "one slot per name," the flat values, and the lists. The old
two-concept worry D8 removed ("component *and* many-of-a-type") does **not**
return — one-per-name plus a list-in-field covers multiplicity.

**Cost, named.** This reopens the substrate Phase S shipped and went green on
(`world`, `analyze`, `save`, `share`, `reflect`, and every example's
`each`/`get`). It is **another clean break of Phase-S size**, done whole, never
half-applied (D8's own rule).

**Revises.** D8's representation (referenced entity → bag on the holder);
answers **ADR-1's open** ("declared, derived, or both"): **both** — declared
components (here), cross-checked against derived use (`analyze`, D8's blocking
gap).

**Open.** Whether the declaration lives in the world as **entities**
(homoiconicity — so a meta-rule can read a schema) or as a module artifact the
engine loads — recommend **both**, one derived from the other. The exact query
spelling over qualified names (`each("listing.price")`). Whether a rule may set a
field no declaration names (recommend: yes, flagged underived) — D8's open 6.

---

## ADR-11 — Operations: a minimal, homoiconic language; tools are an engine seam

Status: **proposed** (the language is agreed; the rename's scope is open).

**Context.** ADR-7 fixed a rule's *form* (a production made of entities); ADR-9
made it a **capability**. The note renames it an **operation** — *"they just
specify what is possible and the effect of what's possible"* — and adds a
language law: *"if statements, but not while statements."* Its third sentence
bundles a language fact with an engine fact: *"alter the state of the blackboard
**and** call tools."* The discussion separated them.

**Decision.**

1. An **operation** is a capability: identity + **derived** projections
   (`reads`/`writes`/`models`) + a body over a **closed, limited operator set**,
   homoiconic (operations are entities, ADR-7). It **reads the blackboard and
   effects the blackboard**.
2. The language has **`if` (a guard) and effects, and no `while`.** Iteration is
   **not a construct**: it is **stigmergic re-firing** — an operation mints or
   consumes a marker and fires again on a later step because the world changed.
   A **loop model** is an **ordinary model** (components + operations, ADR-12)
   that packages that discipline; neither the language nor the engine knows it
   is "a loop."
3. **Tool calls are not language operators — they are an engine seam.** An
   operation **deposits a request** (a special entity/component); the engine
   **watches for it** and, **between two ticks**, calls the tool and reifies the
   output back as ordinary entities/components. The language never sees the
   call: no operator, no blocking, no return value. (The posture of
   `circuits.Call`/`ToolRequest`: confine free Python to tools; keep rules as
   data.) A tool-using operation therefore stays **analyzable** — the edge is
   *declared and named*, not code inside the operation body.
4. An **application** is an operation **bound** to concrete entities + context,
   whose guard holds. The engine **enumerates applications**; the network selects
   one (ADR-13). *"Rule"* stays the implementation noun; *operation* /
   *application* is the concept.

**Why separating the layers matters.** "Alter the blackboard" is a fact about the
*language*; "call tools" is a fact about a *seam the engine offers*. Stacked as
two operators, the language grows impure verbs and the "limited operator set"
and totality of analysis both erode. Sorted, a pure operation stays pure and the
tool edge is exactly the concession ledger's kind of edge: **declared and
reported.**

**Revises.** ADR-7/ADR-9 terminology only (rule → operation + application, and
the loop model named).

**Open.** Whether the concept rename propagates to **code** now or with the IR
fold (ADR-7's staged execution). Recommendation: the vocabulary now, the code
rename with the kernel fold — a nine-domain churn is not worth a cosmetic word;
the *distinction* (operation vs application) is what earns it, and it is already
real.

---

## ADR-12 — A model is an importable module; authors use a guided surface

Status: **proposed.**

**Context.** The note: *"a 'model' can contain components, operations, both or
some of them. They are distributed in an importable way so users can create
their system with a set of modules"*; and *"the homoiconic representation is not
what the authors write, we need some dedicated and guided editing."*

**Decision.**

1. A **model** is the unit of **distribution**: a module declaring a **namespace**
   (its model-qualified component names, ADR-10) and holding its **components**
   and **operations**, in any mix (components only, operations only, or both). A
   system is composed by importing models.
2. **Everything visible** *(confirmed in discussion)*: importing a model makes
   all its components and operations available; there is **no declared
   interface** yet. Composition is by the world and model-qualified names;
   ADR-5's declared bridge is deferred until a second model must compose against
   a contract.
3. The homoiconic form (operations as entities, ADR-7; components as schemas,
   ADR-10) is **machine-facing**. **For prototyping, authors write a textual
   format with schema validation**; the target surface is a **guided editor/UI**
   or an **NL-led** one — ADR-1's ladder, built later.

**Naming, reconciled.** The repo has accumulated *model, island, bundle, agent,
pattern*. This ADR fixes the base: **model** = the importable unit (components +
operations + namespace); **island** (ADR-6/D6) = a **terminology-indexed view**
over operations; **bundle / agent** (ADR-5) = a **shipped set of models** +
examples + knobs; **pattern** = a reusable hole-shaped operation or shape. *Model*
is the primitive; the rest are views or packages.

**Revises.** ADR-5 (a bundle is a shipped set of **models**), ADR-6 (a mode *is*
a model), ADR-9 (model = coordinate system + operations, now also the unit of
distribution).

**Open.** When and how a model **declares a dependence** on another (a versioned
import, or a declared interface only); whether composition is validated by a
held-out **joint** split (ADR-5's open, restated).

---

## ADR-13 — The control network is one pure evaluator; the trajectory is recorded

Status: **settled** (the contract; the algorithm is chosen by probe).

**Context.** D9 made the network **stigmergic rules** that write **opaque control
attributes** to the *world*, steering later applications. The note states a
stricter contract: *"The control network never alters the blackboard... It can
read the blackboard and it can read the candidate applications, so they must be
materialized somehow."* The discussion resolved what "materialized" and
"intermediate data" mean.

**Decision.**

1. The network is a **distinct evaluator artifact** the engine calls each step —
   **not** operations, **not** world-writing rules. It **reads** the blackboard
   and the **materialized candidates**, **writes nothing** to the world, may keep
   **private scratch**, and **returns a selection**: one application, or
   `exclude`. *(Confirmed in discussion: a distinct artifact, a pure evaluator.)*
2. **Candidates are materialized by the engine** before selection — every
   application whose guard holds. This **decides** `plan-scheduler.md`'s largest
   open ("does the engine materialise activations or a generic matcher rule?"):
   **the engine does**, which makes the engine **IR-native** (it must see
   bindings).
3. Candidates and scratch live in an **engine-side store**; the language does not
   see them. But the engine **records the selected application** (operation +
   binding + tick — **the selection only**) into an **application memory**
   component, which **is world data**. Because operations are entities
   (homoiconicity), that record is **queryable by the language** — so an ordinary
   operation can reason over the trajectory the network produced. (This is the
   "system-2" role the note sketches — it is *just operations*; it does **not**
   alter the network's decision, only the trajectory, through the world.)
4. The network **subsumes** D7's `RuleControl` and the scheduler's per-activation
   `argmax` — it is **the one selection point**. Those become special cases, or
   retire.
5. **Multi-step steering is entirely "which application fires next."** The
   network's only lever is selection; the chosen operation's effects shape the
   next step's candidates. D9's "one attribute-set steers the next application"
   is **gone**.
6. **Growth** is offline, over examples/scenarios evaluated automatically
   (ADR-4's frozen-judge tower), frozen before run. **First option: a decision
   tree / listwise scorer** that progressively scores and **eliminates bottom
   candidates** (the note's own phrasing). Compared later if the first does not
   earn it: **GP over a feature program** (extend `loopingrules_forge.evolve`),
   and **XCS-style accuracy credit** (D9's crux).

**What this revises in D9.** The stigmergic network is **replaced** by a pure
evaluator. D9's *searchability* (an opaque alphabet the generator mutates) is
kept but **relocated**: the alphabet is the network's own representation and
scratch, not the domain world. The consequence is the point —
`PRINCIPLES.md`'s *"the only channel between rules is the shared World"* is
**fully restored**: the network is not a set of world-writing rules but an
evaluator the engine calls. The one thing it emits *into* the world is the
**application record** (borrowed from the engine), for reflection. Cost, named:
D9's "shared split across subtrees" relied on control attributes being state read
by later applications; under this contract a split prunes the **candidate set**,
not the world, so sharing is a property of the *evaluation*, not of world state.

**Revises.** D9 (mechanism), ADR-9 §5 (the kernel now **calls** a network, and
the network is one evaluator, not a fixpoint of control rules).

**Open.** The network's **artifact interface** (what an evaluator is: a tree, a
program, weights) and whether it is grown per-domain or shared; **stability** —
a scorer whose scratch feeds its own next split can oscillate (D9's open,
unchanged); and whether `RuleControl`/`argmax` retire or stay as authored
special cases.

---

## A worked composite: the travelling trader

**The two islands, as they actually are.** `trip` speaks `stop`/`leg`/`frontier`/
`trip_request` and already projects onto `decide` (`occasion`=request,
`score`=-cost). `market` speaks `card`/`listing`/`offer`/`purse`/`policy` and
already projects onto `decide` (`occasion`=card, `score`=value-price) **and**
`judge` (`risk_level`). **Both expose the same interface** — a `decide`
projection and a `judge` projection. That is the oblivious-composition contract
(ADR-5's bridge), and it exists today.

**Intent.** "Make money: buy a card cheap in one city, carry it where it is
dear, sell." Coerces (ADR-3) into a `trade_intent` entity, not state.

**Two composition mechanisms — not one.**

| Composition | Mechanism | New? |
|---|---|---|
| **Value / choice** (which itinerary, which listing) | the `decide` bridge | no |
| **Trajectory / sequence** (when to move/buy/sell) | the **controller** (D9) | **yes — the "third agent"** |

**What the controller is.** Not a re-implementation of buy/sell/move; a
**router over activations** that:

- reads a **cross-island context** — `leg{destination,fare}`,
  `listing{card,price,city}`, `card{value,held}`, `purse{cash}`,
  `frontier{at,time,cost}` — exactly its derived `reads` (`analyze` gives it);
- writes **control attributes** (`route=arbitrage`, `phase=buy/carry/sell`);
- writes **`RuleControl`** to *select* which island rule may fire (e.g. disable
  `market.decide_buy` unless at the buy city) — locked 8: selects, never
  rewrites.

**The shared split.** One scoring rule: *card C is cheap here, dear there, and
`fare` < spread → `route=carry(C)`*. Every downstream move/buy/sell for C is
routed by it — one decision cuts a subtree — and its read set spans both islands
(the point).

**The trajectory** emerges one activation per tick: move → buy → move → sell →
profit.

**Why this is the right example: it has the anchor.** Mechanical ground truth =
**final cash** and **settles** (pure `checks`), so a controller *can* be trained
here (ADR-4's mechanical base exists). It is a D10-knowledge-maze in a real
domain: multi-step, cross-island, mechanical fitness.

**The seams it exposes.**

1. **Vocabulary collision** — `cards`/`market` each own a `purse`/`policy`;
   `trip` owns `stop`. The composite needs one trader and one city namespace →
   the bundle must **declare its interfaces** (ADR-5).
2. **Island rules fire unconditionally** — `market.decide_buy` buys whenever
   affordable; buying in the wrong city is wrong. The controller gates it with
   `RuleControl` — proof "select, never rewrite" suffices.
3. **`occasion` namespace collision** — both islands nominate onto
   `decide.occasion`; in one world they compete unless scoped. D9's "one
   namespace or scoped" resolves to **scoped**.
4. **Nonstationarity** — change the fares, the controller shifts → joint
   examples (ADR-5).
5. **Termination / cost** — needs a dominance bound on trader state
   `(city, cash, cargo, time)` (`trip.frontier`'s dominance generalized); the
   shared split is what prunes.

**Verdict.** A third agent with overarching scoring rules *is* needed — but it
is a **router over activations**, not an owner of the domain. The repo already
has both composition mechanisms (`decide` for value, D9 for trajectory); what is
missing is the controller and the declared interfaces.

---

## Candidate spikes (cheap, falsifiable)

- **S1 — coercion as rules, no LM.** One tiny domain (`trip`'s "book a taxi from
  Downtown to the Airport at 9"), a handful of hand-written meta-rules over
  token entities, producing typed instruction entities; existing domain rules
  carry instruction → state. Pin: deterministic, settles, and *abstains* on an
  unparseable sentence. (M3's coercion half, without the LM.)
- **S2 — calibrate the lexicon.** Kernel fixed; fit token → attribute constants
  from a few examples with `search`; held-out examples generalise; a wrong
  lexicon degrades. Pins *values-from-search* for parsing.
- **S3 — the disambiguation policy** *(built: `loopingrules_ux.s3`, pinned by
  `tests/test_ux_s3.py`)*. Two islands both write `want`; a controller picks one
  by context via `RuleControl`; growth finds the context-dependent
  `afford_first`, beating every fixed choice (held-out +210 vs +175 / +40).
  Finding: *which island* is a rule-level choice (`RuleControl`); *which deal*
  (S5) is a binding, needing control attributes. Pins *structure-from-generation*
  for the policy.
- **S4 — the LM as last-resort tool.** Only the residual, called through the
  tool convention, output coerced + round-trip-checked before entering the world.
- **S5 — the cross-island controller** *(built: `loopingrules_ux.s5`, pinned by
  `tests/test_ux_s5.py`)*. Two islands (route + trade) composed by a controller
  grown by searching a tiny policy space, reading a **cross-island context** and
  routing by **control attributes** (not `RuleControl` — per-deal selection is a
  binding, the scheduler doc's own point). Ground truth = final cash; grows
  `['spread>0', 'affordable']`, beats a do-nothing / always-trade policy, and
  generalises (train +70, held-out +95). Finding: the *literal*
  `examples.trip`/`examples.market` do not compose for a moving trader — U1 uses
  minimal islands of the same shape.

---

## Open decisions queued (not yet written)

10. ~~Is the schema declared, derived, or both?~~ **Answered (ADR-10): both** —
    declared components (model-qualified), cross-checked against derived use.
11. The **batteries**: the command schema + metarules, and where they live.
12. **Tools**: the convention, the render/parse manifest, the adapter stdlib.
    (ADR-11 fixes the *seam* — a deposited request answered between ticks — so
    this queued item is the adapters and the manifest, not the shape.)
13. Packaging details: how a model/bundle declares its **interfaces** (ADR-12
    says *none yet*), and how joint examples are represented.
