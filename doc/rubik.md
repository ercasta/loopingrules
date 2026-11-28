# Rubik: a rich example

*Status: design (2026-11-28). Steps 1–3 and the first solver stage are built: `examples/rubik`, `examples/rubik-viewer`, `examples/rubik-show`, `engine/tests/test_rubik.py`.*

## Goal
A complete example built from separate, shareable parts:
- **an external program** that shows a Rubik's cube in 3D (Three.js);
- **a model** that represents a cube semantically and solves it;
- **an integration pack** that drives the external program;
- **a policy pack** that orchestrates the solving steps and their display.

## Terms: project and pack
- **Project:** a folder that LoopingRules runs. It contains:
  - `sheet.ttl`, the seed state;
  - definitions (operations, shapes, controllers);
  - knowledge;
  - a manifest, `package.ttl`.
- **Pack:** an export whose manifest says `lr:extends "<title>"`. It installs into a project's `layers/<title>/` (`lr add-layer`). It can add operations, shapes, controllers and knowledge, but it never has a `sheet.ttl`. It extends the base project or another pack (D28).

The cube's colours are state, and a pack can't carry state. So the cube model is the **base project**, and the integration and the policy are **packs stacked on it**:

```
rubik            project   cube, moves, solver
└─ rubik-viewer  pack      lr:extends "rubik"         + the Three.js app
   └─ rubik-show pack      lr:extends "rubik-viewer"  policy
```

## 1. `examples/rubik`: the project
### Geometry is knowledge
- The geometry is generated once by a script (`examples/rubik/gen_geometry.py`), and the output, `geometry.ttl`, is committed.
- **Positions:** 54 facelets, `pos:U1 … pos:B9`, named face by face, from 1 to 9 in reading order.
- **Slots:** 12 edge slots and 8 corner slots, each listing its facelets in a fixed order, e.g. `slot:UF rk:facelet pos:U8, pos:F2`. The solver uses them to find pieces.
- **Turns:** the 6 quarter turns `mv:U mv:D mv:F mv:B mv:L mv:R` (clockwise). Each is 20 named mappings:
  ```turtle
  mv:U_01 rk:of mv:U ; rk:from pos:U1 ; rk:to pos:U3 .
  ```
  Knowledge can't contain blank nodes, so the mappings have names.
- **Prime and double turns:**
  - each move names its face and direction: `mv:Ui` (U′) is `rk:face face:U ; rk:dir rk:ccw`, so it uses U's mappings in reverse. `rk:inverse` links each move to its inverse.
  - `mv:U2` is `rk:dir rk:cw ; rk:twice true`, and the turn applies U's mappings in a second step.

### State
- One triple per facelet: `pos:F5 rk:colour rk:Green`.
- The seed `sheet.ttl` is a solved cube, with the centres fixed: white up, green front.
- **Shapes:** every position has exactly one colour, and that colour is one of the six.

### The plan and the turn operation
- **The plan** is a queue of moves, kept as an RDF list: `rk:cube rk:plan ( mv:R mv:U mv:Ri … )`.
- **`rk:turn`** is one generic operation:
  - it pops the head of the plan;
  - one step, `?map rk:of ?face ; rk:from ?f ; rk:to ?t . ?f rk:colour ?c`, deletes `?f rk:colour ?c` and inserts `?t rk:colour ?c` (from and to are swapped for a prime turn);
  - a step's rows apply together, all deletes and then all inserts, so the 20 colours move as one permutation (D22).
- **History:** each executed move is recorded as `[] a rk:Executed ; rk:move mv:R ; rk:seq …` (a minted node), so the packs can react to it.
  - Without aggregates (D23) a rule can't compute "max + 1". So `rk:seq` comes from a counter on `rk:cube`, which the turn deletes and re-inserts as `n + 1`.

### Commands (`lr:in`, D25)
- `[] a rk:Scramble ; rk:moves ( mv:R mv:U2 … )` appends the moves to the plan.
  - The viewer generates the random sequence. That keeps the model deterministic.
  - A post may contain lists, because their nodes are the post's own blank nodes.
- `[] a rk:Solve` starts the solver. Like every command, it only matches when the plan is empty, so commands posted during a run wait their turn.
- `[] a rk:Reset` restores the solved colours.

