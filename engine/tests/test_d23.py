"""Design D23: operation patterns use a subset of SPARQL; controllers carry lr:weight."""

from pathlib import Path

import pytest
from rdflib import Graph

from loopingrules.controllers import load_controllers
from loopingrules.engine import Engine
from loopingrules.operations import load_operations
from loopingrules.patterns import UnsupportedPattern, check_pattern
from loopingrules.project import Project

PFX = ("@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> . "
       "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
SPARQL_PFX = "PREFIX ex: <https://example.org/>\n"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


# --- the subset ----------------------------------------------------------

@pytest.mark.parametrize("where", [
    "",
    "?s ex:a ?o",
    "?s a ex:T ; ex:a ?o . OPTIONAL { ?o ex:b ?z } BIND(CONCAT(STR(?s), 'x') AS ?k)",
    "{ ?s ex:c ?q } UNION { ?s ex:d ?q }",
    "?s ex:a ?o VALUES ?o { 1 2 }",
    "?s ex:a ?o FILTER(?o IN (1, 2) && EXISTS { ?s ex:b ?z })",
    "?s ex:a ?o FILTER NOT EXISTS { ?o ex:b ?z FILTER NOT EXISTS { ?z ex:c ?w } }",
])
def test_allowed_patterns(where):
    check_pattern(where, SPARQL_PFX)


@pytest.mark.parametrize("where, construct", [
    ("?s ex:a/ex:b ?o", "property paths"),
    ("?s ^ex:a ?o", "property paths"),
    ("?s ex:a* ?o", "property paths"),
    ("?s ex:a|ex:b ?o", "property paths"),
    ("{ SELECT ?s WHERE { ?s ex:a ?o } }", "subqueries"),
    ("{ SELECT ?s (COUNT(?o) AS ?n) WHERE { ?s ex:a ?o } GROUP BY ?s }", "aggregates"),
    ("?s ex:a ?o MINUS { ?s ex:b ?o }", "MINUS"),
    ("GRAPH ?g { ?s ex:a ?o }", "GRAPH"),
    # nested inside EXISTS, where rdflib keeps the parse tree
    ("?s ex:a ?o FILTER NOT EXISTS { { SELECT ?s WHERE { ?s ex:c ?z } } }", "subqueries"),
    ("?s ex:a ?o FILTER NOT EXISTS { ?o ex:b+ ?z }", "property paths"),
    ("?s ex:a ?o FILTER NOT EXISTS { ?o ex:b ?z MINUS { ?z ex:c ?o } }", "MINUS"),
    ("?s ex:a ?o FILTER EXISTS { GRAPH ?g { ?o ex:b ?z } }", "GRAPH"),
])
def test_refused_patterns(where, construct):
    with pytest.raises(UnsupportedPattern, match=construct):
        check_pattern(where, SPARQL_PFX)


def test_operation_outside_the_subset_is_refused_at_load():
    g = Graph().parse(data=PFX + '''
        ex:op a lr:Operation ; rdfs:label "chained" ;
          lr:where "?s ex:parent/ex:parent ?g" ;
          lr:insert "?s ex:grandparent ?g" .''', format="turtle")
    with pytest.raises(UnsupportedPattern, match="operation chained.*property paths"):
        load_operations(g)


@pytest.mark.parametrize("example", ["folder-scan", "folder-scan-goal"])
def test_examples_fit_the_subset(example):
    model = Graph().parse(EXAMPLES / example / "model.ttl")
    assert load_operations(model)


# --- weights ---------------------------------------------------------------

def test_weight_defaults_to_one_and_is_read():
    g = Graph().parse(data=PFX + '''
        ex:a a lr:Controller ; lr:query "SELECT (1 AS ?score) WHERE {}" .
        ex:b a lr:Controller ; lr:query "SELECT (1 AS ?score) WHERE {}" ; lr:weight -2.5 .''',
        format="turtle")
    assert [c.weight for c in load_controllers(g)] == [1.0, -2.5]


def test_weight_must_be_a_number():
    g = Graph().parse(data=PFX + '''
        ex:a a lr:Controller ; lr:query "SELECT (1 AS ?score) WHERE {}" ; lr:weight "heavy" .''',
        format="turtle")
    with pytest.raises(ValueError, match="lr:weight"):
        load_controllers(g)


MODEL = PFX + '''
ex:makeA a lr:Operation ; rdfs:label "make a" ;
  lr:where "ex:x a ex:Thing . FILTER NOT EXISTS { ex:x ex:made ?any }" ; lr:insert "ex:x ex:made ex:a" .
ex:makeB a lr:Operation ; rdfs:label "make b" ;
  lr:where "ex:x a ex:Thing . FILTER NOT EXISTS { ex:x ex:made ?any }" ; lr:insert "ex:x ex:made ex:b" .
'''

CONTROLLERS = PFX + '''
ex:likeA a lr:Controller ; rdfs:label "like a" ;
  lr:query "SELECT (COUNT(?x) AS ?score) WHERE {{ ?x ex:made ex:a }}" ; lr:weight {wa} .
ex:likeB a lr:Controller ; rdfs:label "like b" ;
  lr:query "SELECT (COUNT(?x) AS ?score) WHERE {{ ?x ex:made ex:b }}" ; lr:weight {wb} .
'''


@pytest.mark.parametrize("wa, wb, winner", [(1, 3, "make b"), (3, 1, "make a")])
def test_weights_steer_the_winner(tmp_path, wa, wb, winner):
    (tmp_path / "model.ttl").write_text(MODEL)
    (tmp_path / "controllers.ttl").write_text(CONTROLLERS.format(wa=wa, wb=wb))
    (tmp_path / "sheet.ttl").write_text(PFX + "ex:x a ex:Thing .")
    eng = Engine(Project.load(tmp_path, persist=False))
    apps = {a.operation.name: a for a in eng.applications()}
    # scores hold each controller's weighted contribution, and the total sums them
    assert apps["make a"].scores == {"like a": wa, "like b": 0}
    assert apps["make b"].total == wb
    assert eng.step().application.operation.name == winner


def test_a_pattern_without_variables_has_one_solution(tmp_path):
    # rdflib returns no rows for SELECT * without variables; SPARQL says one empty solution.
    (tmp_path / "model.ttl").write_text(MODEL)
    (tmp_path / "controllers.ttl").write_text(PFX)
    (tmp_path / "sheet.ttl").write_text(PFX + "ex:x a ex:Thing .")
    eng = Engine(Project.load(tmp_path, persist=False))
    apps = eng.applications()
    assert sorted(a.operation.name for a in apps) == ["make a", "make b"]
    assert all(a.bindings == {} for a in apps)
    eng.step()
    assert eng.applications() == []  # the FILTER NOT EXISTS now fails: no solution
