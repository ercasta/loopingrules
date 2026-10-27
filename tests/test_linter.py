"""`loopingrules_calibration.linter`, and the `analyze.literals` walk it is
built on. These tests pin the properties the product thesis leans on: a
tunable rule that reads its knob is clean, one that hard-codes a threshold is
flagged at the right site, a comparison of two literals is not a threshold, an
unanalyzable knobbed rule is reported (never passed as clean), and a
suppression is accepted only with a reason.
"""

import dataclasses

import pytest

from examples import judge
from loopingrules import analyze
from loopingrules.loop import Loop
from loopingrules_calibration import (
    Knob,
    LintError,
    declared,
    knobs,
    lint,
    runtime_knobs,
    tunable,
)


@dataclasses.dataclass(frozen=True)
class Threshold:
    level: float


@dataclasses.dataclass(frozen=True)
class Reading:
    value: float


@dataclasses.dataclass(frozen=True)
class Over:
    pass


_LIMIT = Knob(Threshold, "level", 0.0, 1.0, steps=5)


@tunable(_LIMIT)
def hard_coded(w):
    for entity, reading in w.each(Reading):
        if reading.value > 0.6:
            w.attach(entity, Over())


@tunable(_LIMIT)
def reads_knob(w):
    tolerance = w.the(Threshold)
    for entity, reading in w.each(Reading):
        if reading.value > tolerance.level:
            w.attach(entity, Over())


@tunable(_LIMIT)
def sentinel(w):
    for entity, reading in w.each(Reading):
        if reading.value == 0:
            w.attach(entity, Over())


@tunable(_LIMIT)
def two_literals(w):
    for entity, reading in w.each(Reading):
        if reading.value > 0.6:
            w.attach(entity, Over())
        if reading.value < 0.2:
            w.attach(entity, Over())


@tunable(_LIMIT)
def only_literal_comparison(w):
    if 1 < 2:
        for entity, reading in w.each(Reading):
            w.attach(entity, Over())


@tunable(_LIMIT)
def bool_compare(w):
    for entity, reading in w.each(Reading):
        if reading.value > True:
            w.attach(entity, Over())


@tunable(_LIMIT)
def unlintable(w):
    other = w                       # store the world parameter: outside the dialect
    other.spawn(Over())


def plain(w):
    """No declared surface, but a hard-coded threshold -- which the linter is
    not entitled to flag, because the rule never claimed to be tunable."""
    for entity, reading in w.each(Reading):
        if reading.value > 0.6:
            w.attach(entity, Over())


# -- analyze.literals -----------------------------------------------------

def test_literals_reports_a_numeric_threshold_at_its_real_line():
    sites = analyze.literals(hard_coded)
    assert len(sites) == 1
    site = sites[0]
    assert site.value == 0.6
    assert site.expression == "reading.value > 0.6"
    assert site.file.endswith("test_linter.py")
    assert site.line > 0                     # a real line, decorator-aware


def test_literals_is_empty_when_the_rule_reads_its_knob_component():
    assert analyze.literals(reads_knob) == ()


def test_literals_ignores_a_comparison_of_two_literals():
    assert analyze.literals(only_literal_comparison) == ()


def test_literals_reports_multiple_sites_in_source_order():
    sites = analyze.literals(two_literals)
    assert [site.value for site in sites] == [0.6, 0.2]
    assert sites[0].line < sites[1].line


def test_literals_treats_a_bool_as_not_numeric():
    assert analyze.literals(bool_compare) == ()


def test_literals_refuses_an_unanalyzable_rule_rather_than_guessing():
    with pytest.raises(analyze.Opaque):
        analyze.literals(unlintable)


# -- the declared surface (@tunable / declared / knobs) -------------------

def test_tunable_attaches_and_declared_reads_back():
    assert declared(hard_coded) == (_LIMIT,)


def test_a_rule_with_no_declaration_has_an_empty_surface():
    assert declared(plain) == ()


def test_stacked_tunable_keeps_declaration_order():
    first = Knob(Reading, "value", 0.0, 1.0)
    second = Knob(Threshold, "level", 0.0, 1.0)

    @tunable(first)
    @tunable(second)
    def stacked(w):
        w.each(Reading)

    assert declared(stacked) == (second, first)


