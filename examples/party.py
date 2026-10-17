"""`party` -- Experiment 5: composing SIMPLE local reasoning into a CHAINED
investigation, with NO central scheduler. Rules each watch their own
(sometimes broader) condition and contribute purely through stigmergy.

## The point

Organising a party needs several questions answered, and the answers raise
new questions: an OUTDOOR venue raises "will it rain?", rain raises "is
there an affordable indoor backup?". No rule plans this chain. There is no
scheduler deciding what to check next. Each rule watches a condition and
deposits a `Question` when it holds; a matching rule consumes that question
and deposits a finding; a finding can make a later rule's condition true.
"After the weather check, ask for a backup" is written as DATA -- the backup
rule reads the `Rain` a finding left behind -- not as an order.

## The primitive: a question is an entity

`Question(kind)` is a pending question; a rule raises one only when its own
condition holds and no question of that kind is pending or already
`Checked` (dedup BY EXISTENCE in the world -- there is no global queue).
Answering consumes the `Question` and leaves two durable records: a
`Checked(kind)` (so it is never asked twice -- also the cost counter) and
the finding itself (`Rain`/`Clear`/`Backup`) attached to the `Choice`.

## The decision waits without a scheduler

`decide` runs only when NO `Question` is pending (`w.first(Question) is
None` -- written this way on purpose, so `analyze` marks `Question` a
NEGATED read and does not gate the rule dormant on the very type whose
absence it watches; see `loop.py`'s note and README History on
`negated_reads`). "Wait for the checks" is therefore a condition, not an
order. With the checks done it books the chosen venue if it is affordable
and weather-safe, else `Rejected(why)`.

## The scope axis -- what this experiment is really about

Each raising rule's condition can be narrower or broader than the constraint
it protects, and that changes the trajectory:

- **narrow** -- the concern is checked for the FIRST row only (`raise_
  weather_first`). It can miss the venue that actually matters.
- **scoped** -- the concern is checked for the row that MATTERS (the chosen
  venue). Correct and cheap.
- **broad** -- the concern is checked for EVERY row (`raise_weather_any`),
  even when the chosen venue is indoor. Correct but wasteful.

## What this found

Two scenarios, venues `hall(indoor, 50)` and `garden(outdoor, 40)`, rain
true, budget 100, reporting `(planned, valid, cost = questions asked)`:

- **outdoor_risky** (choice = garden): `narrow` -> `(False, -, 0)` -- it
  checked the FIRST venue (the indoor hall), never saw the weather, and the
  cautious decision REFUSED (`weather not cleared`) a perfectly good party;
  `scoped`/`broad` -> `(True, True, 2)`, the full weather->backup chain.
- **indoor_chosen** (choice = hall): `narrow`/`scoped` -> `(True, True, 0)`
  -- nothing to check; `broad` -> `(True, True, 2)` -- it asked about the
  weather for a venue nobody is booking. Wasted investigation.
- **A sub-scoped trigger is not safe, it is silent.** With a TRUSTING
  decision (`decide_trusting`, which reads "no `Rain` found" as "fine"),
  `narrow` on `outdoor_risky` yields `(True, **False**, 0)`: a confident,
  INVALID plan -- an outdoor party in the rain with no backup, because the
  check that would have caught it never fired. The cautious decision is what
  converts a too-narrow scope from a wrong answer into a refusal.

So: no scheduler is needed -- the chain emerges from scoped conditions --
but every raising condition must be at least as BROAD as the constraint it
looks after, or the reasoning silently skips a step. Correctness comes from
the SCOPE of the watched conditions; cost comes from how much broader than
necessary they are.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.loop import Loop


# -- facts ---------------------------------------------------------------

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
    rain: bool


@dataclass(frozen=True)
class Choice:
    venue: int


# -- questions, findings, outcome ---------------------------------------

@dataclass(frozen=True)
class Question:
    kind: str            # "weather" | "backup"


@dataclass(frozen=True)
class Checked:
    kind: str            # durable: this question was asked and answered


@dataclass(frozen=True)
class Rain:
    pass


@dataclass(frozen=True)
class Clear:
    pass


@dataclass(frozen=True)
class Backup:
    venue: int


@dataclass(frozen=True)
class Planned:
    venue: int


@dataclass(frozen=True)
class Rejected:
    why: str


# -- raising a question: a scoped condition, deduped by existence --------

def _pending_or_done(w, kind) -> bool:
    """Structural dedup: is this question already pending, or already
    answered? No global queue -- the world IS the queue."""
    if any(question.kind == kind for _e, question in w.all(Question)):
        return True
    return any(checked.kind == kind for _e, checked in w.all(Checked))


def raise_weather_first(w) -> None:
    """NARROW: check the weather only for the FIRST venue."""
    if _pending_or_done(w, "weather"):
        return
    venues = [venue for _e, venue in w.all(Venue)]
    if venues and not venues[0].indoor:
        w.spawn(Question("weather"))


def raise_weather_chosen(w) -> None:
    """SCOPED: check the weather for the venue actually being booked."""
    if _pending_or_done(w, "weather"):
        return
    for _e, choice in w.all(Choice):
        venue = w.get(choice.venue, Venue)
        if venue is not None and not venue.indoor:
            w.spawn(Question("weather"))
            return


def raise_weather_any(w) -> None:
    """BROAD: check the weather if ANY venue is outdoor, booked or not."""
    if _pending_or_done(w, "weather"):
        return
    if any(not venue.indoor for _e, venue in w.all(Venue)):
        w.spawn(Question("weather"))


def answer_weather(w) -> None:
    for entity, question in w.each(Question):
        if question.kind != "weather":
            continue
        forecast = w.the(Forecast)
        w.destroy(entity)
        w.spawn(Checked("weather"))
        for choice_entity, _choice in w.all(Choice):
            if forecast is not None and forecast.rain:
                w.attach(choice_entity, Rain())
            else:
                w.attach(choice_entity, Clear())


def raise_backup(w) -> None:
    """The CHAIN: a `Rain` finding an earlier rule left behind makes this
    rule's condition true -- no scheduler asked for it."""
    if _pending_or_done(w, "backup"):
        return
    for entity, _choice in w.all(Choice):
        if w.has(entity, Rain):
            w.spawn(Question("backup"))
            return


