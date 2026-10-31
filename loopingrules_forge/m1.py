"""M1 -- the gates, and the proof that each one CAN fail.

Run: `python -m loopingrules_forge.m1`

`docs/plan-forge.md`'s verification spine. Before any LLM or corpus exists,
the gates that will judge generated structure must be shown *strong enough to
reject wrong structure and quiet enough to accept right structure*. That is
all this file does -- it is the "a check that cannot fail is not a check"
device (`docs/plan-forge.md`, adversarial probes).

Six gates, each a pure function over a candidate (a lowered module with
provenance), each returning `Finding`s:

    shape        every rule is in `analyze`'s dialect and uses only
                 catalog-declared components
    coherence    every component a rule reads is written by a rule, or the
                 catalog declares it seeded / edge-in (M0's open finding)
    tunability   no hard-coded threshold in a rule that declares a knob
                 (`loopingrules_calibration.lint`)
    provenance   every artifact cites a corpus span
    determinism  two replays of the candidate agree
    behaviour    the candidate settles, and reproduces the reference signature

Then a set of MUTANTS: for each, one deliberate breakage whose *expected*
gate must fire. The clean module and a benign variant must trip nothing --
a gate that rejects a right answer is as useless as one that accepts a wrong.
"""

from __future__ import annotations

import collections
import dataclasses

import loopingrules.analyze as analyze
from loopingrules_calibration import Knob, Scenario, lint, replay, tunable
from loopingrules_patterns.judge import Risk, RiskTolerance, TooRisky, flag_too_risky

from examples import cards
from loopingrules_forge import m0
from loopingrules_forge.fixtures import Ghost, Orphan   # noqa: F401

Finding = collections.namedtuple("Finding", "gate artifact detail")

ORIGIN_RULE, ORIGIN_SEED, ORIGIN_IN, ORIGIN_OUT = "rule", "seed", "in", "out"

GATES = ("shape", "coherence", "tunability", "provenance", "determinism",
         "behaviour")

_SCENARIO = Scenario(lines=m0.LINES)


# ---------------------------------------------------------------------
# The catalog: components, and where each is produced (M0's open finding)
# ---------------------------------------------------------------------
#
# A component a rule reads with no in-rule writer is only a *gap* if nothing
# declares it seeded (install) or edge-in (a channel). Folding that in is
# what stops "read but never written" from being noise -- see the M0 result.

@dataclasses.dataclass(frozen=True)
class Catalog:
    components: frozenset
    origins: dict                       # type -> str

    def known(self, kind) -> bool:
        return kind in self.components

    def origin(self, kind) -> str:
        return self.origins.get(kind, ORIGIN_RULE)


def cards_catalog() -> Catalog:
    report = analyze.component_map(*cards.RULES)
    comps = set(report.reads) | set(report.writes)
    origins = {kind: ORIGIN_RULE for kind in comps}
    for kind in (cards.CardDef, cards.RiskProfile, RiskTolerance):
        origins[kind] = ORIGIN_SEED          # read, never *rule*-written
    origins[cards.Said] = ORIGIN_IN          # arrives on a channel
    origins[cards.Reply] = ORIGIN_OUT        # leaves on a channel
    comps |= {cards.CardDef, cards.RiskProfile, RiskTolerance, cards.Said,
              cards.Reply, Orphan}
    return Catalog(frozenset(comps), origins)


def _rname(fn) -> str:
    module = getattr(fn, "__module__", "") or ""
    return "%s.%s" % (module.rsplit(".", 1)[-1],
                      getattr(fn, "__name__", "rule"))


# ---------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------

def gate_shape(catalog, functions):
    findings = []
    for fn in functions:
        name = _rname(fn)
        try:
            analysis = analyze.analyze(fn)
        except analyze.Opaque as exc:
            findings.append(Finding("shape", name, "opaque: %s" % exc))
            continue
        for kind in analysis.reads | analysis.writes:
            if not catalog.known(kind):
                findings.append(Finding(
                    "shape", name, "undeclared component %s" % kind.__name__))
    return findings


def gate_coherence(catalog, functions):
    reads, writes = set(), set()
    for fn in functions:
        try:
            analysis = analyze.analyze(fn)
        except analyze.Opaque:
            continue                    # shape already reported it
        reads |= analysis.reads
        writes |= analysis.writes
    findings = []
    for kind in sorted(reads, key=lambda k: k.__name__):
        if kind in writes:
            continue
        if catalog.origin(kind) in (ORIGIN_SEED, ORIGIN_IN):
            continue
        findings.append(Finding(
            "coherence", kind.__name__,
            "read by a rule, no rule writes it, and the catalog does not "
            "declare it seeded or edge-in"))
    return findings


