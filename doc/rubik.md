# Rubik: a rich example

*Status: design (2026-11-28). Steps 1 and 2 are built: `examples/rubik`, `examples/rubik-viewer`, `engine/tests/test_rubik.py`.*

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
