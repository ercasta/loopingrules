"""`ablation` -- Experiment 2 from `docs/tuning.md`: how much DATA does it
take to recover, from a flat representation, the decision an authored
structure expresses for free?

## The honest framing (and the trap it avoids)

"Authored structure is more sample-efficient than a generic learner" is
true by construction if you define the target as the authored system -- so
stating it that way proves nothing. What this module measures instead is
the **imitation cost of the structure**: the target is the authored buy
verdict (`observe` computes it on a scoring-only loop, with the acting
rules left out so nothing is bought), and the learner is a plain
axis-aligned decision tree given the SAME raw facts the domain reads --
never the tags. The question is not "can it represent the answer" but
"how many labelled listings does it need to DISCOVER the composition the
rules already spell out."

Three representations, same target, same data budget:

- **primitive** -- raw fields only (`price`, `value`, `held`, `qty`,
  `cash`, `reserve`, and for `market` the other card's facts). Axis-aligned
  splits cannot express a cross-feature comparison (`other_priority >
  priority`) or a threshold on a difference (`price > cash - needed`)
  without a staircase, so these cost data.
- **structure** -- the authored tags as features. The target becomes a
  short conjunction; a few examples suffice. This is the control that
  isolates the tags as the mechanism.
- **authored** -- the domain's own rules. Perfect at `N = 0`, by
  construction, and named as such rather than dressed up.

The slope across `cards` (rung 0) and `market` (rung 1) is the point:
`market`'s cross-entity `Strands` term is a relational condition a flat
tree can only approximate, so its imitation cost should exceed `cards`',
while the tag control stays cheap for both.

## What this does not settle

Whether the authored structure is the RIGHT one, or whether a better flat
feature set (a kernel, a relational learner) would close the gap -- a
decision tree is one honest baseline, not the strongest possible one. And
`cards`/`market` are small: a wide gap here is suggestive, not proof. See
`docs/tuning.md`'s Limits.
"""

from __future__ import annotations

import random

from examples import cards, decide, judge, market, quorum, trip
from loopingrules.loop import Loop


# -- observing the authored verdict, without acting ----------------------

def _cards_sample(cash, value, qty, held, price, premium=0.25, reserve=0):
    loop = Loop()
    for rule in (cards.tag_wanted, cards.tag_affordable, cards.tag_fair_priced,
                 cards.tag_risk_level, judge.flag_too_risky):
        loop.rule(rule)
    w = loop.world
    card = w.spawn(cards.CardDef("x", "rare", value), cards.Copies(held))
    if qty:
        w.attach(card, cards.Wants(qty))
    w.spawn(cards.Purse(cash))
    w.spawn(cards.RiskProfile(max_spend_per_trade=10 ** 9,
                              min_cash_reserve=reserve, max_premium=premium))
    w.spawn(judge.RiskTolerance(0.8))
    listing = w.spawn(cards.Listing(card, price))
    loop.run()
    primitive = {"price": price, "value": value, "held": held,
                 "qty": qty, "cash": cash, "reserve": reserve}
    tags = {"Wanted": w.has(listing, cards.Wanted),
            "Affordable": w.has(listing, cards.Affordable),
            "FairPriced": w.has(listing, cards.FairPriced),
            "TooRisky": w.has(listing, judge.TooRisky)}
    label = (tags["Wanted"] and tags["Affordable"] and tags["FairPriced"]
             and not tags["TooRisky"])
    return primitive, tags, label


