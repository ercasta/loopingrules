# Language layer

Everything on this page is for domains that interpret what a person typed.
It is optional. Nothing in the core imports any of it.

## Proposals and arbitration

**Problem.** Several rules can each read one line differently, or several
independently installed domains can each answer one question. A domain cannot
tell "nobody has proposed yet" from "nobody ever will" unless something
guarantees every rule has had its turn.

**Vocabulary** (in `world.py`, next to `Said` and `Reply`):

```python
occasion = w.spawn(Q("hi"))
propose(w, occasion, Answer("A"))       # spawns Proposal(occasion) + Answer("A")
propose(w, occasion, Answer("B"))

unanswered = arbitrate(w, Q)            # call from a rule
```

`arbitrate(w, OccasionType)` resolves every occasion of that type:

- the **first registered** proposal wins. It loses its `Proposal` tag and is
  now real (carrying whatever component would make it so),
- every other candidate is destroyed,
- the occasion is destroyed,
- occasions with **no** candidate come back in `unanswered`. Whether to say
  something about those is the caller's call.

`census(w, OccasionType)` is the sibling with no rivalry: every candidate
counts, none is destroyed, and it returns `(entity, component, candidates)`
for each resolved occasion.

**Why it waits a tick.** An occasion is never resolved the tick it is first
noticed. It is tagged with a private `_Ripe` marker first and only resolved
the next time. Since `Loop.tick` calls every rule once per tick, by the second
sighting every rule that watches that occasion, from any domain, at any
priority, has had its turn. Verified: in a small run, the pair of proposals
and the occasion settle in three ticks, leaving only the winning `Answer`.

What is **not** shared: *which* proposal should win beyond "first". That is
a decision for the domain (see `DECISION_PATTERNS.md`). Prefer explicit
arbitration over relying on `priority` to pick winners.

## `help`: the one shipped domain

`help.py` shows the propose/arbitrate shape working across two
independently installed domains. `help TOPIC` is answered by whichever
installed domain recognizes the topic.

- `HelpTopic(topic)` is the occasion. `hear_help` (high priority) spawns it.
- Each domain proposes a `HelpAnswer(text)` for topics it knows.
- `arbitrate_help` picks the winner and `reply_help_answer` replies.
  `open_census`/`close_census` gather a topic list for a bare `help`.
- **Install it or don't**: `help.install(loop)` registers its five rules.
  Nothing calls it automatically.

## `memory`: resolving "it", "that", "the one from before"

`Focus(intensity)` is a claim, made by some rule, that one entity is what
attention is on. `Memory()` is a singleton you spawn to opt in.
`MemoryEntry(entity, intensity, seq)` is spawned once per **genuine gain**
of focus, never mutated, so the trail is the whole history.

```python
w.spawn(Memory())                       # opt in: without it, nothing is recorded
# a rule attaches Focus() to the entity the person just referred to ...
memory.trail(w)                         # every MemoryEntry, oldest first
memory.most_recent(w)                   # the latest, or None
memory.most_recent(w, within=3)         # optional recency window
memory.most_intense(w)                  # ranked within one trail
```

Register `memory.track_focus` as a rule. It records only while a `Memory`
singleton exists. Why a trail and not a single "current" marker? Because
"no, the *other* one" needs the last thing that was **not** current.
`intensity` is a hint carried through verbatim. Nothing here normalises or
decays it. `examples/deixis.py` is the worked case.

## `chart`: scored readings of an utterance, and one winner

For lines with several plausible parses. A domain spawns one
`Intake(text, length)` per utterance. Its rules spawn entities carrying
`Span(start, end)` (inclusive, 0-based word indices) alongside
`Interpretation(utterance, score)` and whatever component the domain means.
Every participating rule calls `chart.mark_active(w, intake)`.

- **Quiescence.** `chart.settle` is the one countdown rule (install it
  *last*, at the lowest priority, among every rule that calls
  `mark_active`). `chart.ready(w, intake)` is true after two genuinely idle
  ticks. It is the single signal that parsing has stopped.
- **Judging.** Once ready, domain judge rules may `w.replace` an
  `Interpretation`'s score. Judges call `mark_active` too, since a judge is a
  participating rule by the same test.
- **Selection.** `chart.select` finds the highest-scoring *combination* of
  one intake's interpretations whose spans **union-cover** every word
  position (overlap allowed, no tiling needed) and marks each member
  `Definitive()`.

The design and its open questions are in `DECISION_PATTERNS.md`, the
2026-09-14 entry on judges. No example domain uses `chart` yet. Its behaviour
is pinned by `tests/test_chart.py` (two idle ticks, exactly, and a covering
combination chosen over rival scores), which is the best place to see it run.

!!! note
    Do not confuse this with `examples/judge.py`. That is a separate idea: one
    domain-oblivious `Risk` shape that `cards` and `shopping` both reuse.
