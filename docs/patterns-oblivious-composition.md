# Patterns for oblivious composition: a vocabulary-only hub and keyed reads

Status: **one design note, one probe now built.** The note is the D6 question
half-asked — *how can two models compose when neither names the other?* — and its
answer is narrow and checkable. §7's A/B is **built** (`loopingrules_linda`, a
spike, pinned by `tests/test_linda_ab.py`); the rest is design. It extends D6
(`archived-old/plan-islands.md`: island / bridge / role / convergence) and
ADR-10/11/12; `docs/plan-scale-probe.md` is where the claim is *measured*.

It also corrects two overclaims made while finding this shape, kept visible on
purpose: "islands that compose obliviously" (too broad — see §1) and "the neutral
hub and the frozen judge coincide" (a conflation of two different meanings of
*checks* — see §8).

## 1. The question, and what was wrong with the first answer

Take three models — a **trip** model (T), a **planning** model (P), a **budget**
model (B) — composed so that T⊥B: **T knows nothing about B and B knows nothing
about T**, yet they still compose. Can that be true, and can we check it?

The naive answer — "islands compose obliviously" — is **too broad**, because:

- a rule that reads two models' namespaces *is authored* (ADR-9 §3: *"cross-model
  operations are authored, because their existence is a human claim that two
  imperfect models interact"*); and
