"""`loopingrules_lang` -- a minimal, growable authoring surface + runtime harness.

The user-facing half of Plan U: write **components** and **operations** in YAML,
initialise a **context** (the anchor), and run -- on the existing substrate, with
no control network yet. YAML lowers to Python first (ADR-7's staged execution), so
this is not a throwaway: the same surface folds to the IR core later.

    from loopingrules_lang import harness
    run = harness.run_files("market.yaml", "market.context.yaml")
    run.settled, run.chosen(), run.gaps()

* `components` -- declared schemas (ADR-10).
* `operations` -- capabilities: a guard + effects (ADR-11). The operator set is
  CLOSED and small, grown only where it collides (ADR-2).
* `context` -- the anchor: entities and their components (ADR-8).
* `harness`, `cli` -- load, install, run to a fixpoint, and report applications.
"""

from __future__ import annotations

from .harness import Model, Run, install, load, parse, run, run_files

__all__ = ["Model", "Run", "install", "load", "parse", "run", "run_files"]
