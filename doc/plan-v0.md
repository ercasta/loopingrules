# LoopingRules — v0 build plan

Goal: run the "folder scan" example end to end, both in manual mode and on autopilot. Decisions are in `design.md`.

## Repository layout

```
engine/                     Python core (uv, Python 3.12+)
  loopingrules/
    vocab.py                the lr: namespace
    project.py              load/save a project folder (Turtle)
    store.py                Store interface + rdflib implementation
    operations.py           parse lr:Operation, enumerate applications, compute deltas
    validation.py           pySHACL wrapper
    controllers.py          SPARQL scoring
    engine.py               tick, manual apply, autopilot loop
    tools/shell.py          shell tool + approval queue
    api.py                  FastAPI: REST + WebSocket
  tests/
ui/                         TypeScript, React + Vite
examples/folder-scan/       sheet.ttl, model.ttl, controllers.ttl
doc/
```

## Project format (one folder)

- **`sheet.ttl`**: the current state.
- **`model.ttl`**: SHACL shapes and `lr:Operation`s.
- **`controllers.ttl`**: `lr:Controller`s, each with:
  - `lr:query`: a SPARQL SELECT that returns a single `?score`;
  - `lr:active`: true or false.

## Engine semantics (v0)

1. **Enumerate applications.** For each operation, run `SELECT * WHERE {where}` on the sheet. Each row is one application.
2. **Compute the delta.** Fill in the DELETE and INSERT templates with the row's bindings, using rdflib `initBindings`.
   - A blank node in INSERT becomes a fresh node for each application.
   - Applications whose delta is empty are dropped.
3. **Validate the resulting state.** Copy the graph, apply the delta, and run pySHACL. Invalid applications are kept, but marked `valid=false` with their violations. They are never selected and are greyed out in the UI.
4. **Score.** Each active controller runs on every valid resulting state, and the scores are summed.
5. **Tick.**
   - In manual mode, the user picks an application.
   - On autopilot, the engine picks the highest score; ties go to the first one found.
   - The engine then applies the delta and runs the **tool phase**.
6. **Tool phase.** This happens between ticks: in manual mode, right after the user applies an application; on autopilot, at the start of the next step.
   - Each `lr:ShellCall` with `lr:status lr:Pending` waits for approval.
   - Once approved, the engine runs the command synchronously and writes back:
     - `lr:exitCode`;
     - `lr:stdoutLine` / `lr:stderrLine` resources, each with `lr:index` and `lr:text`;
     - `lr:status lr:Done`.
   - A rejected call gets `lr:status lr:Rejected`.
   - Autopilot pauses while an approval is pending.
7. **Stop.** Autopilot stops when no valid application is left, or when the user stops it.

## Example: `folder-scan`

- **Seed.** The user adds the folder to scan:

  ```turtle
  :f a ex:Folder ; ex:path "C:/some/dir"
  ```

- **Operations** (each one guarded with `FILTER NOT EXISTS`, so autopilot ends):
  1. `scanFolder`: for a Folder that is not yet scanned, add a ShellCall `ls -1 <path>` and mark the folder scanned.
  2. `registerFile`: for each stdout line of a finished scan call, add an `ex:File` with `ex:name`.
  3. `classifyFile`: for each File without an extension, add `ex:extension` using `STRAFTER` / `REPLACE`.
  4. `countLines`: for each `.txt` File without a line count, add a ShellCall `wc -l <file>`.
  5. `recordCount`: parse the result of `wc` into `ex:lineCount`.
- **SHACL.**
  - A File has exactly one `ex:name`.
  - It has at most one `ex:extension`.
  - `ex:lineCount` is an integer.
- **Controllers.**
  - `progress`: score = number of Files with an extension + number of Files with a line count.
  - `preferFewPendingCalls`: score = −(number of pending calls).
- **Platform.** Commands go through a configurable shell (Git Bash on Windows), so `ls` and `wc` work.

## API (FastAPI)

**REST endpoints:**

| Endpoint | Purpose |
|---|---|
| `GET /sheet` | current triples + violations |
| `POST /sheet/triples` | add triples |
| `DELETE /sheet/triples` | remove triples |
| `GET /applications?filter=…` | list applications with delta, validity and score |
| `POST /apply/{id}` | apply one application |
| `POST /autopilot/start` | start autopilot |
| `POST /autopilot/stop` | stop autopilot |
| `GET /approvals` | list calls waiting for approval |
| `POST /approvals/{id}` | `approve` or `reject` a call |
| `POST /project/save` | save the project |
| `POST /project/load` | load a project |

**WebSocket `/events`** pushes:
- `sheet-changed`
- `tick` (with the chosen application)
- `approval-needed`
- `autopilot-stopped`

## UI (React + Vite)

The tables are hand-styled; TanStack Table turned out not to be needed.

- **Sheet panel.** An editable S | P | O grid with prefix-compacted IRIs, add/delete rows and violation badges.
- **Applications panel.** One row per application, showing:
  - the operation name;
  - the bindings;
  - a delta preview, with deletions in red and insertions in green;
  - the score per controller and the total;
  - whether it is valid.

  Filters: operation, binding text, and "resulting state contains pattern". An *Apply* button on each row.
- **Controls.** Step (one autopilot tick), Run / Stop autopilot, and a tick counter.
- **Approvals.** A modal or panel showing the pending command, with Approve / Reject buttons.

## Milestones

| | Deliverable | Check |
|---|---|---|
| ✅ M1 | Engine core: store, operations, validation, controllers, tick | pytest on folder-scan; tool calls stubbed |
| ✅ M2 | Shell tool + approval queue + headless CLI (`lr run examples/folder-scan`) | autopilot completes end to end from the CLI, with approvals prompted in the terminal |
| ✅ M3 | FastAPI + WebSocket | API tests |
| ✅ M4 | UI | manual drive + autopilot of folder-scan in the browser |

## Known v0 limitations, accepted for now

- Full graph copy and full SHACL validation for every candidate, so it will be slow on large sheets.
- No named graphs, no learning, no allowlist, no loop detection.
