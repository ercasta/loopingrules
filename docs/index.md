# LoopingRules developer guide

LoopingRules is a small Python package (no dependencies, Python 3.9+) that
gives you three things:

1. a **World** of entities and the components attached to them,
2. a **Loop** that calls your **rules** over that world until a whole pass
   changes nothing, and
3. an **Engine**: one thread that owns the loop and routes messages between
   it and any number of channels (a terminal, a socket, a test).

It ships **no domain, no channel and no transport**. Everything you would
build on top of it (a file assistant, a trading agent, a trip planner) is a
set of rules and components that live in your own code. The
[`examples/`](examples.md) directory holds worked ones, and two sibling
packages build on the engine: [`loopingrules_calibration`](plan-calibration.md)
tunes a domain's declared knobs, and [`loopingrules_patterns`](patterns.md)
ships curated patterns once a second domain depends on them.

## Who this guide is for

Someone who has to read, change or build on this codebase. It follows the
order you would want to learn things in:

| If you want to... | Read |
|---|---|
| run it and write a first rule | [Getting started](getting-started.md) |
| understand the model | [Core concepts](concepts.md) |
| see how the modules fit and what happens in one tick | [Architecture](architecture.md) |
| write rules that behave well | [Writing rules](writing-rules.md) |
| attach a terminal or socket | [The engine and channels](engine.md) |
| save a world, or move entities between worlds | [Persistence and sharing](persistence.md) |
| know what a rule reads and writes | [Rule analysis](analysis.md) |
| find a worked domain to copy | [Examples](examples.md) |
| reuse a curated pattern | [Patterns](patterns.md) |
| debug a rule that will not settle | [Testing and debugging](testing-debugging.md) |
| send a change | [Contributing](contributing.md) |

## Design documents in the repo

These are not part of this site, but they are the reasoning behind it, and
they are worth reading once the basics are clear:

- `PRINCIPLES.md` covers what keeps a fixpoint over a shared world producing
  the *wanted* kind of emergence, and not the surprising kind.
- `README.md`'s History records design decisions, including ones whose code
  was later removed.
- `TODO.md` lists open threads.
- `git log` is unusually informative here: commit messages carry the
  reasoning. See [Contributing](contributing.md).

The forward-looking plan, unlike the above, *is* part of this site: the
[Roadmap](plan.md) and its four design documents — [Memory and the change
log](plan-memory.md), [Dataset and scoring](plan-dataset.md), [Calibration
API and knobs](plan-calibration.md), and [Online adaptation](plan-adaptation.md).
Phases 1-2 of the roadmap are built — the calibration kit and the change
log — and Phase 3's author surface, linter and first [pattern](patterns.md)
with them; the rest of the pattern library and the roadmap are design. Each
document ends with what it does *not* settle, in the same posture as
`TODO.md`.
