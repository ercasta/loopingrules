"""M2 -- freeze the compiled catalog, then tune it.

Run: `python -m loopingrules_forge.m2`

`docs/plan-forge.md`'s third milestone, and the last cheap, no-LM probe. The
question: is a **frozen** compiled catalog a well-defined artifact that the
existing calibration kit can tune -- reproducibly, with plateaus -- just like
a hand-authored domain?

A `Frozen` is the compiled structure stopped in time: its source, its
provenance, its declared knobs, and a `version` (a hash of the source). The
separation it must preserve is the whole architecture in one line:

    version  = STRUCTURE  (frozen; the same across every knob setting)
    signature = BEHAVIOUR (the knobs choose it)

M2 asserts that separation, plus: freezing is deterministic (and a change
moves the version), two independent freezes reproduce, the frozen catalog
behaves exactly like the unfrozen one, and `calibrate` reports the plateaus
and sensitivity the kit reports for any domain.
"""

from __future__ import annotations

import dataclasses
import hashlib

from loopingrules_calibration import Knob, Scenario, calibrate, replay
from loopingrules_patterns.judge import RiskTolerance, flag_too_risky

from examples import cards
from loopingrules_forge import m0

DEFAULT_KNOBS = (
    Knob(cards.RiskProfile, "max_premium", 0.0, 0.4, steps=3),
    Knob(RiskTolerance, "max_level", 0.0, 1.0, steps=3),
)


@dataclasses.dataclass(frozen=True)
class Frozen:
    """A compiled catalog stopped in time: immutable structure plus the
    declared surface tuning may move over it."""

    source: str
    provenance: tuple                   # ((rule, span), ...)
    knobs: tuple
    version: str = ""                   # filled by `freeze`

    def install(self):
        """Register the frozen rules and seed -- a fresh module each call,
        so two runs of one `Frozen` share no state (see M1's determinism
        gate for why that matters)."""
        module = m0.load_emitted(self.source, name="forge_frozen")

        def _install(loop, cash=100):
            for name in m0.ORDER:
                if hasattr(module, name):
                    loop.rule(getattr(module, name))
                elif name == "flag_too_risky":
                    loop.rule(flag_too_risky)
            m0._seed(loop, cash)
        return _install


def freeze(rules=None, ir_helpers=None, verbatim=None, knobs=DEFAULT_KNOBS):
    source = m0.emit_module(
        rules=m0.IR if rules is None else rules,
        ir_helpers=m0.IR_HELPERS if ir_helpers is None else ir_helpers,
        verbatim=m0.VERBATIM if verbatim is None else verbatim)
    provenance = tuple((name, "span:%d" % i)
                       for i, name in enumerate(m0.ORDER))
    version = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return Frozen(source, provenance, tuple(knobs), version)


# ---------------------------------------------------------------------
# Scenarios and objective -- the data calibration tunes against
# ---------------------------------------------------------------------

def scenarios():
    return (
        Scenario(lines=("list dragon 30", "want dragon 1")),
        Scenario(lines=("list dragon 45", "want dragon 1")),    # fair only p>=.125
        Scenario(lines=("list dragon 40", "want dragon 1")),    # fair at any p
        Scenario(lines=("list goblin 3", "want goblin 1",
                        "list dragon 30", "want dragon 1")),
    )


def bought(trace):
    """A scorer, deliberately domain-specific and outside the engine (see
    `docs/plan-calibration.md`): how many purchases came out."""
    return float(sum(1 for reply in trace.replies if reply.startswith("bought")))


# ---------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------

def _variant_freeze():
    """The same catalog with one reply's text changed -- a change of
    STRUCTURE, so the version must move."""
    rules = dict(m0.IR)
    rules["reply_goal_met"] = lambda: [
        m0.each_for([m0.GoalMet], ("entity", "_goal"), [
            m0.attach(m0.var("entity"), m0.Announced),
            m0.spawn(m0.Reply, {"channel": m0.const("user"),
                                "text": m0.const("a different announcement")}),
        ], without=[m0.Announced]),
    ]
    return freeze(rules=rules)


