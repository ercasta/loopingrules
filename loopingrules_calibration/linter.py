"""`loopingrules_calibration.linter` -- the tunability linter.

`docs/plan-calibration.md` states the product thesis -- a pattern is not
reusable until it exposes a declared tunable surface, and `docs/tuning.md`
states the design rule under it -- a tunable rule never hard-codes its
threshold; it reads a component. `analyze` already derives a rule's reads
from its own source; the same walk (`loopingrules.analyze.literals`) can
point at the numeric literal a tunable rule should have turned into a read.
This module is that check, run by an author or a CI step -- an explicit
tool, not `Loop.rule` at registration time, because the engine must not
learn about calibration.

Two postures, both taken from `analyze`:

* **Refuse rather than guess.** Only a rule that DECLARES a tunable surface
  (`@tunable`, see `.surface`) is linted at all -- a rule that exposes no
  surface is not this tool's business. Among those, a rule `analyze` cannot
  see is reported `unlintable`, never passed as clean: "I could not look"
  is not "there was nothing to find."
* **Explicit suppression, with a reason.** Some constants are structural,
  not calibration (`len(...) == 0`, a sentinel `0`). There are no silent
  auto-exclusions; the author excuses a literal through `lint(..., allow=)`
  with a reason, and every excuse is reported back. A suppression with no
  reason is refused.

This deliberately does NOT try to guess which literal is "really" a
threshold. It reports every numeric-literal comparison in a knobbed rule and
lets the author either make it a knob or excuse it -- the judgment
`docs/tuning.md` reserves for the author.
"""

from __future__ import annotations

import dataclasses

from loopingrules import analyze

from .surface import declared


@dataclasses.dataclass(frozen=True)
class Finding:
    """One hard-coded numeric literal in a rule that declares a tunable
    surface. `knobs` is that rule's own declared surface -- the candidates
    the literal should probably have read instead, or that the author must
    excuse through `lint(allow=...)`."""

    rule: str
    file: str
    line: int
    literal: object
    expression: str
    knobs: tuple


@dataclasses.dataclass(frozen=True)
class LintReport:
    """The result of `lint`. `findings` are the flagged literals;
    `unlintable` is `(rule, reason)` for a knobbed rule `analyze` refused to
    see; `suppressed` records every excused literal AND its reason, so an
    excuse is as visible as a finding; `checked` names the rules that
    declared a surface and linted clean."""

    findings: tuple
    unlintable: tuple
    suppressed: tuple
    checked: tuple

    @property
    def clean(self) -> bool:
        """True when nothing was found AND nothing was unlintable -- a
        suppression is a deliberate, reasoned decision and does not make the
        report unclean."""
        return not self.findings and not self.unlintable

    def to_markdown(self) -> str:
        """A short, human-readable rendering. The structured fields are the
        artifact; this is for reading."""
        out = ["# Tunability lint", ""]
        if self.findings:
            out.append("## Hard-coded thresholds")
            out.append("")
            out.append("Turn each into a declared knob, or excuse it with "
                       "`lint(allow=...)` and a reason.")
            out.append("")
            out.append("| rule | site | literal | declared knobs |")
            out.append("|---|---|---|---|")
            for finding in self.findings:
                names = ", ".join(k.name for k in finding.knobs)
                out.append("| %s | `%s:%d` | `%r` | %s |" % (
                    finding.rule, finding.file, finding.line,
                    finding.literal, names))
            out.append("")
        else:
            out.append("No hard-coded thresholds in any rule that declares "
                       "a tunable surface.")
            out.append("")
        if self.unlintable:
            out.append("## Unlintable")
            out.append("")
            out.append("Declare a surface, but `analyze` refused to see the "
                       "rule -- not the same as clean.")
            out.append("")
            for name, reason in self.unlintable:
                out.append("- `%s`: %s" % (name, reason))
            out.append("")
        if self.suppressed:
            out.append("## Excused")
            out.append("")
            for name, literal, reason in self.suppressed:
                out.append("- `%s` `%r`: %s" % (name, literal, reason))
            out.append("")
        out.append("%d rule(s) linted clean." % len(self.checked))
        return "\n".join(out) + "\n"


class LintError(Exception):
    """Raised by `lint(..., strict=True)` when the report is not clean
    (`LintReport.clean` is False); `.report` carries it."""

    def __init__(self, report: LintReport) -> None:
        self.report = report
        super().__init__(
            "%d hard-coded threshold(s), %d unlintable rule(s)"
            % (len(report.findings), len(report.unlintable)))


def _rule_name(fn) -> str:
    """`fs.flag_big` -- the same `module.function` name `Loop` uses, so a
    finding names the rule the way `/rules` would."""
    module = getattr(fn, "__module__", "") or ""
    return "%s.%s" % (module.rsplit(".", 1)[-1],
                      getattr(fn, "__name__", "rule"))


def lint(rules, allow=(), strict: bool = False) -> LintReport:
    """Lint `rules` -- a `Loop`, or an iterable of rule functions -- for
    hard-coded numeric literals.

    Only rules that declare a tunable surface (`@tunable`) are examined;
    every other rule is skipped, so this reports on exactly the rules an
    author has claimed are calibration targets.

    `allow` excuses specific literals, each entry `(rule, literal, reason)`
    where `rule` is the function itself (matched by identity) or its
    `module.function` name, and `reason` must be a non-empty string. An
    excused literal still appears under `LintReport.suppressed`.

    `strict=True` raises `LintError` when the report is not clean -- i.e.
    on any finding, or on any knobbed rule `analyze` could not see (a
    declared surface the linter is not allowed to skip). Reporting stays
    the default; the raise is opt-in, for a CI gate.
    """
    if hasattr(rules, "rules"):             # a Loop: use its own rules
        rules = [fn for _registered, fn in rules.rules]
    allowed = {}
    for entry in allow:
        rule, literal, reason = entry
        if not (isinstance(reason, str) and reason.strip()):
            raise ValueError(
                "every lint suppression needs a reason: %r" % (entry,))
        allowed[(id(rule) if callable(rule) else rule, literal)] = reason

    findings, unlintable, suppressed, checked = [], [], [], []
    for fn in rules:
        declared_knobs = declared(fn)
        if not declared_knobs:
            continue                        # no declared surface: not our job
        name = _rule_name(fn)
        try:
            sites = analyze.literals(fn)
        except analyze.Opaque as exc:
            unlintable.append((name, str(exc)))
            continue
        clean = True
        for site in sites:
            reason = allowed.get((id(fn), site.value))
            if reason is None:
                reason = allowed.get((name, site.value))
            if reason is not None:
                suppressed.append((name, site.value, reason))
                continue
            clean = False
            findings.append(Finding(name, site.file, site.line, site.value,
                                    site.expression, declared_knobs))
        if clean:
            checked.append(name)
    report = LintReport(tuple(findings), tuple(unlintable),
                        tuple(suppressed), tuple(checked))
    if strict and not report.clean:
        raise LintError(report)
    return report
