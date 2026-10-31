# D5 — The Forge: corpus to catalog

Turn a natural-language **corpus** into **components and rules** — verified,
frozen before use — behind a single **catalog** that also serves NL-in /
NL-out at run time. This is the structure-authoring layer the roadmap
deferred ("the closed catalog was built *for* a future search but none is
built yet"). It is **design only; nothing is built.** The package name
`loopingrules_forge` is provisional.

It rests on a scope change to the repo's own rules; read
[`PRINCIPLES.md`](../PRINCIPLES.md)'s new section, "What is machine-derived,
and at which layer," first.

## The pivot: one catalog, three surfaces

The catalog is not a build artifact. It is an **interlingua**: both NL
directions and the structured mode are renderings of it.

| Surface | Translation | When | Authority | Verified by |
|---|---|---|---|---|
| **Vertical** (authoring) | corpus NL ↔ **catalog** (schema + rules) | compile time | the corpus | fidelity + the four gates |
| **Horizontal** (use, structured) | world dump ↔ world dump | run time | the world | determinism (existing) |
| **Horizontal** (use, NL) | world dump ↔ NL | run time | the catalog | exact structured round-trip |

The vertical axis asks *what concepts exist*; the horizontal asks *what this
world holds*. They are different translations with different correctness
criteria (fidelity vs. grounding) and must not be merged into one
"translator."

**The rule that makes the pivot work: no NL→NL shortcut.** Every NL→NL request
goes `NL → ECR → (run) → ECR → NL`. If the two directions were independent
learned maps they would drift, and "one catalog backing both" would be lost.

## Components

New sibling package (`loopingrules_forge`), importing the engine the way
`loopingrules_calibration` does; the engine never imports it.

| Component | Responsibility | Builds on |
|---|---|---|
| **Corpus** | The authored spec: clauses + worked examples, **plus an append-only clarification layer**. Sole source of domain facts. | new |
| **Catalog** | The growing ECR artifact: components, connections, rules, bridges, knobs, provenance, presentation. **Derived facts regenerated from code; declared facts checked against derived.** | `analyze`, `surface` |
| **IR** | The target language: component specs + rule productions over the frozen operator set. The only thing the LM may emit. | new |
| **Translator** | LM front-end: corpus clause → IR fragment **+ the span it came from**. Proposes only. | LM + constrained decoding |
| **Emitter** | IR → Python (dataclasses, rule functions) and IR → catalog facts. | `ast` / `libcst` |
| **Introspector** | Wraps `analyze`/`component_map`/`literals` to *derive* facts from compiled code; validates declared against derived, refuses rather than guesses. | `analyze` **directly** |
| **Gates** | Four checks producing typed **Gaps**: shape, static, coverage, behavior. | `analyze`, `linter`, `calibration` |
| **Agenda** | Gaps → typed questions → routing → prioritisation. | new |
| **Tuner** | Fits knobs, detects plateaus, freezes. | `loopingrules_calibration` |
| **Channel / Renderer** | Run-time NL-in (a channel) and NL-out (a renderer). Edge only. | `engine`'s channel seam, `save` |
| **Ledger** | Provenance + reproducibility: catalog version, prompt/model/seed, clarification ids, span maps. | new |
| **Freezer** | Freeze a catalog version for calibration; publish new bridges to `patterns`. | `save`, `patterns` |

## The build loop

```
Corpus (clauses + examples) ─┐
                             ▼
                       Translator ──(retrieve bridges)──► IR
                             │                             │
                             ▼                             ▼
                         Catalog ◄── Emitter (IR→Python, IR→facts) ──┘
                             │
                             ▼
                       Introspector ──► derived facts
                             │
                             ▼
                          Gates ──► typed Gaps ──► Agenda ──► question
                                                             │
                                       ┌─────────────────────┼─────────────────┐
                                       ▼                     ▼                ▼
                                  re-translate         engine-derivable     human
                                 (widen spans)          (auto-close)   (clarification
                                       └─────────────────────┴──────────► appended to
                                                                          Corpus)
                                                             │
                                        loop until no blocking gap
                                                             ▼
                                                     Tuner (knobs) ──► Freezer
```

**The inversion, stated once: the engine generates the questions; the LM (or
the human) only answers.** Questions are computed from static analysis,
coverage and behaviour — all deterministic. The LM's job is narrower and
checkable than "author the domain."

## The Agenda

State: clauses `S` (each with a span id), catalog `K`, candidate `K'`,
clarification layer `Cl`.

```
build(corpus, model):
  S  = segment(corpus)                      # spans; structural or LM-assisted
  K  = seed(patterns)                       # bridges available for reuse
  loop:
    K'    = translate(S, Cl, K, model)      # clauses → IR, retrieve bridges first
    facts = introspect(emit(K'))            # reads/writes/components/literals
    gaps  = gates(K', facts, S, examples)
    if no BLOCKING gap: break
    q = agenda.select(gaps, K)              # prioritised
    a = agenda.route(q)
    Cl.append(a) if a is human else None    # answers are *corpus events*, not code edits
  return freeze(tune(K', examples)), report(gaps)
```

**Gap taxonomy** (each type is a question template):

| Pri | Gap | Question |
|---|---|---|
| P0 | unmapped clause | "Clause 12 has no artifact — out of scope, or missed by translation?" |
| P0 | read-without-writer | "Component X is read but nothing writes it — which condition produces it?" |
| P0 | shape violation | "This rule uses an undeclared component / unknown operator." |
| P0 | non-settling (`hot`) | "This catalog never settles within budget — which rule over-fires?" |
| P1 | ambiguity / bridge overlap | "'Risk' here — the existing bridge, or a new island-local component?" |
| P1 | behavioural ambiguity | "Both readings satisfy the corpus but diverge on example 3 — which is intended?" |
| P2 | literal-to-knob | "Range for `max_premium`? Knob, or structural constant (needs a lint excuse)?" |
| P3 | **expressiveness** | "The corpus says X but the IR cannot express it." — escalated, never auto-resolved |

**Routing — the provenance contract *is* the routing rule.** (1) Send the
question to the Translator with the full corpus; if it can answer **and cite a
span**, it is a translation fix, no human. (2) If no span exists but the
Introspector/analysis can close it, auto-close. (3) Else it is genuinely
under-specified: **ask the human, and append the answer to the clarification
layer** — never edit the code. The build is then a pure function of
`(corpus + clarifications + model/seed + retrieval policy)`: reproducible,
re-runnable, diffable.

**Prioritisation is MDL over the catalog.** `score(q) ≈ (blocking gaps it
closes) / (1 + new-structure cost)`, where new-structure cost counts the
components/bridges the answer would mint; **reusing an existing bridge costs
0.** This is `tuning.md`'s "favor acting from first principles" made a number.
Batch by subject: one component definition may close several gaps at once.

**Termination:** stop when no P0 gap remains. P1/P2 are reported; P3
(expressiveness) is always surfaced — it names a real gap in the *engine*, not
the LM. **Two channels:** LM questions batch; human questions are curated and
become the corpus's future test coverage.

## The catalog: derived, declared, presentation

Hand-maintenance drifts, so the catalog is split three ways:

- **Derived** (regenerated from compiled code, authoritative): components,
  fields, types, each rule's reads/writes, `component_map`, literals — out of
  `analyze`.
- **Declared** (authored, *checked against* derived): which `int` fields are
  **entity references** and to what; which components are **bridges**; knob
  scopes (already `@tunable`); descriptions.
- **Presentation** (edge only, retrieval/render, never consulted by rules):
  phrase patterns and render glosses attached to **components**.

Governing rule, the `Opaque`/`unlintable` posture applied to the catalog:
**derived beats declared; a contradiction is reported, never merged.**

**Connections** are the interesting declared part. The engine lowers entity
handles to plain ints (`concepts.md`), so at runtime the reference *type* is
lost; the catalog must declare edges `(component, field) → target component |
any`. This is *semi-derivable* — likely references can be inferred from which
ints flow into `w.get(e, Kind)` / `w.first(Kind)` during introspection — and
every declared edge no rule exercises is flagged.

**Values stay primitives.** There is no semantic value-type layer. A type
system over values *is* an ontology, and it would be a second semantic layer
that drifts from the component, the rules and the corpus, and that breaks the
primitives-only contract that makes `save`/`share` simple. Semantics lives in
the **component type** — its name, fields, existence, connections, and how
rules use it. One semantic atom = the component. Presentation (why `0.4`
renders as "40%") is derived where possible (rule usage via `literals` gives
the scale; the corpus gives the phrasing) and declared as prose only for the
rest.

## The IR and the DSL

| Layer | What | Why |
|---|---|---|
| **Surface** (optional) | small human-readable text DSL (`lark`) | for a human to read/repair |
| **Wire** | **JSON IR** under a JSON Schema | what the LM emits; the grammar the decoder enforces |
| **Backend** | **plain Python** (dataclasses + rule functions) | what the engine runs; what `analyze` reads |

The DSL is a **front-end; the Python rule is the backend.** This preserves
`analyze.py`'s own choice — *"AST analysis of plain Python, not a new DSL"* —
so the engine stays DSL-free, the dormancy gate and linter keep working, and
the constrained target lives purely on the generation side. "Grammar-directed"
then becomes literal: **grammar-constrained decoding** means the LM can only
emit well-formed IR, so syntax never fails and only semantics do.

The IR is a schema **with presentation metadata** (glosses), but no value
types. That is the one addition the run-time NL axis forces now; retrofitting
it later is painful.

## NL at the run-time edge

The horizontal NL axis lives at the **edges**, not in the engine:

- **NL→ECR at run time = an NL channel** (parses `Said` from text).
- **ECR→NL at run time = a renderer** the channel applies to `Reply`/state.

Neither belongs in the engine or the loop; the engine keeps "no domain, no
channel, no transport" and "no rule may block." The **structured mode is
already `save`/`share`** — load, run, dump — so the horizontal axis is mostly
assembly plus the renderer.

Two consequences:

- **The reverse direction is both the test and the feature.** `dump → NL →
  dump'` is an *exact* structured round-trip (cheap, no judge); `NL → ECR →
  NL'` is judged. The compile-time back-translation gate and the run-time
  explainer are the **same code**.
- **Explanations are grounded, not invented.** For "why," the substrate is the
  change log (`world.changes()`: which rule attached what, at which tick) —
  the causal story (`plan-memory.md`).
- **Run-time parse ambiguity abstains structurally:** spawn a question entity
  and let another rule answer (the `party.py` idiom). The run-time edge and
  the compile-time interview are the **same mechanism at two timescales.**

## Verification architecture (the spine)

The load-bearing question for a project this size is *not* "what do we build"
but "**how do we keep from diverging** when a wrong assumption in a core layer
would ripple outward." The plan answers with four devices and one rule.

**The rule: no layer is built on an untested assumption one level below.**
Prove the seam below before building above. Order the plan by **risk ×
centrality**, not by pipeline order.

**Four devices:**

1. **Assume-and-falsify, risk-first.** Each layer's load-bearing assumption is
   written as a claim *plus a cheap test that can fail*. A milestone is a
   probe, not a feature.
2. **Fitness functions in CI.** Architectural invariants that fail the build —
   the repo's existing posture (`lint(strict=True)`, `Opaque`, `signature`),
   extended to the new layers.
3. **Adversarial probes (mutation).** Every verifier gets a test that it
   **rejects** a deliberately-wrong input and **accepts** a right variant. *A
   check that cannot fail is not a check.*
4. **The concession ledger.** Any relaxation of a principle is declared with a
   reason and reported, never silent — the `allow=(...)` idiom, generalised.
   This is the specific antidote to *"a concession in a core layer ripples
   out"*: concessions become visible, diffable, reviewable.

Plus a **walking skeleton**: one tiny end-to-end path (corpus → compile →
freeze → tune → dump → render) kept green. If it breaks, the project has
diverged.

**The seam map** — each seam is a verification point with a named failure mode:

| Seam | Failure mode | Check |
|---|---|---|
| corpus → clauses | bad segmentation poisons everything | coverage: every clause maps to ≥1 artifact or is explicitly out-of-scope |
| clauses → IR | unfaithful translation | span provenance (every artifact cites a span; every span is covered) + round-trip |
| IR → Python | semantics changed in lowering | lowering round-trip + behavioural equivalence (`signature`) vs a hand-written reference |
| Python → catalog facts | catalog drifts from code | regenerate-and-diff fails the build on drift |
| catalog + corpus → Gates | gates too weak (accept wrong) or too strong (reject right) | mutation tests both ways |
| Gates → Agenda routing | asks the human what the corpus answers | routing accuracy on a labelled gap set |
| frozen catalog → Tuner | freeze ill-defined; tuning non-reproducible | replay determinism + signature/plateau stability |
| world dump ↔ NL | round-trip lossy in a way that breaks use | **exact** structured round-trip; judged NL round-trip |

**Spine invariants (CI fitness functions):**

- the engine imports nothing from the forge; the forge imports no domain;
  `calibration` imports no domain;
- **values are primitives only** — the catalog adds no type system;
- **no LLM call sits in the runtime core's decision path** — the LM appears
  only behind the Translator and the edge adapters;
- **every catalog artifact carries provenance** — an artifact with no span is
  an error, not a warning;
- the catalog is **derived-first**: a regenerate never contradicts the
  declared layer, or the build fails;
- **determinism**: replay twice, same `signature` (existing gate);
- **freeze**: a frozen catalog's signature and knob values reproduce;
- the frozen-operator and freeze-before-tune invariants hold even though the
  "tune values, never structure" scope is retired.

**Milestone gates** (risk-first; each is a falsifiable probe with a
kill/reshape criterion):

| M | Probe | Assumption it tests | If it fails |
|---|---|---|---|
| **M0** *(built)* | Derive the catalog for `cards` from `analyze` alone; hand-write its IR; lower back to Python; assert same `signature`. **No LM.** | the catalog is mostly derivable; the IR can express a real domain | if the IR needs arbitrary Python for `cards`, the DSL target is wrong — **reshape the IR before anything else** |
| **M1** *(built)* | Mutation-test the Gates: inject wrong rules (undeclared component, over-firing, non-settling, literal-for-knob, span-less artifact) → must reject; right variants → must accept | the gates catch wrong translation | strengthen the gates before building translation |
| **M2** *(built)* | Freeze M0's catalog; run the calibration kit; assert determinism + reproducibility + plateaus | freeze is well-defined; tuning against a frozen catalog reproduces | fix the freeze/version semantics |
| **M3** | A hand-written mini-corpus for one tiny domain → LM translate (constrained decoding) → Gates | NL→IR translation achieves useful fidelity | if hopeless even on a toy corpus, **translation is the wrong mechanism** — reconsider before scaling |
| **M4** | Renderer ECR→NL; **exact** structured round-trip; judged NL round-trip | the two directions are consistent via the pivot; the reverse is useful | drop the reverse direction or narrow it |
| **M5** | Run the Agenda on gaps; verify routing on a labelled gap set | questions are derivable; routing is correct | fix the gap taxonomy/routing |
| **M6** | `cards`/`market` with a real corpus; measure fidelity / derivability / reach | the whole pipeline scales to a real domain | the research result, either way |

**M0 result (probe built: `loopingrules_forge/m0.py`, pinned by
`tests/test_forge_m0.py`).** Both halves hold, and survived a reshape.
*Derivability:* `analyze` over `cards.RULES` returns **zero opaque** rules and
recovers all 18 component types with their readers/writers. *Expressiveness:*
**all 12** `cards` rules -- the tag family, `decide_buy`, `check_goal`, the
replies, **and the text front-ends** -- are expressed in a small IR, lowered
back to Python, and reproduce `cards`' `signature` **exactly** (same `fired`,
same settled snapshot, same replies) driven by real command lines through the
kit's `replay`. The reshape acted on three findings: (a) the term language
**grew to more Python shapes** (method calls, indexing, `len`, list literals),
and `_find_card` became an IR **helper** (same-module, still `analyze`-read;
reads match, so gating matches); (b) **lexing/formatting escaped to *verbatim*
helpers** -- `_parse_int` and `_status_text` embedded as raw Python, which is
the **concession ledger's first entry**, and note it is a concession only on
*generation*, never on *analysis* (they stay `analyze`-readable, so the catalog
still derives every read); (c) the IR **is a Python-subset AST**, not a new
language -- the emitter is near-trivial and the artifact stays plain,
`analyze`-readable Python. One finding is still open for the catalog layer: it
must fold in the **installer** and the **engine boundary**, or the "read but
never written" flags on `CardDef`/`Purse`/`RiskTolerance` (seeded) and `Said`
(in from a channel) and the "written but never read" on `Reply` (drained by the
engine) are noise.

