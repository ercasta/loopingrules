"""`help`, `help files`, `help python`, ... -- one occasion, answered by
whichever domain recognizes the topic. The propose/arbitrate/act shape
`harneskills`'s `docs/intake processing.md` names, worked here across
TWO independently-installed domains that do not know about each
other -- `harneskills.examples.fs` and `pystrider` -- rather than
inside one.

## This is the one exception to "ships no rules"

`world.py`, `loop.py`, `engine.py` and `save.py` ship no rules and
never will -- see this package's own README, "Scope." This module is
different, on purpose, and the difference is worth being honest about
rather than quietly stretching "no domain" to cover it: `hear_help`,
`open_census`, `close_census`, `arbitrate_help` and `reply_help_answer`,
below, ARE installed behavior, the first this package has ever shipped.

It is here anyway, briefly: it lived in `harneskills.help` first, and
moved after `pystrider.domain` had to import it from there to answer
`help python` alongside `fs`. That was backwards -- `pystrider` is
meant to be host-agnostic, a domain any harness could install, and
depending on `harneskills` (a SPECIFIC harness) rather than on
`loopingrules` (the substrate every domain already depends on
unconditionally) tied it to one host it should not need to know
exists. `HelpTopic`/`HelpAnswer` are not "loopingrules vocabulary" the
way `Said`/`Reply`/`Proposal` are -- nothing about the substrate needs
a `help` command -- but they are not `harneskills`'s either, once a
domain that is not `harneskills.examples.fs` needs to answer one. This
package is the only home that is neither.

**Install it or don't.** Nothing above imports this module, nothing
calls its `install` automatically, and a domain that never mentions
`help` never pays for it. `RULES`/`install`, below, are exactly the
one instance of that pattern this package carries -- not a `common/`
grouping for a SECOND one that does not exist yet.

## The shape, for `help TOPIC`

`HelpTopic(topic)` is the occasion -- never `""` by the time
`arbitrate_help`/`reply_help_answer` see one, see below -- and
`hear_help` is the only rule that ever spawns one, at HIGH priority, so
a "help ..." line becomes a `HelpTopic` before any OTHER domain's own
`hear` gets a look at the same `Said` and tries to make it mean
something else (`fs.hear` wraps EVERY `Said` regardless of content;
without this ordering, a "help files" line would cost `fs` a
spawned-and-immediately-discarded `ParseRequest` on the way to the
right answer, not just an ugly trace).

A responder -- `fs.propose_help_files`, `pystrider.propose_help_python`
-- is `for occasion, topic in w.each(HelpTopic): if I recognize
topic.topic: propose(w, occasion, HelpAnswer(...))`. `arbitrate_help`
is the arbiter, "first proposal wins" -- the SAME trivial rule
`fs.arbitrate_parse` already is, because these topics are disjoint
strings and there has never been real rivalry to judge.

## The chokepoint: when is "nobody answered" actually true?

`fs.arbitrate_parse` never has to ask this question -- `fs.hear` and
every `propose_*` that could possibly answer are ALL registered in one
ordered tuple, by fs's own `install()`, so "every responder already had
its turn" is just "arbitrate_parse is listed last." That stops being
true the moment a SECOND, separately-installed domain -- `pystrider`,
here -- can also propose: nothing in the rule list guarantees
`pystrider.propose_help_python` ran before `arbitrate_help` looks,
because they are registered by two different `install()` calls that do
not know about each other or their order in the config.

Priority alone does not fix this, it only narrows the race: a low
priority on the arbiter is a bet that no proposer will ever be
registered lower still, correct today, checked by nobody tomorrow, and
silent if it is ever wrong -- a proposer that loses the bet is simply
never seen, with no error anywhere.

`arbitrate`, in `world.py`, is the actual fix, and it does not depend
on priority at all: an occasion is never resolved on the tick it is
(re)noticed, only on a SECOND sighting, by which point every rule that
watches for it -- at any priority, from any domain, known to this
module or not -- has already had its one turn that tick. `arbitrate_help`
below just calls it and decides what to SAY about an occasion nobody
answered; `hear_help`'s HIGH priority is a different, narrower thing --
see its own docstring -- and neither `arbitrate_help` nor
`reply_help_answer` needs any priority at all, and neither carries one.

## The shape, for a bare `help`: a census, not a contest

A bare `help` used to get `propose_default`'s own hard-coded hint --
`"try: help files, help python"` -- a string this module had no way of
knowing was still true (a THIRD domain answering `help kelvinator`
would never show up in it) or was still even valid (a domain dropped
from the config would still be advertised). It named `fs`/`pystrider`
by hand, which is exactly the dependency this module's own docstring,
above, says a substrate should not have on one harness's specific
domains.

`HelpCommandCensus` replaces that hint with a live one. `open_census`
claims a `HelpTopic("")` the instant it is seen -- the same way
`hear_help` claims a `Said` -- destroys it, and spawns a fresh
`HelpCommandCensus` in its place: a bare `help` never reaches
`arbitrate_help` at all, so that rule's own `HelpTopic` handling never
has to special-case an empty topic. Any domain that wants `help` to
list it registers its own responder -- `propose_help_python` below is
one, in `pystrider.domain`; `fs.propose_help_census_files` is another
-- `for occasion, _c in w.each(HelpCommandCensus): propose(w, occasion,
HelpTopicName("python"))`.

This is `census`, in `world.py`, not `arbitrate`: there is no rivalry
to pick a winner from, only an inventory to collect, so EVERY responder
that proposed counts, not just the first. `close_census` reads what
`census` resolved, sorts and joins the topic names it collected into
one line, and says it -- or says that nobody has registered one, if
`census` resolved with nothing. Either way this is the one place a
`HelpCommandCensus` ever turns into a `Reply`: unlike `HelpTopic`,
there is no `Proposal`/`arbitrate`/`HelpAnswer` leg to ride through
first, because there is no winner to arbitrate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .world import Proposal, Said, arbitrate, census, propose, reply


@dataclass(frozen=True)
class HelpTopic:
    """The occasion: someone typed `help TOPIC`. Never `""` -- see
    `HelpCommandCensus` for what a bare `help` becomes instead, and
    `hear_help` for where that split happens."""

    topic: str


@dataclass(frozen=True)
class HelpAnswer:
    """What a winning candidate says, once real. Rides alongside
    `Proposal` on the same candidate entity until `arbitrate_help`
    detaches it -- the same trick every `fs` goal already plays."""

    text: str


@dataclass(frozen=True)
class HelpCommandCensus:
    """The occasion a bare `help` becomes: not who WINS (nothing here
    rivals anything else) but who wants to be LISTED. Any rule that
    watches this and recognizes itself should `propose(w, occasion,
    HelpTopicName(...))` -- see this module's own docstring, the
    section on a bare `help`, for the whole shape."""


@dataclass(frozen=True)
class HelpTopicName:
    """A census candidate's payload: "`help NAME` is mine to answer."
    `close_census` is the only rule that ever reads this."""

    name: str


def hear_help(w) -> None:
    """`Said("help")` / `Said("help TOPIC")` -> a `HelpTopic`, and the
    `Said` is claimed (destroyed) immediately -- "help" is this
    module's verb, the same as `show` is `fs`'s, and nothing else gets
    to have an opinion about what it means.

    HIGH priority (see `install`): must run before any other domain's
    own `hear`, or a "help ..." line is this module's to answer only
    AFTER detouring through whatever that other domain's `hear` does
    with an unclaimed line first.
    """
    for entity, said in w.each(Said):
        words = said.text.split(None, 1)
        if not words or words[0].lower() != "help":
            continue
        topic = words[1].strip() if len(words) > 1 else ""
        w.destroy(entity)
        w.spawn(HelpTopic(topic))


def open_census(w) -> None:
    """A bare `help` (`HelpTopic("")`) is not one domain's occasion to
    answer -- see this module's own docstring -- so it is claimed here,
    immediately, the same way `hear_help` claims a `Said`: destroyed
    the instant it is seen, and replaced with a fresh
    `HelpCommandCensus` for every domain that knows a topic to offer
    instead.

    `hear_help`'s HIGH priority already guarantees a `HelpTopic` this
    rule sees was spawned earlier in the SAME tick, so a bare `help`
    never survives to a second tick regardless of where in that tick
    this rule happens to run relative to `arbitrate_help` -- neither
    needs a priority of its own for that reason, and neither carries
    one.
    """
    for occasion, topic in w.each(HelpTopic):
        if topic.topic == "":
            w.destroy(occasion)
            w.spawn(HelpCommandCensus())


def close_census(w) -> None:
    """Once `census` (see `world.py`) says every domain that watches
    `HelpCommandCensus` has had its turn, the topic names they offered
    are sorted, joined, and said -- or, if nobody offered any, said as
    that instead, not silently swallowed."""
    for _occasion, _component, candidates in census(w, HelpCommandCensus):
        names = sorted(w.get(c, HelpTopicName).name for c in candidates
                       if w.has(c, HelpTopicName))
        for candidate in candidates:
            w.destroy(candidate)
        if names:
            reply(w, "try: " + ", ".join("help %s" % name for name in names))
        else:
            reply(w, "no help topics are registered")


def arbitrate_help(w) -> None:
    """One winner per `HelpTopic`, via `arbitrate` (see `world.py`) --
    see this module's own docstring, "The chokepoint," for why this
    occasion needs that function and `fs.arbitrate_parse` does not.
    Never sees a `""` topic -- `open_census` claims those first.

    A topic nobody answered is SAID, not swallowed: `hear_help` already
    claimed the line, so the engine's own generic "unheard" report --
    which only ever sees a `Said` still standing at settle -- never
    fires for it. Silence here would be a topic that got no answer at
    all, not a topic no one understood.
    """
    for occasion, topic in arbitrate(w, HelpTopic):
        reply(w, "no help for %r" % topic.topic)


def reply_help_answer(w) -> None:
    """The winning `HelpAnswer` -> a `Reply`, once `Proposal` is gone
    (arbitration is done) -- `without=Proposal` is what keeps this from
    ever answering a candidate still rivalling another for the same
    occasion."""
    for entity, answer in w.each(HelpAnswer, without=Proposal):
        w.destroy(entity)
        reply(w, answer.text)


RULES = (hear_help, open_census, close_census, arbitrate_help,
         reply_help_answer)


def install(loop) -> None:
    """Register this module's five rules and the one word this domain
    adds to what the prompt's autocorrect pulls a typo towards.

    Only `hear_help` needs a priority -- ahead of any other domain's
    own `hear`, for the reason its own docstring gives. Every other
    rule here needs none: `arbitrate`/`census` are what make
    `arbitrate_help`/`close_census` correct independent of registration
    order, and `open_census` only ever needs to run after `hear_help`
    within the same tick, which `hear_help`'s own priority already
    guarantees regardless of where in `RULES` `open_census` sits.
    """
    loop.rule(hear_help, priority=50, watches=(Said,))
    loop.rule(open_census, watches=(HelpTopic,))
    loop.rule(close_census, watches=(HelpCommandCensus,))
    loop.rule(arbitrate_help, watches=(HelpTopic,))
    loop.rule(reply_help_answer, watches=(HelpAnswer,))
    loop.world.learn("help")
