# Handoff: the component-substrate break (ADR-10), in progress

Status: **a working handoff**, written so the next session can pick up without
re-reading everything. It points at the docs rather than restating them. The
steering inputs it grew out of (`ux.md`, `components and control network.md`) are
retired to `archived-old/`.

## 1. Where we are

`plan-u` carries **two things now**: **Plan U** (the design — `decisions.md`
ADR-1…ADR-13, `plan-ux.md`) and an **in-progress substrate clean break**
(**ADR-10**), re-founding the engine on `entity → {component → {field → value}}`.

- The **design pass** (ADR-10…13) and the **per-step probe** (`loopingrules_ux.s6`)
  landed first and were green (424). The **break** is mid-flight.
- **Tests: 136 pass** — but *only across the PORTED core*. `loopingrules_calibration`
  (except `kit`/`surface`), `loopingrules_patterns`, `loopingrules_islands`,
  `loopingrules_ux`, the five kept examples, and their tests are **unported and
  red**. This is a **staged clean break, committed per layer**, the way Phase S
  was — the full suite returns to green only at the end.
- The break was done on the branch `components-substrate` and **fast-forwarded
  into `plan-u`**, which is pushed. There is no separate open branch.

## 2. The break, stage by stage

| stage | what | state |
|---|---|---|
| **1** | `world.py` (two-level store) + `schema.py` (declarations) | **done** |
| **2** | `analyze.py` — reads/writes are `(component, field)` **slots** | **done** |
| **3** | `save` (now **version 4**) / `share` / `reflect` / `memory` | **done** |
| **4** | `engine.py`; **`loop.py` needed no change** (its gate is `populated(*slots)`) | **done** |
| **5a** | `calibration` `kit` + `surface` (a `Knob` names a **slot**) | **done** |
| **5b** | `calibration` `checks` / `adapt` / `linter` / `report` | TODO |
| **5c** | `patterns` (`judge` / `memory`) | TODO |
| **6** | examples — `decide`, `cards`, `shopping`, `market`, `trip` | TODO |
| **6b** | `loopingrules_reflect/r0` | TODO |
| **6c** | the tests for all of the above | TODO |

## 3. What the break changed, in one paragraph

A **component** is a declared, model-qualified **bag of fields** on an entity
(at most one of each name; at most one field of each name; multiplicity is a flat
list inside a field). A **tag** is a fieldless component. Only entities have
identity. `save` is **version 4** (3 was the flat attribute set); `refs` is a set
of `(component, field)` **slots**; a `RuleCard`'s `reads`/`writes` are flat lists
of **slot strings** (`"trader.cash"`, `"done"`), via `schema.slot_str`/
`parse_slot` (the store cannot hold a tuple); a promoted memory's `types` are
component names. `schema.py` holds the **declared** half (components, fields,
`Gap` on an undeclared name) — the store does not enforce it, exactly D8's
declared-vs-derived split.

## 4. What the iteration supersedes (decided, **not yet applied**)

The correction pass and Plan U settle what should *not* survive; the port
deliberately does not retire them mid-break (a half-applied break is what D8
forbids). After the break is green:

- **`loopingrules_islands`** — the D6 **spike**, **superseded** by the
  terminology-indexed island **library** (U3/U6): an island is a *view over
  operations*, retrieved by signature.
- **`loopingrules_patterns`** — **subsumed**: ADR-2/ADR-6/ADR-12 say the pattern
  library *is* the island library ("a pattern = a reusable hole-shaped operation
  or shape"). `judge`/`memory` become islands/models.
- **`calibration`'s `adapt`** (the separate online **controller**) — **superseded
  by the network** (ADR-13: the network is the one selection mechanism, subsuming
  `RuleControl`/`argmax`). Its **value-fitting** half (`search`/`Knob`/`checks`) is
  **not** superseded — a different search space (constants inside declared
  operations vs which application fires), ADR-2's levels 2/4 vs 3, sharing the
  same `checks` (Plan U criterion 5; ADR-4's mechanical base).
- **`loopingrules_ux.s3`/`s5`** — **superseded by `s6`** (ADR-9/ADR-13 re-framed
  their rule-vs-binding grain as *one act — selecting among applications*).
- **`loopingrules_reflect/r1`** — **superseded by ADR-7/U5** (the IR becomes the
  engine core; r1's IR-analysis job folds into the kernel).
- **`loopingrules_forge`** — **reframed**, not superseded (ADR-7: its IR becomes
  the rule form).

## 5. The examples decision (made, applied)

**Five examples survive**: `cards`, `market` (the reuse pair), `shopping` (the
second `judge` consumer), `trip` (a graph/plan domain), `decide` (the bridge).
The other **eleven examples and ten test files were dropped** — the tuning/dataset
*experiments* (`ablation`, `acquisition`, `adapters`, `branching`,
`bridge_transfer`, `drift`) and the marginal domains (`party`, `quorum`,
`hierarchy`, `planning`, `trade`); they existed to test a research program Plan U
supersedes. `examples/__init__.py` names the five and why.

## 6. Next (recommended, not started)

1. **Finish the port** — stage **5b** (`checks` first: the shared objective),
   **5c** (`patterns`), **6** (the five examples), **6b** (`r0`), **6c** (tests).
   Then `plan-u` is green on the component substrate again.
2. **Then the design pass resumes**: **U0** (reconcile the prose — the guide is
   now *doubly* stale: it says entity-component, and components came back as
   bags); apply the supersessions in §4; build the **island library** (U3).

The natural first increment after the port is **`checks`** — the load-bearing
piece ADR-4 calls the frozen-judge tower's mechanical base.

## 7. Known red / stale (named, not hidden)

- **The port's unported layers are red** (§1) — packages, examples, their tests.
- **The forge is red** (6 collection errors) and **reframed** by ADR-7; deferred.
- **The guide is stale by design**, now doubly: `concepts.md`, `architecture.md`,
  `analysis.md`, `index.md`, `writing-rules.md`, `README.md` (root) and
  `mkdocs.yml`'s `site_description` all describe a substrate the code no longer
  is. This is **U0**.
- **`TODO.md`** (root) and **`README.md`'s History** carry the pre-UX open
  threads; not reconciled.

## 8. Pointers

- `docs/plan-ux.md` — Plan U: thesis, phases U0–U8, probes, invariants, open
  questions.
- `docs/decisions.md` — ADR-1…ADR-13; **ADR-10…13 are the correction pass**, and
  ADR-10 is the substrate this break performs.
- `loopingrules/schema.py`, `loopingrules/world.py` — the new substrate.
- `loopingrules_ux/s6.py` — the per-step probe (`tests/test_ux_s6.py`).
- `docs/archived-old/` — the design forest this direction grew out of.
- `git log` — the commit messages carry the reasoning, as usual here.