def _market_sample(cash, value, qty, held, price, priority, price_rival,
                   other_value, other_qty, other_held, other_priority,
                   premium=0.25, reserve=0):
    """One market world, TWO rival listings for the same card, and one
    labelled sample per listing -- so the `decide` bridge's `Winner` can
    actually discriminate (a single listing always wins, which would make
    the ranking structure inert), and `Strands` is exercised by a second,
    possibly higher-priority want."""
    loop = Loop()
    for rule in (market.tag_wanted, market.tag_affordable, market.tag_fair_priced,
                 market.tag_risk, market.tag_strands, market.nominate,
                 judge.flag_too_risky, decide.pick_winner):
        loop.rule(rule)
    w = loop.world
    card = w.spawn(market.Card("target", value), market.Held(held))
    if qty:
        w.attach(card, market.Want(qty, priority))
    other = w.spawn(market.Card("other", other_value), market.Held(other_held))
    if other_qty:
        w.attach(other, market.Want(other_qty, other_priority))
    w.spawn(market.Cash(cash))
    w.spawn(market.Policy(premium, reserve, 0.25))
    w.spawn(judge.RiskTolerance(0.8))
    listings = {"a": w.spawn(market.Listing(card, price)),
                "b": w.spawn(market.Listing(card, price_rival))}
    loop.run()
    out = []
    for name, listing in listings.items():
        primitive = {"price": price if name == "a" else price_rival,
                     "value": value, "held": held, "qty": qty,
                     "priority": priority, "cash": cash, "reserve": reserve,
                     "rival_price": price_rival if name == "a" else price,
                     "other_value": other_value, "other_qty": other_qty,
                     "other_held": other_held, "other_priority": other_priority}
        tags = {"Wanted": w.has(listing, market.Wanted),
                "Affordable": w.has(listing, market.Affordable),
                "FairPriced": w.has(listing, market.FairPriced),
                "Winner": w.has(listing, decide.Winner),
                "TooRisky": w.has(listing, judge.TooRisky),
                "Strands": w.has(listing, market.Strands)}
        label = (tags["Wanted"] and tags["Affordable"] and tags["FairPriced"]
                 and tags["Winner"] and not tags["TooRisky"] and not tags["Strands"])
        out.append((primitive, tags, label))
    return out


_CARDS_DOMAIN = dict(
    cash=(30, 50, 100, 200), value=(5, 8, 35, 40, 100), qty=(0, 1, 2),
    held=(0, 1, 2), price=tuple(range(5, 155, 5)), premium=(0.0, 0.25, 0.5),
    reserve=(0, 20))

_MARKET_DOMAIN = dict(
    cash=(30, 50, 100, 200), value=(5, 8, 35, 40, 100), qty=(0, 1, 2),
    held=(0, 1, 2), price=tuple(range(5, 155, 10)),
    price_rival=tuple(range(5, 155, 10)), premium=(0.0, 0.25, 0.5),
    reserve=(0, 20), priority=(0, 1, 5, 10), other_value=(5, 40, 100),
    other_qty=(0, 1, 2), other_held=(0, 1), other_priority=(0, 1, 5, 10))


def _draw(rng, space):
    return {name: rng.choice(values) for name, values in space.items()}


def dataset(which, count, seed=0):
    """`count` `(primitive, tags, label)` samples for `"cards"` or
    `"market"`, drawn from that domain's own reproducible space. A market
    draw yields two samples (its two rival listings)."""
    rng = random.Random(seed)
    space = _CARDS_DOMAIN if which == "cards" else _MARKET_DOMAIN
    build = _cards_sample if which == "cards" else _market_sample
    samples = []
    while len(samples) < count:
        built = build(**_draw(rng, space))
        samples.extend(built if isinstance(built, list) else [built])
    return samples[:count]


# -- a minimal axis-aligned decision tree (stdlib only) ------------------

def _majority(samples):
    ones = sum(1 for _p, _t, label in samples if label)
    return 1 if ones * 2 >= len(samples) else 0


def _gini(samples):
    if not samples:
        return 0.0
    ones = sum(1 for _p, _t, label in samples if label)
    p = ones / len(samples)
    return 1 - p * p - (1 - p) * (1 - p)


