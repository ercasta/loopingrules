"""The tool seam: a registry of capabilities the harness answers between ticks.

A tool is ``fn(world, **kwargs) -> None``: it **reifies** its result into the world
as ordinary entities and components (ADR-11's "reifies the output back as ordinary
entities"). The operation that wants it deposits the capability's OWN request
component (``<capability>_request``, via ``emit`` with named ``with:`` arguments);
the answerer keys on that component, passes its fields as keyword arguments, and
marks the outcome. The model reads whatever the tool wrote, by component. Free
Python is confined here.

## The train timetable reader

``train_timetable(world, path)`` reads a CSV with the header

    train,from,to,depart,arrive,fare

and creates one **``departure``** entity per row. Its **return schema**:

    departure{train: str, from: str, to: str,
              depart: int, arrive: int, fare: number}

``depart``/``arrive`` are MINUTES SINCE MIDNIGHT (so a model can compare and
reduce them); ``fare`` is a number. A model that reads departures declares this
component -- an undeclared use is a ``schema.Gap``.
"""

from __future__ import annotations

import csv
from datetime import datetime


def _minutes(text) -> int:
    """``"09:15"`` -> 555. A bare number is already minutes."""
    text = str(text).strip()
    if ":" not in text:
        return int(float(text))
    hours, minutes = text.split(":", 1)
    return int(hours) * 60 + int(minutes)


def train_timetable(world, path) -> None:
    """The train timetable reader. Return schema: a ``departure`` per CSV row."""
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            entity = world.spawn()
            world.set(entity, "departure", "train", row["train"].strip())
            world.set(entity, "departure", "from", row["from"].strip())
            world.set(entity, "departure", "to", row["to"].strip())
            world.set(entity, "departure", "depart", _minutes(row["depart"]))
            world.set(entity, "departure", "arrive", _minutes(row["arrive"]))
            world.set(entity, "departure", "fare", float(row["fare"]))


def echo(world, *args) -> None:
    """A trivial tool, for tests: one ``echoed{text}`` per call."""
    world.set(world.spawn(), "echoed", "text",
              " ".join(str(arg) for arg in args))


def _coerce(text, kind):
    """A CSV cell -> a primitive. The type is a COERCION at the edge, never a
    stored type (PRINCIPLES.md: values are primitives only)."""
    text = str(text).strip()
    if kind in ("str", "string"):
        return text
    if kind == "int":
        return int(float(text))
    if kind == "float":
        return float(text)
    if kind == "minutes":
        return _minutes(text)
    if kind == "bool":
        return text.lower() in ("true", "1", "yes")
    raise ValueError("unknown column type %r (use str/int/float/minutes/bool)"
                     % kind)


def read_table(world, path, relation, columns) -> None:
    """The generic tabular reader. ``relation`` is the component the rows become;
    ``columns`` is a list of ``"name:type"`` strings (or one comma-separated
    string); a missing type is ``str``. **Return schema**: one
    ``relation{name: value, ...}`` entity per CSV row, the values coerced.
    ``train_timetable`` is this with the schema baked in."""
    if isinstance(columns, str):
        columns = [part for part in columns.split(",") if part.strip()]
    spec = []
    for item in columns:
        name, _, kind = str(item).partition(":")
        spec.append((name.strip(), kind.strip() or "str"))
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            entity = world.spawn()
            for name, kind in spec:
                world.set(entity, relation, name, _coerce(row[name], kind))


## The interpretation adapter: one `reading` per format that parses.
#
# Ambiguous formats (d/m vs m/d) get EQUAL confidence, so a tie stays a tie for
# the `interpret` battery to abstain on rather than guess.
_DATETIME_FORMATS = (
    ("%Y-%m-%d %H:%M", "iso", 0.99),
    ("%Y-%m-%dT%H:%M", "iso-t", 0.99),
    ("%Y-%m-%d", "iso-date", 0.9),
    ("%d/%m/%Y %H:%M", "dmy", 0.6),
    ("%m/%d/%Y %H:%M", "mdy", 0.6),
    ("%d/%m/%Y", "dmy-date", 0.55),
    ("%m/%d/%Y", "mdy-date", 0.55),
    ("%H:%M", "time", 0.5),
)


def _normalise(parsed, fmt) -> str:
    if fmt == "%H:%M":
        return parsed.strftime("%H:%M")
    return parsed.strftime("%Y-%m-%dT%H:%M")


def interpret_datetime(world, text) -> None:
    """The interpretation adapter: try each known format, and emit one **`reading`**
    per format that parses. Return schema::

        reading{tool: str, text: str, format: str, value: str, confidence: number}

    ``value`` is a normalised ``YYYY-MM-DDTHH:MM`` (or ``HH:MM`` for a time-only
    text); ``confidence`` is the format's own weight. No format parses => no
    readings, which the caller reports as a gap."""
    for fmt, name, confidence in _DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        entity = world.spawn()
        world.set(entity, "reading", "tool", "interpret_datetime")
        world.set(entity, "reading", "text", text)
        world.set(entity, "reading", "format", name)
        world.set(entity, "reading", "value", _normalise(parsed, fmt))
        world.set(entity, "reading", "confidence", confidence)


TOOLS = {"train_timetable": train_timetable, "read_table": read_table,
         "interpret_datetime": interpret_datetime, "echo": echo}
