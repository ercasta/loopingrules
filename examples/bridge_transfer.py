"""`bridge_transfer` -- Experiment 1 from `docs/tuning.md`: does a shared
BRIDGE buy cross-island transfer, and how much of it is form versus value?

## The two islands and the one bridge

`examples.cards` and `examples.shopping` are two independent domains that
both project their own fact onto `loopingrules_patterns.judge`'s `Risk(level, reason)`
and both let the SAME `flag_too_risky` compare that `level` to the SAME
`RiskTolerance.max_level`. Cards means RESOURCE EXHAUSTION (how much of
the cash room a price would use); shopping means TIME PRESSURE (how close
a deadline is). Same bridge, different islands -- the exact geometry
`docs/tuning.md` calls islands-and-bridges.

## Form transfers for free; value does not (that is the hypothesis)

The theory says operators/form generalize and semantics/values do not. A
bridge is form: the rule and the component shape are literally the same
objects in both islands (`cards.Risk is shopping.Risk is judge.Risk`, and
so on), so reusing them costs zero new rules and zero new data. A threshold
is a VALUE, and a value is a policy -- "how much risk is acceptable" --
which is island semantics. So the sharp, testable claim is:

    the bridge transfers the SHAPE at zero cost, and transfers the
    THRESHOLD only to the extent the two islands' policies already agree.

This module measures both, using the real domains rather than synthetic
numbers: `replay` runs each domain and the harvested points are the
`Risk.level`s the domains actually project.

## Why not "bridge vs. raw features"

`docs/tuning.md`'s first sketch compared a bridge threshold against a
threshold on raw island features. For these two domains that comparison is
degenerate, and honestly so: each island's `Risk.level` IS its normalized
raw feature (cards: `price/room`; shopping: `1 - days/HORIZON`). A
threshold on the bridge and a threshold on the raw ratio are the same
decision boundary. What is NOT degenerate is the form/value split above,
and the fact that the raw axes do not intersect at all (`raw_axes`) --
which is what makes the bridge, rather than the raw features, the thing
that makes cross-island application possible in the first place.

## Ground truth is authored, on purpose

The labels are defined by an explicit policy on the bridge level
(`level > tau`), one `tau` per island, written into the module rather than
hidden in a data file. That is the auditable part: the experiment measures
whether a threshold fit on one island reproduces the other island's
policy, as a function of how far apart the two `tau`s are. It cannot
measure which `tau` is "right" -- there is no ground truth above the
policy, and pretending otherwise would be the wrong conclusion this repo
refuses everywhere else.
"""

from __future__ import annotations

import random

from examples import cards, shopping
from loopingrules_calibration import Scenario, replay
from loopingrules_patterns import judge


TAU_CARDS = 0.6        # cards' authored policy: flag iff level > 0.6
TAU_SHOPPING = 0.6     # shopping's authored policy, equal by default


# -- harvesting the real projections ------------------------------------

def _labelled(world, kind, tau):
    """Every entity of `kind` carrying a `judge.Risk`, as
    `(level, label)` -- the label being the authored policy `level > tau`.
    Entities with no `Risk` (e.g. a shopping item with no deadline) are
    skipped, not labelled `0`: an island that abstains has not made a
    claim to score, the same refuse-rather-than-guess line the domains
    themselves hold."""
    out = []
    for entity, _component in world.each(kind):
        risk = world.get(entity, judge.Risk)
        if risk is None:
            continue
        out.append((risk.level, 1 if risk.level > tau else 0))
    return out


def cards_points(tau=TAU_CARDS, prices=tuple(range(5, 105, 5)), cash=100):
    """Cards' own `Risk.level`s. `dragon` is listed at each price against a
    `cash`-sized room, so `level` runs `price/room` from `0.05` to `1.0`.
    No `want` line is said, so nothing is bought and every listing stays
    put, carrying the `Risk` `tag_risk_level` recomputed for it."""
    scenario = Scenario(kwargs=(("cash", cash),),
                        lines=tuple("list dragon %d" % price for price in prices))
    return _labelled(replay(scenario, cards.install).world, cards.Listing, tau)


def shopping_points(tau=TAU_SHOPPING, days=tuple(range(0, 8))):
    """Shopping's own `Risk.level`s. One item per deadline (a second
    `needby` for the same item would REPLACE the first, so each deadline
    gets its own settle): `level` runs `1 - days/HORIZON` from `1.0` down
    to `0.0` across the horizon."""
    out = []
    for days_left in days:
        world = replay(Scenario(lines=("needby milk %d" % days_left,)),
                       shopping.install).world
        out.extend(_labelled(world, shopping.Item, tau))
    return out


# -- fitting and scoring a single threshold on the bridge ---------------

