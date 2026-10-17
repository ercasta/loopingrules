"""`hierarchy` -- Experiment 4 from `docs/tuning.md`, the "freeze the
islands, tune only the bridge" scheme, measured rather than asserted.

## The scheme under test

Two-stage ("bilevel", greedy) tuning: (1) tune each island on ITS OWN local
task with its own examples, then FREEZE its knob; (2) tune ONLY the bridge
that connects the islands, against the GLOBAL objective. The claim to test
is that stage 2 is enough to reach the wanted overall behaviour.

## The model, spelled out

One *situation* is a pair of raw signals `(x1, x2)`, each in `[0, 1]`:

- **island ALPHA** sees `x1` and reports a graded opinion in `[0, 1]`,
  `clamp(x1 - bias_a + 0.5)`; its knob is `bias_a`, and its LOCAL task is
  "flag when `x1 > cut_a`". It is tuned on its own examples.
- **island BETA** sees `x2` the same way with `bias_b` and `cut_b`.
- **the bridge** is a weighted threshold: verdict = `w_a*alpha + w_b*beta
  >= theta`. Its knobs are the two weights and the threshold -- the only
  things stage 2 may move.
- **the global objective** is a hidden policy that needs BOTH signals with
  UNEQUAL weight: `0.7*x1 + 0.3*x2 >= 0.5`. Equal bridge weights do not
  express it; tuned weights (w_a : w_b = 7 : 3) do.

Every island's opinion is a pure function of its own signal and knob, so
the tuning harness evaluates them directly (`opinions`) for speed; the
rule world (`install` / `alpha_judge` / `beta_judge` / `gate_decide`) is
the identical computation, and a test pins that the two agree. Everything
is seeded, so every number is reproducible.

## The three measurements

1. **Reach.** With the islands frozen at their locally-tuned knobs, can
   stage 2 (tuning the bridge weights) reach the global objective, and how
   far past the naive equal-weight bridge does it get? Compared against the
   JOINT optimum (everything tuned at once) as the ceiling.
2. **Fight.** `joint - greedy`: how much the freeze COSTS. Run twice --
   once with the islands' local tasks ALIGNED with the global boundary
   (`cut_a = cut_b = 0.5`), once MISALIGNED (`0.2`, `0.8`). Expectation:
   the freeze is free when the local tasks are good proxies for the global
   one, and costs when they are not.
3. **Covariate shift.** Does conditioning the island's training data on the
   region the composed decision actually reaches move its locally-tuned
   optimum? For a threshold task it should not -- the optimum is the label
   boundary regardless of the input distribution -- which points at the
   real lever being the OBJECTIVE, not the data.

## What this found

Measured on held-in situations (this probe measures REACH, not
generalization), the global objective being `0.7*x1 + 0.3*x2 >= 0.5`:

- **The bridge does the work, and the freeze is not free.** With the
  islands frozen, tuning the bridge beats an equal-weight bridge
  (`0.963` vs `0.873` when the local tasks are ALIGNED; `0.933` vs `0.902`
  when they are MISALIGNED). The joint ceiling is `0.983`.
- **Freezing costs more when the local tasks misalign.** `joint - staged`
  is `~0.02` aligned and `~0.05` misaligned -- and it is NOT zero even when
  aligned: joint tuning sets biases away from the local optimum to create a
  SATURATING island the linear bridge can exploit, so "the local task's
  best knob" is not "the best feature for the global task," even when their
  boundaries coincide.
- **Conditioning the data is not the lever.** The locally-tuned knob does
  not move under a shifted input distribution for a well-specified
  threshold OR calibration task (`0.5` either way); it moves only when the
  island's mechanism is MISSPECIFIED (`gain 2`, conditioned to `x1 < 0.4`:
  `0.5 -> 0.4`). And conditioning hard enough can make the local labels a
  single class, at which point the local objective is undefined -- a real
  fragility of "tune on the inputs it actually sees."

So the scheme's load-bearing assumption is not the data distribution but
that **each island's LOCAL objective is an honest proxy for the GLOBAL
one**. Where it is, the freeze is nearly free. Where it is not, re-weighting
the bridge helps but does not close the gap; the fix is to re-target the
objective (the joint tuning), not to re-condition the data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from loopingrules.loop import Loop
from loopingrules.world import transient


# -- the rule world (the identical computation `opinions` does fast) -----

@dataclass(frozen=True)
class Situation:
    x1: float
    x2: float


@dataclass(frozen=True)
class AlphaCal:
    bias: float


@dataclass(frozen=True)
class BetaCal:
    bias: float


@dataclass(frozen=True)
class Gate:
    w_alpha: float
    w_beta: float
    theta: float


@dataclass(frozen=True)
class Alpha:
    value: float


@dataclass(frozen=True)
class Beta:
    value: float


@transient
@dataclass(frozen=True)
class Verdict:
    pass


def _clamp(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _opinion(signal: float, bias: float) -> float:
    return _clamp(signal - bias + 0.5)


def _opinion_gain(signal: float, bias: float, gain: float) -> float:
    """A *misspecifiable* island mechanism: gain 1 is the well-specified
    one above, gain > 1 sharpens (and saturates) it."""
    return _clamp(gain * (signal - bias) + 0.5)


def alpha_judge(w) -> None:
    cal = w.the(AlphaCal)
    for entity, situation in w.each(Situation):
        w.replace(entity, Alpha(_opinion(situation.x1, cal.bias)))


def beta_judge(w) -> None:
    cal = w.the(BetaCal)
    for entity, situation in w.each(Situation):
        w.replace(entity, Beta(_opinion(situation.x2, cal.bias)))


def gate_decide(w) -> None:
    gate = w.the(Gate)
    for entity, _situation, alpha, beta in w.each(Situation, Alpha, Beta):
        if gate.w_alpha * alpha.value + gate.w_beta * beta.value >= gate.theta:
            w.attach(entity, Verdict())
        else:
            w.detach(entity, Verdict)


RULES = (alpha_judge, beta_judge, gate_decide)


def install(loop, alpha_bias=0.5, beta_bias=0.5,
            w_alpha=1.0, w_beta=1.0, theta=1.0) -> None:
    loop.rule(alpha_judge)
    loop.rule(beta_judge)
    loop.rule(gate_decide)
    world = loop.world
    world.spawn(AlphaCal(alpha_bias))
    world.spawn(BetaCal(beta_bias))
    world.spawn(Gate(w_alpha, w_beta, theta))


# -- the fast path (same function, no Loop) ------------------------------

def opinions(situations, alpha_bias, beta_bias):
    """`(alphas, betas)` for every situation, in order -- the same values
    `alpha_judge`/`beta_judge` write into a world."""
    alphas = [_opinion(x1, alpha_bias) for x1, _x2 in situations]
    betas = [_opinion(x2, beta_bias) for _x1, x2 in situations]
    return alphas, betas


def verdicts(alphas, betas, w_alpha, w_beta, theta):
    return [1 if w_alpha * a + w_beta * b >= theta else 0
            for a, b in zip(alphas, betas)]


def run_world(loop, situations):
    """The rule world for real: spawn the situations, tick, and return the
    verdicts in order -- used to PIN that `opinions`/`verdicts` agree with
    what the rules do."""
    world = loop.world
    for x1, x2 in situations:
        world.spawn(Situation(x1, x2))
    loop.run()
    return [world.has(entity, Verdict)
            for entity, _s, _a, _b in world.each(Situation, Alpha, Beta)]


# -- labels: the local tasks, and the hidden global objective ------------

GLOBAL_COEF = (0.7, 0.3)
GLOBAL_CUT = 0.5

ALIGNED_CUTS = (0.5, 0.5)        # local tasks agree with the global boundary
MISALIGNED_CUTS = (0.2, 0.8)     # local tasks disagree with it


def global_truth(x1, x2) -> int:
    return int(GLOBAL_COEF[0] * x1 + GLOBAL_COEF[1] * x2 >= GLOBAL_CUT)


def _local_class(signal, cut) -> int:
    return int(signal > cut)


def dataset(count, seed=0):
    rng = random.Random(seed)
    return tuple((rng.random(), rng.random()) for _ in range(count))


# -- balanced accuracy, and the tuners -----------------------------------

def balanced(preds, labels) -> float:
    positive = [p for p, l in zip(preds, labels) if l]
    negative = [p for p, l in zip(preds, labels) if not l]
    if not positive or not negative:
        raise ValueError("balanced accuracy needs both classes")
    true_pos = sum(1 for p in positive if p) / len(positive)
    true_neg = sum(1 for p in negative if not p) / len(negative)
    return (true_pos + true_neg) / 2


BIAS_GRID = tuple(round(0.1 * i, 1) for i in range(11))          # 0.0 .. 1.0
W_GRID = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)                          # w_beta
THETA_GRID = tuple(round(0.2 * i, 1) for i in range(1, 10))      # 0.2 .. 1.8


def local_score(situations, which, bias, cut) -> float:
    """An island's LOCAL balanced accuracy at `bias`: does its judgment
    (`opinion >= 0.5`) match its own label (`signal > cut`)?"""
    alphas, betas = opinions(situations, bias, bias)
    values = alphas if which == "alpha" else betas
    signals = [x1 if which == "alpha" else x2 for x1, x2 in situations]
    preds = [1 if v >= 0.5 else 0 for v in values]
    labels = [_local_class(s, cut) for s in signals]
    return balanced(preds, labels)


def inner_tune(situations, which, cut, grid=BIAS_GRID):
    """Stage 1: the island's own best knob on its own task. Ties keep the
    smaller bias, deterministically."""
    best = None
    for bias in grid:
        score = local_score(situations, which, bias, cut)
        if best is None or score > best[0]:
            best = (score, bias)
    return best[1]


def global_accuracy(situations, alpha_bias, beta_bias,
                    w_alpha, w_beta, theta) -> float:
    alphas, betas = opinions(situations, alpha_bias, beta_bias)
    labels = [global_truth(x1, x2) for x1, x2 in situations]
    return balanced(verdicts(alphas, betas, w_alpha, w_beta, theta), labels)


def outer_tune(situations, alpha_bias, beta_bias):
    """Stage 2: with the islands frozen, the bridge weights/threshold that
    maximize the GLOBAL objective. `w_alpha` is pinned to 1.0 (the gate is
    scale-invariant, so only the ratio matters)."""
    alphas, betas = opinions(situations, alpha_bias, beta_bias)
    labels = [global_truth(x1, x2) for x1, x2 in situations]
    best = None
    for w_beta in W_GRID:
        for theta in THETA_GRID:
            score = balanced(verdicts(alphas, betas, 1.0, w_beta, theta), labels)
            if best is None or score > best[0]:
                best = (score, (1.0, w_beta, theta))
    return best


def joint_tune(situations):
    """The ceiling: everything tuned at once (islands AND bridge)."""
    labels = [global_truth(x1, x2) for x1, x2 in situations]
    best = None
    for alpha_bias in BIAS_GRID:
        for beta_bias in BIAS_GRID:
            alphas, betas = opinions(situations, alpha_bias, beta_bias)
            for w_beta in W_GRID:
                for theta in THETA_GRID:
                    score = balanced(
                        verdicts(alphas, betas, 1.0, w_beta, theta), labels)
                    if best is None or score > best[0]:
                        best = (score, (alpha_bias, beta_bias, 1.0, w_beta, theta))
    return best


# -- the experiment ------------------------------------------------------

def _staged(cuts, situations):
    """The whole scheme on one pair of local cuts: inner-tune, freeze, then
    outer-tune the bridge against the global objective -- all on the SAME
    situations, so the number is the achieved objective, not a noisy
    held-out estimate (this probe measures REACH, not generalization)."""
    cut_a, cut_b = cuts
    bias_a = inner_tune(situations, "alpha", cut_a)
    bias_b = inner_tune(situations, "beta", cut_b)
    score, (w_a, w_b, theta) = outer_tune(situations, bias_a, bias_b)
    return {
        "frozen_biases": (bias_a, bias_b),
        "bridge": (w_a, w_b, theta),
        "global": score,
        "equal_weight": global_accuracy(situations, bias_a, bias_b, 1.0, 1.0, 1.0),
    }


def _calibration_bias(situations, gain, grid=BIAS_GRID):
    """The island tuned as a CALIBRATED reporter: minimize squared error
    between its opinion and the signal it is supposed to report. Unlike the
    threshold task, this objective CAN depend on the input distribution --
    but only when the mechanism is misspecified (gain != 1)."""
    best = None
    for bias in grid:
        error = sum((_opinion_gain(x1, bias, gain) - x1) ** 2
                    for x1, _x2 in situations) / len(situations)
        if best is None or error < best[0]:
            best = (error, bias)
    return best[1]


def distribution_shift(seed=5):
    """Does conditioning an island's training data on the region the
    composed decision reaches move its locally-tuned knob?

    Two local objectives over a uniform dataset and a conditioned one:

    - the THRESHOLD task (match `signal > cut`): the optimum is the label
      boundary whatever the input distribution -- no shift to remove. Its
      conditioning is kept loose (`x1 < 0.7`) on purpose: squeeze it to a
      region that excludes the boundary and the local labels go all-one-
      class and the objective becomes undefined, a fragility of
      conditioning worth seeing;
    - the CALIBRATION task (report the signal), conditioned hard
      (`x1 < 0.4`): invariant when the island mechanism is well-specified
      (gain 1), and only moves when it is MISSPECIFIED (gain 2).

    So the lever, when there is one, is the objective/mechanism -- not the
    dataset conditioning."""
    uniform = dataset(600, seed=seed)
    shifted = dataset(600, seed=seed + 1)
    near = tuple((x1, x2) for x1, x2 in shifted if x1 < 0.7)
    low = tuple((x1, x2) for x1, x2 in shifted if x1 < 0.4)
    return {
        "threshold_task": {
            "uniform": inner_tune(uniform, "alpha", ALIGNED_CUTS[0]),
            "conditioned": inner_tune(near, "alpha", ALIGNED_CUTS[0]),
        },
        "calibration_wellspecified": {
            "uniform": _calibration_bias(uniform, gain=1.0),
            "conditioned": _calibration_bias(low, gain=1.0),
        },
        "calibration_misspecified": {
            "uniform": _calibration_bias(uniform, gain=2.0),
            "conditioned": _calibration_bias(low, gain=2.0),
        },
    }


def report():
    """Every number Experiment 4 produces, in one dict: reach under aligned
    and misaligned local tasks, the freeze cost (fight) against the joint
    ceiling, and the distribution-shift reading."""
    situations = dataset(600, seed=1)
    aligned = _staged(ALIGNED_CUTS, situations)
    misaligned = _staged(MISALIGNED_CUTS, situations)
    joint = joint_tune(situations)[0]

    return {
        "aligned": aligned,
        "misaligned": misaligned,
        "joint": joint,
        "freeze_cost": {
            "aligned": joint - aligned["global"],
            "misaligned": joint - misaligned["global"],
        },
        "distribution_shift": distribution_shift(),
    }
