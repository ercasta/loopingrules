"""The tool seam: a registry of capabilities the harness answers between ticks.

A tool is ``fn(world, *args) -> None``: it **reifies** its result into the world as
ordinary entities and components (ADR-11's "reifies the output back as ordinary
entities"). The operation that wants it deposits a ``tool_request{name, args}``
(``emit``); the harness calls ``tools[name]`` and marks the outcome, and the model
reads whatever the tool wrote by component. Free Python is confined here.

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


def read_table(world, path, component, columns) -> None:
    """The generic tabular reader. ``columns`` is a ``"name:type"`` string, comma
    separated, or a list of them; a missing type is ``str``. **Return schema**: one
    ``component{name: value, ...}`` entity per CSV row, the values coerced. A
    ``"name:type"`` string (not a list) keeps the request a FLAT value -- the
    substrate stores flat values only. ``train_timetable`` is this with the schema
    baked in."""
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
                world.set(entity, component, name, _coerce(row[name], kind))


TOOLS = {"train_timetable": train_timetable, "read_table": read_table,
         "echo": echo}
