"""The `lr` command line: run a model against a context.

The smallest usable surface: load a model (YAML components + operations), seed a
context (the anchor), run the loop to a fixpoint, and report what happened --
the **applications** (which operation fired, per tick), the settled world, and any
**gaps**. `--json` is for scripting; a `session` subcommand (load once, re-run many
contexts) is the next step.
"""

from __future__ import annotations

import argparse
import json

from . import harness


def _as_json(run) -> dict:
    world = run.world
    return {
        "model": run.model.name,
        "ticks": run.ticks,
        "settled": run.settled,
        "applied": [list(tick) for tick in run.applied],
        "gaps": run.gaps(),
        "entities": [
            {"id": entity.id,
             "components": {name: dict(bag)
                            for name, bag in world.components(entity).items()}}
            for entity in world.entities()
        ],
    }


def _print_run(run) -> None:
    world = run.world
    print("%s: %s in %d tick%s"
          % (run.model.name, "settled" if run.settled else "HOT", run.ticks,
             "" if run.ticks == 1 else "s"))
    print("applied:")
    for index, tick in enumerate(run.applied, 1):
        print("  %-3d %s" % (index, ", ".join(tick) or "(nothing)"))
    print("world:")
    for entity in world.entities():
        print("  " + world.show(entity))
    gaps = run.gaps()
    print("gaps: %s" % (", ".join(gaps) if gaps else "(none)"))


def _run(args) -> int:
    run = harness.run_files(args.model, args.context, budget=args.budget)
    if args.json:
        print(json.dumps(_as_json(run), indent=2, default=str))
    else:
        _print_run(run)
    return 0 if run.settled else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lr", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run a model against a context")
    run_parser.add_argument("model", help="a model YAML (components + operations)")
    run_parser.add_argument("context", help="a context YAML (the anchor)")
    run_parser.add_argument("--budget", type=int, default=200)
    run_parser.add_argument("--json", action="store_true")
    run_parser.set_defaults(func=_run)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