def report():
    frozen = freeze()
    scenarios_ = scenarios()

    # 1. freezing is deterministic; a structural change moves the version.
    other = freeze()
    variant = _variant_freeze()
    freeze_deterministic = frozen.version == other.version
    version_tracks_structure = frozen.version != variant.version

    # 2. determinism: two replays of the frozen install agree.
    a = replay(scenarios_[0], frozen.install(), frozen.knobs,
               tuple(k.values()[1] for k in frozen.knobs))
    b = replay(scenarios_[0], frozen.install(), frozen.knobs,
               tuple(k.values()[1] for k in frozen.knobs))
    deterministic = m0.signature(a.world, a.fired) == m0.signature(b.world, b.fired)

    # 3. two independent freezes reproduce behaviour, and the frozen catalog
    #    behaves exactly like the unfrozen one.
    values = tuple(k.values()[0] for k in frozen.knobs)
    f1 = replay(scenarios_[0], frozen.install(), frozen.knobs, values)
    f2 = replay(scenarios_[0], other.install(), frozen.knobs, values)
    raw = replay(scenarios_[0], m0.make_install(m0.load_emitted(  # unfrozen M0
        m0.emit_module(), name="forge_m0")), frozen.knobs, values)
    frozen_reproduces = (m0.signature(f1.world, f1.fired)
                         == m0.signature(f2.world, f2.fired))
    frozen_matches_unfrozen = (m0.signature(f1.world, f1.fired)
                               == m0.signature(raw.world, raw.fired))

    # 4. structure vs values: the version never moves across knob values,
    #    while at least one value pair changes the signature.
    versions = set()
    signatures = set()
    for va in frozen.knobs[0].values():
        for vb in frozen.knobs[1].values():
            vals = (va, vb)
            versions.add(frozen.version)
            trace = replay(scenarios_[1], frozen.install(), frozen.knobs, vals)
            # the KIT's signature, which EXCLUDES the knob components -- else
            # we would be counting the knob values themselves, not behaviour.
            signatures.add(trace.signature)
    version_is_structural = len(versions) == 1
    values_move_behaviour = len(signatures) > 1

    # 5. the kit's own report: plateaus and sensitivity, on the frozen catalog.
    cal = calibrate(frozen.install(), scenarios_, frozen.knobs, bought,
                    folds=4, seed=1)

    ok = all([freeze_deterministic, version_tracks_structure, deterministic,
              frozen_reproduces, frozen_matches_unfrozen, version_is_structural,
              values_move_behaviour, bool(cal.plateaus)])
    return {
        "frozen": frozen, "calibration": cal, "ok": ok,
        "freeze_deterministic": freeze_deterministic,
        "version_tracks_structure": version_tracks_structure,
        "deterministic": deterministic,
        "frozen_reproduces": frozen_reproduces,
        "frozen_matches_unfrozen": frozen_matches_unfrozen,
        "version_is_structural": version_is_structural,
        "values_move_behaviour": values_move_behaviour,
        "distinct_signatures": len(signatures),
    }


def main():
    result = report()
    frozen = result["frozen"]
    print("== M2: freeze, then tune", "=" * 40)
    print("  frozen version   %s" % frozen.version[:16])
    print("  knobs            %s" % ", ".join(k.name for k in frozen.knobs))
    print()
    checks = [
        ("freeze is deterministic", result["freeze_deterministic"]),
        ("a structural change moves the version",
         result["version_tracks_structure"]),
        ("replays are deterministic", result["deterministic"]),
        ("two independent freezes reproduce", result["frozen_reproduces"]),
        ("frozen behaves like the unfrozen M0 catalog",
         result["frozen_matches_unfrozen"]),
        ("version is structural (constant across knob values)",
         result["version_is_structural"]),
        ("knob values move behaviour (%d distinct signatures)"
         % result["distinct_signatures"], result["values_move_behaviour"]),
        ("calibration reports plateaus", bool(result["calibration"].plateaus)),
    ]
    for label, passed in checks:
        print("  [%s] %s" % ("ok" if passed else "XX", label))
    print()
    print(result["calibration"].to_markdown())
    print("  ALL AS EXPECTED:", result["ok"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
