"""`examples.decide` -- a domain-oblivious rule. Deliberately imports NOTHING
from `examples.trip`: every test here spawns bare entities with no domain
meaning at all, to pin the claim `decide.py`'s own docstring makes -- this
rule knows only `occasion`/`score`, nothing about what produced either."""

from __future__ import annotations

from examples import decide
from loopingrules.loop import Loop


def install(loop):
    loop.rule(decide.pick_winner)


def _option(world, occasion, score):
    entity = world.spawn()
    world.set(entity, "occasion", occasion)
    world.set(entity, "score", score)
    return entity


def test_the_unique_top_scoring_option_wins():
    lp = Loop()
    w = lp.world
    install(lp)
    occasion = w.spawn()
    low = _option(w, occasion.id, 1.0)
    high = _option(w, occasion.id, 2.0)
    lp.tick()
    assert w.has(high, "winner")
    assert not w.has(low, "winner")


def test_an_exact_tie_crowns_nobody():
    lp = Loop()
    w = lp.world
    install(lp)
    occasion = w.spawn()
    a = _option(w, occasion.id, 1.0)
    b = _option(w, occasion.id, 1.0)
    lp.tick()
    assert not w.has(a, "winner")
    assert not w.has(b, "winner")


def test_a_newer_better_option_overtakes_the_former_winner():
    lp = Loop()
    w = lp.world
    install(lp)
    occasion = w.spawn()
    first = _option(w, occasion.id, 1.0)
    lp.tick()
    assert w.has(first, "winner")

    second = _option(w, occasion.id, 2.0)
    lp.tick()
    assert w.has(second, "winner")
    assert not w.has(first, "winner")


def test_two_occasions_are_resolved_independently():
    lp = Loop()
    w = lp.world
    install(lp)
    a = w.spawn()
    b = w.spawn()
    a_winner = _option(w, a.id, 5.0)
    _option(w, a.id, 1.0)
    b_winner = _option(w, b.id, 1.0)
    _option(w, b.id, 0.5)
    lp.tick()
    assert w.has(a_winner, "winner")
    assert w.has(b_winner, "winner")


def test_the_module_imports_no_domain():
    """Checks the ACTUAL import statements never name a domain module."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(decide))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    assert not any(name.startswith("examples.trip") for name in names)
