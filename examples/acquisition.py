"""`acquisition` -- Experiment 3 from `docs/tuning.md`: the novelty crux.
Does acquiring a genuinely NEW behaviour cost the authored system a couple
of rules and a knob, and the de novo learner more labels -- and can the
latter even represent the new decision without a new projection?

## The behaviour, and why it is genuinely absent from the base

`examples.cards` deliberately cannot sell -- `README.md` calls it a named,
load-bearing gap and `TODO.md` repeats it. The new behaviour is
`examples.market`'s SELL side: an `Offer(card, price)` for a held card,
`tag_surplus` (`Surplus` iff `price >= value*(1 + sell_premium)`), and
`decide_sell`'s held-`>=1` gate. The base system carries none of it, so the
acquisition is real rather than a relabelling.

## Two ways to acquire it

- **authored** -- add a couple of rules (`tag_surplus`, plus the held-gate
  `decide_sell` already carries) and one knob (`Policy.sell_premium`).
  Perfect at `N = 0`, by construction, and named as such, not dressed up.
- **de novo** -- a flat axis-aligned tree over the SAME raw facts the
  domain reads (`offer`, `value`, `held`, `premium`), never the `Surplus`
  tag. It must DISCOVER the composed decision: a comparison against a
  PRODUCT (`offer >= value*(1+premium)`) conjoined with an axis condition
  (`held >= 1`). The product is the relational family `ablation.
  RELATIONAL_CONDITIONS` already names (`price > 1.25 * value`), which an
  axis-aligned split can only staircase -- so the question is whether the
  learner reaches the tag's accuracy at all, or needs the projection.

## The imitation-cost framing, unchanged from Experiment 2

The target is the authored verdict (computed on a scoring-only loop, so
nothing is actually sold), the learner is one honest baseline, and the
authored arm is perfect at `N = 0` by construction. The measurable question
is the DATA cost of discovering the composition and whether the new
decision is reachable without the projection -- not whether authored
structure "wins," which would be true by definition.

## What this found

Authored acquisition is a couple of rules and a knob, zero labels -- the
column the learner is judged against. Against it:

- **The projection is worth ~4x at the 0.9 line, ~8x at 0.95.** The tag
  representation reaches `0.9` balanced accuracy at `N = 16` and saturates
  at `1.0` by `N = 32`; the primitive one needs `N = 64` for `0.9` and
  only reaches `~0.95` at `N = 128`.
- **But it is representable without the projection -- at a price.** Pushed
  to `N = 1024` the primitive curve climbs to `~0.99`, never quite closing
  on the tag's `1.0`: a DATA cost (the relational staircase can be refined
  indefinitely), not an impossibility. So on THIS behaviour the de novo
  camp's objection survives in the weak form ("more data buys it") while
  the theory holds in the strong form ("structure buys the data, and the
  residual never fully closes").
- **It confirms the relational reading where `market` did not.** Unlike
  Experiment 2's `market` non-result (its extra condition rarely bound),
  the sell verdict's condition is a comparison against a PRODUCT
  (`offer >= value*(1+premium)`) -- the family the depth dial showed
  structure pays for -- and the gap is real at small `N` (`~0.16` at
  `N = 8`).

A structural wrinkle the build surfaced, named rather than smoothed over:
where Experiment 2's buy verdict is ALL attached tags, the sell verdict is
a projection (`Surplus`) PLUS an inline guard (`held >= 1`) that
`decide_sell` never reifies. A structure control carrying only `Surplus`
under-specified the target and scored BELOW primitive (`~0.79` vs `~0.95`);
the fair control carries both constituents (`Surplus`, `Stock`). The lesson
is that "the authored tags" is not automatically the authored DECISION --
inline control flow is part of the structure and must be reified to be
measured.
"""

from __future__ import annotations

import random

from examples import ablation, cards, market
from loopingrules.loop import Loop


# The new behaviour's raw facts, drawn from market's own value scale. The
# knob (`premium`) is a raw fact the domain reads -- kept in the primitive
# features on purpose, so the learner is not handicapped by withholding it.
_SELL_DOMAIN = dict(
    value=(5, 8, 35, 40, 100),
    held=(0, 1, 2),
    offer=tuple(range(5, 155, 5)),
    premium=(0.0, 0.25, 0.5),
)


