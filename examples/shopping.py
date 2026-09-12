"""`shopping` -- a household shopping list, and the second real domain
this repo has ever asked `examples.judge`'s `Risk` to serve.

## What this is testing

`examples.judge`'s own docstring names the open question plainly: whether
one `Risk` shape (`level: float` in `0..1`, plus a named `reason`) "holds
across two UNRELATED domains, or is secretly two domains' different ideas
wearing one field name," and it says only `examples.cards` has ever had to
find out. This module is the second data point, chosen on purpose to be a
genuinely different KIND of "how concerning is this" than `cards.tag_risk_
level`'s: `cards` projects RESOURCE EXHAUSTION (how much of the room left
to spend a price would use); `project_urgency`, below, projects TIME
PRESSURE (how close a deadline is) -- a domain with no notion of money,
spending, or affordability at all. If `Risk`/`RiskTolerance`/`flag_too_
risky` -- imported here UNMODIFIED, never re-implemented -- work for this
without alteration, that is real evidence the shape generalizes rather
than merely fit the one domain it was drawn from; `tests/test_examples_
shopping.py`'s own `test_shopping_imports_the_judges_vocabulary_rather_
than_reinventing_it` pins that nothing here quietly forked a local copy
instead.

## What it settled, once tried

`flag_too_risky` only ever exposes a boolean (`TooRisky`, past the
tolerance, or not) -- the worry going in was that urgency wants RANKING
too ("which of several overdue items is most pressing" is not a yes/no
question), and a threshold judge does not rank. It turned out not to need
a second judge: `project_urgency` `replace`s a real `Risk(level, reason)`
onto every item with a deadline, past the threshold or not, and nothing
about crossing the threshold consumes or hides that float -- so a caller
that wants a ranking already has one, for free, by reading `Risk.level`
directly off whichever items `TooRisky` flagged, the same fact the judge
itself compared against its own tolerance. `tests/test_examples_shopping
.py::test_several_urgent_items_can_still_be_ranked_by_the_same_risk_
level_the_judge_thresholds` is the evidence. No new vocabulary was needed
to get it.

## Kept here, not shipped

Same standing as `examples.cards`/`examples.judge` -- see `cards.py`'s own
module docstring for what that does and does not mean. This module
imports `examples.judge`, never `examples.cards`, and is not imported by
either.

## Vocabulary

- `Item(name)` -- one entity per shopping-list entry, seeded by `install`
  from `DEFAULT_ITEMS`, by NAME, the same "never touch an entry already
  there" policy `cards.install` gives `CardDef`.
- `Stock(quantity)` -- units on hand right now, `replace`d, singular,
  seeded at `0` per catalog entry and updated by `stock <item> <qty>`.
  Read only for `status`; deliberately NOT part of `project_urgency` --
  see below.
- `NeededBy(days)` -- days until this item is needed for something
  specific, set by `needby <item> <days>`, ABSENT until then: an item
  with no deadline has no urgency at all, refused rather than guessed at
  zero. There is no command to clear one once set -- a deliberate gap,
  the same shape as `cards.py`'s "selling," not an oversight: nothing
  here yet needs "no longer needed," and guessing at that shape now would
  be exactly the speculative generality `DECISION_PATTERNS.md` argues
  against.
- `examples.judge.Risk(level, reason)` -- this domain's projection, onto
  a component it does not own, of how close `NeededBy.days` is to `0`,
  linear across `HORIZON_DAYS`. Deliberately NOT blended with `Stock` --
  the point of this module is testing whether TIME PRESSURE alone fits
  the same shape `cards` built out of SPENDING ROOM, not building the
  most realistic shopping assistant possible.
- `examples.judge.RiskTolerance(max_level)` -- seeded by `install`, owned
  by `judge.py`, same as `cards.py`'s copy.
- `OnList()` -- `@transient` tag, both directions every tick, the same
  "recompute fresh, never cache" discipline `cards.tag_wanted` uses: on
  iff the item's own `TooRisky` (the judge's, not this module's) is
  currently attached.
- `BadCommand(text, why)` -- short-lived, consumed same-or-next tick by
  `reply_bad_command`, identical shape to `cards.py`'s own.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.judge import Risk, RiskTolerance, TooRisky, flag_too_risky
from loopingrules.world import Said, reply, transient


HORIZON_DAYS = 7


@dataclass(frozen=True)
class Item:
    name: str


@dataclass(frozen=True)
class Stock:
    quantity: int


@dataclass(frozen=True)
class NeededBy:
    days: int


@transient
@dataclass(frozen=True)
class OnList:
    pass


@dataclass(frozen=True)
class BadCommand:
    text: str
    why: str


DEFAULT_ITEMS = (Item("milk"), Item("eggs"), Item("bread"),
                  Item("coffee"), Item("batteries"))


def _find_item(w, name: str):
    """The `Item` entity named `name`, case-insensitively, or `None` --
    same discipline as `cards._find_card`: never guesses between two,
    since `install` never seeds a duplicate name and nothing else here
    spawns an `Item` at all."""
    for entity, item in w.all(Item):
        if item.name.lower() == name.lower():
            return entity
    return None


def _parse_nonneg_int(text: str):
    """A non-negative int, or `None` -- refuse-rather-than-guess, same as
    `cards._parse_int`, plus the one extra rule both this module's fields
    need (neither a stock count nor a day count has a negative meaning
    here)."""
    try:
        value = int(text)
    except ValueError:
        return None
    return value if value >= 0 else None


# -- hearing -------------------------------------------------------------

def hear_stock(w) -> None:
    """`stock <item> <qty>` -> `Stock(qty)` on that item, replacing
    whatever it already carried."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "stock":
            continue
        w.destroy(entity)
        if len(words) != 3:
            w.spawn(BadCommand(said.text, "usage: stock <item> <qty>"))
            continue
        item = _find_item(w, words[1])
        if item is None:
            w.spawn(BadCommand(said.text, "unknown item %r" % words[1]))
            continue
        qty = _parse_nonneg_int(words[2])
        if qty is None:
            w.spawn(BadCommand(said.text, "not a quantity: %r" % words[2]))
            continue
        w.replace(item, Stock(qty))


