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
- **Considered in D24 and deferred:** the planned features don't need named graphs.

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
- **Amended by D25:** a model can turn direct edits off (app mode).
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
*Superseded by D28: packs now carry everything (operations, shapes, controllers, knowledge), as plain triples.*

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

### D24. Named graphs: deferred
*Status: **deferred** (2026-11-28). The sheet stays triples-only (D2). The analysis below is kept for when a real need appears.*

**Why deferred:**
- Named graphs don't scope names. IRIs are global, and namespaces already prevent clashes. A graph only groups *statements*, so that a set of statements can be referred to as a whole. That serves provenance, handling a batch as one unit, keeping views that disagree, and access control.
- None of the planned features needs that:
  - `in:`/`out:` channels are a convention (D25). `GRAPH in: { ?m a cmd:X }` and `?m lr:channel lr:in ; a cmd:X` are nearly the same pattern.
  - Pack knowledge can be a read-only layer that the engine tracks internally, so models never see `G`.
  - Provenance is already recorded per transaction in the journal.
  - Intended vs. observed facts are better modelled with different predicates (`:mayImport` vs `:imports`).
- **Graphs don't even isolate data here.** Once SHACL looks across graphs (which we wanted), a message must use its own node anyway.
- **They would cost a lot:** decisions about the default graph, reserved names, merged vs. per-graph views for controllers, consistency of the merged delta, minting for loaded knowledge, and a G column in the UI. That's complexity for its own sake, as goals were in D16.
- **Revisit if** we need statement-level provenance, or views that disagree about the same resource. Even then, shapes would need to apply per graph (see below).

*The proposal as it was drafted:*

**Why now, and not later:**
- Four of the planned features (`doc/hmi_improv.md`) depend on how data is shaped: the `in:`/`out:` channels, knowledge in packs, the graph view, and the MCP server. If we build them on triples, each one has to be reworked once quads arrive.
- The triple-only code is still small and contained: the overlay, operation templates, the journal, the snapshot, export/import, autocomplete, and the sheet rows in the API and UI.
- The journal format already supports quads: an RDF Patch `A`/`D` line takes an optional 4th term. Existing journals stay readable.
- If we build incremental matching on the D23 subset, it should handle `GRAPH` from the start. Adding it to an existing Rete matcher would be much harder.
- Only our own examples and exports use the current format.

**Model:**
- The sheet is an RDF dataset: one **default graph** plus any number of **named graphs**. Graph names are IRIs; minted `gen:` IRIs are fine, blank nodes are not (D17).
- **A pattern without `GRAPH` sees the default graph only, not the union.** Other graphs are reached with `GRAPH <iri> { … }` or `GRAPH ?g { … }`.
  - Every existing model, operation and controller keeps working unchanged, because today's sheet becomes the default graph.
  - Content in a named graph never mixes into the state by accident. For example, an `in:` command saying `:task1 :status :done` is a request, not a fact.
  - Rejected: making the default graph the union of all graphs. It's handy for reading knowledge, but it brings back exactly that mixing. A model that wants knowledge reads it with `GRAPH`.
- **`GRAPH ?g` ranges over the sheet's named graphs only.** The reserved graphs below are reachable only by name.
- As in RDF, a named graph exists while it has triples. Deleting its last triple removes it.

**Reserved graph names:** the `lr:` namespace is reserved for graph names.
- Sheet data can't be written into an `lr:` graph. Edits, templates and tool results that try are refused.
- The names in use are the controller graphs from D20: `lr:before`, `lr:inserted`, `lr:deleted` and `lr:action`.

**Operations (amends D23):**
- `GRAPH <iri>` and `GRAPH ?g` are now **allowed** in operation patterns (`lr:where`, `lr:ask`, step `lr:where`). Naming an `lr:` graph there is refused at load: operations see the sheet, not the controller graphs.
- `lr:delete` and `lr:insert` templates accept `GRAPH <iri> { … }` and `GRAPH ?g { … }` blocks, as in SPARQL Update. In a template, `?g` must be bound by the pattern or be a parameter. Triples outside a block go to the default graph.
- An application's delta becomes a set of quads. The rules for the effective delta and the empty delta (D21, D22) are unchanged, just applied per quad.

**SHACL (D4): shapes look across graphs.**
- The guard validates the **union** of the default graph and every named graph, a read-only merged view, against the model's shapes. The reserved `lr:` graphs aren't part of it.
- So shapes look across graphs. For example, a `sh:class` check on a value in the default graph is satisfied by a type declared in a knowledge graph.
- **This is deliberately different from matching.** Operation patterns are scoped (no `GRAPH` = default graph only), because an operation must know what it reads. Validity is global, because it's a statement about everything the sheet knows.
- **Consequences:**
  - Graph boundaries don't hide anything from the guard. A shape targeting `ex:Task` applies to an `ex:Task` wherever it is declared, including one inside an `in:` message.
  - That's often useful, e.g. a shape on a command class validates commands. But a message mustn't use state classes for anything that isn't meant to be validated as state.
  - The same triple in two graphs counts once.