- the "oblivious" part is **relative**: in a T→P→B chain, P names both, so P is a
  *mediator* (D6's **conjunction**), and the composition is authored — amortized
  onto P, not free.

The defensible claim is narrower:

> Composition is **amortized, not free**. The recurring authored unit is
> per-**interface**, not per-**pair**. Add a model that already speaks a shared
> interface → it composes with zero edits to the others.

## 2. Obliviousness is a *direction*, not a generality

Neutrality is a property of **who may name whom**, and ADR-10's model-qualified
names make it mechanical:

> **Oblivious-composition invariant (OCI).** For every pair of models `m ≠ n`,
> `models(all rules of m) ∩ namespace(n) = ∅` — equivalently, each model's derived
> model-span ⊆ `{itself} ∪ neutral`.

A hub may be named by T, P, and B; the hub must name **none** of them. Then every
pairwise span meets in `{hub}` or `∅`. That is exactly "T, P, B reference its
components; P need not know T and B," stated as something a checker can decide.

`models` is ADR-9 §2's *derived* projection — and it is **not built**: `analyze`
derives `reads`/`writes` today, not the model-span. Deriving it is the first
increment this note asks for.

## 3. The hub is vocabulary, not a module

ADR-12 §1 already permits it: *"a model can contain components, operations, both
or some of them."* So the hub is a **components-only model** — a shared
vocabulary — and it **produces nothing**. The meeting is two rules touching the
same entity, and *"the only channel between rules is what gets deposited into the
World"* (ADR-4): there is no broker, no dispatcher, no delivery, no topics.

The consequence worth stating plainly: **if the hub has no operations, then the
hub collapses into "a shared vocabulary + the World."** The meeting place *is* the
blackboard. That is the deepest form of this shape — there is no hub module, only
a vocabulary and the one channel that already exists.

**Who writes a verdict, then?** A *rule*, and it is one of two kinds:

| kind | model-span | nature |
|---|---|---|
| **domain-owned** | `{own, hub}` | a D6 **conjunction** — authored, and honestly so |
| **neutral** | `{hub}` | a generic checker over the vocabulary's own keys (`constraint.kind`) |

Both leave the hub inert; neither breaks OCI.

## 4. Keyed reads — the load-bearing move

A hub answer is a **keyed relation**, not a typed value:

- a writer attaches `hub.response` **to an entity** (the candidate);
- a **domain-owned reader** binds `hub.response` **+ its own component on that same
  entity** — `each("response", "budget.plan")`.

So the *semantics never live in the hub*; they live at the **read site**, supplied
by the reader's own key. One generic `response` is read differently by budget,
planning, and trip, each through its own join; the hub never needs per-domain
typing, and the vocabulary does not collapse. The **entity is the meeting point**
(it carries `hub.response` + `domain.component` together), which is the earlier
"a component from one model lets another pick up."

**Requirement this introduces — join-key alignment.** The response must sit on (or
reference) an entity that carries the reader's own component. If the candidate is a
`leg` and the reader's component is on a `plan`, the reader needs a reference hop
(refs are primitives, ADR-10 §5) — doable, but a real constraint on the seam.

## 5. The pattern catalog

Each pattern states its invariant as **what each side may name** — that is the
checkable part.

| # | Pattern | Shape | Invariant (allowed names) | Pinned by |
|---|---|---|---|---|
| **1** | **Projection / convergence** | a domain writes a shared thin shape; one reader over it decides | domain: `{own, shape}`; reader: `{shape}` | `i0.propose_cards` + `items.consider`; `judge`; `decide` |
| **2** | **Marker hand-off** (stigmergy proper) | A deposits a marker; B's guard fires on it | marker is shared; B reads the marker, not A | `patterns.LoopCount` → `constraints.max_loops` |
| **3** | **Request/answer over an opaque capability** | requester writes `Request{capability}`; a responder consumes and answers | requester: `{own, capability}`; responder: `{own, capability}`; a registry holds the pairing | `circuits.Call` / `ToolRequest` / `compile_answerer`; ADR-11 §3 |
| **4** | **Role conferral** (entity as join key) | an island confers a `Role` on an entity; any rule over `Role` is live | role is shared; the entity is the join; no rule names the conferrer | `items.consider`; `funds.spendable` |
| **5** | **Projected scalar + neutral policy** | a domain projects a scalar; a neutral chooser ranks | chooser: `{scalar, policy}`; domain: `{own, scalar}` | `patterns.judge`; `decide` |
| **6** | **Shared-vocabulary meeting place** | a *components-only* model (the vocabulary) + the World (the meeting place); entity-keyed reads joined against the reader's own vocabulary; **no hub operations** | hub: `{hub}`; each writer/reader: `{own, hub}` | **design** — §3–§4 |

Pattern 6 is the neutral hub in its clean form: **one vocabulary bridges
arbitrarily many models**, each authoring only its own projection and its own
keyed reads.

## 6. Why keyed reads beat pub/sub — scoped

| coordination | how the reader selects | what it costs |
|---|---|---|
| **Topic pub/sub** | subscribe to a topic | to reach a *specific* answerer you author a **special topic** → couples publisher→topic; the mediator returns |
| **Content-based pub/sub** | filter on message fields | the reader must read the **publisher's message schema** → *peeking* → couples reader→publisher |
| **Keyed meet** | bind `hub.response` **+** `own.component` on a shared entity | nothing: the filter **is** the reader's own state; the publisher's vocabulary is never read; no topic is authored |

The keyed join routes **without a special topic** and **without peeking**, because
the routing key is the reader's *own* component, not the sender's address or
payload. Plain pub/sub has neither; to fake it you add a topic registry (couples)
or content peeking (couples).

**Prior art, stated so the claim is not overstated.** This is a **blackboard**
(Hearsay‑II) and, more exactly, a **tuple space** (Linda's `out`/`rd`/`in` —
"generative communication," reads matched by template). The substrate's version
adds that the template **joins the reader's private vocabulary on a shared key**,
with model-qualified names so that reading the publisher is *structurally
impossible*. The advantage is at the **coordination/decoupling** level only — it is
not a claim over pub/sub's operational properties (delivery, distribution,
backpressure, fan-out at scale).

## 7. Is the advantage real? — the Linda check