def hear_needby(w) -> None:
    """`needby <item> <days>` -> `NeededBy(days)` on that item, replacing
    whatever deadline it already carried -- a second `needby` for the
    same item updates it, the same as `cards.hear_want` updates a goal
    rather than adding a rival one."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "needby":
            continue
        w.destroy(entity)
        if len(words) != 3:
            w.spawn(BadCommand(said.text, "usage: needby <item> <days>"))
            continue
        item = _find_item(w, words[1])
        if item is None:
            w.spawn(BadCommand(said.text, "unknown item %r" % words[1]))
            continue
        days = _parse_nonneg_int(words[2])
        if days is None:
            w.spawn(BadCommand(said.text, "not a day count: %r" % words[2]))
            continue
        w.replace(item, NeededBy(days))


def hear_status(w) -> None:
    """`status` -> stock, deadline (if any), and whether the judge's own
    `TooRisky` currently flags it, per item -- said directly, the same as
    `cards.hear_status`."""
    for entity, said in w.each(Said):
        words = said.text.split()
        if not words or words[0].lower() != "status":
            continue
        w.destroy(entity)
        lines = []
        for item_entity, item in sorted(w.all(Item), key=lambda row: row[1].name):
            stock = w.get(item_entity, Stock)
            have = stock.quantity if stock else 0
            needed = w.get(item_entity, NeededBy)
            line = "%s: %d in stock" % (item.name, have)
            if needed is not None:
                line += ", needed in %d day(s)" % needed.days
            if w.has(item_entity, OnList):
                line += " -- on the list"
            lines.append(line)
        reply(w, "; ".join(lines) if lines else "no items")


# -- projecting, and acting on the judge's verdict ------------------------

def project_urgency(w) -> None:
    """`examples.judge.Risk`, `replace`d fresh onto every item that
    carries a `NeededBy` -- see the module docstring's "What this is
    testing." `level` rises linearly from `0.0` at `HORIZON_DAYS` or
    further out to `1.0` at (or past) `0` days -- capped both ends, the
    same "cap, don't extrapolate past the meaningful range" `cards.tag_
    risk_level` already does for spending room.

    An item with no `NeededBy` gets no `Risk` at all -- not a `Risk(0.0,
    ...)` -- refusing to manufacture an opinion about urgency for
    something that was never asked to have one."""
    for entity, _item, needed in w.each(Item, NeededBy):
        level = max(0.0, min(1.0, 1.0 - needed.days / HORIZON_DAYS))
        w.replace(entity, Risk(
            level, "needed in %d day(s), %.0f%% of the %d-day horizon"
            % (needed.days, level * 100, HORIZON_DAYS)))


def add_to_list(w) -> None:
    """`OnList` iff the judge's own `TooRisky` is currently attached --
    both directions, every tick, the same reasoning as `cards.tag_
    wanted`. This rule never computes a level or a threshold itself; it
    only reads a fourth-party verdict, the same composition idiom `cards
    .decide_buy` already uses for its own `without=TooRisky`."""
    for entity, _item in w.each(Item):
        if w.has(entity, TooRisky):
            w.attach(entity, OnList())
        else:
            w.detach(entity, OnList)


def reply_bad_command(w) -> None:
    for entity, bad in w.each(BadCommand):
        w.destroy(entity)
        reply(w, "! %s" % bad.why)


RULES = (hear_stock, hear_needby, hear_status,
         project_urgency, flag_too_risky, add_to_list,
         reply_bad_command)


def install(loop, tolerance: float = 0.6, catalog=DEFAULT_ITEMS) -> None:
    """Register every rule above (each gated automatically on its own
    reads -- there is no `watches=` to pass by hand any more, see
    `loopingrules.loop`'s own module note), then seed the catalog and the
    judge's own `RiskTolerance` -- same BigFloor-style "only if not
    already there" policy as `cards.install`."""
    loop.rule(hear_stock)
    loop.rule(hear_needby)
    loop.rule(hear_status)
    loop.rule(project_urgency)
    loop.rule(flag_too_risky)
    loop.rule(add_to_list)
    loop.rule(reply_bad_command)

    world = loop.world
    for item in catalog:
        if _find_item(world, item.name) is None:
            entity = world.spawn(item)
            world.attach(entity, Stock(0))
    if world.first(RiskTolerance) is None:
        world.spawn(RiskTolerance(max_level=tolerance))
    world.learn("stock", "needby", "status", *(i.name for i in catalog))