### The solver: the beginner method, as rules
- **Searching won't work.** A cube can't be solved by greedy scores from controllers. The rules are **macro-operators**: each one recognises a case and appends a known algorithm, or a single setup turn, to the plan.
- **Stages** are a convention in the sheet (`rk:cube rk:stage stage:Cross`). An authored operation advances to the next stage when the current one's condition holds (the D16 pattern):
  1. white cross;
  2. white corners;
  3. middle-layer edges;
  4. yellow cross (dot, L and line cases);
  5. yellow edges;
  6. yellow corners placed;
  7. yellow corners oriented, then `rk:cube rk:solved true`.
- **Recognition** joins slots with colours. For example, "the white–red edge is in slot `slot:UF`, flipped" is a match over `slot:UF`'s facelets and their colours.
  - Patterns stay within the D23 subset: triple patterns, FILTER, BIND, UNION and VALUES. There are no property paths, so slot facelets are listed explicitly.
- **Planning only happens with an empty plan.** The solver plans one algorithm, the turns execute it, and then the solver looks again. The plan never runs on a stale recognition.
- **Controllers:**
  - prefer executing the plan over everything else;
  - prefer handling input;
  - a `stop` no-op wins once the cube is solved and the input is empty.

### Tests
- A scramble followed by its inverse gives a solved cube.
- Each turn applied four times is the identity.
- The solver solves N random scrambles (fixed seeds) within a tick limit. This test grows stage by stage.

## 2. `examples/rubik-viewer`: the integration pack, and the app
### The pack (definitions only)
- **`viz:announce`**: for every `rk:Executed` that isn't shown yet, it inserts an `lr:out` message and marks the move as `viz:announced true`:
  ```turtle
  [] lr:channel lr:out ; a viz:Turn ; viz:move mv:R ; viz:seq 17 .
  ```
- **`viz:sync`**: answers a `viz:Sync` post with a `viz:State` message that lists all 54 colours. The viewer uses it on load and after a reset.
- **Stage changes** are also announced as an `lr:Say`, e.g. "Stage 3: middle-layer edges", so the viewer can show a caption.

### The app (`examples/rubik-viewer/app/`)
- A small Vite + TypeScript + Three.js app, like `ui/`. In development it proxies `/api` to `lr serve` on port 8765.
  - The export of the pack contains only its `.ttl` files and `README.md`, so the app stays outside it.
- **It uses only the D25 channels, never direct edits:**
  - it reads `lr:out` from the WebSocket (`/api/events`) and from `GET /api/messages?channel=out`;
  - it posts `rk:Scramble`, `rk:Solve`, `rk:Reset` and `viz:Sync` with `POST /api/in`;
  - after a `viz:Turn` has finished animating, it acknowledges it (`POST /api/out/ack`). **The ack means "displayed".**
- **The cube:**
  - 26 cubies; a turn rotates its layer around a pivot, with tweening, then snaps the cubies back to the grid;
  - it applies `viz:Turn` messages in `viz:seq` order;
  - after each `viz:State` it repaints all 54 facelets, which corrects any drift.
- **The UI:** Scramble, Solve and Reset buttons, a speed slider, a stage caption, and the move list.

## 3. `examples/rubik-show`: the policy pack
- Controllers and one no-op only. No new state and no engine code.
- **Pace the solve with the display:**
  - **`show:wait`** is a no-op operation. A controller makes it strictly win while any `viz:Turn` is still unacknowledged.
  - In listening mode (D25), autopilot then rests until the viewer acks, and continues with the next turn. One move is executed, shown, executed, shown…
- **Prefer announcing** over executing the next turn, so every move reaches the viewer before the next one is made.
- **Optional second policy, `rubik-replay`:** no waiting; it solves at full speed and lets the viewer play the queued messages back. It shows the point of policy packs: the same model and integration, different behaviour, and only data changed.

## Step 1: as built
- `gen_geometry.py` writes `geometry.ttl` (knowledge: 54 positions, 20 slots, 120 mappings, 18 moves) and the solved `sheet.ttl`.
- `model.ttl`: the position, cube and scramble shapes, and the operations `turn`, `scramble` and `reset`. A scramble whose list holds a non-move is refused at posting (a SHACL path through the list).
- Tests: each quarter turn four times is the identity; known effects of R and U pin the conventions; a double turn is two quarters; a 25-move scramble followed by its inverse solves; reset; commands wait for the plan.
- **Performance:** a 100-move scramble runs at **68 ms/tick**, flat, with 361 triples in the sheet after it.