def answer_backup(w) -> None:
    for entity, question in w.each(Question):
        if question.kind != "backup":
            continue
        budget = w.the(Budget)
        backup = None
        for venue_entity, venue in w.all(Venue):
            if venue.indoor and venue.cost <= budget.amount:
                backup = venue_entity
                break
        w.destroy(entity)
        w.spawn(Checked("backup"))
        if backup is not None:
            for choice_entity, _choice in w.all(Choice):
                w.attach(choice_entity, Backup(backup.id))


# -- the decision: waits on NO pending question, then judges -------------

def decide_cautious(w) -> None:
    """Book only if the weather is cleared or a backup exists -- an unrun
    check leaves `weather_safe` false, so a too-narrow scope REFUSES rather
    than guesses."""
    if w.first(Question) is not None:
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
        weather_safe = venue.indoor or w.has(entity, Clear) or w.has(entity, Backup)
        if weather_safe:
            w.attach(entity, Planned(choice.venue))
        else:
            w.attach(entity, Rejected("weather not cleared"))


def decide_trusting(w) -> None:
    """The naive policy: "no `Rain` found" is read as "fine". Cheap, and
    silently WRONG whenever the check that would have found the rain never
    fired (a sub-scoped condition). Here to show what the cautious decision
    above is protecting against."""
    if w.first(Question) is not None:
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
        if venue.indoor or w.has(entity, Clear) or w.has(entity, Backup):
            w.attach(entity, Planned(choice.venue))
        elif w.has(entity, Rain):
            w.attach(entity, Rejected("rain expected"))
        else:
            w.attach(entity, Planned(choice.venue))    # assume safe -- the flaw


def is_valid(w) -> bool:
    """Ground truth, read from the FACTS (not the findings): is the booked
    plan actually sound -- affordable, and not an outdoor party in the rain
    without a backup?"""
    budget = w.the(Budget)
    forecast = w.the(Forecast)
    for entity, choice in w.all(Choice):
        venue = w.get(choice.venue, Venue)
        if venue is None or venue.cost > budget.amount:
            return False
        if not venue.indoor and forecast is not None and forecast.rain:
            if not w.has(entity, Backup):
                return False
    return True


# -- wiring --------------------------------------------------------------

WEATHER_RAISERS = {
    "narrow": raise_weather_first,
    "scoped": raise_weather_chosen,
    "broad": raise_weather_any,
}


def install(loop, scope="scoped", trusting=False,
            venues=(("hall", 50, True), ("garden", 40, False)),
            choice="garden", rain=True, budget=100) -> None:
    loop.rule(WEATHER_RAISERS[scope])
    loop.rule(answer_weather)
    loop.rule(raise_backup)
    loop.rule(answer_backup)
    loop.rule(decide_trusting if trusting else decide_cautious)
    world = loop.world
    venue_entities = {}
    for name, cost, indoor in venues:
        venue_entities[name] = world.spawn(Venue(name, cost, indoor))
    world.spawn(Budget(budget))
    world.spawn(Forecast(rain))
    world.spawn(Choice(venue_entities[choice].id))


def run(scope="scoped", trusting=False, **kwargs):
    """Run one party scenario and report what happened: whether a plan was
    made (`planned`), whether it is actually sound (`valid`, read from the
    facts), and the cost (`asks` = questions asked)."""
    loop = Loop()
    install(loop, scope=scope, trusting=trusting, **kwargs)
    settled = loop.run()
    world = loop.world
    return {
        "planned": any(True for _e, _p in world.all(Planned)),
        "valid": is_valid(world),
        "asks": len(world.all(Checked)),
        "settled": not settled.hot,
        "hot": settled.hot,
    }


_OUTDOOR = dict(venues=(("hall", 50, True), ("garden", 40, False)),
                choice="garden", rain=True)
_INDOOR = dict(venues=(("hall", 50, True), ("garden", 40, False)),
               choice="hall", rain=True)


def report():
    """The whole experiment: the three scopes on the two scenarios, plus the
    trusting decision under a too-narrow scope -- the invalid-but-confident
    plan the cautious decision refuses instead."""
    out = {}
    for name, scenario in (("outdoor_risky", _OUTDOOR), ("indoor_chosen", _INDOOR)):
        out[name] = {scope: run(scope, **scenario)
                     for scope in ("narrow", "scoped", "broad")}
    out["trusting_narrow"] = run("narrow", trusting=True, **_OUTDOOR)
    return out
