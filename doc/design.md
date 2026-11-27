# LoopingRules — Design notes

Living document: decisions taken so far, and questions still open. See `info.md` for the original vision.

## Purpose

A utility for "scripting / computing" through data-driven computation that keeps its semantics. Instead of writing one workflow per task, you describe:
- the **state**: an RDF graph,
- what a **valid state** is: SHACL,
- the **moves** that are possible: operations,
- the **preferences** used to pick a move: controllers.

The engine then drives the computation, either step by step with a human choosing (manual) or automatically (autopilot).

Prior art this resembles, useful for borrowing ideas:
- production systems (OPS5, CLIPS) and their conflict resolution,
- STRIPS-style planning (preconditions → effects),
- graph rewriting,
- greedy best-first search, where the controllers act as the heuristic.

## Decisions

### D1. Architecture: Python core + TypeScript UI
- The **Python engine** holds the store, matches operations, validates, scores, executes ticks and runs tools such as shell commands.
- The **TypeScript UI** is the spreadsheet-like grid, the application picker and the autopilot controls. It talks to the engine over HTTP and WebSocket.
- Reason: a browser alone can't interact with the environment.

### D2. Data: triples first, quads later
- v0 works with plain SPO triples.
- G (named graphs) arrives later, with standard RDF quad meaning.

### D3. Operations: SPARQL-Update shaped, stored as RDF
An operation is an RDF resource whose parts are SPARQL fragments:

```turtle
:moveToDone a lr:Operation ;
  lr:where  """ ?t a :Task ; :status :doing . FILTER NOT EXISTS { ?t :blockedBy ?x } """ ;
  lr:delete """ ?t :status :doing . """ ;
  lr:insert """ ?t :status :done . """ .
```

- Each solution of `WHERE` is one **application**, meaning one binding of the variables.
- `DELETE` and `INSERT`, instantiated with that binding, give the **delta**.
- Operations are stored as data. The model can therefore live in the sheet itself, and later be inspected or generated.
- We are **not inventing a language** for now. If writing raw SPARQL fragments becomes painful, we can add some syntax sugar later.
- Why not SHACL rules (SHACL-AF `sh:SPARQLRule` / `sh:TripleRule`):
  - they are designed for monotonic inference, run to a fixpoint;
  - they only insert and never delete;
  - they have no notion of choosing between alternatives.

  They may still be useful later for *derived* triples, such as computed columns.

### D4. SHACL acts as a guard on results
- For each application, the engine computes the potential next state and validates it against the model's shapes.
- An application whose result is invalid is **not offered**: it is either hidden or shown greyed out with the violations.
- This is how the model "filters" which operations are allowed, on top of the `WHERE` pattern.

### D5. Controllers score resulting states, and their scores are summed
- A controller is a scoring function over a **resulting state**, i.e. the current state with the delta applied.
- Each tick runs the same steps:
  1. enumerate applications;
  2. compute each potential state;
  3. drop the invalid ones;
  4. every active controller scores every remaining state;
  5. sum the scores per application;
  6. execute the highest-scoring application.
- The new state may enable new applications, which is where the "looping" comes from.
- v0 controllers are hand-written, probably as SPARQL `SELECT` queries returning a number (see Q2).

### D6. Learning is out of scope for now
- Manual driving and hand-crafted controllers only.

### D7. Tools: shell first
- A tool call is a set of triples that follows a tool-calling vocabulary, for example `lr:ShellCall` with `lr:command`, `lr:status`, `lr:stdout`, `lr:stderr` and `lr:exitCode`.
- Tool calls run **between ticks**:
  - **synchronous by default**: the call completes and its result triples are added before the next tick;
  - **asynchronous tools** have their status polled between ticks, and the result arrives when it is ready.

### D8. Autopilot stops only when nothing is applicable, or when the user stops it
- There is no local-optimum stop: autopilot always runs the best application, even when its resulting score is lower than the current state's.
- Consequence: a model can loop forever, for example between two operations that undo each other. The user stopping it is the safety net. We may add loop *detection* later as an indicator, not as a stop rule.

### D9. Models and controllers are pure data, with no user code
- The goal is that models and controllers can be shared without the risks of sharing code.
- Operations, SHACL shapes and controllers are declarative: RDF + SPARQL + SHACL only.
- Controllers in v0 are SPARQL `SELECT` queries returning a single numeric `?score`. Each runs against the resulting state of an application. We may need something more sophisticated later.
- The only way to affect the environment is through tools, and tools are gated by approval (D10).

