"""`loopingrules_calibration.report` -- running a calibration and reading it
back.

`search` answers "which values scored highest on this data". `calibrate`
answers the questions an author actually has to ask before trusting that
answer:

- Does the win survive on examples the tuner never saw? (held-out score,
  and its spread across folds.)
- Which settings are behaviourally the SAME (a plateau) rather than a
  unique numeric solution? `docs/tuning.md`: many distinct settings produce
  the same trajectory, so tune to a behavioural equivalence class.
- Which knobs actually move the trajectory, and which do nothing? A flat
  knob is a finding, not noise.

The spread reported is over DATASET RESAMPLING -- which examples fall into
the held-out fold -- not over repeated replays. A replay is deterministic,
so replaying one setting twice gives zero variance and measures nothing;
the variance that matters is how sensitive the answer is to which examples
you happened to keep. (`docs/plan-calibration.md` names this.)
"""

from __future__ import annotations

import dataclasses
import hashlib
import random

from .kit import grid, replay_cached, search


@dataclasses.dataclass(frozen=True)
class Report:
    """The result of `calibrate`. `plateaus` is a tuple of behavioural
    equivalence classes (each a tuple of value-tuples sharing one
    trajectory); `sensitivity` is a tuple of
    `(knob_name, distinct_trajectories, moves)`."""

    best: object
    train_score: float
    eval_score: float
    eval_std: float
    fold_scores: tuple
    plateaus: tuple
    sensitivity: tuple
    signature: str

    def to_markdown(self) -> str:
        """A short, human-readable rendering. The structured fields are
        the artifact; this is for reading."""
        out = ["# Calibration report", ""]
        values = ", ".join(repr(v) for v in self.best.values)
        out.append("Best: `(%s)` -> %.4g" % (values, self.best.score))
        out.append("")
        out.append("Train %.4g / held-out %.4g (+/- %.4g)"
                   % (self.train_score, self.eval_score, self.eval_std))
        out.append("")
        out.append("Signature `%s`" % self.signature)
        out.append("")
        out.append("## Plateaus (behavioural equivalence classes)")
        if self.plateaus:
            for group in self.plateaus:
                rendered = ", ".join(
                    "(" + ", ".join(repr(v) for v in vals) + ")"
                    for vals in group)
                out.append("- %d settings: %s" % (len(group), rendered))
        else:
            out.append("- none: every setting produced a distinct trajectory")
        out.append("")
        out.append("## Sensitivity (each knob swept, the rest held at best)")
        out.append("")
        out.append("| knob | distinct trajectories | moves |")
        out.append("|---|---|---|")
        for name, distinct, moves in self.sensitivity:
            out.append("| %s | %d | %s |"
                       % (name, distinct, "yes" if moves else "no"))
        return "\n".join(out) + "\n"


def _combined_signature(cache, install, scenarios, knobs, values, budget) -> str:
    parts = tuple(replay_cached(cache, install, s, knobs, values, budget).signature
                  for s in scenarios)
    return hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()


def _plateaus(cache, install, scenarios, knobs, budget) -> tuple:
    groups = {}
    for values in grid(knobs):
        sig = _combined_signature(cache, install, scenarios, knobs, values, budget)
        groups.setdefault(sig, []).append(tuple(values))
    plates = [tuple(members) for members in groups.values() if len(members) > 1]
    plates.sort(key=lambda g: (-len(g), g))
    return tuple(plates)


def _sensitivity(cache, install, scenarios, knobs, base_values, budget) -> tuple:
    out = []
    for index, knob in enumerate(knobs):
        sigs = set()
        for value in knob.values():
            values = list(base_values)
            values[index] = value
            sigs.add(_combined_signature(
                cache, install, scenarios, knobs, tuple(values), budget))
        out.append((knob.name, len(sigs), len(sigs) > 1))
    return tuple(out)


def _mean(numbers) -> float:
    return sum(numbers) / len(numbers) if numbers else 0.0


def _pstdev(numbers) -> float:
    if len(numbers) < 2:
        return 0.0
    mean = _mean(numbers)
    return (sum((x - mean) ** 2 for x in numbers) / len(numbers)) ** 0.5


def _folds(cache, install, scenarios, knobs, scorer, folds, seed, budget):
    """k-fold held-out scores. Returns `(train_scores, eval_scores)`, both
    per-fold means, or `((), ())` when the data is too small to split."""
    n = len(scenarios)
    k = min(folds, n)
    if n < 2 or k < 2:
        return (), ()
    indices = list(range(n))
    random.Random(seed).shuffle(indices)
    chunks = [indices[i::k] for i in range(k)]
    train_scores, eval_scores = [], []
    for i in range(k):
        ev = [scenarios[j] for j in chunks[i]]
        train = [scenarios[j] for c in range(k) if c != i for j in chunks[c]]
        best = search(install, train, knobs, scorer, budget=budget, cache=cache)
        train_scores.append(best.score / len(train))
        eval_scores.append(_mean([
            scorer(replay_cached(cache, install, s, knobs, best.values, budget))
            for s in ev]))
    return tuple(train_scores), tuple(eval_scores)


def calibrate(install, scenarios, knobs, scorer, folds: int = 5, seed: int = 0,
              budget: int = 200) -> Report:
    """Tune `knobs` on `scenarios` and report the answer honestly.

    `best` is `search` over ALL the data (the value an author would ship);
    `train_score`/`eval_score`/`eval_std` come from k-fold held-out runs,
    so the win is measured on examples the tuner did not see. With fewer
    than two scenarios there is nothing to hold out, and the held-out
    fields collapse to the training ones with zero spread -- stated, not
    silently faked.

    Every replay across the whole calibration shares one cache, so each
    `(scenario, values)` is computed once even though the full grid is
    walked once per fold.
    """
    scenarios = list(scenarios)
    cache = {}
    best = search(install, scenarios, knobs, scorer, budget=budget, cache=cache)
    signature = _combined_signature(
        cache, install, scenarios, knobs, best.values, budget)
    plateaus = _plateaus(cache, install, scenarios, knobs, budget)
    sensitivity = _sensitivity(
        cache, install, scenarios, knobs, best.values, budget)
    train_scores, eval_scores = _folds(
        cache, install, scenarios, knobs, scorer, folds, seed, budget)
    if eval_scores:
        train_score = _mean(train_scores)
        eval_score = _mean(eval_scores)
        eval_std = _pstdev(eval_scores)
    else:
        train_score = eval_score = best.score / len(scenarios) if scenarios else 0.0
        eval_std = 0.0
    return Report(best=best, train_score=train_score, eval_score=eval_score,
                  eval_std=eval_std, fold_scores=eval_scores,
                  plateaus=plateaus, sensitivity=sensitivity,
                  signature=signature)
