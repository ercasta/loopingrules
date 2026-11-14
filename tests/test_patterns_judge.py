"""`loopingrules_patterns.judge` -- a domain-oblivious rule. Deliberately
imports NOTHING from `examples.cards`: every test here spawns bare entities
with no domain meaning at all, to pin the claim `judge.py`'s own docstring
makes -- this rule knows only `risk_level`/`max_level`, nothing about what
produced either.

Under the attribute substrate (D8): a domain writes `risk_level`; the judge
reads it and flags `too_risky`.
"""

from __future__ import annotations

from loopingrules.loop import Loop
from loopingrules_patterns import judge


def install(loop, max_level=0.5):
    loop.rule(judge.flag_too_risky)
    judge.seed_tolerance(loop.world, max_level)


def _risky(world, level, reason="over budget"):
    entity = world.spawn()
    world.set(entity, "risk_level", level)
    world.set(entity, "risk_reason", reason)
    return entity


def test_flags_an_entity_whose_risk_exceeds_the_tolerance():
    lp = Loop()
    w = lp.world
    install(lp, max_level=0.5)
    entity = _risky(w, 0.9)
    lp.tick()
    assert w.has(entity, "too_risky")


def test_does_not_flag_an_entity_at_or_under_the_tolerance():
    lp = Loop()
    w = lp.world
    install(lp, max_level=0.5)
    entity = _risky(w, 0.5, "right at the line")
    lp.tick()
    assert not w.has(entity, "too_risky")


def test_unflags_once_the_same_entitys_risk_drops_back_down():
    lp = Loop()
    w = lp.world
    install(lp, max_level=0.5)
    entity = _risky(w, 0.9)
    lp.tick()
    assert w.has(entity, "too_risky")
    w.set(entity, "risk_level", 0.1)
    lp.tick()
    assert not w.has(entity, "too_risky")


def test_abstains_with_no_risk_tolerance_seeded():
    lp = Loop()
    w = lp.world
    lp.rule(judge.flag_too_risky)
    entity = _risky(w, 1.0, "maximally risky")
    lp.tick()
    assert not w.has(entity, "too_risky")


def test_the_module_imports_no_domain():
    """A documentation pin: `judge.py`'s actual import statements never name
    a domain module."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(judge))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    assert not any(name.startswith("examples") for name in names)


def test_the_judge_is_a_declared_pattern():
    """`docs/plan.md`, Phase 3: a pattern is not reusable until it exposes a
    DECLARED tunable surface. This one declares `max_level`."""
    from loopingrules_calibration import Knob, declared

    assert declared(judge.flag_too_risky) == (Knob("max_level", 0.0, 1.0, steps=5),)
