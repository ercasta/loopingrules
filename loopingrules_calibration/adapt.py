"""`loopingrules_calibration.adapt` -- slow-timescale adaptation: re-tune a
frozen world between episodes, from the checks, as the environment drifts.

`docs/plan-adaptation.md` (D4) splits adaptation by timescale and says build
the slow one first: *"Run -> observe the completed trace -> adjust knobs ->
next run. This is incremental re-calibration: literally `search` applied to
the latest trace, keeping the inner world deterministic given the knobs."*
This module is that, and nothing more.

* `Adapter` -- the policy: which `Knob`s may move, the `Check`s that score a
  trace (the SAME objects the offline scorer uses), and the three guards D4
  requires from day one and that are easy to skip -- `margin` (hysteresis:
  move only past it), `every` (a rate limit: at most one adjustment per N
  episodes), and the knob's own `low`/`high` (bounds, enforced by the grid).
* `adapt(episodes, install, adapter, start=...)` -- walk a stream of
  scenarios, and before each episode re-`search` a window of the PAST
  episodes; adopt the best values only if they beat the current ones by
  `margin`. Returns the final values and a per-episode `Step` record.

## Why between episodes, not inside one

D4 is explicit that the two timescales are different jobs. The slow one is
safe: the inner world stays deterministic given the knobs, so a re-run is
reproducible and `replay` twice gives the same trace (`docs/tuning.md`'s
gate). The fast one -- a rule that writes a knob or a `RuleControl` mid-run --
is Phase 7, and it is where oscillation lives; `loopingrules.reflect` (D7)
now supplies the channel it will need, but nothing here uses it.

## The one invariant worth stating

`adapt` never lets an episode tune itself: the window is strictly episodes
BEFORE the current one. A leak there would make the reported score optimistic
and the drift curve a lie, so it is the first thing the tests pin.

## What this does not settle

* **Which knob to move, and by how much.** A full re-`search` over the grid
  each step is the honest baseline; a cheaper step is a separate question, and
  the objective is step-shaped anyway (`docs/tuning.md`), so gradients are out.
* **Oscillation between episodes.** `margin`/`every` damp it; there is no
  stability proof, which is `docs/plan-adaptation.md`'s own named gap.
* **Multi-knob coupling.** A re-search moves them together; no policy here.
* **Pull-back to the baseline.** D4 wants a revert when adaptation drives the
  system out of bounds; `start` IS the baseline, but reverting to it on a bad
  episode is not built.
"""

from __future__ import annotations

import dataclasses

from .checks import total
from .kit import replay, replay_cached, search


@dataclasses.dataclass(frozen=True)
class Adapter:
    """The slow-timescale adaptation policy. `knobs` is the declared surface
    that may move (build it from `surface.runtime_knobs(knobs(loop))` -- only
    `scope="runtime"` knobs are fair game, D3/D4); `checks` are the same
    `Check` objects an offline scorer is built from."""

    knobs: tuple
    checks: tuple
    margin: float = 0.0
    every: int = 1
    window: int = 1
    budget: int = 200

    def scorer(self):
        """The shared objective -- the SAME callable is what an offline
        `calibrate`/`search` would use, because the checks are shared."""
        return total(*self.checks)


@dataclasses.dataclass(frozen=True)
class Step:
    """One episode's record: the `values` it ran under, the `score` it earned
    (the shared scorer), and whether this episode moved them."""

    index: int
    values: tuple
    score: float
    moved: bool


def _window_score(install, scenarios, knobs, values, scorer, budget, cache):
    total_ = 0.0
    for scenario in scenarios:
        if values is None:
            trace = replay(scenario, install, budget=budget)
        else:
            trace = replay_cached(cache, install, scenario, knobs, values,
                                  budget)
        total_ += scorer(trace)
    return total_


def adapt(episodes, install, adapter: Adapter, start=None):
    """Re-calibrate across a stream of `episodes` (scenarios, in order).

    `start` is the baseline knob values (D4: "the offline-calibrated world is
    the controller's baseline"); `None` means the domain's own seeded
    defaults. Returns `(values, steps)`: the final values and one `Step` per
    episode. Deterministic: same stream, install and adapter, same result.
    """
    scorer = adapter.scorer()
    cache = {}
    values = start
    history = []
    steps = []
    for i, scenario in enumerate(episodes):
        moved = False
        if history and i % adapter.every == 0:
            window = tuple(history[-adapter.window:])
            best = search(install, window, adapter.knobs, scorer,
                          budget=adapter.budget, cache=cache)
            current = _window_score(install, window, adapter.knobs, values,
                                    scorer, adapter.budget, cache)
            if best.score > current + adapter.margin:
                values = best.values
                moved = True
        if values is None:
            live = replay(scenario, install, budget=adapter.budget)
        else:
            live = replay(scenario, install, adapter.knobs, values,
                          budget=adapter.budget)
        history.append(scenario)
        steps.append(Step(i, values, scorer(live), moved))
    return values, tuple(steps)
