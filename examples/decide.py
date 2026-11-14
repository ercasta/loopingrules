"""`decide` -- one domain-oblivious rule, testing whether the "several
rivals, one winner" half of `DECISION_PATTERNS.md`'s vocabulary generalizes
past a single domain the way `loopingrules_patterns.judge`'s scalar-threshold
half already does.

A domain PROJECTS its own rivalry onto two attributes -- `occasion` (which
entity this is one way to resolve) and `score` (how good it is, higher
better) -- and `pick_winner` reads only the projection, oblivious to what
produced it. `winner` is the flag it writes back. It imports nothing from
`examples.trip` and knows nothing about a frontier or a trip request.
"""

from __future__ import annotations

OCCASION = "occasion"
SCORE = "score"
WINNER = "winner"


def pick_winner(w) -> None:
    """For every `occasion` named by at least one entity carrying both
    `occasion` and `score`: set `winner` on the entity with the strictly
    highest `score`, if exactly one holds it; clear it from every other.

    An exact tie for the top `score` sets `winner` on NOBODY -- refuse
    rather than guess between two rivals that scored identically, the same
    discipline `PRINCIPLES.md` calls non-negotiable. This rule never reads
    anything but `occasion`/`score`.
    """
    by_occasion: "dict[int, list]" = {}
    for entity, occasion, score in w.each("occasion", "score"):
        by_occasion.setdefault(occasion, []).append((entity, score))

    for rows in by_occasion.values():
        best = max(value for _entity, value in rows)
        leaders = [entity for entity, value in rows if value == best]
        winner = leaders[0] if len(leaders) == 1 else None
        for entity, _value in rows:
            if entity is winner:
                w.mark(entity, "winner")
            else:
                w.unmark(entity, "winner")
