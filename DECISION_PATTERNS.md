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
