"""The checks vocabulary (`docs/plan-dataset.md`, D2; Phase 4).

A Check is a pure, named, weighted term; `total` composes the scorer; the
generic checks are the ones every trace has. If scoring ever moved the world
it measures, the offline/online seam (`docs/plan-adaptation.md`) would be
broken -- so purity is the first thing pinned.
"""

import dataclasses

from loopingrules.world import World
from loopingrules_calibration import checks
from loopingrules_calibration.kit import Trace


@dataclasses.dataclass(frozen=True)
class Thing:
    n: int


def _trace(hot=(), ticks=1, replies=(), world=None, observations=()):
    return Trace("sig", (), ticks, hot, tuple(replies),
                 world if world is not None else World(), tuple(observations))


def test_check_is_named_weighted_and_pure():
    ran = []

    @checks.check("count", weight=2.0)
    def term(trace):
        ran.append(True)
        return 3.0

    trace = _trace()
    before = trace.world.revision
    assert term.name == "count" and term.weight == 2.0
    assert term.score(trace) == 6.0
    assert term(trace) == 6.0
    assert trace.world.revision == before, "a check must not move what it reads"
    assert ran


def test_total_composes_weighted_terms():
    a = checks.Check("a", lambda trace: 1.0, weight=1.0)
    b = checks.Check("b", lambda trace: 2.0, weight=0.5)
    assert checks.total(a, b)(_trace()) == 2.0        # 1*1 + 0.5*2


def test_settles_and_ticks():
    assert checks.settles()(_trace()) == 1.0
    assert checks.settles()(_trace(hot=("x",))) == 0.0
    assert checks.ticks_at_most(2)(_trace(ticks=2)) == 1.0
    assert checks.ticks_at_most(2)(_trace(ticks=3)) == 0.0


def test_says_reads_output_only():
    assert checks.says("hi")(_trace(replies=("say hi",))) == 1.0
    assert checks.says("hi")(_trace(replies=("bye",))) == 0.0


def test_world_has_reads_the_settled_world():
    world = World()
    marker = world.spawn()
    world.mark(marker, "thing")
    assert checks.world_has("thing")(_trace(world=world)) == 1.0
    assert checks.world_has("thing")(_trace()) == 0.0


def test_invariant_is_vacuous_when_nothing_was_observed():
    assert checks.invariant(lambda n: n >= 0)(_trace(observations=(1, 2))) == 1.0
    assert checks.invariant(lambda n: n >= 0)(_trace(observations=(1, -1))) == 0.5
    assert checks.invariant(lambda n: False)(_trace(observations=())) == 1.0


def test_as_check_wraps_a_plain_scorer():
    term = checks.as_check("half", lambda trace: 0.5, weight=2.0)
    assert term(_trace()) == 1.0
