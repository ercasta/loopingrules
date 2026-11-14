"""`examples.quorum` -- a decision that is a COUNT over a set."""

from __future__ import annotations

from examples import quorum
from loopingrules.loop import Loop


def vote_world(needed, *choices):
    loop = Loop()
    quorum.install(loop, needed=needed)
    world = loop.world
    motion = world.spawn()
    world.mark(motion, "motion")
    world.set(motion, "name", "m")
    for choice in choices:
        vote = world.spawn()
        world.mark(vote, "vote")
        world.set(vote, "motion", motion)
        world.set(vote, "choice", choice)
    loop.run()
    return world, motion


def test_a_motion_passes_at_the_quorum():
    world, motion = vote_world(2, "for", "for", "against")
    assert world.has(motion, "passed")


def test_a_motion_fails_below_the_quorum():
    world, motion = vote_world(3, "for", "against", "against")
    assert not world.has(motion, "passed")


def test_against_votes_never_count():
    world, motion = vote_world(1, "against", "against")
    assert not world.has(motion, "passed")


def test_motions_are_tallied_independently():
    loop = Loop()
    quorum.install(loop, needed=2)
    world = loop.world
    first = world.spawn()
    world.mark(first, "motion")
    second = world.spawn()
    world.mark(second, "motion")
    for motion, choice in ((first, "for"), (first, "for"),
                           (second, "for"), (second, "against")):
        vote = world.spawn()
        world.mark(vote, "vote")
        world.set(vote, "motion", motion)
        world.set(vote, "choice", choice)
    loop.run()
    assert world.has(first, "passed")
    assert not world.has(second, "passed")


def test_tally_abstains_without_a_quorum_seeded():
    loop = Loop()
    loop.rule(quorum.tally)
    world = loop.world
    motion = world.spawn()
    world.mark(motion, "motion")
    vote = world.spawn()
    world.mark(vote, "vote")
    world.set(vote, "motion", motion)
    world.set(vote, "choice", "for")
    loop.tick()
    assert not world.has(motion, "passed")
