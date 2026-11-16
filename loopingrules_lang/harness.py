"""The harness: load models (YAML), install them, seed a context, run to a fixpoint.

A **model** is a name, a declared **schema** (`components.py`) and a set of
**operations** (`operations.py`). A **context** (`context.py`) is the anchor.
Several models compose on ONE loop -- each operation's name is model-qualified, and
their schemas are **unioned**, so a battery that reads `candidate` and a domain
that declares it meet through the shared shape.

::

    from loopingrules_lang import harness
    run = harness.run_files(["core.yaml", "scope.yaml", "rank.yaml"], "ctx.yaml")
    run.settled, run.applied, run.chosen_of("candidate", "label"), run.gaps()
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

from loopingrules import schema as _schema
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
    models: tuple
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

    @property
    def label(self) -> str:
        return ", ".join(model.name for model in self.models)

    def chosen_of(self, component, field) -> set:
        """Every `component.field` among the entities carrying `chosen`."""
        return {self.world.get(entity, component, field)
                for entity, in self.world.each("chosen")}

    def chosen(self) -> set:
        """The `candidate.name`s carrying `chosen` -- the answer, when a model uses
        that vocabulary."""
        return self.chosen_of("candidate", "name")

    def gaps(self) -> list:
        """Every `unresolved.name` -- the terms with no definer."""
        return sorted(self.world.get(entity, "unresolved", "name")
                      for entity, in self.world.each("unresolved"))


def load(path) -> Model:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return parse(doc, name=Path(path).stem)


def parse(doc, *, name=None) -> Model:
    name = name or doc.get("model") or "model"
    return Model(name=name,
                 schema=_components.parse(doc.get("components") or {}),
                 operations=tuple(_operations.parse(doc.get("operations") or ())))


def combine(models) -> "_schema.Schema":
    """The union of the models' schemas, and the DECLARED check: every component an
    operation names must be declared by SOME model. Two models may declare the same
    component only if identically (a shared shape)."""
    combined = _schema.Schema()
    for model in models:
        for name, component in model.schema.components.items():
            if name in combined.components:
                if combined.components[name] != component:
                    raise _schema.Gap(
                        "component %r is declared differently by %r and another "
                        "model" % (name, model.name))
            else:
                combined.components[name] = component
    for model in models:
        for operation in model.operations:
            for component in sorted(operation.used):
                combined.component(component)   # raises Gap -- refuse rather than guess
    return combined


def install(loop, model) -> None:
    """Register a model's operations on a loop, model-qualifying their names."""
    for operation in model.operations:
        loop.rule(operation.fn, name="%s.%s" % (model.name, operation.name))
        # The compiler knows which components should wake the operation, so the
        # gate the engine would derive from source (which it cannot, for a
        # closure) is set here.
        if operation.gate:
            operation.fn._loopingrules_watches = operation.gate


def _answer(world, tools, requests) -> int:
    """The tool seam (ADR-11 §3): between ticks, answer every unanswered request.
    A request is an entity carrying a capability's OWN component
    (``<capability>_request``); the answerer keys on that component (the same
    hub+own-vocabulary read the patterns doc describes), gathers its fields as
    keyword arguments, calls the tool, and marks the outcome. `requests` is the set
    of capabilities some model DECLARED -- so a request with no tool is a reported
    failure, not silence. Returns how many were answered, so the loop keeps ticking
    when a tool has written new entities."""
    answered = 0
    for capability in sorted(requests):
        component = capability + "_request"
        for entity, in world.each(component, without=("tool_done", "tool_failed")):
            tool = tools.get(capability)
            if tool is None:
                world.set(entity, "tool_failed", "capability", capability)
                world.set(entity, "tool_failed", "reason",
                          "no tool named %r" % capability)
                answered += 1
                continue
            kwargs = dict(world.components(entity).get(component, {}))
            try:
                tool(world, **kwargs)
                world.set(entity, "tool_done", "capability", capability)
            except Exception as exc:  # noqa: BLE001 -- a tool's failure is world data
                world.set(entity, "tool_failed", "capability", capability)
                world.set(entity, "tool_failed", "reason",
                          "%s: %s" % (type(exc).__name__, exc))
            answered += 1
    return answered


def run(models, context_doc, *, budget: int = 200, tools=None) -> Run:
    if isinstance(models, Model):
        models = (models,)
    models = tuple(models)
    combined = combine(models)      # the declared check, before anything runs
    requests = {name[:-len("_request")] for name in combined.components
                if name.endswith("_request")}
    tools = tools or {}
    loop = Loop(budget=budget)
    for model in models:
        install(loop, model)
    seeded = _context.seed(loop.world, context_doc)
    applied = []
    hot = ()
    for _ in range(budget):
        step = loop.tick()
        answered = _answer(loop.world, tools, requests)
        if step:
            applied.append(tuple(step))
        if not step and not answered:
            break
    else:
        hot = applied[-1] if applied else ()
    return Run(models=models, world=loop.world, applied=tuple(applied), hot=hot,
               seeded=tuple(seeded))


def run_files(model_paths, context_path, *, budget: int = 200, tools=None) -> Run:
    if isinstance(model_paths, (str, Path)):
        model_paths = [model_paths]
    return run([load(path) for path in model_paths],
               yaml.safe_load(Path(context_path).read_text(encoding="utf-8")),
               budget=budget, tools=tools)
