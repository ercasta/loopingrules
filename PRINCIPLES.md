# Principles — what makes the entity/component/rules substrate produce the RIGHT kind of emergent behaviour

*Written 2026-08-31 as a design note inside `pystrider` (a domain that reads and writes Python on
this world), out of a design conversation (not solo) about whether entity-component-rules — this
package's `World` + forward-chained rules run to a fixpoint — is a good substrate for emergent
behaviour at all, and if so, what has to be true for the emergence to be the WANTED kind. This file
is the answer that conversation landed on — policy for every session on this substrate after this
one, not just a record of it. Moved here 2026-09-01: the question and the answer are both about the
substrate, not about Python or any one domain running on it.*

*⭐ It lives in `loopingrules` (this package) rather than in the domain that produced it for the same
reason `DECISION_PATTERNS.md` does — see that file's own note. The evidence below is `pystrider`'s
(`symbolic.py`'s `_parent_of`/`_reachable`, `evaluator.py`'s membrane bug, `intake.py`'s `PARTS`)
because that is who paid for it first; the pattern is not. `pystrider/docs/TODO.md`'s own opening
paragraph ("there are NO mechanical transformations... always a passage through semantics") is this
same instinct, stated once, for a narrower question; this file generalizes it and should be read
alongside that paragraph, not instead of it.*

## What kind of emergence this is actually for

"Emergent behaviour" hides at least two different things, and this substrate
is deliberately built for only one of them.

Rules here are oblivious of each other — no rule calls another, the only
channel between them is what gets deposited into the shared `World`. That
*is* real, structural stigmergy: `patterns.LoopCount` gets attached with zero
awareness that `constraints.max_loops` exists; `constraints.max_loops` fires
purely because `LoopCount` showed up. Nobody wrote that pipeline; it
assembles from independently-authored, mutually-ignorant rules the same way
a blackboard architecture's knowledge sources do (Hearsay-II is the direct
architectural ancestor of this shape). That is the kind of emergence this
repo wants, and gets: complex, composed conclusions arising from many small,
individually-legible rules, with the composition never explicitly written
by anyone.

It is **not**, and should not try to be, the kind of emergence that wants
surprise for its own sake — flocking, cellular automata, genetic search,
anything that benefits from stochastic exploration or tolerates noisy local
rules producing an unpredictable but interesting aggregate. Every session
note in this codebase (`evaluator.py`'s "a membrane described in prose is
not a membrane," the `KnownValue` staleness bug, the abstention discipline
everywhere) is optimizing *against* that kind of surprise. A surprising
conclusion here is a bug report, not a feature. Keep that distinction in
mind before reaching for a pattern below to solve a problem that actually
wants a different substrate (an agent-based simulation framework, a
differentiable/continuous one, a genetic-search one) instead.

## The actual lever: a small vocabulary, CLOSED under what rules produce

The mechanism is not "few component types" by itself — it is that a rule's
*conclusion* re-enters the substrate looking exactly like ordinary,
observed structural fact. `KnownValue`, `LoopCount`, `BoundTo` are plain
components, attached the same way `intake.py`'s `Body` or `Name` is; nothing
marks a fact "derived" versus "observed." That is what lets
`constraints.max_loops` read `LoopCount` without knowing or caring that it
came from three hops of reasoning, and it is what will let some future rule
read `BoundTo` the same way. A rule three layers into a derivation chain
looks exactly like one reading the AST directly — so nobody has to design
the chain, it accretes.

