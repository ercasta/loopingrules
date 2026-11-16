"""The batteries: reusable models that name no domain, compose on one loop through
a shared shape, and (with `read_table`) turn a CSV into a choice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopingrules import schema
from loopingrules.world import World
from loopingrules_lang import harness, tools

PKG = Path(harness.__file__).resolve().parent
MODELS = PKG / "models"
BATTERIES = PKG / "batteries"

CORE = BATTERIES / "core.yaml"
SCOPE = BATTERIES / "scope.yaml"
RANK = BATTERIES / "rank.yaml"
TABLE = MODELS / "table.yaml"
TABLE_CTX = MODELS / "table.context.yaml"
TIMETABLE = MODELS / "timetable.csv"


def _context(*entities):
    return {"entities": list(entities)}


def test_batteries_compose_on_one_loop_through_the_shared_shape():
    models = [harness.load(path) for path in (CORE, SCOPE, RANK)]
    run = harness.run(models, _context(
        {"candidate": {"worth": 5.0, "label": "goblin"}},
        {"candidate": {"worth": 25.0, "label": "wand"}},
        {"candidate": {"worth": 40.0, "label": "dragon"}},
        {"policy": {"order": "min", "limit": 30.0}},
    ))
    assert run.settled
    assert run.chosen_of("candidate", "label") == {"goblin"}   # 40 out, min of {5,25}


def test_a_battery_using_an_undeclared_component_is_refused():
    with pytest.raises(schema.Gap):
        harness.run([harness.load(RANK)], _context({"candidate": {"worth": 1.0}}))


def test_read_table_coerces_declared_columns():
    world = World()
    tools.read_table(world, str(TIMETABLE), "departure",
                     ["train:str", "depart:minutes", "fare:float"])
    rows = {world.get(entity, "departure", "train"):
            (world.get(entity, "departure", "depart"),
             world.get(entity, "departure", "fare"))
            for entity, in world.each("departure")}
    assert rows["R1"] == (390, 45.0)      # "06:30" -> 390, "45" -> 45.0
    assert rows["IC1"] == (420, 90.0)


def test_csv_to_choice_end_to_end():
    """Four models on one loop: read the CSV, project onto `candidate`, scope by
    the limit, rank the cheapest -- no per-use-case code."""
    run = harness.run_files([CORE, SCOPE, RANK, TABLE], TABLE_CTX,
                            tools=tools.TOOLS)
    assert run.settled
    assert run.gaps() == []
    assert run.chosen_of("candidate", "label") == {"EZ"}   # 30, the only fare <= 50
