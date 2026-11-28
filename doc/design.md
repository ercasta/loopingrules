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
- **Amended by D21:** a model can also let controllers choose to stop, by authoring a no-op operation. Models without one keep the behaviour above.

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

### D20. Controllers score actions, not only resulting states
Goal: be able to say "from this situation, this change looks better than that one", which is a score of Q(before, action), not just V(after). That is what learned controllers need.

Each controller query runs against a dataset that describes one application:

| Graph | Contents |
|---|---|
| default graph | the resulting state (unchanged, so existing controllers keep working) |
| `GRAPH lr:before` | the current sheet (the live graph, not a copy) |
| `GRAPH lr:inserted`, `GRAPH lr:deleted` | the effective delta |
| `GRAPH lr:action` | `lr:this lr:operation <op> ; lr:binds [ lr:var "file" ; lr:value <node> ]`, one `lr:binds` per parameter (D22) |

```sparql
# reward each line count this action records
SELECT (COUNT(?f) AS ?score) WHERE { GRAPH lr:inserted { ?f ex:lineCount ?n } }
```

- Pure SPARQL, so D9 holds.
- **Performance:** a delta-only controller costs O(|Δ|) per candidate. A whole-state aggregate costs O(N) per candidate, so O(N·A) per tick.
  - **Measured** on a single `COUNT`: the delta form costs a constant ~0.35 ms. The state form costs 0.24 ms at 250 triples, 0.56 ms at 2,500 and 3.0 ms at 25,000. Below ~1,000 triples the state form is cheaper, because rdflib's fixed cost per query dominates.
  - In the folder-scan benchmark (≤ 240 triples), scoring is only 7–9% of the time. Delta versions of its controllers (`engine/benchmarks/folder_scan_delta_controllers.ttl`, run with `--delta`) give the same run and no speedup.
  - **Implementation:** the controller query is evaluated directly, with the resulting state as the default graph. The named graphs come from a `Dataset` subclass that builds each one on first use; `lr:before` is a read-only view of the live sheet, not a copy.
  - **Not yet:** skipping the resulting state altogether when no active controller reads the default graph. It only pays off once validation is lazy (handoff step 1); until then, validation builds the state anyway.
- Controllers must be `SELECT` queries; anything else is refused at load.
- **Learning:** the features are the action, the delta, and the neighbourhood of the bound nodes in `lr:before`. Ranking within a tick only depends on differences, so the user's choices give pairwise preferences: chosen vs. not chosen, stop included (D21).

### D21. Stopping is an authored no-op operation
- **A no-op operation** is an operation with no effects: no `lr:delete`, `lr:insert` or `lr:steps`. Its `WHERE` says when it is available; an empty `WHERE` means always.
- Its applications are kept even though their delta is empty. An operation that *has* effects but produces an empty effective delta for some binding is still dropped (as before).
- Controllers score no-op applications like any other, mostly through `GRAPH lr:action` (D20).
- **Rule: if the winning application changes nothing, autopilot stops.** Applying it wouldn't change the state, so every later tick would choose it again. Stopping is a shortcut for that fixpoint. No halt flag is needed.
- **Ties go to continuing:** a no-op must strictly beat the best application that has effects. It's just a matter of scoring.
- **It's authored, not built in.** If the engine always offered a stop, models that rely on D8 would break. For example, `folder-scan`'s first `scanFolder` lowers the score, so a built-in stop would win on tick 1.
- A model may have several no-ops, e.g. "goal reached" and "give up when stuck". Which one won says why the run stopped.
- **Manual mode:** pressing Stop is recorded as choosing a no-op. That's a training signal.
- **Later, with asynchronous tools (D7):** an empty winner while calls are in flight means "wait", not "stop".
- **Implementation:**
  - `engine.choose` picks the winner, and the UI mirrors the same rule.
  - `Engine.step` returns `stopped` with the winning no-op. `done` still means nothing is applicable, which also happens when a model has no no-op.
  - When only no-ops are applicable, a no-op wins, so a model with an always-available stop ends with `stopped`, not `done`.
  - Applying a no-op by hand changes nothing and isn't journaled. The API logs it ("stop chosen: …"); recording choices for learning comes later.
  - In the UI, no-ops carry a "■ stop" badge and their button reads "Stop".
- **rdflib quirk (fixed in step 1):** rdflib drops solutions that bind no variable. An empty or ground `WHERE` therefore never applied, though SPARQL gives it one empty solution. The engine now appends a marker `BIND` to every `WHERE`.

### D22. Operations: parameters, guards, steps
All three additions are optional and backward compatible.