§6 named the prior art — a **tuple space** (Linda's `out`/`rd`/`in`, "generative
communication") — and claimed an advantage. That claim needs a check, and it needs
one narrowing first:

> "The substrate overcomes Linda" is **not a proposition**. Linda is
> Turing-complete; any coordination can be emulated with a tag field and extra
> `rd`s. Nothing can "overcome" it in expressiveness.

What *is* checkable is whether the substrate's **match primitive** has properties
Linda's does not, and whether they survive a *fair* encoding. Linda's match is a
**single positive positional tuple**; the substrate's is a **conjunctive,
name-keyed query with negation** over an entity. Four axes:

| # | axis | substrate | Linda (basic) | honest status |
|---|---|---|---|---|
| **M1** | **layout decoupling** | a reader names `verdict`; the writer may add components freely | a template fixes arity + positions → adding a field **breaks** the reader | **structural** — named vs positional |
| **M2** | **negation / conjunction, one match** | `each("candidate", without="item")`; `each("verdict","ok")` + `has("alpha")` | one template = one tuple; a cross-tuple join or an absence test needs several `rd`s, and absence needs the non-blocking `rdp`/`inp` probe | **real but emulable** |
| **M3** | **derived obliviousness** | `analyze` derives the read-set → OCI is **decidable** | the template *is* explicit, but positional; with a tag convention obliviousness re-appears | **partly a wash** |
| **M4** | **blocking vs reactive** | rules re-evaluate to a fixpoint; nothing blocks | `rd`/`in` **block** until a match; the consumer must be driven | **a model difference, not a power one** |

### The A/B

Cheap, in the repo's spike idiom — `loopingrules_linda` (a **spike**: absent from
`pyproject.toml`'s `packages=`, pinned by a test, like `loopingrules_islands` and
`loopingrules_forge`):

- **Instrument A** — the substrate: `world`/`loop`, one hub writer (`evaluate`) and
  domain readers (`alpha`, `beta`) joining a shared `verdict` with their **own**
  component.
- **Instrument B** — `loopingrules_linda.linda`, a minimal faithful tuple space
  (`out`/`rd`/`in`, typed formals, plus the non-blocking `rdp`/`inp` probes), the
  *same* coordination.
- **Fairness concession:** B may use a **tag-field convention** (a fixed-arity keyed
  tuple). Comparing A to *B-naive* would be a straw man; the real question is A vs
  *B-conventioned*.

`ab.py` measures:

| test | measure | pre-registered prediction |
|---|---|---|
| **M1** | writer adds a field; does the reader still match? | A: unchanged; B-naive: **0 matches**; B-conventioned: unchanged |
| **M2** | express `without=` / a conjunction | A: one match; B: a scan + a probe per candidate |
| **M3** | derive the reader's read-set | A: `analyze` → named slots; B: the literal templates (positional) |
| **M4** | does anything block? | A: settles with no blocking; B: `rd` raises `Blocked` |

**Pre-registered verdict:** A wins **M1** and **M2**; **M3** is a wash (both
explicit — A's by name, B's by position); **M4** is a model difference, not a power
one. So the defensible claim is **narrower than §6 implies**: the advantage is
**named-component matching decoupled from layout** plus **negation in the match** —
an advantage over *positional* templates, which a tag convention largely erases for
M3 (and may erase for M2 as well; that is why the A/B is run rather than asserted).

**Prior art.** Blackboard vs tuple space — both *shared associative dataspace*
coordination models — is studied ground (Gelernter & Carriero on generative
communication; Papadopoulos & Arbab's survey of coordination models). The substrate
is a blackboard with **named, scoped, declared** components and **derived analysis**
on top; that is the defensible positioning.

**Probe status: built.** `loopingrules_linda` (a spike) + `tests/test_linda_ab.py`
are this A/B, and all four measurements came back as pre-registered:

| axis | measured |
|---|---|
| **M1** | the substrate reader is **unchanged** when the writer adds `verdict.reason`; the naive Linda template matches **nothing** (`[]`), the tag convention restores it (`['a','c']`) |
| **M2** | one `each("candidate", "worth", without="item")` vs **6 calls** (a scan + a probe) for 3 candidates, same outcome |
| **M3** | the reader's read-set is **derived** — `{('verdict','ok'), ('alpha',None)}` (the shared shape *and* its own component) |
| **M4** | the substrate settles with no blocking; Linda's `rd` raises `Blocked` |

So the residual is exactly the pre-registered one: the advantage is **named-component
matching (M1)** and **negation in the match (M2)**; M3 and M4 are concessions. The
doc's §6 wording ("an advantage at the coordination/decoupling level only") is what
this supports — not "overcomes Linda."

## 8. The worked hub: business constraints

"Constraint checking" here means a **business** check ("is this within budget") —
**not** the repo's `checks` (`loopingrules_calibration`, ADR-4's *mechanical base
judge*), which is the training objective. The two are orthogonal: the business hub
is a domain like any other, and it may *optionally* be scored by `checks`. (This is
the conflation corrected at the top.)

