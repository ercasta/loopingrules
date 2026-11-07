"""GP over the forge IR (`loopingrules_forge.evolve`): the pipeline closes.

The claims: the IR hash is content-addressed (the datum, not the source); the
GP operators stay well-formed; the fitness grades a half-right controller
above a do-nothing one and below the known-good one; and the search finds a
controller whose identity is its IR hash and which round-trips to a module
`analyze` sees. If the loop ever stopped closing, or identity drifted from the
datum, this fails.
"""

import loopingrules.analyze as analyze
from loopingrules import reflect
from loopingrules.loop import Loop

from loopingrules_forge import evolve, m0
from loopingrules_forge.evolve import A


def test_ir_hash_is_content_addressed_over_the_datum():
    body = evolve.controller_body(evolve._TARGET)
    assert evolve.ir_hash(body) == evolve.ir_hash(body)          # stable
    # a re-render under another module name hashes the SAME (it is the datum)
    _module, fn, h = evolve.load_controller(evolve._TARGET, name="one_name")
    assert h == evolve.ir_hash(body)
    assert fn._loopingrules_hash == h
    # a different structure, and a different operator version, move it
    other = evolve.controller_body(
        m0.cmp("in", m0.const("A"), evolve._writes()))
    assert evolve.ir_hash(other) != evolve.ir_hash(body)
    assert evolve.ir_hash(body, version="ir2") != evolve.ir_hash(body)


def test_the_emitted_controller_round_trips_through_analyze():
    _module, fn, _h = evolve.load_controller(evolve._TARGET)
    analysis = analyze.analyze(fn)                # no Opaque
    assert {k.__name__ for k in analysis.reads} == {"RuleCard"}
    assert {k.__name__ for k in analysis.writes} == {"RuleControl"}


def test_gp_operators_stay_well_formed():
    import random
    rng = random.Random(0)
    expr = evolve.random_expr(rng)
    for _ in range(50):
        expr = evolve.mutate(expr, rng)
        _m, fn, _h = evolve.load_controller(expr, name="op_check")
        analyze.analyze(fn)                        # must not raise
    a = evolve.random_expr(random.Random(1))
    b = evolve.random_expr(random.Random(2))
    analyze.analyze(evolve.load_controller(evolve.crossover(a, b,
                                                            random.Random(3)),
                                           name="xover")[1])


def test_the_fitness_grades_between_do_nothing_and_the_answer():
    baseline = evolve.fitness(m0.const(False))     # disables nothing -> hot
    half = evolve.fitness(m0.cmp("in", m0.const("A"), evolve._writes()))
    target = evolve.fitness(evolve._TARGET)
    assert baseline == 0.0
    assert 0.0 < half < target
    assert target == 1.0


def _always(w):
    w.spawn(A(0))                   # fires every tick, on any scenario


def test_the_gate_rejects_a_non_settling_rule():
    ok, why = evolve.gate(_always)   # always fires -> never settles anywhere
    assert ok is False
    assert "never settles" in why


def test_evolve_closes_the_loop_and_names_the_winner_by_datum():
    winner, history = evolve.evolve(seed=1)
    assert winner.score == 1.0
    assert history[-1] == 1.0
    assert winner.hash == evolve.ir_hash(evolve.controller_body(winner.condition))
    # deterministic
    assert evolve.evolve(seed=1)[0].hash == winner.hash


def test_a_generated_rule_is_identified_by_its_structure():
    """The integration point: a rule a generator stamped with an IR-datum hash
    is named by that hash through registration and reflection -- not by its
    source -- so a controller can key on it and it survives a re-render."""
    _module, fn, h = evolve.load_controller(evolve._TARGET, name="identity")
    loop = Loop()
    loop.rule(fn)
    assert fn._loopingrules_hash == h
    assert reflect.identity(fn) == h
    reflect.reify(loop)
    card = loop.world.the(reflect.RuleCard)
    assert card.hash == h
