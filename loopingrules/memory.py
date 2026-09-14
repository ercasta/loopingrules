"""`memory` -- `Focus`, a claim some rule makes that ONE entity (of
possibly several candidates) is what attention is currently on, and
`Memory`, the trail of every entity that claim was ever made about --
the substrate a rule resolving `"it"`/`"that"`/`"the one from before"`
reads, instead of every domain that needs this inventing its own notion
of recency by hand.

## Why a trail, not just "the last one"

A single `Focused` marker, moved from entity to entity, answers "what is
focused RIGHT NOW" but throws away the one thing deictic resolution
actually needs: "the last thing that was NOT what is currently being
talked about" -- `"no, the OTHER one"`, or a reference typed after focus
has already moved on and come back. `MemoryEntry`, below, is spawned
once per genuine gain of `Focus` (see `track_focus`'s own docstring for
exactly when), never mutated or destroyed, so `w.each(MemoryEntry)` is
always the whole history -- the same "the trail IS the point" idiom
`harneskills.examples.context.Turn` already proved for a conversation's
own turns, restated here for focus instead of dialogue lines.

## Opt in by existence, not a flag

`track_focus`, the one rule this module ships, only records anything
while `w.the(Memory)` finds a singleton -- a domain that never spawns
one pays nothing for this module (the rule still runs, empty, the same
"called every tick, does nothing" cost any rule keyed on a component
nothing has spawned yet already has -- see `loopingrules.loop`'s own
module note, "A rule wakes only when something it reads exists"). This
is deliberately a `Memory()` singleton to spawn, not a module-level
switch: two independent `World`s (two conversations, two tests) can
each decide for themselves whether focus is worth tracking at all.

## `Focus.intensity` is a hint, not a score this module interprets

Nothing here normalizes, decays, or compares one domain's `intensity`
against another's -- it is carried through to `MemoryEntry` verbatim
and left for `most_intense` (below) to rank WITHIN one trail, the same
"this package does not decide what to do with a claim, only records it
soundly" posture `loopingrules.world.Proposal`'s own docstring already
takes for `occasion`. `None` means the rule that attached `Focus` had
no opinion -- excluded from `most_intense`, not treated as the lowest
possible score (that would be a guess this module refuses to make).

## The overlap with `harneskills.examples.context`, named and not resolved

`context.py`'s `Turn`/`Topic` already tracks a not-dissimilar trail (of
conversation turns, tagged with which DOMAIN resolved them) to
disambiguate `"the <qualifier> one"` by confidence decay over turn
count. `Focus`/`Memory` is a different, more general shape -- a trail of
WHICH ENTITY was attended to, not which domain, with no decay and no
qualifier vocabulary at all -- proven here against its own worked
example (`examples/deixis.py`), not against `context.py`'s. Whether the
two should ever be reconciled (`context.py` rebuilt on top of this, or
this module folded into `context.py`'s own vocabulary) is not decided by
building either one -- the same "a real change, left to whoever owns
that path" posture `DECISION_PATTERNS.md`'s 2026-09-13 `Call` entry
already took for a different cross-repo question.
"""

from __future__ import annotations

import dataclasses
from typing import List, Optional


@dataclasses.dataclass(frozen=True)
class Focus:
    """Attached to (or detached from) any entity by a DOMAIN's own
    rules -- "this is currently salient" -- never by this module, which
    only ever reads it. `intensity`, if given, is that domain's own
    confidence or salience score, on whatever scale it chooses; `None`
    when a domain has no opinion beyond "focused" (see the module
    docstring, "`Focus.intensity` is a hint")."""

    intensity: Optional[float] = None


@dataclasses.dataclass(frozen=True)
class Memory:
    """Spawn one of these to turn `track_focus` on for this `World` --
    see the module docstring, "Opt in by existence." Carries nothing:
    the trail itself is `MemoryEntry` entities, not a field here (a
    Python list of nested components is not what a component field can
    hold at all -- see `loopingrules.world`'s own "primitives-only
    fields" discipline -- and `w.each(MemoryEntry)` is already the
    whole history the same way `w.each(Turn)` already is in
    `harneskills.examples.context`, so nothing would be gained by
    duplicating it into a list here even if the storage model allowed
    it)."""


