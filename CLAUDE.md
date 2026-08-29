# Commit discipline

This repo's commits — and `harneskills`, the sibling repo this engine was
carved out of — are read later, by someone who was not in the room when
the change was made. A commit message is where that reasoning lives, not
a changelog line. Any Claude Code session working here follows the shape
below, not just its terminology.

## Title

One line that states what changed **and** why, in the same breath —
usually `<file/area>: <change>, because <reason>` or `<change> —
<consequence>`. Not a bare imperative ("fix save bug", "add length
check"). The title should be legible on its own in `git log --oneline`:
a reader should get the shape of the problem, not just its location.

## Body

Prose, not a changelog. Walk the reasoning: what was actually broken (the
root cause, ideally with a concrete repro or numbers), why it was
invisible to whatever already guarded against it, what the fix is, and
what it costs. Treat the system as an actor doing something ("a rule
that mints can spend the whole machine before tick 400", "the world does
not come back as twins") rather than narrating the diff mechanically
("changed X to Y in file Z").

Be explicit about what was deliberately left alone and why leaving it is
correct *for now* — a silent gap is worse than a named one. A caveat or
a serious warning earns its own sentence, said plainly, not a symbol.

## Evidence

Close with what was actually verified, concretely: test counts before
and after (`117 -> 128 passing`, `223 passed`), not just "tests pass."
If a regression was reproduced before the fix and confirmed absent
after, say so — that's the evidence the fix addressed the stated cause,
not just that the suite is green.

## Authorship trailer

When an AI session did the work, the commit normally closes with a
`Co-Authored-By: Claude ... <noreply@anthropic.com>` trailer — that's
the standing convention here and in `harneskills`. It is omitted only
when a human author explicitly asks for a specific commit to carry their
authorship alone.
