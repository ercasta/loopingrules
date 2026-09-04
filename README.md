# LoopingRules

**An entity-component world, a loop that runs rules over it, and one
thread to run a session on.**

An *entity* is an identity with no data — `#7`. A *component* is data
with no identity — `Size(bytes=4300)`. A *rule* is a Python function of
one `World` that asks for the entities carrying a set of components,
walks them, and WRITES to it directly — `spawn`/`attach`/`replace`/
`detach`/`remove`/`destroy`. The *loop* calls every rule, once a tick,
over and over, until a whole pass changes nothing, and that is when the
world has something to say. The *engine* is one thread that owns that
loop and routes what it says to however many channels are attached to it.

```
loopingrules/
  world.py        entities, components, and the queries rules ask
  loop.py         every rule, in order, until nothing changes
  engine.py       one thread, the world, and the channels attached to it
  save.py         the world as JSONL: entities are ints, components are values
  analyze.py      what a rule reads and writes, derived from its own AST
  circuits.py     a closed catalog of shapes a rule can be DATA in
tests/
  test_world.py        identity, values, and the intersection of the two
  test_loop.py         order, settling, the budget, a rule that raises
  test_engine.py       one world, several channels, a broadcast reply
  test_save.py         the same world, ids and all, next time
  test_analyze.py      a rule's reads/writes, and where analysis refuses to guess
  test_circuits.py     the catalog, proven against real rules from two domains
DECISION_PATTERNS.md   a design note this package no longer ships the code
                          for -- see History, "Facts/arbitration/request
                          removed"
PRINCIPLES.md           what keeps rules run to a fixpoint over a shared
                          World producing the wanted kind of emergence,
                          not the surprising kind
TODO.md                 open threads named so they are not lost, not a
                          schedule
```

## Try it

```bash
pip install -e .
python3 -c "
from loopingrules import Loop
from loopingrules.world import Reply, Said

loop = Loop()

@loop.rule
def greet(w):
    for e, said in w.each(Said):
        w.destroy(e)
        w.spawn(Reply('user', 'hi, %s' % said.text))

loop.world.spawn(Said('user', 'world'))
loop.run()
for e, r in loop.world.each(Reply):
    print(r.text)
"
```

## Scope

**No domain, no channel, no transport.** `world.py`, `loop.py`,
`engine.py` and `save.py` ship no rules, no components
beyond `Said`, `Reply`, and `Proposal` (the shapes `Engine.drain`,
`Engine._do`, and propose/arbitrate route by), and no knowledge of
files, sockets, or terminals. `Engine` wants anything with `.name`,
`.deliver(message)`, and optionally `.start(engine)` / `.close()` — no
base class, no import required to be one.

`Proposal` is here for the same reason `Said`/`Reply` are: a domain
cannot skip another domain's unresolved candidate, or recognize its
own, without agreeing on what the tag means — that agreement has to
live somewhere neither domain owns. What is deliberately NOT here is
the arbiter — which candidate wins, and on what grounds. That stays
exactly where `harneskills.examples.fs`'s `arbitrate_parse` already
puts it: in the domain whose actual conflict decides what "wins"
means. See History, "Proposal, a shared tag."

`propose`/`reply` (the one-line spellings of `w.spawn(Proposal(occasion),
...)` and `w.spawn(Reply(channel, text))`) and `arbitrate`/`census` (the
two ways an occasion with several `Proposal`s against it can resolve —
one winner, or every candidate) are the vocabulary that shape gets used
WITH, not a domain's own rule. Nothing here decides what a rule does
with a resolved occasion; `arbitrate` and `census` only agree on WHEN
"everyone who could answer already has" is true — see `arbitrate`'s own
docstring, and `loopingrules.help.close_census` for a caller that needs
`census`'s "everyone counts" instead of `arbitrate`'s "one wins." See
History, "arbitrate, a shared chokepoint" and "help gets a census."

