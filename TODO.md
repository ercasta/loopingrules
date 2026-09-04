# TODO

Open threads out of the `examples/circuits.py` prototype (see README
History, "circuits.py: a closed shape catalog"), named so they are not
lost rather than scheduled.

- ~~`check_goal`'s fold.~~ Done: `WorldCircuit` + `Any`/`Forall` (no
  per-entity match, a quantifier over a query instead). `patterns.
  loop_count` (an aggregate too -- how many loops a function directly
  contains) is NOT the same shape and remains open: it counts, over a
  query already scoped to ONE entity's own nested structure, not "every
  entity matching a join" -- `Any`/`Forall` answer yes/no questions,
  `loop_count` needs an actual `Count`/`Sum` returning a number. Not
  designed.
- **`hear_list`/`hear_want`/`hear_status` stay plain Python, on purpose,
  for now.** String parsing (split, lowercase, int-parse, look up by
  name, report which check failed) is a different primitive axis than
  numeric circuits. Might reduce via the same tag-then-compose idiom (a
  `WrongArity`/`UnknownCard`/`BadPrice` tag per failure) -- not
  attempted.
- **`decide_buy_spec` drops the batching `cards.decide_buy` still does**
  (one match per tick, not several). Correct, per README History, but a
  real behavior change if this were ever adopted for real rather than
  tested against it -- worth re-flagging if it is.
- **Whether any of this is worth promoting past a prototype.**
  `circuits.py` is wired into nothing `cards.install()` actually uses.
  Its whole motivation was a closed catalog being easier for a future
  search/learning process to work over -- no search or learning exists
  yet. Per `DECISION_PATTERNS.md`'s "grow it only at the rule that
  actually collides," stays a prototype until something real needs it.
