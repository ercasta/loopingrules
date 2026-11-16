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


TOOLS = {"train_timetable": train_timetable, "echo": echo}
