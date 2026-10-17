"""`examples.quorum` -- a decision that is a COUNT over a set. Convention
mirrors the other example tests: build a small world, run it, read tags."""

from examples import quorum
from loopingrules.loop import Loop


def vote_world(needed, *choices):
    loop = Loop()
    quorum.install(loop, needed=needed)
    world = loop.world
    motion = world.spawn(quorum.Motion("m"))
    for choice in choices:
        world.spawn(quorum.Vote(motion, choice))
    loop.run()
    return world, motion


def test_a_motion_passes_at_the_quorum():
    world, motion = vote_world(2, "for", "for", "against")
    assert world.has(motion, quorum.Passed)


def test_a_motion_fails_below_the_quorum():
    world, motion = vote_world(3, "for", "against", "against")
    assert not world.has(motion, quorum.Passed)


def test_against_votes_never_count():
    world, motion = vote_world(1, "against", "against")
    assert not world.has(motion, quorum.Passed)


def test_motions_are_tallied_independently():
    loop = Loop()
    quorum.install(loop, needed=2)
    world = loop.world
    first = world.spawn(quorum.Motion("first"))
    second = world.spawn(quorum.Motion("second"))
    world.spawn(quorum.Vote(first, "for"))
    world.spawn(quorum.Vote(first, "for"))
    world.spawn(quorum.Vote(second, "for"))
    world.spawn(quorum.Vote(second, "against"))
    loop.run()
    assert world.has(first, quorum.Passed)
    assert not world.has(second, quorum.Passed)


def test_tally_abstains_without_a_quorum_seeded():
    loop = Loop()
    loop.rule(quorum.tally)
    world = loop.world
    motion = world.spawn(quorum.Motion("m"))
    world.spawn(quorum.Vote(motion, "for"))
    loop.tick()
    assert not world.has(motion, quorum.Passed)
