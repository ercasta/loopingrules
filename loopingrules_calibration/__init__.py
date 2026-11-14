"""`loopingrules_calibration` -- the author-facing calibration kit.

> **Phase S in progress (D8).** Ported so far: `kit` (`Knob`/`Scenario`/
> `Trace`/`replay`/`search`/scorers, now naming ATTRIBUTES) and `surface`
> (`@tunable`/`declared`/`knobs`). `checks`, `adapt`, `linter` and `report`
> still describe components and are not re-exported until they are ported.

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

A `Knob` names an attribute; the value lives on whichever entity carries it.
A rule declares its own tunable surface with `@tunable(Knob(...))`, and
`knobs(loop)` collects it from the rules a domain registered.
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
from .surface import declared, knobs, runtime_knobs, tunable

__all__ = [
    "Best",
    "Knob",
    "Scenario",
    "Trace",
    "declared",
    "grid",
    "knobs",
    "reached",
    "read_knobs",
    "replay",
    "replay_cached",
    "reply_contains",
    "runtime_knobs",
    "search",
    "settled",
    "tunable",
    "write_knobs",
]
