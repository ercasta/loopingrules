"""GP over the forge IR: grow a CONTROLLER rule, gated and hashed (D5's
generator slot, locked decision 12 -- "one grammar, many generators").

`docs/plan-reflection.md` (D7) gave the substrate a way for a rule to change
the schedule (`reflect.RuleControl`); Phase 4 gave it a fitness
(`loopingrules_calibration.checks`); R1 proved the forge IR is totally
analyzable. What was missing is the thing this module is: a **generator** that
searches the IR for a controller, scored by the shared checks and disposed of
by a gate, with its identity a hash of the IR datum.

This is a WALKING SKELETON, on purpose -- the same posture as M0-M2. It proves
the PIPELINE (genome -> gate -> fitness -> freeze -> hash), not that GP scales
to real controllers. The genome is deliberately small: a controller PATTERN
(the skeleton of a rule that reads `RuleCard` and writes `RuleControl`) with a
HOLE for its condition, and GP searches the condition. "Select from a set of
controller patterns and grow the condition" is exactly D7's own framing.

## The pipeline

* **Genome** -- a boolean IR expression over the rule's own `RuleCard`: is the
  component a given name writes one of ours? (`in("A", card.writes)`, ...),
  combined with `and`/`or`/`not`. `ir_hash` names it by its datum.
* **Gate** -- `analyze` must see the emitted rule (no `Opaque`: it uses only
  declared components), and it must SETTLE (the behaviour gate M1 names).
* **Fitness** -- the Phase-4 checks: a scenario settles iff the controller
  disabled the runaway rules, and `checks.settles()` scores it. Graded over
  several armed sets, so a half-right condition gets partial credit.
* **Freeze** -- the winner is emitted to a real module, its IR hash and source
  recorded, and it round-trips (`analyze` sees what the IR said).

## The domain (self-contained, so nothing hides the mechanism)

Two runaway rules, `spin_a` writing `A` and `spin_b` writing `B`, each
incrementing forever -- alone, the world never settles. A controller must
disable BOTH by reading the rule cards and writing `RuleControl`. The correct
condition is `in("A", card.writes) or in("B", card.writes)`; a decoy like
`in("RuleControl", ...)` (disabling the controller itself) fails, because the
spinners never get stopped.

## What this does not settle

* **Scaling.** A hand-supplied pattern and a 6-atom condition are not
  "authoring a controller from nothing." Whether GP finds non-obvious
  controllers, or needs the pattern library D7 sketches, is the open question
  this probe does not answer -- it only shows the loop closes.
* **Const_as-knob.** Constants here are literals; the repo's stated division
  is structure-from-generation, values-from-search (freeze-before-tune), so a
  real run would emit a knob instead of a literal.
* **The full gates.** M1's six-gate suite (`m1.check`) is the real disposal;
  this probe uses the two that its tiny genome can trip (shape, behaviour).
"""

from __future__ import annotations

import dataclasses
import hashlib
import random

import loopingrules.analyze as analyze
from loopingrules import reflect
from loopingrules.loop import Loop
from loopingrules.reflect import RuleCard, RuleControl

from loopingrules_calibration import Scenario, checks, replay
from loopingrules_forge import m0


# =====================================================================
# 1. The IR-datum hash -- identity over the structure, not the source
# =====================================================================

def _canon(obj):
    """A canonical, order-stable, hashable form of an IR datum: classes by
    NAME (so a re-import is the same rule), tuples/lists/dicts by shape."""
    if isinstance(obj, tuple):
        return ("t", tuple(_canon(x) for x in obj))
    if isinstance(obj, list):
        return ("l", tuple(_canon(x) for x in obj))
    if isinstance(obj, dict):
        return ("d", tuple((k, _canon(v)) for k, v in sorted(obj.items())))
    if isinstance(obj, type):
        return ("c", obj.__name__)
    return ("v", obj)


