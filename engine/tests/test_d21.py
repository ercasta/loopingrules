"""Design D21: stopping is an authored no-op operation."""

from fastapi.testclient import TestClient
from rdflib import Literal, Namespace

from loopingrules.api import create_app
from loopingrules.engine import Engine
from loopingrules.project import Project
from loopingrules.vocab import LR

EX = Namespace("https://example.org/")

PFX = ("@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> . "
       "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")

# Three items to tag, one at a time, plus a stop that is always available.
MODEL = PFX + '''
ex:tag a lr:Operation ; rdfs:label "tag" ;
  lr:where  "?x ex:untagged true" ;
  lr:delete "?x ex:untagged true" ;
  lr:insert "?x ex:tagged true" .
ex:stop a lr:Operation ; rdfs:label "stop" ; lr:where "" .
'''

SHEET = PFX + "ex:a ex:untagged true . ex:b ex:untagged true . ex:c ex:untagged true ."

# Stopping scores 1.5; tagging scores 2 until two items are tagged, then 0: stop wins at the cap.
CAPPED = PFX + '''
ex:stopValue a lr:Controller ; rdfs:label "stop value" ;
  lr:query """SELECT (1.5 AS ?score) WHERE { GRAPH lr:action { lr:this lr:operation ex:stop } }""" .
ex:tagValue a lr:Controller ; rdfs:label "tag value" ;
  lr:query """SELECT (IF(?done >= 2, 0, 2) AS ?score) WHERE {
                GRAPH lr:action { lr:this lr:operation ex:tag }
                { SELECT (COUNT(?t) AS ?done) WHERE { GRAPH lr:before { ?t ex:tagged true } } } }""" .
'''


def make(tmp_path, controllers=PFX, model=MODEL, sheet=SHEET) -> Engine:
    (tmp_path / "model.ttl").write_text(model)
    (tmp_path / "controllers.ttl").write_text(controllers)
    (tmp_path / "sheet.ttl").write_text(sheet)
    return Engine(Project.load(tmp_path, persist=False))


def count(eng, prop: str) -> int:
    return len(list(eng.sheet.subjects(EX[prop], None)))


def test_a_noop_application_is_offered_with_an_empty_delta(tmp_path):
    eng = make(tmp_path)
    [stop] = [a for a in eng.applications() if a.operation.name == "stop"]
    assert stop.noop and not stop.inserts and not stop.deletes and stop.bindings == {}
    assert stop.valid


def test_ties_go_to_continuing(tmp_path):
    # no controllers: every total is 0, so the stop never strictly wins until nothing else is left
    eng = make(tmp_path)
    results = []
    eng.run(on_step=results.append)
    assert [r.status for r in results] == ["applied"] * 3 + ["stopped"]
    assert results[-1].application.operation.name == "stop"
    assert count(eng, "tagged") == 3


def test_controllers_can_make_stop_win(tmp_path):
    eng = make(tmp_path, controllers=CAPPED)
    journal = len(eng.project.journal)
    result = eng.run()
    assert result.status == "stopped" and result.application.operation.name == "stop"
    assert count(eng, "tagged") == 2 and count(eng, "untagged") == 1
    assert len(eng.project.journal) == journal + 2  # the stop itself is not journaled


def test_a_noop_is_available_only_when_its_where_matches(tmp_path):
    model = MODEL.replace('lr:where "" .', 'lr:where "ex:goal lr:reached true" .')
    eng = make(tmp_path, model=model)
    assert "stop" not in [a.operation.name for a in eng.applications()]
    eng.edit(add=[(EX.goal, LR.reached, Literal(True))])
    assert "stop" in [a.operation.name for a in eng.applications()]


def test_without_a_noop_autopilot_runs_until_nothing_is_applicable(tmp_path):
    eng = make(tmp_path, model=MODEL.replace('ex:stop a lr:Operation ; rdfs:label "stop" ; lr:where "" .', ""))
    assert eng.run().status == "done"


def test_an_operation_with_effects_but_an_empty_delta_is_still_dropped(tmp_path):
    # inserts a triple that already exists: an accidental empty delta, not a stop
    model = PFX + '''
    ex:again a lr:Operation ; rdfs:label "again" ; lr:where "?x ex:untagged true" ; lr:insert "?x ex:untagged true" .
    '''
    assert make(tmp_path, model=model).applications() == []


def test_applying_a_noop_by_hand_changes_nothing(tmp_path):
    eng = make(tmp_path)
    before, journal = set(eng.sheet), len(eng.project.journal)
    stop = next(a for a in eng.applications() if a.noop)
    eng.apply(stop)
    assert set(eng.sheet) == before and len(eng.project.journal) == journal


def test_api_marks_noops_and_logs_a_manual_stop(tmp_path):
    (tmp_path / "model.ttl").write_text(MODEL)
    (tmp_path / "controllers.ttl").write_text(CAPPED)
    (tmp_path / "sheet.ttl").write_text(SHEET)
    with TestClient(create_app(tmp_path, trust_path=tmp_path / "trust.ttl")) as c:
        apps = c.get("/api/applications").json()["applications"]
        stop = next(a for a in apps if a["operation"] == "stop")
        assert stop["noop"] and not any(a["noop"] for a in apps if a is not stop)
        assert c.post(f"/api/apply/{stop['id']}").status_code == 200
        state = c.get("/api/state").json()
        assert state["log"][-1]["text"] == "stop chosen: stop"
        # step until autopilot stops by itself
        statuses = [c.post("/api/autopilot/step").json()["status"] for _ in range(3)]
        assert statuses == ["applied", "applied", "stopped"]
        assert c.get("/api/state").json()["log"][-1]["text"] == "autopilot stopped: stop won"