def fit_threshold(points):
    """The threshold `t` minimizing `(level > t) != label` over `points`.

    One knob, so the optimum is exact rather than searched: only the
    midpoints between distinct levels (plus just outside each end) can
    change an error count. Ties keep the SMALLEST threshold -- refuse to
    guess between two thresholds with the same error, pick the
    conservative one (flag less), the same discipline `decide.pick_winner`
    applies to a tie for the top score.
    """
    if not points:
        raise ValueError("no points to fit")
    levels = sorted({level for level, _label in points})
    candidates = [levels[0] - 1e-6]
    candidates += [(a + b) / 2 for a, b in zip(levels, levels[1:])]
    candidates.append(levels[-1] + 1e-6)
    best = None
    for threshold in candidates:
        errors = sum(1 for level, label in points if (level > threshold) != bool(label))
        if best is None or errors < best[0]:
            best = (errors, threshold)
    return best[1]


def accuracy(points, threshold):
    """The fraction of `points` the threshold classifies correctly."""
    if not points:
        raise ValueError("no points to score")
    hits = sum(1 for level, label in points if (level > threshold) == bool(label))
    return hits / len(points)


# -- the experiment -----------------------------------------------------

def form_reuse():
    """The bridge's FORM, and what reusing it costs.

    Every name is the SAME object, not a same-shaped copy: both islands
    import them from `loopingrules_patterns.judge` unchanged (each pins that with a test
    of its own). That identity is why `new_rules_or_data` is `0` -- the
    shape was bought once and is used twice, and no example was needed to
    make it transfer.
    """
    return {
        "same_judge": cards.flag_too_risky is judge.flag_too_risky
                      and shopping.flag_too_risky is judge.flag_too_risky,
        "same_risk_shape": cards.Risk is judge.Risk is shopping.Risk,
        "same_tolerance_shape": (cards.RiskTolerance is judge.RiskTolerance
                                 and shopping.RiskTolerance is judge.RiskTolerance),
        "same_flag_shape": cards.TooRisky is judge.TooRisky is shopping.TooRisky,
        "new_rules_or_data": 0,
    }


def value_transfer(deltas=(-0.4, -0.3, -0.2, -0.1, 0.0,
                           0.1, 0.2, 0.3, 0.4)):
    """Fit ONE threshold on cards' labelled points, then score it against
    shopping's points for a shopping policy `TAU_CARDS + delta`.

    `delta == 0` is the two islands agreeing; `|delta|` is how far their
    policies diverge. Returns `(fitted_threshold, [(delta, accuracy), ...])`.
    The prediction: accuracy `1.0` at `delta == 0`, falling as `|delta|`
    grows -- one value cannot serve two policies that disagree.
    """
    threshold = fit_threshold(cards_points(tau=TAU_CARDS))
    rows = []
    for delta in deltas:
        test = shopping_points(tau=TAU_CARDS + delta)
        rows.append((delta, accuracy(test, threshold)))
    return threshold, rows


def learning_curve(sizes=(1, 2, 3, 5, 8, 13, 21), repeats=200, tau=TAU_CARDS,
                   seed=0):
    """How many labelled cards examples it takes to recover the bridge
    threshold. For each `N`, draw `N` points from cards' own pool
    (with replacement), fit, and score against the whole pool; report the
    mean accuracy over `repeats` draws. Seeded, so the curve is
    reproducible. Returns `[(N, mean_accuracy), ...]`.

    The bridge model is ONE parameter, so this is the easy end: the honest
    number is small. It exists so the other experiments have a baseline,
    and so its shape (a step up, then flat) is visible rather than
    assumed."""
    pool = cards_points(tau=tau)
    rng = random.Random(seed)
    rows = []
    for size in sizes:
        scores = []
        for _ in range(repeats):
            sample = [pool[rng.randrange(len(pool))] for _ in range(size)]
            scores.append(accuracy(pool, fit_threshold(sample)))
        rows.append((size, sum(scores) / len(scores)))
    return rows


def raw_axes():
    """The raw, island-specific axes each domain would have to expose
    WITHOUT the bridge -- and their intersection.

    Empty intersection is the point: there is no shared axis to transfer a
    raw-feature rule along, which is what makes the bridge (a shared,
    monotone `[0, 1]` scalar) the thing that makes cross-island
    application possible at all, rather than merely convenient.
    """
    return {"cards": ("price", "room"), "shopping": ("days",), "shared": ()}


def report():
    """Every number Experiment 1 produces, in one dict, for a caller that
    wants to print or assert on all of it at once."""
    threshold, transfer = value_transfer()
    return {
        "form_reuse": form_reuse(),
        "fitted_threshold_from_cards": threshold,
        "value_transfer": transfer,
        "learning_curve": learning_curve(),
        "raw_axes": raw_axes(),
    }
