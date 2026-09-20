"""`chart` -- a chart of scored `Interpretation`s attached to `Span`s of
an utterance, one quiescence signal that tells a domain when the chart
has stopped moving, `select`, the generic covering-set winner search
that marks the winning combination `Candidate`, and `promote`, which
turns that into `Definitive` once it is safe to act on. See
`DECISION_PATTERNS.md`'s 2026-09-14 entry ("judges, closing 'Not built:
chart parsing' above") for the design `select` implements, its
2026-09-20 entry ("waves, vocabulary, and discourse-level
reinterpretation") for `Candidate`/`promote`/`Discourse` and the rest
of this docstring's own second half, the precedent both are grounded
against (`pystrider/spans.py`'s `Span`, `world.py`'s `_Ripe`,
`harneskills.examples.context`'s `_Recorded`), and what is still
genuinely open -- this module is the mechanical half of both entries,
not a restatement of their reasoning.

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
member of the winning combination `Candidate()`. `promote`, below,
turns that into `Definitive()` once it is safe to act on.

## Isolating tentative interpretations

A rule that composes bigger interpretations from smaller ones (an
`after_threshold`-shaped rule) keys on bare `Span`/`Interpretation` and
must never see `Candidate` -- attaching it is `select`'s own, and
ONLY `select`'s own, business. A rule that ACTS on a resolved reading
keys on `Interpretation` PLUS `Definitive`, the same `without=
NeedsApproval` shape `harneskills.examples.fs.do_rename` already uses,
renamed rather than reinvented. No new effect or engine mechanism is
needed for this split -- it is an ordinary component gate, the same as
every other "don't act on the tentative one" idiom this codebase
already has.

## Waves, vocabulary, and discourse

`Token`, `Vocabulary`, `Matched`, and `read_vocabulary`, below, are the
generic half of "how do `Span`/`Interpretation` pairs get built out of
raw text in the first place." A domain's own splitting rule spawns
`Token`s (co-attached with `Span`, the same marker-plus-component shape
as everything else here); a domain's own setup rule attaches
`Vocabulary(word)` onto WHATEVER entity it names (a `Stop`, a keyword,
...) rather than a separate registry entity; `read_vocabulary` is the
one generic rule that matches the two into a fresh `Interpretation`. A
rule "triggered" by another needs no new mechanism either -- it is an
ordinary rule gated on whatever component the triggering rule
attached, ordinary `w.each`, nothing more.

`select` now attaches `Candidate`, not `Definitive` -- provisional,
still retractable (see `retract`, below) -- and `promote` is the only
rule that ever attaches `Definitive`. A standalone `Intake` (no
`SentenceOf`) promotes immediately; one that IS `SentenceOf` a
`Discourse` (several sentences making up one longer utterance, where a
later sentence may force a reinterpretation of an earlier one's own
`Candidate`) waits until that `Discourse` is itself `ready` -- `settle`,
generalized with a `kind=` parameter, reused UNCHANGED one level up
rather than a second quiescence concept: a `Discourse`'s own countdown
resets whenever `attach_sentence` adds a new sentence to it, or
`retract` reopens it. See `DECISION_PATTERNS.md`'s 2026-09-20 entry for
the reasoning, the precedent each piece is grounded against, and the
alternatives it named and rejected.
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
class Discourse:
    """One per multi-sentence utterance whose own `Intake`s (see
    `SentenceOf`) may need to reinterpret each other -- a later
    sentence overturning an earlier one's own `Candidate`. Carries no
    `length`: unlike `Intake`, nothing here needs a coverage check over
    a numeric range, only "has anything moved lately," which `settle
    (w, kind=Discourse)` already answers without one -- see
    `DECISION_PATTERNS.md`'s 2026-09-20 entry for the alternatives this
    rejected."""

    text: str


@dataclasses.dataclass(frozen=True)
class SentenceOf:
    """Attached to an `Intake` (never to a bare word span) to say it is
    sentence number `order` of `discourse` -- `order` exists so a
    reinterpretation rule can find "the previous sentence," not for any
    generic-code coverage check. Use `attach_sentence`, below, rather
    than attaching this bare: spawning a sentence must also reopen its
    `Discourse`'s own countdown, and that second call is easy to forget
    doing by hand."""

    discourse: int
    order: int


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
class Token:
    """One split unit of `utterance`'s own text, at word-token `index`
    -- co-attach `Span(index, index)` on the same entity, the same
    "marker plus whichever component would make it real" shape
    `Interpretation` itself uses. A domain's own splitting rule spawns
    these; this module does not tokenize (see `Intake.length`'s own
    docstring) and has no opinion on what splits one word from the
    next."""

    utterance: int
    index: int
    text: str


@dataclasses.dataclass(frozen=True)
class Vocabulary:
    """Attached by a domain's own rule onto WHATEVER entity it names --
    a `Stop`, a keyword, anything -- not a separate registry entity:
    recognizing "milan" as a station is `w.attach(stop_entity,
    Vocabulary("milan"))` run once over a domain's own `Stop`s, never a
    new lookup structure `read_vocabulary` has to know about."""

    word: str


@dataclasses.dataclass(frozen=True)
class Matched:
    """Co-attached alongside `Span`/`Interpretation` by `read_
    vocabulary`, below, naming which `Vocabulary`-bearing entity a
    `Token` matched -- the domain's own meaning (what a `Stop` IS, what
    a keyword MEANS) is read off `target`, never named here, the same
    split `Interpretation` itself already draws for what a span
    means."""

    target: int


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
class Candidate:
    """Attached by `select`, and ONLY by `select`, to every
    `Interpretation` entity that was part of its own winning
    combination -- provisional, not yet acted on: see `promote` for
    what turns this into `Definitive`, and `retract` for how a
    reinterpretation rule undoes it. A composing rule (an `after_
    threshold`-shaped rule) must never see this any more than it saw
    `Definitive` before this entry -- same gate, moved earlier."""


@dataclasses.dataclass(frozen=True)
class Definitive:
    """Attached by `promote`, and ONLY by `promote`, to every
    `Candidate` interpretation `select` chose once it is safe to act on
    -- immediately for a standalone `Intake`, or once its own
    `Discourse` (if any) is `ready` for one that is `SentenceOf` one.
    See the module docstring, "Isolating tentative interpretations,"
    for the gate this exists to be -- still the one component an
    ACTING rule keys on, unchanged by this entry."""


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


def mark_active(w, entity) -> None:
    """The one call a participating rule adds alongside whatever
    `Span`/`Interpretation` write it already makes, to say "this
    utterance is still moving" -- named for the verb, the same shape
    `loopingrules.world.propose` already has. Works on a `Discourse`
    exactly the same way, for the identical reason one level up -- see
    `attach_sentence`/`retract`, below."""
    w.attach(entity, Active())


def attach_sentence(w, intake, discourse, order: int) -> None:
    """Mark `intake` as sentence number `order` of `discourse`, and
    mark `discourse` active in the same call -- a `Discourse` is still
    moving while sentences are still being added to it, and splitting
    those two writes apart is exactly the atomicity trap `DECISION_
    PATTERNS.md`'s 2026-09-14 entry already found once by hand
    (`flag_stale`'s `without=Proposal` gate assuming an invariant its
    own caller no longer upheld atomically) -- bundled here so a
    splitting rule cannot spawn a sentence without also reopening its
    discourse's own countdown.
    """
    w.attach(intake, SentenceOf(_plain_id(discourse), order))
    mark_active(w, discourse)


def settle(w, kind=Intake) -> None:
    """The one countdown rule, scanning every entity of `kind` --
    `Intake` by default, so every existing call site (`chart.settle
    (w)`) is unaffected. Pass `kind=Discourse` to run the identical
    countdown one level up, over `Discourse` entities instead -- the
    same `Active`/`Countdown` components, not a second quiescence
    concept; see the module docstring, "Waves, vocabulary, and
    discourse."

    Install this LAST (lowest `priority=`) among every rule that ever
    calls `mark_active` on the same `Loop`, so it only ever sees an
    entity still `Active` THIS tick if something really did mark it
    that way before `settle` got its own turn -- the same same-tick-
    ordering discipline `harneskills.examples.context.record_intake`'s
    own HIGH priority already relies on, used here in reverse (LOW, to
    run last).

    Both queries below -- who is `Active`, who is not -- are read
    BEFORE either is written, the same "read phase, then write phase"
    discipline `loopingrules.circuits.ActionCircuit` already applies:
    writing `Countdown` for the idle set must not change which entities
    the active-set write below still matches, or an entity freshly
    marked active this very tick could be decremented in the same call
    that is supposed to reset it.
    """
    idle = w.each(kind, without=Active)
    active = w.each(kind, Active)
    for entity, _meta in idle:
        countdown = w.get(entity, Countdown)
        remaining = (countdown.remaining if countdown is not None else BASE_COUNTDOWN) - 1
        w.replace(entity, Countdown(remaining))
    for entity, _meta, _active in active:
        w.detach(entity, Active)
        w.replace(entity, Countdown(BASE_COUNTDOWN))


def ready(w, entity) -> bool:
    """Whether two genuinely idle ticks have passed for `entity` --
    `Intake` or `Discourse`, this does not care which -- `False` before
    any `Countdown` exists at all (nothing has settled even once yet)."""
    countdown = w.get(entity, Countdown)
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
    `Candidate` -- an efficiency check, not a new verdict: `select`
    would reach the identical answer re-running `_best_covering` (`w.
    attach` on an already-`Candidate` entity is a no-op, per `World`'s
    own dedup), this just skips paying for the search again. A
    reinterpretation rule's own `retract` clears `Candidate` along with
    `Definitive`, which is what lets `select` reconsider at all -- see
    the module docstring, "Waves, vocabulary, and discourse.\""""
    for _entity, interp, _candidate in w.each(Interpretation, Candidate):
        if interp.utterance == intake_id:
            return True
    return False


