"""`examples.shopping` -- the second real domain fed to the judge's
`risk_level`/`max_level`/`flag_too_risky`."""

from __future__ import annotations

import pytest

from examples import shopping
from loopingrules.engine import said
from loopingrules.loop import Loop


def say(loop, line):
    w = loop.world
    said(w, "user", line)
    loop.run()
    out = [w.get(entity, "text") for entity, _ in w.each("reply")]
    for entity, _ in w.each("reply"):
        w.destroy(entity)
    return out


def item(w, name):
    for entity, _tag, item_name in w.each("item", "name"):
        if item_name == name:
            return entity
    raise AssertionError("no such item in this world: %r" % name)


def _tolerance(w):
    row = w.first("max_level")
    return None if row is None else row[1]


@pytest.fixture
def loop():
    lp = Loop()
    shopping.install(lp, tolerance=0.6)
    return lp


# -- install / seeding --------------------------------------------------

def test_install_seeds_catalog_with_zero_stock(loop):
    w = loop.world
    assert len(w.each("item")) == len(shopping.DEFAULT_ITEMS)
    assert all(w.get(entity, "stock") == 0 for entity, _ in w.each("item"))


def test_install_seeds_the_judges_risk_tolerance(loop):
    assert _tolerance(loop.world) == 0.6


def test_install_does_not_re_seed_tolerance_on_restore():
    lp = Loop()
    w = lp.world
    w.set(w.spawn(), "max_level", 0.1)
    shopping.install(lp, tolerance=0.9)
    assert _tolerance(w) == 0.1


# -- hearing ------------------------------------------------------------

def test_stock_sets_the_quantity(loop):
    w = loop.world
    say(loop, "stock milk 4")
    assert w.get(item(w, "milk"), "stock") == 4


def test_stock_rejects_an_unknown_item(loop):
    assert say(loop, "stock kombucha 4") == ["! unknown item 'kombucha'"]


def test_stock_rejects_a_non_integer_quantity(loop):
    assert say(loop, "stock milk lots") == ["! not a quantity: 'lots'"]


def test_needby_sets_the_deadline(loop):
    w = loop.world
    say(loop, "needby milk 2")
    assert w.get(item(w, "milk"), "needed") == 2


def test_a_second_needby_replaces_the_first_rather_than_adding_a_rival(loop):
    w = loop.world
    say(loop, "needby milk 5")
    say(loop, "needby milk 1")
    assert w.get(item(w, "milk"), "needed") == 1


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


# -- the actual experiment: does the risk shape hold for a deadline? -----

def test_an_item_due_today_is_flagged_urgent(loop):
    w = loop.world
    say(loop, "needby milk 0")
    assert w.has(item(w, "milk"), "too_risky")
    assert w.has(item(w, "milk"), "on_list")


def test_an_item_with_a_distant_deadline_is_not_flagged(loop):
    w = loop.world
    say(loop, "needby milk 7")
    assert not w.has(item(w, "milk"), "too_risky")
    assert not w.has(item(w, "milk"), "on_list")


def test_an_item_with_no_deadline_gets_no_risk_at_all(loop):
    w = loop.world
    assert not w.has(item(w, "milk"), "risk_level")


def test_urgency_rises_as_the_deadline_gets_closer(loop):
    w = loop.world
    say(loop, "needby milk 6")
    far = w.get(item(w, "milk"), "risk_level")
    say(loop, "needby milk 1")
    near = w.get(item(w, "milk"), "risk_level")
    assert near > far


def test_falling_off_the_list_once_the_deadline_moves_back_out(loop):
    w = loop.world
    say(loop, "needby milk 0")
    assert w.has(item(w, "milk"), "on_list")
    say(loop, "needby milk 7")
    assert not w.has(item(w, "milk"), "on_list")


def test_several_urgent_items_can_still_be_ranked_by_the_same_risk_level(loop):
    w = loop.world
    say(loop, "needby milk 0")
    say(loop, "needby eggs 1")
    say(loop, "needby bread 2")
    flagged = [(w.get(item(w, name), "risk_level"), name)
               for name in ("milk", "eggs", "bread")]
    for _level, name in flagged:
        assert w.has(item(w, name), "too_risky"), name
    ranked_names = [name for _level, name in sorted(flagged, reverse=True)]
    assert ranked_names == ["milk", "eggs", "bread"]


def test_shopping_imports_the_judges_vocabulary_rather_than_reinventing_it():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(shopping))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    assert "loopingrules_patterns.judge" in names