def fit_tree(samples, feature, max_depth=6, min_leaf=2):
    """A decision tree over the chosen feature dict, recursive threshold
    splits, `feature` a `"primitive"` or `"tags"` key. Deterministic:
    features are tried in insertion order and ties keep the first split,
    so the same samples always give the same tree."""
    names = list(samples[0][0 if feature == "primitive" else 1])

    def build(rows, depth):
        label = _majority(rows)
        if depth == 0 or len(rows) < 2 * min_leaf or _gini(rows) == 0:
            return ("leaf", label)
        best = None
        for name in names:
            values = sorted({row[0 if feature == "primitive" else 1][name]
                             for row in rows})
            for low, high in zip(values, values[1:]):
                if low == high:
                    continue
                threshold = (low + high) / 2
                left = [r for r in rows
                        if r[0 if feature == "primitive" else 1][name] <= threshold]
                right = [r for r in rows
                         if r[0 if feature == "primitive" else 1][name] > threshold]
                if len(left) < min_leaf or len(right) < min_leaf:
                    continue
                impurity = (len(left) * _gini(left) + len(right) * _gini(right)) / len(rows)
                if best is None or impurity < best[0]:
                    best = (impurity, name, threshold, left, right)
        if best is None:
            return ("leaf", label)
        _impurity, name, threshold, left, right = best
        return ("split", name, threshold,
                build(left, depth - 1), build(right, depth - 1))

    return build(list(samples), max_depth)


def predict(tree, sample, feature):
    node = tree
    while node[0] == "split":
        _kind, name, threshold, left, right = node
        value = sample[0 if feature == "primitive" else 1][name]
        node = left if value <= threshold else right
    return node[1]


def accuracy(tree, samples, feature):
    if not samples:
        raise ValueError("no samples to score")
    hits = sum(1 for sample in samples
               if predict(tree, sample, feature) == sample[2])
    return hits / len(samples)


def balanced_accuracy(tree, samples, feature):
    """The mean of the true-positive and true-negative rates. The authored
    verdict is rare (a buy is a conjunction of conditions), so plain
    accuracy would sit on the majority class and hide the signal; balanced
    accuracy asks the honest question -- did it learn the POSITIVE
    decision, not just predict "don't buy" everywhere."""
    positive = [s for s in samples if s[2]]
    negative = [s for s in samples if not s[2]]
    if not positive or not negative:
        raise ValueError("balanced accuracy needs both classes")
    true_pos = sum(1 for s in positive if predict(tree, s, feature) == 1)
    true_neg = sum(1 for s in negative if predict(tree, s, feature) == 0)
    return (true_pos / len(positive) + true_neg / len(negative)) / 2


def balanced(samples, seed=0):
    """The same samples, subsampled to equal positives and negatives and
    shuffled -- so a learning curve measures the decision, not the base
    rate. Seeded, so it is reproducible."""
    positive = [s for s in samples if s[2]]
    negative = [s for s in samples if not s[2]]
    size = min(len(positive), len(negative))
    rng = random.Random(seed)
    rng.shuffle(positive)
    rng.shuffle(negative)
    out = positive[:size] + negative[:size]
    rng.shuffle(out)
    return out


# -- the learning curve --------------------------------------------------

def curve(samples, test, feature, sizes=(1, 2, 4, 8, 16, 32, 64, 128),
          repeats=20, seed=0, max_depth=6):
    """Mean held-out balanced accuracy vs number of training samples, for
    one representation. `sizes` are capped at `len(samples)`. Seeded, so
    the curve is reproducible."""
    rng = random.Random(seed)
    rows = []
    for size in sizes:
        size = min(size, len(samples))
        scores = []
        for _ in range(repeats):
            draw = [samples[rng.randrange(len(samples))] for _ in range(size)]
            scores.append(balanced_accuracy(fit_tree(draw, feature, max_depth),
                                            test, feature))
        rows.append((size, sum(scores) / len(scores)))
    return rows


def report(sizes=(1, 2, 4, 8, 16, 32, 64, 128), repeats=20):
    """Both domains, both representations. Each domain gets a balanced
    held-out test set and a balanced training pool -- so the curve measures
    how fast the decision is recovered, not the base rate."""
    out = {}
    for which in ("cards", "market"):
        pool = balanced(dataset(which, 4000, seed=1), seed=3)
        test = balanced(dataset(which, 800, seed=2), seed=4)
        out[which] = {
            "sizes": sizes,
            "primitive": curve(pool, test, "primitive", sizes, repeats),
            "structure": curve(pool, test, "tags", sizes, repeats),
        }
    return out


