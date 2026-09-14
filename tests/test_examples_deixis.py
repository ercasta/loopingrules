"""`examples.deixis` -- `loopingrules.memory`'s `Focus`/`Memory`/
`MemoryEntry`, proven against a real (if tiny) reference-resolution
rule rather than direct calls to `track_focus`. What's pinned: focus
moves one entity at a time; a name typed twice, with something else
focused in between, still resolves "it" to the SECOND visit, not the
first (the one behavior a trail gives that a single "current topic"
flag could not); and an unrecognized name or an empty trail gets a
reply, not silence.
"""

from loopingrules.loop import Loop
from loopingrules.world import Reply, Said

from examples import deixis


def _say(loop, text):
    loop.world.spawn(Said("user", text))
    loop.run()


def _last_reply(w):
    replies = w.each(Reply)
    assert replies, "nothing replied"
    return replies[-1][1].text


def _install(*names):
    loop = Loop()
    deixis.install(loop)
    for name in names:
        loop.world.spawn(deixis.Named(name))
    return loop


def test_it_with_nothing_ever_focused_gets_an_honest_reply():
    loop = _install("a")
    _say(loop, "it")
    assert _last_reply(loop.world) == "not sure what that refers to"


def test_looking_at_an_unknown_name_replies_and_does_not_focus_anything():
    loop = _install("a")
    _say(loop, "look at ghost")
    assert _last_reply(loop.world) == "no such thing: ghost"
    assert loop.world.first(deixis.Focus) is None


def test_it_resolves_to_the_one_thing_ever_looked_at():
    loop = _install("a")
    _say(loop, "look at a")
    _say(loop, "it")
    assert _last_reply(loop.world) == "that's a"


def test_focus_moving_between_two_names_makes_it_track_the_latest():
    loop = _install("a", "b")
    _say(loop, "look at a")
    _say(loop, "look at b")
    _say(loop, "it")
    assert _last_reply(loop.world) == "that's b"
    # only ONE entity is focused at a time in this domain
    focused = loop.world.each(deixis.Focus)
    assert len(focused) == 1


def test_a_revisited_name_resolves_to_the_second_visit_not_the_first():
    """The behavior a bare `Focused` flag could not give: two separate
    visits to `a`, with `b` focused in between, are two separate trail
    entries -- `"it"` after coming BACK to `a` means the second one."""
    loop = _install("a", "b")
    _say(loop, "look at a")
    _say(loop, "look at b")
    _say(loop, "look at a")
    _say(loop, "it")
    assert _last_reply(loop.world) == "that's a"
    from loopingrules import memory
    trail = memory.trail(loop.world)
    assert [entry.entity for entry in trail] == [
        deixis._find_named(loop.world, "a").id,
        deixis._find_named(loop.world, "b").id,
        deixis._find_named(loop.world, "a").id,
    ]
