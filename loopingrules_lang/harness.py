"""The harness: load a model (YAML), install it, seed a context, run to a fixpoint.

A **model** is a name, a declared **schema** (`components.py`) and a set of
**operations** (`operations.py`). A **context** (`context.py`) is the anchor. The
harness ties them to the existing `Loop` and reports what happened -- the
trajectory (which operations applied, per tick), the settled world, and any
**gaps**.

::

    from loopingrules_lang import harness
    model = harness.load("market.yaml")
    run = harness.run_files("market.yaml", "session.yaml")
    print(run.settled, run.applied, run.chosen(), run.gaps())
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

from loopingrules.loop import Loop

from . import components as _components
from . import context as _context
from . import operations as _operations


@dataclasses.dataclass(frozen=True)
class Model:
    name: str
    schema: object
    operations: tuple


@dataclasses.dataclass
class Run:
    model: Model
    world: object
    applied: tuple          # one tuple of applied operation names per tick
    hot: tuple              # the operations still firing when the budget ran out
    seeded: tuple = ()

    @property
    def ticks(self) -> int:
        return len(self.applied)

    @property
    def settled(self) -> bool:
        return not self.hot

    def chosen(self) -> set:
        """The `candidate.name`s carrying `chosen` -- the answer, when a model uses
        that vocabulary."""
        return {self.world.get(entity, "candidate", "name")
                for entity, in self.world.each("chosen")}

    def gaps(self) -> list:
        """Every `unresolved.name` -- the terms with no definer."""
        return sorted(self.world.get(entity, "unresolved", "name")
                      for entity, in self.world.each("unresolved"))


def load(path) -> Model:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return parse(doc, name=Path(path).stem)


def parse(doc, *, name=None) -> Model:
    name = name or doc.get("model") or "model"
    schema = _components.parse(doc.get("components") or {})
    operations = tuple(_operations.parse(doc.get("operations") or ()))
    return Model(name=name, schema=schema, operations=operations)


def install(loop, model) -> None:
    """Register a model's operations on a loop, model-qualifying their names."""
    for operation in model.operations:
        loop.rule(operation.fn, name="%s.%s" % (model.name, operation.name))
        # The compiler knows what each operation reads, so the gate the engine
        # would derive from source (which it cannot, for a closure) is set here.
        if operation.gate is not None:
            operation.fn._loopingrules_watches = (operation.gate,)


def run(model, context_doc, *, budget: int = 200) -> Run:
    loop = Loop(budget=budget)
    install(loop, model)
    seeded = _context.seed(loop.world, context_doc)
    applied = []
    hot = ()
    for _ in range(budget):
        step = loop.tick()
        if not step:
            break
        applied.append(tuple(step))
    else:
        hot = applied[-1] if applied else ()
    return Run(model=model, world=loop.world, applied=tuple(applied), hot=hot,
               seeded=tuple(seeded))


def run_files(model_path, context_path, *, budget: int = 200) -> Run:
    return run(load(model_path),
               yaml.safe_load(Path(context_path).read_text(encoding="utf-8")),
               budget=budget)