# -- earning the slope: a controlled depth dial --------------------------
#
# The domain-natural result (`report`) showed a ~10x data advantage but no
# WIDENING with `market`'s extra depth -- because the sampled distribution
# barely made the cross-entity condition decision-relevant. To earn the
# slope the composition has to be made deeper ON PURPOSE and the gap
# watched as it grows, with the feature vectors still drawn from the real
# domain. Two families isolate the mechanism:
#
#   axis       -- conditions on a SINGLE feature (`price > 50`), which one
#                 axis-aligned split expresses exactly.
#   relational -- conditions COMPARING features (`price > cash - reserve`,
#                 `other_priority > priority`), which an axis-aligned tree
#                 can only approximate with a staircase.
#
# If the authored-structure claim holds, the primitive gap should grow with
# DEPTH for the relational family (composition of relations is what the
# tags dissolve) while the tag representation stays flat.

AXIS_CONDITIONS = (
    ("price > 50", lambda f: f["price"] > 50),
    ("value > 20", lambda f: f["value"] > 20),
    ("cash > 100", lambda f: f["cash"] > 100),
    ("qty > 0", lambda f: f["qty"] > 0),
    ("held > 0", lambda f: f["held"] > 0),
)

RELATIONAL_CONDITIONS = (
    ("price > cash - reserve", lambda f: f["price"] > f["cash"] - f["reserve"]),
    ("price > 1.25 * value", lambda f: f["price"] > 1.25 * f["value"]),
    ("other_priority > priority", lambda f: f["other_priority"] > f["priority"]),
    ("held >= qty", lambda f: f["held"] >= f["qty"]),
    ("cash - price < 1.25 * other_value",
     lambda f: f["cash"] - f["price"] < 1.25 * f["other_value"]),
)


def _probe(vectors, conditions, depth):
    """Label each feature vector by the conjunction of the first `depth`
    conditions, and expose each condition's own truth as a tag feature --
    exactly the shape a domain's rules produce (`cx` is a tag, the label is
    the composed decision)."""
    out = []
    for vector in vectors:
        tags = {}
        label = True
        for index, (_name, condition) in enumerate(conditions[:depth]):
            truth = condition(vector)
            tags["c%d" % index] = truth
            label = label and truth
        out.append((vector, tags, label))
    return out


def slope(depths=(1, 2, 3, 4, 5), sizes=(16, 32, 64), vectors=6000,
          repeats=12, seed=5, max_depth=6):
    """For each family and each composition depth, the held-out balanced
    accuracy of the primitive representation vs the tag representation, at
    a fixed small data budget. The feature vectors are market's own
    observed primitives, so the only thing dialled is the DEPTH of the
    composed target. `max_depth` caps the flat learner's capacity -- a
    shallower tree cannot staircase a relational condition for free, which
    is the second half of the claim. Returns
    `{family: [(depth, [(size, primitive, structure), ...]), ...]}`."""
    pool = [primitive for primitive, _tags, _label in dataset("market", vectors, seed=seed)]
    split = int(len(pool) * 0.8)
    train_vectors, test_vectors = pool[:split], pool[split:]
    out = {}
    for family, conditions in (("axis", AXIS_CONDITIONS),
                               ("relational", RELATIONAL_CONDITIONS)):
        rows = []
        for depth in depths:
            train = balanced(_probe(train_vectors, conditions, depth), seed=11)
            test = balanced(_probe(test_vectors, conditions, depth), seed=12)
            primitive = dict(curve(train, test, "primitive", sizes, repeats,
                                   seed=0, max_depth=max_depth))
            structure = dict(curve(train, test, "tags", sizes, repeats,
                                   seed=0, max_depth=max_depth))
            rows.append((depth, [(size, primitive[size], structure[size])
                                 for size in sizes]))
        out[family] = rows
    return out


