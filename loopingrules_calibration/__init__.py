"""`loopingrules_calibration` -- the author-facing calibration kit.

The engine (`loopingrules`) runs a world of rules to a fixpoint but says
nothing about whether a run is GOOD. When the trajectory is decided by
parameters the rules READ (`docs/tuning.md`: "a tunable rule never
hard-codes its threshold; it reads an attribute"), deciding whether a run is
good -- and searching for the values that make it so -- is a separate job.

    from loopingrules_calibration import Knob, Scenario, replay, search

    knobs = (Knob("max_premium", 0.0, 0.4, steps=5),)
    cases = (Scenario(kwargs=(("cash", 100),), lines=("list dragon 40",)),)

    def scorer(trace):
        return 1.0 if trace.world.populated("bought") else 0.0

    best = search(cards.install, cases, knobs, scorer)

A `Knob` names an ATTRIBUTE; the value lives on whichever entity carries it.
A rule declares its own tunable surface with `@tunable(Knob(...))`,
`knobs(loop)` collects it, and `lint` holds those rules to it. The
**objective** has a vocabulary of its own: `checks.Check` names a pure term,
`total(*checks)` composes the scorer, and the SAME `Check` objects feed a
slow-timescale `adapt.Adapter` that re-tunes the knobs between episodes as
the world drifts (`docs/plan-adaptation.md`).
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
from .linter import Finding, LintError, LintReport, lint
from .report import Report, calibrate
from .checks import (
    Check,
    as_check,
    check,
    invariant,
    says,
    settles,
    ticks_at_most,
    total,
    world_has,
)
from .adapt import Adapter, Step, adapt
from .surface import declared, knobs, runtime_knobs, tunable

__all__ = [
    "Adapter",
    "Best",
    "Check",
    "Finding",
    "Knob",
    "LintError",
    "LintReport",
    "Report",
    "Scenario",
    "Step",
    "Trace",
    "adapt",
    "as_check",
    "calibrate",
    "check",
    "declared",
    "grid",
    "invariant",
    "knobs",
    "lint",
    "reached",
    "read_knobs",
    "replay",
    "replay_cached",
    "runtime_knobs",
    "says",
    "search",
    "settled",
    "settles",
    "ticks_at_most",
    "total",
    "tunable",
    "world_has",
    "write_knobs",
]
