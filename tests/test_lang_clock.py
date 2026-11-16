"""The `clock` battery, and its composition with `interpret`: a text -> readings
-> a time of day -> a window. Five models on one loop.
"""

from __future__ import annotations

from pathlib import Path

from loopingrules.world import World
from loopingrules_lang import cli, harness, tools

PKG = Path(harness.__file__).resolve().parent
CORE = PKG / "batteries" / "core.yaml"
SCOPE = PKG / "batteries" / "scope.yaml"
INTERPRET = PKG / "batteries" / "interpret.yaml"
CLOCK = PKG / "batteries" / "clock.yaml"
WHEN = PKG / "models" / "when.yaml"
WHEN_WINDOW_CTX = PKG / "models" / "when.window.context.yaml"
MODELS = [CORE, SCOPE, INTERPRET, CLOCK, WHEN]


def _run(text, **policy):
    entities = [{"input": {"text": text}}]
    if policy:
        entities.append({"policy": policy})
    return harness.run([harness.load(path) for path in MODELS],
                       {"entities": entities}, tools=tools.TOOLS)


def _moment(run):
    rows = run.world.each("moment", "minutes")
    assert len(rows) == 1, rows
    entity, minutes = rows[0]
    return minutes, run.world.has(entity, "window")


def test_interpret_datetime_emits_time_of_day():
    world = World()
    tools.interpret_datetime(world, "2026-04-03 09:00")
    assert [minutes for _e, minutes in world.each("reading", "minutes")] == [540]


def test_a_moment_in_the_window_is_marked():
    run = _run("2026-04-03 09:00", after=480, before=540)     # 08:00 .. 09:00
    assert run.settled
    assert run.chosen_of("candidate", "label") == {"iso"}     # determinate text
    assert _moment(run) == (540, True)


def test_a_moment_outside_the_window_is_left_out():
    run = _run("2026-04-03 09:00", after=480, before=500)     # 540 > 500
    assert _moment(run) == (540, False)


def test_without_a_window_nothing_is_marked():
    run = _run("2026-04-03 09:00")
    assert _moment(run) == (540, False)


def test_cli_runs_the_five_model_composition(capsys):
    code = cli.main(["run", str(CORE), str(SCOPE), str(INTERPRET), str(CLOCK),
                     str(WHEN), "-c", str(WHEN_WINDOW_CTX)])
    out = capsys.readouterr().out
    assert code == 0
    assert "clock.clock_window" in out
    assert "window" in out