# -- generalizing: the slope on the REAL verdict -------------------------
#
# The controlled probe above dials a synthetic target. This dials the
# DOMAIN itself: `competitors` is how many other cards carry a competing
# want, and each one MAY or MAY NOT outrank the target's (its priority is
# the target's plus a drawn delta). So growing the competitor count grows
# the composition of the cross-entity condition without driving it
# degenerate, and the label stays the real authored verdict throughout.
#
# The parameterisation is deliberately market-natural rather than tuned to
# a result: a price derived from value (`price = value * m`), and cash just
# above it (`cash = price + slack`). That keeps the cross-entity condition's
# region (`reach`) from collapsing to nothing -- an agent whose cash
# barely covers a purchase is the ordinary case, not a contrived one.

_COMPETE_DOMAIN = dict(
    value=(5, 8, 35, 40, 100), m=(0.5, 0.8, 1.0, 1.2, 1.5),
    slack=(15, 30, 80), reserve=(0, 10), qty=(0, 1, 2), held=(0, 1, 2),
    priority=(0, 1, 5), premium=(0.0, 0.25, 0.5),
    comp_value_a=(5, 40, 100), comp_value_b=(5, 40, 100),
    comp_value_c=(5, 40, 100), comp_delta_a=(-1, 0, 1, 2),
    comp_delta_b=(-1, 0, 1, 2), comp_delta_c=(-1, 0, 1, 2))


def _market_compete(cash, value, price, qty, held, priority, comp_value_a,
                    comp_value_b, comp_value_c, comp_delta_a, comp_delta_b,
                    comp_delta_c, competitors, premium=0.25, reserve=0):
    """One market world with `competitors` competing wants (out of three
    fixed slots, so the primitive feature vector stays a fixed length), and
    one labelled sample -- the real authored verdict, cross-entity condition
    and all. Each active competitor's priority is the target's plus its own
    drawn `comp_delta_*`, so it MAY or MAY NOT outrank the target and strand
    the purchase. `price`/`cash` arrive already derived (see
    `_compete_inputs`): `cash = price + slack`."""
    loop = Loop()
    for rule in (market.tag_wanted, market.tag_affordable, market.tag_fair_priced,
                 market.tag_risk, market.tag_strands, judge.flag_too_risky):
        loop.rule(rule)
    w = loop.world
    card = w.spawn(market.Card("target", value), market.Held(held))
    if qty:
        w.attach(card, market.Want(qty, priority))
    primitive = {}
    for index, (comp_value, comp_delta) in enumerate(
            ((comp_value_a, comp_delta_a), (comp_value_b, comp_delta_b),
             (comp_value_c, comp_delta_c))):
        active = index < competitors
        entity = w.spawn(market.Card("comp%d" % index, comp_value), market.Held(0))
        if active:
            w.attach(entity, market.Want(1, priority + comp_delta))
        primitive["comp%d_value" % index] = comp_value
        primitive["comp%d_qty" % index] = 1 if active else 0
        primitive["comp%d_priority" % index] = (priority + comp_delta) if active else -1
    w.spawn(market.Cash(cash))
    w.spawn(market.Policy(premium, reserve, 0.25))
    w.spawn(judge.RiskTolerance(0.8))
    listing = w.spawn(market.Listing(card, price))
    loop.run()
    primitive.update({"price": price, "value": value, "held": held, "qty": qty,
                      "priority": priority, "cash": cash, "reserve": reserve})
    tags = {"Wanted": w.has(listing, market.Wanted),
            "Affordable": w.has(listing, market.Affordable),
            "FairPriced": w.has(listing, market.FairPriced),
            "TooRisky": w.has(listing, judge.TooRisky),
            "Strands": w.has(listing, market.Strands)}
    label = (tags["Wanted"] and tags["Affordable"] and tags["FairPriced"]
             and not tags["TooRisky"] and not tags["Strands"])
    return (primitive, tags, label)


