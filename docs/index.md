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
[`examples/`](examples.md) directory holds worked ones.

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
| know what a rule reads and writes | [Rule analysis and circuits](analysis.md) |
| resolve "it", or score rival readings of a line | [Language layer](language.md) |
| find a worked domain to copy | [Examples](examples.md) |
| debug a rule that will not settle | [Testing and debugging](testing-debugging.md) |
| send a change | [Contributing](contributing.md) |

## Design documents in the repo

These are not part of this site, but they are the reasoning behind it, and
they are worth reading once the basics are clear:

- `PRINCIPLES.md` covers what keeps a fixpoint over a shared world producing
  the *wanted* kind of emergence, and not the surprising kind.
- `DECISION_PATTERNS.md` records design decisions, including ones whose code
  was removed.
- `TODO.md` lists open threads.
- `git log` is unusually informative here: commit messages carry the
  reasoning. See [Contributing](contributing.md).