def gate_tunability(functions):
    report = lint(functions)
    findings = [Finding("tunability", finding.rule,
                        "hard-coded literal %r at %s:%d"
                        % (finding.literal, finding.file, finding.line))
                for finding in report.findings]
    findings += [Finding("tunability", name, "unlintable: %s" % why)
                 for name, why in report.unlintable]
    return findings


def gate_provenance(provenance, expected):
    return [Finding("provenance", name, "no corpus span")
            for name in expected if not provenance.get(name)]


def gate_determinism(install, scenario=_SCENARIO):
    first = replay(scenario, install)
    second = replay(scenario, install)
    if m0.signature(first.world, first.fired) != \
            m0.signature(second.world, second.fired):
        return [Finding("determinism", None, "two replays disagree")]
    return []


def gate_behaviour(reference, candidate, scenario=_SCENARIO):
    ref = replay(scenario, reference)
    cand = replay(scenario, candidate)
    if cand.hot:
        return [Finding("behaviour", "settle",
                        "did not settle: hot %r after %d ticks"
                        % (list(cand.hot), cand.ticks))]
    if m0.signature(ref.world, ref.fired) != \
            m0.signature(cand.world, cand.fired):
        return [Finding("behaviour", "equivalence",
                        "signature differs from the reference")]
    return []


# ---------------------------------------------------------------------
# A candidate: a lowered module + provenance
# ---------------------------------------------------------------------

@dataclasses.dataclass
class Candidate:
    label: str
    source: str
    wanted: str                 # the gate that MUST fire, or "" to be clean
    extra: tuple = ()           # extra rule names to register and check
    spanning: bool = True       # False -> drop a provenance span (mutant)

    def module(self):
        return m0.load_emitted(self.source, name="forge_%s" % self.label)

    def functions(self):
        module = self.module()
        fns = [getattr(module, n) for n in m0.ORDER if hasattr(module, n)]
        fns += [getattr(module, n) for n in self.extra]
        fns.append(flag_too_risky)          # the imported judge rule
        return fns

    def provenance(self):
        if not self.spanning:
            return {n: "span:%d" % i for i, n in enumerate(m0.ORDER[:-1])}
        return {n: "span:%d" % i for i, n in enumerate(m0.ORDER)}

    def install(self):
        module = self.module()

        def _install(loop, cash=100):
            for name in m0.ORDER:
                if hasattr(module, name):
                    loop.rule(getattr(module, name))
                elif name == "flag_too_risky":
                    loop.rule(flag_too_risky)
            for name in self.extra:
                loop.rule(getattr(module, name))
            m0._seed(loop, cash)
        return _install


def check(candidate, catalog):
    findings = []
    findings += gate_shape(catalog, candidate.functions())
    findings += gate_coherence(catalog, candidate.functions())
    findings += gate_tunability(candidate.functions())
    findings += gate_provenance(candidate.provenance(), m0.ORDER)
    findings += gate_determinism(candidate.install())
    findings += gate_behaviour(clean_install(), candidate.install())
    return findings


# ---------------------------------------------------------------------
# The clean candidate, and a benign (semantically identical) variant
# ---------------------------------------------------------------------

def clean_source():
    return m0.emit_module()


def clean_install():
    return Candidate("clean", clean_source(), "").install()


def _fair_priced_identity_add():
    """`(1 + max_premium)` written as `((1 + 0) + max_premium)` -- same
    value, different shape. A RIGHT variant the gates must ACCEPT."""
    risk = m0.var("risk")
    return [
        m0.let("risk", m0.w_the(m0.RiskProfile)),
        m0.each_for([m0.Listing], ("entity", "listing"), [
            m0.let("card_def", m0.w_get(m0.attr(m0.var("listing"), "card"),
                                        m0.CardDef)),
            m0.if_(m0.isnone(m0.var("card_def")),
                   [m0.detach(m0.var("entity"), m0.FairPriced), m0.cont()]),
            m0.let("limit", m0.binop(
                "*", m0.attr(m0.var("card_def"), "value"),
                m0.binop("+", m0.binop("+", m0.const(1), m0.const(0)),
                         m0.attr(risk, "max_premium")))),
            m0.if_(m0.cmp("<=", m0.attr(m0.var("listing"), "price"),
                          m0.var("limit")),
                   [m0.attach(m0.var("entity"), m0.FairPriced)],
                   [m0.detach(m0.var("entity"), m0.FairPriced)]),
        ]),
    ]


