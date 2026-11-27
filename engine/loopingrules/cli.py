"""Headless CLI.

    lr apps  <project>                 list applications with validity and scores
    lr run   <project> [--yes] [--max-ticks N] [--save] [--svg out.svg]
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from rdflib import BNode

from .engine import Engine, StepResult
from .operations import Application
from .project import Project
from .tools.shell import PendingCall
from .trust import TrustStore


_bnode_labels: dict = {}


def _short(term, g) -> str:
    if isinstance(term, BNode):
        return _bnode_labels.setdefault(term, f"_:b{len(_bnode_labels) + 1}")
    return term.n3(g.namespace_manager)


def _bindings(app: Application, g) -> str:
    return "  ".join(f"[dim]?{k}[/]={_short(v, g)}" for k, v in sorted(app.bindings.items())
                     if k not in ("cmd", "line", "path", "text"))


def apps_table(eng: Engine) -> Table:
    t = Table(title="Applications", title_justify="left", expand=False)
    t.add_column("operation", style="bold cyan")
    t.add_column("bindings")
    t.add_column("Δ", justify="right")
    t.add_column("score", justify="right")
    t.add_column("valid")
    for a in sorted(eng.applications(), key=lambda a: -a.total):
        t.add_row(a.operation.name, _bindings(a, eng.sheet),
                  f"[red]-{len(a.deletes)}[/] [green]+{len(a.inserts)}[/]",
                  f"{a.total:g}" if a.valid else "–",
                  "[green]✓[/]" if a.valid else f"[red]✗ {len(a.violations)}[/]")
    return t


def cmd_apps(args, console: Console) -> int:
    eng = Engine(Project.load(args.project))
    console.print(apps_table(eng))
    return 0


def cmd_run(args, console: Console) -> int:
    project = Project.load(args.project)

    trust = TrustStore(args.project)

    def approver(call: PendingCall) -> bool:
        console.print(f"   [yellow]⚙ shell[/] [bold]{call.command}[/]")
        if rule := trust.match(call.command):
            console.print(f"     approved by trust rule [green]{rule.template}[/]")
            return True
        if args.yes:
            console.print("     approve? [y/n] [green]y[/] [dim](--yes)[/]")
            return True
        return Confirm.ask("     approve?", console=console)

    eng = Engine(project, approver=approver)
    console.print(Panel.fit(f"[bold]LoopingRules[/] autopilot · project [cyan]{args.project}[/]\n"
                            f"{len(eng.operations)} operations · {len(eng.controllers)} controllers · "
                            f"{len(eng.sheet)} triples", border_style="magenta"))
    tick = 0

    def on_step(r: StepResult) -> None:
        nonlocal tick
        if r.status == "applied":
            tick += 1
            a = r.application
            console.print(f"[dim]tick {tick:>3}[/]  [bold cyan]{a.operation.name:<18}[/] "
                          f"score [bold]{a.total:>4g}[/]  {_bindings(a, eng.sheet)}")
        elif r.status == "awaiting-approval":
            console.print("[yellow]⏸ paused: a tool call is awaiting approval[/]")
        else:
            console.print(f"[green]■ done[/] after {tick} ticks — no applicable operations left")

    eng.run(max_ticks=args.max_ticks, on_step=on_step)

    violations = eng.sheet_violations()
    console.print(f"sheet: {len(eng.sheet)} triples, "
                  + ("[green]valid[/]" if not violations else f"[red]{len(violations)} violations[/]"))
    if args.save:
        project.save()
        console.print(f"saved to {project.path}")
    return 0


def cmd_serve(args, console: Console) -> int:
    import uvicorn

    from .api import UI_DIST, create_app

    console.print(f"[bold magenta]LoopingRules[/] serving [cyan]{args.project}[/] on http://{args.host}:{args.port}")
    if not UI_DIST.exists():
        console.print("[yellow]ui/dist not found: API only (run `npm run build` in ui/, or use `npm run dev`)[/]")
    uvicorn.run(create_app(args.project), host=args.host, port=args.port, log_level="warning")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lr", description="LoopingRules semantic spreadsheet engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_apps = sub.add_parser("apps", help="list applications")
    p_apps.add_argument("project")
    p_run = sub.add_parser("run", help="run autopilot")
    p_run.add_argument("project")
    p_run.add_argument("--yes", action="store_true", help="approve every tool call")
    p_run.add_argument("--max-ticks", type=int, default=None)
    p_run.add_argument("--save", action="store_true", help="write the sheet back to the project")
    p_serve = sub.add_parser("serve", help="serve the API and web UI")
    p_serve.add_argument("project")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    for p in (p_apps, p_run):
        p.add_argument("--svg", help="also export the console output as an SVG")
    args = ap.parse_args(argv)

    svg = getattr(args, "svg", None)
    console = Console(record=bool(svg), width=110 if svg else None)
    code = {"apps": cmd_apps, "run": cmd_run, "serve": cmd_serve}[args.cmd](args, console)
    if getattr(args, "svg", None):
        console.save_svg(args.svg, title="lr " + " ".join(argv if argv is not None else sys.argv[1:]))
    return code


if __name__ == "__main__":
    sys.exit(main())
