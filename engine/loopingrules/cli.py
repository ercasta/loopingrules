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
        elif r.status == "stopped":
            console.print(f"[green]■ stopped[/] after {tick} ticks — "
                          f"[bold cyan]{r.application.operation.name}[/] won (score {r.application.total:g})")
        else:
            console.print(f"[green]■ done[/] after {tick} ticks — no applicable operations left")

    eng.run(max_ticks=args.max_ticks, on_step=on_step)

    violations = eng.sheet_violations()
    console.print(f"sheet: {len(eng.sheet)} triples, "
                  + ("[green]valid[/]" if not violations else f"[red]{len(violations)} violations[/]"))
    if args.save:
        console.print(f"snapshot written to {project.snapshot()}")
    return 0


def cmd_serve(args, console: Console) -> int:
    import uvicorn

    from .api import UI_DIST, create_app

    console.print(f"[bold magenta]LoopingRules[/] serving [cyan]{args.project}[/] on http://{args.host}:{args.port}")
    if not UI_DIST.exists():
        console.print("[yellow]ui/dist not found: API only (run `npm run build` in ui/, or use `npm run dev`)[/]")
    uvicorn.run(create_app(args.project), host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_export(args, console: Console) -> int:
    from .package import export_project

    state = Project.load(args.project).sheet if args.sheet == "state" else None
    out = export_project(args.project, args.out, sheet=args.sheet, state_sheet=state)
    console.print(f"[green]exported[/] {out}")
    return 0


def cmd_import(args, console: Console) -> int:
    from pathlib import Path

    from .package import PackageError, import_export

    try:
        manifest = import_export(Path(args.file).read_bytes(), args.dest)
    except PackageError as e:
        console.print(f"[red]refused:[/] {e}")
        return 1
    console.print(Panel.fit(
        f"[bold]{manifest.title}[/] {manifest.version}"
        + (f"\n{manifest.description}" if manifest.description else "")
        + (f"\nby {manifest.creator}" if manifest.creator else "")
        + (f" · {manifest.license}" if manifest.license else ""),
        title="imported", border_style="green"))
    if manifest.may_run:
        console.print("This model may ask to run:")
        for t in manifest.may_run:
            console.print(f"   [yellow]{t}[/]")
        if args.trust_declared:
            trust = TrustStore(args.dest)
            for t in manifest.may_run:
                trust.add(t)
            console.print(f"[green]trusted[/] these templates for {args.dest}")
        else:
            console.print("[dim]Each call will ask for approval. Use --trust-declared to trust them now.[/]")
    console.print(f"Run it with: lr serve {args.dest}")
    return 0


def cmd_add_layer(args, console: Console) -> int:
    from pathlib import Path

    from .package import PackageError, add_layer

    try:
        m = add_layer(Path(args.file).read_bytes(), args.project)
    except PackageError as e:
        console.print(f"[red]refused:[/] {e}")
        return 1
    console.print(f"[green]added layer[/] [bold]{m.title}[/] {m.version} on top of {m.extends}"
                  + (f"\n{m.description}" if m.description else ""))
    console.print(f"[dim]remove it by deleting {Path(args.project) / 'layers' / m.title}[/]")
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
    p_run.add_argument("--save", action="store_true", help="also write a snapshot (every change is journaled anyway)")
    p_serve = sub.add_parser("serve", help="serve the API and web UI")
    p_serve.add_argument("project")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_exp = sub.add_parser("export", help="write a shareable .lr.zip of a project's model and controllers")
    p_exp.add_argument("project")
    p_exp.add_argument("-o", "--out", help="output file (default: <title>-<version>.lr.zip next to the project)")
    p_exp.add_argument("--sheet", choices=["seed", "state", "none"], default="seed",
                       help="include the authored seed sheet (default), the current state, or no sheet")
    p_imp = sub.add_parser("import", help="create a project from a .lr.zip export")
    p_imp.add_argument("file")
    p_imp.add_argument("dest", help="new project folder")
    p_imp.add_argument("--trust-declared", action="store_true",
                       help="trust the command templates the package declares")
    p_layer = sub.add_parser("add-layer", help="add a controller pack (.lr.zip with lr:extends) to a project")
    p_layer.add_argument("file")
    p_layer.add_argument("project")
    for p in (p_apps, p_run):
        p.add_argument("--svg", help="also export the console output as an SVG")
    args = ap.parse_args(argv)

    svg = getattr(args, "svg", None)
    console = Console(record=bool(svg), width=110 if svg else None)
    code = {"apps": cmd_apps, "run": cmd_run, "serve": cmd_serve, "export": cmd_export, "import": cmd_import,
            "add-layer": cmd_add_layer}[args.cmd](args, console)
    if getattr(args, "svg", None):
        console.save_svg(args.svg, title="lr " + " ".join(argv if argv is not None else sys.argv[1:]))
    return code


if __name__ == "__main__":
    sys.exit(main())