def benign_source():
    rules = dict(m0.IR)
    rules["tag_fair_priced"] = _fair_priced_identity_add
    return m0.emit_module(rules=rules)


def _wrong_reply_goal_met():
    """Right shape, wrong text -- only the behaviour gate can tell."""
    return [
        m0.each_for([m0.GoalMet], ("entity", "_goal"), [
            m0.attach(m0.var("entity"), m0.Announced),
            m0.spawn(m0.Reply, {"channel": m0.const("user"),
                                "text": m0.const("done")}),
        ], without=[m0.Announced]),
    ]


# ---------------------------------------------------------------------
# The mutants
# ---------------------------------------------------------------------

EXTRA_GHOST = """
from loopingrules_forge.fixtures import Ghost


def ghost_rule(w):
    for entity, listing in w.each(Listing):
        w.attach(entity, Ghost(n=0))
"""

EXTRA_OPAQUE = """
def sneaky(w):
    reader = w
    for entity, listing in reader.each(Listing):
        w.detach(entity, Wanted)
"""

EXTRA_LITERAL = """
from loopingrules_calibration import Knob, tunable


@tunable(Knob(RiskTolerance, "max_level", 0.0, 1.0, steps=5))
def risky_literal(w):
    for entity, risk in w.each(Risk):
        if risk.level > 0.8:
            w.attach(entity, TooRisky())
        else:
            w.detach(entity, TooRisky)
"""

EXTRA_ORPHAN = """
from loopingrules_forge.fixtures import Orphan


def orphan_rule(w):
    for entity, orphan in w.each(Orphan):
        w.attach(entity, Wanted())
"""

EXTRA_CHURN = """
def churn(w):
    w.spawn(GoalMet())
"""

EXTRA_STATEFUL = """
_COUNTER = [0]


def stateful(w):
    _COUNTER[0] += 1
    if _COUNTER[0] == 1:
        w.spawn(BadCommand(text="x", why="y"))
"""


def candidates():
    clean = clean_source()
    return [
        Candidate("clean", clean, ""),
        Candidate("benign", benign_source(), ""),
        Candidate("ghost", clean + EXTRA_GHOST, "shape", extra=("ghost_rule",)),
        Candidate("opaque", clean + EXTRA_OPAQUE, "shape", extra=("sneaky",)),
        Candidate("literal", clean + EXTRA_LITERAL, "tunability",
                  extra=("risky_literal",)),
        Candidate("orphan", clean + EXTRA_ORPHAN, "coherence",
                  extra=("orphan_rule",)),
        Candidate("spanless", clean, "provenance", spanning=False),
        Candidate("churn", clean + EXTRA_CHURN, "behaviour", extra=("churn",)),
        Candidate("stateful", clean + EXTRA_STATEFUL, "determinism",
                  extra=("stateful",)),
        Candidate("wrong-reply",
                  m0.emit_module(rules={**m0.IR,
                                        "reply_goal_met": _wrong_reply_goal_met}),
                  "behaviour"),
    ]


# ---------------------------------------------------------------------
# Run them all
# ---------------------------------------------------------------------

def run_all():
    catalog = cards_catalog()
    rows = []
    ok = True
    for candidate in candidates():
        findings = check(candidate, catalog)
        fired = {f.gate for f in findings}
        if candidate.wanted == "":
            passed = not findings
        else:
            passed = candidate.wanted in fired
        ok = ok and passed
        rows.append((candidate.label, candidate.wanted, sorted(fired), passed,
                     findings))
    return ok, rows


def main():
    print("== M1: the gates", "=" * 46)
    print("  scenario lines:", ", ".join(repr(x) for x in m0.LINES))
    print("  reference signature:", m0.signature(
        replay(_SCENARIO, clean_install()).world,
        replay(_SCENARIO, clean_install()).fired)[:12], "...")
    print()
    print("  %-12s %-12s %-28s %s" % ("CANDIDATE", "MUST FIRE", "FIRED", "OK"))
    ok, rows = run_all()
    for label, wanted, fired, passed, findings in rows:
        print("  %-12s %-12s %-28s %s" % (
            label, wanted or "(clean)", ", ".join(fired) or "-",
            "ok" if passed else "FAIL"))
        for finding in findings:
            print("        %s: %s -- %s" % (finding.gate, finding.artifact,
                                            finding.detail))
    print()
    print("  ALL AS EXPECTED:", ok)
    print("""
  Read it as: two RIGHT candidates (clean, benign) trip nothing; eight
  WRONG ones each trip their intended gate. The gates are therefore both
  able to reject wrong structure and quiet on right structure -- which is
  the whole claim M1 exists to test.""")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
