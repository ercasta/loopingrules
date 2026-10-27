"""`branching` -- Experiment 7: a finding raises a choice, and the chosen
remedy raises ANOTHER choice -- a branch, not a chain, with no scheduler.

## The shape

`planning` chose among remedies in one step. Here the level-1 choice can
OPEN a level-2 choice:

    rain on the garden
      -> Q(cover): rent a TENT, or RELOCATE to the indoor hall
           - relocate -> done (the hall is indoor)
           - tent     -> Q(tent_size): which tent fits the guests? (depth 2)

Both levels are the SAME mechanism -- rules propose candidates carrying
`examples.decide`'s `Option`/`Score`, and `decide.pick_winner` crowns the
best -- but the two levels never collide because each question ENTITY is
its own `occasion`: `Option(cover_question_id)` at level 1,
`Option(tent_size_question_id)` at level 2. So the SAME oblivious rule
resolves both, and the branch is just a condition (`Question("tent_size")`
exists only if the tent branch won).

## Depth is data, and it is what you tune

A `Policy(prefer_relocate, max_checks)` is the tunable surface:

- `prefer_relocate` -- a bonus that makes the shallow `relocate` branch
  (1 check after the weather) beat the deeper `tent` branch (2 checks),
  when both are valid. Choosing the shallow branch is a TRAJECTORY choice.
- `max_checks` -- the depth budget. Set it to 1 and the sub-question is
  never asked, so the tent branch cannot complete and the plan is refused.

## What this found

Scenarios: a small party (a cheap fitting tent exists), a big one (no
fitting cheap tent -- relocate already wins), a dry day, and an indoor
venue. Score `valid*3 - checks`.

- **The branch really is two levels.** The small-party run under the
  default policy rents a tent, and the tent SIZE is a second choice with its
  own proposed candidates and its own winner -- `pick_winner` resolved both
  without knowing there were two levels.
- **Depth costs.** `tent` branch = 3 checks (weather, cover, tent_size);
  `relocate` = 2. Tuning `prefer_relocate` up moves the small party onto the
  shallow branch: the total rises from `6` (default) to `7` with
  `prefer_relocate >= 40`, and `max_checks` must be at least 2 or the tent
  branch cannot finish.
- **A too-small depth budget is a silent refusal.** `max_checks = 1` stops
  after the weather check, so neither remedy is reached and the plan is
  refused -- safe, but a missed party.
"""

from __future__ import annotations

from dataclasses import dataclass

import loopingrules_calibration as tuning
from examples.decide import Option, Score, Winner, pick_winner
from loopingrules.loop import Loop


# -- facts and knobs -----------------------------------------------------

@dataclass(frozen=True)
class Venue:
    name: str
    cost: int
    indoor: bool


@dataclass(frozen=True)
class Tent:
    name: str
    capacity: int
    cost: int


@dataclass(frozen=True)
class Budget:
    amount: int


@dataclass(frozen=True)
class Forecast:
    rain: float


@dataclass(frozen=True)
class Guests:
    count: int


@dataclass(frozen=True)
class Choice:
    venue: int


@dataclass(frozen=True)
class Policy:
    prefer_relocate: float
    max_checks: int


# -- questions, findings, outcome ---------------------------------------

@dataclass(frozen=True)
class Question:
    kind: str            # "weather" | "cover" | "tent_size"


@dataclass(frozen=True)
class Checked:
    kind: str


@dataclass(frozen=True)
class Rain:
    pass


@dataclass(frozen=True)
class Clear:
    pass


@dataclass(frozen=True)
class Remedy:
    kind: str            # "tent" | "relocate" | "tent_option"
    subject: int         # 0 | a venue id | a tent entity id


@dataclass(frozen=True)
class Backup:
    venue: int


@dataclass(frozen=True)
class TentUsed:
    name: str


@dataclass(frozen=True)
class Planned:
    venue: int


@dataclass(frozen=True)
class Rejected:
    why: str


# -- helpers -------------------------------------------------------------

def _pending_or_done(w, kind) -> bool:
    if any(question.kind == kind for _e, question in w.all(Question)):
        return True
    return any(checked.kind == kind for _e, checked in w.all(Checked))


def _budget_spent(w) -> bool:
    return len(w.all(Checked)) >= w.the(Policy).max_checks


def _cover_question(w):
    for entity, question in w.each(Question):
        if question.kind == "cover":
            return entity
    return None


def _candidate(w, question_id, kind) -> bool:
    for entity, remedy in w.all(Remedy):
        if remedy.kind != kind:
            continue
        option = w.get(entity, Option)
        if option is not None and option.occasion == question_id:
            return True
    return False


# -- weather -------------------------------------------------------------

def raise_weather(w) -> None:
    if _pending_or_done(w, "weather") or _budget_spent(w):
        return
    for entity, choice in w.all(Choice):
        venue = w.get(choice.venue, Venue)
        if venue is not None and not venue.indoor and not w.has(entity, Rain) and not w.has(entity, Clear):
            w.spawn(Question("weather"))
            return


def answer_weather(w) -> None:
    for entity, question in w.each(Question):
        if question.kind != "weather":
            continue
        forecast = w.the(Forecast)
        w.destroy(entity)
        w.spawn(Checked("weather"))
        for choice_entity, _choice in w.all(Choice):
            if forecast is not None and forecast.rain > 0.0:
                w.attach(choice_entity, Rain())
            else:
                w.attach(choice_entity, Clear())


def raise_cover(w) -> None:
    if _pending_or_done(w, "cover") or _budget_spent(w):
        return
    for entity, _choice in w.all(Choice):
        if w.has(entity, Rain):
            w.spawn(Question("cover"))
            return


# -- level 1: cover the exposed venue ------------------------------------