**M1 result (probe built: `loopingrules_forge/m1.py`, pinned by
`tests/test_forge_m1.py`).** Six gates — **shape** (in `analyze`'s dialect,
catalog-declared components only), **coherence**, **tunability**
(`calibration.lint`), **provenance** (every artifact cites a span),
**determinism**, **behaviour** (settles + reference `signature`) — and eight
mutants, each of which trips its intended gate while the clean module and a
semantically-identical variant trip **nothing**. It also closes M0's open
finding: **coherence folds in the installer and the edge** (`CardDef`/
`RiskProfile`/`RiskTolerance` seeded, `Said` edge-in, `Reply` edge-out), so
"read but never written" fires only where it should. The concrete lesson that
generalises: **a gate accepts right structure and rejects wrong, and both
halves are tested** — a check that cannot fail is not a check.

**M2 result (probe built: `loopingrules_forge/m2.py`, pinned by
`tests/test_forge_m2.py`).** A `Frozen` (source + provenance + declared knobs
+ a `version` hash) is a well-defined artifact the calibration kit tunes
directly. Freezing is **deterministic**, and a structural change moves the
`version` while **no knob value does** — the separation the whole architecture
rests on: `version` = structure (frozen), `signature` = behaviour (chosen by
the knobs). Two independent freezes **reproduce**, and the frozen catalog
behaves **exactly** like the M0 catalog it came from. `calibrate` runs on it
unchanged and reports **plateaus** (e.g. 4 settings collapsing to one
trajectory) and sensitivity, exactly as it does for a hand-authored domain.
One thing it corrects: an artifact's *structure* is frozen, but its *declared
knob surface* is part of the freeze too — you tune a frozen catalog, you do
not re-emit it.

