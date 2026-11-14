# Handoff: Plan U, and its first two probes

Status: **a working handoff**, written so the next session can pick up without
re-reading everything. It points at the docs rather than restating them. The
steering input it grew out of (`ux.md`) is retired to `archived-old/`.

## 1. Where we are

`main` now carries **two things**: the **attribute-substrate port** (Phase S,
`plan-attributes.md`) and **Plan U** (the user experience) with its first two
probes. The port was a clean break: the engine is re-founded on
**entity + attribute** (a value a scalar, an entity reference, or a flat list; a
"component" a tagged entity; no Python class) and every layer above is
retargeted onto attribute **names**.

- **Tests: 409 pass, with 6 collection errors** — all of them the unported
  `loopingrules_forge` spike and `loopingrules_reflect.r1`. That is the one red
  piece, and it is deliberately deferred (see §6).
- **Docs** (this is the "clean slate"): the guide, plus **`decisions.md`**
  (ADR-1…ADR-8, the reasoning) and **`plan-ux.md`** (Plan U, the roadmap). Every
  other doc — the D1–D10 design docs, `tuning`, the study guide/plan, `modeling`,
  `comparison-soar`, and the notes that started this (`ux.md`,
  `changes-to-perform.md`, `review.md`, `learn to reconstruct.md`) — is kept for
  provenance under **`archived-old/`**.

## 2. What Plan U is, in one paragraph

> The engine is a tiny **fixpoint** kernel; the substance is a **library of
> islands** (clusters of rules keyed by terminology); structured input
> **anchors** onto islands; and a **grown control network** resolves the
> **ambiguities** (non-confluence) a person cannot feasibly rule by hand.

Everything is entities, so there is no separate authoring pipeline. A term's
definers decide what is needed: **none** → a gap (ask, never induce); **one or
confluent** → a **fixpoint** (plain rule execution); **several, non-confluent** →
the **control network** resolves it. That last case is the entire reason the
growth algorithm exists. See `plan-ux.md` §1 and `decisions.md` ADR-1…ADR-8.

## 3. The two probes, and what they settled

`loopingrules_ux/` (a spike package, **not** in `pyproject.toml`'s `packages=`):

- **S5 — the walking skeleton** (`s5.py`, `tests/test_ux_s5.py`). A **grown
  controller** composes two islands (a `route` island and a `trade` island) into
  a multi-step trajectory, scored by a **mechanical** example (final cash). It
  grows `['spread>0', 'affordable']`, beating a do-nothing and an always-trade
  policy and generalising (train +70, **held-out +95**).
- **S3 — the ambiguity probe** (`s3.py`, `tests/test_ux_s3.py`). **Two** chooser
  islands both write `want` (a real conflict); a controller picks one per tick by
  context. It grows the context-dependent **`afford_first`**, beating every fixed
  choice (**held-out +210** vs +175 / +40).

**The finding that matters:** the two probes pin the design's *grain*.

| the choice | unit | mechanism |
|---|---|---|
| **which island** (S3) | a **rule** | `RuleControl` (rule-level on/off) |
| **which deal** (S5) | a **binding** | **control attributes** (and, later, IR-native activations) |

Both are "the network **selects**, never rewrites" (locked 8). S3 is the one
that justifies growth at all: two islands handling one term is exactly the
ambiguity that no hand-written control rule can cover.

## 4. What the probes changed in the plan

- **The forge is reframed, not merely deferred.** Under ADR-7 the forge **IR
  becomes the engine's rule form** (a rule is a production made of entities), so
  the forge is the *authoring/generation surface over* that datum, not a spike to
  finish first. That is why finishing it is no longer Track A.
- **Locked 8 refined** (an LM may be a **tool at the edge**, coerced + verified)
  and **locked 11 split** (concepts declared; wiring/conditions **grown**; values
  fit). See `plan-ux.md` §2.

## 5. What is *not* done in U3

U3's probes are half-built: **S3 landed**; the **terminology index** and the
**shipped islands** (evaluation/ranking, scoping, procedure-following, graph) are
still to build, as is **S2** (calibrate a lexicon; check it generalises). The
natural next increment is the **bundle + terminology-index convention with one
real island reused across two domains** — the D6 reuse bar — because that is what
turns S5/S3's stand-in islands into the library everything else indexes into.

## 6. Known red / stale (named, not hidden)

- **The forge is red** (6 collection errors): `loopingrules_forge/m0.py` still
  imports the retired `Reply`/`Said` **classes** from `loopingrules.engine`, and
  its IR still takes component classes. Retargeting it is now a *larger* job
  (ADR-7): the engine grows a term interpreter, and the forge keeps the surface
  and the generator. Until then the heavy/pinned suites in `loopingrules_forge/`
  and `tests/test_reflect_r1.py` do not collect.
- **The guide is stale by design.** `concepts.md`, `architecture.md`,
  `analysis.md`, `index.md`, `writing-rules.md` and `README.md` (root) still
  describe **components**; the code is **attributes**. `mkdocs.yml`'s
  `site_description` says "entity-component" too. Reconciling this is **U0** —
  a named task, not silent drift.
- **`TODO.md`** (root) and **`README.md`'s History** carry the pre-UX open
  threads; they have not been reconciled to Plan U.

## 7. Pointers

- `docs/plan-ux.md` — Plan U: thesis, phases U0–U7, probes, invariants, open
  questions.
- `docs/decisions.md` — ADR-1…ADR-8, with rationale and what each revises.
- `loopingrules_ux/s5.py`, `s3.py` and `tests/test_ux_s5.py`, `test_ux_s3.py` —
  the two probes.
- `docs/archived-old/` — the design forest this direction grew out of and
  revises (D5–D10, `plan-scheduler`, `plan-attributes`, `modeling`, …).
- `git log` — the commit messages carry the reasoning, as usual here.
