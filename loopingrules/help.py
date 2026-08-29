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
`propose_default`, `arbitrate_help` and `reply_help_answer`, below, ARE
installed behavior, the first this package has ever shipped.

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

## The shape

`HelpTopic(topic)` is the occasion -- "" for a bare `help`, the rest of
the line otherwise. `hear_help` is the only rule that ever spawns one,
at HIGH priority, so a "help ..." line becomes a `HelpTopic` before any
OTHER domain's own `hear` gets a look at the same `Said` and tries to
make it mean something else (`fs.hear` wraps EVERY `Said` regardless of
content; without this ordering, a "help files" line would cost `fs` a
spawned-and-immediately-discarded `ParseRequest` on the way to the
right answer, not just an ugly trace).

A responder -- `propose_default` below, `fs.propose_help_files`,
`pystrider.propose_help_python` -- is `for occasion, topic in
w.each(HelpTopic): if I recognize topic.topic: w.spawn(Proposal(occasion.id),
HelpAnswer(...))`. `arbitrate_help` is the arbiter, "first proposal
wins" -- the SAME trivial rule `fs.arbitrate_parse` already is, because
these topics are disjoint strings and there has never been real
rivalry to judge.

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
"""

from __future__ import annotations

from dataclasses import dataclass

from .world import Proposal, Reply, Said, arbitrate


@dataclass(frozen=True)
class HelpTopic:
    """The occasion: someone typed `help`, or `help TOPIC`. `topic` is
    `""` for a bare `help`, never `None` -- a responder that only cares
    about one exact topic string never has to spell out two cases
    where this component only ever carries one."""

    topic: str


@dataclass(frozen=True)
class HelpAnswer:
    """What a winning candidate says, once real. Rides alongside
    `Proposal` on the same candidate entity until `arbitrate_help`
    detaches it -- the same trick every `fs` goal already plays."""

    text: str


def _say(w, text: str) -> None:
    w.spawn(Reply("user", text))


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


def propose_default(w) -> None:
    """The THIRD responder: a bare `help` belongs to no one domain, so
    it is this module's own candidate, not a domain's. The only place
    here that names another domain's topic, and only as a hint for a
    person to type next -- not an import, and not something this
    module checks."""
    for occasion, topic in w.each(HelpTopic):
        if topic.topic == "":
            w.spawn(Proposal(occasion.id),
                   HelpAnswer("try: help files, help python"))


def arbitrate_help(w) -> None:
    """One winner per `HelpTopic`, via `arbitrate` (see `world.py`) --
    see this module's own docstring, "The chokepoint," for why this
    occasion needs that function and `fs.arbitrate_parse` does not.

    A topic nobody answered is SAID, not swallowed: `hear_help` already
    claimed the line, so the engine's own generic "unheard" report --
    which only ever sees a `Said` still standing at settle -- never
    fires for it. Silence here would be a topic that got no answer at
    all, not a topic no one understood.
    """
    for occasion, topic in arbitrate(w, HelpTopic):
        _say(w, "no help for %r" % topic.topic)


def reply_help_answer(w) -> None:
    """The winning `HelpAnswer` -> a `Reply`, once `Proposal` is gone
    (arbitration is done) -- `without=Proposal` is what keeps this from
    ever answering a candidate still rivalling another for the same
    occasion."""
    for entity, answer in w.each(HelpAnswer, without=Proposal):
        w.destroy(entity)
        _say(w, answer.text)


RULES = (hear_help, propose_default, arbitrate_help, reply_help_answer)


def install(loop) -> None:
    """Register this module's four rules and the one word this domain
    adds to what the prompt's autocorrect pulls a typo towards.

    Only `hear_help` needs a priority -- ahead of any other domain's
    own `hear`, for the reason its own docstring gives. `arbitrate_help`
    and `reply_help_answer` need none: `arbitrate` is what makes their
    correctness independent of registration order, not where they sit
    in this list or what priority they carry.
    """
    loop.rule(hear_help, priority=50, watches=(Said,))
    loop.rule(propose_default, watches=(HelpTopic,))
    loop.rule(arbitrate_help, watches=(HelpTopic,))
    loop.rule(reply_help_answer, watches=(HelpAnswer,))
    loop.world.learn("help")
