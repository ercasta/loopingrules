"""i0's claims, as permanent verification points (`docs/plan-islands.md`).

The islands/bridges shape must WORK (settle, reuse, compose) and its
antipattern must be CATCHABLE -- a check that cannot fail is not a check.
"""

from __future__ import annotations

from loopingrules import Loop
from loopingrules_calibration import knobs, lint

from loopingrules_islands import funds, i0, items


def _find(world, name, field, match):
    for entity, _t, value in world.each(name, field):
        if match(value):
            return entity
    raise AssertionError("no %s matched" % name)


def test_shape_settles_and_replays_to_one_signature():
    """Claim 1: the shape reaches a fixpoint, and replay is deterministic."""
    first = i0.clean_trace()
    second = i0.clean_trace()
    assert not first.hot
    assert first.ticks == second.ticks
    assert first.signature == second.signature


def test_island_decision_is_declared_and_lint_clean():
    """Claim 2: each island owns its decision, declares it with `@tunable`,
    and hard-codes no threshold."""
    loop = Loop()
    i0.install(loop)
    declared = {knob.name for knob in knobs(loop)}
    assert "min_worth" in declared
    assert "reserve" in declared
    report = lint(loop)
    assert report.findings == ()
    assert report.unlintable == ()


def test_two_domains_reuse_the_same_island():
    """Claim 3: `cards` and `lots` land on the SAME `items` island, zero
    island rules rewritten."""
    world = i0.clean_trace().world
    dragon = _find(world, "card", "name", lambda name: name == "dragon")
    goblin = _find(world, "card", "name", lambda name: name == "goblin")
    lot1 = _find(world, "lot", "ref", lambda ref: ref == "lot-1")
    assert world.has(dragon, "item")
    assert world.has(lot1, "item")
    assert not world.has(goblin, "item")        # below the island's policy
    inventory = world.first("inventory")[0]
    assert (world.get(inventory, "total"), world.get(inventory, "count")) == (160.0, 3)


def test_conjunction_reads_across_two_islands():
    """Claim 4: a composer reads the `item` role and the `spendable` amount
    and concludes something neither island can."""
    world = i0.clean_trace().world
    assert world.first("spendable")[1] == 60.0            # 70 - 10
    dragon = _find(world, "card", "name", lambda name: name == "dragon")
    lot2 = _find(world, "lot", "ref", lambda ref: ref == "lot-2")
    assert world.has(dragon, "affordable")                 # 40 <= 60
    assert not world.has(lot2, "affordable")               # 90 > 60


def test_reach_is_bounded_by_projections():
    """Claim 5: the role rule only ever writes on what a domain projected."""
    assert i0.confers_only_on_projected(i0.clean_trace(), "consider")


def test_fabricating_island_is_caught():
    """Claim 6: the antipattern is caught, and settles, and differs."""
    trace = i0.fabricating_trace()
    assert not trace.hot
    assert not i0.confers_only_on_projected(trace, "fabricating_consider")
    assert trace.signature != i0.clean_trace().signature


def test_run_all_expects_what_it_gets():
    """The probe's own verdict, so the module and the suite cannot disagree."""
    _clean, _fabricating, rows = i0.run_all()
    assert [(label, settled, bounded) for label, _t, settled, bounded in rows] \
        == [("clean", True, True), ("fabricating", True, False)]