### D10. Tool calls need approval
- Before the engine runs a tool call, such as a shell command, the call must be approved.
- v0 approval is per call.
- **Allowlist (implemented):** command *templates* approve matching calls automatically, e.g. `wc -l < '{}'`.
  - Each `'{}'` matches one single-quoted argument without quotes or newlines, and the whole command must match, so nothing can be appended.
  - Regexes were rejected as too easy to make dangerously broad.
- **Trust is stored per user, not per project:** `~/.loopingrules/trust.ttl` (override with `LR_TRUST`), scoped to the project's absolute path. A shared project folder cannot carry its own approvals; this is required by D9.
- "Always allow…" proposes a template by replacing each quoted argument of the command with `'{}'`.
- In autopilot, a call waiting for approval pauses the loop until it is approved or rejected.

### D11. User input is through the sheet
- Operations take no free parameters: every variable is bound from the sheet.
- To provide input, the user creates or edits SPOs directly, then selects an operation that applies to them.

### D12. The applications list can be filtered
- In the UI, the user can filter the applications list by criteria, for example "the resulting state contains SPOs matching pattern P", the operation name, or the bound variables.

### D13. Direct edits can make the sheet invalid
- Direct edits are allowed even when the sheet stops satisfying SHACL; the violations are shown.
- This lets the user build up a valid state step by step.
- The SHACL guard (D4) still applies to applications.

### D14. Shell output is structured
- SPARQL cannot split a string into several rows.
- So the shell tool writes stdout one line per resource:
  `?call lr:stdoutLine [ lr:index 0 ; lr:text "a.txt" ]`.
- Operations can then match the lines one by one.

### D15. SHACL-driven autocomplete for editing (implemented)
The loaded shapes guide the user's editing:
- **Subject.** Suggest existing subjects. For a new subject, suggest `rdf:type` values taken from the shapes' `sh:targetClass`.
- **Predicate.** For a subject of type C, suggest the `sh:path` of the property shapes that target C.
  - Highlight properties that are still missing their `sh:minCount`.
  - Hide properties whose `sh:maxCount` is already reached.
- **Object.** Depends on what the property shape declares:
  - `sh:in`: offer the listed values;
  - `sh:class`: offer existing instances of that class;
  - `sh:datatype`: use a typed literal editor;
  - `sh:nodeKind`: offer only IRIs or only literals, as declared;
  - `sh:pattern`: validate as the user types.
- **"Complete this resource".** One action that pre-fills every required property that is still missing.
- **Engine side.** A `GET /suggest?s=&p=` endpoint that reads the shapes graph.

Implemented in `engine/loopingrules/suggest.py` and `GET /api/suggest?field=s|p|o&s=&p=&q=`.
- The "complete this resource" action is a "still needs" strip of the missing required properties; clicking one fills the predicate.
- Not supported yet:
  - complex `sh:path`s;
  - `rdfs:subClassOf` inference for targets;
  - `sh:targetSubjectsOf` / `sh:targetObjectsOf`;
  - `sh:or` / `sh:and` / `sh:node`.

### D16. Goals are a modeling pattern, not an engine feature
Goal-driven computation needs **no engine support**. A goal is:
- **a typed resource in the sheet** (`ex:g1 a ex:CountLinesGoal ; ex:folder ex:target`), with its parameters as properties. The user creates it like any other SPO, guided by the goal's SHACL shape (D15);
- **an authored "reached" operation** per goal type. Its `WHERE` is the concrete achievement pattern, and it inserts `?goal lr:reached true`;
- **goal-gated operations**: operations require an unreached goal in their `WHERE`. Once the goal is reached, nothing is applicable and autopilot stops under D8;
- **goal-aware controllers**: authored controllers that score only work related to an active goal, plus a large reward for `lr:reached`, so the goal is marked as soon as possible;
- **subgoals** are operations that insert goal resources, much like HTN methods.

Convention (no engine meaning, so the UI can show goals in the future): goal classes are `rdfs:subClassOf lr:Goal`, and achievement is `lr:reached true`.

Lessons from `examples/folder-scan-goal`:
- **The "reached" pattern must not be vacuously true.** "Every .txt file is counted" holds before any file is known, so it also requires that the scan is done and every listed file has been registered and classified.
- **Greedy plateaus remain the author's problem.** Steps that don't raise any controller's score need subgoals with their own controllers.
- **Minted IRIs must be unique per context.** File IRIs now include the folder; without that, a second goal on another folder was blocked by SHACL.

