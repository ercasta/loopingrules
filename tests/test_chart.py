"""`loopingrules.chart` -- `Intake`/`Span`/`Interpretation`, the
`Active`/`Countdown` quiescence signal `settle` maintains, and `select`,
the generic covering-set winner search. What's pinned: the countdown
really does take exactly two consecutive idle ticks to reach `ready`,
not one and not three; a rule that keeps marking `Active` never lets it
fire; `select` picks the highest-scoring combination that covers every
word, allowing overlap; an `Ignorable` interpretation fills a gap
without contributing score; and no covering combination means no
`Definitive` at all, not a guess.
"""

from loopingrules import chart
from loopingrules.world import World


def _intake(w, text, length=None):
    words = text.split()
    return w.spawn(chart.Intake(text, length if length is not None else len(words)))


def _reading(w, intake, start, end, score=0.0, ignorable=False):
    components = [chart.Span(start, end), chart.Interpretation(intake.id, score)]
    if ignorable:
        components.append(chart.Ignorable())
    return w.spawn(*components)


# -- quiescence -------------------------------------------------------

def test_ready_is_false_before_any_countdown_exists():
    w = World()
    intake = _intake(w, "hello world")
    assert chart.ready(w, intake) is False


def test_two_idle_ticks_are_required_not_one_and_not_three():
    w = World()
    intake = _intake(w, "hello world")
    chart.settle(w)
    assert chart.ready(w, intake) is False   # one idle tick: not yet
    chart.settle(w)
    assert chart.ready(w, intake) is True    # two idle ticks: ready
    chart.settle(w)
    assert chart.ready(w, intake) is True    # stays ready, does not un-ready


def test_marking_active_resets_the_countdown():
    w = World()
    intake = _intake(w, "hello world")
    chart.settle(w)
    chart.settle(w)
    assert chart.ready(w, intake) is True
    chart.mark_active(w, intake)
    chart.settle(w)                          # this tick was active, not idle: reset
    assert chart.ready(w, intake) is False
    chart.settle(w)                          # 1st idle tick since the reset
    assert chart.ready(w, intake) is False
    chart.settle(w)                          # 2nd idle tick since the reset: ready again
    assert chart.ready(w, intake) is True


def test_a_rule_that_keeps_marking_active_never_reaches_ready():
    w = World()
    intake = _intake(w, "hello world")
    for _ in range(5):
        chart.mark_active(w, intake)
        chart.settle(w)
    assert chart.ready(w, intake) is False


def test_active_is_consumed_the_tick_settle_sees_it():
    w = World()
    intake = _intake(w, "hello world")
    chart.mark_active(w, intake)
    chart.settle(w)
    assert w.has(intake, chart.Active) is False


# -- select: coverage and scoring --------------------------------------

def test_select_does_nothing_before_ready():
    w = World()
    intake = _intake(w, "a b")
    _reading(w, intake, 0, 1, score=1.0)
    chart.select(w)
    assert w.first(chart.Definitive) is None


def test_a_single_interpretation_covering_everything_wins():
    w = World()
    intake = _intake(w, "a b c")
    entity = _reading(w, intake, 0, 2, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(entity, chart.Definitive)


def test_two_adjacent_interpretations_together_cover_and_win():
    w = World()
    intake = _intake(w, "a b c d")
    first = _reading(w, intake, 0, 1, score=1.0)
    second = _reading(w, intake, 2, 3, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(first, chart.Definitive)
    assert w.has(second, chart.Definitive)


def test_a_reading_that_leaves_a_gap_never_wins_alone():
    w = World()
    intake = _intake(w, "a b c d")
    partial = _reading(w, intake, 0, 1, score=100.0)   # huge score, but leaves c/d uncovered
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(partial, chart.Definitive) is False


def test_no_covering_combination_leaves_nothing_definitive():
    w = World()
    intake = _intake(w, "a b c")
    _reading(w, intake, 0, 1, score=5.0)   # never covers word 2, alone or combined
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.first(chart.Definitive) is None


def test_overlapping_interpretations_may_both_win_if_the_combination_scores_highest():
    w = World()
    intake = _intake(w, "a b c")
    whole = _reading(w, intake, 0, 2, score=1.0)
    overlapping = _reading(w, intake, 1, 2, score=1.0)   # overlaps `whole`, adds nothing to coverage
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    # both cover fully on their own; the combination of both scores higher (2.0) than either alone
    assert w.has(whole, chart.Definitive)
    assert w.has(overlapping, chart.Definitive)


def test_a_negatively_scored_rival_is_excluded_when_it_would_drag_the_total_down():
    """Overlap is free, so a redundant NON-negative reading is never
    excluded (adding it never lowers the total) -- the only way this
    search actually chooses between rivals is a NEGATIVE score, the
    shape a judge that downweighted a reading it disfavors would
    produce. `downweighted` covers the utterance on its own, same as
    `favored`; combining both scores LOWER than `favored` alone, so the
    best combination excludes it."""
    w = World()
    intake = _intake(w, "a b")
    favored = _reading(w, intake, 0, 1, score=5.0)
    downweighted = _reading(w, intake, 0, 1, score=-3.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(favored, chart.Definitive) is True
    assert w.has(downweighted, chart.Definitive) is False


def test_ignorable_fills_a_gap_without_contributing_score():
    w = World()
    intake = _intake(w, "please a b")
    filler = _reading(w, intake, 0, 0, score=0.0, ignorable=True)
    meaningful = _reading(w, intake, 1, 2, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(filler, chart.Definitive)
    assert w.has(meaningful, chart.Definitive)


def test_two_utterances_in_one_world_are_resolved_independently():
    w = World()
    first = _intake(w, "a b")
    second = _intake(w, "c d e")
    first_reading = _reading(w, first, 0, 1, score=1.0)
    second_partial = _reading(w, second, 0, 1, score=1.0)   # leaves word 2 of `second` uncovered
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(first_reading, chart.Definitive) is True
    assert w.has(second_partial, chart.Definitive) is False
