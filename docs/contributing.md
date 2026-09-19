# Contributing

## Scope: what belongs in this package

The package is a **substrate**. Before adding anything, check it against
"no domain, no channel, no transport":

- A rule for a specific domain belongs in `examples/` (or your own repo), not
  in `loopingrules/`.
- A channel (terminal, socket) belongs in a host such as `harneskills`.
- Shared vocabulary earns a place in the core only when two independently
  motivated domains must agree on it and neither can own it. `Said`, `Reply`
  and `Proposal` are the precedent. `help.py` is the single stated exception
  and explains itself.
- `pyproject.toml` lists `packages = ["loopingrules"]`. Examples are never
  added to it.

Read `PRINCIPLES.md` before adding a component type or a rule. In short:

- Prefer an existing vocabulary to a new one. A new edge or component type is
  a decision to justify.
- A rule's conclusion re-enters the world as an ordinary component, never a
  special "result" wrapper.
- **A wrong conclusion is worse than a missing one.** Make abstention
  structural. A rule that can be uncertain must be able to produce nothing.
- Keep component types literal in a rule so `analyze` stays sound.
- Do not add caching until a rule's cost is measured and named as the
  bottleneck.

## Working on the code

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest -q
```

Add a test with every change, in the file that matches the module. If you
add an example domain, add a matching `tests/test_examples_*.py`.

Write code that reads like its surroundings: match the neighbouring comment
density, naming and idiom. This codebase explains *why* in docstrings, and new
modules should too.

## Line endings on Windows

This repo is edited on Windows. Set `git config core.autocrlf true` locally,
or files can appear entirely modified when only their line endings differ.
`git diff --stat --ignore-cr-at-eol` tells you whether a diff is real.

## Commits

Commits here are read later by someone who was not in the room. A message
is where the reasoning lives, not a changelog line.

**Title.** One line saying what changed *and* why, in the same breath:
`<file/area>: <change>, because <reason>` or `<change> — <consequence>`.
Not a bare imperative. It should make sense in `git log --oneline`.

**Body.** Prose, not a changelog. Say what was actually broken (the root
cause, ideally with a repro or numbers), why whatever already guarded
against it did not catch it, what the fix is and what it costs. Treat the
system as an actor ("a rule that mints can spend the whole machine before
tick 400") and not as a diff being narrated. Name what you deliberately left
alone and why that is correct *for now*. A silent gap is worse than a named
one. A caveat or warning gets its own plain sentence.

**Evidence.** Close with what was verified, concretely: `117 -> 128 passing`,
not "tests pass". If you reproduced a regression before the fix and saw it
gone after, say so.

**Trailer.** Work done by an AI session ends with a `Co-Authored-By: Claude
... <noreply@anthropic.com>` trailer, unless a human author asks for a specific
commit to carry their authorship alone.

Recent history is the best template: `git log -5`.

## Where design goes

- Open threads: `TODO.md`. Named so they are not lost, not a schedule.
- Decisions, including ones whose code was removed: `DECISION_PATTERNS.md`.
- What keeps emergence the *wanted* kind: `PRINCIPLES.md`.
- How the site is built: edit `docs/` and `mkdocs.yml`, then see below.

## Building this guide

```powershell
.venv\Scripts\python -m pip install mkdocs
.venv\Scripts\python -m mkdocs serve        # live preview at http://127.0.0.1:8000
.venv\Scripts\python -m mkdocs build --strict   # the check: fails on broken links
```

The guide describes the code as of the commit it is in. When you change a
public behaviour, update the matching page in the same commit. Code samples on
these pages were run against the code, so re-run one if you change what it
shows.