def _sell_sample(value, held, offer, premium=0.25):
    """One scoring-only world exposing the SELL tags, and the authored
    verdict `(primitive, tags, label)` for it -- mirroring `ablation.
    _market_sample`'s observation-without-acting discipline. `label` is
    what `decide_sell` would do: the offer is `Surplus` AND the agent
    actually holds a copy (`held >= 1`).

    The `tags` dict carries the FULL authored decision, which here is two
    constituents, not one: `Surplus`, the tag `tag_surplus` attaches, and
    `Stock`, the `held >= 1` guard `decide_sell` computes INLINE rather
    than reifying. Documented because it differs from Experiment 2, where
    every constituent of the buy verdict is an attached tag (`Wanted`/
    `Affordable`/`FairPriced`/`TooRisky`) -- the sell decision is
    projection-plus-guard, and a structure control must carry both or it
    under-specifies the target."""
    loop = Loop()
    loop.rule(market.tag_surplus)
    w = loop.world
    card = w.spawn(market.Card("x", value), market.Held(held))
    w.spawn(market.Policy(max_price_ratio=0.25, min_reserve=0,
                          sell_premium=premium))
    offer_entity = w.spawn(market.Offer(card, offer))
    loop.run()
    primitive = {"offer": offer, "value": value, "held": held,
                 "premium": premium}
    tags = {"Surplus": w.has(offer_entity, market.Surplus),
            "Stock": held >= 1}
    label = tags["Surplus"] and tags["Stock"]
    return primitive, tags, label


def sell_dataset(count, seed=0):
    """`count` `(primitive, tags, label)` samples drawn from `_SELL_DOMAIN`,
    reproducibly for a seed -- the exact shape `ablation.dataset` returns."""
    rng = random.Random(seed)
    samples = []
    while len(samples) < count:
        draw = {name: rng.choice(values) for name, values in _SELL_DOMAIN.items()}
        samples.append(_sell_sample(**draw))
    return samples


# -- the experiment ------------------------------------------------------

def authored_cost():
    """The authored system's price for the new behaviour: a couple of rules
    and one knob, no labels -- perfect at `N = 0` by construction. The
    column the de novo learner is measured against."""
    return {
        "rules": 2,               # tag_surplus + decide_sell's held-gate
        "knobs": 1,               # Policy.sell_premium
        "labels": 0,              # by construction, not learned
        "base_has_it": hasattr(cards, "tag_surplus"),
    }


def acquisition(sizes=(1, 2, 4, 8, 16, 32, 64, 128), repeats=20,
                pool_size=4000, test_size=800):
    """The learning curve for the new behaviour, primitive (raw facts, no
    projection) vs structure (the `Surplus` tag), on balanced held-out data
    -- exactly Experiment 2's harness, run on the SELL verdict."""
    pool = ablation.balanced(sell_dataset(pool_size, seed=1), seed=3)
    test = ablation.balanced(sell_dataset(test_size, seed=2), seed=4)
    return {
        "sizes": sizes,
        "primitive": ablation.curve(pool, test, "primitive", sizes, repeats),
        "structure": ablation.curve(pool, test, "tags", sizes, repeats),
    }


def _n_to(curve, target):
    """The smallest training size in `curve` whose mean held-out balanced
    accuracy reaches `target`, or `None` if the curve never gets there."""
    for size, value in curve:
        if value >= target:
            return size
    return None


def novelty(result=None, tolerance=0.05, target=0.9):
    """The crux reading: how much data each representation needs to reach
    `target` balanced accuracy, and whether the primitive one (no
    projection) has closed the gap to the tag at the largest budget
    tested.

    `n_to_primitive` vs `n_to_structure` is the "more labels" number
    `docs/tuning.md` asks for; `gaps` is where the cost bites, per size.
    `reaches_the_tag` True means the new decision is representable from
    raw facts alone at that budget (at a price in data); False means the
    projection -- the `Surplus` tag -- is what buys it."""
    result = acquisition() if result is None else result
    primitive = dict(result["primitive"])
    structure = dict(result["structure"])
    largest = result["sizes"][-1]
    gaps = {size: round(structure[size] - primitive[size], 6)
            for size in result["sizes"]}
    return {
        "target": target,
        "n_to_primitive": _n_to(result["primitive"], target),
        "n_to_structure": _n_to(result["structure"], target),
        "primitive_at_largest_N": primitive[largest],
        "structure_at_largest_N": structure[largest],
        "gap_at_largest_N": structure[largest] - primitive[largest],
        "gaps": gaps,
        "reaches_the_tag": (structure[largest] - primitive[largest]) <= tolerance,
    }


def converge(sizes=(128, 256, 512, 1024), repeats=10,
             pool_size=6000, test_size=1200):
    """The representability probe: as the budget grows well past where the
    tag has long saturated, does the primitive representation CLOSE the
    gap to it, or plateau below? A closing gap is a data cost; a plateau
    is representability. Returns `(sizes, rows)`, each row
    `(size, primitive, structure)` at one large budget."""
    pool = ablation.balanced(sell_dataset(pool_size, seed=11), seed=13)
    test = ablation.balanced(sell_dataset(test_size, seed=12), seed=14)
    primitive = dict(ablation.curve(pool, test, "primitive", sizes, repeats))
    structure = dict(ablation.curve(pool, test, "tags", sizes, repeats))
    return sizes, tuple((size, primitive[size], structure[size])
                        for size in sizes)


def report():
    """Every number Experiment 3 produces, in one dict: the authored price,
    both curves, the novelty reading, and the large-budget convergence
    probe."""
    result = acquisition()
    return {
        "authored_cost": authored_cost(),
        "curve": result,
        "novelty": novelty(result),
        "converge": converge(),
    }
