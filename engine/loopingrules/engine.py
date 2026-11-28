"""The engine: enumerate, validate, score, apply; tool phase between ticks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal as Lit

from rdflib import Graph

from .controllers import Controller, load_controllers
from .operations import Application, Operation, enumerate_applications, load_operations
from .project import Project
from .store import apply_delta, copy_graph, prologue
from .tools.shell import PendingCall, ShellTool
from .validation import validate, violation_key
from .vocab import BUILTIN_SHAPES

# approver(call) -> True (run), False (reject), None (leave pending for later)
Approver = Callable[[PendingCall], "bool | None"]


@dataclass
class StepResult:
    status: Lit["applied", "awaiting-approval", "done"]
    application: Application | None = None


class Engine:
    def __init__(self, project: Project, shell: ShellTool | None = None, approver: Approver | None = None):
        self.project = project
        self.shell = shell or ShellTool()
        self.approver = approver
        self.reload_model()

    # --- model -----------------------------------------------------------
    def reload_model(self) -> None:
        self.operations: list[Operation] = load_operations(self.project.model)
        self.controllers: list[Controller] = load_controllers(self.project.controllers)
        for name, g in self.project.layers:
            self.controllers += load_controllers(g, layer=name)
        self.shapes = Graph()
        self.shapes += self.project.model
        self.shapes.parse(data=BUILTIN_SHAPES, format="turtle")

    @property
    def sheet(self) -> Graph:
        return self.project.sheet

    def sheet_violations(self) -> list[dict]:
        return validate(self.sheet, self.shapes)

    # --- applications ----------------------------------------------------
    def applications(self) -> list[Application]:
        """All applications, each validated and scored against its resulting state.

        An application is invalid if its resulting state has violations that the
        current state does not have (so an already-invalid sheet, see D13, does not
        block everything).
        """
        apps = enumerate_applications(self.sheet, self.operations, self.project.model)
        if not apps:
            return apps
        baseline = {violation_key(v) for v in self.sheet_violations()}
        prefixes = prologue(self.project.controllers, *(g for _, g in self.project.layers),
                            self.project.model, self.sheet)
        active = [c for c in self.controllers if c.active]
        for app in apps:
            state = self.resulting_state(app)
            new = [v for v in validate(state, self.shapes) if violation_key(v) not in baseline]
            app.valid = not new
            app.violations = new
            if app.valid:
                # Each entry is the controller's weighted contribution (D23).
                app.scores = {c.name: c.weight * c.score(state, prefixes) for c in active}
        return apps

    def resulting_state(self, app: Application) -> Graph:
        state = copy_graph(self.sheet)
        apply_delta(state, app.deletes, app.inserts)
        return state

    def apply(self, app: Application, run_tools: bool = True, kind: str = "tick") -> None:
        apply_delta(self.sheet, app.deletes, app.inserts)
        nm = self.sheet.namespace_manager
        self.project.record(app.inserts, app.deletes, kind=kind, label=app.operation.name,
                            bindings=" ".join(f"?{k}={v.n3(nm)}" for k, v in sorted(app.bindings.items())))
        if run_tools:
            self.tool_phase()

    # --- journaled changes outside operations -----------------------------
    def _journaled(self, fn: Callable[[], None], **headers) -> None:
        before = set(self.sheet)
        fn()
        after = set(self.sheet)
        self.project.record(after - before, before - after, **headers)

    def edit(self, add=(), remove=()) -> None:
        """A manual change to the sheet, journaled as one transaction."""
        def do():
            for t in remove:
                self.sheet.remove(t)
            for t in add:
                self.sheet.add(t)
        self._journaled(do, kind="edit")

    def undo(self):
        """Revert the latest journaled change; returns its transaction or None."""
        return self.project.undo()

    # --- tools -----------------------------------------------------------
    def pending_calls(self) -> list[PendingCall]:
        return self.shell.pending(self.sheet)

    def tool_phase(self) -> None:
        """Between ticks: run or reject pending calls the approver decides on."""
        if self.approver is None:
            return
        for call in self.pending_calls():
            decision = self.approver(call)
            if decision is True:
                self._journaled(lambda: self.shell.run(self.sheet, call), kind="tool", label=call.command)
            elif decision is False:
                self._journaled(lambda: self.shell.reject(self.sheet, call), kind="tool-rejected", label=call.command)

    def resolve(self, call_id: str, approve: bool) -> None:
        for call in self.pending_calls():
            if call.iri.n3() == call_id:
                action = self.shell.run if approve else self.shell.reject
                self._journaled(lambda: action(self.sheet, call),
                                kind="tool" if approve else "tool-rejected", label=call.command)
                return
        raise KeyError(f"No pending call {call_id}")

    # --- autopilot -------------------------------------------------------
    def step(self) -> StepResult:
        """One autopilot tick. The tool phase for the previous tick runs first."""
        self.tool_phase()
        if self.pending_calls():
            return StepResult("awaiting-approval")
        valid = [a for a in self.applications() if a.valid]
        if not valid:
            return StepResult("done")
        best = max(valid, key=lambda a: a.total)  # ties: first found
        self.apply(best, run_tools=False)
        return StepResult("applied", best)

    def run(self, max_ticks: int | None = None, on_step: Callable[[StepResult], None] | None = None) -> StepResult:
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            result = self.step()
            if on_step:
                on_step(result)
            if result.status != "applied":
                return result
            ticks += 1
        return StepResult("applied")
