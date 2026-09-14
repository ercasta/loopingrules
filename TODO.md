# TODO

Open threads out of `loopingrules/circuits.py` (see README History,
"circuits.py: a closed shape catalog" and "circuits.py promoted to
core"), named so they are not lost rather than scheduled.

- ~~`check_goal`'s fold.~~ Done: `ActionCircuit` (a seeded `GoalCheck`
  marker, consumed) + `Any`/`Forall` for the quantifier over `CardDef`/
  `Wants` the condition asks about. (A first attempt used a fourth rule
  shape, `WorldCircuit`, guarding "don't fire twice" by self-reference;
  removed once it turned out to be a strict special case of
  `ActionCircuit` with a seeded marker -- see README History, "don't
  fire twice is consuming a component.")
- ~~`patterns.loop_count`'s aggregate.~~ Done: `Count(over, condition)`
  (a number, not a boolean -- `Any`/`Forall`'s sibling) plus `Children
  (base, fk_field, component)`, the one-to-many scope `Via` cannot
  reach (a `Function`'s `Body` names ONE entity, but that entity carries
  MANY `Stmt`s), plus `HasSelf(component)` for "does the entity
  currently being counted carry this."
- ~~`hear_list`'s parsing.~~ Tried, and it DOES reduce, exactly, with
  `Lower`/`Split`/`At`/`Len`/`ParseInt`/`FindBy` (six new primitives) and
  a ten-spec decomposition (two `ValueCircuit`s computing `ListParse`/
  `ListResolved`, four `TagCircuit`s for the four mutually exclusive
  outcomes, four `ActionCircuit`s acting on them). All four outcomes
  (wrong arity, unknown card, bad price, a real `Listing`) reproduced
  exactly, including the specific wording of each `BadCommand`. Originally
  verdicted here by RAW COUNT ("six primitives, ten specs -- the worst
  ratio tried") -- corrected: count is not the metric `PRINCIPLES.md`
  asks for. Each of the sixteen pieces is individually as simple as
  anything else in this catalog; the one real, specific cost is that the
  four outcomes' mutual exclusivity is now a hand-authored invariant
  across four independent conditions rather than an if/elif chain's
  free guarantee -- checked directly now, not just asserted (`tests/
  test_circuits.py::test_hear_list_outcomes_are_structurally_mutually_
  exclusive`). See README History, "count was the wrong metric."
- ~~`hear_want`'s parsing.~~ Same four-outcome shape as `hear_list`,
  with one new wrinkle: its success effect replaces a component on an
  entity FOUND BY NAME (`FindBy`), not one reached by a stored field --
  which `ReplaceVia`/`ReplaceWorld` could not do at all. Generalized
  into one `ReplaceAt(at, component, fields)` instead of adding a third,
  narrower effect -- `ReplaceVia`/`ReplaceWorld` turned out to both be
  `ReplaceAt` with a specific `at` already baked in, so they are gone,
  not kept alongside it. `If(condition, then, else_)` also added --
  defaulting an omitted quantity to `1` depends on WHICH case holds, not
  on a read coming back `MISSING`. See README History, "one Replace
  effect, not three."
- ~~`hear_status`'s parsing.~~ A different shape from the other two --
  no wrong outcome to reject, just one report to build, needing a
  variable-length, SORTED piece of TEXT from an unbounded set (every
  wanted card, alphabetically) that nothing built so far could produce.
  `Join(over, expr, sep, sort_by=None)` (`Any`/`Forall`/`Count`'s
  sibling, reducing a set to text instead of a boolean or a number),
  `Optional(condition, expr)`, `JoinStrings(sep, exprs)` (a handful of
  known pieces, some conditionally present, assembled with one
  separator). Only two specs needed -- the flattest decomposition of
  the three `hear_*` rules, despite needing the most genuinely new
  machinery. See README History, "hear_status's report."
- ~~The three `reply_*` rules.~~ The simplest shape yet -- claim, destroy,
  spawn a `Reply` -- needing one new primitive, `SelfId()` (`ReplaceAt`'s
  target when an effect acts on the entity its OWN `ActionCircuit`
  matched, `reply_goal_met`'s `w.attach(entity, Announced())`). Caught
  a real bug in it before trusting it: `SelfId` first returned the
  `Entity` HANDLE `entity` may actually be bound to, not the plain int
  every other read in this catalog resolves to -- found by a unit test
  that compared the two, not by inspection. Also surfaced, and pinned
  rather than smoothed over: `reply_bad_command`/`reply_bought` loop
  over EVERY match in the original (several `BadCommand`s/`Bought`s can
  coexist in one tick); an `ActionCircuit` only ever acts on the first.
  Converges to the identical FINAL set of replies either way -- but
  when `cards.decide_buy`'s own real batching produces two `Bought`s at
  once, `reply_goal_met` can now fire IN BETWEEN the two replies instead
  of after both, because two independent one-match-per-tick queues are
  competing for tick slots instead of one rule draining both in a
  single pass. Same SET, different ORDER -- checked directly (`tests/
  test_circuits.py::test_reply_bought_reaches_the_same_final_replies_
  but_not_the_same_order_when_batched`), the sharper, compounding cousin
  of the bullet below.
- **`decide_buy_spec` drops the batching `cards.decide_buy` still does**
  (one match per tick, not several). Correct, per README History, but a
  real behavior change if this were ever adopted for real rather than
  tested against it -- worth re-flagging if it is. Now known to compound
  when composed with another reduced rule reading its output (see the
  `reply_bought` bullet above) -- not just decide_buy's own tick count,
  but cross-rule reply ORDER.
- ~~Whether any of this is worth promoting past a prototype.~~ Promoted
  (2026-09-06) -- `loopingrules/circuits.py`, ahead of this repo's own
  usual bar (every prior promotion waited for a second domain to
  actually depend on the thing at runtime; this one didn't), on the
  strength of cross-repo evidence alone. See README History, "circuits.py
  promoted to core." What's still genuinely open, now that it ships:
  nothing yet actually WRITES a rule as one of these specs outside a
  test file -- `cards.install()` still registers its own thirteen
  hand-written rules, unchanged, and no domain (in this repo or
  `pystrider`) has adopted the catalog for real. Promotion answered
  "is the catalog sound," not "does anyone use it."
- **The `check_goal`-shaped `stable=`/false-positive-in-`check_watches`
  question, and every other `loopingrules.analyze` finding from the
  `pystrider` audit, are still just conversation, not code.** The
  6-bucket breakdown (avoidable DRY, `pystrider.rules`'s own capability-
  stripping sibling solution, deliberate genericity, real computation)
  lives in this README's History only -- nothing forces `analyze.py`'s
  own method vocabulary to learn `purge_transient`, and no `pystrider`
  rule was actually rewritten. 32 of 51 real `pystrider` rules audited
  analyzed cleanly; `patterns.py`/`constraints.py` specifically (the
  ones this catalog is built on) were 100%. Left for whoever next wants
  the map more complete than that.
- **Whether `examples.judge.Risk` is general enough to promote into
  `loopingrules/`.** `examples/shopping.py` (see `README.md` History,
  "the second domain `examples.judge`'s `Risk` has ever had to serve")
  is a second, deliberately different data point, and it held -- but one
  more independently-motivated domain agreeing is not yet the same bar
  `circuits.py` waited for (a second domain actually depending on it AT
  RUNTIME, not just in a test file feeding it on purpose). Still open:
  does a THIRD domain, picked without trying to make `Risk` work, also
  fit the same `level`/`reason` shape -- and if `Risk` does get
  promoted, does it keep its name, or does "risk" stop being the right
  word once a shopping list is calling the same field "urgency"?
- `shopping.NeededBy` has no command to clear it once set -- a
  deliberate gap, the same shape as `cards.py`'s "selling," not
  something forgotten.
- **`circuits.Call` -- a spec can now dispatch, by name, to a
  pre-registered Python tool, proven against real disk I/O in
  `examples/files.py` -- but nothing has actually authored a spec
  through anything other than Python yet.** The motivating question
  ("confine free Python to tools, keep rules as data an untrusted
  author cannot turn into arbitrary code") is answered at the
  MECHANISM level -- `tool` is a literal string, resolved against a
  caller-supplied registry, checked eagerly at `compile_circuit` time;
  a tool receives only already-evaluated data, never a live `Entity`,
  never a callable (see `Call`'s own docstring, and `tests/
  test_examples_files.py::
  test_call_hands_the_tool_a_plain_int_never_a_live_entity`, which
  checks this rather than assumes it) -- but the SURFACE a genuinely
  untrusted author (a person, an LLM) would actually type specs
  through does not exist: `do_stat_spec` is still a Python literal, in
  a file only someone who can already write Python edits. A YAML (or
  other human-friendly) loader onto these same dataclasses was
  discussed and deliberately deferred -- see `README.md`'s History,
  the entry that added `Call` -- until a real authoring workflow needs
  one, the same "grow it only at the rule that actually collides"
  discipline `DECISION_PATTERNS.md` already states. ~~`Call` invokes
  the tool in place, inside `ActionCircuit`'s own atomic write phase.~~
  Done (2026-09-14) -- `Call` now spawns a `ToolRequest`, and a new
  `compile_answerer(tools)` is the one rule that actually calls
  `tools[tool](w, *args)`, on whichever later tick sees the request;
  see `README.md`'s History, the entry that built
  `DECISION_PATTERNS.md`'s 2026-09-13 design. Still open from THAT
  entry: whether `compile_answerer` should be auto-installed by
  `compile_circuit` itself (every caller that passes `tools=` hand-
  writes its own `loop.rule(circuits.compile_answerer(tools))` today,
  `examples/files.py::install` the only example) rather than a second
  call a caller could forget; and `confirm=True`/approval, entirely
  unbuilt -- `Rejected` exists for a tool that is unregistered or
  raises, not for one that is waiting on a human to say yes.
- **`reads()`/`writes()` no longer raise `Opaque` for a `Call`-bearing
  spec -- the opacity moved to `compile_answerer`'s own rule, and
  IT is coarse the same way `circuits.py` used to be.** A tool that
  only ever touches one or two known component types (`stat` only ever
  touches `Size`/`Modified`/`Failed`) gets the same total `analyze.
  Opaque` refusal, from `loopingrules.analyze`, as one that could touch
  anything -- neither `circuits.py` nor `analyze.py` has a way for a
  tool's REGISTRATION to declare what it reads/writes. Worth doing only
  once something downstream actually wants a non-`Opaque` answer for
  the answerer rule -- `component_map()`-style tooling, say -- nothing
  does yet.
- **A YAML surface plus an examples-driven evolution search over a base
  rule set, with author-frozen rules held fixed.** Designed, not built --
  see `DECISION_PATTERNS.md`'s 2026-09-10 entry for the YAML mapping onto
  `circuits.py`'s closed catalog, the `frozen:` contract, and the
  add/modify/delete search's scoring (reusing this file's own
  `ruled_out`/`ranked`/Forced/Ambiguous/Unresolved vocabulary rather than
  inventing a new one). Picks up both this repo's own deferred YAML
  loader (see the `circuits.Call` bullet above) and the 2026-09-07
  "examples in, spec out" thread, generalized from one synthesized spec
  to a whole set.
