"""R0 -- a rule over memory and rule-cards changes the trajectory, and the
rules it controls are never edited.

Run: `python -m loopingrules_reflect.r0`

`docs/plan-reflection.md`'s first probe. The claim it must falsify or hold:
that reflection is a real capability of the EXISTING substrate once rules are
reified as data -- not a new mechanism.

The demonstration is deliberately small and self-contained, so nothing about
`cards` can hide the mechanism:

* `bump` increments `Counter` every tick and, alone, never settles (a HOT
  loop -- the budget breaker runs out).
* `memory` is installed, so every firing of every rule lands as a durable
  `Remembered` -- "which rule fired" is world data (`loopingrules.memory`).
* `reflect.reify` deposits a `RuleCard` per rule -- "what each rule does" is
  world data (`RuleCard.writes` names the component types it writes).
* `freeze_prolific`, a controller, reads BOTH: it counts how often the rule
  that writes `Counter` has fired, and once that reaches `RunBudget.limit` it
  attaches `RuleControl(enabled=False)` for that rule's hash.

The three things this proves, each pinned by a test:

1. The controller tames the hot loop -- the run SETTLES, where the same
   `bump` without a controller stays hot.
2. `bump` is the SAME FUNCTION OBJECT in both runs; its source is not
   touched. Control is a component, read by the loop, not an edit.
3. A BAD controller -- one that toggles a rule's enable every tick, so the
   evidence it acts on flips because of its own action -- stays HOT, caught
   by the existing budget breaker. This is `docs/plan-adaptation.md`'s named
   oscillation failure mode, shown to survive as a failure here.

## What this does not settle

* **Credit assignment.** The controller here counts firings; it does not
  learn WHICH rule to control or by how much. Scoring a controller against a
  trajectory is the calibration kit's job (`docs/plan-calibration.md`), and
  the search over controller structure is the forge's (locked decision 12).
* **Flicker on a revisable controller.** `freeze_prolific` is monotone (once
  it disables, it stays disabled), so it settles trivially. A controller that
  re-enables is exactly the hazard `flip_flop` pins.
* **Multiple controllers, multi-knob coupling.** One controller, one rule
  controlled. Interaction between several is not probed (`docs/
  plan-adaptation.md`'s own open question).
"""

from __future__ import annotations

import dataclasses

from loopingrules import memory, reflect
from loopingrules.reflect import RuleCard, RuleControl

from loopingrules_calibration.kit import Scenario, replay


@dataclasses.dataclass(frozen=True)
class Counter:
    """The one number `bump` drives -- and the thing the controller watches
    to know the rule has fired, via `RuleCard.writes` naming this type."""

    value: int = 0


@dataclasses.dataclass(frozen=True)
class RunBudget:
    """How many times the counter rule may fire before the controller stops
    it. A component, not a literal, so the controller is tunable like any
    other rule (`docs/tuning.md`)."""

    limit: int = 3


def bump(w) -> None:
    """Increment `Counter` every tick. Unbounded on purpose: with no
    controller the world never settles, which is what the controller is for.
    This rule is NEVER edited to be controllable -- see the module note."""
    for entity, counter in w.each(Counter):
        w.replace(entity, Counter(counter.value + 1))


def freeze_prolific(w) -> None:
    """The controller: read the firing history (`Remembered`) and the rule
    catalog (`RuleCard`), and disable the rule that writes `Counter` once it
    has fired `RunBudget.limit` times.

    Identifies its target by STRUCTURE (`"Counter" in card.writes`), never by
    a hard-coded name, so it is a rule over rule-data rather than a rule that
    happens to know a string. Monotone: `enabled` is decided from a count
    that only grows, so it fires once and then re-emits an equal
    `RuleControl`, which `World.replace` dedupes -- the world settles.
    """
    budget = w.the(RunBudget)
    if budget is None:
        return
    fired = {}
    for _entity, entry in w.each(memory.Remembered):
        if entry.rule is not None:
            fired[entry.rule] = fired.get(entry.rule, 0) + 1
    for entity, card in w.each(RuleCard):
        if "Counter" not in card.writes:
            continue
        times = fired.get(card.name, 0)
        w.replace(entity, RuleControl(card.hash, enabled=times < budget.limit))


def flip_flop(w) -> None:
    """A DELIBERATELY bad controller -- the oscillation hazard, pinned.

    It inverts the target rule's `enabled` every tick, so the `RuleControl`
    it writes is always different from the last: the rule fires, the
    controller fires, forever. The world never settles and the loop reports
    it `hot`, which is the failure `docs/plan-adaptation.md` says fast
    adaptation must be watched for (hysteresis, a rate limit, bounds -- none
    of which this controller has)."""
    for entity, card in w.each(RuleCard):
        if "Counter" not in card.writes:
            continue
        control = w.get(entity, RuleControl)
        enabled = not (control.enabled if control is not None else True)
        w.replace(entity, RuleControl(card.hash, enabled=enabled))


def build(loop, limit: int = 3, controller="prolific") -> None:
    """Install the probe into `loop`: the counter rule, short-term memory (so
    firings are remembered), the chosen controller, and the reified rule
    cards. Order is load-bearing -- `reify` runs after every rule it should
    make visible is registered."""
    loop.world.spawn(Counter(0))
    loop.world.spawn(RunBudget(limit))
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

    counter = controlled.world.the(Counter)
    # Derived, not asserted: the disabled control names a rule whose own
    # card shows it neither reads nor writes `RuleControl` -- i.e. it was
    # never edited to be controllable.
    cards = {card.hash: card for _entity, card in controlled.world.each(RuleCard)}
    disabled = [control for _entity, control
                in controlled.world.each(RuleControl) if not control.enabled]
    never_edited = bool(disabled) and all(
        "RuleControl" not in cards[c.hash].reads
        and "RuleControl" not in cards[c.hash].writes for c in disabled)
    return {
        "controlled": controlled,
        "uncontrolled": uncontrolled,
        "oscillating": oscillating,
        "counter_final": None if counter is None else counter.value,
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
    checks = [
        ("a controller settles a loop that alone is hot",
         result["uncontrolled"].hot and not result["controlled"].hot),
        ("the controlled rule was never edited",
         result["never_edited"]),
        ("an oscillating controller stays hot (budget catches it)",
         result["bad_controller_is_hot"]),
    ]
    for label, passed in checks:
        print("  [%s] %s" % ("ok" if passed else "XX", label))
    print("  ALL AS EXPECTED:", result["ok"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
