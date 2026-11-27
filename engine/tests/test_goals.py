"""Goals as a modelling pattern (design D16): no engine support involved."""

import shutil
from pathlib import Path

import pytest
from rdflib import Literal, Namespace
from rdflib.namespace import RDF, XSD

from loopingrules.engine import Engine
from loopingrules.project import Project
from loopingrules.tools.shell import ShellTool
from loopingrules.vocab import LR

EX = Namespace("https://example.org/folderscan#")
EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "folder-scan-goal"


def stub_shell():
    def run(cmd):
        if cmd.startswith("ls"):
            return 0, "a.txt\nb.md\nnotes.txt\nsub/\n", ""
        if cmd.startswith("wc"):
            return 0, "7\n", ""
        raise AssertionError(cmd)
    return ShellTool(executor=run)


@pytest.fixture
def project(tmp_path):
    proj = tmp_path / "proj"
    shutil.copytree(EXAMPLE, proj)
    p = Project.load(proj)
    # a second folder that no goal mentions
    p.sheet.add((EX.other, RDF.type, EX.Folder))
    p.sheet.add((EX.other, EX.path, Literal("elsewhere")))
    return p


def add_goal(p: Project, goal=EX.g1, folder=EX.target):
    p.sheet.add((goal, RDF.type, EX.CountLinesGoal))
    p.sheet.add((goal, EX.folder, folder))


def test_nothing_happens_without_a_goal(project):
    eng = Engine(project, shell=stub_shell(), approver=lambda c: True)
    assert eng.applications() == []
    assert eng.step().status == "done"


def test_goal_is_not_reached_vacuously(project):
    add_goal(project)
    apps = Engine(project).applications()
    assert [a.operation.name for a in apps] == ["scan folder"]
    assert apps[0].bindings["folder"] == EX.target  # not ex:other


def test_autopilot_reaches_the_goal_and_stops(project):
    add_goal(project)
    eng = Engine(project, shell=stub_shell(), approver=lambda c: True)
    ticks = []
    result = eng.run(max_ticks=60, on_step=lambda r: ticks.append(r.application and r.application.operation.name))
    g = eng.sheet

    assert result.status == "done"
    assert (EX.g1, LR.reached, Literal(True)) in g
    # "goal reached" is the last thing autopilot did, then nothing was applicable
    assert [t for t in ticks if t][-1] == "goal reached"
    counted = {str(g.value(f, EX.name)): g.value(f, EX.lineCount) for f in g.subjects(EX.lineCount, None)}
    assert counted == {"a.txt": Literal(7, datatype=XSD.integer), "notes.txt": Literal(7, datatype=XSD.integer)}
    # the folder without a goal was never touched
    assert (EX.other, EX.scanned, Literal(True)) not in g
    assert eng.sheet_violations() == []


def test_a_second_goal_restarts_the_loop(project):
    add_goal(project)
    eng = Engine(project, shell=stub_shell(), approver=lambda c: True)
    eng.run(max_ticks=60)
    add_goal(project, goal=EX.g2, folder=EX.other)
    assert [a.operation.name for a in eng.applications()] == ["scan folder"]
    assert eng.run(max_ticks=60).status == "done"
    assert (EX.g2, LR.reached, Literal(True)) in eng.sheet


def test_goal_shape_guides_editing(project):
    from loopingrules.suggest import Suggester

    project.sheet.add((EX.g1, RDF.type, EX.CountLinesGoal))
    eng = Engine(project)
    missing = [p["term"] for p in Suggester(eng.shapes, eng.sheet).missing(EX.g1)]
    assert missing == [EX.folder]
    objs = Suggester(eng.shapes, eng.sheet).objects(EX.g1, EX.folder)
    assert {v["term"] for v in objs["values"]} == {EX.target, EX.other}
