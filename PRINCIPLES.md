# Principles — what makes the entity/component/rules substrate produce the RIGHT kind of emergent behaviour

## What kind of emergence this is actually for

"Emergent behaviour" hides at least two different things, and this substrate
is deliberately built for only one of them.

Rules here are oblivious of each other — no rule calls another, the only
channel between them is what gets deposited into the shared `World`. That
*is* real, structural stigmergy: `patterns.LoopCount` gets attached with zero
awareness that `constraints.max_loops` exists; `constraints.max_loops` fires
purely because `LoopCount` showed up. Nobody wrote that pipeline; it
assembles from independently-authored, mutually-ignorant rules the same way
a blackboard architecture's knowledge sources do (Hearsay-II is the direct
architectural ancestor of this shape). That is the kind of emergence this
repo wants, and gets: complex, composed conclusions arising from many small,
individually-legible rules, with the composition never explicitly written
by anyone.