- The rule that an application is invalid only if it *adds* violations stays the same, compared on the union.
- **Reporting:** a violation names its focus node, as today. The UI also shows which graphs the focus node appears in.
- **Rejected:** validating each graph separately, which is pySHACL's own behaviour for a dataset. Knowledge in one graph couldn't satisfy a shape in another.
- **Later, if needed:** shapes that apply only to one graph's nodes (e.g. `lr:graph <g>` on a shape), while values are still read from the union. Not in the first cut.

**Controllers (amends D20):**
- The default graph is still the resulting default graph, and `GRAPH <g>` gives the resulting named graph `<g>`.
- `lr:before` is still the current *default* graph. The current state of a named graph is reached as `GRAPH <g>` in the resulting state, or through the delta.
- `lr:inserted` and `lr:deleted` hold the triples inserted or deleted in **any** graph, without saying which. Existing delta controllers keep working.
- `lr:action` also lists `lr:this lr:touches <g>` for each named graph the application changes. The default graph isn't listed.
- **Not yet:** a delta that keeps track of which graph each change belongs to (e.g. one `lr:inserted` graph per graph). We'll add it when a controller needs it.

**Files and persistence (D17, D18):**
- The seed is either `sheet.ttl` (default graph only, as today) or `sheet.trig` (default plus named graphs). A project with both is refused.
- Journal: `A s p o g .` for a quad in named graph `g`; a 3-term line is the default graph, so old journals replay unchanged.
- The snapshot becomes `snapshot.trig`. The `# lr:snapshot-tx N` header stays, and an existing `snapshot.ttl` is still read.
- Exports follow the same naming rule: `sheet.ttl` or `sheet.trig`, never both. Import checks the same way.
- `model.ttl` and `controllers.ttl` stay triples.

**Tools (D7, D14):** shell call results still go to the default graph. A tool that writes to its own graph can come later.

**API and UI:**
- Each sheet row gets `g`, which is `null` for the default graph.
- The Sheet panel gets a G column, hidden while the sheet has no named graphs.
- An edit has an optional graph, with autocomplete from the existing graph names.
- The applications list shows deltas as quads.

