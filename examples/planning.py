"""`planning` -- Experiment 6: a finding that raises a CHOICE among next
questions, and tuning the investigation's thresholds against TRAJECTORY
examples.

Under the attribute substrate (D8): a `venue`/`choice`/`question`/`checked`/
`remedy` is a tagged entity; budget/forecast/tent/policy are singletons;
findings (`rain`/`clear`/`backup`/`tent_used`) are flags/an attribute on the
choice. The remedy candidates ride `examples.decide`'s `occasion`/`score`,
unmodified.
"""

from __future__ import annotations

import loopingrules_calibration as tuning
from examples.decide import pick_winner
from loopingrules.loop import Loop


# -- helpers -------------------------------------------------------------

def _pending_or_done(w, kind) -> bool:
    for _e, _t, k in w.each("question", "kind"):
        if k == kind:
            return True
    for _e, _t, k in w.each("checked", "kind"):
        if k == kind:
            return True
    return False


def _budget_spent(w) -> bool:
    policy = w.first("policy")
    max_checks = w.get(policy[0], "max_checks", 0) if policy else 0
    return len(w.each("checked")) >= max_checks


def _remedy_pending(w) -> bool:
    for _e, _t, k in w.each("question", "kind"):
        if k == "remedy":
            return True
    return False


def _has_candidate(w, choice_id, kind) -> bool:
    for entity, _t, rkind, candidate_id in w.each("remedy", "kind", "subject"):
        if rkind != kind:
            continue
        if w.get(entity, "occasion") == choice_id:
            return True
    return False


def _spawn_kind(w, tag, kind):
    entity = w.spawn()
    w.mark(entity, tag)
    w.set(entity, "kind", kind)
    return entity


# -- raising and answering, then the CHOICE point -----------------------

def raise_weather(w) -> None:
    if _pending_or_done(w, "weather") or _budget_spent(w):
        return
    for _e, _t, venue_id in w.each("choice", "venue"):
        if not w.get(venue_id, "indoor", False):
            _spawn_kind(w, "question", "weather")
            return


def answer_weather(w) -> None:
    policy = w.first("policy")
    threshold = w.get(policy[0], "rain_threshold", 0.0) if policy else 0.0
    forecast = w.first("forecast")
    rain = w.get(forecast[0], "rain", 0.0) if forecast else 0.0
    for entity, _t, kind in w.each("question", "kind"):
        if kind != "weather":
            continue
        w.destroy(entity)
        _spawn_kind(w, "checked", "weather")
        risky = rain > threshold
        for choice_entity, _ct in w.each("choice"):
            if risky:
                w.mark(choice_entity, "rain")
            else:
                w.mark(choice_entity, "clear")


def raise_remedy(w) -> None:
    """The finding (`rain`) raises a CHOICE of next question."""
    if _pending_or_done(w, "remedy") or _budget_spent(w):
        return
    for entity, _t in w.each("choice"):
        if w.has(entity, "rain"):
            _spawn_kind(w, "question", "remedy")
            return


def _propose(w, choice_entity, kind, subject, cost) -> None:
    remedy = w.spawn()
    w.mark(remedy, "remedy")
    w.set(remedy, "kind", kind)
    w.set(remedy, "subject", subject)
    w.set(remedy, "occasion", choice_entity.id)
    w.set(remedy, "score", float(-cost))


def propose_backup(w) -> None:
    if not _remedy_pending(w):
        return
    budget = w.first("budget")
    amount = w.get(budget[0], "amount", 0) if budget else 0
    for choice_entity, _ct in w.each("choice"):
        if not w.has(choice_entity, "rain") or _has_candidate(w, choice_entity.id,
                                                               "backup"):
            continue
        for venue_entity, _vt, indoor, cost in w.each("venue", "indoor", "cost"):
            if indoor and cost <= amount:
                _propose(w, choice_entity, "backup", venue_entity.id, cost)
                return


def propose_tent(w) -> None:
    if not _remedy_pending(w):
        return
    budget = w.first("budget")
    amount = w.get(budget[0], "amount", 0) if budget else 0
    tent = w.first("tent")
    if tent is None:
        return
    cost = w.get(tent[0], "cost")
    for choice_entity, _ct in w.each("choice"):
        if not w.has(choice_entity, "rain") or _has_candidate(w, choice_entity.id,
                                                               "tent"):
            continue
        if cost <= amount:
            _propose(w, choice_entity, "tent", cost, cost)
            return


def resolve_remedy(w) -> None:
    for entity, _t, kind in w.each("question", "kind"):
        if kind != "remedy":
            continue
        w.destroy(entity)
        _spawn_kind(w, "checked", "remedy")
        for choice_entity, _ct in w.each("choice"):
            chosen = None
            for candidate, _rt, rkind, subject in w.each("remedy", "kind",
                                                          "subject"):
                if (w.get(candidate, "occasion") == choice_entity.id
                        and w.has(candidate, "winner")):
                    chosen = (rkind, subject)
                    break
            if chosen is None:
                continue
            if chosen[0] == "backup":
                w.set(choice_entity, "backup", chosen[1])
            else:
                w.set(choice_entity, "tent_used", chosen[1])


