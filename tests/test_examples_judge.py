"""`examples.judge` -- a domain-oblivious rule. Deliberately imports
NOTHING from `examples.cards`: every test here spawns bare entities with
no domain meaning at all, to pin the claim `judge.py`'s own docstring
makes -- this rule knows only `Risk` and `RiskTolerance`, nothing about
what produced either."""

from examples import judge
from loopingrules.loop import Loop


def install(loop, max_level=0.5):
    loop.rule(judge.flag_too_risky, watches=(judge.Risk,))
    loop.world.spawn(judge.RiskTolerance(max_level))


def test_flags_an_entity_whose_risk_exceeds_the_tolerance():
    lp = Loop()
    w = lp.world
    install(lp, max_level=0.5)
    entity = w.spawn(judge.Risk(0.9, "over budget"))
    lp.tick()
    assert w.has(entity, judge.TooRisky)


def test_does_not_flag_an_entity_at_or_under_the_tolerance():
    lp = Loop()
    w = lp.world
    install(lp, max_level=0.5)
    entity = w.spawn(judge.Risk(0.5, "right at the line"))
    lp.tick()
    assert not w.has(entity, judge.TooRisky)


def test_unflags_once_the_same_entitys_risk_drops_back_down():
    lp = Loop()
    w = lp.world
    install(lp, max_level=0.5)
    entity = w.spawn(judge.Risk(0.9, "over budget"))
    lp.tick()
    assert w.has(entity, judge.TooRisky)
    w.replace(entity, judge.Risk(0.1, "no longer over budget"))
    lp.tick()
    assert not w.has(entity, judge.TooRisky)


def test_abstains_with_no_risk_tolerance_seeded():
    lp = Loop()
    w = lp.world
    lp.rule(judge.flag_too_risky, watches=(judge.Risk,))
    entity = w.spawn(judge.Risk(1.0, "maximally risky"))
    lp.tick()
    assert not w.has(entity, judge.TooRisky)


def test_the_module_imports_no_domain():
    """Not a behavioural test -- a documentation pin. `judge.py`'s own
    docstring claims it "imports nothing from `examples.cards`"; this
    checks the ACTUAL import statements (not prose that merely mentions
    `cards` by name, which the module's docstring does, to explain
    itself) never name a domain module."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(judge))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    assert not any(name.startswith("examples.cards") for name in names)