**Implementation notes:**
- **Dataset class:** keep the default graph a plain rdflib `Graph`, and keep named graphs in a dict of `Graph`s (a small `Sheet` class) rather than in rdflib's `Dataset`/`ConjunctiveGraph`, which is slower. Present a `Dataset` view only where SPARQL needs one, as `store.NamedGraphs` already does for controllers.
- **Overlay:** `store.Overlay` becomes one overlay per graph the delta touches; untouched graphs are passed through as they are.
- **Union view for SHACL:** a read-only `Graph` subclass that chains the default graph's and named graphs' (or their overlays') `triples()` and drops duplicates. pySHACL already accepts the overlay, which is built the same way. With no named graphs, validation gets the default graph directly, so the cost doesn't change.
- **Performance:** a model that uses only the default graph should run the folder-scan benchmark at the same speed. Measure before and after with `bench_folder_scan.py` (and `--delta`).

**What this enables (separate decisions, later):**
- `in:` and `out:` as named graphs: input/output channels.
- Pack knowledge as a read-only named graph loaded from the layer.
- A graph view where nodes are resources and the graph is shown on statements. A node can't sit in a single graph's box, since its statements can be spread over several graphs.

**Open issues found before deferral:**
- **`lr:before` covers only the default graph** in the draft above, while `lr:inserted`/`lr:deleted` merge all graphs, which is inconsistent. The preferred fix:
  - `lr:before` and a new `lr:after` merge all graphs;
  - the merged delta is *defined* as `lr:after − lr:before` (and the reverse), because the same triple can sit in two graphs;
  - moving a triple between graphs then shows only through `lr:touches`.
- **Loaded knowledge needs deterministic IRIs for its blank nodes.**
- **A knowledge graph's prefixes must not enter the query prologue.**

### D25. Input and output channels are a convention
*Status: built (2026-11-28). The `in:` and `out:` of `doc/hmi_improv.md` are the resources `lr:in` and `lr:out`. Example: `examples/hello-channels`.*

**Goal:** humans and tools send commands to a running model, and the model answers, all as SPOs. This is the base for the tutorial, the MCP server and tool integration.

**A message is a resource on a channel:**
```turtle
gen:m1 lr:channel lr:in ;  a cmd:AddTask ; cmd:title "write D25" .              # a request
gen:m2 lr:channel lr:out ; a lr:Say ; lr:text "Added." ; lr:replyTo gen:m1 .     # an answer
```
- **Vocabulary:**
  - `lr:channel` takes `lr:in` or `lr:out`.
  - `lr:text` is optional human-readable text, which the UI shows. It's the same property shell output lines use (D14).
  - `lr:replyTo` links an answer to the request it answers.
  - `lr:Say` is a plain text message.
  - Every other message class and property belongs to the model (`cmd:`, `tut:`, …).
- **A message is a request, not a fact.** It describes itself with its own node and never restates facts about state subjects. `gen:m1 cmd:task :t1 ; cmd:status :done` asks for a change; `:t1 :status :done` inside a message would *be* the change. SHACL sees messages like everything else, so shapes on message classes validate commands.
- **It's just triples in the sheet.** Matching, SHACL, controllers, the journal and undo need no changes.

**Posting to `in:`** (UI I/O panel, `POST /api/in`, `lr send`, and later MCP):
- The poster sends a Turtle snippet whose **subjects are all blank nodes of the snippet**, e.g. `[] a cmd:AddTask ; cmd:title "write D25"`.
  - There must be exactly one **root**: a blank node that isn't the object of another triple in the snippet. The engine adds `lr:channel lr:in` to it.
  - Blank nodes are minted as `gen:` IRIs (D17), and the poster gets the root's IRI back, to match answers via `lr:replyTo`.
- **A post only adds triples, and only about its own new nodes.** So a post can't edit state: it can only ask. This is what makes `in:` safe to open to tools.
- **A post that would add SHACL violations is refused**, with the violations. Unlike a direct edit (D13), there's no reason to accept a malformed command, and the tool needs the feedback.
- Each post is one journaled transaction of kind `input`.

**Consuming `in:`:** it's done by the model's own operations.
- An operation matches `?m lr:channel lr:in ; a cmd:X` and acts on it.
- It deletes the message in the same application, using `lr:params "m"` and `?m ?p ?o` (D22). The journal keeps the history.
- Unrecognised messages: a model may author a catch-all operation that answers with an `lr:Say` and drops the message. Otherwise the message just stays there.
- Controllers decide when input is handled; usually it's preferred, e.g. by rewarding deleted `lr:in` messages through `GRAPH lr:deleted` (D20).

**Producing `out:`:** operations insert messages, e.g. `[ lr:channel lr:out ; a lr:Say ; lr:text "…" ]`. Blank nodes in INSERT templates are minted fresh (D17).

**Reading `out:`** (UI, `GET /api/out`, the WebSocket, `lr receive`, MCP):
- Messages are returned with what they say about themselves, plus the triples of `gen:` nodes they point to.
- **Order:** messages are listed in the order they appeared, i.e. by the transaction that added them. The API knows this from the journal, so order isn't stored in the data. Rules can't compute "max + 1" anyway: aggregates are outside D23.
- **Acknowledging** deletes the message: a journaled edit of kind `ack`.
  - Programmatic readers (`lr receive`, MCP) ack by default.
  - The UI panel shows `out:` as a log and acks only when the user clears it.
  - Unacknowledged messages stay in the sheet, visible like any SPO.

**Listening autopilot (the one engine change):**
- Today autopilot stops when nothing is applicable, or when a no-op wins (D8, D21).
- In **listening** mode, it waits instead, and resumes on the next post or edit.
- UI: a "listen" toggle next to autopilot.
- CLI: `lr run --listen` reads messages from stdin (Turtle snippets, one per blank-line-separated block) and prints `out:` messages as they appear. That gives a pipe interface with no server.
- **Approval (D10) is unchanged.** A tool call that needs approval still pauses the loop. Over stdin with no human attached, unapproved calls are refused unless they match the allowlist.

**Direct edits: the model chooses, and tools are limited to `in:`:**
- **Edits stay allowed by default.** A project without a declaration keeps direct edits (D11, D13, D15), because the spreadsheet is the product and authoring needs to change the state directly.
- **App mode:** a model can declare `lr:directEdits false` in `package.ttl`.
  - The Sheet becomes read-only, and input goes through the I/O panel.
  - All state changes then come from operations, tool results and posts, so the SHACL guard holds for the whole run (if the seed is valid).
  - The model's command classes are its interface. Import (D18) shows the declaration.
- **The human can unlock it.** An "unlock editing" toggle with a warning turns editing on for the current session. It resets on reload, and edits made while unlocked are journaled as usual.
  - It's a guardrail, not a security boundary: the project files and the journal belong to the user.
  - Undo stays available in app mode, since it only reverses journaled changes.
- **Tools get `in:` only, whatever the model says.**
  - The tool fronts (the MCP server, `lr run --listen` on stdin) can post, read `out:` and run, but can't edit the sheet directly.
  - The user can grant direct edits to tools for one project. That grant is stored per user in `~/.loopingrules/trust.ttl`, like command templates (D10), so a shared project can't grant it to itself.
  - Here the restriction *is* a boundary: a tool may ask, but not rewrite.
  - The HTTP API serves the UI, so its edit endpoints follow the app-mode lock, not the tool rule. It listens on localhost by default (`--host`).
- ~~The tutorial ships in app mode.~~ **Revised in D26:** the tutorial keeps direct edits on, because its exercises are edits to the sheet, which a post can't make.
- **Amends D13:** direct edits can still make the sheet invalid, but only where direct edits are allowed.

**Implementation notes (as built):**
- `channels.py` parses and checks posts, and lists messages; `Engine.post`, `Engine.messages` and `Engine.ack` do the journaled work.
- **A post may not use `lr:` terms**, except `lr:text`, `lr:replyTo` and `lr:Say`. Otherwise a tool could post, for example, an `lr:ShellCall` with status `lr:Pending`, or a message that claims to be on `lr:out`.
- **A message's parts** are the minted (`gen:`) nodes that only the message and its other parts refer to, like blank nodes in Turtle. A minted node that anything else refers to is shared state: it isn't returned with the message, and acknowledging doesn't delete it.
- **How an operation consumes a message.** Answer in the operation's own `lr:insert`, and delete the message in a step: `lr:steps ( [ lr:where "?m ?p ?o" ; lr:delete "?m ?p ?o" ] )`. Don't put `?m ?p ?o` in the main `lr:where`. Rows are merged by `lr:params`, but each row mints its own `[]`, so the answer would be repeated once per triple of the message.
- **API:**
  - `POST /api/in` returns 422 with the violations when a post is refused.
  - `GET /api/messages?channel=in|out` lists messages, and `POST /api/out/ack` acknowledges them (all of them without `ids`).
  - `POST /api/autopilot/listen` switches listening on or off, and `start` takes `listen` too. The new status is `listening`.
  - Edit endpoints take `force` for "unlock editing".
- **`lr run --listen`:**
  - stdout carries only Turtle: `lr:out` messages, plus `# posted <iri>` and `# refused: …` comments. The log goes to stderr.
  - A tool call that needs approval and doesn't match the allowlist is refused; `--yes` approves everything.
  - If a call is still left pending, the command exits with code 1.
- **Not built yet:** the per-project grant of direct edits to tools. No tool front can edit yet; it comes with the MCP server.

**Not in this decision:** the tutorial (it builds on this), the MCP server, and any routing beyond the two channels. More channels would just be more resources than `lr:in`/`lr:out`; nothing in the engine assumes there are only two.

### D26. The tutorial is a model
*Status: built (2026-11-28): `examples/tutorial`, `lr tutorial`, `engine/tests/test_tutorial.py`.*

**Goal:** get used to thinking in SPOs, by doing. The tutorial is an ordinary project, `examples/tutorial`, built only from data, operations, shapes and controllers. The only code added is the `lr tutorial` command.

**Direct edits stay on (this revises D25).** The exercises are edits to the sheet, such as `ex:me ex:knows ex:grace`, and a post can only describe its own new nodes. So you practise in the sheet and talk to the tutorial with messages, which teaches both ways of giving input.

**Lessons are data in the sheet:**
```turtle
tut:L3 a tut:Lesson ; tut:order 3 ; tut:next tut:L4 ;
  tut:intro "…" ; tut:hint "…" ; tut:praise "…" .
tut:progress tut:current tut:L3 .
```
- Progress is a triple too. Editing it is allowed, and that's a lesson in itself: the tutorial's state is your data.
- `tut:` is the tutorial's own machinery; `ex:` is the learner's world.
- The first message, a welcome on `lr:out`, is in the seed, so it shows up before anything runs. It asks the learner to tick *listen* and start autopilot.

**Operations:**
- **Generic ones work for any lesson:**
  - *present* says the current lesson's intro, once (`tut:presented true`);
  - *hint* answers `[] a tut:Hint .`;
  - *next* answers `[] a tut:Next .`, on reading lessons only (`a tut:Reading`);
  - *skip* answers `[] a tut:Skip .`;
  - *not understood* answers any other message.
- **One check operation per lesson.** Its `WHERE` is the exercise, written as `FILTER EXISTS { … }` so it binds no extra variables. When it matches, the check says the praise text and moves `tut:current` on.
  - Lessons can't store their check as data, because an operation can't evaluate a pattern it reads from the sheet. That would be an engine feature, and we prefer conventions.
- **The learner's world has its own operations:** *introduce*, *greet formally*, *greet casually*, and the handler for the `ex:Introduce` command. Each is guarded (`lr:requires`, D22) by the lesson that unlocks it, so before then the UI shows them as "blocked by: unlocked in lesson N".
- **A no-op *wait* (D21)** lets autopilot rest while there's nothing the tutorial should do by itself. Listening (D25) then waits for the learner's next edit, message or manual application.

**Controllers (they're also lesson material):**
| Controller | Scores |
|---|---|
| tutorial first | 2 for the tutorial's own operations and the command handler |
| fallback | 1 for *not understood*, so a specific answer always wins |
| rest | 0.5 for *wait* |
| prefer formal (active) | 3 for *greet formally* |
| prefer casual (inactive) | 3 for *greet casually* |

Operations in the learner's world score 0. So *wait* beats *introduce*, and the learner applies it by hand in lesson 5. In lesson 6, switching the controllers over changes what autopilot does.

**Curriculum:**
| # | Lesson | Exercise / check |
|---|---|---|
| 0 | Messages | read it, then send `[] a tut:Next .` |
| 1 | A triple | some `?x a ex:Person` |
| 2 | Properties and literals | a person with an `ex:name` |
| 3 | Links | `?a ex:knows ?b`, where `?b` is also an `ex:Person` |
| 4 | Shapes | a shape requires names; at least two people, and none without a name |
| 5 | Operations | apply *introduce* by hand; check: some `ex:introduced` |
| 6 | Controllers | switch to casual, then add a person; check: some `ex:greetingStyle "casual"` |
| 7 | Commands | post `[] a ex:Introduce ; ex:who … ; ex:to … .`; check: some `ex:Introduction` (the record of a request, which is a fact) |
| 8 | Wrap-up | reading only, with pointers to the other examples |

**Delivery and checks:**
- `lr tutorial [dir]` copies `examples/tutorial` to `dir` (default `./lr-tutorial`) unless it already exists, and serves it. Running it again resumes where the learner left off.
- A test plays the whole tutorial with scripted edits, posts, a manual application and a controller switch. That keeps lesson changes from breaking the flow, and documents the intended solutions.
- **Small API change:** a manual application, an undo and a controller switch now wake a listening autopilot, like posts and edits do.

### D27. A graph view of the sheet
*Status: built (2026-11-28).*

A **Graph** tab next to the Sheet shows the same triples as a graph, built with Cytoscape.js. It's UI only: no API or engine changes.

- **Nodes are resources** (IRIs and minted nodes), drawn once each. A node isn't "in" anything: it's just everything the sheet says about it.
  - **Literals stay inside their subject's card.** They're values, not things, so they don't become nodes.
  - **`rdf:type` is shown as the node's colour and badge,** not as edges. Otherwise every instance would be wired to its class, and the picture would become a hairball.
  - An IRI that is only ever an object (e.g. `ex:Greeter` used as a value) still gets a node, a smaller one.
- **Links between subjects** are ordinary SPOs whose object is an IRI. A toggle chooses how they're shown:
  - **edges:** arrows labelled with the predicate;
  - **chips:** no arrows. The links are listed in the details panel of the selected node, and clicking one selects and centres the target. This keeps large sheets readable.
- **Expand / compact:**
  - Compact shows the name and type.
  - Expanded also lists the literal properties and, in chip mode, the links.
  - Double-click toggles one node; buttons expand or compact all of them.
- **Filters:**
  - text search, which dims what doesn't match;
  - types and namespaces, which can be hidden;
  - messages, hidden by default as in the sheet (D25);
  - **focus:** the selected node's neighbourhood within N hops.
- **Details panel:**
  - the selected node's outgoing triples and the links pointing to it, with clickable resources;
  - "show in sheet", which switches to the Sheet tab filtered on that subject.
- **Live:**
  - The view follows the sheet. Triples the last change added are highlighted, as in the sheet, and nodes with SHACL violations have a red border.
  - Existing nodes keep their positions when the sheet changes. New nodes are placed next to a neighbour, and "re-layout" runs the full layout again.
- **Loading:** the graph code is loaded only when the tab is opened, so the sheet view doesn't pay for Cytoscape.

### D28. Everything is SPO: packs carry complete features, and knowledge
*Status: built (2026-11-28). Supersedes the controller-only packs of D19.*

**Goal:** share complete, usable features. A pack can add operations, shapes, controllers and facts, not just steer.

**Convention: definitions are recognised by their type.** Operations, shapes and controllers are already RDF. So a project or a pack is just a set of Turtle files, and file names no longer matter (only `sheet.ttl` keeps its special meaning, as the state). The engine reads every triple and sorts it:

| The triples describe… | Role |
|---|---|
| a subject `a lr:Package` | the manifest |
| a subject `a lr:Operation` | an operation |
| a subject `a sh:NodeShape` or `sh:PropertyShape`, or with `sh:targetClass`, `sh:targetNode`, `sh:targetSubjectsOf`, `sh:targetObjectsOf`, `sh:property` or `sh:path` | a shape |
| a subject `a lr:Controller` | a controller |
| everything else | **knowledge** |

- **A definition includes the blank nodes reachable from it,** such as `sh:property [ … ]`, `lr:requires [ … ]` and `lr:steps ( … )`. So "everything else" is well defined.
- **The existing files keep working.** `model.ttl` and `controllers.ttl` are only triples. A project may also put everything in one file.
- **Side effect:** non-definition triples in a model file, such as `ex:Person rdfs:label "Person"` or `rdfs:subClassOf`, become knowledge that operations and controllers can query. Before, only SHACL saw them.

**Knowledge is read-only data that sits beside the sheet:**
- **Who sees it:** operations, guards, controllers and SHACL see the sheet plus the knowledge, through a read-only combined view (`store.Union`). Writes only ever go to the sheet.
- **It isn't journaled.** It's reloaded from its files at every start, so removing a pack removes its knowledge.
- **An application that would delete a knowledge triple is invalid** ("would delete knowledge from <source>"). Deleting nothing silently would mislead. A direct edit that removes knowledge is refused too.
- **Inserting a triple that's already known changes nothing,** as with any triple already present.
- **Knowledge may not contain blank nodes.** It's never journaled, so its nodes need names that are the same on every load (D17). Definitions may use blank nodes freely, because nothing in the journal refers to them.
- **UI:** knowledge rows are shown in the Sheet and Graph, marked with their source (`knowledge` for the project, otherwise the pack's title). They can't be edited, and a checkbox hides them.

**Packs (layers):**
- A pack is an export with `lr:extends "<title>"`. It may contain any `.ttl` files except `sheet.ttl`, plus a `README.md`.
- `<title>` is the base project's title, or the title of a pack that is already installed. So packs can extend packs.
- `lr add-layer` installs a pack into `layers/<title>/`, as before. It now also loads the project with the new layer, and refuses the pack (removing it again) if it conflicts.
- Operations from a pack are marked with the pack's name in the UI, like its controllers.

**Conflicts are refused at load and at install:**
- the same operation, controller or shape IRI defined in two sources;
- the same prefix bound to two different namespaces in two sources.

**Safety is unchanged (D9, D10, D18):**
- A pack's operations and controllers pass the same checks: the security check and the D23 subset.
- A pack's `lr:mayRun` templates are shown at install and trusted only with `--trust-declared`.
- A tool call counts as "declared" if the project or any installed pack declares it.

**Not yet:**
- disabling a pack without deleting its folder;
- version constraints on `lr:extends`;
- definitions inside the sheet itself, which would let operations rewrite operations. That's a separate, bigger decision.

### D29. `lr check`: run to rest, report, exit code
*Status: built (2026-11-28). Example: `examples/arch-check` checks this repository's layering.*

**Goal:** use a model as a check in CI, pre-commit, and coding-agent hooks. For example: "the code respects the architecture", with the architecture written as knowledge (D28).

`lr check <project> [--trust-declared] [--max-ticks N] [--json] [--quiet] [--stderr]`:
- **It starts fresh from the seed and writes nothing:** it doesn't read the journal, and no `.lr/` folder appears. The same commit always gives the same result.
- **It runs autopilot until it rests** (D8, D21).
- **Tool calls run only if they're trusted:** they must match the user's trust rules (D10), or, with `--trust-declared`, the `lr:mayRun` templates of the project and its packs. Anything else is refused, because nobody is there to approve it.
- **Exit codes:**
  - **0 passed;**
  - **1 failed:** SHACL violations in the final state, or findings;
  - **2 incomplete:** a refused tool call, the tick limit reached (default 1000), or a project that doesn't load.
- **Severities:** `sh:Warning` and `sh:Info` results are reported but don't fail the check.
- **Output:** a human summary by default, or `--json` with status, exit code, ticks, violations, warnings, findings, notes and refused calls. `--stderr` writes the report to stderr, for agent hooks.

**Findings are how a check model reports problems.** The SHACL guard (D4) means an operation can never make the state invalid. So a model that checks something can't report a problem by breaking a shape: the operation that recorded it would never be offered.
- **Convention:** a model reports a problem as an `lr:out` message of type **`lr:Finding`** (D25), with `lr:text`. `lr check` fails on any finding. Other `lr:out` messages are printed as notes.
- **SHACL violations in the final state still fail the check.** Since operations can't create them, they come from the seed or from tool results.
- **A post can't fake a finding.** `lr:Finding` isn't one of the `lr:` terms a post may use (D25).

**Hooks:**
- **pre-commit:** a `repo: local` hook with `entry: lr check <project> --trust-declared --quiet`, `language: system` and `pass_filenames: false`. There's no packaged `.pre-commit-hooks.yaml` yet: that needs `lr` installable from the repository root, and the package lives in `engine/`.
- **Claude Code:** a `Stop` hook that runs `lr check <project> --trust-declared --quiet --stderr || exit 2`. Exit code 2 sends the report back to the agent, so it fixes the problem before stopping.
- **Other agents' hooks:** any hook that runs a command and reads its exit code works the same way.

**Dogfooding: `examples/arch-check`:**
- **Facts:** `ls` lists `engine/loopingrules`, and `grep` collects each module's relative imports.
- **Architecture (knowledge):** five ranked layers (core, model, runtime, sharing, front), and each module's layer.
- **Findings:**
  - an import from a higher layer;
  - a module with no layer.
- **Limitation:** imports are found with a regular expression on `from .x import` lines, so other forms of import are missed.

### D30. Matching on a pyoxigraph mirror; applications in a fixed order
*Status: built (2026-11-28). Code: `engine/loopingrules/mirror.py`; tests: `test_mirror.py`.*

**Why:** after lazy validation and overlays, matching operation patterns was most of a tick (74% on the Rubik solver). rdflib evaluates SPARQL in pure Python, and nested `FILTER NOT EXISTS` over knowledge is its slowest case. pyoxigraph (Oxigraph, in Rust) gave identical results on every operation pattern, 8–15× faster.

**What runs where:**
- **On the mirror:** operation `lr:where`s and guards (`lr:requires`), against sheet + knowledge; and steps (`lr:steps`, phase 2). A step runs with its state's net delta applied to the mirror, which is reverted right after.
- **On rdflib, as before:** postconditions (`lr:ensures`); controllers, which read the `lr:before`/`lr:inserted`/… graphs (D20); SHACL, since pySHACL needs rdflib. rdflib stays the source of truth.

**How:**
- **Sync:** the knowledge is loaded once per model load. The sheet is synced before each enumeration by diffing it against the last snapshot: O(sheet), but no write path (edits, tools, undo, acks) can be missed.
- **Terms map back to the rdflib terms they came from**, so templates instantiate exactly what's in the sheet. Oxigraph stores some typed literals in canonical form (`"1.50"^^xsd:decimal` as `"1.5"`), and the map accounts for that. *Limitation:* two sheet literals with the same canonical form are one term in the mirror.
- **Parameters (guards, steps)** must be bound everywhere, as rdflib's `initBindings` are:
  - **variables in scope** go in as Oxigraph substitutions, which also reach `UNION` branches. A `VALUES` join is evaluated after the union, and made a step 80× slower;
  - **variables only inside `FILTER (NOT) EXISTS`**, which substitutions refuse, are joined in with `VALUES`;
  - a blank node that would need `VALUES` (which can't hold one) falls back to rdflib.
- **Anything Oxigraph can't parse runs on rdflib**, and is listed in `Mirror.unsupported`. The equivalence tests assert that the examples have none.
- **Security is unchanged:** patterns are checked at load time (D11, D23), before either store sees them.

**Optional dependency:** `pip install -e ".[fast]"`. Without pyoxigraph, or when it can't load, the engine uses rdflib, with the same results. `LR_MATCHER=rdflib` forces it, and `lr serve` prints which matcher runs. *Windows:* Smart App Control blocks unsigned native modules without a reputation. pyoxigraph 0.5.0 and 0.4.11 load; 0.5.10–0.5.13 were blocked (2026-11-28).

**Applications come in a fixed order.** Within an operation, applications are sorted by their parameter values. Before, they came in the store's row order, which in rdflib follows Python's set order, so it changed with the hash seed. Oxigraph's order differs again. Ties go to the first application (Q3), so the same project could take different paths on different runs, and with different matchers. Now ties go to the operation IRI, then the parameter values in order.

**Measured** (`bench_rubik_solve.py`, seeds 3–5; `bench_folder_scan.py`, 20 files):

| | rdflib | mirror |
|---|---|---|
| Rubik, planning tick | 450–620 ms | 73–97 ms |
| Rubik, average tick | 173–216 ms | 68–81 ms |
| folder-scan, per tick | 56 ms | 33 ms |

Validating in place (pySHACL no longer copies the data graph) gave ~20% before this.

*Update (same day, Rubik stage 2):* with steps on the mirror and a cheap `__bool__` on `Overlay`/`Union` (pySHACL's `if graph:` was counting every knowledge triple), a Rubik tick averages ~36 ms (turns ~27 ms, planning ~65 ms) over two stages and 46 cases. See `doc/rubik.md`.

### D31. A planning pack: methods, stages, cases and procedures; modules talk through requests and answers
*Status: built (2026-11-28). Code: `examples/planning` (a library pack); tests: `test_d31.py` (a counter domain), `test_rubik.py` (the cube solved through the pack). Input: the Rubik solver (`doc/rubik.md`, "What the procedure needed"), and two points from the user: algorithms should be written as named procedures, and modules should talk by depositing requests and answers in the graph.*

**Goal:** a general pack for following a *method*: reach a series of subgoals, each by recognising the situation and carrying out a known procedure. It's procedural knowledge, written as data, as in a textbook. It's not search.

**Vocabulary** (`pl:`, `https://loopingrules.org/planning#`). The domain writes it as knowledge:

| Term | Meaning |
|---|---|
| `pl:Method` | `pl:firstStage`, `pl:view` (the views cases are recognised through) |
| `pl:Stage` | `rdfs:label`, `pl:goal` (conditions that must hold in every view), `pl:next` (none for the last stage) |
| `pl:Case` | `pl:stage`, `pl:when` (conditions), `pl:do` (a procedure), `pl:priority` (default 0) |
| `pl:Procedure` | `rdfs:label`, `pl:steps` (a list) |
| a step | one of: a **procedure** (call it); `pl:Repeat` (`pl:times`, `pl:do`); `pl:Until` (`pl:until` conditions, `pl:do`: check first, then run it again until they hold); anything else is a **primitive action**, for the domain |

**Modules talk through the sheet: requests and answers** (the user's design). The pack never reads the domain's state, and the domain never reads the stack:

| The pack deposits | The domain answers |
|---|---|
| `[] a pl:Check ; pl:run ?r ; pl:about ?x ; pl:condition ?c ; pl:view ?v` | `?check pl:result true\|false`, all pending checks in one application (`lr:params ""`) |
| `?run pl:doing ?action` | carries it out and deletes `pl:doing` in the same application, so the pack never asks about a state that hasn't changed yet |

- **This replaced the proposed engine feature (named patterns).** The domain's knowledge of how a condition is checked stays in the domain, with no engine change.
- **What it gives besides decoupling:**
  - the questions and answers are visible in the sheet;
  - anyone can answer: rules, a tool, or a person through `lr:in`.

**Orchestration:**
- **The order is in the preconditions.** Every operation waits through its own pattern: nothing pending, nothing being done, the right phase. The run's phase is `pl:Look`, then `pl:Question`.
- **A round of questions** takes 5 ticks:
  1. look;
  2. ask about the stage's goal and every case's conditions, in every view;
  3. the domain answers;
  4. decide: next stage or finish, plan a case, or stuck;
  5. forget the answers.
- **A procedure runs on a call stack of frames.** Call, repeat, until, dispatch an action and return are one tick each. `Until` asks about its conditions in the run's view, with the same request/answer round.
- **The only controller is `pl:casePriority`:** the highest-priority matching case goes first. Everything else is exclusive by its preconditions. Nothing depends on the order of names any more.

**Library packs** (engine change, `package.py`): a manifest with `lr:library true` and no `lr:extends` is a pack for any project. `lr add-layer` installs it anywhere, and importing it as a project is refused. The Rubik project carries an installed copy in `layers/planning`, and a test keeps it equal to `examples/planning`.

**The Rubik method on the pack:**
- The last layer is written as the textbook writes it, with named procedures: `sexy`, `sune`, `yellowCross` = (`F`, `sexy`, `F'`), and so on.
- Stage 7 is one case: *repeat 4 times: (until yellow is up: twist the corner), turn the top; then until aligned: turn the top*. The three cases, their priorities and the "same frame" rule of the previous version are gone. A case's procedure runs in the view it was planned in.
- The cube's side is three operations:
  - `rk:solve` starts a run;
  - `rk:answer` reads the cube for every pending check;
  - `rk:do` makes the move, and records `rk:Executed`, so the viewer and show packs keep working.

**Performance: what the build taught** (one solve, seed 3):

| Change | Solve |
|---|---|
| first working version | 111 s |
| decisions only mark `pl:decided`; `pl:forget` clears the ~1000 triples of answers (deleting them inside each candidate decision cost seconds per candidate) | 214 s* |
| expensive operations start from a positive phase triple; the cube's answer has self-contained `UNION` branches | 106 s |
| checks carry `pl:about`, so "a false check about this case" is one star pattern | **28 s** |

\* Slower at that step, because the phase fix wasn't in yet: every tick paid for the planning patterns.

**Rules for authors** (also in the pack's README). Oxigraph builds every candidate row before applying `FILTER NOT EXISTS`, and evaluates a `UNION` (and `EXISTS` bodies) without the outer bindings:
- start an expensive pattern from a positive triple that's missing when it doesn't apply;
- keep `UNION` branches self-contained;
- prefer star patterns on one node to joins inside `NOT EXISTS`.

A possible engine improvement: rewrite patterns to follow these rules, or evaluate `EXISTS` with the outer bindings.

**Cost now:** a Rubik solve is ~490–550 ticks, 29–39 s (the direct solver took ~170–200 ticks, ~6 s). Each move takes 2 ticks of ~50–60 ms, and moves are most of the solve. Options, if it matters:
- fold dispatch into the domain's action, which would be a second, direct protocol;
- make each tick cheaper: every tick matches ~20 pack operations plus the domain's.

**Bug found by the tests:** a run and a case both use `pl:stage`. A pattern that said `?case pl:stage ?stage` without `?case a pl:Case` matched the run itself, so "stuck" never fired. Patterns over cases now say `a pl:Case`.

## Open questions

- **Q3. Ties and no-ops.** Partly settled by D21: empty deltas are excluded except for no-op operations, and a tie between a no-op and an application with effects goes to continuing. Other ties: the first application, in a fixed order (operation IRI, then parameter values: D30).
- **Q4. Cost.** Scoring every resulting state is expensive. Options:
  - score against an overlay view (base + inserts − deletes) instead of copying the store;
  - for SHACL, validate only the shapes affected by the delta, or accept full validation in v0.
  - Default: accept full validation in v0.
- **Q5. Store.**
  - rdflib: slow, but pySHACL works with it natively.
  - pyoxigraph: fast and supports quads, but needs a bridge to SHACL.
  - Default: put the store behind an interface and start with rdflib.
  - Update (D30): rdflib stays the store; operation patterns match on an optional pyoxigraph mirror.
- **Q8. UI stack.** Default: React + Vite + a grid component (TanStack Table).
- **Q9. Persistence.** Default: save the sheet, model and controllers as Turtle files in a project folder.