The clearest evidence of this from inside the codebase: `pystrider/
symbolic.py`'s `_parent_of`/`_reachable` (2026-08-31) walk `set(intake.PARTS.
values())` generically — they know nothing about `Assign`, `Call`, `If`, or
`For` specifically. They correctly resolved a `Name` buried three hops deep
inside a bare-call statement (`Callee → Call → Stmt → Block → Body →
Function`) without that specific combination ever being enumerated, because
the vocabulary they walk is the same small, closed one `intake.py` and
`pystrider/denotation.py`'s `Step` already share (`denotation.py:13`, "never
a second vocabulary invented here"). A larger, per-construct-specific edge
vocabulary would have made that walker impossible to write generically at
all.

## To promote it

**⭐ Before minting a new edge/component type, check whether an existing
vocabulary already names the shape.** `denotation.Step` reusing
`intake.PARTS` rather than inventing a second hop vocabulary is the model —
see `intake.py`'s own `PARTS` table (`intake.py:373`) and its docstring
("⭐ PUBLIC... since `pystrider.denotation`'s `Step` walks the SAME label
vocabulary rather than inventing a second one"). A new part-edge type is a
decision to justify, not a default.

**A rule's conclusion must re-enter the substrate as an ordinary component,
never a distinguishable "result" wrapper.** No bespoke "Answer"/"Conclusion"
supertype a consumer has to unwrap differently than it would unwrap a raw
fact — `KnownValue`/`LoopCount`/`BoundTo` all follow this already; every new
analysis should too.

**Prefer a generic walker over the shared vocabulary to a construct-by-
construct switch.** When a new capability needs "walk up/down the
structure," reach for something shaped like `_parent_of`/`_reachable`
(`symbolic.py`) before writing a bespoke per-construct traversal. That is
what lets new compositions become answerable by code nobody wrote with that
specific combination in mind.

## To guard it

**⚠⚠ A wrong conclusion is worse than a missing one — make abstention
STRUCTURAL, not prose.** This is the one non-negotiable rule of the whole
paradigm, more than any other item here. In an oblivious-experts
architecture a bad guess does not stay local — it becomes false premise for
every downstream rule that picks it up, with no way to tell it apart from a
true one. `evaluator.py`'s own ⚠⚠⚠ names the real bug this caused once: "An
earlier evaluator's comment said it modelled `gt`/`ge` only; the code fell
through to the `gt` path for everything else... **A membrane described in
prose is not a membrane.**" (`evaluator.py:12-16`). Every partial mapping in
this codebase (`_DECIDES`, `_ARITH`/`_COMPARE`) is the fix: an explicit
table that refuses by NAME, not a comment that refuses by intention. Any
new rule that can be uncertain must be able to produce nothing, structurally
— not "try to guess and hope."

**`watches=` correctness should be tested, not just reviewed.**
`loopingrules/loop.py`'s own docstring names the exact risk: declare
`watches` too narrow and "the rule goes dormant while something it depended
on sits unnoticed on a type it never declared... not too much firing, but a
rule that should have fired and silently didn't. There is no way to catch
this from here." That is a standing invitation to a silent regression.
Concretely actionable: any rule registered with `watches=` should have a
test that mutates something *not* obviously in the watched set and confirms
the rule still eventually fires — testing the over-approximation directly,
not just the happy path.

**Guard vocabulary collision with a check, not just a comment.** This
already exists in one place — `tests/test_spine.py::
test_intake_and_the_descriptions_share_NO_vocabulary` asserts `patterns.py`'s
`Iteration`/`Choice`/`Applies`/`LoopCount` are not also defined in
`intake.py`, straight off `patterns.py`'s own docstring rule ("Intake must
not reuse a description's word," `patterns.py:18`). It is scoped to those
four names by hand, not to every domain's vocabulary against `PARTS`/each
other generally. As more description modules accrete (`symbolic.py`'s
`KnownValue`/`BoundTo`, `constraints.py`'s `TooManyLoops`, `evaluator.py`'s
`Guard`/`IfStmtOf`/`BlockOf`...) this check should grow with them, or the
next accidental collision has nothing automated standing in its way.

**Disagreement between rules gets explicit arbitration, never implicit
priority.** `repair.py`'s `Verdict` (`"forced"` vs. `"ambiguous"`,
`repair.py:199-205`) is the existing primitive for this. `priority=` should
stay reserved for genuine two-phase pipelining — `domain.py`'s `_read`
before `patterns`, `_report_read` after — never for silently picking a
winner between two rules that substantively disagree about the same fact.
The moment registration order is doing arbitration's job, the disagreement
it is resolving has become invisible; it should be a `Verdict`-shaped
deposit instead, named where anyone can query it.

**Termination is a safety net, not a guarantee — check it, don't just have
it available.** `loopingrules/loop.py`'s `budget`/hot-rule reporting
(`Settled(ticks, hot)`) exists because "two rules can feed each other
forever... nothing detects that in general." As the rule count grows, a new
rule that accidentally creates a feedback loop with an existing one should
fail a test, not quietly become a "hot" rule nobody scripted anything to
notice.

**No caching until a rule's own cost is empirically the bottleneck it
names.** The "recompute fresh, never cache" discipline (`fold`, `bound_to`,
`_parent_of`/`_reachable`'s full linear scans) is correct at today's scale
and is what makes the TMS guarantee (`pystrider/evaluation.py`) cheap to
earn. It will not stay free forever — `watches=` buys dormancy for rules
whose subject matter never appears at all, but a rule that IS awake still
rescans its component type's full current extension every tick, not a delta
since last tick (no semi-naive evaluation here). The signal to introduce
real indexing for a specific hot path is that path's own cost becoming
visible and named, not scale anticipated in advance — the same "do one
concretely first" instinct this codebase already applies to `Qualname`
disambiguation and the constraint catalog.
