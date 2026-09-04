# TODO

Open threads out of the `examples/circuits.py` prototype (see README
History, "circuits.py: a closed shape catalog"), named so they are not
lost rather than scheduled.

- ~~`check_goal`'s fold.~~ Done: `ActionCircuit` (a seeded `GoalCheck`
  marker, consumed) + `Any`/`Forall` for the quantifier over `CardDef`/
  `Wants` the condition asks about. (A first attempt used a fourth rule
  shape, `WorldCircuit`, guarding "don't fire twice" by self-reference;
  removed once it turned out to be a strict special case of
  `ActionCircuit` with a seeded marker -- see README History, "don't
  fire twice is consuming a component.")
- ~~`patterns.loop_count`'s aggregate.~~ Done: `Count(over, condition)`
  (a number, not a boolean -- `Any`/`Forall`'s sibling) plus `Children
  (base, fk_field, component)`, the one-to-many scope `Via` cannot
  reach (a `Function`'s `Body` names ONE entity, but that entity carries
  MANY `Stmt`s), plus `HasSelf(component)` for "does the entity
  currently being counted carry this."
- ~~`hear_list`'s parsing.~~ Tried, and it DOES reduce, exactly, with
  `Lower`/`Split`/`At`/`Len`/`ParseInt`/`FindBy` (six new primitives) and
  a ten-spec decomposition (two `ValueCircuit`s computing `ListParse`/
  `ListResolved`, four `TagCircuit`s for the four mutually exclusive
  outcomes, four `ActionCircuit`s acting on them). All four outcomes
  (wrong arity, unknown card, bad price, a real `Listing`) reproduced
  exactly, including the specific wording of each `BadCommand`. The
  honest verdict, not smoothed over: this is by far the worst
  primitive-to-value ratio tried so far -- six new primitives and ten
  specs to restate one ~25-line rule, versus zero new primitives for
  `decide_buy` or three each for `check_goal`/`loop_count`. `hear_want`/
  `hear_status` were not attempted -- same primitives would likely cover
  them, at a similar cost, and nothing new would be learned by doing it
  again. See README History, "hear_list's parsing."
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
