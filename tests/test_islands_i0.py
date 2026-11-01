"""i0's claims, as permanent verification points (`docs/plan-islands.md`).

The islands/bridges shape must WORK (settle, reuse, compose) and its
antipattern must be CATCHABLE -- a check that cannot fail is not a check.
If the shape stops settling, stops reusing, or the fabricating mutant stops
being caught, these fail -- which is the point.
"""

from loopingrules import Loop
from loopingrules_calibration import knobs, lint

from loopingrules_islands import funds, i0, items


def _find(world, kind, match):
    for entity, component in world.each(kind):
        if match(component):
            return entity
    raise AssertionError("no %s matched" % kind.__name__)


def test_shape_settles_and_replays_to_one_signature():
    """Claim 1: the shape reaches a fixpoint, and replay is deterministic."""
    first = i0.clean_trace()
    second = i0.clean_trace()
    assert not first.hot
    assert first.ticks == second.ticks
    assert first.signature == second.signature


def test_island_decision_is_declared_and_lint_clean():
    """Claim 2: each island owns its decision, declares it with `@tunable`,
    and hard-codes no threshold -- `knobs(loop)` collects the surfaces and
    `lint` finds nothing to report."""
    loop = Loop()
    i0.install(loop)
    declared = {(knob.component, knob.field) for knob in knobs(loop)}
    assert (items.ItemsPolicy, "min_worth") in declared
    assert (funds.Reserve, "amount") in declared
    report = lint(loop)
    assert report.findings == ()
    assert report.unlintable == ()


def test_two_domains_reuse_the_same_island():
    """Claim 3: `cards` and `lots` land on the SAME `items` island, zero
    island rules rewritten -- and the island's OWN rule (`total_worth`)
    sees both, without ever hearing of a card or a lot."""
    world = i0.clean_trace().world
    dragon = _find(world, i0.Card, lambda card: card.name == "dragon")
    goblin = _find(world, i0.Card, lambda card: card.name == "goblin")
    lot1 = _find(world, i0.Lot, lambda lot: lot.ref == "lot-1")
    assert world.has(dragon, items.Item)
    assert world.has(lot1, items.Item)
    assert not world.has(goblin, items.Item)        # below the island's policy
    inventory = world.the(items.Inventory)
    assert (inventory.total, inventory.count) == (160.0, 3)


def test_conjunction_reads_across_two_islands():
    """Claim 4: a composer reads `items.Item` and `funds.Spendable` and
    concludes something neither island can -- an `Affordable` role that
    exists in neither island's vocabulary."""
    world = i0.clean_trace().world
    assert world.the(funds.Spendable).amount == 60.0        # 70 - 10
    dragon = _find(world, i0.Card, lambda card: card.name == "dragon")
    lot2 = _find(world, i0.Lot, lambda lot: lot.ref == "lot-2")
    assert world.has(dragon, i0.Affordable)                 # 40 <= 60
    assert not world.has(lot2, i0.Affordable)               # 90 > 60


def test_reach_is_bounded_by_projections():
    """Claim 5: the role rule only ever writes on what a domain projected."""
    assert i0.confers_only_on_projected(i0.clean_trace(), "consider")


def test_fabricating_island_is_caught():
    """Claim 6: the antipattern -- an island fabricating its own candidates
    instead of domains projecting them -- is caught, and settles (so the
    catch is REACH, not a failure to settle), and differing."""
    trace = i0.fabricating_trace()
    assert not trace.hot
    assert not i0.confers_only_on_projected(trace, "fabricating_consider")
    assert trace.signature != i0.clean_trace().signature


def test_run_all_expects_what_it_gets():
    """The probe's own verdict, so `python -m loopingrules_islands.i0` and
    the suite cannot disagree."""
    _clean, _fabricating, rows = i0.run_all()
    assert [(label, settled, bounded) for label, _t, settled, bounded in rows] \
        == [("clean", True, True), ("fabricating", True, False)]
