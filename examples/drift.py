"""`drift` -- Experiment 8: does slow-timescale adaptation (D4/Phase 4) track a
world that MOVES, using the same checks the offline tuner used?

## The scheme under test

`docs/plan-adaptation.md` says the slow timescale "Run -> observe the
completed trace -> adjust knobs -> next run" is incremental re-calibration,
and locks the seam: the checks that tune offline are the *same* checks a
controller consumes. This probe measures whether that actually helps when the
environment drifts.

## The model, spelled out

A one-knob threshold classifier -- the shape `judge.flag_too_risky` already
is (`docs/tuning.md`: single-threshold operating-point selection):

- each episode offers `Signal(x)` examples with a ground-truth `Label`: it is
  correct to CHOOSE an example iff `x >= target`, where `target` is HIDDEN and
  the environment's own;
- the rule `choose` attaches a transient `Choice` iff `x >= Policy.cut` --
  one tunable knob, `Policy.cut`;
- the check `agreement` is the fraction of examples the choice gets right; the
  objective is `total(agreement, settles)`.

The environment drifts: `target` ramps from `0.3` to `0.7` across the stream,
so the best `cut` moves with it. Nothing about the domain "knows" the target;
only the labels do, and only the check reads them.

## The measurements

1. **Frozen degrades.** Offline-tune `cut` on the first few episodes (all
   near `0.3`), freeze it, and score the rest of the stream. Its agreement
   falls as the target walks away -- the cost of not adapting.
2. **Adaptive tracks.** The slow adapter (`loopingrules_calibration.adapt`),
   starting from that frozen baseline, keeps agreement high -- and its final
   `cut` lands near the final target.
3. **It settles.** On a STATIONARY stream, started from a wrong value, the
   adapter moves a bounded number of times and then stops -- no churn.
4. **The guard works.** A rate limit (`Adapter.every`) trades a few points of
   tail agreement for materially fewer adjustments -- the D4 knob.

## What this does not settle

This is a CONTROLLED probe (the target is a known ramp; labels are generated,
not elicited), so it measures the MECHANISM, not a natural domain. It does not
touch the fast timescale (a rule writing a knob mid-run, Phase 7, where
oscillation lives) and it does not test multi-knob coupling or pull-back.
"""

from __future__ import annotations

import random

from loopingrules.loop import Loop

from loopingrules_calibration import (
    Adapter,
    Knob,
    Scenario,
    adapt,
    check,
    knobs as collect_knobs,
    replay,
    runtime_knobs,
    search,
    settles,
    total,
    tunable,
)


# -- the rule world ------------------------------------------------------
# Under the attribute substrate (D8): a `signal` entity carries `x` and its
# ground-truth `label`; `choice` is a flag; the policy is a singleton `cut`.

@tunable(Knob("cut", 0.0, 1.0, steps=11, scope="runtime"))
def choose(w) -> None:
    """Choose everything at or above the singleton `cut`. The one knob is
    READ, never hard-coded, so the linter is quiet and the surface is real."""
    policy = w.first("cut")
    if policy is None:
        return
    ceiling = policy[1]
    for entity, _t, x in w.each("signal", "x"):
        if x >= ceiling:
            w.mark(entity, "choice")
        else:
            w.unmark(entity, "choice")


# -- the check: ONE object, used offline and online ----------------------

@check("agreement")
def agreement(trace) -> float:
    """Fraction of examples whose `Choice` matches its `Label` -- the black-box
    pole (D2 (a)), read off the settled world. This is the term the objective
    is dominated by, and the SAME object the adapter's scorer is built from."""
    world = trace.world
    rows = list(world.each("signal", "label"))
    if not rows:
        return 0.0
    correct = sum(1 for entity, _t, label in rows
                  if world.has(entity, "choice") == bool(label))
    return correct / len(rows)


CHECKS = (agreement, settles(weight=0.05))
SCORER = total(*CHECKS)


# -- the domain: an episode is (target, seed) in the scenario kwargs -----

SAMPLES = 200


def episode_data(target, seed):
    rng = random.Random(seed)
    out = []
    for _ in range(SAMPLES):
        x = rng.random()
        out.append((x, int(x >= target)))
    return tuple(out)


def install(loop, target=0.5, seed=0, samples=SAMPLES) -> None:
    """Register the rule and seed ONE episode: `samples` labelled examples for
    `target`, plus the `Policy` singleton (its default is overwritten by any
    knob values a replay writes)."""
    loop.rule(choose)
    world = loop.world
    for x, chosen in episode_data(target, seed):
        entity = world.spawn()
        world.mark(entity, "signal")
        world.set(entity, "x", x)
        world.set(entity, "label", chosen)
    policy = world.spawn()
    world.set(policy, "cut", 0.5)


