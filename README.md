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
tests/
  test_world.py        identity, values, and the intersection of the two
  test_loop.py         order, settling, the budget, a rule that raises
  test_engine.py       one world, several channels, a broadcast reply
  test_save.py         the same world, ids and all, next time
DECISION_PATTERNS.md   a design note this package no longer ships the code
                          for -- see History, "Facts/arbitration/request
                          removed"
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

## History

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