### D17. Persistence: seed + journal + snapshot
- **Authored files are never rewritten by the engine.** This covers `sheet.ttl`, `model.ttl`, `controllers.ttl` and `package.ttl`. `sheet.ttl` is the seed state.
- **Runtime state lives in `.lr/`:**
  - `history.rdfp` is an append-only journal in RDF Patch style. Each transaction is a `TX` … `TC` block with `H` headers (kind, label, bindings, time) and `A`/`D` lines. There is one transaction per tick, edit, tool call result or undo, written immediately, so saving is automatic.
  - `snapshot.ttl` holds the sheet after the first N transactions; its first line is `# lr:snapshot-tx N`. It is written every 100 transactions and on request.
- **Load** = the snapshot, or the seed, plus a replay of the later transactions. An incomplete transaction at the end of the journal (a crash mid-write) is ignored.
- **Undo** appends the inverse of the latest change that hasn't already been undone (header `undoes`), so the journal stays append-only.
- **No blank nodes at runtime.** Fresh nodes from INSERT templates and tool results are minted as `urn:lr:gen:<8 hex>` (prefix `gen:`). Blank nodes in the seed are minted on load, and `_:x` typed in the UI becomes `gen:u_x`. Without this, journal entries could not refer to a node across reloads.

### D18. Sharing: `.lr.zip` exports
- **An export is a zip with a fixed set of files:** `package.ttl` (manifest), `model.ttl`, optional `controllers.ttl`, optional `sheet.ttl` (the seed, the current state, or none), optional `README.md`. The journal and trust rules are never included.
- **The manifest declares `lr:mayRun` command templates.** Import shows them, and nothing is trusted unless the user asks (`--trust-declared`). A call that matches no declared template still goes through normal approval, but the banner flags it as undeclared.
- **Import is defensive:**
  - exact file names only, so no paths or folders (prevents zip-slip);
  - size limits;
  - every file must parse;
  - operations and controllers must pass the security check (D9);
  - declared templates must be valid trust templates;
  - the destination folder must be new or empty.
- Exports were chosen over git repos as the sharing channel; a registry can come later.
- **Security (D9 addendum):** rdflib executes `SERVICE` and may dereference `FROM` graphs. Both are refused in operations, controllers and UI filters, and `SPARQL_LOAD_GRAPHS` is disabled. Still to do: query time limits.

### D19. Controller packs (layered controllers)
- **A controller pack is an export with `lr:extends "<base package title>"`** that contains only `package.ttl`, `controllers.ttl` and an optional `README.md`. A model or sheet inside it is refused.
- **Install:** `lr add-layer pack.lr.zip project` puts it in `project/layers/<title>/`. It is checked against the project's own `package.ttl` title and refused if already installed. Remove it by deleting the folder. `lr import` refuses a pack and points the user to `add-layer`.
- **Engine:** a layer's controllers are loaded with `layer=<title>`. Their scores are summed with the project's own controllers like any other controller, and the UI marks them with the pack's name.
- **A pack can only steer; it cannot add behaviour.** So a model that wants to be steerable must *offer* alternatives. `folder-scan` 0.2.0 offers per-file and batch line counting; its own controllers prefer per-file, and the `big-folders` pack prefers the batch above a threshold that is read from the sheet.
- **Observation:** a pack's condition is evaluated on what the sheet knows at each tick, so a decision can flip as knowledge grows. With `big-folders`, the batch wins as soon as the 5th file is registered, even before all files are known. That's fine here, because the batch counts every `*.txt` in the folder anyway.
- **Not yet:** pinning the version of the base package (`lr:extends` matches the title only), packs that extend other packs, and freezing a layer's controllers versus editing them.

## Open questions

- **Q3. Ties and no-ops.**
  - How are ties broken: first found, random, or operation priority?
  - Should applications whose delta is empty be excluded?
  - Default if no objection: exclude empty deltas; break ties by first found.
- **Q4. Cost.** Scoring every resulting state is expensive. Options:
  - score against an overlay view (base + inserts − deletes) instead of copying the store;
  - for SHACL, validate only the shapes affected by the delta, or accept full validation in v0.
  - Default: accept full validation in v0.
- **Q5. Store.**
  - rdflib: slow, but pySHACL works with it natively.
  - pyoxigraph: fast and supports quads, but needs a bridge to SHACL.
  - Default: put the store behind an interface and start with rdflib.
- **Q8. UI stack.** Default: React + Vite + a grid component (TanStack Table).
- **Q9. Persistence.** Default: save the sheet, model and controllers as Turtle files in a project folder.
