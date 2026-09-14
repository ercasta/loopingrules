"""`chart` -- a chart of scored `Interpretation`s attached to `Span`s of
an utterance, one quiescence signal that tells a domain when the chart
has stopped moving, and `select`, the generic covering-set winner
search that marks the winning combination `Definitive`. See
`DECISION_PATTERNS.md`'s 2026-09-14 entry ("judges, closing 'Not built:
chart parsing' above") for the design this implements, the precedent it
is grounded against (`pystrider/spans.py`'s `Span`, `world.py`'s
`_Ripe`, `harneskills.examples.context`'s `_Recorded`), and what is
still genuinely open -- this module is the mechanical half of that
entry, not a restatement of its reasoning.

## The shape, in one pass

A domain spawns one `Intake(text, length)` per utterance. Its own
rules -- some reading raw `Span`s, some reading `Interpretation`s
other rules already attached, exactly the two tiers the design entry
describes -- spawn fresh entities, each carrying a `Span(start, end)`
(inclusive, 0-based word-token indices) ALONGSIDE an `Interpretation
(utterance, score)` and whatever component the domain's own reading
actually means (`AfterThreshold`, `Located`, ...) -- the same "a
marker plus whichever component would make it real" shape `loopingrules
.world.Proposal` already has for occasions, restated for a span
instead. Every one of those rules also calls `mark_active(w, intake)`
-- see `settle`, below, for why.

Once `ready(w, intake)` (two genuinely idle ticks, nothing `Active`),
domain-authored JUDGE rules may `w.replace` an `Interpretation`'s own
`score` -- a judge is a participating rule by the same test any other
one is, so it calls `mark_active` too, the same flag, not a second one
(see the design entry's own "quiescence is ONE signal, not two").
`select`, the one generic rule this module ships past `settle`, runs
once things are quiet again and picks the highest-scoring COMBINATION
of one `Intake`'s own `Interpretation`s whose `Span`s union-cover every
word position -- overlap allowed, no tiling required -- marking every
member of the winning combination `Definitive()`.

## Isolating tentative interpretations

A rule that composes bigger interpretations from smaller ones (an
`after_threshold`-shaped rule) keys on bare `Span`/`Interpretation` and
must never see `Definitive` -- attaching it is `select`'s own, and
ONLY `select`'s own, business. A rule that ACTS on a resolved reading
keys on `Interpretation` PLUS `Definitive`, the same `without=
NeedsApproval` shape `harneskills.examples.fs.do_rename` already uses,
renamed rather than reinvented. No new effect or engine mechanism is
needed for this split -- it is an ordinary component gate, the same as
every other "don't act on the tentative one" idiom this codebase
already has.
"""

from __future__ import annotations

import dataclasses
from typing import List, Optional, Tuple

#: What `Countdown.remaining` resets to the tick something is `Active`.
#: `1`, not `2`: `ready()` fires at `remaining <= -1`, so the first
#: idle tick after the last activity brings a fresh `1` down to `0`
#: (not yet ready), and the SECOND consecutive idle tick brings it to
#: `-1` -- "two ticks nothing new is added" is two DECREMENTS away from
#: a fresh reset, not two away from `-1` itself. A literal constant,
#: not yet a knob -- see the design entry's own "Left open" section for
#: why.
BASE_COUNTDOWN = 1


@dataclasses.dataclass(frozen=True)
class Intake:
    """One per utterance. `length` is the number of word-token
    positions `select`'s own coverage check must see covered -- word
    indices `0..length-1` inclusive. This module does not tokenize;
    `length` is whatever the domain's own tokenizer says it is."""

    text: str
    length: int


@dataclasses.dataclass(frozen=True)
class Span:
    """Which word positions an entity is about -- inclusive, 0-based.
    A raw fact some rule observed (one token) or derived by composing
    smaller `Span`s (an `AfterThreshold`-shaped rule's own two-token
    span) -- this component alone does not say what it MEANS; see
    `Interpretation`, always co-attached alongside it."""

    start: int
    end: int