@dataclasses.dataclass(frozen=True)
class MemoryEntry:
    """One trail entry, its own entity: `entity` (a plain id) gained
    `Focus` at trail position `seq` (0, 1, 2, ... in the order it
    happened -- `harneskills.examples.context.Turn.seq`'s own "no
    counter entity needed, `w.each` is already the whole history"
    idiom), carrying whatever `intensity` the `Focus` that caused this
    entry had at the moment it was recorded. Never mutated or
    destroyed by this module once spawned."""

    entity: int
    intensity: Optional[float]
    seq: int


@dataclasses.dataclass(frozen=True)
class _FocusSeen:
    """Private bookkeeping for `track_focus`, below -- marks an entity's
    CURRENT, continuous span of carrying `Focus` as already recorded,
    so a rule that re-attaches an equal `Focus` every tick (the
    `tag_affordable`-style "recompute fresh" idiom) does not spawn a
    fresh `MemoryEntry` every tick it does. Cleared the moment `Focus`
    is gone, not before -- a real detach-then-reattach, even back to an
    identical `intensity`, is a genuine second gain of attention and
    gets its own entry. What this does NOT catch, named rather than
    silently handled: `intensity` changing while `Focus` stays
    continuously attached (a domain's own `w.replace`) records no new
    entry, because nothing here is watching for a CHANGE, only a GAIN --
    see `most_intense`, which reads whatever was true at the one moment
    each entry was recorded, not "as of now.\""""


def track_focus(w) -> None:
    """The one rule this module ships. Two halves, in order: every
    entity carrying `Focus` for the first time since its last loss (not
    yet `_FocusSeen`) gets a fresh `MemoryEntry` and is marked seen;
    every entity marked seen that no longer carries `Focus` at all has
    that marking cleared, so the NEXT gain is not silently skipped as
    "already recorded." No-op entirely while `w.the(Memory)` finds
    nothing -- see the module docstring, "Opt in by existence.\""""
    if w.the(Memory) is None:
        return
    for entity, focus in w.each(Focus, without=_FocusSeen):
        w.attach(entity, _FocusSeen())
        w.spawn(MemoryEntry(entity.id, focus.intensity, _next_seq(w)))
    for entity, _seen in w.each(_FocusSeen, without=Focus):
        w.detach(entity, _FocusSeen)


def _next_seq(w) -> int:
    return sum(1 for _entity, _entry in w.each(MemoryEntry))


def trail(w) -> "List[MemoryEntry]":
    """The whole history, oldest first -- every `MemoryEntry`, sorted by
    its own `seq` (a checked guarantee, not an assumption that `w.each`
    happens to return them in spawn order)."""
    return sorted((entry for _entity, entry in w.each(MemoryEntry)), key=lambda e: e.seq)


def most_recent(w) -> "Optional[MemoryEntry]":
    """The last entry in the trail, or `None` if `Focus` has never been
    granted (or `Memory` was never spawned at all) -- what an "it"/
    "that" typed with no qualifier at all should resolve against."""
    entries = trail(w)
    return entries[-1] if entries else None


def most_intense(w, within: "Optional[int]" = None) -> "Optional[MemoryEntry]":
    """The entry with the highest `intensity` among the last `within`
    entries (the whole trail if `within` is `None`), ties broken by
    recency. Entries whose `intensity` is `None` are EXCLUDED, not
    treated as the lowest possible score -- see the module docstring,
    "`Focus.intensity` is a hint." `None` if no entry in range ever
    carried an `intensity` at all."""
    entries = trail(w)
    if within is not None:
        entries = entries[-within:]
    scored = [entry for entry in entries if entry.intensity is not None]
    if not scored:
        return None
    return max(scored, key=lambda e: (e.intensity, e.seq))
