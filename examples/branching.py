"""`branching` -- Experiment 7: a finding raises a choice, and the chosen
remedy raises ANOTHER choice -- a branch, with no scheduler.

Under the attribute substrate (D8): `venue`/`tent`/`choice`/`question`/
`checked`/`remedy` are tagged entities; budget/forecast/guests/policy are
singletons; findings are flags/an attribute on the choice. Both levels ride
`examples.decide`'s `occasion`/`score`, each question its own occasion.
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


def _cover_question(w):
    for entity, _t, kind in w.each("question", "kind"):
        if kind == "cover":
            return entity
    return None


def _candidate(w, question_id, kind) -> bool:
    for entity, _t, rkind in w.each("remedy", "kind"):
        if rkind != kind:
            continue
        if w.get(entity, "occasion") == question_id:
            return True
    return False


def _spawn_kind(w, tag, kind):
    entity = w.spawn()
    w.mark(entity, tag)
    w.set(entity, "kind", kind)
    return entity


def _singleton(w, name, field, default=0):
    row = w.first(name)
    return w.get(row[0], field, default) if row else default


# -- weather -------------------------------------------------------------

def raise_weather(w) -> None:
    if _pending_or_done(w, "weather") or _budget_spent(w):
        return
    for entity, _t, venue_id in w.each("choice", "venue"):
        if (not w.get(venue_id, "indoor", False) and not w.has(entity, "rain")
                and not w.has(entity, "clear")):
            _spawn_kind(w, "question", "weather")
            return


def answer_weather(w) -> None:
    rain = _singleton(w, "forecast", "rain", 0.0)
    for entity, _t, kind in w.each("question", "kind"):
        if kind != "weather":
            continue
        w.destroy(entity)
        _spawn_kind(w, "checked", "weather")
        for choice_entity, _ct in w.each("choice"):
            if rain > 0.0:
                w.mark(choice_entity, "rain")
            else:
                w.mark(choice_entity, "clear")


def raise_cover(w) -> None:
    if _pending_or_done(w, "cover") or _budget_spent(w):
        return
    for entity, _t in w.each("choice"):
        if w.has(entity, "rain"):
            _spawn_kind(w, "question", "cover")
            return


# -- level 1: cover the exposed venue ------------------------------------

def _propose(w, question, kind, subject, score):
    remedy = w.spawn()
    w.mark(remedy, "remedy")
    w.set(remedy, "kind", kind)
    w.set(remedy, "subject", subject)
    w.set(remedy, "occasion", question)
    w.set(remedy, "score", float(score))


def propose_tent(w) -> None:
    """Level-1 candidate: rent the cheapest tent that fits and is affordable."""
    question = _cover_question(w)
    if question is None or _candidate(w, question.id, "tent"):
        return
    amount = _singleton(w, "budget", "amount", 0)
    guests = _singleton(w, "guests", "count", 0)
    best = None
    for _e, _t, capacity, cost in w.each("tent", "capacity", "cost"):
        if capacity >= guests and cost <= amount:
            if best is None or cost < best:
                best = cost
    if best is not None:
        _propose(w, question.id, "tent", 0, -best)


def propose_relocate(w) -> None:
    """Level-1 candidate: move to the cheapest affordable indoor venue."""
    question = _cover_question(w)
    if question is None or _candidate(w, question.id, "relocate"):
        return
    amount = _singleton(w, "budget", "amount", 0)
    bonus = _singleton(w, "policy", "prefer_relocate", 0.0)
    best = None
    for venue_entity, _t, indoor, cost in w.each("venue", "indoor", "cost"):
        if indoor and cost <= amount:
            if best is None or cost < best[1]:
                best = (venue_entity, cost)
    if best is not None:
        _propose(w, question.id, "relocate", best[0].id, -best[1] + bonus)


def resolve_cover(w) -> None:
    """Apply the level-1 winner; if it is the tent, OPEN the level-2 choice."""
    question = _cover_question(w)
    if question is None:
        return
    winner = None
    for candidate, _t, kind, subject in w.each("remedy", "kind", "subject"):
        if w.get(candidate, "occasion") == question.id and w.has(candidate,
                                                                 "winner"):
            winner = (kind, subject)
            break
    if winner is None:
        return
    w.destroy(question)
    _spawn_kind(w, "checked", "cover")
    if winner[0] == "relocate":
        for choice_entity, _ct in w.each("choice"):
            w.set(choice_entity, "backup", winner[1])
    elif not _budget_spent(w):
        _spawn_kind(w, "question", "tent_size")       # depth 2


# -- level 2: which tent? (the same mechanism, its own occasion) ---------

def propose_tents(w) -> None:
    amount = _singleton(w, "budget", "amount", 0)
    guests = _singleton(w, "guests", "count", 0)
    for entity, _t, kind in w.each("question", "kind"):
        if kind != "tent_size":
            continue
        if _candidate(w, entity.id, "tent_option"):
            return
        for tent_entity, _tt, capacity, cost in w.each("tent", "capacity",
                                                       "cost"):
            if capacity >= guests and cost <= amount:
                _propose(w, entity.id, "tent_option", tent_entity.id, -cost)
        return


def resolve_tent_size(w) -> None:
    for entity, _t, kind in w.each("question", "kind"):
        if kind != "tent_size":
            continue
        winner = None
        for candidate, _rt, rkind, subject in w.each("remedy", "kind",
                                                     "subject"):
            if w.get(candidate, "occasion") == entity.id and w.has(candidate,
                                                                   "winner"):
                winner = subject
                break
        if winner is None:
            continue
        w.destroy(entity)
        _spawn_kind(w, "checked", "tent_size")
        name = w.get(winner, "name")
        for choice_entity, _ct in w.each("choice"):
            if name is not None:
                w.set(choice_entity, "tent_used", name)


# -- the decision --------------------------------------------------------

def finalize(w) -> None:
    if w.first("question") is not None:      # NEGATED read
        return
    amount = _singleton(w, "budget", "amount", 0)
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


def _tent_by_name(w, name):
    for entity, _t, tent_name in w.each("tent", "name"):
        if tent_name == name:
            return entity
    return None


def is_valid(w) -> bool:
    """Ground truth: affordable, and any rain on an outdoor venue is handled
    by an indoor backup OR a tent that actually fits the guests."""
    amount = _singleton(w, "budget", "amount", 0)
    rain = _singleton(w, "forecast", "rain", 0.0)
    guests = _singleton(w, "guests", "count", 0)
    for entity, _t in w.each("choice"):
        venue_id = w.get(entity, "venue")
        if not w.has(venue_id, "cost") or w.get(venue_id, "cost") > amount:
            return False
        if w.get(venue_id, "indoor", False) or rain <= 0.0:
            continue
        if w.has(entity, "backup"):
            continue
        used = None if not w.has(entity, "tent_used") else w.get(entity,
                                                                  "tent_used")
        tent = None if used is None else _tent_by_name(w, used)
        if tent is None or w.get(tent, "capacity", 0) < guests:
            return False
    return True


# -- wiring and the trajectory score ------------------------------------

def install(loop, venues=(("hall", 50, True), ("garden", 40, False)),
            tents=(("popup", 4, 20), ("marquee", 20, 60)),
            choice="garden", rain=0.9, guests=4, budget=100,
            prefer_relocate=0.0, max_checks=4) -> None:
    loop.rule(raise_weather)
    loop.rule(answer_weather)
    loop.rule(raise_cover)
    loop.rule(propose_tent)
    loop.rule(propose_relocate)
    loop.rule(pick_winner)
    loop.rule(resolve_cover)
    loop.rule(propose_tents)
    loop.rule(resolve_tent_size)
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
    for name, capacity, cost in tents:
        entity = world.spawn()
        world.mark(entity, "tent")
        world.set(entity, "name", name)
        world.set(entity, "capacity", capacity)
        world.set(entity, "cost", cost)
    b = world.spawn()
    world.mark(b, "budget")
    world.set(b, "amount", budget)
    f = world.spawn()
    world.mark(f, "forecast")
    world.set(f, "rain", rain)
    g = world.spawn()
    world.mark(g, "guests")
    world.set(g, "count", guests)
    p = world.spawn()
    world.mark(p, "policy")
    world.set(p, "prefer_relocate", prefer_relocate)
    world.set(p, "max_checks", max_checks)
    c = world.spawn()
    world.mark(c, "choice")
    world.set(c, "venue", venue_entities[choice])


KNOBS = (
    tuning.Knob("prefer_relocate", 0.0, 60.0, steps=4),
    tuning.Knob("max_checks", 1, 3, steps=3, integer=True),
)


def score_replay(replay) -> float:
    world = replay.world
    return (3.0 if is_valid(world) else 0.0) - 1.0 * len(world.each("checked"))


def scenarios():
    return (
        tuning.Scenario(kwargs=(("guests", 4), ("rain", 0.9))),     # small
        tuning.Scenario(kwargs=(("guests", 10), ("rain", 0.9))),    # big
        tuning.Scenario(kwargs=(("guests", 4), ("rain", 0.0))),     # dry
        tuning.Scenario(kwargs=(("choice", "hall"), ("rain", 0.9))),  # indoor
    )


def evaluate(values, cases=None):
    cases = scenarios() if cases is None else cases
    rows, total = [], 0.0
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
    cases = scenarios()
    best = tuning.search(install, cases, KNOBS, score_replay)
    return {
        "default_values": (0.0, 4),
        "default": evaluate((0.0, 4), cases)["total"],
        "tuned_values": best.values,
        "tuned": best.score,
        "shallow_budget": evaluate((40.0, 1), cases)["total"],
    }
