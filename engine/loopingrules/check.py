"""`lr check`: run a project to rest from its seed, and report (design D29).

- Starts fresh from the seed and writes nothing (no .lr/ appears).
- Runs autopilot until it rests. Tool calls run only if they match the user's trust
  rules, or the templates the project and its packs declare (with trust_declared).
- Fails on SHACL violations of the final state (sh:Violation; warnings and infos are
  only reported), and on findings: lr:out messages of type lr:Finding. The SHACL guard
  keeps operations from ever making the state invalid, so a model that checks
  something reports what it found as findings.

Exit codes: 0 passed, 1 failed (violations or findings), 2 incomplete (a tool call
was refused, the tick limit was reached, or the project did not load).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .engine import Engine, StepResult
from .package import manifests
from .project import Project
from .tools.shell import PendingCall, ShellTool
from .trust import TrustStore, compile_template
from .vocab import LR


@dataclass
class CheckResult:
    ticks: int = 0
    violations: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # other lr:out messages
    refused: list[str] = field(default_factory=list)
    incomplete: str | None = None

    @property
    def exit_code(self) -> int:
        if self.incomplete or self.refused:
            return 2
        return 1 if self.violations or self.findings else 0

    @property
    def status(self) -> str:
        return {0: "passed", 1: "failed", 2: "incomplete"}[self.exit_code]

    def as_dict(self) -> dict:
        return {"status": self.status, "exit": self.exit_code, "ticks": self.ticks,
                "violations": self.violations, "warnings": self.warnings, "findings": self.findings,
                "notes": self.notes, "refused": self.refused, "incomplete": self.incomplete}


def _severity(v: dict) -> str:
    sev = v.get("severity") or ""
    return "warning" if sev.endswith("Warning") else "info" if sev.endswith("Info") else "violation"


def check(project: str | Path, trust_declared: bool = False, max_ticks: int = 1000,
          trust_path: str | Path | None = None, shell: ShellTool | None = None,
          on_step=None) -> CheckResult:
    result = CheckResult()
    try:
        proj = Project.load(project, persist=False)
        trust = TrustStore(project, trust_path)
        declared = [compile_template(t) for m in manifests(project) for t in m.may_run] if trust_declared else []

        def approver(call: PendingCall) -> bool:
            if trust.match(call.command) or any(t.match(call.command.strip()) for t in declared):
                return True
            result.refused.append(call.command)
            return False

        eng = Engine(proj, shell=shell, approver=approver)
    except (ValueError, OSError) as e:
        result.incomplete = f"the project did not load: {e}"
        return result

    def step(r: StepResult) -> None:
        if r.status == "applied":
            result.ticks += 1
        if on_step:
            on_step(r)

    last = eng.run(max_ticks=max_ticks, on_step=step)
    if last.status == "applied":
        result.incomplete = f"autopilot did not come to rest within {max_ticks} ticks"

    for v in eng.sheet_violations():
        (result.violations if _severity(v) == "violation" else result.warnings).append(v)
    for m in eng.messages("out"):
        text = m.text or " ".join(t.n3(eng.sheet.namespace_manager) for t in m.types) or m.iri.n3()
        (result.findings if LR.Finding in m.types else result.notes).append(text)
    return result
