"""D31: the planning pack, on a domain that isn't a cube: a counter.

The domain answers checks ("the value is at least n") and carries out one action
(ex:inc, add one). The pack runs the method: stages, cases, procedures, Repeat, Until.
"""

from pathlib import Path

import pytest
from rdflib import Literal, Namespace

from loopingrules.engine import Engine
from loopingrules.package import PackageError, add_layer, export_project, import_export
from loopingrules.project import Project

PLANNING = Path(__file__).resolve().parents[2] / "examples" / "planning"
EX = Namespace("https://example.org/counter#")
PL = Namespace("https://loopingrules.org/planning#")

PFX = """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix lr: <https://loopingrules.org/ns#> .
@prefix pl: <https://loopingrules.org/planning#> .
@prefix ex: <https://example.org/counter#> .
"""

# The domain: how it answers checks, and its one action.
DOMAIN = PFX + '''
[] a lr:Package ; <http://purl.org/dc/terms/title> "counter" .
ex:answer a lr:Operation ; rdfs:label "read the counter" ;
  lr:params "" ;
  lr:where  """ ?k a pl:Check ; pl:condition ?c . FILTER NOT EXISTS { ?k pl:result ?any }
                ?c ex:atLeast ?n . ex:counter ex:value ?x . BIND(?x >= ?n AS ?r) """ ;
  lr:insert """ ?k pl:result ?r . """ .
ex:inc a lr:Operation ; rdfs:label "add one" ;
  lr:params "run" ;
  lr:where  """ ?run pl:doing ex:inc . ex:counter ex:value ?x . BIND(?x + 1 AS ?y) """ ;
  lr:delete """ ?run pl:doing ex:inc . ex:counter ex:value ?x . """ ;
  lr:insert """ ex:counter ex:value ?y . """ .
'''

# The method, as knowledge (named list nodes: knowledge has no blank nodes).
# Its procedure: repeat "add one" 3 times; until the value is at least 5, add one; add one.
METHOD = PFX + '''
ex:method a pl:Method ; pl:firstStage ex:count ; pl:view ex:asIs .
ex:count a pl:Stage ; rdfs:label "count to {goal}" ; pl:goal ex:goal .
ex:goal ex:atLeast {goal} .
ex:fiveOrMore ex:atLeast 5 .
ex:case a pl:Case ; pl:stage ex:count ; rdfs:label "always" ; pl:do ex:main {when}.
ex:never ex:atLeast 1000 .

ex:inc1 a pl:Procedure ; rdfs:label "add one" ; pl:steps ex:i0 .
ex:i0 rdf:first ex:inc ; rdf:rest rdf:nil .
ex:three a pl:Repeat ; pl:times 3 ; pl:do ex:inc1 .
ex:toFive a pl:Until ; pl:until ex:fiveOrMore ; pl:do ex:inc1 .
ex:main a pl:Procedure ; rdfs:label "main" ; pl:steps ex:m0 .
ex:m0 rdf:first ex:three ; rdf:rest ex:m1 .
ex:m1 rdf:first ex:toFive ; rdf:rest ex:m2 .
ex:m2 rdf:first ex:inc1 ; rdf:rest rdf:nil .
'''

SHEET = PFX + "ex:counter ex:value 0 .\n[] a pl:Run ; pl:method ex:method .\n"


def project(tmp_path, goal=7, when=""):
    d = tmp_path / "counter"
    d.mkdir()
    (d / "model.ttl").write_text(DOMAIN)
    (d / "method.ttl").write_text(METHOD.replace("{goal}", str(goal)).replace("{when}", when))
    (d / "sheet.ttl").write_text(SHEET)
    add_layer(export_project(PLANNING, tmp_path / "planning.lr.zip").read_bytes(), d)
    return Engine(Project.load(d, persist=False))


def said(eng):
    return [m.text for m in eng.messages("out")]


def value(eng):
    return int(eng.sheet.value(EX.counter, EX.value))


def test_the_planning_pack_is_a_library_any_project_can_install(tmp_path):
    eng = project(tmp_path)
    assert (tmp_path / "counter" / "layers" / "planning" / "planning.ttl").exists()
    assert any(op.name == "plan a case" for op in eng.operations)
    with pytest.raises(PackageError, match="library"):
        import_export((tmp_path / "planning.lr.zip").read_bytes(), tmp_path / "elsewhere")


def test_procedures_repeat_and_until(tmp_path):
    # 1st time: 3 (repeat) + 2 (until >= 5) + 1 = 6; the goal (7) fails, so again:
    # 3 + 0 (already >= 5) + 1 = 10, and the goal holds.
    eng = project(tmp_path, goal=7)
    assert eng.run(max_ticks=500).status == "done"
    assert value(eng) == 10
    assert said(eng) == ["Done: count to 7.", "Finished."]
    assert not list(eng.sheet.subjects(None, PL.Run)) and not list(eng.sheet.subjects(None, PL.Check))
    assert eng.sheet_violations() == []


def test_a_reached_goal_runs_nothing(tmp_path):
    eng = project(tmp_path, goal=0)
    assert eng.run(max_ticks=100).status == "done"
    assert value(eng) == 0
    assert said(eng) == ["Done: count to 0.", "Finished."]


def test_no_case_fits_says_stuck_and_stops(tmp_path):
    eng = project(tmp_path, goal=7, when="; pl:when ex:never ")
    assert eng.run(max_ticks=100).status == "done"
    assert value(eng) == 0
    assert said(eng) == ["Stuck in count to 7: no case fits."]
    assert (None, PL.stuck, Literal(True)) in eng.sheet


def test_the_domain_answers_every_check_in_one_tick(tmp_path):
    eng = project(tmp_path, goal=7)
    names = []
    eng.run(max_ticks=500, on_step=lambda r: names.append(r.application.operation.name if r.application else None))
    # each question round: look, ask, one answer, decide, forget
    assert names[:6] == ["start the method", "about to look", "look at the situation", "read the counter",
                         "plan a case", "forget the answers"]
