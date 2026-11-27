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