def test_tunable_refuses_a_non_knob():
    with pytest.raises(TypeError):
        @tunable("max_level")
        def _(w):
            pass


def test_tunable_needs_at_least_one_knob():
    with pytest.raises(ValueError):
        tunable()


def test_knobs_collects_from_a_loop_and_dedupes():
    loop = Loop()
    loop.rule(hard_coded)
    loop.rule(reads_knob)               # the same knob declared again
    assert knobs(loop) == (_LIMIT,)


def test_runtime_knobs_keeps_only_the_runtime_scope():
    live = Knob(Threshold, "level", 0.0, 1.0, steps=5, scope="runtime")
    assert runtime_knobs((_LIMIT, live)) == (live,)
    assert runtime_knobs((_LIMIT,)) == ()


# -- lint -----------------------------------------------------------------

def test_lint_flags_a_hard_coded_threshold_at_the_right_site():
    report = lint([hard_coded])
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.rule == "test_linter.hard_coded"
    assert finding.literal == 0.6
    assert finding.expression == "reading.value > 0.6"
    assert finding.file.endswith("test_linter.py")
    assert finding.knobs == (_LIMIT,)
    assert not report.clean


def test_lint_passes_a_rule_that_reads_its_knob():
    report = lint([reads_knob])
    assert report.findings == ()
    assert report.checked == ("test_linter.reads_knob",)
    assert report.clean


def test_lint_skips_a_rule_with_no_declared_surface():
    report = lint([plain])
    assert report.findings == ()
    assert report.checked == ()         # not examined at all: no surface claimed
    assert report.clean


def test_lint_reports_a_knobbed_rule_it_cannot_see_as_unlintable():
    report = lint([unlintable])
    assert report.findings == ()
    assert len(report.unlintable) == 1
    name, reason = report.unlintable[0]
    assert name == "test_linter.unlintable"
    assert reason                       # a real reason, not an empty string
    assert not report.clean             # "could not look" is not "clean"


def test_lint_flags_a_sentinel_zero_without_an_explicit_excuse():
    # The chosen posture: NO silent auto-exclusions, not even for 0.
    report = lint([sentinel])
    assert [finding.literal for finding in report.findings] == [0]
    assert not report.clean


def test_lint_excuses_a_literal_only_when_a_reason_is_given():
    reason = "0 is a sentinel, not a threshold"
    report = lint([sentinel], allow=((sentinel, 0, reason),))
    assert report.findings == ()
    assert report.suppressed == (("test_linter.sentinel", 0, reason),)
    assert report.clean


def test_lint_suppression_by_rule_name_also_works():
    report = lint([hard_coded],
                  allow=(("test_linter.hard_coded", 0.6, "authored default"),))
    assert report.findings == ()


def test_lint_refuses_a_suppression_without_a_reason():
    with pytest.raises(ValueError):
        lint([hard_coded], allow=((hard_coded, 0.6, "   "),))


def test_lint_accepts_a_loop():
    loop = Loop()
    loop.rule(hard_coded)
    report = lint(loop)
    assert report.findings
    assert report.findings[0].rule == "test_linter.hard_coded"


def test_lint_strict_raises_on_a_finding_and_carries_the_report():
    with pytest.raises(LintError) as raised:
        lint([hard_coded], strict=True)
    assert raised.value.report.findings


def test_lint_strict_raises_on_an_unlintable_knobbed_rule():
    with pytest.raises(LintError):
        lint([unlintable], strict=True)


def test_lint_strict_passes_a_clean_surface():
    report = lint([reads_knob], strict=True)
    assert report.clean


def test_lint_markdown_names_the_site_the_literal_and_the_knob():
    text = lint([hard_coded]).to_markdown()
    assert "Hard-coded thresholds" in text
    assert "test_linter.py" in text
    assert "0.6" in text
    assert "Threshold.level" in text


# -- the real bridge rule the linter is meant to defend -------------------

def test_the_real_judge_rule_declares_its_knob_and_lints_clean():
    assert declared(judge.flag_too_risky)
    report = lint([judge.flag_too_risky])
    assert report.clean
    assert report.checked == ("judge.flag_too_risky",)
