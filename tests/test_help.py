"""`help`, on its own: the occasion, the third (default) responder, and
an unanswered topic -- the one exception to "ships no rules" (see
`help.py`'s own docstring), pinned in isolation. Cross-domain
integration (`harneskills.examples.fs` and `pystrider` both answering
alongside this) is `harneskills`'s own `tests/test_help.py` and
`pystrider`'s `tests/test_domain_help.py` -- this package does not
depend on either."""

from loopingrules import help as help_
from loopingrules.loop import Loop
from loopingrules.world import Proposal, Reply, Said


def say(loop, line):
    """One typed line, settled, and every reply it produced."""
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
            if w.destroy(entity) or True]


def test_a_bare_help_gets_the_default_answer():
    loop = Loop()
    help_.install(loop)
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
    assert w.each(Proposal) == []
    assert w.each(help_.HelpAnswer) == []
    assert w.each(Said) == []