def select(w) -> None:
    """The generic winner: for every `ready` `Intake` not already
    resolved, the highest-scoring covering combination of its own
    `Interpretation`s (see `_best_covering`) is marked `Candidate` --
    provisional, not yet acted on; see `promote` for what turns this
    into `Definitive`.

    No combination covering the whole utterance -> no `Candidate` at
    all for that `Intake` -- said by whatever downstream rule reads the
    absence, never guessed at (see the design entry). This rule
    re-attempts the search every tick for an `Intake` that never finds
    a winner -- harmless (nothing changes, so nothing FIRES, the same
    "re-runs harmlessly until there is nothing left to prune" posture
    `harneskills.examples.context.rank_by_confidence` already has), but
    a real, known cost for an utterance nothing ever covers.

    Does NOT call `mark_active` -- marking `Candidate` is the terminal
    act of THIS rule's own stage, not a "keep going" signal, so it must
    not re-open the quiescence window it just took two idle ticks to
    close. (`retract`, not this rule, is what reopens it later, if a
    reinterpretation rule needs to.)
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
            w.attach(entity, Candidate())


def retract(w, entity, intake, discourse=None) -> bool:
    """Undo a `Candidate`/`Definitive` a reinterpretation rule no
    longer trusts, and reopen every window that attaching it once
    closed: `intake`'s own (so `select` reconsiders that span) and, if
    given, `discourse`'s own (so `promote` waits again before acting on
    whatever `intake` settles on next) -- the same detach-then-reopen
    shape `attach_sentence`'s own bundling already uses, the two halves
    of one write kept from ever happening apart. Returns whether
    anything was actually attached to retract, the same `bool` `World.
    detach` itself returns.
    """
    gone = w.detach(entity, Candidate, Definitive)
    if gone:
        mark_active(w, intake)
        if discourse is not None:
            mark_active(w, discourse)
    return gone


def _normalize_word(word: str) -> str:
    return word.strip().lower()


def read_vocabulary(w) -> None:
    """The one generic wave-1 rule: for every `Token`, look up every
    entity carrying a `Vocabulary` component whose own `word`
    normalizes (stripped, cased down) to the same thing the token's own
    `text` does, and for each match spawn a fresh `Span` (copied from
    the token's own) + `Interpretation` + `Matched(target)` -- `target`
    the id of the entity whose `Vocabulary` matched, the domain's own
    meaning read off THAT entity, never named here. Calls `mark_active`
    on the token's own `Intake`, the same "this utterance is still
    moving" call any other proposing rule makes.

    Score starts at `1.0`, a plain default a domain's own judge may
    later `w.replace` -- an approximate/fuzzy match is a DIFFERENT
    domain rule's own business (this one only ever does exact,
    normalized equality), scored however that domain rule sees fit; see
    `DECISION_PATTERNS.md`'s 2026-09-20 entry, "left open."

    Does not skip a `Token` some other interpretation already covers --
    overlap is `select`'s own concern to arbitrate, not this rule's
    (see `select`'s own docstring, "even overlapping").
    """
    vocabulary = w.each(Vocabulary)
    for token_entity, token in w.each(Token):
        span = w.get(token_entity, Span)
        if span is None:
            continue
        needle = _normalize_word(token.text)
        for target_entity, entry in vocabulary:
            if _normalize_word(entry.word) != needle:
                continue
            w.spawn(Span(span.start, span.end),
                   Interpretation(token.utterance, 1.0),
                   Matched(target_entity.id))
            mark_active(w, w.entity(token.utterance))


def promote(w) -> None:
    """The only rule that ever attaches `Definitive` -- to every
    `Candidate` interpretation `select` chose, once it is safe to act
    on. A standalone `Intake` (no `SentenceOf`) promotes immediately:
    nothing else can still overturn it. An `Intake` that IS `SentenceOf`
    a `Discourse` waits until that `Discourse` is itself `ready` (see
    `settle(w, kind=Discourse)`) -- a later sentence may still `retract`
    an earlier one's own `Candidate` while the discourse is still
    moving, and promoting early would act on a reading that gets undone
    a tick later.

    Re-checks every tick, the same harmless-re-run posture `select`
    itself has: `w.attach` on an already-`Definitive` entity is a
    no-op, so this only ever does real work the first tick a given
    `Candidate` becomes eligible.
    """
    for entity, interp, _candidate in w.each(Interpretation, Candidate,
                                             without=Definitive):
        sentence_of = w.get(w.entity(interp.utterance), SentenceOf)
        if sentence_of is not None and not ready(w, w.entity(sentence_of.discourse)):
            continue
        w.attach(entity, Definitive())