- **`lr:params`** lists the variables that identify an action.
  - One application per distinct parameter tuple; the other variables are local.
  - `WHERE` rows that share a tuple are merged, and their instantiated effects are unioned. That's SPARQL Update semantics with the parameters pre-bound, so "for every file in this folder" needs no new construct.
  - The application id hashes the parameters only.
  - Without `lr:params`, every variable is a parameter (today's behaviour). Identical solutions are still merged.
  - Spelling: `lr:params "folder file"`, `"?folder, ?file"`, or repeated values. Each name must be a variable `lr:where` binds; otherwise the operation is refused at load.
  - Only the parameters are an application's bindings: they're what the UI shows, what `GRAPH lr:action` lists (D20), and what guards, postconditions and steps see.
- **`lr:requires`**: named guards (`rdfs:label` + `lr:ask`), evaluated per parameter tuple with the parameters pre-bound.
  - `WHERE` is still a precondition. Guards add explanation: the UI can list matched-but-blocked applications as "blocked by: …".
  - They're also clean features for learning, and cheaper than finding out through SHACL after building the resulting state.
  - A guard can also be written as a plain string, `lr:requires "?folder ex:scanned true"`, labelled by its own text.
  - A blocked application is still listed, invalid, with "blocked by: <label>". Its delta isn't computed, so it shows none.
- **`lr:ensures`**: optional postconditions specific to one operation, checked on the resulting state. SHACL stays the global invariant (D4).
  - Same shape as guards. They're checked before SHACL, since they're cheaper; a failure makes the application invalid, and it still shows its delta.
- **`lr:steps`**: an ordered `rdf:List` of `[ lr:where ; lr:delete ; lr:insert ]` steps for transformations that one pattern can't express.
  - The operation's own `lr:delete`/`lr:insert`, over the solutions of `lr:where`, act as the first step.
  - Each step runs against the state left by the previous steps. Within a step, every delete happens before every insert (SPARQL Update order), and rows are unioned as above.
  - **Only the parameters carry over between steps** (revised from "the parameters and earlier bindings"). A step's other variables are local to it. With several rows per step, "earlier bindings" would be ambiguous; to refer to something an earlier step created, match it again, e.g. `?n ex:about ?folder`.
  - A step without `lr:where` runs once, with the parameters only. A step without effects is refused at load.
  - The net delta is tracked as steps apply: a later step can undo an earlier one, and an application whose net delta is empty is dropped.
  - Only the final state is validated, so intermediate states may be inconsistent.
  - Operations without steps keep the fast template path. With steps, the engine works on a copy of the sheet, to be replaced by an overlay (handoff, performance step 2).
- **Fixed on the way:** an operation that deletes and re-inserts the same triple used to remove it. It now keeps it, following SPARQL Update order.
- **Moved to load time:** the "no blank nodes in DELETE templates" check.

```turtle
ex:forgetFolder a lr:Operation ;
  lr:params "folder" ;
  lr:where  """ ?folder a ex:Folder ; ex:scanned true . """ ;
  lr:requires [ rdfs:label "no scan in progress" ;
                lr:ask """ FILTER NOT EXISTS { ?c ex:scanOf ?folder ; lr:status lr:Pending } """ ] ;
  lr:steps (
    [ lr:where """ ?f ex:inFolder ?folder ; ?p ?o . """ ; lr:delete """ ?f ?p ?o . """ ]
    [ lr:delete """ ?folder ex:scanned true . """ ]
  ) .
```

### D23. Operation patterns use a subset of SPARQL; controllers are weighted
- **No new language.** Structure is RDF (params, guards, steps); expressions stay SPARQL.
- **Operation patterns use a subset.** This applies to `lr:where`, `lr:ask` and step `lr:where`; the subset is checked at load.
  - **Allowed:** triple patterns, `FILTER` (with `EXISTS`/`NOT EXISTS`), `BIND`, `OPTIONAL`, `UNION`, `VALUES`, and the expression functions.
  - **Refused:** subqueries, aggregates and `GROUP BY`, `MINUS`, property paths other than a plain predicate, and `GRAPH` (plus `SERVICE`/`FROM`, as in D18).
  - **Why:** this subset can later be compiled to incremental matching (Rete-style). That turns "re-run every `WHERE` every tick" into "update the matches the delta touched". Full SPARQL on rdflib can't make that jump.
  - The current examples already fit the subset.
- **Controllers stay full SPARQL.** Their cost is handled by delta scoring (D20).
- **`lr:weight`** (number, default 1) on a controller: the total is Σ weight × score.
  - It's an extra lever when authoring: rebalance controllers without editing queries. A layer can also re-weight.
  - Learning can tune weights over existing controllers before growing new ones.
  - `lr:active false` still means "not evaluated". A weight of 0 still evaluates the controller (useful to show its score).

## Open questions

- **Q3. Ties and no-ops.** Partly settled by D21: empty deltas are excluded except for no-op operations, and a tie between a no-op and an application with effects goes to continuing. Other ties: still first found.
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
