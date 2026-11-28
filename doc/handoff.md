# Handoff: where LoopingRules stands, and what's next

*Written 2026-11-27, at the end of the first build session.*

*Updated 2026-11-28, at the end of the second session:*
- *The operations/controllers review became D20–D23 and is built.*
- *Performance work is paused after lazy validation and overlays (§5). The next option there is reusing matches across ticks.*
- ***Next focus: the UI and integration wishes in `doc/hmi_improv.md`**: a graph view, `in:`/`out:` channels, a tutorial written as rules, knowledge in packs, an MCP server, and pre-commit hooks.*

*Updated 2026-11-28, third session (`doc/hmi_improv.md` work):*
- *D24 (named graphs) was drafted, then **deferred**. Graphs don't scope names, and none of the planned features needs them.*
- ***D25 is built:** `lr:in`/`lr:out` channels as a convention (`channels.py`), listening autopilot, app mode (`lr:directEdits false`), the Messages panel, `lr run --listen`, and `examples/hello-channels`.*
- ***D26 is built:** the tutorial, `examples/tutorial` + `lr tutorial`, tested end to end in `test_tutorial.py`.*
  - *UI polish that came with it:* the sheet hides message triples (with a checkbox to show them), the Messages panel keeps the newest message in view, and `index.html` is served with `no-cache`.
  - ***Known rough edge:** the sheet scrolls to the first changed row, which in the tutorial is often the tutorial's own bookkeeping (`tut:Lx tut:presented true`), so the learner's `ex:` rows scroll out of view. Possible fixes: scroll only for edits the user made, or prefer changed rows of the user's namespaces.*
