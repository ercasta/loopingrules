# Decision patterns - agency without a backward-chaining engine


## The claim

Backward-reading a recognition rule to get a generation rule is not a valid move: 
`structure -> effect` does not invert into `effect -> structure`
any more than "wet -> rained" licenses "rained -> wet" as the *only* way to get wet. What a generation
capability actually needs is its own, independently authored **forward** rule -> antecedent *wanted
effect*, consequent *this structure* - running on the exact same substrate as recognition. Nothing
about "goes in the backward direction" requires an engine that reads backwards.

Everything below is that idea, pushed until it broke or didn't: propose facts, arbitrate over sets of
facts, run to a fixpoint. No goal stack, no unification, no CNL, no new engine.

## Already proven, not just argued

Every piece of this pattern was already doing real work in `pystrider` - a sibling repo,
`../pystrider` next to this checkout, that reads and writes Python by reasoning straight through
a `loopingrules.world.World` (no vocabulary layer in between; see its own `pyproject.toml` note,
"`ugm` IS GONE") - before this note was written. The module names below are that domain's, cited
as EVIDENCE that each piece was load-bearing somewhere real, not as code you will find beside this
file:

- **Goal-as-antecedent** - `pystrider/repair.py`'s `relax`/`lower`: `wants(unmet) -> specific edit`.
  Not derived by inverting a recognizer; hand-authored, the same way `patterns.py`'s recognizers are.
- **Composability by disjointness** - `pystrider/demos/playground/design.py`'s `check_interference`:
  "the placed widgets compose iff their writes are pairwise disjoint." Two candidates need no shared
  awareness to combine safely; they need disjoint `(entity, component)` footprints, a structural,
  generic test.
- **Refuse rather than guess** - the same `design.py`'s `resolve_screen`: a decision point with more
  than one satisfying candidate is **Ambiguous**, not resolved by taking the first. This repo's own
  instance of the same discipline is `loopingrules.analyze`'s and `loopingrules.circuits`'s `Opaque`
  - a different question (what a rule touches, not which candidate wins) answered the same way:
  refuse, named, rather than under-report.
- **Subgoaling with no subgoal machinery** - `pystrider/repair.py`'s `ask`/`answer`/`checked`: `ask`
  deposits a bare request (`evaluate(function, case)`), `answer` watches for it and answers when it
  can (or deposits its refusal, `could_not_evaluate`, rather than staying silent), `checked` reads the
  answer back. None of the three call each other. The loop's "run everyone, every tick, until nothing
  changes" *is* the dispatch.
- **Free transitive propagation** - `pystrider/effects.py`'s `transitive()`: `outer` calls `inner`,
  `inner` has an effect, so `outer` does too - one more rule reading the same fixpoint, not new
  machinery.
- **A generic reader over proposals, already shipped here, but a narrower one** -
  `loopingrules.world`'s `Proposal`/`propose`/`reply`/`arbitrate`/`census`, used for real by
  `loopingrules.help`'s `arbitrate_help`. This is the shape the vocabulary below generalizes, not a
  finished instance of it: `arbitrate` today is "first registration wins, every other candidate is
  destroyed" and `census` is "every candidate counts" - neither knows about `ruled_out`, `ranked`,
  `needs`, or a `winner` distinct from "whoever got there first." A domain that needs the fuller
  contest below writes its own components and its own generic reader over them, the way
  `pystrider.repair` already does for its own occasions - see this repo's own `README.md`, "no
  vocabulary above entities and components either."

## The vocabulary

For one contested decision point (an *occasion* - an entity, or a `reify()`d proposition):

| relation | shape | written by | meaning |
|---|---|---|---|
| `candidate(occasion, option)` | monotonic | any proposer, unaware of rivals | *this is one way to resolve it* |
| `realizes(option, property)` | monotonic, transitive | any proposer | the justification chain a judge reasons over - `pizza realizes carbs`, `carbs realizes energy` |
| `ruled_out(occasion, option, reason)` | monotonic, never retracted | a hard-constraint judge | a categorical, named veto |
| `ranked(occasion, option, ...)` | monotonic | a soft-preference judge | orders survivors; never eliminates one |
| `winner(occasion, option)` | `state()`d | the one generic commit step | eligible-minus-ruled-out, top-ranked |
| `needs(occasion, information)` | monotonic, idempotent | a blocked judge | an explicit, inspectable request - not silence |

A judge writes `ruled_out`/`ranked`/`needs` about a `candidate`; it never has to know which other judges
exist, only the vocabulary (`realizes`, or whatever property it reasons in) the candidates are described
in. A judge that finds no chain from a candidate to its own vocabulary abstains on that candidate - the
same discipline `patterns.py` already uses for `readable`: silence, not a guess.

## Composability is a structural test, not luck

Two candidates compose for free - both stand, no arbitration needed - exactly when their delta
footprints are disjoint `(entity, component)` pairs. That's `check_interference`, generalized past UI
widgets. Overlapping footprints are the only case that ever needs a judge's attention; today's
`repair.py` treats *every* case this way, arbitrating by bare registration order, and its own docs
record the cost: `gated=False` makes `relax` and `lower` both fire on one bug, "correct by luck and
wrong as a repair." That's what happens when agency lives in the base rule instead of in one generic
reader of the candidate set.

## Elimination and ranking are different things, kept apart on purpose

A hard veto (`ruled_out`) and a soft preference (`ranked`) could collapse into one numeric score (a
veto is just rank = negative infinity), but that throws away exactly what this project's decisions already insist on -
a *named* reason (`interferes_with`, `uncovered`, `detail`), not an opaque number. Keeping them separate
also buys safety for free: elimination only ever shrinks the candidate set (an ordinary monotonic
write - `w.attach`, never a retraction),
so a chain of judges - *pizza beats ice cream on preference, then diet rules pizza out* - can't cycle
back to a prior answer, because nothing is ever un-ruled-out. That's `nothing`'s whole win in the pizza
example: not chosen by override, just never eliminated once everything ahead of it was.

**Four verdicts at commit time**, not three - `resolve_screen`'s Forced/Ambiguous/Unresolved plus one:

- **Forced** - exactly one candidate survives elimination and leads the ranking.
- **Ambiguous** - more than one ties; refuse, the same way `resolve_screen` already does for its own
  Ambiguous case.
- **Unresolved** - every candidate was ruled out, and the occasion declared no fallback (`is_default`,
  or an always-eligible `nothing`) of its own. Distinct from a *declared* fallback winning - that's an
  ordinary Forced.
- **Pending** - a `needs` request is still open when the world settles. Not a hang (`Loop.run` reports a
  clean settle either way) and not the same as Unresolved: *someone might still answer this.*

## Observability comes from the substrate

Every relation above is deposited with the same plain `World` writes this repo already ships -
`w.attach`/`w.replace` - the way `pystrider.patterns`/`pystrider.repair` already write onto a
`loopingrules.world.World` directly, with no fact/state layer in between (see `pystrider`'s own
`pyproject.toml` note, "`ugm` IS GONE"). Nothing in `World` lets a rule hide a conclusion in a local
variable - `attach`/`replace` write onto an entity, not into a return value. So the trace of a decision -
which candidates existed, what ruled each one out, who won - is just `w.each(Candidate)` /
`w.each(RuledOut)` / `w.the(Winner)`, the same generic `each`/`the`/`show` reads `world.py` already
exposes for anything else, regardless of which rule wrote them. 

## Non-goals

- No SLD-resolution-style backward search, no unification, no choice-point/backtracking stack. A
  "goal" here is not a first-class thing the engine manages - it's an ordinary fact a judge's ordinary
  guard is checking for, the same as every other fact.
- No score that swallows a categorical veto and a soft preference into one number.

## What building it settled, and what it did not

*What is an occasion, generically?* - **anything the caller mints, and the module does not
care.** In a previous version, `commit` iterated `world.each(Candidate)`, so an occasion was just whatever entity a
`candidate` was deposited on: a `node()`, an interned `word("decision:screen")`, a `reify()`d
proposition. No registry of decision points, and nothing to generalize past.

**Settled, by deletion.** *Should `needs` be a relation?* - **no.** A judge that lacks information
asserts an ordinary fact and some unrelated rule answers it; `commit` needs no code at all for this,
because unblocking is "the guard read false, now it reads true," the same as every rule, always.
The `Pending` verdict argued for below was not built, for the same reason.

## Not built: chart parsing, where the winner is a whole interpretation