M0–M2 need **no LM at all** and are cheap: they de-risk the structural half
before the model ever appears. Only M3 introduces the LM, and only after the
substrate is proven. That ordering *is* the anti-rabbit-hole device.

## What this reuses

- **Grammar-constrained decoding** — `llama.cpp` GBNF, `outlines`,
  `llguidance`, `lm-format-enforcer` — the concrete realisation of
  "grammar-directed"; ideal for a small local model.
- **Backend codegen** — stdlib `ast` + `libcst`.
- **Introspection** — `analyze` **as-is**; do not reinvent.
- **Tuning** — `loopingrules_calibration` **as-is**.
- **Catalog validation** — JSON Schema / `pydantic`; plain, portable, diffable.
- **The decidable slice** — the monotone rules (tags derived from queries, no
  retract/destroy) are **stratified Datalog**, which provably terminates; use
  `souffle`/`scallop`/`egglog` as a **checker/model, never the runtime**.
- **Bounded search/consistency** — `z3` / `OR-Tools`, *bounded* only.
- **Provenance** — W3C PROV *ideas*, in a simple ledger.

**Avoid as the internal representation:** OWL/RDF — yet its *discipline*
(typed relations, shapes, derivation) is borrowed. The mismatches are
structural: open-world vs closed-world; monotone description logic vs
`attach`/`detach`/`destroy` (a tag is a *fluent*, not a class membership);
global triples vs entity-attached components. Keep the catalog in a
self-owned plain format (JSON + schema) and treat any ontology formalism as an
**export target or checker**, never the source of truth.

## What this does not settle

- **Clause granularity** — the unit of meaning (sentence? paragraph? example?).
  Bad segmentation is the silent input to everything downstream.
- **Whether to restrict a subset of rules to monotone Datalog** for guaranteed
  settling — a large, tempting decision that buys decidability for the tame
  slice and costs expressiveness.
- **Textual surface DSL vs JSON-only.**
- **One-question-at-a-time vs batched**, and the human/LM channel split.
- **How much of the connection schema is derivable** vs must be declared.
- **Freeze/version semantics** — what "a catalog version" is, and how it rolls
  back.
- **The package name.**

## Open questions

1. Does the vertical axis need NL-out as a *deliverable* (domain documentation
   rendered from the compiled catalog), or is that only the forge's internal
   back-translation test?
2. At run time, is an output text-with-structured-payload, or is the NL channel
   *optional* so pure structured mode bypasses NL entirely?
3. Is the LM used as a round-trip *judge* (a third learned surface), or is
   span attribution enough?
4. Where does the concession ledger live — the Ledger, or `lint`?