**`analyze.py` is the other generic mechanism here, and it is a reader,
not a vocabulary.** Given a rule — a plain function of one `World` —
`analyze()` derives which component types it reads and writes by walking
its own AST, so `Loop.rule(watches=...)` can be checked against what a
rule actually does instead of trusted by convention; `component_map()`
builds the `{component: {rules}}` index the same walk produces across
several rules at once. It knows nothing about any domain's own
components — only the eleven methods `World`/`Entity` already expose,
plus `propose`/`reply` by identity (see its own docstring, "Two named
exceptions," for why those two specifically). A rule that uses its world
parameter outside the dialect `analyze.py`'s own docstring names is
never guessed at — it raises `Opaque`, by name and reason, the same
refuse-rather-than-guess discipline every parse boundary in this
codebase already applies. See History, "analyze.py."

**`circuits.py` is a third generic mechanism, and the only one built by
restating rules rather than by a domain needing to interoperate with
another.** A closed, minimal catalog of shapes (`TagCircuit`/
`ValueCircuit`/`ActionCircuit`, plain dataclasses, no loop, no `if`) a
rule can be DATA in, instead of a hand-written Python body — motivated
by a closed catalog being what a FUTURE search or learning process over
rules would need to be tractable, the way genetic programming and
program synthesis reach for a small typed combinator set rather than
arbitrary source code. No search or learning is built here yet.

Lived in `examples/circuits.py` — a prototype, not shipped — through
eight commits of restating real rules against it: seven of `examples.
cards`'s own thirteen, five of `pystrider.patterns`/`constraints`'s
entire real vocabulary, every one checked both by replaying the actual
regression it came from and by comparing its own structurally-derived
reads/writes against `loopingrules.analyze`'s AST-derived ones for the
original. Promoted here DELIBERATELY ahead of this repo's own usual bar
— every other promotion (`Proposal`, `arbitrate`, `census`) waited for
a second domain to actually depend on the thing at runtime; nothing
does that for this yet. The cross-repo evidence above was judged
sufficient on its own, without waiting for a specific consumer — see
`circuits.py`'s own docstring, `TODO.md` for what is still open, and
History, "circuits.py promoted to core."

**`help.py` is the one exception to "ships no rules," and it says so
itself.** `world.py`/`loop.py`/`engine.py`/`save.py` still ship none,
and that has not changed; `help.py` is installed opt-in, by any domain
that wants `help`/`help TOPIC` answered, and by nothing automatically.
It lives here rather than in a domain because it moved OUT of one:
`pystrider` needed to answer `help python` alongside `harneskills.examples.fs`
answering `help files`, and depending on `harneskills` — a specific
harness, not the substrate every domain already depends on — was the
wrong direction for a domain meant to be host-agnostic. See `help.py`'s
own docstring and History, "help moves in."

A bare `help` answers through `census`, not a hard-coded hint: any
domain that wants to be listed registers its own responder against
`HelpCommandCensus`, and `help.py` itself has no idea, at import time,
which domains that will turn out to be. See History, "help gets a
census."

**And no vocabulary above entities and components either, any more.**
This package used to also ship `facts.py`/`arbitration.py` — a
`fact`/`state`/`deny` way of writing relations as components, and a
generic reader arbitrating between rules proposing/vetoing/ranking
candidates for one contested decision. Removed, not ported, once the
core above was rewritten — see History, "Facts/arbitration/request
removed." `DECISION_PATTERNS.md` keeps the argument for why a generic
arbitration reader beats agency in the base rule (extracted from
`pystrider`, a domain that measured the alternative's cost first: two
repair rules firing on one bug, "correct by luck"); it just is not code
in this package any more. A domain that wants that pattern writes its
own components and its own generic reader over them, the way
`harneskills.examples.fs` already writes everything else it needs.

**`harneskills`, a sibling repo, is the worked door onto it** — a
`Terminal` channel, a WebSocket `Listener` and `client`, a config-file
format for naming domains, and `harneskills.examples.fs`, a domain built
on `World` and `Loop` alone. None of that is imported here; this package
does not know `harneskills` exists, and does not know where its checkout
lives on disk.

**`examples/cards.py` is a second domain, kept here, and still not
shipped.** `examples/` is a top-level directory, a sibling of
`loopingrules/` and `tests/`, not a subpackage of `loopingrules/` — it is
not in `pyproject.toml`'s `packages=`, so `pip install -e .` puts
`loopingrules` on a consumer's path and nothing else, exactly as before.
It is a worked example the same way `harneskills.examples.fs` and
`pystrider` are, one repo closer to home: one autonomous trading agent
reacting to a virtual card market according to a goal and a risk profile,
with no rivalry anywhere in it (one agent, its own money — no
`Proposal`/`arbitrate`/`census` needed), demonstrating instead the
compositional-tag idiom `pystrider.patterns.LoopCount` →
`pystrider.constraints.TooManyLoops` already proved: independent rules
tagging one shared entity, and a rule that acts only once several tags
land on it together. `tests/test_examples_cards.py` is where its own
tests live, importable via the `pythonpath = ["."]` this repo's own
`pyproject.toml` now carries for exactly that — the same knob, and the
same reason, `harneskills/pyproject.toml` already uses to import
`loopingrules` from a sibling checkout without a real install. See
`examples/cards.py`'s own docstring for the full design, and History,
"A cards example."

**`examples/judge.py` is a second module in `examples/` (alongside
`cards.py`), and the only one that never imports `examples.cards` back.**
It is not a domain — one
rule, `flag_too_risky`, that reads a generic `Risk`/`RiskTolerance` and
writes `TooRisky`, oblivious to what produced either. `examples.cards.
tag_risk_level` is the domain-specific half: it projects `Purse`/
`RiskProfile`/`Listing` onto `Risk`, and `decide_buy` reads the judge's
`TooRisky` back the same way it reads its own three tags. Built to test,
concretely, a narrower version of a "shared vocabulary between domains"
question this README already answers "no" to for the general case (see
above, "no vocabulary above entities and components either") — see
`judge.py`'s own docstring for what this does and does not settle, and
History, "A domain-oblivious judge."

**`examples/parts.py` is a third module in `examples/`, and the only one
built to test a question about a SIBLING repo rather than about
`loopingrules` itself.**
`pystrider.symbolic._parent_of`/`_reachable` walk a Python-level dict
(`intake.PARTS.values()`) generically, rather than enumerating specific
part-edge types — exactly the shape `PRINCIPLES.md` holds up as the
model, and exactly the shape `loopingrules.analyze` cannot see into
(there is no literal component type at that call site for a static
reader to point at). `parts.py` prototypes the fix: a generic `Part`
component, minted through ONE choke point alongside every specific edge,
so a generic reader walks `Part` alone — proven, not just argued, to
keep the actual property that matters (a brand-new edge kind, added
after the walkers are written, costs them zero changes) while becoming
fully analyzable. Also proves, honestly, what it does NOT fix: a reader
parameterized by which ANCESTOR kind to stop at (`pystrider.symbolic.
_enclosing`) stays opaque regardless, a separate, sibling instance of
the "kind held in a variable" pattern found elsewhere in `pystrider`.
Nothing here touches the actual `pystrider` checkout — see History,
"a generic Part tag."

## History

**The three `reply_*` rules: the simplest shape yet, a real bug caught
by a unit test, and a genuine cost of composing reductions together,
2026-09-06 (later still).** `reply_bad_command`/`reply_bought`/
`reply_goal_met` all reduce to a single `ActionCircuit` each -- claim a
fact, destroy it (or, for `reply_goal_met`, mark it `Announced` without
destroying `GoalMet`), spawn a `Reply`. One new primitive, `SelfId()`:
the plain int id of the entity an `ActionCircuit` itself matched, for
`reply_goal_met`'s own `w.attach(entity, Announced())` -- the one effect
in this whole catalog that acts on the SAME entity the match found,
rather than a related or looked-up one.

`SelfId`'s first implementation returned `entity` exactly as handed to
it -- which, from `compile_circuit`'s own `ActionCircuit` branch, is an
`Entity` HANDLE, not the plain int every other expression in this
catalog resolves to. A unit test comparing `evaluate(SelfId(), w, e)`
against `e.id` caught it immediately (`Entity.__eq__` compares by
`(world, id)`, so a handle never equals a bare int by design -- see
`loopingrules.world.Entity`'s own docstring). Fixed with `getattr
(entity, "id", entity)`, the same normalization `World.attach` already
does on the way into a component field.

The other real finding, surfaced by the SAME discipline (check, don't
assume): `reply_bad_command`/`reply_bought` loop over EVERY match in
the original (several `BadCommand`s or `Bought`s can coexist in one
tick); an `ActionCircuit` only ever acts on the first. A first attempt
at the comparison test used `sorted()` on both sides and passed --
which would have hidden a real difference. Compared unsorted instead:
for a single event the order matches exactly, but when `cards.
decide_buy`'s own real batching produces two `Bought`s in one tick,
`reply_goal_met` can now land IN BETWEEN the two replies instead of
after both, because two independent one-match-per-tick queues are
competing for tick slots where the original had one rule draining both
in a single pass. Same final SET of replies, different ORDER -- both
halves checked directly, not assumed, and pinned as a test rather than
a comment (`test_reply_bought_reaches_the_same_final_replies_but_not_
the_same_order_when_batched`). This is the sharper, compounding form of
the cost `decide_buy_spec`'s own batching-drop already named: it is not
only decide_buy's OWN tick count that changes when the batching goes,
it is the observable ORDER of everything downstream that reads its
output through another reduced, one-per-tick rule.

Every rule `examples.cards` registers has now been tried against this
catalog at least once. 7 new tests in `tests/test_circuits.py`. 276 ->
283 passing.

**`hear_want`/`hear_status`: the other two `hear_*` rules, and one
Replace effect where there were three, 2026-09-06 (yet later).**
`hear_want` is the same four-mutually-exclusive-outcome shape as
`hear_list`, restated the same way (two `ValueCircuit`s, four
`TagCircuit`s, four `ActionCircuit`s) -- but its success effect
replaces `Wants` on the card entity `FindBy` looks up BY NAME, and
neither `ReplaceVia` (a stored fk field) nor `ReplaceWorld` (the world
singleton) could reach an entity found that way. Rather than add a
third, narrower effect for the third way of naming a target, `ReplaceAt
(at, component, fields)` generalizes all three: `at` is just an
expression, `Self(base, fk_field)` for what `ReplaceVia` did,
`TheEntity(component)` (new) for what `ReplaceWorld` did, `FindBy(...)`
for the new case. `ReplaceVia`/`ReplaceWorld` are deleted outright, not
kept alongside it -- `decide_buy_spec` (the only other consumer)
rewritten onto `ReplaceAt` and reverified against every regression it
already had, unchanged. `If(condition, then, else_)` was also needed --
`hear_want` defaults an omitted quantity to `1`, which depends on WHICH
case holds (was a third word typed at all), not on whether a read came
back `MISSING` (`Coalesce`'s narrower question) -- explicitly NOT a
contradiction of "no loop, no `if`, by construction": it selects
between two already-evaluated VALUES, never a different effect, rule,
or `for_each`, the same as `SafeDiv` already silently does for one
specific case.

`hear_status` is a different shape from both -- no wrong outcome to
reject at all (trailing garbage after "status" is ignored, matching the
original exactly), just one report to build. Building it needed a
genuinely new kind of aggregate: `Join(over, expr, sep, sort_by=None)`,
`Any`/`Forall`/`Count`'s sibling, reducing an unbounded set to
variable-length, SORTED TEXT instead of a boolean or a number --
`examples.cards.hear_status`'s own `sorted(w.each(CardDef, Wants),
key=lambda row: row[1].name)` restated as data, an entity whose own
`expr`/`sort_by` is `MISSING` dropped rather than failing the whole
report. `Optional(condition, expr)`/`JoinStrings(sep, exprs)` assemble
the fixed, small set of KNOWN pieces around it (cash, the per-card
report or "no goal set", optionally "goal met") -- `Optional` drops a
segment entirely rather than joining an empty string in its place.
Needing the most genuinely new machinery of the three `hear_*` rules
produced the FLATTEST decomposition of them: two specs total, one
`TagCircuit` and one `ActionCircuit`, no branching at all.

Both checked against the real rules, exactly: `hear_want` across ten
lines (defaulted quantity, an explicit one, both directions of wrong
arity, unknown card, three distinct bad-quantity shapes including one
that parses to the same `-1` sentinel this restatement uses internally,
case-insensitive lookup) with its own mutual-exclusivity pin, the same
discipline `hear_list`'s correction already established; `hear_status`
across six scenarios (no goal, one unmet want, two wants sorted out of
input order, goal met, partially met, different cash).

32 new tests in `tests/test_circuits.py`. 244 -> 276 passing.

**A correction: count was the wrong metric for `hear_list`'s
decomposition, 2026-09-06 (later still).** The entry directly below this
one verdicted the ten-spec, six-primitive restatement of `hear_list` by
RAW COUNT -- "by far the worst primitive-to-value ratio tried so far...
costs more structure than it saves." Wrong measure, pointed out
directly: `PRINCIPLES.md`'s entire argument is that many small,
individually-legible pieces composing over a shared substrate beat one
rule holding several branches' worth of decision in its own control
flow -- Hearsay-II's blackboard architecture, stated as the model this
whole package is FOR, regardless of how many pieces that composition
turns out to have. `examples.cards` already has thirteen rules and
`pystrider.patterns`/`constraints` several more; nobody has ever
verdicted THOSE by counting them. Judged by the metric this package
actually uses -- is each piece small and independently legible -- the
`hear_list` decomposition is unremarkable: a `ValueCircuit` computing
four small facts, four `TagCircuit`s each one short boolean, four
`ActionCircuit`s each "match one tag, destroy, spawn one thing," and
six primitives (`Lower`/`Split`/`At`/`Len`/`ParseInt`/`FindBy`) each
doing exactly one well-defined, independently-unit-tested thing. None
of that is worse than `decide_buy_spec`'s own single `ActionCircuit` for
having more siblings.

There IS one real, specific cost in the decomposition, and it has
nothing to do with count: the original `hear_list`'s if/elif chain
guarantees its four outcomes are mutually exclusive BY CONSTRUCTION --
only one branch can ever run. The four `TagCircuit`s restate that as
four INDEPENDENTLY-AUTHORED conditions, each written as the negation of
the ones before it, which is correct today but not structurally
guaranteed the way control flow is -- a future edit to one condition
without a matching edit to its siblings could silently break the
invariant. Named honestly this time, and checked rather than left as
prose: `test_hear_list_outcomes_are_structurally_mutually_exclusive`
runs the four tags against ten lines (including non-`list` commands and
an empty string) and asserts at most one outcome ever lands on the same
`Said`. That is the actual, specific thing worth watching if this
decomposition is ever extended -- not the number sixteen.

1 new test (parametrized 10 ways) in `tests/test_circuits.py`. 234 ->
244 passing.

**`circuits.py` promoted to core, ahead of this repo's own usual bar,
2026-09-06 (later still).** `examples/circuits.py` -> `loopingrules/
circuits.py`, `tests/test_examples_circuits.py` -> `tests/test_circuits.
py` (the latter still imports `examples.cards`/`examples.judge` to
prove the catalog against real rules, the same way `tests/test_analyze.
py` already does for `loopingrules.analyze` -- a real, precedented
pattern, not a new dependency direction). No code changed in the move;
`circuits.py` had zero imports beyond `dataclasses`/`typing` to begin
with, so nothing about promoting it introduced new coupling.

What DID change is which bar this promotion met. Every prior promotion
in this package's own history (`Proposal`, `arbitrate`, `census`)
waited for a second, independently-motivated domain to actually
DEPEND on the thing at runtime -- `harneskills.examples.fs` and
`pystrider` both needing to recognize one candidate, concretely, is
what moved `Proposal` here in the first place. Nothing depends on
`circuits.py` at runtime yet: `pystrider` was read from and validated
against, repeatedly, across `patterns.py`/`constraints.py`'s entire
real vocabulary, but never wired to import or install any of it, and
`cards.install()` still uses none of its own restated rules either.
Asked directly whether that was the actual trigger or an oversight, the
answer was direct too: deliberate. The cross-repo evidence accumulated
across eight prior commits -- `loopingrules.analyze` agreement on every
spec, byte-identical behavior against real rules from two
independently-authored domains, twelve rules total -- was judged
sufficient on its own terms, without waiting for a specific consumer to
show up first. Named here plainly rather than left to look like the bar
was forgotten: this is a genuine departure from this package's own
precedent, made with the precedent in view, not around it.

**`hear_list`'s parsing DOES reduce -- at the worst cost of anything
tried so far, 2026-09-06 (later).** Named in `TODO.md` as a different
primitive axis (string parsing, not arithmetic) and left untried. Tried,
in full: `Lower`, `Split` (the one place a value in this algebra is a
LIST, not a scalar), `At`/`Len` (the only two things that ever read one
back out), `ParseInt` (`MISSING`, not a `ValueError`), and `FindBy
(component, field, value)` -- a different KIND of "reach a related
entity" than `Via`: `Via` follows an id a field already stores, `FindBy`
scans for the entity whose field EQUALS a computed value, the reverse
lookup `examples.cards._find_card` already does by hand.

The SHAPE of the decision turned out to be exactly the tag-composition
idiom already used everywhere else, once split: `hear_list` claims a
`Said` and produces exactly one of four MUTUALLY EXCLUSIVE outcomes
(wrong arity, unknown card, bad price, a real `Listing`) -- restated as
two `ValueCircuit`s (`ListParse` -- is this a `list` line, how many
words, the two words after the verb; `ListResolved` -- the card looked
up and the price parsed, both sentineled `-1` on failure, computed only
once arity is confirmed right), four `TagCircuit`s (one per outcome,
each condition the negation of the ones before it, so they are
provably mutually exclusive), and four `ActionCircuit`s, each keyed on
its own outcome's tag so `w.first()`'s "first match" is never ambiguous
about WHICH `Said` it means even with several in flight at once -- the
same reason `decide_buy_spec` needed its tags precomputed rather than
folded into a post-hoc condition.

Checked against the real `hear_list`, exactly, across all four outcomes
plus a case-insensitive successful match (`list DRAGON 40`) and both
directions of wrong arity (too few words, too many) -- seven cases,
parametrized, byte-identical listings AND replies, including the exact
wording of each distinct `BadCommand`.

The honest verdict, stated plainly rather than folded into a tidy
success story: this is by far the WORST primitive-to-value ratio of
anything tried in this file. `decide_buy` needed zero new primitives.
`check_goal` needed three (`Any`/`Forall`, plus the `ActionCircuit`
`condition` field). `loop_count` needed three (`Count`/`Children`/
`HasSelf`). `hear_list` needed SIX new primitives and TEN specs to
restate one rule of about twenty-five lines. It is fully, exactly
expressible -- and that is a different claim from it being a good idea:
nothing here changes the recommendation `TODO.md` already carries for
`hear_want`/`hear_status` (not attempted, same primitives, same cost,
nothing new to learn from doing it again), and if this catalog is ever
promoted past a prototype, string parsing is the strongest candidate
for "stays hand-written Python on purpose," not because it can't be
done, but because doing it costs more structure than it saves.

11 new tests in `tests/test_examples_circuits.py` (4 for the new
primitives, 7 parametrized end-to-end cases). 223 -> 234 passing.

**`loop_count`'s aggregate: `Count`, `Children`, `HasSelf`, 2026-09-06.**
`pystrider.patterns.loop_count` -- "how many of a `Function`'s `Stmt`s
are `ForStmt`s" -- is a third aggregate shape, distinct from both
`check_goal`'s `Any`/`Forall` (a boolean, over a GLOBAL join) and every
per-entity circuit before it (one entity's own fields): it needs a
NUMBER, and what it counts is not a world-wide join at all -- it is
reached by following `self`'s own `Body` to one specific entity, then
reading every `Stmt` THERE (`get_all`, plural, the one-to-many hop
`Via` cannot reach, since `Via` reads a single field off a single
related entity).

Three additions, each earning its place from this one real rule, not
speculated in advance: `Children(base, fk_field, component)` names the
one-to-many scope; `Count(over, condition)` is `Any`/`Forall`'s sibling
that counts instead of asking yes/no, over EITHER a `Children` scope or
an ordinary global join; `HasSelf(component)` answers "does the entity
currently being counted carry this," needed because `Count`'s own
condition is evaluated with each CHILD as self, not the `Function`
`loop_count` itself iterates -- `Exists` needs an expression naming an
id to ask about, and here the id in question just IS self.

Tried for real against the actual `pystrider` checkout, same as the
monotonic mode and the generic `Part` tag before it: restated exactly
as `ValueCircuit(for_each=(Function, Body), monotonic=True, fields=
(Count(Children(Body, "entity", Stmt), HasSelf(ForStmt)),))`, its reads/
writes matched `loopingrules.analyze.analyze(patterns.loop_count)`
exactly on the first attempt, and the compiled circuit -- swapped in
alongside the three already-restated descriptions -- produced a
byte-identical `LoopCount`, with `constraints.max_loops` (itself already
a circuit, from two entries ago) still composing correctly on top of
it. `patterns.py`'s and `constraints.py`'s entire real vocabulary now
reduces to this catalog, not just the three tag-shaped descriptions.

4 new tests in `tests/test_examples_circuits.py`, self-contained against
synthetic `Box`/`Item`/`Flagged` components so this suite needs no
`pystrider` checkout to verify the three new primitives. 219 -> 223
passing.

**"Don't fire twice" is consuming a component, not testing an absence
-- `WorldCircuit` removed, 2026-09-05 (later).** A correction to the
entry directly below this one, landed the same day it did: `check_goal`
was restated with `WorldCircuit`, guarding "don't fire twice" by
self-reference inside its own condition (`Not(Any((GoalMet,)))`) --
correct, but the wrong idiom, pointed out directly: this codebase's own
answer to "don't fire twice" is CONSUMING the thing that triggered the
rule (`Said`/`Proposal`, claimed and destroyed the instant a rule acts),
not testing whether the CONCLUSION already exists. `ValueCircuit.
monotonic`'s `without=into` guard is a third, genuinely different
idiom, for a reason worth keeping straight: it guards a STANDING
property of PERSISTENT data (a `Function` that must never be destroyed)
by testing the conclusion's own absence, because the data under it
cannot be consumed and still be useful to anything else that reads it.
`check_goal`'s `Wants` set is exactly that kind of persistent data
(`hear_status` still reads it) -- so its "don't fire twice" needed a
SEPARATE, purpose-built, one-shot marker to consume instead of either
consuming `Wants` (wrong -- destroys data other rules need) or
self-referencing `GoalMet` (works, but is the wrong idiom for a rule
whose actual shape is "handle one occasion, once").

Fixed by giving `ActionCircuit` a `condition` field (checked after the
match, against the matched entity, but free to ask about an entirely
different set via `Any`/`Forall` -- `check_goal`'s own shape: the match
finds a seeded `GoalCheck` marker, the condition asks about `CardDef`/
`Wants`) and restating `check_goal` as an ordinary `ActionCircuit`:
match `GoalCheck`, check the condition, and -- if it holds --
`Destroy()` the marker and `Spawn` `GoalMet`, in the same action. No
self-reference to `GoalMet` needed at all; the guard is now STRUCTURAL
(once `GoalCheck` is gone, there is nothing left to match, ever again),
not logical (a boolean the reader has to trust is wired correctly) --
the same "make it structural, not prose" preference `PRINCIPLES.md`
already states for a different guard (abstention). `WorldCircuit` is
deleted outright, not deprecated: once `ActionCircuit` could express
everything it did (nothing in it ever needed `Self`/`Via` off a real
entity, since a seeded marker serves exactly as well as no entity at
all), keeping both would have been two ways to say the same thing --
the same reasoning `facts.py`/`arbitration.py`/`deltas` were removed
for, applied to a shape that lived for exactly one commit this time
before the redundancy was caught.

`check_goal_spec`'s reads/writes now match a hand-written
`check_goal_consuming` reference exactly (`{CardDef, Copies, GoalCheck,
Wants}` reads, `{GoalMet}` writes, `destroys=True`) -- deliberately NOT
the shipped `cards.check_goal`, which reads `GoalMet` itself as part of
its own different guard; the two rules answer the same question with
different idioms, so their reads legitimately differ. The end-to-end
regressions (goal-met flow, once-only announcement) still hold with
`GoalCheck` seeded once, the same `install()`-time, BigFloor-style
seeding `Purse`/`RiskProfile` already use.

2 new tests, net (one added, one rewritten to check the guard is
structural rather than assumed). 218 -> 219 passing.

**`check_goal`'s quantifier: `WorldCircuit`, `Any`, `Forall`, 2026-09-05.**
`check_goal` is not a per-entity circuit at all -- "every wanted card is
met" is a universal quantifier over a SET, and "spawn `GoalMet` once,
never again" has no single entity driving it, unlike every shape
`circuits.py` had until now. Fixed with a fourth rule shape,
`WorldCircuit(condition, effects)` -- no per-entity match, `condition`
evaluated with NO entity in scope (`Self`/`Via` return `MISSING` rather
than raise when asked to read off nothing) -- plus two expressions:
`Any(over)` (at least one entity matches this join; `False` on an empty
set) and `Forall(over, condition)` (every matching entity satisfies
`condition`, evaluated with THAT entity as self; vacuously `True` on an
empty set, the classical convention, which is exactly why `check_goal`
needs both combined with `And` -- no goal is ever "met" if none was
stated). The "never fire again" guard is not a third flag: it is
ordinary self-reference inside the condition (`Not(Any((GoalMet,)))`),
the same discipline `check_goal`'s own `w.the(GoalMet) is not None`
already uses -- a separate flag would have said the same thing twice.

`check_goal_spec`'s reads/writes matched `loopingrules.analyze.analyze
(cards.check_goal)` exactly on the first attempt (`{CardDef, Copies,
GoalMet, Wants}` / `{GoalMet}`), and the compiled circuit, swapped in
for the real rule alongside the five already-restated ones, reproduces
the goal-met flow byte-for-byte, including the once-only announcement
that depends on `reply_goal_met` (untouched, real Python) composing
correctly with a circuit-derived `GoalMet`. `patterns.loop_count`
(an aggregate too, but "how many loops does one function directly
contain," not "how many entities in a query satisfy a condition") is a
different shape `Any`/`Forall` do not reach -- named in `TODO.md`,
not attempted.

6 new tests in `tests/test_examples_circuits.py`. 212 -> 218 passing.

**A correction: recursion is not "real computation, not orchestration"
after all, 2026-09-04 (later still).** A full audit of every rule
`pystrider` actually registers (51 rules, across `patterns`/
`constraints`/`repair`/`effects`/`effects_repair`/`plan`/`spans`/
`symbolic`/`domain`) found 19 `loopingrules.analyze` could not see
through, sorted into buckets — most were avoidable DRY (a `kind` closed
over a loop or ternary instead of written out — `symbolic.known_value`
split into three literally-typed rules analyzes cleanly with zero
behavior change, checked, not assumed), one was a sibling solution to
the same problem `circuits.py` solves (`pystrider.rules`'s `derive`/
`assign`/`minting`, restricted by stripping `World` methods at runtime
rather than by being data), one was deliberate genericity `PRINCIPLES.
md` itself celebrates (`_parent_of`/`_reachable`'s walk over `intake.
PARTS.values()` — see "a generic Part tag," below, for the fix tried),
and the last bucket was named "real computation, not orchestration" —
`symbolic.fold`'s recursion over a `Left`/`Right` tree, judged
irreducible to attach/detach composition.

That last claim was too strong. Production/term-rewriting systems —
structurally what this substrate already is — are Turing-complete, and
a recursive call flattens into "compute what depends on nothing yet,
then whatever now depends only on already-computed values, then
whatever depends on THAT" — exactly a `ValueCircuit` reading its own
output on related entities via `Exists`/`Via`, run to a fixpoint across
TICKS instead of stack frames. Proved with no new primitive:
`fold_lit`/`fold_add`/`fold_mul` in `tests/test_examples_circuits.py`
fold `(2 + 3) * (4 + 5)` to `45` with zero Python recursion, using only
`Add`/`Mul`/`Via`/`Exists`/`Eq`/`Const`, already in the catalog. Not a
novel discovery, either direction: `pystrider.effects.transitive`'s own
docstring already states the propagation half ("a call graph five deep
needs no more code than a call graph one deep — the loop just runs a
few more ticks"), and `pystrider.symbolic`'s own module docstring
records that `fold` USED TO work this way and was deliberately rewritten
to recurse in Python instead — "a side benefit" of an unrelated fix (a
repair mutating a `Constant` in place needs `fold` to never trust a
stale per-tick cache). The real, measured cost: ticks-to-settle depends
on registration order (dependency order resolves a whole tree in ONE
productive tick, thanks to `Loop.tick`'s own same-tick write visibility;
the adversarial order costs one tick per nesting level) — correctness
never does, pinned as two tests reaching the identical answer either
way. The corrected claim: expressible, but only worth it once something
else in the world wants to observe or extend an intermediate step —
otherwise recursion is strictly cheaper, and `pystrider`'s own authors
already made that exact call, in writing, for this exact function.

3 new tests in `tests/test_examples_circuits.py`. 209 -> 212 passing.

**A generic `Part` tag, prototyped against a real gap in `pystrider`,
2026-09-04 (later).** `examples/parts.py`: a toy tree (not `pystrider`'s
real one) with specific edges (`Left`/`Right`/`Body`) minted through one
choke point, `part_edge()`, that ALSO attaches a generic `Part(entity,
label)` on the same call. `parent_of`/`reachable`, restated to walk
`Part` alone, analyze cleanly (`reads == {Part}`, exactly) where
`pystrider.symbolic._parent_of`/`_reachable`'s real walk over `intake.
PARTS.values()` cannot — proof, not assertion, that the fix keeps the
actual property PRINCIPLES.md credits the original design with: a test
defines a BRAND NEW edge kind (`Otherwise`) after both walkers already
exist, mints it through the same choke point, and confirms neither
walker needed a single line changed to see it. The handoff the fix
depends on also checked: `both_operands_readable`, a rule keying on the
SPECIFIC `Left`/`Right`/`Readable` vocabulary and never mentioning
`Part`, analyzes cleanly on its own, oblivious to the generic walkers
the same way every tag-composition rule in this codebase already is of
every other one.

Named honestly, not smoothed over: `enclosing` (`_enclosing`'s
restatement) stays `Opaque` even after the fix, pinned as its own test —
it is parameterized by WHICH ancestor kind to stop at, a separate,
sibling instance of the "kind held in a variable" pattern the `pystrider`
audit already found elsewhere (`known_value` and others), and `Part`
only ever fixed the traversal half of that function's job.

Nothing here touches the actual `pystrider` checkout — `loopingrules`
does not depend on it, the same as it never has on `harneskills`. 9 new
tests in `tests/test_examples_parts.py`. 200 -> 209 passing.

**The monotonic mode, and `pystrider.patterns`/`constraints` tried for
real, 2026-09-04.** A live `pystrider` checkout audited against both
`loopingrules.analyze` and `examples.circuits` (neither imported by, nor
imports, this repo — the audit ran the sibling checkout's own rules
directly, nothing committed here depends on it). `analyze.analyze()`
resolved `patterns.py`/`constraints.py` — the exact `LoopCount` →
`TooManyLoops` idiom `PRINCIPLES.md` already cites as the model for this
whole catalog — with ZERO `Opaque`, on the first try. `circuits.py` did
not fare as well against the same rules: every one of them uses
`without=self`-guarded, ATTACH-ONCE-NEVER-DETACH semantics, the opposite
mode from every rule in `examples.cards`, which recomputes and goes
both directions every tick. `TagCircuit`/`ValueCircuit` only had the
`cards` mode.

Fixed by giving `ValueCircuit` a `monotonic` flag (an implicit `without=
into` guard, `attach` instead of `replace`, never revisited) and a
separate `condition` (gating whether an entity is derived AT ALL,
independent of whether its FIELDS are computable — `iteration`'s
`Readable` checks are not needed to compute `item`/`sequence`/`does`,
only to decide whether the derivation is trusted yet), plus one new
expression, `Exists(at, component)` — a boolean existence check
(`iteration` needs to know THAT three independently-named related
entities carry `Readable`, not read a field off them), and `for_each`
generalized to accept a JOIN of several component types (`iteration`'s
own `(ForStmt, Target, Iterated, Body)`). `TagCircuit` did not need a
monotonic mode of its own — nothing in `patterns.py`'s actual vocabulary
is a bare, fieldless tag, so this was not spent speculatively.

Tried for real, not just designed: `iteration`/`conditional`/
`application`/`max_loops`, restated as `ValueCircuit`s, matched
`loopingrules.analyze`'s reads/writes on the four real `pystrider` rules
exactly, and produced byte-identical `Iteration`/`Choice`/`Applies`/
`TooManyLoops` end-to-end against a real `intake()` of real Python
source with three loops (over `MAX_LOOPS=2`) and a conditional call —
run against the actual sibling checkout, not a stand-in. `patterns.
loop_count` (an aggregate — how many loops a function directly
contains) was left as the real, hand-written `pystrider` rule; it needs
a fold/aggregate shape this catalog still does not have, the same gap
already named in `TODO.md` for `examples.cards.check_goal`.

6 new tests in `tests/test_examples_circuits.py`, self-contained against
synthetic components so this suite needs no `pystrider` checkout to
verify the two new primitives. 194 -> 200 passing.

**`circuits.py`: a closed shape catalog, tried against five real rules,
2026-09-03 (later still).** A conversation about rule vocabularies and a
general DSL landed, in order, on: no vast shared vocabulary (`examples.
judge`), no general DSL (`loopingrules.analyze` got a sound map out of
plain Python instead), no YAML/JSON middle ground (either a string
expression language with worse tooling than Python, or a structural
comparison tree covering the same narrow shape `analyze.py` already
covers for free) -- and then a genuinely different proposal: not a
general escape hatch but a DELIBERATELY small, closed set of shapes,
motivated by future learnability rather than expressiveness or map-
building. `examples/circuits.py`: `Self`/`Via`/`World`/`Const` for reads
(missing-safe -- `MISSING` propagates through arithmetic, collapses to
`False` at a comparison, resolved early by `Coalesce`), `Add`/`Sub`/
`Mul`/`Min`/`Max`/`SafeDiv` for arithmetic, `Le`/`Lt`/`Ge`/`Gt`/`Eq`/
`And`/`Or` for conditions, `Format` for one string leaf, and three rule
shapes -- `TagCircuit` (attach/detach), `ValueCircuit` (replace),
`ActionCircuit` (a read phase then a write phase over `ReplaceWorld`/
`ReplaceVia`/`Destroy`/`Spawn` effects, on the single first match a
tick, never several). `reads(spec)`/`writes(spec)` walk the spec's own
dataclass tree -- sound by construction, no analysis needed at all.

Tried, not just designed, against `cards.tag_wanted`/`tag_affordable`/
`tag_fair_priced`/`tag_risk_level` and a reduced `decide_buy`
(`decide_buy_single`, dropping only the hand-rolled multi-purchase-per-
tick batching a prior conversation showed was an optimization, not a
correctness requirement -- the tick loop's own retry-with-fresh-tags
does the same job). Every one of the five, compiled from its spec and
SWAPPED IN for the hand-written original on a fully-installed `cards`
`Loop`, reproduced every existing regression this repo already had
pinned (the full buy flow, the two-listings overspend regression, the
too-risky judge regression) byte-for-byte -- the overspend one
confirmed to now genuinely take more than one tick, proving the
batching really is gone without reintroducing the bug it used to guard
against. `circuits.reads()`/`writes()` matched `loopingrules.analyze
.analyze()`'s AST-derived map on the ORIGINAL rule exactly, for all
five, on the first run for four of them.

Two real bugs were caught by that equivalence checking before any of it
was trusted, not glossed over: `Coalesce` returned its unevaluated
`default` expression node instead of the evaluated value, and the
reads-walker recursed into a component CLASS's own "fields" (`dataclasses
.is_dataclass` says yes to a class as readily as an instance) rather
than treating a type reference as a leaf.

What this does not settle, on purpose: `check_goal`'s "every want is
met" is a fold over a SET, not a per-entity circuit, and needs a shape
this catalog does not have yet; `hear_list`/`hear_want`/`hear_status`
stay plain Python, since string parsing is a different primitive axis
than numeric circuits; and the actual motivation -- a catalog a future
search/learning process could work over -- has no search or learning
built on it. See `TODO.md`, and `circuits.py`'s own docstring.

11 new tests in `tests/test_examples_circuits.py`. 183 -> 194 passing.

**`analyze.py`: a rule's reads and writes, derived from its own AST, not
declared by hand, 2026-09-03 (later).** Came out of a conversation about
whether this package should grow a small DSL for rules so a "map" of
which rules touch which components could be built from analysis instead
of trusted by convention. `analyze(fn)` walks a rule's own source and
derives its component reads/writes; `component_map(*fns)` builds the
`{component: {rule names}}` index; `check_watches(fn, watches, stable=)`
checks a rule's declared `watches=` against what it actually reads --
`loop.py`'s own docstring names this exact gap ("declare `watches` too
narrow... there is no way to catch this from here").

Chose AST analysis of plain Python over a new language because the
dialect rules are already written in turned out narrow enough to make it
sound: `PRINCIPLES.md` already establishes rules never call each other,
so the only indirection worth resolving is a same-module helper a rule
calls that also touches the world (`examples.cards._find_card`).
Anything a rule does with its world parameter outside that dialect --
aliased into a variable, forwarded into an unrelated function, a starred
call, a component argument that is not a literal `Kind(...)` -- raises
`Opaque` by name and reason rather than silently under-reporting, the
same refuse-rather-than-guess discipline `_parse_int` already applies to
a typed line. `reply`/`propose` (`loopingrules.world`, cross-module by
construction) are special-cased by identity, since this README already
promises their shape is stable.

Run against every real rule in `examples.cards` and `examples.judge` (13
rules), this comes back with ZERO `Opaque` -- the whole corpus this
package has today already fits the dialect, with no rewriting.
`check_watches`, though, produced a genuine negative result worth
recording rather than smoothing over: run with `stable=()` against
`cards.RULES`, it flags TWELVE of thirteen rules, every one a false
alarm -- `tag_affordable` reads `Purse`/`RiskProfile` without watching
either, and `tests/test_examples_cards.py`'s own `test_watches_tag_
affordable_wakes_on_listing_then_notices_a_purse_only_change` already
proves that is safe, because both are singletons seeded once at
`install()` and never removed. `stable=` fixes that category. A SECOND
category -- `decide_buy` reading `Wanted`/`Affordable`/`TooRisky`
without watching any of them, safe because those tags only ever land on
an already-watched `Listing` -- is not fixable by `stable=`, and still
(correctly) flags; `check_watches` is a hint for human review, not an
automatic gate, and that limit is pinned as a permanent, named test in
`tests/test_analyze.py` rather than a bug to loosen away.

14 new tests in `tests/test_analyze.py`, run against the real rules
rather than synthetic ones wherever that was possible. 169 -> 183
passing.

**A domain-oblivious judge, and the vocabulary question it was built to
test, 2026-09-03.** `examples/judge.py`: `Risk(level, reason)`,
`RiskTolerance(max_level)`, and `flag_too_risky`, a rule that reads only
those two and writes `TooRisky` -- the only module in `examples/` that
never imports `examples.cards` back. Built to test a question raised in
conversation: whether `loopingrules` should ship a "vast set of common
components" (`good`/`bad`/`risk`/`evaluation`...) as a lingua franca
between domains. This README and `DECISION_PATTERNS.md` already argue
against that shape in general (`facts.py`/`arbitration.py`, built,
proven inside `pystrider`, still deleted because nothing here ever
imported the SHARED version) -- so shipping a vocabulary speculatively
was declined. What survived from that conversation was `DECISION_
PATTERNS.md`'s deleted `arbitration.py`'s narrower shape: a judge
reasoning over `realizes(option, property)` -- a domain PROJECTS its own
facts onto a shared property, and an oblivious judge reads only the
projection. `examples.cards.tag_risk_level` is that projection (how much
of the affordable room a `Listing`'s price would use, as a `0..1`
float); `judge.flag_too_risky` is the judge; `decide_buy` reads its
`TooRisky` tag the same way it reads its own three.

Confirmed for real, not just under pytest: at `cash=45`, a `dragon`
listing at `40` that satisfies `Wanted`/`Affordable`/`FairPriced` still
never gets bought (`Risk.level` = 0.889, over the judge's default 0.8
tolerance), while the same listing at `cash=100` buys exactly as it did
before this change. What this settles: the projection-then-oblivious-
judge MECHANISM composes cleanly with the existing tag-reading idiom.
What it does not settle, and `judge.py`'s own docstring says so plainly:
whether one `Risk` shape actually holds across two UNRELATED domains,
since only `cards` has ever had to project onto it -- it stays in
`examples/`, not `loopingrules/`, until a second domain needs to feed
the same judge, per `DECISION_PATTERNS.md`'s "grow it only at the rule
that actually collides."

9 new tests (4 in `tests/test_examples_cards.py`, 5 in `tests/test_
examples_judge.py` -- the latter importing nothing from `cards`, pinning
the judge's own obliviousness with an AST check of its own imports).
160 -> 169 passing.

**A cards example, 2026-09-02.** `examples/cards.py`: a worked domain
kept in this repo, requested as a demonstration rather than a second
shipped domain — see the Scope section, above, for what that split
actually means in `pyproject.toml`. The scope settled on was one
autonomous agent reacting to a virtual card market by its own goal and
risk profile, deliberately not a two-party negotiation or a multi-bidder
market: no rivalry anywhere in it, so none of `Proposal`/`arbitrate`/
`census` are used at all. What the example is actually FOR is the other
mechanism this package's own vocabulary doesn't cover: `pystrider.
patterns.LoopCount` → `pystrider.constraints.TooManyLoops`'s
independent-rules-tagging-one-entity idiom, restated here as `Wanted`/
`Affordable`/`FairPriced`, three rules that share no code, composed by
one more rule (`decide_buy`) that reads all three off one `Listing` with
no idea which of them derived what.

Two things the naive version of this design got wrong, caught by a
second design pass before any code was written rather than after: the
three tags cannot use `LoopCount`'s monotonic `without=`-guarded
attach-only shape, because the facts under them (`Purse.cash`,
`Wants.qty`, `Copies.count`) mutate in place on long-lived entities while
a `Listing` sits on the market for many ticks — `LoopCount`'s guard is
only safe because a `pystrider` reread destroys and rebuilds the whole
entity, so nothing changes under a live id there. Each tag rule here
recomputes fresh every tick and goes both directions (`attach` when true,
`detach` when false) instead. Separately, `decide_buy` cannot trust the
one `each()` snapshot it materializes per call: two listings that are
each affordable ALONE but not TOGETHER — `DECISION_PATTERNS.md`'s
"composability is a structural test... exactly when footprints are
disjoint," and two candidates spending the same `Purse` do not have
disjoint footprints — would otherwise both buy in the same tick and
overspend. `decide_buy` re-fetches `Purse`/`Wants`/`Copies` fresh at the
top of each iteration and skips (never destroys) a listing this same call
already made stale, buying in listing-creation order — a regression test
(`test_decide_buy_does_not_overspend_across_two_simultaneously_qualifying_
listings_in_one_tick`) pins the fix with two such listings and asserts
`Purse.cash` never goes negative and exactly one purchase happens.

Selling is a named, deliberate gap — not built, so the example stays
small and the composition stays legible; a future `decide_sell` would
follow the same tag-then-act shape once something actually needs it, per
`DECISION_PATTERNS.md`'s "grow it only at the rule that actually
collides."

Kept OUT of `pyproject.toml`'s `packages=` — `examples/` is a top-level
directory, not a subpackage of `loopingrules/`, so `pip install -e .`
still installs `loopingrules` alone; `pythonpath = ["."]` was added to
`[tool.pytest.ini_options]` so `tests/test_examples_cards.py` can import
it anyway, the same knob and the same reason `harneskills/pyproject.toml`
already carries for its own sibling-checkout import of `loopingrules`.

24 new tests in `tests/test_examples_cards.py`, including the three
`PRINCIPLES.md`-mandated `watches=` correctness pins (each rule
registered alone on a bare `Loop`, a component outside its declared
`watches=` mutated directly, the rule still shown to fire) and the two
regressions above. 136 -> 160 passing. Manually run, too, not just under
`pytest`: `cards.install` seeded, `want dragon` then `list dragon 30`
typed as `Said`, `loop.run()` settling in two ticks with no hot rules and
replying `bought dragon for 30` then `goal met -- every wanted card is in
the collection`.

**`PRINCIPLES.md` moves in from `pystrider`, 2026-09-01.** Written there
2026-08-31 out of a design conversation about whether entity-component-rules
is a good substrate for emergent behaviour at all, and what has to be true
for the emergence to be the wanted kind (structural stigmergy through a
small vocabulary closed under what rules produce) rather than the
unwanted kind (stochastic surprise). Same move `DECISION_PATTERNS.md` made
one day earlier in the calendar but a repo-age ago: the question is about
this substrate, not about Python, so the answer belongs here even though
the evidence it cites (`pystrider/symbolic.py`, `evaluator.py`, `intake.py`)
is `pystrider`'s. `pystrider/docs/principles.md` is gone; `pystrider/
docs/TODO.md` points here instead.

**`help` gets a census, and two helpers a rule no longer has to
hand-write, 2026-08-30 (later).** A bare `help` used to answer with
`propose_default`'s own hard-coded `"try: help files, help python"` --
a string this module had no way of knowing was still complete (a
THIRD domain would never appear in it) or still correct (a domain
dropped from the config would still be advertised), and the one place
`loopingrules.help` named specific domains by hand despite its own
docstring arguing a substrate should not have to. `HelpCommandCensus`
replaces it: `open_census` claims a bare `help` the instant `hear_help`
spawns one -- the same claim-and-destroy `hear_help` already performs
on `Said` -- and opens a fresh occasion any domain can answer with
`HelpTopicName("python")`/`HelpTopicName("files")`/whatever it knows.
`close_census` reads what came back, sorted and joined, or says nobody
is registered if nothing did.

That needed a mechanism `arbitrate` does not provide: `arbitrate` picks
ONE winner and destroys the rest, correct for "who answers `help
python`" (disjoint topics, no rivalry) but wrong for "which domains
exist" (every answer is real, none are losers). `census`, in `world.py`,
is `arbitrate`'s sibling -- same two-sighting mechanism (refactored into
a shared `_resolved()` both now call, rather than duplicated), but every
candidate survives and none are picked over another. Built the moment a
SECOND real need for the "has everyone answered yet" question showed up
with a different answer required once it had — the same reasoning that
justified `arbitrate` itself over `arbitrate_parse`'s single-domain
shortcut, applied a second time.

Also added, beside `arbitrate`/`census`: `propose(w, occasion,
*components)` and `reply(w, text, channel="user")`, the one-line
spellings of `w.spawn(Proposal(occasion), ...)` and
`w.spawn(Reply(channel, text))` every `propose_*` rule and every
domain's own `_say`/`_reply` helper already hand-wrote. Deliberately
RUNTIME helpers, not a factory that builds and registers a rule for
you: they shorten what a rule's body already does without hiding
`loop.rule`/`watches` from whoever needs a shape these two do not
cover. `help.py` now uses both throughout, replacing its own local
`_say`; `HelpAnswer`'s `Proposal`-riding leg is untouched -- `help
TOPIC` still arbitrates exactly as before, only a bare `help` changed
protocol.

8 new tests in `tests/test_world.py` (`census` mirroring `arbitrate`'s
own four, plus `propose`/`reply`); `tests/test_help.py`'s own bare-`help`
test split in two (nobody registered, and two synthetic responders
registered, sorted and joined) for a net one more. 118 -> 127 passing
(`harneskills`/`pystrider` get their own responders and test updates in
their own repos, not counted here — see their own commits).

**A rule's name is unique now, and can be traced, 2026-08-30.** Two
changes, landed together because the second needed the first: `Loop.rule`
raises `ValueError` if the name it is about to register — given or
inferred (`module.function`) — is already taken on that loop, rather than
silently letting a second rule answer to a name the first one already
had; and `World` gained an opt-in write log (`World.tracing`,
`World.changes`, one `Change` per `spawn`/`destroy`/`attach`/`detach`/
`replace`/`remove`/`changed`) that `Loop.tick` drains around each rule's
own turn into `Loop.trace` — a `TraceEntry(tick, rule, changes)` per rule
per tick that wrote anything, tagged with the name that write is now
guaranteed to be unique.

Neither is new behavior a domain has to adopt: every rule this
repository's own `help.py`, and every rule `harneskills`/`pystrider`
register, already passes (or infers) a name that turns out to already be
unique in practice — checked by grepping both sibling repos' own call
sites before this landed, not asserted and hoped. The uniqueness check
turns a convention that was previously only a habit (`"effects.%s" %
name`, one per closure a factory hands back, done by hand to dodge a
collision the engine never caught) into something the engine itself
refuses to violate. Tracing is off by default in both `World` and
`Loop` — a `Change` per write is an allocation nobody should pay for
unasked — and, deliberately, goes no further than `Loop.trace` in this
pass: no `Engine` wiring, no `/trace` command, no structured sink to
write it to yet. That is the next step, on purpose left undone here
rather than guessed at before there is a caller that actually wants to
read the log somewhere specific.

15 new tests (8 in `test_loop.py`, 7 in `test_world.py`): a duplicate
explicit name refused, a duplicate inferred name refused, an inferred
name colliding with an explicit one refused, tracing off by default (on
`World` and on `Loop`), every write kind logged once tracing is on, a
no-op attach logging nothing, `detach` logging one entry per value it
actually removed (not one per kind), a raising rule still tracing
whatever it wrote before it raised, and tracing toggled off mid-session
stopping new entries without discarding old ones. 103 -> 118 passing.

**`help` moves in, 2026-08-29 (later that night).** `HelpTopic`/
`HelpAnswer`/`hear_help`/`propose_default`/`arbitrate_help`/
`reply_help_answer` lived in `harneskills.help` for about a day, then
moved here whole -- same names, same behavior, same tests, just a
different package. The reason: `pystrider.domain.propose_help_python`
had to import them from `harneskills.help`, and that made `pystrider`
depend on a SPECIFIC harness rather than on the substrate under it,
which a domain meant to be host-agnostic should never have to do.
`loopingrules` is the one thing `harneskills.examples.fs` and
`pystrider` both already depend on unconditionally; `harneskills`
never was, for `pystrider`.

This IS the one exception to "ships no rules" above, not a quiet
redefinition of it: `help.py`'s four rules are the first behavior this
package has ever installed. Nothing calls `help.install` automatically
and nothing above it imports the module -- a domain that never
mentions `help` never pays for it. No `common/` grouping either: this
is the ONLY module of its kind here, and inventing a namespace for a
second one that does not exist yet is exactly the speculative
generality `DECISION_PATTERNS.md` already argues against.

3 tests moved from `harneskills`'s own suite to `tests/test_help.py`
here (the ones that never touched `fs`); the ones that DO --
`fs` answering `help files` alongside this module -- stayed in
`harneskills`, which is the only repo that can import both without
help from `PYTHONPATH`. `pystrider`'s own `tests/test_domain_help.py`
now needs only `PYTHONPATH=../loopingrules`, not `../harneskills` too --
confirmed by actually running its suite with `harneskills` absent from
the path entirely. 100 -> 103 passing here.

**`arbitrate`, a shared chokepoint, 2026-08-29 (night).** A function,
not a component -- `arbitrate(w, occasion_type)` resolves every
ripe occasion of that type against its `Proposal`s, first-registered
wins, and reports the ones nobody answered. It exists beside `Proposal`
for the same reason `Proposal` is here at all: `harneskills.help` needed
two INDEPENDENTLY-INSTALLED domains (`harneskills.examples.fs`,
`pystrider`) to both propose against one occasion, and "has everyone
proposed yet" has no free answer once that is true -- a single domain's
own ordered rule list answers it for nothing (see
`harneskills.examples.fs.arbitrate_parse`, which calls none of this),
but two domains that do not know about each other's registration order
cannot.

The mechanism: an occasion is never resolved on the tick it is
(re)noticed. `arbitrate` tags it `_Ripe` (private, this function's own
bookkeeping) and only checks candidates on a SECOND sighting -- every
registered rule runs exactly once a tick regardless of priority, so by
then every proposer that was ever going to see it, at any priority,
from any domain, already has. That is a STRUCTURAL guarantee, not a
convention two domain authors have to independently get right (a
priority number picked to run "late enough" is exactly such a
convention, and silently wrong the day someone picks a lower one).

⚠ `arbitrate_parse` was NOT switched to call this -- it does not need
the chokepoint (its own proposers are single-domain, registration-
ordered, hand-verified in the harneskills PR that added this), and
switching it would cost every typed `fs` command an extra tick to
resolve for a safety property it does not need. `DECISION_PATTERNS.md`'s
"grow it only at the rule that actually collides" argument applies to
`arbitrate_parse` staying as it is, exactly as much as it applied to
building `arbitrate` at all once a second, real collision showed up.

4 new tests in `tests/test_world.py`: no resolution on first sighting,
first-registered-wins on the second, an unanswered occasion reported
only once ripe (read before destroyed, not after), and two different
occasion types never interfering with each other. 96 -> 100 passing.

**Proposal, a shared tag, 2026-08-29 (evening).** `Proposal` (one field,
`occasion: int`) joins `Said`/`Reply` as the third component this
package ships. It moved here from `harneskills.examples.model`, where
`docs/intake processing.md`'s propose/arbitrate/act shape was first
worked out (`fs.py`'s `propose_*` rules and `arbitrate_parse`) — the
TAG is core now, the same test `Said`/`Reply` already pass: no domain
can act on, or correctly skip, a candidate it did not propose without
agreeing what "not yet real" means, and that agreement cannot live
inside the one domain that happened to need it first. `pystrider`,
already named in that doc as the next domain expected to use this
shape, is why the question came up at all.

What did NOT move: the arbiter. "First proposal wins," or whatever a
domain grows past it, stays exactly where `arbitrate_parse` already
put it — this is not the generic reader `arbitration.py` tried to be
and was deleted for being (below). The distinction is: nothing can
interoperate without sharing what a `Proposal` MEANS, but two domains
never need to share how one gets RESOLVED, because they never resolve
each other's.

`fs.py`'s own occasion type, `ParseRequest` — "one typed line, waiting
for a reading" — stayed in `harneskills`, on purpose: it is fs's
domain-specific payload for *its* occasions, not a shape any other
domain's occasion need share.

Applied here first, not in `harneskills` -- `harneskills` still
depends on its own embedded, pre-extraction copy of this package
(`./engine`, importable as `ugm`) rather than on this repo, so this
change had to land in `harneskills`'s own checkout too, by hand, to
take effect there; the two copies are not wired together yet. One
new pin, `test_proposal_tags_a_candidate_against_any_occasion`,
95 -> 96 passing.

**loopingrules, 2026-08-29 (afternoon).** Carved out of `harneskills`'s
`./engine` into this, its own repo, and renamed from `ugm` to
`loopingrules` on the way out -- the third name this package has carried
(see "This is `ugm` a second time," below, for the second). A mechanical
rename throughout -- `ugm.world` → `loopingrules.world`, the private
`_ugm_watches`/`_ugm_priority` function attributes → `_loopingrules_
watches`/`_loopingrules_priority`, the package's own `__init__.py`
dropped the "Universal Graph Machine" acronym it no longer answers to --
with ONE deliberate exception: every History entry below this one is left
exactly as it was written, `ugm` and all, because it is an accurate record
of what this package was called at the time each entry happened, not a
description of what it is called now. `harneskills` depends on this
package by name (`loopingrules`) the same way it used to depend on `ugm`
-- nothing about `World`/`Loop`/`Engine`/`save` changed shape, only where
they are imported from.

**Facts/arbitration/request removed, 2026-08-29 (afternoon).** `facts.py`,
`arbitration.py` and `request.py` -- ON HOLD since the core rewrite below
left them unable to import -- are deleted outright, along with their
tests. Nothing in this repository ever imported any of the three
(`harneskills.examples.fs` writes its own components throughout), and
there was no third path between "port them" and "delete them" left worth
keeping open: the standing argument for a generic arbitration reader
(`DECISION_PATTERNS.md`, kept) does not need the CODE to survive, only
a domain that wants it to reach for the pattern by hand.

**Deltas removed, 2026-08-29 (midday).** A rule calls `world.spawn`/
`attach`/`replace`/`detach`/`remove`/`destroy` directly again, the same
as `install()` always did — see "Deltas, 2026-08-27" below for what this
undoes. The guarantee deltas bought (a rule that forgot the contract and
touched the world anyway got caught, named, on `loop.errors`) had already
stopped holding in practice: three rules in `harneskills`'s own test suite
called `w.spawn`/`w.destroy` directly, `loop.errors` recorded the
violation every tick, and the suite stayed green throughout because
nothing asserted it was empty. The other half of the argument for
removing it: a "proposed" action that matters to a domain is better
modelled as an explicit component sitting in the world for another rule
to query (`fs.py`'s `RenameWish` + `NeedsApproval` already does exactly
this) than as a second, lower-level notion of "not yet real" underneath
every write, including the ones no domain ever treats as provisional at
all. `ugm.delta` — `Pending`, the six delta classes, the two `_resolve_*`
functions — is deleted outright, not deprecated; `Loop.tick` is
correspondingly a few lines shorter, with nothing left to apply after
calling a rule and nothing left to check for a rule having "cheated."

**Rules, not systems, 2026-08-29 (late morning).** `Loop.system`/
`Facts.system` → `Loop.rule`/`Facts.rule`, `self.systems` → `self.rules`,
the `/systems` REPL command → `/rules`, `fs.py`'s `SYSTEMS` tuple →
`RULES`, and every docstring, comment, and README that said "a system is
a function that..." now says "a rule." "Filesystem," `SystemExit`,
`systemd`, and TOML's own `[build-system]` table name are the same words
for something else entirely and stayed put.

**Priority ordering, 2026-08-29 (mid-morning).** `Loop.rule(fn,
priority=N)` -- higher runs first, ties (the default, `0`, included) keep
registration order. The one deliberate override of "registration order
is the whole of arbitration": two rules `watches`-ing the same component
type, installed by two domains that do not know about each other and so
cannot agree on which one to register first. A rule is still one entry
in `self.rules` regardless of how many types it watches, so declaring
`priority` changes WHEN it runs, never how many times.

**A core rewrite and a request/response protocol, 2026-08-29 (morning).**
Two changes landed in one commit, because the second turned out to
depend on the first: `world.py`'s storage moved to plain
`@dataclasses.dataclass` components (no more `Component` base class),
several per entity (`attach` appends and dedupes, `replace`/`remove`
join `detach` for the singular and one-value cases, `get_all`/`all` read
the plural one), and primitives-only fields (a reference to another
entity is its plain id, never a live handle -- `World.attach` enforces
this on the way in). `ugm.save` became JSONL, version 2, dropping the
`{"$entity": ...}` wrapper a plain int no longer needs.

Built the same day on top of it: `request.py` extracted the other
pattern `docs/overview.md` had been asking for since before this
package's own split -- a rule deposits a request (a `details` entity,
characterized by ordinary facts and listed in one row of `request(hub,
details)`), any number of responders `respond`/`complete` on it without
knowing about each other or the asker, and one generic `watch()` retires
it -- `fulfilled` once every responder that started has finished,
`timed_out` if a tick budget (widened by a responder's own `extend()`)
runs out first. It was `arbitration.commit`'s counterpart for a
different shape of question ("did everyone answer" rather than "who
won"), and the one place either module fired on a clock rather than a
change: ageing the counter *is* the observable a silent, hung, or simply
absent responder needs someone to notice. `Loop.rule`'s `watches=` --
skip calling a rule's body entirely on a tick where none of its declared
component types exist yet -- landed alongside it, for the same reason:
a request nobody is answering still has to be checked on, every tick,
without every OTHER rule in a large ruleset paying for that.

This is `ugm` a second time. The first `universal-graph-machine` was a
graph substrate `harneskills` was a terminal onto — a corpus format, a
loader, attention and arbitration over a graph of facts. That dependency
was dropped and replaced with `loop.py`: a rule is a Python function
of one `World`, not a rule matched against a graph, and the loop calls
every one of them in registration order until a pass changes nothing.
This package is that replacement, carved back out once `harneskills`'s
own split between "the engine" and "the doors onto it" had already drawn
the line the old dependency used to sit on.

**A vocabulary, 2026-08-28.** `facts.py` and `arbitration.py` arrived from
`pystrider`, which had carried them since it was rewritten onto this world.
`facts.py` lost the one thing that was about living in another checkout —
`_NEEDS`, a set of `ugm` names asserted on import so that drift failed by
name rather than three frames into a run. It versions with `world.py` now,
so there is no gap left to assert across.

**A world of facts survives a restart, 2026-08-28.** It did not before, and
it failed quietly, which is the worst way. `save` resolves a component by
`module:ClassName` with `getattr`; `relation()` MAKES its classes with
`type()`; so every relation in a saved world came back as one named problem
and a dropped component, and a relation whose name collided with something
`ugm.facts` imports (`spawn`, `attach`) raised `TypeError` out of `load` and
cost the session rather than the component. A class may now say how to name
itself — `Relation` answers `ugm.facts:relation(for_stmt)`, and the trailing
call is resolved by calling it. ⭐ The second half was that interning lived
in `Facts._words`, a dict beside the world: restoring the components alone
would have given you a fact pointing at one `Printed("loop")` and every new
rule asking for another. Which entity is THE one for its text is a component
now (`Interned`), so it comes back too, and `_words` is a cache of the world
rather than the truth about it.

**Deltas, 2026-08-27.** A rule stopped being allowed to touch a world
at all. It used to call `world.spawn`/`attach`/`detach`/`destroy`
directly, applied and visible the moment it did; now it RETURNS a list
of `ugm.delta` values describing what should happen, and `Loop.tick` is
the only thing that ever calls those four methods, right after a rule
returns, before the next one runs -- so a later rule in the same tick
still sees an earlier one's own effect, the same as direct mutation
always let it. `tick()` checks this rather than trusting it: a rule
whose own code moved `world.revision` is a named, loud error on
`loop.errors`, not a silent bypass. The one real wrinkle was a `spawn`
a rule wants to use again before its own turn ends -- attach more to
it, embed it in another component's field -- solved by handing back a
`Pending` from `spawn()` that resolves to the real entity the moment its
`Spawn` is applied, walking every later delta in the same list and every
field of every component in it for the same token (`_resolve_component`,
built the way `ugm.save` already rebuilds a component off disk, without
its `__init__`).
