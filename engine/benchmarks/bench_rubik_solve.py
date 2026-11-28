"""Benchmark: the Rubik solver (examples/rubik), a matching-heavy workload.

    .venv/Scripts/python benchmarks/bench_rubik_solve.py [--profile] [seeds...]   (default seed: 3)

For each seed: a 25-move scramble, then a solve. Reports ticks and ms/tick per
operation. The planning ticks ("plan a case", "next stage") match every case of
the stage in 4 frames, with nested FILTER NOT EXISTS over knowledge: they are the
cost to watch. Nothing touches the disk.
"""

import cProfile
import pstats
import random
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from loopingrules.engine import Engine
from loopingrules.project import Project

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "rubik"
MOVES = [f + s for f in "UDFBRL" for s in ("", "i", "2")]


def run(seed: int) -> tuple[Counter, Counter]:
    d = Path(tempfile.mkdtemp()) / "rubik"
    shutil.copytree(EXAMPLE, d, ignore=shutil.ignore_patterns(".lr", "*.py"))
    eng = Engine(Project.load(d, persist=False))
    rng = random.Random(seed)
    moves = [rng.choice(MOVES) for _ in range(25)]
    eng.post("[] a rk:Scramble ; rk:moves ( " + " ".join("mv:" + m for m in moves) + " ) .")
    eng.run()
    eng.post("[] a rk:Solve .")
    spent, count = Counter(), Counter()
    while True:
        t = time.perf_counter()
        r = eng.step()
        dt = time.perf_counter() - t
        if r.status != "applied":
            break
        spent[r.application.operation.name] += dt
        count[r.application.operation.name] += 1
    shutil.rmtree(d.parent, ignore_errors=True)
    return spent, count


def main() -> None:
    args = sys.argv[1:]
    profile = "--profile" in args
    seeds = [int(a) for a in args if a != "--profile"] or [3]
    prof = cProfile.Profile() if profile else None
    for seed in seeds:
        if prof:
            prof.enable()
        spent, count = run(seed)
        if prof:
            prof.disable()
        n, total = sum(count.values()), sum(spent.values())
        print(f"seed {seed}: {n} ticks, {total:.1f} s, {1000 * total / n:.0f} ms/tick")
        for op in count:
            print(f"  {op:16} {count[op]:4} ticks  {1000 * spent[op] / count[op]:6.0f} ms/tick")
    if prof:
        pstats.Stats(prof).sort_stats("cumulative").print_stats(20)


if __name__ == "__main__":
    main()
