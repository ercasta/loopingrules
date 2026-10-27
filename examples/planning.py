"""`planning` -- Experiment 6: (b) a finding that raises a CHOICE among
next questions, and (c) tuning the investigation's thresholds against
TRAJECTORY examples.

## (b) A choice point, resolved locally -- still no scheduler

`party` chained linearly (weather -> backup). Here the weather finding
raises a CHOICE: an outdoor venue on a rainy day can be made safe by an
indoor BACKUP venue or by renting a TENT. Several rules PROPOSE remedies --
`propose_backup` and `propose_tent` -- each attaching `examples.decide`'s
`Option(occasion)`/`Score(value)` to a candidate; `decide.pick_winner` (the
same oblivious rule `examples.trip` uses) attaches `Winner` to the cheapest;
`resolve_remedy` applies it. The choice is a LOCAL conflict resolution at
one decision point, not an omniscient scheduler -- exactly the "resolve only
where scopes overlap" line.

## (c) Tuning the investigation against trajectory examples

`Policy(rain_threshold, max_checks)` is the tunable surface -- components
the rules read, per `docs/tuning.md`'s design rule ("a tunable rule never
hard-codes its threshold; it reads a component"):

- `rain_threshold` -- how rainy it must look before a remedy is sought. A
  THRESHOLD that stands in for scope: too high and the agent calls a drizzly
  day "clear" and skips the remedy.
- `max_checks` -- how many checks may run at all. Too low and the chain is
  cut off before the remedy; too high only wastes.

The objective is a TRAJECTORY score, not a final number:
`valid * 2 - 0.5 * checks` -- reach a sound plan, cheaply. `tuning.search`
grids the two knobs against a handful of scenarios and picks the best.

## What this found

- **The choice point works, with no scheduler.** On a rainy outdoor booking
  both a backup and a tent are proposed; the cheaper (the tent) wins and is
  applied -- `decide.pick_winner` reused verbatim from the option/score
  bridge.
- **The knobs are the trajectory.** `max_checks = 1` cuts the chain after
  the weather check, so no remedy is ever sought and the plan is refused;
  a `rain_threshold` above the actual drizzle declares it clear and books an
  unprotected venue (INVALID). `tuning.search` finds a setting that is valid
  on every scenario at minimum checks.
- **The surface has plateaus.** Several thresholds are equally good (any
  value below the lightest rain, and above zero) -- reported as a
  behavioural equivalence class, per `docs/tuning.md`, not as one number.
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
class Budget:
    amount: int


@dataclass(frozen=True)
class Forecast:
    rain: float


@dataclass(frozen=True)
class Tent:
    cost: int


@dataclass(frozen=True)
class Choice:
    venue: int


@dataclass(frozen=True)
class Policy:
    rain_threshold: float
    max_checks: int


# -- questions, findings, outcome ---------------------------------------

@dataclass(frozen=True)
class Question:
    kind: str            # "weather" | "remedy"


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
    kind: str            # "backup" | "tent"
    subject: int         # a venue id (backup) or a tent cost (tent)


@dataclass(frozen=True)
class Backup:
    venue: int


@dataclass(frozen=True)
class TentUsed:
    cost: int


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
    policy = w.the(Policy)
    return len(w.all(Checked)) >= policy.max_checks


def _remedy_pending(w) -> bool:
    return any(question.kind == "remedy" for _e, question in w.all(Question))


def _has_candidate(w, choice_id, kind) -> bool:
    for entity, remedy in w.all(Remedy):
        if remedy.kind != kind:
            continue
        option = w.get(entity, Option)
        if option is not None and option.occasion == choice_id:
            return True
    return False


# -- raising and answering, then the CHOICE point -----------------------

def raise_weather(w) -> None:
    if _pending_or_done(w, "weather") or _budget_spent(w):
        return
    for _e, choice in w.all(Choice):
        venue = w.get(choice.venue, Venue)
        if venue is not None and not venue.indoor:
            w.spawn(Question("weather"))
            return


def answer_weather(w) -> None:
    policy = w.the(Policy)
    for entity, question in w.each(Question):
        if question.kind != "weather":
            continue
        forecast = w.the(Forecast)
        w.destroy(entity)
        w.spawn(Checked("weather"))
        risky = forecast is not None and forecast.rain > policy.rain_threshold
        for choice_entity, _choice in w.all(Choice):
            if risky:
                w.attach(choice_entity, Rain())
            else:
                w.attach(choice_entity, Clear())


def raise_remedy(w) -> None:
    """The finding (`Rain`) raises a CHOICE of next question."""
    if _pending_or_done(w, "remedy") or _budget_spent(w):
        return
    for entity, _choice in w.all(Choice):
        if w.has(entity, Rain):
            w.spawn(Question("remedy"))
            return


def propose_backup(w) -> None:
    if not _remedy_pending(w):
        return
    budget = w.the(Budget)
    for choice_entity, _choice in w.all(Choice):
        if not w.has(choice_entity, Rain) or _has_candidate(w, choice_entity.id, "backup"):
            continue
        for venue_entity, venue in w.all(Venue):
            if venue.indoor and venue.cost <= budget.amount:
                w.spawn(Remedy("backup", venue_entity.id),
                        Option(choice_entity.id), Score(float(-venue.cost)))
                return


def propose_tent(w) -> None:
    if not _remedy_pending(w):
        return
    budget = w.the(Budget)
    tent = w.the(Tent)
    for choice_entity, _choice in w.all(Choice):
        if not w.has(choice_entity, Rain) or _has_candidate(w, choice_entity.id, "tent"):
            continue
        if tent is not None and tent.cost <= budget.amount:
            w.spawn(Remedy("tent", tent.cost),
                    Option(choice_entity.id), Score(float(-tent.cost)))
            return


def resolve_remedy(w) -> None:
    for entity, question in w.each(Question):
        if question.kind != "remedy":
            continue
        w.destroy(entity)
        w.spawn(Checked("remedy"))
        for choice_entity, _choice in w.all(Choice):
            chosen = None
            for candidate, remedy in w.all(Remedy):
                option = w.get(candidate, Option)
                if (option is not None and option.occasion == choice_entity.id
                        and w.has(candidate, Winner)):
                    chosen = remedy
                    break
            if chosen is None:
                continue
            if chosen.kind == "backup":
                w.attach(choice_entity, Backup(chosen.subject))
            else:
                w.attach(choice_entity, TentUsed(chosen.subject))


# -- the decision --------------------------------------------------------

def finalize(w) -> None:
    if w.first(Question) is not None:      # a NEGATED read -- see party.py
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


def is_valid(w) -> bool:
    """Ground truth, from the FACTS, independent of the policy: is the
    booking actually sound? Any rain on an outdoor venue needs a remedy."""
    budget = w.the(Budget)
    forecast = w.the(Forecast)
    for entity, choice in w.all(Choice):
        venue = w.get(choice.venue, Venue)
        if venue is None or venue.cost > budget.amount:
            return False
        if not venue.indoor and forecast is not None and forecast.rain > 0.0:
            if not (w.has(entity, Backup) or w.has(entity, TentUsed)):
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
        venue_entities[name] = world.spawn(Venue(name, cost, indoor))
    world.spawn(Budget(budget))
    world.spawn(Forecast(rain))
    world.spawn(Tent(tent))
    world.spawn(Policy(rain_threshold, max_checks))
    world.spawn(Choice(venue_entities[choice].id))


KNOBS = (
    tuning.Knob(Policy, "rain_threshold", 0.0, 1.0, steps=6),
    tuning.Knob(Policy, "max_checks", 1, 5, steps=5, integer=True),
)


def score_replay(replay) -> float:
    """A TRAJECTORY score: reach a sound plan (`valid`), cheaply (`checks`).
    Nothing here reads a 'correct number' -- only the shape of the run."""
    world = replay.world
    return (2.0 if is_valid(world) else 0.0) - 0.5 * len(world.all(Checked))


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
            "checks": len(replay.world.all(Checked)),
            "score": score,
        })
    return {"total": total, "rows": rows}


def report():
    """The trajectory numbers: the default knobs, the tuned ones, and two
    naive settings -- too high a rain threshold (misses the drizzle) and too
    small a check budget (cuts the chain before the remedy)."""
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
