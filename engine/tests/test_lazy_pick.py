"""Engine.pick (lazy validation) must choose exactly what choose(applications()) chooses."""

import shutil
from pathlib import Path

import pytest
from rdflib import RDF, Namespace

from loopingrules.engine import Engine, choose
from loopingrules.package import add_layer, export_project
from loopingrules.project import Project
from loopingrules.tools.shell import ShellTool

ROOT = Path(__file__).resolve().parents[2] / "examples"
EX = Namespace("https://example.org/folderscan#")
FILES = ["a.txt", "b.md", "c.txt", "d.txt", "e.txt", "f.txt", "noext", "sub/"]


def stub_shell():
    def run(cmd):
        if cmd.startswith("ls"):
            return 0, "".join(f + "\n" for f in FILES), ""
        if cmd.startswith("wc -l <"):
            return 0, "3\n", ""
        txt = [f for f in FILES if f.endswith(".txt")]  # batch
        return 0, "".join(f"  {i + 1} data/{f}\n" for i, f in enumerate(txt)) + "  15 total\n", ""
    return ShellTool(executor=run)


def project(tmp_path, example: str, layer: bool) -> Project:
    p = tmp_path / "proj"
    shutil.copytree(ROOT / example, p, ignore=shutil.ignore_patterns(".lr"))
    if layer:
        add_layer(export_project(ROOT / "big-folders", tmp_path / "pack.lr.zip").read_bytes(), p)
    proj = Project.load(p, persist=False)
    if example == "folder-scan-goal":  # a goal, as in test_goals
        proj.sheet.add((EX.g1, RDF.type, EX.CountLinesGoal))
        proj.sheet.add((EX.g1, EX.folder, EX.target))
    return proj


@pytest.mark.parametrize("example, layer", [("folder-scan", False), ("folder-scan", True),
                                            ("folder-scan-goal", False)])
def test_pick_matches_the_eager_choice_at_every_tick(tmp_path, example, layer):
    eng = Engine(project(tmp_path, example, layer), shell=stub_shell(), approver=lambda c: True)
    ticks = 0
    while True:
        eng.tool_phase()
        eager = choose(eng.applications())
        lazy = eng.pick()
        assert (lazy and lazy.id) == (eager and eager.id)
        if lazy is None:
            break
        assert lazy.total == eager.total
        eng.apply(lazy, run_tools=False)
        ticks += 1
    assert ticks > 3


PFX = ("@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> . "
       "@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")

# "big" scores highest but breaks the shape (at most one size); "small" is the valid winner.
MODEL = PFX + '''
ex:BoxShape a sh:NodeShape ; sh:targetClass ex:Box ; sh:property [ sh:path ex:size ; sh:maxCount 1 ] .
ex:big a lr:Operation ; rdfs:label "big" ;
  lr:where "?b a ex:Box . FILTER NOT EXISTS { ?b ex:size 1 }" ; lr:insert "?b ex:size 1, 2" .
ex:small a lr:Operation ; rdfs:label "small" ;
  lr:where "?b a ex:Box . FILTER NOT EXISTS { ?b ex:size ?s }" ; lr:insert "?b ex:size 1" .
ex:stop a lr:Operation ; rdfs:label "stop" ; lr:where "" .
'''
CONTROLLERS = PFX + '''
ex:sizes a lr:Controller ; rdfs:label "sizes" ;
  lr:query "SELECT (COUNT(*) AS ?score) WHERE {{ GRAPH lr:inserted {{ ?b ex:size ?s }} }}" .
ex:stopping a lr:Controller ; rdfs:label "stopping" ;
  lr:query "SELECT ({stop} AS ?score) WHERE {{ GRAPH lr:action {{ lr:this lr:operation ex:stop }} }}" .
'''


@pytest.mark.parametrize("stop, winner", [(0, "small"), (1, "small"), (1.5, "stop"), (3, "stop")])
def test_an_invalid_top_candidate_is_skipped(tmp_path, stop, winner):
    # big = 2 (invalid), small = 1, stop = `stop`: stop must strictly beat small
    (tmp_path / "model.ttl").write_text(MODEL)
    (tmp_path / "controllers.ttl").write_text(CONTROLLERS.format(stop=stop))
    (tmp_path / "sheet.ttl").write_text(PFX + "ex:b1 a ex:Box .")
    eng = Engine(Project.load(tmp_path, persist=False))
    assert eng.pick().operation.name == winner == choose(eng.applications()).operation.name
