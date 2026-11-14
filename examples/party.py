"""`party` -- Experiment 5: composing SIMPLE local reasoning into a CHAINED
investigation, with NO central scheduler.

Under the attribute substrate (D8): a `venue` is a tagged entity; the budget
and forecast are singletons; a `choice` entity carries `venue` (a reference);
`question`/`checked` are entities (the world IS the queue); the findings
`rain`/`clear`/`backup` are flags/an attribute on the choice; `planned` is an
attribute (the booked venue id) and `rejected` an attribute (why).
"""

from __future__ import annotations

from loopingrules.loop import Loop


def _pending_or_done(w, kind) -> bool:
    """Structural dedup: is this question already pending, or answered?"""
    for _e, _t, k in w.each("question", "kind"):
        if k == kind:
            return True
    for _e, _t, k in w.each("checked", "kind"):
        if k == kind:
            return True
    return False


def _spawn_kind(w, tag, kind):
    entity = w.spawn()
    w.mark(entity, tag)
    w.set(entity, "kind", kind)
    return entity


def raise_weather_first(w) -> None:
    """NARROW: check the weather only for the FIRST venue."""
    if _pending_or_done(w, "weather"):
        return
    venues = w.each("venue", "indoor")
    if venues and not venues[0][2]:
        _spawn_kind(w, "question", "weather")


def raise_weather_chosen(w) -> None:
    """SCOPED: check the weather for the venue actually being booked."""
    if _pending_or_done(w, "weather"):
        return
    for _e, _t, venue_id in w.each("choice", "venue"):
        if not w.get(venue_id, "indoor", False):
            _spawn_kind(w, "question", "weather")
            return


def raise_weather_any(w) -> None:
    """BROAD: check the weather if ANY venue is outdoor."""
    if _pending_or_done(w, "weather"):
        return
    for _e, _t, indoor in w.each("venue", "indoor"):
        if not indoor:
            _spawn_kind(w, "question", "weather")
            return


def answer_weather(w) -> None:
    forecast = w.first("forecast")
    rain = bool(forecast) and w.get(forecast[0], "rain", False)
    for entity, _t, kind in w.each("question", "kind"):
        if kind != "weather":
            continue
        w.destroy(entity)
        _spawn_kind(w, "checked", "weather")
        for choice_entity, _ct in w.each("choice"):
            if rain:
                w.mark(choice_entity, "rain")
            else:
                w.mark(choice_entity, "clear")


def raise_backup(w) -> None:
    """The CHAIN: a `rain` finding an earlier rule left behind makes this
    rule's condition true -- no scheduler asked for it."""
    if _pending_or_done(w, "backup"):
        return
    for entity, _t in w.each("choice"):
        if w.has(entity, "rain"):
            _spawn_kind(w, "question", "backup")
            return


def answer_backup(w) -> None:
    budget = w.first("budget")
    amount = w.get(budget[0], "amount", 0) if budget else 0
    for entity, _t, kind in w.each("question", "kind"):
        if kind != "backup":
            continue
        backup = None
        for venue_entity, _vt, indoor, cost in w.each("venue", "indoor",
                                                      "cost"):
            if indoor and cost <= amount:
                backup = venue_entity
                break
        w.destroy(entity)
        _spawn_kind(w, "checked", "backup")
        if backup is not None:
            for choice_entity, _ct in w.each("choice"):
                w.set(choice_entity, "backup", backup)


# -- the decision: waits on NO pending question, then judges -------------

def _decide(w, trusting: bool) -> None:
    if w.first("question") is not None:
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
        weather_safe = indoor or w.has(entity, "clear") or w.has(entity, "backup")
        if weather_safe:
            w.set(entity, "planned", venue_id)
        elif not trusting and w.has(entity, "rain"):
            w.set(entity, "rejected", "rain expected")
        elif not trusting:
            w.set(entity, "rejected", "weather not cleared")
        else:
            w.set(entity, "planned", venue_id)    # assume safe -- the flaw


def decide_cautious(w) -> None:
    """Book only if the weather is cleared or a backup exists."""
    _decide(w, trusting=False)


def decide_trusting(w) -> None:
    """The naive policy: "no `rain` found" is read as "fine"."""
    _decide(w, trusting=True)


def is_valid(w) -> bool:
    """Ground truth, read from the FACTS: is the booked plan sound --
    affordable, and not an outdoor party in the rain without a backup?"""
    budget = w.first("budget")
    amount = w.get(budget[0], "amount", 0) if budget else 0
    forecast = w.first("forecast")
    rain = bool(forecast) and w.get(forecast[0], "rain", False)
    for entity, _t in w.each("choice"):
        venue_id = w.get(entity, "venue")
        if not w.has(venue_id, "cost") or w.get(venue_id, "cost") > amount:
            return False
        if not w.get(venue_id, "indoor", False) and rain:
            if not w.has(entity, "backup"):
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
    c = world.spawn()
    world.mark(c, "choice")
    world.set(c, "venue", venue_entities[choice])


def run(scope="scoped", trusting=False, **kwargs):
    """Run one party scenario: whether a plan was made (`planned`), whether
    it is sound (`valid`, read from the facts), and the cost (`asks`)."""
    loop = Loop()
    install(loop, scope=scope, trusting=trusting, **kwargs)
    settled = loop.run()
    world = loop.world
    return {
        "planned": world.populated("planned"),
        "valid": is_valid(world),
        "asks": len(world.each("checked")),
        "settled": not settled.hot,
        "hot": settled.hot,
    }


_OUTDOOR = dict(venues=(("hall", 50, True), ("garden", 40, False)),
                choice="garden", rain=True)
_INDOOR = dict(venues=(("hall", 50, True), ("garden", 40, False)),
               choice="hall", rain=True)


def report():
    """The whole experiment: the three scopes on the two scenarios, plus the
    trusting decision under a too-narrow scope."""
    out = {}
    for name, scenario in (("outdoor_risky", _OUTDOOR),
                           ("indoor_chosen", _INDOOR)):
        out[name] = {scope: run(scope, **scenario)
                     for scope in ("narrow", "scoped", "broad")}
    out["trusting_narrow"] = run("narrow", trusting=True, **_OUTDOOR)
    return out
