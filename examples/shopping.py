"""`shopping` -- a household shopping list, and the second real domain to
ask `loopingrules_patterns.judge`'s risk convention to serve it.

`cards` projects RESOURCE EXHAUSTION; `project_urgency` here projects TIME
PRESSURE -- a domain with no notion of money at all. Both write
`risk_level`/`risk_reason` and are thresholded by the same oblivious
`flag_too_risky` into a `too_risky` flag. Under the attribute substrate (D8)
a `stock`/`needed` fact is an attribute on the `item` entity, and the judge's
`max_level` is a singleton.
"""

from __future__ import annotations

from loopingrules.engine import reply
from loopingrules_patterns.judge import flag_too_risky, seed_tolerance


HORIZON_DAYS = 7

DEFAULT_ITEMS = ("milk", "eggs", "bread", "coffee", "batteries")


def _find_item(w, name: str):
    """The `item` entity named `name`, case-insensitively, or `None`."""
    for entity, _tag, item_name in w.each("item", "name"):
        if item_name.lower() == name.lower():
            return entity
    return None


def _parse_nonneg_int(text: str):
    """A non-negative int, or `None`."""
    try:
        value = int(text)
    except ValueError:
        return None
    return value if value >= 0 else None


def _bad(w, text: str, why: str) -> None:
    entity = w.spawn()
    w.mark(entity, "bad_command")
    w.set(entity, "text", text)
    w.set(entity, "why", why)


# -- hearing ------------------------------------------------------------

def hear_stock(w) -> None:
    """`stock <item> <qty>` -> the `stock` attribute on that item."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "stock":
            continue
        w.destroy(entity)
        if len(words) != 3:
            _bad(w, text, "usage: stock <item> <qty>")
            continue
        item = _find_item(w, words[1])
        if item is None:
            _bad(w, text, "unknown item %r" % words[1])
            continue
        qty = _parse_nonneg_int(words[2])
        if qty is None:
            _bad(w, text, "not a quantity: %r" % words[2])
            continue
        w.set(item, "stock", qty)


def hear_needby(w) -> None:
    """`needby <item> <days>` -> the `needed` attribute on that item."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "needby":
            continue
        w.destroy(entity)
        if len(words) != 3:
            _bad(w, text, "usage: needby <item> <days>")
            continue
        item = _find_item(w, words[1])
        if item is None:
            _bad(w, text, "unknown item %r" % words[1])
            continue
        days = _parse_nonneg_int(words[2])
        if days is None:
            _bad(w, text, "not a day count: %r" % words[2])
            continue
        w.set(item, "needed", days)


def hear_status(w) -> None:
    """`status` -> stock, deadline (if any), and whether the judge's own
    `too_risky` currently flags it, per item."""
    for entity, _tag, text in w.each("said", "text"):
        words = text.split()
        if not words or words[0].lower() != "status":
            continue
        w.destroy(entity)
        lines = []
        rows = sorted(w.each("item", "name"), key=lambda row: row[2])
        for item_entity, _itag, item_name in rows:
            have = w.get(item_entity, "stock", 0)
            line = "%s: %d in stock" % (item_name, have)
            if w.has(item_entity, "needed"):
                line += ", needed in %d day(s)" % w.get(item_entity, "needed")
            if w.has(item_entity, "on_list"):
                line += " -- on the list"
            lines.append(line)
        reply(w, "user", "; ".join(lines) if lines else "no items")


# -- projecting, and acting on the judge's verdict ----------------------

def project_urgency(w) -> None:
    """`risk_level`/`risk_reason`, set fresh onto every item carrying a
    `needed` deadline. An item with no deadline gets no projection at all."""
    for entity, _tag, needed in w.each("item", "needed"):
        level = max(0.0, min(1.0, 1.0 - needed / HORIZON_DAYS))
        w.set(entity, "risk_level", level)
        w.set(entity, "risk_reason",
              "needed in %d day(s), %.0f%% of the %d-day horizon"
              % (needed, level * 100, HORIZON_DAYS))


def add_to_list(w) -> None:
    """`on_list` iff the judge's own `too_risky` is currently set -- both
    directions, every tick. This rule computes nothing itself."""
    for entity, _tag in w.each("item"):
        if w.has(entity, "too_risky"):
            w.mark(entity, "on_list")
        else:
            w.unmark(entity, "on_list")


def reply_bad_command(w) -> None:
    for entity, _tag, why in w.each("bad_command", "why"):
        w.destroy(entity)
        reply(w, "user", "! %s" % why)


RULES = (hear_stock, hear_needby, hear_status,
         project_urgency, flag_too_risky, add_to_list,
         reply_bad_command)


def install(loop, tolerance: float = 0.6, catalog=DEFAULT_ITEMS) -> None:
    """Register every rule, then seed the catalog and the judge's own
    tolerance."""
    loop.rule(hear_stock)
    loop.rule(hear_needby)
    loop.rule(hear_status)
    loop.rule(project_urgency)
    loop.rule(flag_too_risky)
    loop.rule(add_to_list)
    loop.rule(reply_bad_command)

    world = loop.world
    for name in catalog:
        if _find_item(world, name) is None:
            entity = world.spawn()
            world.mark(entity, "item")
            world.set(entity, "name", name)
            world.set(entity, "stock", 0)
    seed_tolerance(world, tolerance)