Everything above (`arbitrate`, `census`) resolves ONE occasion at a time:
either exactly one candidate wins outright, or every candidate stands,
independently, side by side. Neither shape fits a sentence like *"there
are two loops in function `a`. Delete the first one."* - "the first one"
is not a fact any single rule can propose on its own. It is the OUTCOME
of composing several: which loops exist in `a` (a per-loop `Iteration`
recognizer), what order they come in (an ordering over `Span`, see
`pystrider/spans.py`), and which one "the first" - a phrase in THIS
sentence - resolves to, given that ordering. No one candidate is "the
first loop"; only holding all three together is.

That is chart parsing's own shape (Earley/CYK, the classical technique
this is named for): a constituent is a claim about a SPAN, and a bigger
constituent is built by COMBINING smaller ones over adjacent or nested
spans - never generated whole by one rule in one step. Ported into this
package's vocabulary: `Proposal(occasion)` today claims "one candidate
resolves this one occasion"; chart parsing additionally needs a claim of
"these several already-resolved occasions combine into one bigger one" -
so what `arbitrate`/`census` hand back as "the winner" is sometimes not a
leaf proposal at all, but a whole assembled tree of them.

Genuinely not designed past this note - flagged as a real gap, not a
nice-to-have, because a request shaped like the example above is
ordinary, not an edge case, for any domain (`pystrider` first) that
means to understand what a person actually asked for and not just
recognize isolated facts about one thing at a time. Open: whether this
wants a THIRD verb alongside `arbitrate`/`census` (a `compose`, say), or
whether it falls out of `census` plus a domain-authored rule that reads
several already-censused results and proposes a NEW, larger occasion
spanning them - the second reuses everything that already exists and
costs nothing new here, so it is the version to try first if anyone
picks this up.

**Still open.**
- Does a `ranked` judge ever legitimately need to see *why* something was `ruled_out` (not just that it
  was), or is the boundary between the two total?
- Should "no fallback declared" be something every occasion author states explicitly, or should the
  generic commit step supply a bare "Unresolved, no default" verdict when none was declared? As built,
  `commit` reports `unresolved` and an author who wants a fallback proposes it as an ordinary candidate
  that survives every veto.
- `ranked` scores default to `0` for an unranked eligible candidate, so an explicitly *negative* rank
  sorts below silence. Nothing has needed a negative rank yet; the day one does, that default is the
  thing to look at first.

## 2026-08-31 - in parsing, nothing "wins"; interpretations fade out

A pushback on the vocabulary above, prompted by re-reading the chart-parsing note. `winner(occasion,
option)` names a decision a commit step makes, explicit and final - a contest with a declared outcome.
Parsing doesn't work that way. A chart holds every interpretation that combines cleanly, in parallel,
for as long as nothing needs to pick between them. A bad interpretation isn't ruled out by some judge
weighing it against rivals; it just stops producing anything, because no further rule's antecedent is
satisfied by it - it makes no meaning, so nothing downstream fires on it. It doesn't lose. It fades out.

So "winning" may not be a fact about parsing itself at all - it's a fact some *domain* rule imposes when
IT needs a single answer (`pystrider`'s "delete the first loop" needing exactly one referent for "the
first," from the 2026-08-30 note above). Chart parsing's own contest-free default - an interpretation
simply goes quiet for lack of anything to trigger - might be the right base case everywhere, with
`winner`/`ruled_out` reserved for the occasions where a domain rule actually needs to force a pick.
Not resolved - flagged so the open "third verb" question above (`compose`, or `census` plus a
domain rule) isn't answered in the wrong vocabulary: composing interpretations and picking a winner
among them look like they want to stay two different verbs, not one.

## 2026-09-07 - not built: rules as world data, examples in, spec out, never reflection in between

Prompted by a conversation asking whether `loopingrules.circuits`'s specs (`TagCircuit`/`ValueCircuit`/
`ActionCircuit`, promoted 2026-09-06, see `README.md` History) should live as entities and components in
the `World` itself, rather than as plain Python values - with some rule or process watching for one and
turning it into a live, registered rule. Worked through, not built, because the two halves of that
question have different, and differently-sized, answers.

