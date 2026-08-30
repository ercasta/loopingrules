"""`help`, on its own: the occasion, the census a bare `help` becomes,
and an unanswered topic -- the one exception to "ships no rules" (see
`help.py`'s own docstring), pinned in isolation. Cross-domain
integration (`harneskills.examples.fs` and `pystrider` both answering
alongside this) is `harneskills`'s own `tests/test_help.py` and
`pystrider`'s `tests/test_domain_help.py` -- this package does not
depend on either."""

from loopingrules import help as help_
from loopingrules.loop import Loop
from loopingrules.world import Proposal, Reply, Said, propose


def say(loop, line):
    """One typed line, settled, and every reply it produced."""
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
            if w.destroy(entity) or True]


def test_a_bare_help_with_nobody_registered_says_so():
    loop = Loop()
    help_.install(loop)
    assert say(loop, "help") == ["no help topics are registered"]


def test_a_bare_help_lists_every_registered_topic_sorted_and_joined():
    loop = Loop()
    help_.install(loop)

    def offer(name):
        def rule(w):
            for occasion, _c in w.each(help_.HelpCommandCensus):
                propose(w, occasion, help_.HelpTopicName(name))
        return rule

    loop.rule(offer("python"), name="offer-python",
             watches=(help_.HelpCommandCensus,))
    loop.rule(offer("files"), name="offer-files",
             watches=(help_.HelpCommandCensus,))
    assert say(loop, "help") == ["try: help files, help python"]


def test_a_topic_nobody_answers_is_said_not_swallowed():
    loop = Loop()
    help_.install(loop)
    assert say(loop, "help therealm") == ["no help for 'therealm'"]


def test_settling_leaves_nothing_behind():
    loop = Loop()
    help_.install(loop)
    say(loop, "help")
    w = loop.world
    assert w.each(help_.HelpTopic) == []
    assert w.each(help_.HelpCommandCensus) == []
    assert w.each(help_.HelpTopicName) == []
    assert w.each(Proposal) == []
    assert w.each(help_.HelpAnswer) == []
    assert w.each(Said) == []
