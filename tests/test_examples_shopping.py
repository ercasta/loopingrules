"""`examples.shopping` -- the second real domain fed to `examples.judge`'s
`Risk`/`RiskTolerance`/`flag_too_risky`, and the tests that actually check
the claim its own module docstring makes ("What this is testing" /
"What it settled, once tried"). Convention mirrors `tests/test_examples_
cards.py`: a `say(loop, line)` helper spawns a `Said`, runs the loop to a
settle, and hands back every `Reply` text produced."""

import pytest

from examples import judge, shopping
from loopingrules.loop import Loop
from loopingrules.world import Reply, Said


def say(loop, line):
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
            if w.destroy(entity) or True]


def item(w, name):
    """The `Item` entity named `name` -- a test-local lookup, not
    `shopping._find_item`, so these tests exercise public behaviour
    only."""
    for entity, it in w.all(shopping.Item):
        if it.name == name:
            return entity
    raise AssertionError("no such item in this world: %r" % name)


@pytest.fixture
def loop():
    lp = Loop()
    shopping.install(lp, tolerance=0.6)
    return lp


# -- install / seeding ----------------------------------------------------

def test_install_seeds_catalog_with_zero_stock(loop):
    w = loop.world
    assert len(w.all(shopping.Item)) == len(shopping.DEFAULT_ITEMS)
    for _entity, stock in w.all(shopping.Stock):
        assert stock == shopping.Stock(0)


def test_install_seeds_the_judges_risk_tolerance(loop):
    w = loop.world
    assert w.the(judge.RiskTolerance) == judge.RiskTolerance(0.6)


def test_install_does_not_re_seed_tolerance_on_restore():
    lp = Loop()
    w = lp.world
    w.spawn(judge.RiskTolerance(0.1))
    shopping.install(lp, tolerance=0.9)
    assert w.the(judge.RiskTolerance) == judge.RiskTolerance(0.1)


# -- hearing ----------------------------------------------------------------

def test_stock_sets_the_quantity(loop):
    w = loop.world
    say(loop, "stock milk 4")
    assert w.get(item(w, "milk"), shopping.Stock) == shopping.Stock(4)


def test_stock_rejects_an_unknown_item(loop):
    assert say(loop, "stock kombucha 4") == ["! unknown item 'kombucha'"]


def test_stock_rejects_a_non_integer_quantity(loop):
    assert say(loop, "stock milk lots") == ["! not a quantity: 'lots'"]


def test_needby_sets_the_deadline(loop):
    w = loop.world
    say(loop, "needby milk 2")
    assert w.get(item(w, "milk"), shopping.NeededBy) == shopping.NeededBy(2)


def test_a_second_needby_replaces_the_first_rather_than_adding_a_rival(loop):
    w = loop.world
    say(loop, "needby milk 5")
    say(loop, "needby milk 1")
    assert w.get_all(item(w, "milk"), shopping.NeededBy) == [shopping.NeededBy(1)]


def test_status_reports_stock_deadline_and_list_membership(loop):
    say(loop, "stock milk 0")
    say(loop, "needby milk 0")
    [line] = say(loop, "status")
    assert "milk: 0 in stock" in line
    assert "needed in 0 day(s)" in line
    assert "on the list" in line


def test_status_omits_deadline_for_an_item_with_none_set(loop):
    [line] = say(loop, "status")
    assert "milk: 0 in stock" in line
    assert "needed in" not in line.split("milk: 0 in stock")[1].split(";")[0]


# -- the actual experiment: does Risk hold for a deadline, not a spend? -----

def test_an_item_due_today_is_flagged_urgent(loop):
    w = loop.world
    say(loop, "needby milk 0")
    assert w.has(item(w, "milk"), judge.TooRisky)
    assert w.has(item(w, "milk"), shopping.OnList)


def test_an_item_with_a_distant_deadline_is_not_flagged(loop):
    w = loop.world
    say(loop, "needby milk 7")
    assert not w.has(item(w, "milk"), judge.TooRisky)
    assert not w.has(item(w, "milk"), shopping.OnList)


def test_an_item_with_no_deadline_gets_no_risk_at_all(loop):
    w = loop.world
    assert w.get(item(w, "milk"), judge.Risk) is None


def test_urgency_rises_as_the_deadline_gets_closer(loop):
    w = loop.world
    say(loop, "needby milk 6")
    far = w.get(item(w, "milk"), judge.Risk).level
    say(loop, "needby milk 1")
    near = w.get(item(w, "milk"), judge.Risk).level
    assert near > far


def test_falling_off_the_list_once_the_deadline_moves_back_out(loop):
    w = loop.world
    say(loop, "needby milk 0")
    assert w.has(item(w, "milk"), shopping.OnList)
    say(loop, "needby milk 7")
    assert not w.has(item(w, "milk"), shopping.OnList)


def test_several_urgent_items_can_still_be_ranked_by_the_same_risk_level_the_judge_thresholds(loop):
    """The finding named in the module docstring's "What it settled":
    `flag_too_risky` only ever exposes a boolean, but `Risk.level` itself
    survives thresholding, so a caller that wants to know WHICH flagged
    item is most pressing already can, by reading the same fact the judge
    compared -- no ranking judge needed on top of the threshold one."""
    w = loop.world
    say(loop, "needby milk 0")
    say(loop, "needby eggs 1")
    say(loop, "needby bread 2")
    flagged = [(w.get(item(w, name), judge.Risk).level, name)
               for name in ("milk", "eggs", "bread")]
    for _level, name in flagged:
        assert w.has(item(w, name), judge.TooRisky), name
    ranked_names = [name for _level, name in sorted(flagged, reverse=True)]
    assert ranked_names == ["milk", "eggs", "bread"]


def test_shopping_imports_the_judges_vocabulary_rather_than_reinventing_it():
    """Not a behavioural test -- a documentation pin, the mirror image of
    `tests/test_examples_judge.py::test_the_module_imports_no_domain`:
    checks the ACTUAL import statements name `examples.judge`, so the
    reuse claimed in the module docstring is real, not merely a
    same-shaped component defined twice."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(shopping))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    assert "examples.judge" in names
