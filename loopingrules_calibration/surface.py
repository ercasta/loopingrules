"""`loopingrules_calibration.surface` -- a rule's declared tunable surface,
written down next to the rule.

`docs/plan-calibration.md`: a pattern is not reusable until it exposes a
DECLARED tunable surface, and the declaration must sit next to the rule that
reads the component so it cannot drift from it. `@tunable(Knob(...))` binds
the knob(s) to the rule FUNCTION itself -- one opaque attribute, the same
trick `Loop.rule` already uses for the gate it derives from `analyze` -- and
`knobs(loop)` gathers a domain's whole surface from the rules it actually
registered. The engine never imports any of this: a knob parked on a
function is just data, so `loopingrules/` stays free of calibration and a
domain still declares its surface in its own module.

This does NOT replace the explicit knob list a tinkering experiment may
still pass to `search`; it is the surface those lists were standing in for.
A knob read by several rules may be declared on more than one of them --
`knobs(loop)` de-duplicates, because it is still one knob.
"""

from __future__ import annotations

from .kit import Knob

# Where `@tunable` parks a rule's knobs: a plain tuple on the function
# object, read by `declared` -- no registry, and no import back into the
# engine.
_ATTR = "_loopingrules_knobs"


def tunable(*declarations):
    """Declare the `Knob`(s) a rule is tunable over, ON the rule::

        @tunable(Knob(RiskTolerance, "max_level", 0.0, 1.0, steps=5))
        def flag_too_risky(w): ...

    Stackable -- `@tunable(a)` above `@tunable(b)` gives `(b, a)`. The
    arguments must be real `Knob`s: a typo that parked anything else there
    would make `knobs()` search a surface no rule reads, which is the one
    thing the declaration exists to prevent, so it is refused up front
    rather than discovered at tuning time.
    """
    declared_knobs = tuple(declarations)
    if not declared_knobs:
        raise ValueError("@tunable() needs at least one Knob")
    for knob in declared_knobs:
        if not isinstance(knob, Knob):
            raise TypeError(
                "@tunable() takes Knob instances, not %r" % (knob,))

    def decorate(fn):
        existing = tuple(getattr(fn, _ATTR, ()))
        fn._loopingrules_knobs = existing + declared_knobs
        return fn

    return decorate


def declared(fn) -> tuple:
    """The knobs `@tunable` declared on `fn`, in declaration order -- `()`
    for a rule that declares none."""
    return tuple(getattr(fn, _ATTR, ()))


def knobs(loop) -> tuple:
    """Every knob declared on any rule registered on `loop`, in registration
    order, de-duplicated by value: a knob shared by several rules and
    declared on more than one of them is still ONE knob."""
    out = []
    for _registered, fn in loop.rules:
        for knob in declared(fn):
            if knob not in out:
                out.append(knob)
    return tuple(out)


def runtime_knobs(surface) -> tuple:
    """The subset of `surface` whose `scope` is `"runtime"` -- the small,
    auditable set `docs/plan-adaptation.md` lets an online controller move,
    as opposed to the offline-only default frozen at deploy."""
    return tuple(knob for knob in surface if knob.scope == "runtime")