```
constraint hub (components only; models(hub) = {hub})
  components:  Constraint{kind, limit, scope}, Candidate{...}, Response{candidate, ok}

trip:      projects legs/stops into hub Candidate/Constraint   # names {trip, hub}
planning:  reads hub Candidates, builds plans, writes Candidate # names {planning, hub}
budget:    writes hub Constraint{kind="budget", limit=...}      # names {budget, hub}
           (or: a neutral rule over Constraint{kind} writes Response)
```

P never names `trip.*`; budget never names `planning.*` or `trip.*`; the hub names
none of them. Composition happens because budget's `Constraint` *and* trip's legs
*and* planning's `Candidate`s land in the same vocabulary, and the domains' keyed
reads close the loop — nobody having called anyone.

## 9. The check (four levels)

| level | assertion | instrument |
|---|---|---|
| **static** | `models(hub) = {hub}`; pairwise spans meet only in `{hub}` | `analyze.models` — **to build** (ADR-9 §2) |
| **dynamic** | a rule wrote only on entities projected into the hub | `i0.reach` / `confers_only_on_projected` |
| **negative** | a rule that scans the world (reads `trip.*` directly) must **fail** reach | `i0`'s `fabricating_consider` mutant |
| **held-out** | a 4th model speaks the hub; T/P/B **byte-identical**; new use cases appear | fan-out per interface (`plan-scale-probe.md` §5.5) |

The negative row pins the question exactly: *"does P know T?"* becomes *"does any
rule read a slot outside `{own, hub}`?"* — and an accidentally-leaky hub is caught
the way `fabricating_consider` is.

## 10. Anti-patterns

From D6, plus two this shape adds:

1. **Fabricating candidates** — an island scans the world instead of waiting for
   projections; reach becomes unbounded. (`i0` claim 6.)
2. **Unbounded reads** — reading the whole world / the log unfiltered.
3. **Confinement everywhere** — every rule reads only its own model; no bug, but
   no stigmergy; the *default* unless a shared shape and a projection exist.
4. **Spooky coupling** — X and Y coupled through a Z invisible from either side;
   the strongest argument that a **derived cross-model read graph** is
   load-bearing. Not built.
5. **Hidden mediator** — a "neutral" model that actually names both sides (the
   T→P→B scenario as first stated). Amortized authoring, not an oblivious bridge.
6. **Over-broad *operations*** — the vocabulary may be shared and generic;
   collapse comes only if the hub's *operations* are domain-specific. With a
   vocabulary-only hub (no operations) this cannot arise.

## What this does not settle

- **`analyze.models` is not built** — the static check cannot run yet.
- **Expressiveness** — can T, P, and B each express their contribution in the hub
  vocabulary without naming their own domain? If one cannot, the hub fails for
  that model and the mediator returns.
- **Whether the Linda advantage survives a fair encoding** (§7) — the A/B in
  `loopingrules_linda` answers this; the predicted residual is named-component
  matching (M1) and negation (M2), with M3/M4 conceded.
- **Where the verdict-writer lives** — domain-owned (conjunction) vs neutral
  (`{hub}`); the hub stays inert either way, but the amortization differs.
- **Vocabulary breadth** — how generic a shared shape can be before every domain
  projects different semantics onto it (D6's *overlapping bridges*).
- **Monotone vs revisable** — a revisable `Response` is what lets a controller
  move the decision online, and is where flicker lives (D6's open).
- **Scale** — whether fan-out per interface is actually superlinear; that is
  `plan-scale-probe.md`'s axis B, not this note's.

## Open questions

1. Does `models` count a *neutral* model's own span as `{hub}`, and is the hub
   declared or derived (ADR-10's "both")?
2. Is a components-only model the right artifact for the hub, or does the library
   (U3) want the vocabulary to be an *island* with its readers?
3. Does the response need a `kind` at all, or is the reader's own component
   sufficient to disambiguate — i.e. is the hub even more inert than §7 draws it?
4. Should join-key alignment be enforced (a declared reference the reader can key
   on) or left to the author, with a gap when it is missing?
5. Does the derived cross-model read graph (anti-pattern 4) become a shipped
   artifact, and does it live beside `analyze` or in the catalog?