def propose_tent(w) -> None:
    """Level-1 candidate: rent the cheapest tent that fits and is affordable."""
    budget, guests = w.the(Budget), w.the(Guests)
    question = _cover_question(w)
    if question is None or _candidate(w, question.id, "tent"):
        return
    best = None
    for _entity, tent in w.all(Tent):
        if tent.capacity >= guests.count and tent.cost <= budget.amount:
            if best is None or tent.cost < best:
                best = tent.cost
    if best is not None:
        w.spawn(Remedy("tent", 0), Option(question.id), Score(float(-best)))


def propose_relocate(w) -> None:
    """Level-1 candidate: move to the cheapest affordable indoor venue."""
    budget, policy = w.the(Budget), w.the(Policy)
    question = _cover_question(w)
    if question is None or _candidate(w, question.id, "relocate"):
        return
    best = None
    for venue_entity, venue in w.all(Venue):
        if venue.indoor and venue.cost <= budget.amount:
            if best is None or venue.cost < best[1]:
                best = (venue_entity, venue.cost)
    if best is not None:
        w.spawn(Remedy("relocate", best[0].id), Option(question.id),
                Score(float(-best[1] + policy.prefer_relocate)))


def resolve_cover(w) -> None:
    """Apply the level-1 winner; if it is the tent, OPEN the level-2 choice."""
    question = _cover_question(w)
    if question is None:
        return
    winner = None
    for candidate, remedy in w.all(Remedy):
        option = w.get(candidate, Option)
        if option is not None and option.occasion == question.id and w.has(candidate, Winner):
            winner = remedy
            break
    if winner is None:
        return
    w.destroy(question)
    w.spawn(Checked("cover"))
    if winner.kind == "relocate":
        for choice_entity, _choice in w.all(Choice):
            w.attach(choice_entity, Backup(winner.subject))
    elif not _budget_spent(w):
        w.spawn(Question("tent_size"))       # depth 2


# -- level 2: which tent? (the same mechanism, its own occasion) ---------

def propose_tents(w) -> None:
    budget, guests = w.the(Budget), w.the(Guests)
    for entity, question in w.each(Question):
        if question.kind != "tent_size":
            continue
        if _candidate(w, entity.id, "tent_option"):
            return
        for tent_entity, tent in w.all(Tent):
            if tent.capacity >= guests.count and tent.cost <= budget.amount:
                w.spawn(Remedy("tent_option", tent_entity.id),
                        Option(entity.id), Score(float(-tent.cost)))
        return


def resolve_tent_size(w) -> None:
    for entity, question in w.each(Question):
        if question.kind != "tent_size":
            continue
        winner = None
        for candidate, remedy in w.all(Remedy):
            option = w.get(candidate, Option)
            if option is not None and option.occasion == entity.id and w.has(candidate, Winner):
                winner = remedy
                break
        if winner is None:
            continue
        w.destroy(entity)
        w.spawn(Checked("tent_size"))
        tent = w.get(winner.subject, Tent)
        for choice_entity, _choice in w.all(Choice):
            if tent is not None:
                w.attach(choice_entity, TentUsed(tent.name))


# -- the decision --------------------------------------------------------

def finalize(w) -> None:
    if w.first(Question) is not None:      # NEGATED read -- see party.py
        return
    for entity, choice in w.each(Choice, without=(Planned, Rejected)):
        venue = w.get(choice.venue, Venue)
        budget = w.the(Budget)
        if venue is None:
            w.attach(entity, Rejected("no such venue"))
            continue
        if budget is None or venue.cost > budget.amount:
            w.attach(entity, Rejected("over budget"))
            continue
        safe = (venue.indoor or w.has(entity, Clear)
                or w.has(entity, Backup) or w.has(entity, TentUsed))
        if safe:
            w.attach(entity, Planned(choice.venue))
        else:
            w.attach(entity, Rejected("weather not handled"))


def _tent_named(w, name):
    for _entity, tent in w.all(Tent):
        if tent.name == name:
            return tent
    return None


def is_valid(w) -> bool:
    """Ground truth: affordable, and any rain on an outdoor venue is handled
    by an indoor backup OR a tent that actually fits the guests."""
    budget, forecast, guests = w.the(Budget), w.the(Forecast), w.the(Guests)
    for entity, choice in w.all(Choice):
        venue = w.get(choice.venue, Venue)
        if venue is None or venue.cost > budget.amount:
            return False
        if venue.indoor or forecast is None or forecast.rain <= 0.0:
            continue
        if w.has(entity, Backup):
            continue
        used = w.get(entity, TentUsed)
        tent = None if used is None else _tent_named(w, used.name)
        if tent is None or tent.capacity < guests.count:
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
        venue_entities[name] = world.spawn(Venue(name, cost, indoor))
    for name, capacity, cost in tents:
        world.spawn(Tent(name, capacity, cost))
    world.spawn(Budget(budget))
    world.spawn(Forecast(rain))
    world.spawn(Guests(guests))
    world.spawn(Policy(prefer_relocate, max_checks))
    world.spawn(Choice(venue_entities[choice].id))


KNOBS = (
    tuning.Knob(Policy, "prefer_relocate", 0.0, 60.0, steps=4),
    tuning.Knob(Policy, "max_checks", 1, 3, steps=3, integer=True),
)


def score_replay(replay) -> float:
    world = replay.world
    return (3.0 if is_valid(world) else 0.0) - 1.0 * len(world.all(Checked))


def scenarios():
    return (
        tuning.Scenario(kwargs=(("guests", 4), ("rain", 0.9))),     # small party
        tuning.Scenario(kwargs=(("guests", 10), ("rain", 0.9))),    # big party
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
            "checks": len(replay.world.all(Checked)),
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