@dataclasses.dataclass(frozen=True)
class Interpretation:
    """Attached ALONGSIDE `Span` (same entity) once some rule claims
    that span means something specific -- the domain's own meaning
    rides as a SEPARATE component on the same entity, never named
    here. `utterance` is the `Intake` this reading is for, a plain id
    (several utterances may be live in one `World` at once).

    `score` starts however the proposing rule sets it, and is the one
    field a domain-authored JUDGE may later `w.replace` -- what makes a
    good interpretation is left to the domain, the same split
    `loopingrules.world.arbitrate`/`census` already draw for "what
    makes a good candidate.\""""

    utterance: int
    score: float = 0.0


@dataclasses.dataclass(frozen=True)
class Ignorable:
    """Co-attached alongside `Span`/`Interpretation`, by a domain's own
    rule, for a span that is fine to skip -- a filler word ("please",
    "um") with no real meaning. Counts toward `select`'s coverage
    check the same as any other interpretation; contributes nothing to
    a combination's score, and is not otherwise treated specially --
    it wins or loses as part of the SAME combination as everything
    else, `Definitive` or not exactly like its neighbors."""


@dataclasses.dataclass(frozen=True)
class Definitive:
    """Attached by `select`, and ONLY by `select`, to every
    `Interpretation` entity that was part of the winning combination.
    See the module docstring, "Isolating tentative interpretations,"
    for the gate this exists to be."""


@dataclasses.dataclass(frozen=True)
class Active:
    """Attached to an `Intake` by any participating rule (parsing OR
    judging) that did something relevant to it THIS tick -- consumed by
    `settle`, below, the moment it is seen. See `mark_active`."""


@dataclasses.dataclass(frozen=True)
class Countdown:
    """How many more idle ticks before `ready()` answers true for this
    `Intake` -- reset to `BASE_COUNTDOWN` any tick `Active` was seen,
    decremented by 1 any tick it was not. `select` fires once this
    reaches `-1` or below: two genuinely idle ticks have passed."""

    remaining: int


def mark_active(w, intake) -> None:
    """The one call a participating rule adds alongside whatever
    `Span`/`Interpretation` write it already makes, to say "this
    utterance is still moving" -- named for the verb, the same shape
    `loopingrules.world.propose` already has."""
    w.attach(intake, Active())


def settle(w) -> None:
    """The one countdown rule. Install this LAST (lowest `priority=`)
    among every rule that ever calls `mark_active` on the same `Loop`,
    so it only ever sees an `Intake` still `Active` THIS tick if
    something really did mark it that way before `settle` got its own
    turn -- the same same-tick-ordering discipline `harneskills.
    examples.context.record_intake`'s own HIGH priority already relies
    on, used here in reverse (LOW, to run last).

    Both queries below -- who is `Active`, who is not -- are read
    BEFORE either is written, the same "read phase, then write phase"
    discipline `loopingrules.circuits.ActionCircuit` already applies:
    writing `Countdown` for the idle set must not change which
    entities the active-set write below still matches, or an `Intake`
    freshly marked active this very tick could be decremented in the
    same call that is supposed to reset it.
    """
    idle = w.each(Intake, without=Active)
    active = w.each(Intake, Active)
    for intake, _meta in idle:
        countdown = w.get(intake, Countdown)
        remaining = (countdown.remaining if countdown is not None else BASE_COUNTDOWN) - 1
        w.replace(intake, Countdown(remaining))
    for intake, _meta, _active in active:
        w.detach(intake, Active)
        w.replace(intake, Countdown(BASE_COUNTDOWN))


def ready(w, intake) -> bool:
    """Whether two genuinely idle ticks have passed for `intake` --
    `False` before any `Countdown` exists at all (nothing has settled
    even once yet)."""
    countdown = w.get(intake, Countdown)
    return countdown is not None and countdown.remaining <= -1


def _plain_id(entity) -> int:
    """`entity`, as a plain int, whether it arrived as a live `Entity`
    handle or already a bare id -- the same normalization `circuits.
    py`'s own `_matches` docstring names, restated here rather than
    imported (this module does not depend on `circuits.py`)."""
    return entity.id if hasattr(entity, "id") else int(entity)


