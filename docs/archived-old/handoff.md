# Handoff: the attribute-substrate port, and where the plan stands

Status: **a working handoff**, written so a review can judge what is done and
steer the next step. It is not a plan doc; it points at them. The steering
input it is written *for* is `docs/ux.md` (the user-experience direction:
authoring without code, tool calling, input ingestion, packaging) — marked
work-in-progress in the tree.

## 1. Where we stand

The plan's frontier was D8 (**the attribute substrate**, `docs/plan-attributes.md`,
Phase S in `docs/plan.md`). It is largely **built**, on the branch
`attribute-substrate` (pushed; open a PR at
`https://github.com/ercasta/loopingrules/pull/new/attribute-substrate`). `main`
is untouched.

**392 tests pass. 6 collection errors remain — all of them the `forge` spike
package and `loopingrules_reflect.r1`.**

| Layer | State |
|---|---|
| `loopingrules` — `world`/`analyze`/`reflect`/`loop`/`memory`/`save`/`share`/`engine` | ported |
| `loopingrules_calibration` — `kit`/`surface`/`checks`/`adapt`/`linter`/`report` | ported |
| `loopingrules_patterns` — `judge`/`memory` | ported |
| `loopingrules_islands` — `items`/`funds`/`i0` | ported |
| `loopingrules_reflect.r0` | ported |
| `examples/` — all 17 domains + `drift` | ported |
| their test suites | rewritten, green |
| `loopingrules_forge` — `m0`/`m1`/`m2`/`q0`/`evolve`/`fixtures` | **red** |
| `loopingrules_reflect.r1` (rides `m0`) | **red** |

Nothing was deleted to get here: the port is a clean break that retargeted
every layer onto attributes; the forge is the one layer not yet retargeted.

## 2. The substrate as built (what is now REAL)

Reference: `docs/plan-attributes.md` (D8). The decisions that matter for
steering, because everything above now depends on them:

- **Entity + attribute.** A `(name, value)` slot, at most one per name per
  entity. A value is a scalar, an entity **reference** (a plain int id), or a
  **flat list** of those — no dict, no nesting.
- **A component is a shape a ref targets**, realized as a **tagged entity**;
  a **tag is a flag**. In practice the examples used a working-reading of
  this: a *facet* is a flat attribute, a *standalone record* is a tagged
  entity carrying its fields, a *tag* is a flag.
- **Refs and transience are declared by NAME** (`World.refs`, `World.transient`),
  not by class metadata — `share` remaps the declared ref names.
- **The change log holds `(name, old, new)` deltas** (`MISSING` for absence);
  `changes(changed="…")` filters by attribute name.
- **A knob names an attribute** (`Knob("max_level", …)`); the value lives on
  whichever entity carries it.

Two consequences the port surfaced, both worth knowing before designing on
top (see `docs/ux.md`):

1. **A tag flag adds a column to every `each` row** — `each("listing","card")`
   yields `(entity, <listing-flag>, card)`.
2. **A tag flag whose name collides with a ref name breaks `share`** (a `stop`
   tag vs a `frontier.stop` ref) — naming conventions for shapes vs links are
   now load-bearing, and D8 leaves them open.

## 3. Where this sits in the plan

- `docs/plan.md` — the roadmap. Phase S (the substrate) supersedes the
  component vocabulary Phases 1-13 assumed, so the phases whose layers it
  retargets (`analyze`, `save`, the IR, the scheduler) must be re-verified
  after it. That re-verification is effectively what this branch did for
  everything except the forge.
- `docs/plan-attributes.md` (D8) — **done as a port**; its open questions
  (naming convention, constructor idiom, verb set, schema versioning, cycles,
  anonymous attributes) are now answered by *code* and should be folded back
  into the doc.
- `docs/plan-reflection.md` (D7) / `plan-scheduler.md` — their engine halves
  (`reflect`, `Loop(schedule=True)`) are ported; their IR-native halves are
  not, and the forge is the IR.
- `docs/plan-control-network.md` (D9) / `plan-maze.md` (D10) — design only;
  the substrate they will be built on is now real.
- `docs/plan-forge.md` (D5) — the one red piece (below).

## 4. The red piece: the forge

`loopingrules_forge` is the IR / six-gate verification / freeze / scheduler /
GP spike (`docs/plan-forge.md`). It is red because `m0.py`'s IR constructors
still take **component classes** (`w_the(Kind)`, `w_get(e, Kind)`,
`each_for([Kind], …)`) and its hand-written IR expresses `cards` in the old
component model. Retargeting it means re-deriving all 12 `cards` rules in an
attribute-name IR, then `m1` (gates + mutants), `m2` (freeze + knobs),
`evolve` (GP controller), `q0` (scheduler) follow. `reflect.r1` is agnostic
(it compares IR analysis to `analyze`) and goes green with `m0`.

It is **bounded and mechanical, but large** (~1,800 lines across four files
that share `m0`). It is a spike, explicitly "not a commitment to a real
package layout," so deferring it costs nothing structural.

## 5. Next steps

Two tracks. Their order is exactly what the review should decide, because
`docs/ux.md` likely reorders them.

**Track A — finish the port.**
1. Retarget the forge IR to attribute names (`m0` → `m1`/`m2`/`evolve`/`q0`/`r1`)
   to get the branch fully green.
2. Reconcile the prose: `README.md`, `docs/concepts.md`, `docs/architecture.md`,
   `docs/analysis.md`, `docs/comparison-soar.md`, `mkdocs.yml`'s description,
   and `TODO.md` still describe components; `docs/plan-attributes.md`'s open
   questions should be updated to the as-built answers.
3. Then open the PR / merge.

**Track B — the UX factor (`docs/ux.md`).** The handoff is written so this is
the steering input. Its asks land on gaps the engine has *today*:
- a **no-code authoring "language"** over entity-attributes (the substrate was
  simplified precisely so structure need not be Python — but no such language
  exists yet; today every domain is still a Python module);
- a **tool-calling convention** (the engine spawns a request entity and calls
  the tool; `circuits.Call`/`ToolRequest` is the historical seed, and the
  `engine`'s channel seam is the boundary — but there is no stdlib of tools,
  no render/parse mapping, no code of "batteries");
- **input ingestion** (turn user text into entity-attributes via conventional
  schemas + a shipped set of "metarules");
- **packaging/sharing** agents (`share.py` is the byte-level primitive; there
  is no agent/rule-bundle artifact).

These are new work, not substrate work — but they depend on exactly the
decisions in §2 (names, shapes, flags), so the review may want to fold a few
of D8's open questions shut *toward* the UX asks before the forge is finished.

## 6. Open questions for the steering review

1. **Order:** finish the forge first (fully green branch), or pause it for the
   UX track — the no-code authoring language is the UX load-bearer, and it
   touches the same "what is a shape, what is a name" decisions the forge
   retarget would freeze.
2. **The authoring language:** is it an IR/JSON-authored rule form (the forge
   IR is the nearest thing), a surface over `circuits`-style specs, or a
   loader onto the existing Python rules? D8's homoiconicity (a rule is an
   entity) is the intended answer; nothing embodies it yet.
3. **Naming conventions** (shape vs link, plural for a set of refs): the port
   proved they matter (`share` collisions). Settle them before a no-code
   authoring surface hardens them.
4. **Tools / batteries:** does the engine ship the tool convention + a
   metarule set (the UX note assumes yes), or is that a separate package?
5. **Docs vs code first:** the prose is now wrong about the code by design;
   reconcile now, or after the UX shape is decided?
