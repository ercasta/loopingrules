"""How the cost of a tick grows with the sheet (N) and the number of operations (O).

    .venv/Scripts/python benchmarks/bench_scaling.py [folder|folder-delta|junk|ops ...]   (default: all)

- folder: folder-scan with N files (real work). Times a window of ticks after the listing
  has put all N files in the sheet, so each size is measured at that size.
- folder-delta: the same, with controllers that read only the change (D20).
- junk:   a tiny counter model, plus N triples nothing reads. Costs that grow here are
          paid for data that doesn't matter.
- ops:    the same counter, plus O operations that never apply (each with its own
          predicate and a FILTER NOT EXISTS). Costs that grow here are paid for
          operations that can't match.

Per size: ms per tick, split by phase (exclusive: nested time is counted once), and at
the end the growth exponent of each phase: the slope of log(time) against log(size).
1 is linear, 2 quadratic, 0 flat.
"""

from __future__ import annotations

import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

import loopingrules.controllers as controllers
import loopingrules.mirror as mirror
import loopingrules.operations as operations
import loopingrules.validation as validation
from loopingrules.engine import Engine
from loopingrules.project import Project
from loopingrules.tools.shell import ShellTool

FOLDER = Path(__file__).resolve().parents[2] / "examples" / "folder-scan"
# the same controllers, rewritten to read only the change (D20)
DELTA_CONTROLLERS = Path(__file__).resolve().parent / "folder_scan_delta_controllers.ttl"

# --- exclusive phase timers --------------------------------------------------------

spent: dict[str, float] = {}
_stack: list[list] = []  # [name, start, time spent in nested timed calls]


def timed(name, fn):
    def wrapper(*a, **k):
        _stack.append([name, time.perf_counter(), 0.0])
        try:
            return fn(*a, **k)
        finally:
            nm, start, nested = _stack.pop()
            total = time.perf_counter() - start
            spent[nm] = spent.get(nm, 0.0) + total - nested
            if _stack:
                _stack[-1][2] += total
    return wrapper


def instrument() -> None:
    mirror.Mirror.solutions = timed("match", mirror.Mirror.solutions)
    mirror.Mirror.holds = timed("match", mirror.Mirror.holds)
    mirror.Mirror.step_solutions = timed("steps", mirror.Mirror.step_solutions)
    mirror.Mirror.sync = timed("sync", mirror.Mirror.sync)
    mirror.RdflibMatcher.solutions = timed("match", mirror.RdflibMatcher.solutions)
    mirror.RdflibMatcher.holds = timed("match", mirror.RdflibMatcher.holds)
    mirror.RdflibMatcher.step_solutions = timed("steps", mirror.RdflibMatcher.step_solutions)
    controllers.Controller.score = timed("score", controllers.Controller.score)
    validation.validate = timed("shacl", validation.validate)
    validation.affected_nodes = timed("shacl", validation.affected_nodes)
    Engine.step = timed("other", Engine.step)  # whatever the phases above don't cover


PHASES = ["match", "steps", "score", "shacl", "sync", "other"]


def measure(eng: Engine, ticks: int) -> tuple[float, dict, int]:
    """ms per tick over `ticks` ticks (or until the run stops), per phase."""
    spent.clear()
    t, n = time.perf_counter(), 0
    for _ in range(ticks):
        if eng.step().status != "applied":
            break
        n += 1
    total = time.perf_counter() - t
    n = max(n, 1)
    return 1000 * total / n, {p: 1000 * spent.get(p, 0.0) / n for p in PHASES}, n


# --- the three workloads -----------------------------------------------------------

def folder(n: int, delta: bool = False) -> Engine:
    files = [f"f{i}.txt" if i % 2 else f"f{i}.md" for i in range(n)]

    def run(cmd):
        if cmd.startswith("ls"):
            return 0, "".join(f + "\n" for f in files), ""
        return 0, "3\n", ""
    d = Path(tempfile.mkdtemp()) / "fs"
    shutil.copytree(FOLDER, d, ignore=shutil.ignore_patterns(".lr"))
    if delta:
        shutil.copy(DELTA_CONTROLLERS, d / "controllers.ttl")
    eng = Engine(Project.load(d, persist=False), shell=ShellTool(executor=run), approver=lambda c: True)
    for _ in range(20):  # list the folder: then the sheet holds all n files
        eng.step()
        if len(list(eng.sheet.subjects(None, None))) > n:
            break
    return eng


PFX = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix lr: <https://loopingrules.org/ns#> .
@prefix ex: <https://example.org/s#> .
"""
COUNTER = PFX + """
ex:count a lr:Operation ; rdfs:label "count" ;
  lr:where  " ex:c ex:value ?x . FILTER(?x < 100000) BIND(?x + 1 AS ?y) " ;
  lr:delete " ex:c ex:value ?x . " ;
  lr:insert " ex:c ex:value ?y . " .
"""


def counter(junk: int = 0, ops: int = 0) -> Engine:
    d = Path(tempfile.mkdtemp())
    model = COUNTER + "".join(
        f'ex:idle{i} a lr:Operation ; rdfs:label "idle {i}" ;\n'
        f'  lr:where " ?a ex:p{i} ?b . FILTER NOT EXISTS {{ ?b ex:q{i} ?a }} " ;\n'
        f'  lr:insert " ?b ex:q{i} ?a . " .\n' for i in range(ops))
    (d / "model.ttl").write_text(model)
    sheet = PFX + "ex:c ex:value 0 .\n" + "".join(f"ex:n{i} ex:junk ex:n{i + 1} .\n" for i in range(junk))
    (d / "sheet.ttl").write_text(sheet)
    return Engine(Project.load(d, persist=False))


WORKLOADS = {
    "folder": ("files", [25, 50, 100, 200, 400], lambda n: folder(n), 40),
    "folder-delta": ("files", [25, 50, 100, 200, 400], lambda n: folder(n, delta=True), 40),
    "junk": ("junk triples", [1000, 5000, 20000, 50000], lambda n: counter(junk=n), 40),
    "ops": ("idle operations", [10, 25, 50, 100, 200], lambda n: counter(ops=n), 40),
}


def slope(xs, ys) -> float:
    pts = [(math.log(x), math.log(y)) for x, y in zip(xs, ys) if y > 0.01]
    if len(pts) < 2:
        return float("nan")
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    num = sum((x - mx) * (y - my) for x, y in pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    return num / den


def main() -> None:
    instrument()
    chosen = [a for a in sys.argv[1:] if a in WORKLOADS] or list(WORKLOADS)
    print(f"matcher: {mirror.describe()}")
    for name in chosen:
        unit, sizes, make, ticks = WORKLOADS[name]
        print(f"\n{name}: ms per tick by {unit}")
        print(f"{'size':>8} {'ticks':>6} {'total':>8} " + " ".join(f"{p:>7}" for p in PHASES))
        rows = []
        for n in sizes:
            eng = make(n)
            eng.step()  # warm the query caches
            per_tick, phases, done = measure(eng, ticks)
            rows.append((n, per_tick, phases))
            print(f"{n:>8} {done:>6} {per_tick:>8.1f} " + " ".join(f"{phases[p]:>7.1f}" for p in PHASES))
        xs = [r[0] for r in rows]
        print(f"{'growth':>8} {'':>6} {slope(xs, [r[1] for r in rows]):>8.2f} "
              + " ".join(f"{slope(xs, [r[2][p] for r in rows]):>7.2f}" for p in PHASES))


if __name__ == "__main__":
    main()
