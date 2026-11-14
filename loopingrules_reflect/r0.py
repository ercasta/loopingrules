"""R0 -- a rule over memory and rule-cards changes the trajectory, and the
rules it controls are never edited.

Under the attribute substrate (D8): the counter is an attribute `counter`;
the budget is a singleton `limit`; a rule card is a `rule_card` entity
carrying `hash`/`name`/`reads`/`writes`; a control is a `rule_control` entity.
"""

from __future__ import annotations

from loopingrules import memory, reflect

from loopingrules_calibration.kit import Scenario, replay


def bump(w) -> None:
    """Increment `counter` every tick. Unbounded on purpose: with no
    controller the world never settles. NEVER edited to be controllable."""
    for entity, value in w.each("counter"):
        w.set(entity, "counter", value + 1)


def freeze_prolific(w) -> None:
    """The controller: read the firing history (`remembered`) and the rule
    catalog (`rule_card`), and disable the rule that writes `counter` once it
    has fired `limit` times. Identifies its target by STRUCTURE, never by a
    hard-coded name. Monotone."""
    budget = w.first("limit")
    if budget is None:
        return
    fired = {}
    for _entity, _t, rule in w.each("remembered", "rule"):
        if rule is not None:
            fired[rule] = fired.get(rule, 0) + 1
    for entity, _t, h, name, written in w.each("rule_card", "hash", "name",
                                               "writes"):
        if "counter" not in written:
            continue
        times = fired.get(name, 0)
        reflect.control(w, h, enabled=times < budget[1])


def flip_flop(w) -> None:
    """A DELIBERATELY bad controller -- the oscillation hazard, pinned. It
    inverts the target rule's `enabled` every tick, so the world never
    settles and the loop reports it `hot`."""
    for _entity, _t, h, written in w.each("rule_card", "hash", "writes"):
        if "counter" not in written:
            continue
        enabled = True
        for _c, _ct, ch, ce in w.each("rule_control", "hash", "enabled"):
            if ch == h:
                enabled = ce
                break
        reflect.control(w, h, enabled=not enabled)


def build(loop, limit: int = 3, controller="prolific") -> None:
    """Install the probe: the counter rule, short-term memory, the chosen
    controller, and the reified rule cards."""
    counter = loop.world.spawn()
    loop.world.set(counter, "counter", 0)
    budget = loop.world.spawn()
    loop.world.set(budget, "limit", limit)
    if controller == "prolific":
        loop.rule(freeze_prolific, priority=100)
    elif controller == "flip":
        loop.rule(flip_flop, priority=100)
    elif controller is not None:                       # pragma: no cover
        raise ValueError("unknown controller %r" % (controller,))
    loop.rule(bump)
    memory.install(loop)
    reflect.reify(loop)


def install(loop, limit: int = 3):
    """The controlled installer the kit's `replay` drives."""
    build(loop, limit=limit, controller="prolific")


def install_uncontrolled(loop, limit: int = 3):
    build(loop, limit=limit, controller=None)


def install_oscillating(loop, limit: int = 3):
    build(loop, limit=limit, controller="flip")


def run(install_fn, limit: int = 3, budget: int = 200):
    """Replay the probe under `install_fn` and return the `Trace`."""
    return replay(Scenario(), install_fn, budget=budget)


def report():
    controlled = run(install)
    uncontrolled = run(install_uncontrolled)
    oscillating = run(install_oscillating)

    counter = controlled.world.first("counter")
    cards = {h: (reads, writes)
             for _e, _t, h, reads, writes in controlled.world.each(
                 "rule_card", "hash", "reads", "writes")}
    disabled = [h for _e, _t, h, en in controlled.world.each(
        "rule_control", "hash", "enabled") if not en]
    never_edited = bool(disabled) and all(
        "rule_control" not in cards[h][0] and "rule_control" not in cards[h][1]
        for h in disabled)
    return {
        "controlled": controlled,
        "uncontrolled": uncontrolled,
        "oscillating": oscillating,
        "counter_final": None if counter is None else counter[1],
        "never_edited": never_edited,
        "bad_controller_is_hot": bool(oscillating.hot),
        "ok": (not controlled.hot and bool(uncontrolled.hot)
               and bool(oscillating.hot) and never_edited),
    }


def main():
    result = report()
    print("== R0: reflection over memory and rule-cards", "=" * 30)
    print("  uncontrolled: ticks=%d hot=%r"
          % (result["uncontrolled"].ticks, list(result["uncontrolled"].hot)))
    print("  controlled:   ticks=%d hot=%r counter=%r"
          % (result["controlled"].ticks, list(result["controlled"].hot),
             result["counter_final"]))
    print("  oscillating:  ticks=%d hot=%r"
          % (result["oscillating"].ticks, list(result["oscillating"].hot)))
    print("  ALL AS EXPECTED:", result["ok"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
