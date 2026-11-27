"""Baseline benchmark: autopilot on folder-scan with a stub shell.

    .venv/Scripts/python benchmarks/bench_folder_scan.py [sizes...]   (default: 5 10 20)

Reports, per folder size: ticks, final triples, total time, time per tick, and
the share of time spent in SPARQL parsing/translation, SHACL validation and
graph copying. Nothing touches the disk or the real shell.
"""

import shutil
import sys
import tempfile
import time
from pathlib import Path

import rdflib.plugins.sparql.algebra as algebra
import rdflib.plugins.sparql.parser as parser
import rdflib.plugins.sparql.processor as processor

import loopingrules.engine as engine_mod
from loopingrules.engine import Engine
from loopingrules.project import Project
from loopingrules.tools.shell import ShellTool

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "folder-scan"
spent: dict[str, float] = {}


def timed(name, fn):
    def wrapper(*a, **k):
        s = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            spent[name] = spent.get(name, 0.0) + time.perf_counter() - s
    return wrapper


def instrument():
    processor.parseQuery = timed("sparql parse", parser.parseQuery)
    processor.translateQuery = timed("sparql translate", algebra.translateQuery)
    engine_mod.validate = timed("shacl validate", engine_mod.validate)
    engine_mod.copy_graph = timed("graph copy", engine_mod.copy_graph)


def stub_shell(n: int) -> ShellTool:
    files = [f"f{i}.txt" if i % 2 else f"f{i}.md" for i in range(n)]

    def run(cmd):
        if cmd.startswith("ls"):
            return 0, "".join(f + "\n" for f in files), ""
        return 0, "3\n", ""
    return ShellTool(executor=run)


def bench(n: int) -> None:
    spent.clear()
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(EXAMPLE, Path(d) / "p", ignore=shutil.ignore_patterns(".lr"))
        proj = Project.load(Path(d) / "p", persist=False)
        eng = Engine(proj, shell=stub_shell(n), approver=lambda c: True)
        ticks = []
        s = time.perf_counter()
        eng.run(max_ticks=1000, on_step=lambda r: ticks.append(r))
        total = time.perf_counter() - s
    shares = "  ".join(f"{k} {v / total:4.0%}" for k, v in sorted(spent.items()))
    print(f"files={n:3d} ticks={len(ticks):3d} triples={len(proj.sheet):5d} "
          f"total={total:7.1f}s per-tick={total / max(1, len(ticks)) * 1000:6.0f}ms   {shares}")


if __name__ == "__main__":
    instrument()
    for size in [int(x) for x in sys.argv[1:]] or [5, 10, 20]:
        bench(size)