**Embedding a spec's own tree as entities costs more than it looks like it should.** A `TagCircuit`'s
expression tree is recursive, and several of its leaves are Python *types* (`Le(Via(base=Listing, ...),
Const(5))`) - neither shape fits a component field, which `World.attach()`'s own `_lower()` restricts to
primitives, an `Entity` id, or a list/dict/tuple of those, on purpose (`world.py`'s module note: "a
component field never holds a live Python object reference"). Embedding a spec for real means turning
every node of the tree into its own entity and every type-valued field into a resolved name string
(`loopingrules/save.py`'s existing `module:ClassName` trick, but needed at every leaf instead of once at
the top) - and "ingestion" then has to walk that entity graph back into a real spec object, which *is* a
parser, just one pointed at a graph instead of text: no line numbers, no `git diff`, and every one of the
sixteen-odd entities a reduction like `hear_list`'s needs (`TODO.md`) now clutters `w.show()`, `census`,
and `save.dump()` with something that means "program text," not "domain fact" - a category `World`'s
existing generic tools have no way to tell apart from an ordinary one.

**Framing the human's role as *examples*, not *authorship in any form*, dissolves the reason to embed at
all.** The original pressure for putting a spec in the World was letting some other rule *generate* one
without needing a parser - composability the same way `KnownValue`/`LoopCount` already get it. But if a
person only ever supplies before/after examples and a synthesizer derives the spec, nobody hand-authors
the spec as text *or* as an entity graph - so the spec's own representation stops being a human-ergonomics
question and becomes a pure implementation choice for whatever does the deriving. Plain Python data (what
`circuits.py` already is) is easier to enumerate and score during a search than an equivalent entity
graph, for the same reason `_lower()` forbids nested object references in the first place. What *should*
be world-visible, because it is ordinary data and already has a home: the examples themselves (a
before/after snapshot, using `loopingrules/save`'s own serialization rather than a second format), and
the request to derive a rule from them - structurally the same `ask`/`answer`/`checked` shape this file
already names above, not a new verb. A synthesized spec is installed by *reference* (a name pointing at a
Python value), the way `save.py` already resolves a component class from `module:ClassName` - never by
exploding its tree into the World.

**A handful of examples routinely underdetermines the rule, and that risk already has a home in this
file's own vocabulary.** Several distinct specs can satisfy the same two or three examples and diverge on
a case nobody demonstrated - the `ranked`/`ruled_out` machinery above, and the Forced/Ambiguous/Unresolved
verdicts, apply one level up: rank candidate specs consistent with every example by simplicity, and treat
a tie - more than one candidate equally consistent - as `Ambiguous`, refusing to install rather than
silently picking one. `PRINCIPLES.md`'s one non-negotiable ("a wrong conclusion is worse than a missing
one") is exactly as true of a wrongly-generalized rule as it is of a wrongly-guessed fact; it is just one
level more diffuse, because everything the installed rule touches afterward inherits its mistake.

**Genuinely rejected, not just left undone: letting the rule language itself refer to a component or
field without ever naming it, resolved from world data at runtime instead.** That would have been one way
to make a search's job easier, but it defeats the exact property the whole exercise above depends on -
see `PRINCIPLES.md`'s new "To guard it" entry on this. A synthesizer's *search* can range over many named
candidates; the spec it settles on must still name them, literally, or nothing downstream (`reads`,
`writes`, `watches=`) stays answerable.

**Not implemented.** No request/response wiring for "derive a rule from these examples," no
synthesizer, no `Loop`-level step to install what one finds. Flagged because `circuits.py`'s own docstring
already named this as the reason its catalog is closed ("a closed catalog is the thing a FUTURE search or
learning process over rules would need to be tractable at all... No search or learning is built yet") -
this is that thread, picked up in conversation and not yet in code.

## 2026-09-10 — designed, not built: evolving a whole rule SET against examples, frozen rules held fixed

Picks the 2026-09-07 thread back up, from a different angle: not "derive one spec from scratch" but "a rule
author already has a BASE set of `circuits.py` specs (some of them declared off-limits), hands over
input/output examples, and wants the system to propose additions, edits, and deletions to the REST that
make the set match." Two things the 2026-09-07 entry deferred are exactly what this needs and neither is
built yet: an actual human/LLM-typeable surface for a spec (the YAML loader `README.md`'s History and
`TODO.md` both name as "discussed and deliberately deferred... until a real authoring workflow needs one"),
and any per-rule way to say "do not touch this one," which has never come up before now because nothing has
tried to mutate a SET of specs at all, only ever author one by hand or synthesize one from nothing.

**What's genuinely new relative to 2026-09-07, not a restatement of it.** That entry's synthesizer answers
one occasion at a time — one spec, from examples, ranked against rivals by simplicity. A SET raises a
question a single spec never has to: an example's expected outcome is the composed effect of every rule in
the set running to a fixpoint together, so a candidate edit to rule B can only be scored by re-running the
WHOLE set (base, unchanged frozen rules, and every other candidate edit under consideration) against every
example, never by checking B in isolation. This is the same "no rule calls another, the only channel is the
shared `World`" substrate `PRINCIPLES.md` already describes — nothing new is being asked of the runtime,
only of the search that proposes edits to it.

**The YAML surface is a literal, structural restatement of the closed catalog — no new expressiveness.**
Every node in `circuits.py`'s catalog gets exactly one YAML shape, tagged by an explicit `op`/`shape` key
(YAML has no dataclass-type tag of its own); a component or tag TYPE (`CardDef`, `Wants`, the `into` of a
`ValueCircuit`) is written the same `module:ClassName` string `loopingrules/save.py` already resolves a
component class from, per 2026-09-07's own instruction not to invent a second reference format:

| catalog shape | YAML shape (sketch) |
|---|---|
| `Self(component, field)` | `{op: self, component: cards:CardDef, field: wanted}` |
| `Via(base, fk, component, field)` | `{op: via, base: ..., fk_field: listing, component: cards:Listing, field: price}` |
| `Const(value)` | `{op: const, value: 5}` |
| `Le(a, b)` / `And(*terms)` | `{op: le, a: ..., b: ...}` / `{op: and, terms: [...]}` |
| `TagCircuit(for_each, condition, tag)` | `{shape: tag, for_each: cards:CardDef, condition: {...}, tag: cards:Wanted}` |
| `ValueCircuit(for_each, into, fields, condition, monotonic)` | `{shape: value, for_each: ..., into: ..., fields: [...], monotonic: false}` |
| `ActionCircuit(require, without, condition, effects)` | `{shape: action, require: [...], effects: [{op: replace_at, at: ..., component: ..., fields: [...]}, {op: destroy}]}` |

A rule entry also carries `name` (matching `loop.rule`'s own naming, `TODO.md`'s "a name must be unique
now") and `frozen: false` by default. `Call`'s `tool` field stays a literal string, exactly as it is in
Python — the loader changes WHO can type a spec, never what a spec can name; a tool the caller of
`compile_circuit` did not register still fails at compile time, same as today. Building the loader AND a
dumper together (dataclass tree → YAML, not just the reverse) is deliberate: the evolution search below
needs to hand a rule author back a readable, diffable rule set, not just consume one.

**The frozen contract.** `frozen: true` marks one rule INSTANCE in a set, not a type — a sibling idea to
`@transient` marking a component CLASS disposable to `save.py`, but scoped to a value in a YAML file rather
than a Python class, because "do not evolve this" is a fact about one author's rule, not about every rule
of that shape everywhere. A frozen rule is never an add/modify/delete candidate; it fully PARTICIPATES in
every replay of every example, unchanged, the same as any other rule in the set — freezing it exempts it
from the search, not from running. If a frozen rule's own behavior already contradicts an example no matter
what the unfrozen rules do, that is not the search's problem to paper over by mutating something else
nearby; it is a distinct outcome, named below.

**The search stays inside vocabulary this file already has, rather than inventing a fifth.** The catalog
being closed is what keeps "add a rule," "edit a rule," and "delete a rule" enumerable moves rather than
general program synthesis, the same argument `circuits.py`'s own docstring already makes for a single spec:
an add is a new `TagCircuit`/`ValueCircuit`/`ActionCircuit` built from the same closed node set to a bounded
depth; a modify is a structural edit to one unfrozen rule's tree (swap a comparison operator, change a
`Const` literal, widen or narrow a `for_each` type, add or remove a `Not`) — an enumerable list of edits,
not free-form rewriting; a delete removes one whole unfrozen rule. Commit reuses this file's own
2026-09-07 verdicts rather than a new scoring scheme: a candidate SET that produces a wrong world on any
single example is `ruled_out`, full stop — consistency is not a score to trade off, it is `PRINCIPLES.md`'s
one non-negotiable ("a wrong conclusion is worse than a missing one") applied to a derived rule set instead
of a derived fact. Among sets that survive every example, `ranked` by simplicity (fewest edits, smallest
trees). Forced is exactly one simplest survivor; Ambiguous is a tie, refused rather than silently broken by
picking the first; Unresolved is no survivor at all under the enumerated edit space with frozen rules held
fixed — which is also the outcome that surfaces "the frozen rules themselves already disagree with an
example," rather than that case being silently absorbed into a worse edit elsewhere. Every accumulated
example is re-scored against `base` fresh each time a new example arrives, never patched incrementally onto
the last derived set, the same "recompute fresh, never cache" discipline `PRINCIPLES.md` already states —
otherwise the same two examples given in a different order could derive two different rule sets.

**Non-goals, named rather than left to look like a gap nobody noticed.** No gradient or statistical fitting
— this is discrete structural search over a small closed grammar, consistent with `PRINCIPLES.md`'s own
non-goal ("not the kind of emergence that wants surprise... a genetic-search substrate instead" is a
DIFFERENT tool, not this one dressed up). `Call`-bearing rules are out of scope for both mutation and fresh
synthesis: a tool is trusted Python chosen by whoever installs the spec, not something an examples-driven
search should get to introduce, and `Opaque`'s own refusal means the search cannot reason about what a
`Call`-bearing rule touches when planning an edit around it anyway — it may appear in `base`, frozen or
not, but the search treats it as opaque, never as a template to vary. No cross-example weighting: every
example is an equally hard constraint, not a soft loss; "mostly right" is a different question than this
design answers.

⚠ Nothing here is implemented: no YAML loader/dumper, no edit enumeration, no scorer, no commit step. Still
open:
- What counts as "the same rule" across an edit, so the dumper's YAML diff shows one changed field rather
  than a full rewrite of the entry.
- How deep/wide the enumerable edit space for "modify" can go before it stops being tractable — needs a
  bound picked against a real base set and real examples, not decided here in the abstract; starting with
  edits scoped to shapes `base` already uses, rather than the full catalog, is the likely tractable default,
  per this file's own "grow it only where it collides" discipline.
- Whether Ambiguous should ever surface PARTIAL agreement across a tied set ("every tied candidate agrees on
  rules A and C, disagrees only on B") rather than the whole tied set opaquely — the same open question this
  file's own `ranked`/`ruled_out` section leaves open for the unrelated arbitration vocabulary, now asked
  again here.

## 2026-09-13 — designed, not built: `Call` deposits a request instead of invoking a tool in place

`circuits.py`'s `ActionCircuit` commits its effects inside one atomic write phase — "refuse the WHOLE
action, not half of it" is the module's own comment at both `MISSING` checks in that phase (`circuits.py:988`,
`:992`) — and `Call` sits inside that same phase today, called synchronously: `tools[effect.tool](w, *values)`
(`circuits.py:1002`), the tool running to completion, in place, before the tick that fired it ends. That is
exactly right for a tool whose answer is knowable the same tick it is asked (`fs_tools.stat`, a disk read).
It stops being right the moment a tool's real answer can only come later — a `rename` that first needs a
human or another rule to confirm it. The only way to keep `ActionCircuit`'s atomic contract under THAT
tool is to build resumption machinery inside `circuits.py` itself: call it, discover nothing usable came
back, refire the same action next tick, and now invent some way to tell "already asked, still waiting" from
"never asked" so the refire does not ask twice. `circuits.py` has no such machinery and was never meant to —
its own docstring's `Call` section (`circuits.py:698-717`) only ever described same-tick tools.

**The fix is not a new pattern — it is the one this file already names as proven.** `pystrider/repair.py`'s
`ask`/`answer`/`checked` (`Already proven`, above) does exactly this, concretely: `ask` (`repair.py:247`)
attaches `Evaluate(case)` to the subject; `answer` (`repair.py:262`) reads every `Evaluate`, and DEPOSITS
either `Evaluated(case, value)` or `CouldNotEvaluate(case, refused)` back onto the same subject — never
silence, never a bare failure to attach anything; `checked` (`repair.py:283`) reads `Evaluated` back and
concludes. None of the three call each other; the loop's "run everyone, every tick, until nothing changes"
IS the dispatch. Mapped onto `Call`:

- **ask** — an ordinary `Spawn`, not a new effect: `Spawn(ToolRequest, (tool, *args))` puts a fresh entity
  carrying `ToolRequest(tool: str, args: tuple)` into the `World` — plain data, exactly as constrained as
  `Call`'s own `tool`/`args` are today, so this is a completely ordinary, soundly-analyzable write. No code
  runs when a rule deposits one.
- **answer** — a rule the COMPILING CALLER installs (the same party that supplies `tools=` today), watching
  `w.each(ToolRequest, without=(ToolResult, Rejected))`. This is the one and only place `tools[tool](w,
  *args)` is ever actually called — still name-checked, still plain-data-in, still trusted Python, but now
  an ordinary loop rule running in its own tick, not code wedged into `ActionCircuit`'s write phase.
- **the result is deposited, not returned** — the same rule attaches `ToolResult(...)` onto the request
  entity, or, matching `repair.answer`'s own "deposit the refusal, never stay silent" discipline, a named
  `Rejected`/`Failed` instead.
- **checked** — a downstream rule simply does not match yet, because `ToolResult` is not there. Nothing to
  build for "waiting": the fixpoint does it, the same way this file's own "Settled, by deletion" entry
  already argues `needs` requires no code at all.

**Why this is strictly better than resumption machinery, not just a style preference.** `ActionCircuit`'s
atomicity constraint never bites under this shape, because depositing a request no longer stands in for the
tool's answer — it IS the whole action, and it commits cleanly in one tick like any other `Spawn`. There is
no "call it, see nothing happened, refire" logic to invent inside `circuits.py` at all; `answer` and
`checked` are ordinary rules OUTSIDE the closed catalog, which is exactly where open-ended waiting already
belongs per this file's own vocabulary.

**Approval (`rename`'s confirmation) falls out of this for free, and more uniformly than a hand-rolled
check would.** The answerer is the one chokepoint every `ToolRequest` passes through no matter who deposited
it — a human-typed command and an automation's own proposal are both, by the time the answerer sees them,
just an entity carrying `ToolRequest("rename", ...)`. Marking `rename` `confirm=True` in the answerer's own
tool table gets every request for it asked, unconditionally, without any proposer having to remember to tag
itself as needing confirmation.

**A consequence worth flagging here, not decided by this entry.** `Call`'s own special-cased `Opaque` in
`reads()`/`writes()` (`circuits.py:1080-1091`) exists ONLY because invoking `tools[tool]` used to happen
inside the analyzable catalog itself. Once `Call` is "spawn a `ToolRequest`," that effect is a `Spawn` of
plain data like any other and is soundly analyzable again — the opacity does not disappear, it MOVES to the
answerer rule, which lives outside `circuits.py`'s catalog and is already covered by `loopingrules.analyze`'s
own `Opaque`, exactly the distinction this file's "Already proven" section already draws between the two
(a closed catalog that knows where its own knowledge ends, versus an AST walk that cannot resolve an
indirection). So `circuits.py` can drop its own `_refuse_calls`/`Opaque` special case for `Call` entirely —
the generic `analyze.py` `Opaque`, applied to the hand-written answerer rule, already does the job. This is
a real change to `circuits.py`'s contract, and — separately — to `harneskills`'s rename path, which does not
go through `Call` at all today; adopting this there is a decision for whoever owns that path, not implied by
writing it down here.

⚠ Nothing here is implemented: `Call` is unchanged in `circuits.py`, no `ToolRequest`/`ToolResult`/`Rejected`
components exist, no answerer-generating machinery exists. Still open:
- Whether `Call` survives as a node authors still write (compiled, under the hood, into `Spawn(ToolRequest,
  ...)`) or is retired outright in favor of authors writing that `Spawn` directly — "an ordinary `Spawn`, not
  a new kind of effect" argues for the latter, but nothing here decides it.
- Whether `compile_circuit`'s existing `tools=` parameter keeps meaning what it means today (a lookup table
  `Call` dispatches through inline) or becomes the table an AUTO-GENERATED answerer rule is built from, so
  every caller that already passes `tools=` gets ask/answer/checked for free rather than having to hand-write
  an answerer.
- Whether `ToolRequest`/`ToolResult`/`Rejected` are permanent, like `repair.py`'s `Evaluate`/`Evaluated`
  (kept as a durable record even once answered, `attach`ed rather than `replace`d), or consumed/destroyed
  once read — `repair.py` picks the former for exactly the reason its own module note gives (evidence a
  repair worked should not be erasable), and nothing here has checked whether `Call`'s occasions want the
  same permanence or would rather not accumulate.
- How `confirm=True` itself resolves an outstanding request — whether it is itself another `ask`/`answer`
  hop (a `ConfirmRequest` a human or a rule answers) or something else entirely; this entry names WHERE the
  chokepoint is, not HOW a pending confirmation gets from "asked" to "answered."

## 2026-09-14 — designed, not built: judges, closing "Not built: chart parsing" above

The 2026-08-31 note above ("in parsing, nothing 'wins'; interpretations fade out") left two things
unresolved: whether composing a whole interpretation out of smaller ones needs a third verb, and separately
— the harder half — what tells a domain the CHART has stopped changing and it is safe to pick a winner at
all. `harneskills.examples.fs`'s own `tokenize`/`mark_keyword`/`mark_number`/`after_threshold`/`located`
swarm (built since that note, migrated under exactly one of five `propose_*` rules so far) is real evidence
this shape is needed for real, not a hypothetical: `AfterThreshold`/`Located` are already "the winner is a
whole interpretation, composed from adjacent `Token`s," by hand, with no generic `Span`, no score, no
notion of "has this line stopped producing new readings," and no check that a winning reading covers the
WHOLE line rather than just the part one rule happened to recognize.

**Grounding, checked before designing against it, not remembered:** `pystrider/spans.py`'s `Span(start,
end)` is the one proven precedent for a plain span primitive (line numbers there, word-token indices here).
`world.py`'s private `_Ripe` (`world.py:301-307`) already does "survived one full tick" for `arbitrate`/
`census`, but is single-tick, single-occasion, and not exported — too narrow to reuse directly. `context.py`'s
`record_intake`/`hear_qualified` already use `priority=` to guarantee same-tick ordering across independent
rules, and `harneskills`'s own `_Recorded`/`loopingrules.memory`'s own `_FocusSeen` are the exact "mark it
seen, clear the mark the moment the thing that earned it is gone" idiom this entry's own quiescence
bookkeeping reuses rather than invents a fourth time.

### The shape: `loopingrules/chart.py`, a fourth vocabulary alongside `Proposal`/`request`/`Call`

**`Span(start, end)`** — inclusive 0-based word-token indices, a plain fact some rule observed (one token)
or derived by composing smaller `Span`s (`AfterThreshold`'s own two-token span, restated). **`Interpretation
(utterance, score=0.0)`** — attached ALONGSIDE `Span` on the SAME fresh entity, the domain's own meaning
riding as a separate component next to it (`AfterThreshold`, `Located`, ...) — exactly `Proposal`'s own
"a marker plus whichever component would make it real" shape, restated for a span instead of an occasion.
`score` is the one field a JUDGE may later `replace` — what makes a good interpretation is left to the
domain, the same split `arbitrate`/`census` already draw for "what makes a good candidate."

**Quiescence is ONE signal, not two.** A first draft of this entry gated "stop composing, start judging" and
"stop judging, start selecting" as two separate countdowns — wrong: a domain-authored judge rule that
`replace`s a score IS a participating rule by the same test a `tokenize`/`after_threshold` rule already is,
so it flips the SAME flag. `Intake(text)` is the one entity per utterance every `Span`/`Interpretation` this
entry's own components carry a reference to; `Active()`, attached to it by ANY participating rule (parsing
OR judging) that did something this tick, consumed the moment `settle()` (the one countdown rule, LOW
priority, installed last) sees it; `Countdown(remaining)`, reset to `BASE=1` the tick anything is `Active`,
decremented by 1 every tick nothing is — `ready(w, intake)` is `remaining <= -1`, reached exactly two
DECREMENTS after a reset (`1 -> 0`, not yet; `0 -> -1`, ready), "two genuinely idle ticks passed," mechanically
the same shape the entry's own author described in words. Caught, and fixed, only while implementing this:
an earlier version of this paragraph said `BASE=2`, which is three idle ticks from a reset to `-1`, not two —
arithmetic this note got wrong stating it, corrected against the running code rather than left standing.
`mark_active(w,
intake)` is the one call a participating rule adds alongside whatever `Span`/`Interpretation` write it
already makes — named for the verb, `propose`'s own shape.

`settle()`'s own read phase (both queries — who is `Active`, who is not — issued BEFORE either write)
matters the same way `ActionCircuit`'s read-then-write phase does: writing `Countdown` during the first loop
must not change which entities the second loop's `w.each(Intake, without=Active)` matches, or an intake
freshly marked active this tick would ALSO get decremented in the same call. Named here because it is the
one place this design is easy to get wrong silently, not because it is subtle to state correctly once seen.

**`select(w)`, the third verb `arbitrate`/`census` never needed:** the generic step, gated on `ready` and
"not yet resolved" (so it never re-fires once it has), that reads every `Interpretation` an `Intake` carries
and picks the highest-total-score COMBINATION whose `Span`s' union covers every word index of the utterance
— overlap permitted, no tiling requirement — marking every member of the winning combination `Definitive
()`. A word covered only by an `Ignorable()`-marked interpretation (a domain's own rule, for filler words —
"please", "um" — co-attached the same way `AfterThreshold` is) still counts toward coverage; `Ignorable`
members win or lose as part of the SAME combination as everything else, carrying no score of their own, not
specially exempted downstream. No combination covers the whole utterance -> no `Definitive` at all for that
`Intake` — said by whatever downstream rule reads absence, never guessed at. `select` does NOT call `mark_
active` itself: its own write is the terminal act, not a "keep going" signal, so it does not re-open a
window it just closed.

**Isolating tentative interpretations is the gate the entry's own author proposed, unmodified:** every rule
downstream of judging keys on `Interpretation` PLUS `Definitive`, never bare `Interpretation` — the same
`without=NeedsApproval` shape `do_rename` already uses, renamed rather than reinvented. Composing rules
(`after_threshold`/`located`-shaped) key on raw `Span`/`Interpretation` and must NOT see `Definitive` at all,
or a tentative reading could compose further after judging has already closed the window on it.

### What is genuinely new here, restated plainly

`select` is the third verb the 2026-08-31 note speculated about, resolved: not `compose` (nothing here
builds a BIGGER interpretation out of smaller ones automatically — domain rules like `after_threshold`
still do that composing by hand, the same as today), but a covering-SET winner search over an already-built
chart, the "falls out of `census` plus a domain-authored rule" branch that note itself named as the version
to try first — except the covering-set search is generic enough to live in `loopingrules.chart` itself, not
left to each domain to reinvent, because "does this combination's spans cover the whole utterance" is
exactly as domain-agnostic as "does every veto answer no" already is for `arbitrate`.

### Left open, named rather than guessed at — blocks implementing, not designing

- **The covering-set search is a real, unaddressed complexity question.** As designed, `select` searches
  subsets of one `Intake`'s own `Interpretation`s for the best-covering combination — exponential in the
  number of candidate interpretations in the worst case. Fine at the scale `fs.py`'s own lines run at (a
  handful of tokens, a handful of readings); a domain with long utterances or many rival readings per span
  would need a real algorithm (dynamic programming over spans, the classical chart-parser's own answer) that
  this entry does not design. Worth revisiting once a real utterance is slow, not before.
- **Whether `Countdown`'s `BASE=1` ("two genuinely idle ticks," see the arithmetic correction above) is a
  good default, a per-domain knob, or should live on `Intake` itself** (one conversation's lines settle
  faster than another's) is not decided — `1` is what "two ticks" the entry's own author described in words
  actually requires, kept as a literal constant until something needs it to vary.
- ~~Whether `harneskills.examples.fs`'s `propose_stale` swarm migrates onto this.~~ Done (2026-09-14,
  `harneskills` commit "fs.py: propose_stale migrated onto loopingrules.chart"): `compose_stale_reading`
  wraps `AfterThreshold`/`Located` into ONE whole-line `Interpretation` (this domain never had rival readings
  to actually score — the migration proved the MECHANISM composes with a real domain, the same bar `Call`
  was held to against `examples/files.py`, not that this rule needed scoring). Surfaced a real, structural
  bug in the process, not anticipated here: `fs.flag_stale`'s `without=Proposal` gate assumed `StaleHunt`
  never exists without `Proposal`, an invariant the ORIGINAL `propose_stale` upheld for free by spawning both
  atomically — a naively two-layered version broke that silently, letting `flag_stale` claim a reading before
  arbitration ever ran, skipping the whole two-idle-tick wait while every EXISTING test kept passing anyway
  (none checked WHEN resolution happened, only what it eventually produced). Caught only by a test that
  checked tick-by-tick state rather than trusting `loop.run()`'s settled end state — see `harneskills`'s own
  `PendingStaleHunt` for the fix, and `tests/test_fs_chart.py::
  test_compose_stale_reading_never_spawns_a_real_stalehunt` for where it is pinned.
- **`Interpretation.utterance`, a plain id, is how a reading is scoped to one `Intake` among possibly
  several live at once** (two conversations, two `World`s, or two utterances mid-processing in the same
  `World`) — proven against exactly one live `Intake` at a time by both the worked example and the `fs.py`
  migration; still untested with two or more genuinely concurrent.

Found only while implementing, not anticipated by this design:
- **`select`'s covering-set search has no notion of two interpretations CONFLICTING, only of them
  coexisting.** Overlap is unconditionally free, so a non-negative-scored reading is never excluded from the
  winning combination — two genuinely rival readings of the same span (`"stale after 3 days"` vs. `"stale
  after 5 days"`) both win together unless a judge gives at least one a NEGATIVE score. Whether that is
  simply a domain judge's own job (down-weight what it disfavors below zero) or a real gap `select` itself
  should eventually close (some notion of "these two occupy the same slot, pick one") is not decided — see
  `loopingrules/chart.py`'s own `_best_covering` docstring for where this is checked, not just asserted
  (`tests/test_chart.py::test_overlapping_interpretations_may_both_win_if_the_combination_scores_highest`
  pins the surprising case directly, rather than leaving it to be discovered by a real domain later).

## 2026-09-20 — designed, not built: waves, vocabulary, and discourse-level reinterpretation, extending `chart.py`

The 2026-09-14 entry designed how a chart of `Span`/`Interpretation`s gets JUDGED and SELECTED from — it
said nothing about how those `Span`/`Interpretation`s get BUILT out of raw text in the first place, nor
about an utterance longer than one line, where a later sentence can overturn an earlier one's already-chosen
reading. `harneskills.examples.fs`'s own `tokenize`/`mark_keyword`/`mark_number`/`after_threshold`/`located`
swarm — the same one the 2026-09-14 entry cites as its evidence chart parsing was needed for real — already
does the first half BY HAND, one domain at a time, with no shared shape a second domain could reuse; this
entry gives that shape a name and asks whether the existing chart mechanism already covers the second half
(a longer discourse) once generalized one level up, rather than needing a second kind of "done."

**Grounding, checked before designing against it:** `examples/trip.py`'s `Stop` entities are the concrete
case that "registering a vocabulary" need not mean a domain builds a separate lookup table — the entities a
domain already has ARE the vocabulary once tagged, the same way that module's own `Leg`/`TripRequest`
already ride `share.ref`-tracked ids rather than a name-keyed dict. `examples.cards.decide_buy`'s "compose a
tag nobody wrote the composition of" idiom is the precedent for triggered rules needing no new activation
primitive — a rule reading a marker another rule attached is already an ordinary `w.each` gate, not a new
kind of dependency. `trip.py`'s `Expanded` tag is the precedent this entry deliberately does NOT reuse for
discourse completeness (see "what alternatives were rejected," below) — considered and set aside in favor of
restating this design's own 2026-09-14 correction ("quiescence is one signal, not two") one level up instead
of introducing a second bookkeeping tag beside it.

### The shape: three additions to `chart.py`, none touching `select`'s own search

**Wave 0/1, tokens and vocabulary.** `Token(utterance, index, text)` — co-attached with `Span(index, index)`,
spawned by a domain's own splitting rule (whitespace, punctuation-aware, whatever; this entry does not design
a splitter, the same way `chart.py` itself does not tokenize). `Vocabulary(word)` — co-attached by a domain
rule onto WHATEVER entity it names, not a separate registry entity: recognizing "milan" as a station is
`w.attach(stop_entity, Vocabulary("milan"))` run once over `trip.py`'s own `Stop`s, not a new lookup
structure. One generic rule, `read_vocabulary(w)`, matches un-interpreted `Token`s against attached
`Vocabulary` components and spawns the `Span`+`Interpretation` pair the same way any other proposing rule
does.

**Triggered rules need no new primitive.** "Train" being recognized should enable a fuzzier station-name
check over the OTHER tokens — this is an ordinary rule gated on a marker component (`TravelModeDetected`,
say) that the keyword rule attaches to the `Intake` itself alongside its own `Interpretation`, the identical
shape `decide_buy` already uses. A rule "activated by" another rule is just a rule with one more `w.each`
clause; nothing in `World` or `Loop` needs to change for this.

**`Candidate` vs. `Definitive`, and `promote`.** `select` now attaches `Candidate`, not `Definitive`, to its
winning combination — `Candidate` carries the identical "isolating tentative interpretations" gate `Definitive`
had (composing rules must never see it, acting rules key on it), but is explicitly retractable: a
cross-sentence rule may later `w.detach` it. A new generic rule, `promote(w)`, is the only thing that ever
attaches `Definitive` — for an `Intake` with no `Discourse`, immediately, once it holds a `Candidate` (nothing
to wait for); for one that is `SentenceOf` a `Discourse`, only once that `Discourse` is itself `ready` (see
below). `Definitive` keeps its EXACT existing meaning and existing consumers unmodified — it is `Candidate`
that is new, sitting one step earlier in the pipeline, not a redefinition of the terminal marker itself.

**`Discourse`/`SentenceOf`, and reinterpretation.** `Discourse(text)` is one per multi-sentence utterance;
`SentenceOf(discourse, order)` marks which `Discourse` an `Intake` belongs to and in what order, so a
cross-sentence rule can find "the previous sentence." A `Discourse` gets its own `Active`/`Countdown` —
literally the same components `Intake` already uses, not a parallel type — and TWO kinds of rule call
`mark_active` on it: the rule that spawns a new `SentenceOf` `Intake` (a discourse is still "moving" while
sentences are still being added to it), and any reinterpretation rule that retracts an earlier sentence's
`Candidate`/`Definitive` because a later sentence contradicted it. Reinterpretation itself is not a new verb
either: `w.detach(entity, Definitive())` (or `Candidate`), then `mark_active` on BOTH the earlier sentence's
own `Intake` (reopening ITS countdown, so `select` reconsiders) and the `Discourse` (reopening promotion's
own wait) — the same detach-and-reopen shape this module already has, called from a different rule.

### What alternatives were rejected for "when has a discourse stopped growing"

Three ways were on the table for telling `promote` a `Discourse` has all the sentences it is going to get,
not just that the ones it has are quiet:

- An explicit `Discourse.length` (sentence count), mirroring `Intake.length`. Rejected: `Intake.length` is a
  real geometric constraint `_best_covering` checks against (every word position covered); a discourse has
  no equivalent per-sentence coverage check, so a count here would exist ONLY to tell `promote` something
  else could tell it for free — see below.
- A `Closed` tag, mirroring `trip.py`'s own `Expanded`. Rejected for the same reason: it is a second
  bookkeeping fact riding beside quiescence rather than being quiescence, the exact shape the 2026-09-14
  entry already corrected once (`BASE_COUNTDOWN`'s arithmetic note, "quiescence is ONE signal, not two").
- **Chosen:** spawning a new `SentenceOf` `Intake` is ITSELF activity — the spawning rule calls `mark_active
  (w, discourse)` the same tick it spawns, so a `Discourse`'s own `ready()` already means "no sentence added,
  and no candidate retracted, for two ticks," with nothing new to define. A `Discourse` that goes quiet
  because some sentence never resolves a `Candidate` at all behaves exactly like today's `select` on an
  uncoverable `Intake`: `promote` never fires for it, silence read as silence by whatever downstream rule
  looks, never specially detected or reported.

### Left open, named rather than guessed at — blocks implementing, not designing

- **How much a fuzzy/approximate vocabulary match should score relative to an exact one** ("milan" matching
  `Stop("Milan")` exactly vs. a misspelling matching it approximately) is not designed here — left to the
  domain's own judge rules, the same split `arbitrate`/`census`/`chart.select` already draw for "what makes a
  reading good," restated rather than special-cased for approximate matches.
- **Wave ordering (splitting before vocabulary before triggered rules before composition before judging) is
  a documentation convention, not an engine-enforced one** — `Loop`'s own `priority=` can express it, the
  same way `context.record_intake`/`hear_qualified` already rely on same-tick ordering, but nothing stops a
  misordered rule from reading a `Token` before it exists. Worth a real guard if a second domain gets this
  wrong in practice; not designed defensively here.
- **Two or more `Discourse`s live at once, and a `Discourse` nested inside another, are both untested by this
  design** — `SentenceOf` scopes an `Intake` to one `Discourse` the same bare-id way `Interpretation.utterance`
  scopes a reading to one `Intake`, a pattern the 2026-09-14 entry already flagged as "proven against exactly
  one live at a time," not against several concurrent ones; this entry inherits that same open question one
  level up rather than resolving it.
- **Nothing here decides how far back a reinterpretation rule is allowed to reach** — a `Discourse` with many
  sentences could in principle let sentence 50 retract sentence 1's `Definitive`, reopening a window that
  looked closed long ago. Whether that is the correct behavior (discourse-wide correction, by design) or
  needs a domain-imposed limit (only the immediately preceding sentence, say) is left to whichever domain
  writes the first real reinterpretation rule, not decided in the abstract here.

## 2026-10-01 — designed, tested on paper and in scratch code, not built: closed shapes, open vocabulary

Prompted by a review of `circuits.py` that asked for something different from what it had become: not complex
rules written out of its expression algebra (45 node types by now, grown one hard rule at a time —
`Split`, `Join`, `Children`, `FindBy`), but complex *compositions* of rules, drawn from a small set of
parametrizable templates and wired together by attaching and detaching components. Nothing here is
implemented; four checks were run against the existing specs and one fresh domain, with throwaway scripts
(not committed), to find out whether the idea survives contact with the corpus before any code is written.

### What is closed and what is not

The first framing was wrong and the correction is the point of this entry. A limited component
*vocabulary* was proposed; it cannot work, because named components (`Wanted`, `Affordable`, `Risk`,
`Resolved`) are where a domain's meaning lives, and meaning has to grow without bound. What stays closed is
the layer above the names:

- **Shapes** — the roles a component can play (occasion, subject, tag, derived value, reference, state,
  parameter, latch), each a set of named *slots*.
- **Templates** — the rule patterns that act on those roles (gate, derive, resolve-by-key, claim-and-emit,
  classify, latch).

A new name is cheap. A new shape, a new template or a new expression node is a decision to justify. This is
`PRINCIPLES.md`'s "small vocabulary, closed under what rules produce" with the closure moved up one level:
closed under *shape*, open under *name*.

A second correction followed: "protocol shapes" (fixed field names) and "free-field shapes" are not two
kinds. Every field name in `circuits.py` is already a literal parameter of a spec, so a fixed name is only a
template's default. One model covers both: a component *declares* which shape it instantiates and binds
each slot to a real field (`judgement(Risk, level="level", reason="reason")`), and a template takes the
component, never the field names. The one real exception is a component read by trusted code outside the
catalog (`Reply`, `Said`, `ToolRequest`): its slots are pinned, because the engine would silently stop
matching if a domain remapped them.

### What the four checks found

1. **Pure-parameter reuse is low.** 37 specs (everything module-level in `tests/test_circuits.py` and
   `examples/files.py`) have 31 distinct structural skeletons with component classes, field names and
   constants blanked, 28 with comparison and arithmetic operators blanked too. What does repeat is
   claim-and-emit (11 of 15 `ActionCircuit`s are `Destroy` then `Spawn`) and the `hear_list`/`hear_want`
   twin pairs. A `TagCircuit`'s condition is its content, so a template named "tag if comparison" would
   carry almost nothing; templates have to be coarser than that, or the condition language has to count as
   part of what a template is parameterized by. Not decided.
2. **A component has no lifecycle of its own; its entity does.** 14 entity archetypes are consumed whole by
   a `Destroy` (a `Said` with its tags and parse results, a `Listing` with `Wanted`/`Affordable`/
   `FairPriced`, a `Bought`). `cards.Listing` is an occasion, not a subject, which an earlier draft of this
   table got wrong. A tag comes in two kinds (recomputed both ways every tick by a `TagCircuit`, versus
   latched once like `Announced`), and state that actions replace (`Purse`, `Copies`, `Wants`) is a different
   shape from a read-only parameter (`RiskProfile`). `Listing`'s three tags are conjunctive; `Said`'s nine
   fall into exclusive families (list, want, status) that nothing in the specs says are exclusive, so
   exclusivity has to be *declared*, which is the argument for `classify` as a template and not three loose
   `TagCircuit`s.
3. **A fresh domain (a product, its features, requirements checked against them) needed no new shape.**
   About a dozen names, all fitting the roles above, run end to end on the existing catalog. It also
   exposed two gaps in what the shapes guarantee, neither predicted beforehand:
   - **A correlated aggregate cannot be written, and the failure is silent.** Inside `Count`/`Forall`,
     self is rebound to the matched entity, so "how many requirements point at *this* product" has no
     expression: the naive attempt returned `0` where the answer was `3`, with no error. Reviewing one
     product at a time through a singleton works, at the price of outside code swapping the singleton.
   - **`ValueCircuit` never retracts.** When a source it derived from disappears, the evaluation skips the
     tick and the old output stays. Destroying one feature left its requirement with a stale `Resolved`,
     `Via` read `MISSING`, every comparison was false, and the requirement ended with no outcome tag at
     all — not even "unknown", because the stale `Resolved` made it look resolved. Exclusivity held;
     exhaustiveness did not. A derived value that skips on `MISSING` is not "recomputed fresh every tick".
     `cards` never hit this; it is existing behavior, unchanged by this entry.
4. **Renaming is safe through slot binding.** The same domain was built twice from stub templates that read
   fields only through declared slots: once with the original names, once with every component and field
   renamed and every dataclass's field order shuffled. Outcome tags and the one reply were identical. A
   typo'd field, a missing slot and a remap of `Reply` were each refused at declaration time. A
   deliberately swapped binding (`bound` and `sense`) changed the result, so the check has teeth — and it is
   the limit: a swapped binding of two numeric slots is *not* caught structurally, only by a behavior
   test. Slot types would catch some such swaps, not all.

### What this does not settle

- The corpus is mostly `cards` (about 30 of the 37 specs), restated to reproduce rules that already
  existed, not written for templates. The fresh domain was written by someone who already knew the
  catalog's limits and the earlier findings, so it is easier than a stranger's would be.
- Nothing here shows the model helps rule search or learning, which was a motivation of the original
  catalog. That needs an actual search.
- The stub declaration layer and templates in check 4 were scratch code. No `declare`, no template functions
  and no wiring check exist in `loopingrules/`.

### Left open, named rather than guessed at — blocks implementing, not designing

- **Whether `ValueCircuit` should retract its output when a read goes `MISSING`**, or whether a
  `classify` template should instead carry an explicit exhaustive fallback ("unknown") and leave derived
  values stale. Changes the meaning of "fresh" for every existing derived value.
- **Whether to add a reverse-reference scope** (entities whose field names *me*, `Children`'s converse), or
  to accept one-at-a-time review through a singleton. The first grows the expression algebra, against this
  entry's own direction; the second leaves the gap and the silent wrong answer in place.
- **Template granularity and which come first.** Claim-and-emit, resolve-by-key (appeared in `hear_list`,
  `hear_want` and the product domain) and classify are the three the evidence points at.
- **Whether slot declarations check field types as well as names.** Names are cheap and structural; types
  would catch more, at the cost of constraining components that today accept loosely typed fields.

## 2026-10-01 (later) — discussed, nothing built or tested: rules that write rules, learned from input/output shapes

This follows the entry above and uses its vocabulary (shapes, templates, slot binding, open names). It
records a conversation only: no code was written, no scratch script was run, and nothing here has been
checked against examples. It exists so the design is not lost; treat every "would" as a proposal.

### The idea, as the user stated it

The system is given **input shapes and desired shapes** (entities and components, as in a world snapshot)
and finds the rules that turn one into the other. Complexity is meant to come from many simple learned rule
instances over the closed templates, not from complex rule bodies, so the learner's output vocabulary is
the template catalog and the learner's job is choosing a template, binding its slots and adding a guard.

- **Reuse before writing.** Existing rules run first. The learner writes a rule that moves the input toward
  a shape the existing rules already carry on, then another from the "almost matching" shape to the
  desired one. What the system must actually possess are heuristic rules that, given an input shape and a
  desired shape, decide which computation to trigger.
- **The desired shape is partial.** Anything not stated is unconstrained. Ambiguity is removed by the
  author naming the wanted components explicitly, not by the learner guessing.
- **Components are never invented.** Declaring a new component kind is part of writing the example itself;
  the learner composes names that already exist.
- **Existing rules may be changed unless declared frozen**, so a run is always scored against the *whole*
  set of input/output samples, never one sample at a time. This is the 2026-09-10 contract (`frozen`,
  every sample a hard constraint, rescored fresh) applied to learned rules.

Sketch of the means-ends reading (mine, not yet agreed): run the existing rules to a fixpoint on the input,
diff the result against the desired shape, and let the kind of difference suggest a template: a missing
component suggests Derive or Gate, a missing entity Claim-and-emit or Spawn, an extra one Destroy or a
retract, a changed value Update, data sitting behind a key Resolve-by-key. A second stage then fills the
holes from the examples.

### The two-phase proposal (the user's latest message)

1. **Phase 1, relationships.** A fixed set of *relationship rules* is tried blindly against every
   input/output sample. Those that hold in every positive sample are collected as **must hold**. Matching
   the same relationships against **negative examples** gives **must not hold**: those that hold only in
   negatives. A relationship that holds in only some samples, or fails in only some, becomes **generally
   holds** or **generally does not hold**.
2. **Phase 2, derivation.** From the must-hold and must-not-hold sets the system derives the rules that
   actually run.

### Assessment

The shape is **Daikon-style invariant detection** (Ernst et al.): a fixed catalog of invariant templates is
instantiated over every type-compatible combination of variables, each instance is tested against each
observation, falsified ones are dropped, and survivors are reported as likely invariants, with a
statistical filter against coincidence and suppression of implied ones. Daikon has no negative examples,
so that part is the user's addition. It also resembles version-space learning over a fixed hypothesis
language, and "applies only in some cases" is decision-tree induction with the relationships as features,
which is the user's original "rules that build a decision tree" idea.

What it buys, if it works:
- **Phase 1 is cheap.** Testing a relationship is a per-sample check. The 09-10 search runs a fixpoint per
  candidate edit, so phase 1 is a much cheaper first filter, and its output (a list of what holds) is
  declarative and reviewable.
- **Exclusivity and exhaustiveness can be discovered.** An output-only relation like "`Met` and `Unmet`
  never co-occur" is an invariant, which is how a `classify` template would get its declared exclusivity
  without anyone writing it, and the negatives would test it.
- **It fits the closed-shapes model.** Typed slots prune the relationship space, and the template set is
  what makes phase 2 tractable.

Risks named in the discussion:
1. **Two roles for negative examples.** A relationship that holds on all positives *and* on a negative
   does not discriminate; one that holds only on negatives is a forbidden signature. Whether a negative is
   a wrong output for an input, or an input on which nothing should fire, is not defined yet. Both could
   be supported.
2. **"Generally holds" conflicts with two earlier positions.** `PRINCIPLES.md` says a wrong conclusion is
   worse than a missing one, and the 09-10 entry lists "no cross-example weighting; every example is a hard
   constraint" as a non-goal. Proposed reading: a soft relationship is never a silent runtime rule. It is a
   proposal that needs a guard (another relationship that separates the cases where it holds from where it
   doesn't, which is the decision-tree step), a human confirmation, or an `Ambiguous` verdict.
3. **Coincidences on few samples.** Daikon's known failure. Typed slots remove most, a minimum support
   count is still needed. A threshold such as `Ge(value, 8)` is underdetermined: any constant between the
   largest negative and the smallest positive fits, so the honest verdict is `Ambiguous` with the range
   stated and a request for a boundary example.
4. **Direction and alignment.** Relationships are symmetric, rules have direction; the input/output split
   supplies it. A relationship over several entities needs alignment through key or reference slots, and a
   relationship over a set (a count) runs into the correlated-aggregate gap from the entry above.
5. **Phase 2 is still a search.** Many true relationships are redundant, and runtime rules fire stepwise,
   not input-to-output in one move. Proposed: keep replaying against all samples as the final gate, so
   relationships propose and replay disposes.

### What this does not settle

- Phase 1's behavior on realistic data is unknown. Whether the true relationships are recovered and how
  many spurious ones survive at 2, 5 and 10 samples has not been measured.
- Phase 2 (relationships to runtime rules) is the unspecified half; this entry has only argued it is a
  search gated by replay.
- Nothing here changes `circuits.py`, `specs.py` or `loop.py`. `Loop` still has no rule removal, which a
  learner that modifies or deletes rules would need.

### Left open, named rather than guessed at

- **What exactly a negative example is** (wrong output for an input, input where nothing should fire, or
  both), and how a relationship that holds on a negative is treated.
- **Whether a "generally holds" relationship can ever become a runtime rule**, or only a proposal that is
  confirmed or guarded first.
- **Whether the relationship catalog is fixed like the templates, or can grow.** Closed is consistent with
  this entry's direction; open would put a new decision on the same footing as a new template.
- **Closed-world scoping:** for which component kinds does "absent from the desired shape" mean "must not
  be there", versus "unconstrained"? The partial-shape rule says unconstrained by default.
- **When intermediate kinds are declared**, since components are never invented but a two-stage rule chain
  may need one that the author did not think to put in an example.
- **Whether current behavior on seen inputs counts as implicit samples**, so that changing an existing
  rule is checked against what it already does without anyone writing those samples.
- **A cheap test before any design hardens:** write about eight relationship templates over declared slots
  in the product domain, generate positive samples and corrupt outputs for negatives, run phase 1 only, and
  count recovered versus spurious relationships at 2, 5 and 10 samples.

## 2026-10-03 — tested in scratch code, not built: a baton, so the computation can be modulated and not only run to a fixpoint

Prompted by the observation that unrelated rules fire side by side with no central control, and "run to
fixpoint" is then the only thing shaping a computation. The proposal: a *baton* that rules pass to each
other, or that a regulating rule takes away, so the computation can follow a logical thread. The stated
goals are both **mutual exclusion** (rivals that do not know each other cannot both act) and
**preemption** (something central can interrupt work in flight). Nothing here is in `loopingrules/`; two
throwaway scripts (`/tmp/baton_check.py`, `/tmp/baton_check2.py`, not committed) ran it against a real
documented problem before any design was fixed.

### The shape, and why it is vocabulary and not engine

Rules are not parallel today. `Loop.tick` runs every rule once per tick in priority order and each write is
visible to the next rule at once, so "everything whose guard holds fires" is the whole control story. A
baton is one ordinary component, `Baton(scope, holder)`, on its own entity. A rule that takes part guards on
it (`holder == "bought"`), passing is a `replace`, taking away is a higher-priority rule that `replace`s it.
No `Loop` change. This keeps this file's own non-goal ("a goal is an ordinary fact a judge's guard checks")
and keeps `analyze()` sound, because the baton is an ordinary read. The alternative, a `Loop.rule(...,
thread=)` gate, would enforce the guard but tie rules to threads and cost the analysis; not taken.

A baton belongs to an occasion or thread, not to a rule, for the reason the rest of this file already gives
for occasions: rules are shared across threads, entities are not.

`loopingrules.memory.Focus` was checked first as a possible reuse and is not one. `Focus` is a salience claim
a domain makes about an entity, recorded as a trail, with no holder, no authority and nothing gating on it
(two entities may both carry it, which is why `most_intense` exists). The one overlap is
`examples/deixis.py`, which keeps `Focus` single-valued by detaching it from every other entity before
attaching it: a hand-rolled exclusive baton, exclusive only by convention. A baton would generalize that;
`Focus` stays a plain claim.

### What the scratch run found

The test case was the one `TODO.md` records: `cards.decide_buy` can produce two `Bought`s in one tick, and a
reply rule that drains one per tick (the compiled circuit's behavior) lets `reply_goal_met` fire between the
two replies. Reproduced first: `bought dragon`, `goal met`, `bought griffin`.

1. **A central regulator fixes the order and gives exclusion.** One high-priority rule derives the holder
   from the world by precedence (a `BadCommand` first, then a pending `Bought`, then an unannounced
   `GoalMet`, else `idle`) and `replace`s the baton only when it differs; the three reply rules each guard
   on it. Result: `bought dragon`, `bought griffin`, `goal met`. From the loop trace, at most one reply
   rule fired in any tick.
2. **Preemption needs no saved state.** With one `Bought` still pending, a `BadCommand` was spawned. Result:
   `bought dragon`, `! interrupted`, `bought griffin`, `goal met`, one reply rule per tick throughout. The
   preempted work resumed by itself because rules hold no stack and every in-flight fact is already a
   component; the baton only decides who may act next.
3. **Collaborative passing alone stalls, silently.** When the reply rules pass the baton to each other
   (`bought` passes to `goal` once the last `Bought` is gone), the case where the goal is met with no
   purchase at all leaves the baton on `bought` forever: no reply, `hot == []`, a clean settle that looks
   exactly like "done". This is the exact hazard flagged beforehand and it is real, not theoretical. A
   regulator that derives the holder from the world closes it.
4. **A regulator needs a stable resting value.** A first version that flipped the holder between `bought`
   and `goal` when neither had work changed the world every tick and never settled. An explicit `idle`
   holder, reached and left only when data changes, fixes it.
5. **It stays inside the analysis.** `analyze()` follows a same-module helper that takes `w`, so
   `holds(w, who)` and a compare-and-swap `pass_baton(w, frm, to)` analyze cleanly, and the set of rules
   whose `writes` include `Baton` came out as exactly the regulator: "central take-away" is a checkable
   property, not a convention. (A rule that referred to its types as `cards.X` attributes instead of
   imported names went `Opaque`, and the check then had to treat it as a possible writer; that was the
   scratch script's own mistake, but it is the same dialect restriction every analyzed rule has.) A
   compiled `ActionCircuit` can also gate on a baton held on a different entity:
   `Gt(Count(Baton, Eq(Self(Baton, "holder"), Const("bought"))), Const(0))` as its `condition`, and
   `circuits.reads` reports `Baton`.

### What it costs

- **Latency.** The central version settled in 6 ticks where the ungated one took 2, because the regulator
  hands over one tick before the holder acts and again after.
- **Preemption can lag one tick.** A regulator only sees what was written before it runs in the tick. A
  `BadCommand` produced later in the same tick preempts a tick late. An earlier run of the preemption case
  hid exactly this: the `BadCommand` came from a `Said` that had not been parsed yet, so the second purchase
  reply went out first and the run looked like a failure of preemption when it was the lag. Spawned
  directly, it preempted correctly.
- **Advisory.** A rule that forgets the guard still runs. Nothing enforces participation, only the closed
  `gate` template could add the clause automatically (see the 2026-10-01 entry, where `gate` is one of the
  named templates); hand-written rules can still forget it.

### Left alone on purpose

- **Concurrent threads.** One baton for one thread was tested. One baton per thread entity, several live,
  is the same open question `Intake`/`Discourse` already carry ("proven against one at a time").
- **Other domains.** Only `cards` was used. `pystrider`'s `relax`/`lower` ("correct by luck and wrong as a
  repair" above) is the obvious second case and has not been tried.
- **Nesting.** Preemption of a preemptor was not tried. The derived-by-precedence regulator handles any
  order of arrival by construction, but a domain whose precedence is not a fixed list is untested.
- **Whether `examples/deixis.py` should move onto a baton.** Not decided; `Focus`'s single-valuedness is
  currently a convention nothing checks.

⚠ Nothing is implemented: no `Baton` component, no helpers and no `gate` template exist in `loopingrules/`.
The regulator was written by hand for one domain, so this shows the pattern works there, not that a generic
regulator can be written.

Still open:
- Whether the regulator should be one rule per scope that derives the holder (as run here) or whether
  collaborative passing with a regulator only as a watchdog is worth its extra moving parts. The evidence so
  far favors derived: the collaborative form needed the regulator anyway to avoid the stall.
- How a regulator states its precedence so a second domain does not rewrite it. A fixed list of
  `(condition, holder)` pairs read top to bottom is the obvious candidate and was not built.
- Whether a baton should be able to say *why* it was taken, the way `ruled_out` carries a named reason.