# -- the decision --------------------------------------------------------

def finalize(w) -> None:
    if w.first("question") is not None:      # a NEGATED read
        return
    budget = w.first("budget")
    amount = w.get(budget[0], "amount", 0) if budget else 0
    for row in w.each("choice", "venue", without=("planned", "rejected")):
        entity, _t, venue_id = row
        if not w.has(venue_id, "indoor"):
            w.set(entity, "rejected", "no such venue")
            continue
        indoor = w.get(venue_id, "indoor")
        cost = w.get(venue_id, "cost")
        if cost > amount:
            w.set(entity, "rejected", "over budget")
            continue
        safe = (indoor or w.has(entity, "clear") or w.has(entity, "backup")
                or w.has(entity, "tent_used"))
        if safe:
            w.set(entity, "planned", venue_id)
        else:
            w.set(entity, "rejected", "weather not handled")


def is_valid(w) -> bool:
    """Ground truth, from the FACTS, independent of the policy."""
    budget = w.first("budget")
    amount = w.get(budget[0], "amount", 0) if budget else 0
    forecast = w.first("forecast")
    rain = w.get(forecast[0], "rain", 0.0) if forecast else 0.0
    for entity, _t in w.each("choice"):
        venue_id = w.get(entity, "venue")
        if not w.has(venue_id, "cost") or w.get(venue_id, "cost") > amount:
            return False
        if not w.get(venue_id, "indoor", False) and rain > 0.0:
            if not (w.has(entity, "backup") or w.has(entity, "tent_used")):
                return False
    return True


# -- wiring and the trajectory score ------------------------------------

def install(loop, venues=(("hall", 50, True), ("garden", 40, False)),
            choice="garden", rain=0.7, budget=100, tent=30,
            rain_threshold=0.5, max_checks=4) -> None:
    loop.rule(raise_weather)
    loop.rule(answer_weather)
    loop.rule(raise_remedy)
    loop.rule(propose_backup)
    loop.rule(propose_tent)
    loop.rule(pick_winner)
    loop.rule(resolve_remedy)
    loop.rule(finalize)
    world = loop.world
    venue_entities = {}
    for name, cost, indoor in venues:
        entity = world.spawn()
        world.mark(entity, "venue")
        world.set(entity, "name", name)
        world.set(entity, "cost", cost)
        world.set(entity, "indoor", indoor)
        venue_entities[name] = entity
    b = world.spawn()
    world.mark(b, "budget")
    world.set(b, "amount", budget)
    f = world.spawn()
    world.mark(f, "forecast")
    world.set(f, "rain", rain)
    t = world.spawn()
    world.mark(t, "tent")
    world.set(t, "cost", tent)
    p = world.spawn()
    world.mark(p, "policy")
    world.set(p, "rain_threshold", rain_threshold)
    world.set(p, "max_checks", max_checks)
    c = world.spawn()
    world.mark(c, "choice")
    world.set(c, "venue", venue_entities[choice])


KNOBS = (
    tuning.Knob("rain_threshold", 0.0, 1.0, steps=6),
    tuning.Knob("max_checks", 1, 5, steps=5, integer=True),
)


def score_replay(replay) -> float:
    """A TRAJECTORY score: reach a sound plan (`valid`), cheaply (`checks`)."""
    world = replay.world
    return (2.0 if is_valid(world) else 0.0) - 0.5 * len(world.each("checked"))


def scenarios():
    return (
        tuning.Scenario(kwargs=(("rain", 0.9),)),
        tuning.Scenario(kwargs=(("rain", 0.4),)),
        tuning.Scenario(kwargs=(("rain", 0.0),)),
        tuning.Scenario(kwargs=(("choice", "hall"), ("rain", 0.9))),
        tuning.Scenario(kwargs=(("rain", 0.9), ("tent", 200))),
    )


def evaluate(values, cases=None):
    cases = scenarios() if cases is None else cases
    rows = []
    total = 0.0
    for scenario in cases:
        replay = tuning.replay(scenario, install, KNOBS, values)
        score = score_replay(replay)
        total += score
        rows.append({
            "kwargs": scenario.kwargs,
            "valid": is_valid(replay.world),
            "checks": len(replay.world.each("checked")),
            "score": score,
        })
    return {"total": total, "rows": rows}


def report():
    """The trajectory numbers: the default knobs, the tuned ones, and two
    naive settings."""
    cases = scenarios()
    best = tuning.search(install, cases, KNOBS, score_replay)
    return {
        "default_values": (0.5, 4),
        "default": evaluate((0.5, 4), cases)["total"],
        "tuned_values": best.values,
        "tuned": best.score,
        "naive_high_threshold": evaluate((0.9, 4), cases)["total"],
        "naive_shallow_budget": evaluate((0.5, 1), cases)["total"],
    }
