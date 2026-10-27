"""`loopingrules_calibration` -- the author-facing calibration kit.

The engine (`loopingrules`) runs a world of rules to a fixpoint but says
nothing about whether a run is GOOD. When the trajectory is decided by
parameters the rules READ (`docs/tuning.md`: "a tunable rule never
hard-codes its threshold; it reads a component"), deciding whether a run is
good -- and searching for the values that make it so -- is a separate job.
This is that job, and it ships no domain vocabulary: it is the same kind of
generic machinery `loopingrules.analyze` is, in a second package so the
engine keeps its "no domain, no channel, no transport" stance.

    from loopingrules_calibration import Knob, Scenario, replay, search

    knobs = (Knob(cards.RiskProfile, "max_premium", 0.0, 0.4, steps=5),)
    cases = (Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",)),)

    def scorer(trace):
        return 1.0 if trace.world.populated(cards.Bought) else 0.0

    best = search(cards.install, cases, knobs, scorer)

Four things, kept apart on purpose:

* **data** -- `Scenario` (an episode) and `Trace` (its result, the unit a
  scorer reads);
* **tunables** -- `Knob` (one field of one singleton component, with the
  range to search, and a `scope` saying whether a runtime controller may
  move it later);
* **search** -- `grid`/`search` (an optimizer-free baseline: the objective
  is piecewise-constant, so gradients are meaningless) and `calibrate`,
  which reports held-out scores and behavioural plateaus;
* **objective** -- a `scorer: Trace -> float` supplied by the caller, with a
  few generic helpers (`settled`, `reply_contains`, `reached`) that compose
  in ordinary Python.

See `docs/plan-calibration.md` for the design, and `docs/tuning.md` for the
theory this is the instrument for. What is NOT here yet, named so it is not
mistaken for settled: the dataset artifact and capture channel, the checks
vocabulary, preference pairs (`docs/plan-dataset.md`), the tunability
linter, and the change log (`docs/plan-memory.md`).
"""

from __future__ import annotations

from .kit import (
    Best,
    Knob,
    Scenario,
    Trace,
    grid,
    reached,
    read_knobs,
    replay,
    replay_cached,
    reply_contains,
    search,
    settled,
    write_knobs,
)
from .report import Report, calibrate

__all__ = [
    "Best",
    "Knob",
    "Report",
    "Scenario",
    "Trace",
    "calibrate",
    "grid",
    "reached",
    "read_knobs",
    "replay",
    "replay_cached",
    "reply_contains",
    "search",
    "settled",
    "write_knobs",
]
