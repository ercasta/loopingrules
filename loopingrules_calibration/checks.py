"""`loopingrules_calibration.checks` -- the pure vocabulary an objective is
built from, shared by the offline scorer and a runtime controller.

`docs/plan-dataset.md` (D2) names a **Check** as the unit: "a pure function
`Trace -> score or observation` (plus the ability to compose)". `docs/
plan-adaptation.md` (D4) then locks the reason it must be *pure*: the same
checks drive **two sandboxes** -- an inert `scorer` over recorded traces
(offline, which must NOT perturb what it measures) and a controller that
deliberately writes (online, where perturbation is the point). If those were
two implementations they would drift; one vocabulary, wired twice, is the
seam Phase 4 exists to prove.

## Why a class and not just functions

A bare `Trace -> float` composes with `sum`/`lambda`, which is fine for one
author. What the seam needs is for the *terms to be nameable* -- so a report
can say which check a controller moved, and so a controller and a scorer can
be shown to be the SAME objects rather than two same-shaped lambdas. A `Check`
is a name, a pure function, and a weight; `total(*checks)` is the scorer.

Nothing here touches the engine or a domain: a check reads a `Trace` (its
`world`, `replies`, `observations`, `changes`, `hot`, `ticks`) and returns a
number. Higher is better. Composition is a weighted sum, kept inspectable on
purpose (`docs/tuning.md`: "keep the objective inspectable").

## What this does not settle

* **Ranking checks.** D2 makes preference pairs (`A > B`) first-class. This
  module is scalar-only; a pairwise check is a real, separate addition.
* **Tuned checks.** Whether a check may itself read a knob (D2's own open
  question: "checks may themselves be tuned") is not decided here.
* **The observation contract.** `invariant` reads `Trace.observations`, which
  is whatever `replay(..., observe=...)` returned -- the domain's own shape.
  A check that assumes a shape couples the dataset to it (D2's named hazard).
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Check:
    """A named, pure term of an objective. `fn(trace) -> float`, higher
    better; `weight` scales it in a `total`. Call it to score one trace."""

    name: str
    fn: object
    weight: float = 1.0

    def score(self, trace) -> float:
        return self.weight * float(self.fn(trace))

    def __call__(self, trace) -> float:
        return self.score(trace)


def check(name: str, weight: float = 1.0):
    """Decorate a pure `fn(trace) -> float` into a `Check`."""
    def wrap(fn):
        return Check(name, fn, weight)
    return wrap


def as_check(name: str, scorer, weight: float = 1.0) -> Check:
    """Wrap an existing plain scorer (`Trace -> float`, e.g. a kit helper like
    `settled()`) as a named `Check`, so old and new terms compose together."""
    return Check(name, scorer, weight)


def total(*checks) -> "object":
    """The scorer: a pure `Trace -> float` summing each check's weighted
    score. The SAME callable is handed to `search`/`calibrate` offline and to
    a controller online -- that identity is the point (`docs/plan-adaptation.
    md`), so build it once and pass it to both."""
    def scorer(trace) -> float:
        return sum(term.score(trace) for term in checks)
    return scorer


# -- generic checks, true of any domain --------------------------------
#
# Helpers, not a framework, in the same spirit as the kit's own scorers.
# Domain terms (goal met, overpaid, agreement with a label) belong in the
# domain; these are the ones every trace has.

def settles(weight: float = 1.0) -> Check:
    """1.0 if the world settled inside the budget, else 0.0 -- `hot` is the
    circuit breaker having fired (`docs/tuning.md` penalises it)."""
    return Check("settles", lambda trace: 0.0 if trace.hot else 1.0, weight)


def ticks_at_most(n: int, weight: float = 1.0) -> Check:
    """1.0 if it settled in at most `n` ticks -- a cheap 'does not dither'."""
    return Check("ticks<%d" % n,
                 lambda trace: 1.0 if trace.ticks <= n else 0.0, weight)


def says(text: str, weight: float = 1.0) -> Check:
    """1.0 if any `Reply` on the trace contains `text` -- the black-box pole
    (D2 (a)): an output observable, no internal vocabulary assumed. (The kit's
    older `reply_contains(text)` is a plain scorer that does the same; this is
    its named, composable form.)"""
    return Check("says:%s" % text,
                 lambda trace: 1.0 if any(text in r for r in trace.replies)
                 else 0.0, weight)


def world_has(kind, weight: float = 1.0) -> Check:
    """1.0 if the settled world carries `kind` anywhere."""
    return Check("has:%s" % kind.__name__,
                 lambda trace: 1.0 if trace.world.populated(kind) else 0.0,
                 weight)


def invariant(pred, weight: float = 1.0) -> Check:
    """The fraction of ticks an observation held `pred` -- the PROCESS pole
    (D2 (b)). Reads `Trace.observations`, which is whatever the caller's
    `replay(observe=...)` recorded (one value per firing tick); an EMPTY
    observation list scores 1.0 (vacuously true), so a scenario that does not
    observe is not silently punished."""
    def fn(trace) -> float:
        obs = trace.observations
        if not obs:
            return 1.0
        return sum(1 for value in obs if pred(value)) / len(obs)
    return Check("invariant", fn, weight)