- ***D27 is built:** the Graph tab (`ui/src/components/GraphPanel.tsx`, lazy-loaded Cytoscape.js). `window.__lrGraph` exposes the Cytoscape instance for `scripts/dev/shot.py`.*
- *Also fixed: the CLI no longer crashes on cp1252 consoles or pipes (`main()` reconfigures the output streams to replace characters they can't encode).*
- ***D28 is built: everything is SPO.** Definitions are recognised by type (`definitions.py`). Everything else is read-only knowledge (`store.Union`, `Engine.view`). Packs carry complete features and can extend packs. Conflicts are refused.*
- ***D29 is built:** `lr check` (`check.py`), with exit codes 0/1/2, findings (`lr:Finding`), and `examples/arch-check`, which checks this repo's layering. Pre-commit and Claude Code hook snippets are in the README.*
- *Next session was going to be the MCP server. It's still open: its tools only post to `lr:in`, read `lr:out` and run (D25). Granting direct edits per project is still to be built.*

*Updated 2026-11-28, fourth session (the Rubik example, `doc/rubik.md`):*
- ***Built:** the four-part example, as a project plus packs:*
  - *`examples/rubik`: the project. The cube is 54 facelet colours; the geometry, frames and method are generated knowledge (`gen_geometry.py`, `gen_method.py`); `turn`, `scramble` and `reset` are operations.*
  - *`examples/rubik-viewer`: a pack plus a Three.js app (`app/`, Vite, port 5180). It only uses the channels, and an ack means "displayed".*
  - *`examples/rubik-show`: a policy pack. It holds the plan with a penalty, so a sync is never blocked.*
  - *The solver's first stage, the white cross (`solver.ttl`): the method is knowledge (cases = needs + algorithms, written with white on D and recognised through 4 frames), and the solver is 4 generic operations.*
- ***Engine fixes along the way:***
  - *an ack wakes a listening autopilot;*
  - *step templates see the operation's parameters even when the step's pattern doesn't mention them (regression test in `test_d22.py`);*
  - *`lr run --listen` runs again after acknowledging `lr:out`.*
- ***Paused at step 4, after stage 1 of 7.** Planning ticks cost ~500–600 ms with 23 cases. Profile: **matching 74%, SHACL 26%**. A full method has ~100 cases, so planning ticks would take ~2 s and solver tests minutes. The suite already went from 83 s to 160 s.*
- ***Next session: performance**, with the new matching-heavy benchmark `engine/benchmarks/bench_rubik_solve.py`. See §5, "Next: pyoxigraph for matching". Then resume `doc/rubik.md` step 4 with the corners stage.*

*Updated 2026-11-28, fifth session (performance):*
- ***D30 is built:** operation `WHERE`s and guards match on an optional pyoxigraph mirror (`mirror.py`, extra `[fast]`). Rubik planning ticks: ~500 → ~85 ms. See §5, "Done: pyoxigraph phase 1".*
- *SHACL validates in place: pySHACL was copying the data graph before every validation (~20% of a Rubik tick).*
- *Applications now come in a fixed order (operation IRI, then parameter values). Ties used to depend on the hash seed, so the same seed could solve in 13 or 17 ticks.*
- ***Next:** phase 2 (steps on the mirror) or incremental SHACL; see §5. We also discussed Rete and a Rust engine; both are deferred until we re-profile after these.*

## 1. State in one paragraph
LoopingRules is a working "semantic spreadsheet":
- **Engine:** a Python engine (rdflib + pySHACL). Operations are SPARQL `WHERE`/`DELETE`/`INSERT`; the SHACL shapes guard every result; controllers are SPARQL queries whose scores are summed; autopilot runs until nothing is applicable.
- **Interfaces:** a FastAPI server, a React/Vite UI, and the headless `lr` CLI.
- **Tools and safety:** a shell tool with per-call approval and a template allowlist stored per user, plus a security guard that refuses `SERVICE`/`FROM`.
- **Persistence:** an append-only journal with undo; authored files are never rewritten.
- **Sharing:** `.lr.zip` exports with manifests, and controller packs (layers).

There are 60 tests, all green, and the suite takes ~25 s. Every decision is recorded in `doc/design.md` (D1–D19).

## 2. Working agreements with the user (important)
- **Commits and PRs list only the user as author: no Claude co-author or attribution lines.** This overrides any default attribution guidance.
- **Discuss before building big things.** The user likes short design discussions with a recommendation, then builds.
- **Prefer conventions over engine features.** Goals were proposed with engine support, and the user rejected that: they are a pure modeling pattern (D16). No goals panel, no special handling. Apply the same instinct elsewhere: if something can live in the model, it should.
- **Models and controllers are pure data:** no user code, and sharing must stay safe (D9).
- **Light theme by default** (dark is a toggle). Keep the README screenshots up to date when the UI changes.

## 3. How to run things
```bash
# engine
cd engine && python -m venv .venv && .venv/Scripts/pip install -e ".[dev,server]"
.venv/Scripts/python -m pytest -q                       # 60 tests, ~25 s
.venv/Scripts/python benchmarks/bench_folder_scan.py    # perf baseline (see §5)

# UI
cd ui && npm install && npm run build                   # served by `lr serve`
# dev: `npm run dev` (port 5173) proxies /api to `lr serve` on 8765

# run
engine/.venv/Scripts/lr serve examples/folder-scan      # http://127.0.0.1:8765
engine/.venv/Scripts/lr run examples/folder-scan --yes  # headless
```

## 4. Map of the code
| Path | What |
|---|---|
| `engine/loopingrules/engine.py` | tick: enumerate → resulting state → SHACL → score → apply; tool phase; journaling (`_journaled`, `edit`, `undo`) |
| `operations.py` | parse operations; `enumerate_applications`; templates filled in Python; fresh nodes minted |
| `controllers.py` | SPARQL scoring; layers (`layer=` field) |
| `validation.py` | pySHACL wrapper; violations compared against the current state (an application is invalid only if it *adds* violations) |
| `store.py` | `copy_graph`, `apply_delta`, `prologue`, **`prepared()` query cache** |
| `project.py` | project folder, `.lr/` journal + snapshot, undo, minting (`gen:`), layers |
| `package.py` | export/import, manifest (`lr:mayRun`, `lr:extends`), `add_layer` |
| `security.py` | refuses `SERVICE` / `FROM`; disables `SPARQL_LOAD_GRAPHS` |
| `trust.py` | allowlist templates (`'{}'` = one quoted argument), stored per user |
| `suggest.py` | SHACL-driven autocomplete |
| `api.py` | FastAPI + WebSocket; `Session._mutate` diffs and broadcasts |
| `cli.py` | `apps`, `run`, `serve`, `export`, `import`, `add-layer` |
| `ui/src/` | `App.tsx`, `components/` (Sheet, Applications, Sidebar, ApprovalBanner, Combobox, TermView) |
| `examples/` | `folder-scan` (0.2.0), `folder-scan-goal`, `big-folders` (controller pack), `hello-channels`, `tutorial`, `arch-check`, `rubik` + `rubik-viewer` (pack + Three.js `app/`) + `rubik-show` (policy pack) |
| `engine/benchmarks/` | `bench_folder_scan.py` (growing sheet), `bench_rubik_solve.py` (matching-heavy) |
| `exports/` | downloadable `.lr.zip` examples, generated with `lr export` |
| `scripts/dev/` | `drive.py` (drives a running server via the API), `shot.py` (headless Edge over CDP → PNG) |

## 5. Performance: findings and plan

### Measured (`engine/benchmarks/bench_folder_scan.py`, stub shell, no disk)
| files | ticks | triples | before | after query cache | ms/tick after |
|---|---|---|---|---|---|
| 5 | 16 | 61 | 8.3 s | 0.8 s | 53 |
| 10 | 32 | 123 | 24.6 s | 2.6 s | 82 |
| 20 | 62 | 238 | 91.1 s | 13.7 s | 221 |

- **Before:** profiling showed **~88% of the time was SPARQL parsing and translation**: 1,065 parses of the same few strings in a 32-tick run. That cost had been blamed on SHACL; validation was only 5–12% and graph copying 1–3%.
- **Fixed** (commit "Parse each SPARQL query once"): queries are prepared once (`store.prepared`, an LRU cache), and DELETE/INSERT templates are parsed once and filled in Python.
- **Now: SHACL validation is ~60% of the time** and graph copying ~15%. Cost per tick still grows faster than linearly with sheet size: there are more candidates *and* each candidate costs more.

### Update 2026-11-28: steps 1 and 2 done
| files | ticks | before (eager, copies) | lazy validation | + overlay |
|---|---|---|---|---|
| 20 | 62 | 12.8 s | 5.4 s | 4.1–5.6 s (noisy) |
| 40 | 122 | — | 41.2 s | 19.6 s |

- **Lazy validation** (`Engine.pick`): autopilot scores every candidate and validates in score order, stopping at the first valid one. `test_lazy_pick.py` checks that it matches `choose(applications())` at every tick. `applications()`, used for the UI, still validates everything.
- **Overlay** (`store.Overlay`): resulting states are views, not copies. pySHACL accepts them.
- **New profile at 40 files:**
  - matching operation `WHERE`s: ~57% (rdflib evaluating `FILTER NOT EXISTS`);
  - scoring: ~24%;
  - SHACL: ~18% (one validation per tick, plus the baseline when needed).
- **So steps 3–4 below (incremental SHACL, cross-tick validation cache) now target only ~18%.** The big remaining cost is matching. Options, to be discussed:
  - (a) incremental matching of the D23 subset (Rete-style);
  - (b) match against a pyoxigraph mirror of the sheet;
  - (c) cross-tick reuse of matches for operations the last delta can't affect.

### Next steps, in order (measure after each one with the benchmark)
1. **Validate lazily.**
   - Autopilot only needs the best *valid* application: score every candidate, sort, and validate in descending order, stopping at the first valid one. That turns roughly A validations per tick into about 1.
   - The UI/API still shows validity for all candidates. Compute it lazily or in the background, e.g. return scores first and mark validity "checking", or validate only the visible top K.
   - Careful: today `applications()` scores **only valid** applications, and scoring is cheap, so the order of the two steps flips.
2. **Use an overlay instead of `copy_graph`.** A read-only view of base − deletes + inserts, used for scoring and validation. rdflib needs a small custom Store or a `ReadOnlyGraphAggregate`-style wrapper. Check that pySHACL accepts it, or that it's cheap to materialise only for validation.
3. **Validate incrementally.**
   - Pass `focus_nodes` to pySHACL (supported in 0.40) with the nodes the delta touches plus one hop. This is needed because `sh:class` reaches the object's type and `sh:in`/`sh:datatype` reach values.
   - Fall back to full validation when shapes use complex paths or SPARQL constraints.
   - Keep the "only *new* violations" rule (the baseline is the current state's violations, cached per tick).
4. **Cache across ticks.** Most applications survive a tick unchanged. Reuse their validation result when their focus region wasn't touched by the applied delta. Scores are global aggregates, so they can't be reused safely; just re-score.
5. **Only if still needed: a faster store.** Oxigraph (pyoxigraph) for SPARQL, with SHACL Core compiled to SPARQL ourselves, since pySHACL needs rdflib. This is a big step; decide it from numbers.

### Also worth knowing
- **Prologue churn:** `prologue(model, sheet)` text changes whenever the sheet gains a namespace binding, which creates new cache entries. It's harmless but visible in the cache. Consider a stable prologue built from model + controllers only.
- **Journaling diffs:** `Engine._journaled` diffs `set(sheet)` before and after tool calls and edits, which costs O(N) per call. It's fine at current sizes; record the deltas directly if it shows up in profiles.
- **`api.Session._mutate`** also diffs the whole sheet on every mutation, for UI highlighting. Same remedy: have the engine return the delta.
- **Benchmarks:** add a bigger generated case, e.g. 100 and 500 files, once the steps above land, and consider a pytest-benchmark smoke test with a generous threshold so regressions are noticed.

### Next: pyoxigraph for matching (added 2026-11-28, fourth session)
**There are now two benchmarks, with different profiles:**

| Benchmark | Workload | Profile |
|---|---|---|
| `bench_folder_scan.py` | a growing sheet; each tick touches a few triples about one file | matching 57%, scoring 24%, SHACL 18% (at 40 files) |
| `bench_rubik_solve.py` | a small sheet (~360 triples) plus ~1,000 knowledge triples; every turn rewrites 20 colours, and the planning ticks match 23 cases × 4 frames with nested `FILTER NOT EXISTS` | matching 74%, SHACL 26%; turn ~110 ms, planning ~550 ms per tick |

**What each option buys:**
- **(c) Reusing matches across ticks** helps folder-scan, but almost nothing on Rubik: every turn changes colours that every case reads.
- **(b) A pyoxigraph mirror for matching** helps both. Rubik's expensive queries are exactly what rdflib evaluates slowly.
- **(a) Rete** is the bigger build. Keep it for later, if (b) isn't enough.

**Recommended first step: a time-boxed trial of (b).**
- Keep a pyoxigraph store in sync with sheet + knowledge, by applying each delta and loading knowledge once.
- Evaluate operation `WHERE`s, steps and guards there. Controllers and SHACL stay on rdflib.
- Points to check:
  - **overlays:** steps query the state earlier steps left; insert/delete on the mirror and roll back, or materialise per application;
  - **term round-tripping** (literals, datatypes, minted IRIs);
  - **the security check** (`SERVICE`/`FROM` must stay refused);
  - **identical results:** `test_lazy_pick.py` style, comparing against rdflib at every tick.
- **Measure both benchmarks before and after.**
- **SHACL (the remaining 26%):** incremental validation with `focus_nodes` (step 3 above) is the separate fix.

### Done: pyoxigraph phase 1 (2026-11-28, fifth session; design D30)
- **Built:** `WHERE`s and guards on the mirror; equivalence tests at every tick of folder-scan (with and without the pack), folder-scan-goal and a Rubik scramble + solve (`test_mirror.py`).
- **Results:** Rubik average tick 173–216 → 68–81 ms (planning ~500 → ~85 ms); folder-scan, 20 files, 56 → 33 ms/tick.
- **Gotchas found on the way:**
  - **Smart App Control** blocks pyoxigraph 0.5.10–0.5.13 here ("un criterio di controllo dell'applicazione ha bloccato il file"). The venv has 0.5.0.
  - **Oxigraph canonicalises typed literals** when it stores them; the mirror maps them back to the sheet's own terms.
  - **Oxigraph refuses substitutions for variables a pattern doesn't have in scope**, and rdflib binds `initBindings` inside `FILTER NOT EXISTS` too: guards use `VALUES` instead (`test_d22` caught this).
  - **Row order differs between the stores** (and in rdflib, with the hash seed): applications are now sorted by parameters. `bench_rubik_solve.py` still pins `PYTHONHASHSEED=0` for other set orders.
- **Now a Rubik turn (~70 ms) is the slowest tick.** What's left: steps on overlays (rdflib), SHACL (one validation per tick), scoring, and the O(sheet) diff to sync the mirror.

### Next options (re-profile first)
1. **Phase 2: steps on the mirror.** Apply each application's overlay delta to the mirror, run the step, revert. Steps were ~3 s of an 18 s profiled run.
2. **Incremental SHACL** (`focus_nodes`, step 3 above).
3. **A bigger folder-scan** (500+ files): the mirror is a constant factor, while cost per tick still grows with the sheet. That's where incremental matching (Rete, or DBSP/Differential Dataflow over the D23 subset) would pay off.
4. **A Rust engine (store + SPARQL subset + SHACL + incremental matching):** discussed and deferred. Prove the incremental algorithms in Python first, then port them, building on Oxigraph's crates (`oxrdf`, `spargebra`) and rudof (SHACL).

## 6. Other open items (not performance)
- Query time limits for shared models (D18 to-do).
- `lr:extends` matches the base package title only: no version pinning, and packs can't extend packs (D19).
- Loop detection as a warning: incremental hash of the state per tick; minted names now make this simpler (D8).
- CLI smoke tests. The CLI isn't covered by tests, and twice a `\n` written through a shell heredoc broke `cli.py` without any test failing.
- Named graphs (full SPOG), and learned controllers (`doc/info.md`): later.

## 7. Gotchas from this session
- **Line endings: LF everywhere**, enforced by `.gitattributes` since 2026-11-28. Before that the repo mixed CRLF and LF, and edits on Windows kept flipping whole files. If `git diff --stat` shows a whole-file change for a small edit, check the endings. The normalization commit is listed in `.git-blame-ignore-revs`.
- **Shell heredocs vs escapes.** Writing Python through `cat <<'EOF'` / `python - <<'EOF'` turned `"\\n"` into real newlines several times. Prefer the Edit/Write tools for code that contains escapes.
- **Stopping `lr serve` started in the background:** stopping the bash wrapper can leave the Python child holding port 8765. Kill by port, e.g. `Get-NetTCPConnection -LocalPort 8765 -State Listen | % { Stop-Process -Id $_.OwningProcess }`.
- **Demos and screenshots:** run demo servers with `LR_TRUST=<scratch file>`, so the user's real `~/.loopingrules/trust.ttl` isn't touched, and delete the demo project's `.lr/` for a fresh state.
- **Headless screenshots** (`scripts/dev/shot.py`) need `Emulation.setFocusEmulationEnabled`, or focus/blur events (and so the dropdowns) misbehave.
- **The UI top bar has `backdrop-filter`, so it needs `position: relative; z-index`** or its menus get painted over by the panels.
- **The `lr` launcher in Git Bash** can fail with "Permission denied"; `python -m loopingrules.cli` always works.
- **rdflib SPARQL strings:** avoid backslash escapes in regexes inside Turtle `"""…"""` blocks; use character classes (`[.]`, `[^0-9]`).