def _interpretations_of(w, intake_id: int) -> "List[Tuple[object, Span, Interpretation, bool]]":
    rows = []
    for entity, interp in w.each(Interpretation):
        if interp.utterance != intake_id:
            continue
        span = w.get(entity, Span)
        if span is None:
            continue
        rows.append((entity, span, interp, w.has(entity, Ignorable)))
    return rows


def _best_covering(rows, length: int):
    """The highest-total-score combination of `rows` whose `Span`s
    union-cover every word position `0..length-1`, or `None` if no
    combination does. Brute-force over every non-empty subset -- see
    `DECISION_PATTERNS.md`'s 2026-09-14 entry, "the covering-set search
    is a real, unaddressed complexity question": exponential in
    `len(rows)`, correct and fine at the scale a real utterance's own
    rival readings run at, not engineered further here.

    A real consequence, not a bug, discovered writing this rather than
    designed in advance: overlap is unconditionally free (see the
    module docstring, "even overlapping"), so a NON-negative-scored
    reading is never excluded from the winning combination -- adding
    one, redundant or not, can only raise or hold the total, never
    lower it. Two genuinely RIVAL readings of the same span (`"stale
    after 3 days"` vs. `"stale after 5 days"`, both plausible, only one
    true) both win together unless a judge gives at least one of them a
    NEGATIVE score -- this module has no notion of two interpretations
    CONFLICTING, only of them coexisting or not. Nothing here decides
    whether that is a domain's own judge's job (down-weight a reading
    it disfavors below zero) or a gap this module should eventually
    close itself."""
    wanted = set(range(length))
    n = len(rows)
    best = None
    best_score = None
    for mask in range(1, 1 << n):
        chosen = [rows[i] for i in range(n) if mask & (1 << i)]
        covered = set()
        for _entity, span, _interp, _ignorable in chosen:
            covered.update(range(span.start, span.end + 1))
        if covered != wanted:
            continue
        score = sum(interp.score for _e, _s, interp, ignorable in chosen if not ignorable)
        if best_score is None or score > best_score:
            best_score = score
            best = chosen
    return best


def _already_resolved(w, intake_id: int) -> bool:
    """Whether some `Interpretation` of `intake_id` already carries
    `Definitive` -- an efficiency check, not a new verdict: `select`
    would reach the identical answer re-running `_best_covering` (`w.
    attach` on an already-`Definitive` entity is a no-op, per `World`'s
    own dedup), this just skips paying for the search again."""
    for _entity, interp, _definitive in w.each(Interpretation, Definitive):
        if interp.utterance == intake_id:
            return True
    return False


def select(w) -> None:
    """The generic winner: for every `ready` `Intake` not already
    resolved, the highest-scoring covering combination of its own
    `Interpretation`s (see `_best_covering`) is marked `Definitive`.

    No combination covering the whole utterance -> no `Definitive` at
    all for that `Intake` -- said by whatever downstream rule reads
    the absence, never guessed at (see the design entry). This rule
    re-attempts the search every tick for an `Intake` that never finds
    a winner -- harmless (nothing changes, so nothing FIRES, the same
    "re-runs harmlessly until there is nothing left to prune" posture
    `harneskills.examples.context.rank_by_confidence` already has), but
    a real, known cost for an utterance nothing ever covers.

    Does NOT call `mark_active` -- marking `Definitive` is the terminal
    act of this whole pipeline, not a "keep going" signal, so it must
    not re-open the quiescence window it just took two idle ticks to
    close.
    """
    for intake, meta in w.each(Intake):
        if not ready(w, intake):
            continue
        intake_id = _plain_id(intake)
        if _already_resolved(w, intake_id):
            continue
        rows = _interpretations_of(w, intake_id)
        winner = _best_covering(rows, meta.length)
        if winner is None:
            continue
        for entity, _span, _interp, _ignorable in winner:
            w.attach(entity, Definitive())