def _compete_inputs(rng, competitors):
    """Draw one world's inputs from `_COMPETE_DOMAIN`, deriving the
    market-natural price and cash: `price = value * m`, `cash = price +
    slack`. `competitors` is set explicitly rather than drawn."""
    inputs = _draw(rng, _COMPETE_DOMAIN)
    price = int(round(inputs["value"] * inputs.pop("m")))
    inputs["price"] = price
    inputs["cash"] = price + inputs.pop("slack")
    inputs["competitors"] = competitors
    return inputs


def relevance(competitors=(1, 2, 3), size=32, vectors=4000, repeats=10,
              seed=6, conditional=False):
    """How the authored advantage moves with the number of competing wants,
    on the REAL verdict and over the NATURAL distribution.

    Two numbers say where the cross-entity condition lives: `reach`, the
    fraction of worlds where a listing is otherwise buyable at all (only
    there can `Strands` matter), and `binding`, the fraction of those the
    condition actually flips. With the market-natural parameterisation
    (`_compete_inputs`) `reach` is a healthy fraction and `binding` rises
    with the competitor count, so the aggregate curve is measured
    unconditionally. `conditional=True` restricts it to the governed region
    instead, for comparison.

    Returns `{competitors: {"reach", "binding", "size", "primitive",
    "structure"}}`."""
    out = {}
    for count in competitors:
        rng = random.Random(seed)
        samples = []
        while len(samples) < vectors:
            samples.append(_market_compete(**_compete_inputs(rng, count)))
        reachable = [s for s in samples
                     if s[1]["Wanted"] and s[1]["Affordable"] and s[1]["FairPriced"]
                     and not s[1]["TooRisky"]]
        reach = len(reachable) / len(samples)
        stranded = sum(1 for s in reachable if s[1]["Strands"])
        binding = stranded / len(reachable) if reachable else 0.0
        pool = balanced(reachable if conditional else samples, seed=13)
        effective = min(size, len(pool))
        primitive = curve(pool, pool, "primitive", (effective,), repeats, seed=0)[0][1]
        structure = curve(pool, pool, "tags", (effective,), repeats, seed=0)[0][1]
        out[count] = {"reach": reach, "binding": binding, "size": effective,
                      "primitive": primitive, "structure": structure}
    return out


# -- ladder rung: ranking (trip's decide bridge) -------------------------
#
# `market` composes a CONJUNCTION over rivals. `trip`'s bridge composes a
# RANKING: several rival itineraries for one request, one winner, chosen by
# `decide.pick_winner` on the negated cost+time score `trip` projects. A
# per-row flat learner can express the answer only by learning `own_score <
# every rival's score` -- comparisons AND the arithmetic of the score --
# while the `Winner` tag states it outright. The dial is the number of
# rivals, and the composition is a total order, not a conjunction.

_COST = (5, 10, 20, 40, 80)
_TIME = (10, 20, 40, 80)
_WEIGHT = (1.0, 0.7, 0.5, 0.3, 0.0)


def _ranking_sample(costs, times, weight_cost):
    """One `trip` request with rival `Complete` itineraries, projected by
    `trip.nominate_itinerary` and ranked by `decide.pick_winner`, and one
    labelled sample per rival -- the real ranking verdict."""
    loop = Loop()
    loop.rule(trip.nominate_itinerary)
    loop.rule(decide.pick_winner)
    w = loop.world
    request = w.spawn(trip.TripRequest(
        origin=0, destination=0, start_time=0, budget=10 ** 9, max_hops=9,
        weight_cost=weight_cost, weight_time=1.0 - weight_cost))
    frontiers = []
    for cost, time in zip(costs, times):
        entity = w.spawn(trip.Frontier(request=request.id, stop=0, time=time,
                                       cost=float(cost), hops=1, path=()))
        w.attach(entity, trip.Complete())
        frontiers.append(entity)
    loop.run()
    samples = []
    for index, entity in enumerate(frontiers):
        primitive = {"own_cost": costs[index], "own_time": times[index],
                     "weight_cost": weight_cost}
        others = [j for j in range(len(frontiers)) if j != index]
        for slot, other in enumerate(others):
            primitive["rival%d_cost" % slot] = costs[other]
            primitive["rival%d_time" % slot] = times[other]
        tags = {"Winner": w.has(entity, decide.Winner)}
        samples.append((primitive, tags, tags["Winner"]))
    return samples


