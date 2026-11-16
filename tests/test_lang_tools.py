"""The tool seam: `emit` -> a `tool_request` answered between ticks, and the train
timetable reader's return schema. The timetable is world data the model reads by
component; a scope and a choice then compose over it with no per-use-case code.
"""

from __future__ import annotations

from pathlib import Path

from loopingrules.world import World
from loopingrules_lang import cli, harness, tools

MODELS = Path(harness.__file__).resolve().parent / "models"
TRIP = MODELS / "trip.yaml"
TRIP_CTX = MODELS / "trip.context.yaml"
TIMETABLE = MODELS / "timetable.csv"


def test_minutes_parses_times():
    assert tools._minutes("09:15") == 555
    assert tools._minutes("07:00") == 420
    assert tools._minutes(390) == 390


def test_train_timetable_return_schema():
    world = World()
    tools.train_timetable(world, str(TIMETABLE))
    rows = {world.get(entity, "departure", "train"):
            (world.get(entity, "departure", "depart"),
             world.get(entity, "departure", "fare"))
            for entity, in world.each("departure")}
    assert rows == {"IC1": (420, 90.0), "IC2": (555, 60.0),
                    "R1": (390, 45.0), "EZ": (1380, 30.0)}


def _trip(**directive):
    model = harness.load(TRIP)
    do = {"timetable": str(TIMETABLE)}
    do.update(directive)
    return harness.run(model, {"entities": [{"do": do}]}, tools=tools.TOOLS)


def test_a_tool_request_is_answered_and_the_result_is_chosen():
    run = _trip(what="cheapest")
    assert run.settled
    assert run.gaps() == []
    assert run.chosen_of("departure", "train") == {"EZ"}     # 30, the night train


def test_a_scope_combines_with_the_choice():
    run = _trip(what="cheapest", before=480.0)               # 08:00
    assert run.chosen_of("departure", "train") == {"R1"}     # 45, the cheap morning


def test_earliest_is_a_second_choose_operation():
    assert _trip(what="earliest").chosen_of("departure", "train") == {"R1"}


def test_an_unknown_what_is_a_gap():
    run = _trip(what="scenic")
    assert run.chosen_of("departure", "train") == set()
    assert run.gaps() == ["scenic"]


def test_an_unknown_tool_is_world_data_not_a_crash():
    model = harness.parse({
        "model": "t",
        "components": {"do": {"timetable": "singular"},
                       "tool_request": {"name": "singular", "args": "sequence"},
                       "tool_failed": {"reason": "singular"}},
        "operations": [{"name": "ask",
                        "match": {"component": "do", "fields": ["timetable"],
                                  "without": ["tool_request"]},
                        "effect": [{"emit": {"request": "nope",
                                             "args": [{"field": "timetable"}]}}]}],
    })
    run = harness.run(model, {"entities": [{"do": {"timetable": "x"}}]}, tools={})
    assert run.settled
    assert any(run.world.has(entity, "tool_failed")
               for entity in run.world.entities())


def test_cli_runs_the_trip_model(capsys):
    code = cli.main(["run", str(TRIP), "-c", str(TRIP_CTX), "--json"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"settled": true' in out
    assert "EZ" in out