## Step 2: as built
- **The pack** (`examples/rubik-viewer/viz.ttl`) has two operations: `announce turn` and `send the cube's state`.
  - The state message's IRI is derived from the request with `BIND(IRI(CONCAT(STR(?m), "-state")))`, so one step can add all 54 facelets to the same message.
- **The app** (`examples/rubik-viewer/app/`, Vite + TypeScript + Three.js, port 5180, proxy to 8765):
  - it shows turns in `viz:seq` order and acknowledges each one once it has been animated;
  - a `viz:State` overwrites its colours;
  - it asks for the state at start, after a reset, and on a gap, and polls slowly as a fallback;
  - it renders on demand.
- **Two engine fixes:**
  - `POST /api/out/ack` wakes a listening autopilot;
  - **step parameters:** a step's templates now see the parameters even when its pattern doesn't mention them. rdflib's `SELECT *` drops initial bindings the pattern doesn't use, so before this fix `?s` never reached the facelet template. There's a regression test in `test_d22.py`.
- **Checked end to end** against `lr serve`, with the pack installed through `lr export` + `lr add-layer`:
  - after a scramble the viewer animated turns 21–40, and its 54 colours matched the model's;
  - reset re-synced to solved;
  - both channels ended empty.
- **Dev tooling:** `scripts/dev/shot.py` takes `LR_SHOT_URL` and `LR_SHOT_SCALE`, and prints the values steps return.
  - Headless Edge renders WebGL in software. Use scale 1, and read async probes back synchronously, because promises awaited over CDP stall while WebGL frames render.

## Step 3: as built
- **The pack** (`examples/rubik-show/show.ttl`) holds back the plan with a **penalty** rather than a block.
  - The controller `hold the plan until the last turn is shown` scores `turn` −10 while an executed turn is unannounced, or a `viz:Turn` is unacknowledged.
  - `wait for the viewer` is a no-op scoring 0, so it strictly beats only a held-back turn.
  - **Why not a block:** a viewer that has just loaded holds back its acks until it has the state. If waiting beat everything, its `viz:Sync` would never be answered, and the run would deadlock.
- **CLI fix:** `lr run --listen` runs again after it acknowledges `lr:out`, instead of blocking on stdin while the policy could continue.
- **Tests:**
  - with the engine: one turn per ack;
  - a sync is answered while the plan is held;
  - over the API with a listening autopilot: never more than one `viz:Turn` waiting;
  - over stdin.
- **Live, with the viewer:** the model's turn count now advances one turn at a time, in step with the viewer, instead of jumping to 20. The log shows the cycle `turn` → `announce turn` → `wait for the viewer won`.

## Step 4, stage 1 (white cross): as built
- **The method is knowledge; the solver is generic.**
  - `gen_method.py` writes `method.ttl` with the stages and the cases. Each case is a set of needs, e.g. `need:x rk:at rpos:U8 ; rk:like rpos:D5`, "the sticker at U8 has the colour of the D centre". Each case has an algorithm: a named list of relative moves (`rmv:`).
  - Everything is written as the beginner method writes it, with white on D.
- **Frames** (added to `geometry.ttl`): the 4 rotations that put white down. Each maps relative positions and moves to absolute ones (`frame:fB rpos:F2 pos:…`, `rmv:R mv:…`). A case is written once and recognised from all 4 sides.
- **Algorithms are found by search.** The generator runs a bidirectional search for the shortest sequence that solves the target and keeps the other cross slots sticker for sticker. Every algorithm is replayed to check it.
  - The cross has 23 cases, with algorithms of 1–4 moves.
- **The solver** (`solver.ttl`) has four generic operations:
  - `start solving` (`rk:Solve`);
  - `plan a case`: a case whose needs all hold in a frame, written as "no need fails", becomes the plan, with that frame;
  - `next stage`: the goal holds in every frame;
  - `finish solving`.
- **`turn`** resolves relative moves through `rk:cube rk:frame`. It walks the plan with a pointer and deletes only list nodes that are not `rk:AlgorithmStep`s, since an algorithm's nodes are knowledge.
- Scramble and reset now also wait while a solve runs.
- **Tests:**
  - 6 random scrambles get the white cross in at most 16 turns;
  - solving a solved cube makes no turns.
