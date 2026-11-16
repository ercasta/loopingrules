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
        return self.chosen_of("candidate", "name")

    def chosen_of(self, component, field) -> set:
        """Every `component.field` among the entities carrying `chosen`."""
        return {self.world.get(entity, component, field)
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
    for operation in operations:
        for component in sorted(operation.used):
            schema.component(component)      # raises Gap -- refuse rather than guess
    return Model(name=name, schema=schema, operations=operations)


def install(loop, model) -> None:
    """Register a model's operations on a loop, model-qualifying their names."""
    for operation in model.operations:
        loop.rule(operation.fn, name="%s.%s" % (model.name, operation.name))
        # The compiler knows which components should wake the operation, so the
        # gate the engine would derive from source (which it cannot, for a
        # closure) is set here.
        if operation.gate:
            operation.fn._loopingrules_watches = operation.gate


def _answer(world, tools) -> int:
    """The tool seam (ADR-11 §3): between ticks, answer every unanswered
    `tool_request` by calling its tool and marking the outcome. Returns how many
    were answered, so the loop knows a tool may have written new entities and it
    should keep ticking."""
    answered = 0
    for entity, name in world.each("tool_request", "name",
                                   without=("tool_answered", "tool_failed")):
        tool = tools.get(name)
        if tool is None:
            world.set(entity, "tool_failed", "reason", "no tool named %r" % name)
            answered += 1
            continue
        args = world.get(entity, "tool_request", "args") or []
        try:
            tool(world, *args)
            world.mark(entity, "tool_answered")
        except Exception as exc:  # noqa: BLE001 -- a tool's failure is world data
            world.set(entity, "tool_failed", "reason",
                      "%s: %s" % (type(exc).__name__, exc))
        answered += 1
    return answered


def run(model, context_doc, *, budget: int = 200, tools=None) -> Run:
    tools = tools or {}
    loop = Loop(budget=budget)
    install(loop, model)
    seeded = _context.seed(loop.world, context_doc)
    applied = []
    hot = ()
    for _ in range(budget):
        step = loop.tick()
        answered = _answer(loop.world, tools)
        if step:
            applied.append(tuple(step))
        if not step and not answered:
            break
    else:
        hot = applied[-1] if applied else ()
    return Run(model=model, world=loop.world, applied=tuple(applied), hot=hot,
               seeded=tuple(seeded))


def run_files(model_path, context_path, *, budget: int = 200, tools=None) -> Run:
    return run(load(model_path),
               yaml.safe_load(Path(context_path).read_text(encoding="utf-8")),
               budget=budget, tools=tools)
