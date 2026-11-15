# Handoff: the design after the correction pass (ADR-10…13)

Status: **a working handoff**, written so the next session can pick up without
re-reading everything. It points at the docs rather than restating them. The two
steering inputs it grew out of (`ux.md`, and the later `components and control
network.md`) are retired to `archived-old/`.

## 1. Where we are

`main` carries the **attribute-substrate port** (Phase S, `plan-attributes.md`)
and **Plan U** with its first two probes. Then a **steering note** — `components
and control network.md` — forced a **correction pass**, **ADR-10…ADR-13**, over
the substrate and the control network. It was **discussed before it was written**:
the note mixed the operation *language* with *engine seams*, and each claim was
sorted into language / seam / open **before** anything landed in the docs.

- **Tests: 424 pass, with 6 collection errors** — all the unported
  `loopingrules_forge` spike and `loopingrules_reflect.r1`. That is the one red
  piece, deliberately deferred (see §4).
- **The correction pass has a per-step walking skeleton**: `loopingrules_ux.s6`
  (15 tests) — the train trip with a budget, in **three** models (train,
  planning, budget), pinning ADR-13's deepest claim on the *current* substrate:
  **multi-step steering is "which application fires next."** Each step
  materializes the candidate moves, the budget excludes the unaffordable, a
  distinct pure scorer selects one and writes nothing, the train model applies
  it, and the selection is recorded — so the trajectory is a sequence. Grown
  network `+1*lookahead`, generalising (train `+34`, held-out `+38`, = oracle).
- **Docs** (the "clean slate"): the guide, plus **`decisions.md`** (ADR-1…ADR-13,
  the reasoning) and **`plan-ux.md`** (Plan U, the roadmap). Everything else — the
  D1–D10 design docs, `tuning`, the study guide/plan, `modeling`, `comparison-soar`,
  and the notes that started this (`ux.md`, `components and control network.md`,
  `changes-to-perform.md`, `review.md`, `learn to reconstruct.md`) — is kept for
  provenance under **`archived-old/`**.

## 2. The correction pass, in one paragraph

> **Components return** as **declared, model-qualified bags** of fields on
> entities (`entity → {component → {field}}`; one per name, lists for many; only
> entities have identity). A **model is an importable module** of components and
> **operations**. The operation language is minimal — `if`, no `while`, iteration
> as stigmergic re-firing — and **tools are an engine seam**, a deposited request
> answered between ticks, not a language operator. The **control network is a
> pure evaluator**: the engine **materializes** the candidate applications, the
> network selects one and **writes nothing**, and the engine records the
> selection into **application memory** for reflection. It **subsumes** both
> `RuleControl` and the scheduler's `argmax`.

Everything still hangs off ADR-1…ADR-9; the correction pass turns three of their
"someday" questions into decisions and **reverses two of D8/D9's**.

## 3. What changed, and what it costs

| ADR | Change | Cost |
|---|---|---|
| **10** | Components = declared, model-qualified **bags** (D8's "component is a referenced entity" is reversed) | reopens the shipped substrate — **another clean break of Phase-S size** |
| **11** | rule → **operation** + **application**; tools an engine **seam**, not an operator | a concept rename; the code rename waits for the kernel fold |
| **12** | a **model** is an importable module; **everything visible**; textual format now, UI/NL later | none yet (interfaces deferred) |
| **13** | the network is a **pure evaluator**; candidates materialized; the **application memory**; it subsumes `RuleControl`/`argmax` | the engine becomes **IR-native** (it must see bindings); D9's stigmergic sharing is relocated |

## 4. Known red / stale (named, not hidden)

- **The forge is red** (6 collection errors): `loopingrules_forge/m0.py` still
  imports retired classes. Under ADR-7 the forge IR becomes the engine's rule
  form, so retargeting it is a *larger* job, deferred.
- **The guide is stale by design** — and now doubly: it describes the old
  **typed-component** substrate, and ADR-10 brings components back but as
  **bags**, not classes. `concepts.md`, `architecture.md`, `analysis.md`,
  `index.md`, `writing-rules.md`, `README.md` (root) and `mkdocs.yml`'s
  `site_description` all need reconciling. This is **U0** — a named task.
- **`TODO.md`** (root) and **`README.md`'s History** carry the pre-UX open
  threads; they have not been reconciled to Plan U or the correction pass.

## 5. Next (recommended, not started)

1. **Grow the skeleton (S6 → U8)** — add the third model (the train-trip graph),
   more planners, and a **listwise** scorer in place of the two-leaf tree; it is
   cheap and it teaches the shape the clean breaks must serve.
2. **U0** — reconcile the prose (the guide, `mkdocs.yml`) with what the code
   does: attributes *with declared, model-qualified components*.
3. **The components clean break (ADR-10)** — `world` → `analyze` → `save`/`share`
   → `reflect`/IR → `examples`, in the clean-break order D8 gave, done whole, and
   migrate `s6` onto it. The largest single piece of work now open; do it once
   the skeleton has settled the shape.

## 6. Pointers

- `docs/plan-ux.md` — Plan U: thesis, phases U0–U8, probes, invariants, open
  questions.
- `docs/decisions.md` — ADR-1…ADR-13, with rationale and what each revises
  (ADR-10…ADR-13 are the correction pass).
- `loopingrules_ux/s5.py`, `s3.py` and `tests/test_ux_s5.py`, `test_ux_s3.py` —
  the two probes.
- `docs/archived-old/` — the design forest this direction grew out of and
  revises (D5–D10, `plan-scheduler`, `plan-attributes`, `modeling`, the steering
  notes, …).
- `git log` — the commit messages carry the reasoning, as usual here.