- **Cost** (`bench_solve`, a 25-move scramble, then solve):

  | tick | ms/tick |
  |---|---|
  | turn | 103 (68 before the solver: every tick also tries the solver's patterns) |
  | plan a case | ~500 (23 cases × 4 frames, nested `NOT EXISTS`) |
  | next stage | ~510 |

  The profile shows **matching 74%, SHACL 26%**. Planning grows with the number of cases. The full method will have about 100 cases, so expect planning ticks of about 2 s.

## Step 4, stage 2 (white corners): as built, and a stress test
- **Only knowledge changed.** `gen_method.py` adds `stage:Corners` (after `stage:Cross`) and 23 corner cases. **The solver didn't change:** `plan a case`, `turn` and `next stage` picked up the new stage as they are. That's the design working as intended.
  - **Target:** the white-front-right corner into DFR (`D3`, `F9`, `R7` like `D5`, `F5`, `R5`).
  - **Cases:** every place and twist of that corner. They're found by applying moves to the solved corner, so a twist that can't happen can't be written.
  - **Kept:** the cross, and the other three bottom corner slots except the one the target is in, sticker for sticker.
  - **Algorithms:** 3–6 moves, each replayed against the 20 tracked stickers.
- **The search is now byte-based.** A state is a `bytes` of facelet indices, a move is a `bytes.translate` table, and paths are parent pointers. The cross output is identical. Both stages generate in under a second.
- **Test:** 6 random scrambles reach cross + corners in at most 4×4 + 4×6 turns.
- **Cost** (`bench_rubik_solve.py`, seeds 3–5, cross + corners, ~32–37 ticks):

  | tick | start of session (rdflib) | mirror (D30) | + cheap `__bool__` | + steps on the mirror |
  |---|---|---|---|---|
  | plan a case | ~570 | ~100 | ~66 | **~65** |
  | turn | ~75 | ~75 | ~47 | **~27** |
  | average | ~210 | ~78 | ~52 | **~36** |

- **Findings from the stress test:**
  - **The number of cases per stage matters, not the total.** Doubling the cases (23 → 46) took planning from ~85 to ~100 ms, because patterns join on `?stage` first. ~100 cases over 7 stages should keep planning near 100 ms or below.
  - **pySHACL tested `if graph:` 3 times per validation**, and our `Union.__len__` is O(knowledge), so 74% of SHACL time went to counting triples. `Overlay` and `Union` now have a cheap `__bool__`.
  - **Steps now run on the mirror** (D30, phase 2).
  - **Oxigraph doesn't push a `VALUES` join into `UNION` branches.** The quarter-turn step took 31 ms instead of 0.4 ms. Bindings now go in as substitutions where they're in scope.
  - **What's left per tick:** SHACL is ~60% of `pick` (one validation per tick), and matching plus steps ~35%.
- **Estimate for the full method:** ~150 turns at ~27 ms plus ~40 planning ticks at ~65 ms, so ~7 s per solve, down from ~45 s at the start of the session.

## Step 4, stage 3 (middle layer): as built
- **Again only knowledge changed:** `stage:Middle` and 15 cases. The solver is unchanged.
  - **Target:** the front-right edge into FR (`F6`, `R4` like `F5`, `R5`).
  - **Kept:** the first layer, and the other three middle slots except the one the target is in.
  - **Cases:** with the first layer solved, the edge is either in the top layer (8 cases: *insert it*) or in a wrong middle slot or flipped (7 cases: *take it out*). Cases with the edge in the bottom layer are left out, since the cross is there.
- **Extraction cases use the loop on purpose.** Inserting a misplaced middle edge directly takes ~16 moves, beyond the search. As in the beginner method, its algorithm only takes the edge out to the top layer (any position, either way round), and the next planning tick recognises an insertion. The search now accepts several goal states for this.
- **Algorithms:** 5–7 moves. The search finds shorter insertions than the textbook 8.
- **Test:** 6 random scrambles reach the first two layers, in at most 4×4 + 4×6 + 4×2×7 turns.
- **Cost:** flat. With 61 cases over 3 stages, planning is ~62 ms and turns ~27 ms, as with 46 cases. A first-two-layers solve takes 71–99 ticks, 2.5–3.3 s.

## Step 4, stages 4–7 (the last layer): as built. The rules solve the cube.
**Goal of this phase** (agreed with the user): not to discover algorithms, but to see whether the rules can express and run a complex procedure, and to find out what that needs. Hand-written textbook algorithms are fine. Next: extract what the solver needs into a general **planning pack**.

- **The last layer is iterative.** A few textbook algorithms are applied to the case at hand, then the solver looks again:

  | stage | cases | algorithm |
  |---|---|---|
  | 4. yellow cross | dot, L, line (needs say which edges are *not* yellow) | `F R U R' U' F'` |
  | 5. yellow edges | adjacent pair right, opposite pair right, or else turn U (fallback) | `R U R' U R U2 R' U` |
  | 6. yellow corners placed | front-right corner in place (any twist), or none (fallback) | `U R U' L' U R' U' L` |
  | 7. yellow corners oriented | twist it (`R' D' R D`), bring the next one round (`U`), align the top (`U`) | |

- **`gen_method.py` now describes stages as data** (`Stage`, `Case`): stages 1–3 are searched, stages 4–7 are written by hand. There are 72 cases in all.
- **`simulate.py`** emulates the solver's rules in Python, in the same order, and reads the same stage data: 1000 scrambles in seconds. All 1000 are solved, in 60–196 turns (mean 130) and 13–45 plans (mean 31).
- **Test:** 6 random scrambles are solved by the rules through all 7 stages, with no SHACL violations.
- **Cost:** a full solve is 169–198 ticks in **5.5–6.1 s** (~32 ms per tick; planning ~43 ms, turns ~29 ms).
  - With the new need forms written as a `UNION` inside `FILTER NOT EXISTS`, planning took ~390 ms. Two `FILTER NOT EXISTS` blocks, one per kind, say the same and took ~43 ms. **Oxigraph and `UNION` don't mix well** (see also D30); worth a note for authors, or a rewrite in the engine.

### What the procedure needed: input for the planning pack
Found by removing each feature in the simulator (100 scrambles each):

| Need | Why | Without it |
|---|---|---|
| **Negative conditions** (`rk:unlike`) | The yellow-cross cases are told apart by which edges are *not* yellow. | 38/100 solved |
| **Any-of conditions** (several `rk:at` in one need) | "The corner is in place, whichever way it's twisted", both as a case and as the stage's goal. | can't be expressed |
| **Case priority** (`rk:priority`, scored by a controller) | Fallback cases ("no corner in place", "turn the top") must only win when nothing else matches. | 19/100 solved (cases tried in name order) |
| **A stage that keeps its frame** (`rk:sameFrame`) | `R' D' R D`, repeated, must use the same R and D, or the bottom never comes back. | 5/100 solved |
| **Explicit operation priority** | Ending a stage must win over planning in a finished stage. Until now this held only because `rk:nextStage` sorts before `rk:planCase`. | not measured; by reasoning, stage 6 would loop: `cp_one` still matches once every corner is placed |

**What stayed generic:** stages with goals and a next stage; cases as needs + algorithm; plan → execute → look again; recognition through frames (symmetries). **What's domain-specific:** how a need is checked ("the sticker at X has the colour of centre Y"), written twice, in `rk:planCase` and `rk:nextStage`. A generic pack must leave that check to the domain. That's the main design question for the pack.

**Also learned:** before this phase, the order in which cases were tried was the alphabetical order of their IRIs, an invisible priority. Two of the five needs above showed up as "it works, by luck of naming". Priority belongs in controllers.

## Engine changes needed (small)
- *(done in step 2)* **`POST /api/out/ack` must wake a listening autopilot** (`session.input_event.set()`, as the other mutations do). Today an ack doesn't, so `show:wait` would never be re-evaluated.
- Nothing else is expected. Revisit this if the solver's performance demands it.

## Risk: performance
- A beginner solve is about 100–150 turns plus the planning ticks, so 200–300 ticks.
- The recognition rules are join-heavy, and every operation is matched on every tick (handoff §5: matching is the bottleneck).
- **Measure the time per tick right after step 1**, with geometry and turns only, and again as the solver stages land. If it's too slow, that is the case for cross-tick reuse of matches (handoff §5, option c).

## Build order (each step agreed before building)
1. Geometry generator, `rk:turn`, scramble, reset, and the tests (inverse and four-turn identity). Benchmark the ticks.
2. `rubik-viewer`: the pack, the app, and the ack fix. Scramble from the viewer and watch it.
3. `rubik-show`: paced display.
4. The solver, one stage at a time, each with its test over random scrambles.
5. READMEs, screenshots, exports (`exports/rubik-*.lr.zip`), and optionally `rubik-replay`.
