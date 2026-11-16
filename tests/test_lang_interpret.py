"""The `interpret` battery: competing readings of ONE input, a confidence floor,
and abstention on a tie (ADR-8's ambiguity discipline).
"""

from __future__ import annotations

from pathlib import Path

from loopingrules_lang import cli, harness, tools

PKG = Path(harness.__file__).resolve().parent
CORE = PKG / "batteries" / "core.yaml"
SCOPE = PKG / "batteries" / "scope.yaml"
INTERPRET = PKG / "batteries" / "interpret.yaml"
WHEN = PKG / "models" / "when.yaml"
WHEN_CTX = PKG / "models" / "when.context.yaml"
MODELS = [CORE, SCOPE, INTERPRET, WHEN]


def _run(text, **policy):
    entities = [{"input": {"text": text}}]
    if policy:
        entities.append({"policy": policy})
    return harness.run([harness.load(path) for path in MODELS],
                       {"entities": entities}, tools=tools.TOOLS)


def test_a_single_format_is_chosen():
    run = _run("2026-04-03 09:00")
    assert run.settled
    assert run.chosen_of("candidate", "label") == {"iso"}
    assert run.gaps() == []


def test_an_ambiguous_date_abstains_on_the_tie():
    """d/m and m/d are equally confident -- so nothing is chosen, and the input is
    marked UNDETERMINED rather than guessed."""
    run = _run("03/04/2026 09:00", floor=0.5)
    assert run.chosen_of("candidate", "label") == set()
    assert run.gaps() == ["03/04/2026 09:00"]


def test_a_floor_can_drop_the_only_reading():
    run = _run("2026-04-03", floor=0.95)          # iso-date is 0.9
    assert run.chosen_of("candidate", "label") == set()
    assert run.gaps() == ["2026-04-03"]


def test_a_text_no_format_parses_is_a_gap():
    run = _run("banana")
    assert run.chosen_of("candidate", "label") == set()
    assert run.gaps() == ["banana"]


def test_readings_project_confidence_onto_candidate():
    run = _run("03/04/2026 09:00")
    readings = {(run.world.get(entity, "reading", "format"),
                 run.world.get(entity, "candidate", "worth"))
                for entity, in run.world.each("reading")}
    assert readings == {("dmy", 0.6), ("mdy", 0.6)}


def test_cli_runs_the_when_model(capsys):
    code = cli.main(["run", str(CORE), str(SCOPE), str(INTERPRET), str(WHEN),
                     "-c", str(WHEN_CTX)])
    out = capsys.readouterr().out
    assert code == 0
    assert "when.undetermined" in out
    assert "unresolved" in out