def ranking(rivals=(2, 3, 4), size=32, vectors=2000, repeats=10, seed=7):
    """For each number of rival itineraries, the held-out balanced accuracy
    of primitive vs tag features on `trip`'s real ranking decision. Returns
    `{rivals: {"tie": float, "size": int, "primitive": float,
    "structure": float}}`; `tie` is the fraction of fields where no unique
    winner existed (`decide.pick_winner` refuses an exact tie)."""
    out = {}
    rng = random.Random(seed)
    for count in rivals:
        samples = []
        ties = 0
        while len(samples) < count * vectors:
            costs = [rng.choice(_COST) for _ in range(count)]
            times = [rng.choice(_TIME) for _ in range(count)]
            produced = _ranking_sample(costs, times, rng.choice(_WEIGHT))
            if not any(tags["Winner"] for _p, tags, _l in produced):
                ties += 1
            samples.extend(produced)
        pool = balanced(samples, seed=13)
        effective = min(size, len(pool))
        primitive = curve(pool, pool, "primitive", (effective,), repeats, seed=0)[0][1]
        structure = curve(pool, pool, "tags", (effective,), repeats, seed=0)[0][1]
        out[count] = {"tie": ties / max(vectors, 1), "size": effective,
                      "primitive": primitive, "structure": structure}
    return out


# -- ladder rung: counting (the `quorum` domain) -------------------------
#
# A conjunction composes over a fixed arity; a count composes over a set of
# unknown size. Here the verdict is `#{for votes} >= needed`, and a per-row
# learner is handed every vote's choice in fixed slots but never the count
# -- so it has to reconstruct a cardinality before it can compare. The dial
# is the number of votes, and the composition is a fold, not a conjunction.

def _counting_sample(choices, needed):
    """One `quorum` motion with these votes and threshold, and one labelled
    sample per vote -- the real authored verdict (does the motion pass)."""
    loop = Loop()
    quorum.install(loop, needed=needed)
    w = loop.world
    motion = w.spawn(quorum.Motion("m"))
    for choice in choices:
        w.spawn(quorum.Vote(motion.id, choice))
    loop.run()
    passed = w.has(motion, quorum.Passed)
    samples = []
    for index, choice in enumerate(choices):
        primitive = {"own": 1 if choice == "for" else 0, "needed": needed}
        others = [c for j, c in enumerate(choices) if j != index]
        for slot, other in enumerate(others):
            primitive["other%d" % slot] = 1 if other == "for" else 0
        tags = {"Passed": passed}
        samples.append((primitive, tags, passed))
    return samples


def counting(votes=(3, 5, 7), size=32, vectors=800, repeats=10, seed=8):
    """For each number of votes, the held-out balanced accuracy of
    primitive vs tag features on `quorum`'s real verdict. Returns
    `{votes: {"size": int, "primitive": float, "structure": float}}`."""
    out = {}
    for count in votes:
        rng = random.Random(seed)
        samples = []
        while len(samples) < count * vectors:
            needed = rng.randint(1, max(1, count - 1))
            choices = [rng.choice(("for", "against")) for _ in range(count)]
            samples.extend(_counting_sample(choices, needed))
        pool = balanced(samples, seed=13)
        effective = min(size, len(pool))
        primitive = curve(pool, pool, "primitive", (effective,), repeats, seed=0)[0][1]
        structure = curve(pool, pool, "tags", (effective,), repeats, seed=0)[0][1]
        out[count] = {"size": effective, "primitive": primitive,
                      "structure": structure}
    return out
