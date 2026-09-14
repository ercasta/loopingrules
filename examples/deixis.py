"""`deixis` -- a tiny worked domain proving `loopingrules.memory`'s
`Focus`/`Memory`/`MemoryEntry` against a real reference-resolution rule:
`"look at <name>"` sets focus, and `"it"`/`"that"`/`"this"` resolves to
whatever was focused most recently -- the shortest real case that
actually needs a TRAIL rather than a single "current topic" flag, since
focus moves and can come back (`"look at a"`, `"look at b"`, `"look at
a"` again, `"it"` -- the answer is `a`, not `b`, and nothing but a trail
tells the two `a`-visits apart from one continuous focus).

Modeled on `harneskills.examples.context`'s own `hear_qualified`/
`arbitrate_ambiguous` (`Said`-recognizes-one-fixed-shape, claims and
destroys it either way, `reply`s something even when resolution fails
rather than staying silent) but deliberately narrower: one entity
focused at a time, no confidence, no competing domains, no qualifier
vocabulary. This proves `loopingrules.memory`'s OWN mechanism, not a
second theory of disambiguation -- see that module's own docstring for
the deliberately-not-reconciled overlap between the two.
"""

from __future__ import annotations

from dataclasses import dataclass

from loopingrules.memory import Focus, Memory, most_recent, track_focus
from loopingrules.world import Said, reply


@dataclass(frozen=True)
class Named:
    """The one fact an entity in this domain carries: a name, typed
    exactly, case-sensitive -- `"look at Apple"` and `"look at apple"`
    name different entities, the same way two real filenames could."""

    name: str


def _find_named(w, name: str):
    for entity, named in w.each(Named):
        if named.name == name:
            return entity
    return None


def look_at(w) -> None:
    """`Said("look at <name>")` -> `Focus()` on the entity `<name>`
    names, replacing whichever ONE entity had it before (this domain
    only ever focuses one thing at a time). Claims and destroys the
    `Said` either way -- an unknown name is a fact worth replying to,
    not a reason to leave the line standing for something to retry."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if len(words) != 3 or words[0] != "look" or words[1] != "at":
            continue
        w.destroy(entity)
        target = _find_named(w, words[2])
        if target is None:
            reply(w, "no such thing: %s" % words[2])
            continue
        for other, _focus in w.each(Focus):
            if other != target:
                w.detach(other, Focus)
        w.attach(target, Focus())
        reply(w, "looking at %s" % words[2])


def hear_it(w) -> None:
    """`Said("it")`/`Said("that")`/`Said("this")` -> resolved against
    `loopingrules.memory.most_recent` -- the whole point of this
    module: nothing here decides what "it" means, `Memory`'s own trail
    does. `"not sure what that refers to"` (said, not swallowed -- the
    same posture `context.arbitrate_ambiguous` already takes) when the
    trail is empty.

    Named honestly, not smoothed over: calling `most_recent` -- an
    IMPORTED function, not a same-module helper -- makes this rule
    `Opaque` to `loopingrules.analyze` (`most_recent`/`most_intense`
    are not among its own "four named exceptions"), so this rule gets
    no dormancy gate and runs every tick regardless of whether `Said`
    exists -- correct, just not the free optimization `look_at` gets.
    Extending `analyze.py`'s exception list for `loopingrules.memory`
    is a real, separate decision, not implied by writing this rule."""
    for entity, said in w.each(Said):
        word = said.text.strip().lower()
        if word not in ("it", "that", "this"):
            continue
        w.destroy(entity)
        entry = most_recent(w)
        if entry is None:
            reply(w, "not sure what that refers to")
            continue
        named = w.get(entry.entity, Named)
        reply(w, "that's %s" % (named.name if named is not None else "#%d" % entry.entity))


def install(loop) -> None:
    """Register this module's two rules, plus `loopingrules.memory`'s
    own `track_focus` and the `Memory` singleton that turns it on --
    see that module's own docstring, "Opt in by existence." Installed
    here, not by `loopingrules.memory` itself, because THIS domain is
    the one that wants focus tracked; a caller that composes `deixis`
    with something else that also wants it should spawn its own
    `Memory` before calling this (`w.spawn` on an equal value is a
    no-op, so calling `install` twice against one `World` is harmless)."""
    loop.world.spawn(Memory())
    loop.rule(look_at, name="deixis.look_at")
    loop.rule(hear_it, name="deixis.hear_it")
    loop.rule(track_focus, name="deixis.track_focus")
