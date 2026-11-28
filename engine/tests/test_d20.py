"""Design D20: controllers see the application through named graphs."""

import pytest
from rdflib import Graph

from loopingrules.controllers import load_controllers, scoring_view
from loopingrules.engine import Engine
from loopingrules.project import Project
from loopingrules.vocab import LR

PFX = ("@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> . "
       "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")

MODEL = PFX + '''
ex:tag a lr:Operation ; rdfs:label "tag" ;
  lr:where  "?x ex:untagged true" ;
  lr:delete "?x ex:untagged true" ;
  lr:insert "?x ex:tagged true" .
'''

SHEET = PFX + "ex:a ex:untagged true . ex:b ex:untagged true . ex:old ex:tagged true ."

CONTROLLERS = {
    # the resulting state is still the default graph
    "after": "SELECT (COUNT(?s) AS ?score) WHERE { ?s ex:tagged true }",
    # the current sheet, before the action
    "before": "SELECT (COUNT(?s) AS ?score) WHERE { GRAPH lr:before { ?s ex:tagged true } }",
    "inserted": "SELECT (COUNT(*) AS ?score) WHERE { GRAPH lr:inserted { ?s ?p ?o } }",
    "deleted": "SELECT (10 * COUNT(*) AS ?score) WHERE { GRAPH lr:deleted { ?s ex:untagged true } }",
    # the action: its operation and bindings
    "is tag of a": """SELECT (COUNT(*) AS ?score) WHERE { GRAPH lr:action {
                          lr:this lr:operation ex:tag ; lr:binds [ lr:var "x" ; lr:value ex:a ] } }""",
    "graph names": "SELECT (COUNT(DISTINCT ?g) AS ?score) WHERE { GRAPH ?g { ?s ?p ?o } }",
    "other graph": "SELECT (COUNT(*) AS ?score) WHERE { GRAPH ex:nope { ?s ?p ?o } }",
}


def controllers_ttl() -> str:
    out = PFX
    for i, (label, q) in enumerate(CONTROLLERS.items()):
        out += f'ex:c{i} a lr:Controller ; rdfs:label "{label}" ; lr:query """{q}""" .\n'
    return out


@pytest.fixture
def engine(tmp_path):
    (tmp_path / "model.ttl").write_text(MODEL)
    (tmp_path / "controllers.ttl").write_text(controllers_ttl())
    (tmp_path / "sheet.ttl").write_text(SHEET)
    return Engine(Project.load(tmp_path, persist=False))


def test_controllers_see_before_delta_and_action(engine):
    apps = {str(a.bindings["x"]).rsplit("/", 1)[1]: a for a in engine.applications()}
    assert apps["a"].scores == {
        "after": 2,          # ex:old and ex:a
        "before": 1,         # only ex:old
        "inserted": 1,
        "deleted": 10,
        "is tag of a": 1,
        "graph names": 4,    # lr:before, lr:inserted, lr:deleted, lr:action
        "other graph": 0,
    }
    assert apps["b"].scores["is tag of a"] == 0


def test_the_sheet_is_not_changed_by_scoring(engine):
    before = set(engine.sheet)
    engine.applications()
    assert set(engine.sheet) == before


def test_named_graphs_are_built_only_when_reached(engine):
    app = engine.applications()[0]
    view = scoring_view(engine.sheet, app)
    only_default = next(c for c in engine.controllers if c.name == "after")
    only_default.score(engine.resulting_state(app), view, engine_prefixes(engine))
    assert view._made == {}
    delta = next(c for c in engine.controllers if c.name == "inserted")
    delta.score(engine.resulting_state(app), view, engine_prefixes(engine))
    assert list(view._made) == [LR.inserted]


def test_the_before_graph_is_the_live_sheet(engine):
    app = engine.applications()[0]
    before = scoring_view(engine.sheet, app).get_context(LR.before)
    assert before._base is engine.sheet


def test_a_controller_must_be_a_select():
    g = Graph().parse(data=PFX + 'ex:c a lr:Controller ; lr:query "ASK { ?s ?p ?o }" .', format="turtle")
    with pytest.raises(ValueError, match="must be a SELECT"):
        load_controllers(g)


def engine_prefixes(engine) -> str:
    from loopingrules.store import prologue
    return prologue(engine.project.controllers, engine.project.model, engine.sheet)