def ir_hash(body, version: str = "ir1") -> str:
    """The content hash of an IR rule body -- the identity a `RuleControl`
    keys on. Unlike `reflect.rule_hash` (which hashes SOURCE, so a re-emit
    under a new module name changes it), this hashes the DATUM: the same rule
    is the same hash however it is rendered. `version` pins the operator
    language, so a change to what a tag MEANS moves every hash (the seam the
    freeze needs)."""
    material = repr((version, _canon(body)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


# =====================================================================
# 2. The genome: a controller pattern with a condition hole
# =====================================================================

def _writes():
    return m0.attr(m0.var("card"), "writes")


COMPONENT_NAMES = ("A", "B", "RuleControl", "Remembered", "RuleCard")


def atoms():
    """The boolean leaves GP may use: `in(<name>, card.writes)` for each
    candidate component name. Two are the answer; the rest are decoys."""
    return [m0.cmp("in", m0.const(name), _writes())
            for name in COMPONENT_NAMES]


def controller_body(condition):
    """The controller PATTERN: for every rule card, if `condition` holds,
    disable that rule. The `condition` is the genome."""
    return [
        m0.each_for([RuleCard], ("entity", "card"), [
            m0.if_(condition, [
                m0.replace(m0.var("entity"), RuleControl, {
                    "hash": m0.attr(m0.var("card"), "hash"),
                    "enabled": m0.const(False),
                }),
            ]),
        ]),
    ]


HEADER = "from loopingrules.reflect import RuleCard, RuleControl\n"


def emit_controller(condition, name="evolved_controller") -> str:
    return HEADER + "\n\n" + m0.emit_rule("controller",
                                          controller_body(condition))


def load_controller(condition, name="evolved_controller"):
    """Emit the genome to a real module and stamp its IR-datum hash on the
    function, so `Loop.rule`/`reflect` use the IR identity -- not the source
    hash -- for a generated rule. Returns `(module, function, hash)`."""
    body = controller_body(condition)
    module = m0.load_emitted(emit_controller(condition, name), name=name)
    fn = module.controller
    fn._loopingrules_hash = ir_hash(body)
    return module, fn, fn._loopingrules_hash


# -- GP operators over boolean IR expressions --------------------------

BOOL_TAGS = frozenset({"cmp", "and", "or", "not"})


def _bool_nodes(expr):
    if not isinstance(expr, tuple) or expr[0] not in BOOL_TAGS:
        return []
    found = [expr]
    for child in expr[1:]:
        if isinstance(child, tuple):
            found.extend(_bool_nodes(child))
    return found


def _replace_bool(expr, target_id, replacement):
    if not isinstance(expr, tuple) or expr[0] not in BOOL_TAGS:
        return expr
    if id(expr) == target_id:
        return replacement
    return tuple(_replace_bool(c, target_id, replacement)
                 if isinstance(c, tuple) else c for c in expr)


def random_expr(rng, pool=None) -> tuple:
    """A random boolean expression over the atoms."""
    pool = pool or atoms()
    expr = rng.choice(pool)
    while rng.random() < 0.4:
        other = rng.choice(pool)
        expr = rng.choice([m0.lor(expr, other), m0.land(expr, other),
                           m0.lnot(expr)])
    return expr


def mutate(expr, rng, pool=None) -> tuple:
    """Pick a SNP: replace a random boolean node with a random atom, or wrap
    it in `and`/`or`/`not` with another atom."""
    pool = pool or atoms()
    nodes = _bool_nodes(expr)
    if not nodes:
        return rng.choice(pool)
    target = rng.choice(nodes)
    if rng.random() < 0.5:
        return _replace_bool(expr, id(target), rng.choice(pool))
    wrapped = rng.choice([m0.lor(target, rng.choice(pool)),
                          m0.land(target, rng.choice(pool)),
                          m0.lnot(target)])
    return _replace_bool(expr, id(target), wrapped)


def crossover(a, b, rng) -> tuple:
    """Splice a random boolean subtree of `b` into `a` -- the standard
    subtree swap, restricted to boolean nodes so the result stays typed."""
    donor_nodes = _bool_nodes(b)
    a_nodes = _bool_nodes(a)
    if not donor_nodes or not a_nodes:
        return a
    return _replace_bool(a, id(rng.choice(a_nodes)), rng.choice(donor_nodes))


# =====================================================================
# 3. The domain, the gate, and the fitness
# =====================================================================

@dataclasses.dataclass(frozen=True)
class A:
    value: int = 0


@dataclasses.dataclass(frozen=True)
class B:
    value: int = 0


@dataclasses.dataclass(frozen=True)
class Limit:
    n: int = 2


def spin_a(w) -> None:
    for entity, a in w.each(A):
        w.replace(entity, A(a.value + 1))


def spin_b(w) -> None:
    for entity, b in w.each(B):
        w.replace(entity, B(b.value + 1))


SCENARIOS = (("A",), ("B",), ("A", "B"))       # which spinners are ARMED
SCORER = checks.total(checks.settles())


def build_install(controller_fn, armed):
    """An `install` for one scenario: arm the named spinners, register the
    controller first (so its `RuleControl` writes land before the next tick),
    and reify the cards the controller reads."""
    def install(loop):
        world = loop.world
        world.spawn(Limit(2))
        if "A" in armed:
            world.spawn(A(0))
        if "B" in armed:
            world.spawn(B(0))
        loop.rule(controller_fn, priority=10)
        loop.rule(spin_a)
        loop.rule(spin_b)
        reflect.reify(loop)
    return install


def gate(fn):
    """The disposal: `analyze` must see the rule (no `Opaque` -- a generated
    rule that uses an undeclared component is refused, never guessed at), and
    it must SETTLE on at least one armed scenario. Returns `(ok, why)`."""
    try:
        analyze.analyze(fn)
    except analyze.Opaque as exc:
        return False, "opaque: %s" % exc
    for armed in SCENARIOS:
        trace = replay(Scenario(), build_install(fn, armed))
        if not trace.hot:
            return True, "settles on %s" % (armed,)
    return False, "never settles"


def fitness(condition, cache=None):
    """The Phase-4 objective: mean `settles` over the armed scenarios -- a
    controller that stops only some runaway rules gets partial credit."""
    if cache is not None:
        # dedup identical genomes by IR-datum hash (GP re-generates a lot)
        key = ir_hash(controller_body(condition))
        if key in cache:
            return cache[key]
    _module, fn, _h = load_controller(condition)
    ok, why = gate(fn)
    if not ok:
        score = 0.0
    else:
        hits = [SCORER(replay(Scenario(), build_install(fn, armed)))
                for armed in SCENARIOS]
        score = sum(hits) / len(hits)
    if cache is not None:
        cache[ir_hash(controller_body(condition))] = score
    return score


# =====================================================================
# 4. The search loop, and the probe
# =====================================================================

@dataclasses.dataclass(frozen=True)
class Winner:
    condition: tuple
    score: float
    source: str
    hash: str


_TARGET = m0.lor(m0.cmp("in", m0.const("A"), _writes()),
                 m0.cmp("in", m0.const("B"), _writes()))


def evolve(population=24, generations=10, elite=4, seed=1):
    """A small (mu+lambda) GP: score, keep the elite, refill with mutation and
    crossover. Deterministic given `seed`. Returns `(winner, history)`."""
    rng = random.Random(seed)
    cache = {}
    pop = [random_expr(rng) for _ in range(population)]
    pop[0] = m0.cmp("in", m0.const("RuleControl"), _writes())   # a decoy start
    history = []
    best = None
    for _gen in range(generations):
        scored = sorted(((fitness(e, cache), i, e) for i, e in enumerate(pop)),
                        key=lambda row: (-row[0], row[1]))
        top_score, _i, top = scored[0]
        history.append(top_score)
        if best is None or top_score > best.score:
            body = controller_body(top)
            best = Winner(top, top_score, emit_controller(top), ir_hash(body))
        if top_score >= 1.0:
            break
        survivors = [e for _s, _i, e in scored[:elite]]
        children = list(survivors)
        while len(children) < population:
            if rng.random() < 0.5:
                children.append(mutate(rng.choice(survivors), rng))
            else:
                children.append(crossover(rng.choice(survivors),
                                          rng.choice(survivors), rng))
        pop = children
    return best, tuple(history)


def report(seed=1):
    baseline = fitness(m0.const(False))            # disables nothing
    winner, history = evolve(seed=seed)
    target_score = fitness(_TARGET)                # the known-good condition
    return {
        "baseline": baseline,
        "target": target_score,
        "winner": winner,
        "history": history,
        "ok": winner.score >= target_score and baseline < target_score,
    }


def main():
    r = report()
    print("== Evolve: GP over the forge IR ==")
    print("  baseline (disables nothing): %.3f" % r["baseline"])
    print("  known-good condition:        %.3f" % r["target"])
    print("  evolved: %.3f  hash %s" % (r["winner"].score, r["winner"].hash))
    print("  fitness per generation: %s"
          % ", ".join("%.2f" % s for s in r["history"]))
    print("  winner condition: %s"
          % m0.e_src(r["winner"].condition))
    ok = r["ok"]
    print("  [%s] GP found a controller at least as good as the known one"
          % ("ok" if ok else "XX"))
    print("  ALL AS EXPECTED:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