def stream(count=24, start=0.30, end=0.70, seed=7):
    """Episodes whose hidden target RAMPS `start -> end`; the seed moves too,
    so the examples are redrawn each episode (drift, not a re-labelling)."""
    out = []
    for i in range(count):
        frac = i / (count - 1) if count > 1 else 0.0
        target = round(start + (end - start) * frac, 3)
        out.append(Scenario(kwargs=(("target", target), ("seed", seed + i))))
    return tuple(out)


def stationary(count=12, target=0.6, seed=21):
    return tuple(Scenario(kwargs=(("target", target), ("seed", seed + i)))
                 for i in range(count))


def runtime_surface():
    """The knobs a controller may move, collected from the rule that reads
    them -- `scope="runtime"` only (D3/D4)."""
    loop = Loop()
    install(loop)
    return runtime_knobs(collect_knobs(loop))


KNOBS = runtime_surface()


# -- the measurements ----------------------------------------------------

def frozen_values(episodes, train=4):
    """Offline-tune on the first `train` episodes, then it is frozen."""
    return search(install, tuple(episodes[:train]), KNOBS, SCORER).values


def scores_at(episodes, values):
    return tuple(SCORER(replay(ep, install, KNOBS, values)) for ep in episodes)


def mean(values):
    values = tuple(values)
    return sum(values) / len(values) if values else 0.0


def final_cut(values):
    """The `cut` value in a `KNOBS`-ordered tuple (the only knob here)."""
    return values[0] if values else None


def report(train=4, count=24):
    episodes = stream(count=count)
    frozen = frozen_values(episodes, train=train)
    adapter = Adapter(knobs=KNOBS, checks=CHECKS, margin=0.0, every=1,
                      window=2)
    adapted, steps = adapt(episodes, install, adapter, start=frozen)

    frozen_scores = scores_at(episodes, frozen)
    adaptive_scores = tuple(step.score for step in steps)
    tail = slice(count // 2, count)         # the drifted second half

    # settling: a stationary world, started from a WRONG cut.
    still = stationary()
    _, still_steps = adapt(still, install,
                           Adapter(knobs=KNOBS, checks=CHECKS, window=2),
                           start=(0.1,))
    still_moves = sum(1 for step in still_steps if step.moved)
    still_final = still_steps[-1].values[0] if still_steps else None

    # the rate limit trades tail score for fewer adjustments.
    slow_steps = adapt(episodes, install,
                       Adapter(knobs=KNOBS, checks=CHECKS, window=2, every=12),
                       start=frozen)[1]
    fast_moves = sum(1 for step in steps if step.moved)
    slow_moves = sum(1 for step in slow_steps if step.moved)

    return {
        "frozen": frozen,
        "adapted": adapted,
        "frozen_tail": mean(frozen_scores[tail]),
        "adaptive_tail": mean(adaptive_scores[tail]),
        "final_target": 0.70,
        "frozen_cut": final_cut(frozen),
        "adaptive_cut": final_cut(adapted),
        "still_moves": still_moves,
        "still_final": still_final,
        "fast_moves": fast_moves,
        "slow_moves": slow_moves,
        "slow_tail": mean(step.score for step in slow_steps[tail]),
    }


def main():
    r = report()
    print("== Drift: slow-timescale adaptation ==")
    print("  frozen  tail %.3f  (cut %s)" % (r["frozen_tail"], r["frozen_cut"]))
    print("  adapted tail %.3f  (cut %s, target %s)"
          % (r["adaptive_tail"], r["adaptive_cut"], r["final_target"]))
    print("  stationary: %d moves, final cut %s (started wrong at 0.1)"
          % (r["still_moves"], r["still_final"]))
    print("  rate limit: moves %d -> %d, tail %.3f"
          % (r["fast_moves"], r["slow_moves"], r["slow_tail"]))
    checks = [
        ("frozen degrades under drift", r["frozen_tail"] < r["adaptive_tail"]),
        ("adapted tracks the target",
         abs(r["adaptive_cut"] - r["final_target"]) <= 0.15),
        ("a stationary world settles (<=2 moves)", r["still_moves"] <= 2),
        ("a rate limit reduces adjustments", r["slow_moves"] < r["fast_moves"]),
    ]
    for label, ok in checks:
        print("  [%s] %s" % ("ok" if ok else "XX", label))
    print("  ALL AS EXPECTED:", all(ok for _l, ok in checks))
    return 0 if all(ok for _l, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
