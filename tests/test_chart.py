"""`loopingrules.chart` -- `Intake`/`Span`/`Interpretation`, the
`Active`/`Countdown` quiescence signal `settle` maintains, `select`,
the generic covering-set winner search, and `promote`, the rule that
turns `select`'s own `Candidate` into `Definitive`. What's pinned: the
countdown really does take exactly two consecutive idle ticks to reach
`ready`, not one and not three; a rule that keeps marking `Active`
never lets it fire; `select` picks the highest-scoring combination that
covers every word, allowing overlap; an `Ignorable` interpretation
fills a gap without contributing score; no covering combination means
no `Candidate` at all, not a guess; a standalone `Intake` promotes a
`Candidate` to `Definitive` immediately, one that is `SentenceOf` a
`Discourse` waits for it; and `retract` undoes a `Candidate`/
`Definitive` and reopens exactly the windows that closing it once
closed, no more.
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
    chart.promote(w)
    assert w.first(chart.Definitive) is None


def test_a_single_interpretation_covering_everything_wins():
    w = World()
    intake = _intake(w, "a b c")
    entity = _reading(w, intake, 0, 2, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    chart.promote(w)
    assert w.has(entity, chart.Definitive)


def test_two_adjacent_interpretations_together_cover_and_win():
    w = World()
    intake = _intake(w, "a b c d")
    first = _reading(w, intake, 0, 1, score=1.0)
    second = _reading(w, intake, 2, 3, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    chart.promote(w)
    assert w.has(first, chart.Definitive)
    assert w.has(second, chart.Definitive)


def test_a_reading_that_leaves_a_gap_never_wins_alone():
    w = World()
    intake = _intake(w, "a b c d")
    partial = _reading(w, intake, 0, 1, score=100.0)   # huge score, but leaves c/d uncovered
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    chart.promote(w)
    assert w.has(partial, chart.Definitive) is False


def test_no_covering_combination_leaves_nothing_definitive():
    w = World()
    intake = _intake(w, "a b c")
    _reading(w, intake, 0, 1, score=5.0)   # never covers word 2, alone or combined
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    chart.promote(w)
    assert w.first(chart.Definitive) is None


def test_overlapping_interpretations_may_both_win_if_the_combination_scores_highest():
    w = World()
    intake = _intake(w, "a b c")
    whole = _reading(w, intake, 0, 2, score=1.0)
    overlapping = _reading(w, intake, 1, 2, score=1.0)   # overlaps `whole`, adds nothing to coverage
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    chart.promote(w)
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
    chart.promote(w)
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
    chart.promote(w)
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
    chart.promote(w)
    assert w.has(first_reading, chart.Definitive) is True
    assert w.has(second_partial, chart.Definitive) is False


# -- promote: candidate is provisional, definitive is not --------------

def test_select_alone_never_attaches_definitive():
    w = World()
    intake = _intake(w, "a b")
    entity = _reading(w, intake, 0, 1, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(entity, chart.Candidate) is True
    assert w.has(entity, chart.Definitive) is False


def test_promote_is_immediate_for_a_standalone_intake():
    w = World()
    intake = _intake(w, "a b")
    entity = _reading(w, intake, 0, 1, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    chart.promote(w)
    assert w.has(entity, chart.Candidate) is True   # promote adds Definitive, does not remove Candidate
    assert w.has(entity, chart.Definitive) is True


def test_promote_waits_for_its_discourse_to_be_ready():
    """A `Candidate` on a sentence-of-a-discourse `Intake` is not
    promoted to `Definitive` until the `Discourse` itself has been
    quiet for two idle ticks -- `attach_sentence`'s own `mark_active`
    is the activity being waited out, the same reset-then-two-idle-
    ticks shape `test_marking_active_resets_the_countdown` already
    pins for a plain `Intake`."""
    w = World()
    discourse = w.spawn(chart.Discourse("one sentence, for now"))
    intake = _intake(w, "a b")
    chart.attach_sentence(w, intake, discourse, 0)
    entity = _reading(w, intake, 0, 1, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    assert w.has(entity, chart.Candidate) is True

    chart.promote(w)
    assert w.has(entity, chart.Definitive) is False   # discourse's countdown hasn't even reset yet

    chart.settle(w, kind=chart.Discourse)             # consumes attach_sentence's own mark_active
    chart.promote(w)
    assert w.has(entity, chart.Definitive) is False

    chart.settle(w, kind=chart.Discourse)             # 1st idle tick
    chart.promote(w)
    assert w.has(entity, chart.Definitive) is False

    chart.settle(w, kind=chart.Discourse)             # 2nd idle tick: discourse ready
    chart.promote(w)
    assert w.has(entity, chart.Definitive) is True


# -- retract: undoing a Candidate/Definitive reopens both windows ------

def test_retract_reopens_the_intake_and_discourse_windows():
    w = World()
    discourse = w.spawn(chart.Discourse("about to be reinterpreted"))
    intake = _intake(w, "a b")
    chart.attach_sentence(w, intake, discourse, 0)
    entity = _reading(w, intake, 0, 1, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    for _ in range(3):
        chart.settle(w, kind=chart.Discourse)
    chart.promote(w)
    assert w.has(entity, chart.Definitive) is True

    assert chart.retract(w, entity, intake, discourse) is True
    assert w.has(entity, chart.Candidate) is False
    assert w.has(entity, chart.Definitive) is False

    # one settle each is enough to prove the window reopened: without
    # retract's own mark_active, an already-ready entity stays ready
    # (its countdown only ever goes MORE negative on an idle tick); the
    # reset branch is the only way `ready` flips back to False here.
    chart.settle(w)
    chart.settle(w, kind=chart.Discourse)
    assert chart.ready(w, intake) is False
    assert chart.ready(w, discourse) is False


def test_retract_returns_false_and_reopens_nothing_if_there_was_no_candidate():
    w = World()
    intake = _intake(w, "a b")
    entity = _reading(w, intake, 0, 1, score=1.0)
    chart.settle(w)
    chart.settle(w)
    assert chart.ready(w, intake) is True
    assert chart.retract(w, entity, intake) is False
    assert chart.ready(w, intake) is True   # nothing was there to retract, so nothing reopened


def test_reinterpretation_lets_a_downweighted_rival_lose_its_second_pass():
    """The full loop a cross-sentence rule would run: `retract` an
    earlier `Definitive` winner, down-weight it the same way any judge
    would, let a new rival in -- `select` then excludes the
    downweighted reading (see `test_a_negatively_scored_rival_is_
    excluded_when_it_would_drag_the_total_down`) and `promote` acts on
    the new winner once the discourse is quiet again."""
    w = World()
    discourse = w.spawn(chart.Discourse("first pass, then overturned"))
    intake = _intake(w, "a b")
    chart.attach_sentence(w, intake, discourse, 0)
    first = _reading(w, intake, 0, 1, score=1.0)
    chart.settle(w)
    chart.settle(w)
    chart.select(w)
    for _ in range(3):
        chart.settle(w, kind=chart.Discourse)
    chart.promote(w)
    assert w.has(first, chart.Definitive) is True

    chart.retract(w, first, intake, discourse)
    w.replace(first, chart.Interpretation(intake.id, -10.0))
    second = _reading(w, intake, 0, 1, score=5.0)

    for _ in range(3):
        chart.settle(w)
    chart.select(w)
    assert w.has(second, chart.Candidate) is True
    assert w.has(first, chart.Candidate) is False

    for _ in range(3):
        chart.settle(w, kind=chart.Discourse)
    chart.promote(w)
    assert w.has(second, chart.Definitive) is True
    assert w.has(first, chart.Definitive) is False


# -- read_vocabulary: matching tokens against registered words ---------

def test_read_vocabulary_matches_a_token_against_a_registered_word():
    w = World()
    intake = _intake(w, "train milan rome")
    stop = w.spawn(chart.Vocabulary("milan"))
    w.spawn(chart.Token(intake.id, 1, "milan"), chart.Span(1, 1))
    chart.read_vocabulary(w)
    matches = w.each(chart.Interpretation, chart.Matched)
    assert len(matches) == 1
    entity, interp, matched = matches[0]
    assert interp.utterance == intake.id
    assert matched.target == stop.id
    span = w.get(entity, chart.Span)
    assert (span.start, span.end) == (1, 1)


def test_read_vocabulary_normalizes_case_and_surrounding_space():
    w = World()
    intake = _intake(w, "downtown")
    w.spawn(chart.Vocabulary(" Downtown "))
    w.spawn(chart.Token(intake.id, 0, "DOWNTOWN"), chart.Span(0, 0))
    chart.read_vocabulary(w)
    assert w.first(chart.Matched) is not None


def test_read_vocabulary_ignores_a_token_with_no_matching_word():
    w = World()
    intake = _intake(w, "xyz")
    w.spawn(chart.Vocabulary("milan"))
    w.spawn(chart.Token(intake.id, 0, "xyz"), chart.Span(0, 0))
    chart.read_vocabulary(w)
    assert w.first(chart.Matched) is None


def test_read_vocabulary_marks_the_token_s_intake_active():
    w = World()
    intake = _intake(w, "milan")
    w.spawn(chart.Vocabulary("milan"))
    w.spawn(chart.Token(intake.id, 0, "milan"), chart.Span(0, 0))
    chart.read_vocabulary(w)
    assert w.has(intake, chart.Active) is True
