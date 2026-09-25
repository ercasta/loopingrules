"""`examples.decide` -- a domain-oblivious rule. Deliberately imports
NOTHING from `examples.trip`: every test here spawns bare entities with
no domain meaning at all, to pin the claim `decide.py`'s own docstring
makes -- this rule knows only `Option` and `Score`, nothing about what
produced either."""

from examples import decide
from loopingrules.loop import Loop


def install(loop):
    loop.rule(decide.pick_winner)


def test_the_unique_top_scoring_option_wins():
    lp = Loop()
    w = lp.world
    install(lp)
    occasion = w.spawn()
    low = w.spawn(decide.Option(occasion.id), decide.Score(1.0))
    high = w.spawn(decide.Option(occasion.id), decide.Score(2.0))
    lp.tick()
    assert w.has(high, decide.Winner)
    assert not w.has(low, decide.Winner)


def test_an_exact_tie_crowns_nobody():
    lp = Loop()
    w = lp.world
    install(lp)
    occasion = w.spawn()
    a = w.spawn(decide.Option(occasion.id), decide.Score(1.0))
    b = w.spawn(decide.Option(occasion.id), decide.Score(1.0))
    lp.tick()
    assert not w.has(a, decide.Winner)
    assert not w.has(b, decide.Winner)


def test_a_newer_better_option_overtakes_the_former_winner():
    lp = Loop()
    w = lp.world
    install(lp)
    occasion = w.spawn()
    first = w.spawn(decide.Option(occasion.id), decide.Score(1.0))
    lp.tick()
    assert w.has(first, decide.Winner)

    second = w.spawn(decide.Option(occasion.id), decide.Score(2.0))
    lp.tick()
    assert w.has(second, decide.Winner)
    assert not w.has(first, decide.Winner)


def test_two_occasions_are_resolved_independently():
    lp = Loop()
    w = lp.world
    install(lp)
    a = w.spawn()
    b = w.spawn()
    a_winner = w.spawn(decide.Option(a.id), decide.Score(5.0))
    w.spawn(decide.Option(a.id), decide.Score(1.0))
    b_winner = w.spawn(decide.Option(b.id), decide.Score(1.0))
    w.spawn(decide.Option(b.id), decide.Score(0.5))
    lp.tick()
    assert w.has(a_winner, decide.Winner)
    assert w.has(b_winner, decide.Winner)


def test_the_module_imports_no_domain():
    """Not a behavioural test -- a documentation pin, the same check
    `tests/test_examples_judge.py::test_the_module_imports_no_domain`
    already runs for `judge.py`. Checks the ACTUAL import statements
    never name a domain module, not just that the docstring claims so."""
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
