"""store.Overlay: the sheet with a delta applied, without copying the sheet."""

import pytest
from rdflib import RDF, Graph, Literal, Namespace

from loopingrules.store import Overlay, apply_delta, copy_graph

EX = Namespace("https://example.org/")


@pytest.fixture
def base():
    g = Graph()
    g.bind("ex", EX)
    g.add((EX.a, RDF.type, EX.Box))
    g.add((EX.a, EX.next, EX.b))
    g.add((EX.b, EX.next, EX.c))
    g.add((EX.b, EX.size, Literal(1)))
    return g


DELETES = {(EX.b, EX.next, EX.c), (EX.nope, EX.p, EX.q)}  # the second isn't in the base
INSERTS = {(EX.c, RDF.type, EX.Box), (EX.b, EX.next, EX.d), (EX.a, RDF.type, EX.Box)}  # the last is already there


def copy_with_delta(base):
    c = copy_graph(base)
    apply_delta(c, DELETES, INSERTS)
    return c


def test_overlay_has_the_same_triples_as_a_copy(base):
    o, c = Overlay(base, DELETES, INSERTS), copy_with_delta(base)
    assert set(o) == set(c) and len(o) == len(c)
    assert o.deleted == {(EX.b, EX.next, EX.c)}  # net change only
    assert o.added == {(EX.c, RDF.type, EX.Box), (EX.b, EX.next, EX.d)}


@pytest.mark.parametrize("pattern", [(None, None, None), (EX.b, None, None), (None, EX.next, None),
                                     (None, RDF.type, EX.Box), (EX.b, EX.next, EX.c), (EX.b, EX.next, EX.d)])
def test_patterns_and_membership(base, pattern):
    o, c = Overlay(base, DELETES, INSERTS), copy_with_delta(base)
    assert set(o.triples(pattern)) == set(c.triples(pattern))
    assert (pattern in o) == (pattern in c)


@pytest.mark.parametrize("query", [
    "SELECT ?x WHERE { ?x a ex:Box }",
    "SELECT ?x ?y WHERE { ?x ex:next+ ?y }",
    "SELECT ?x WHERE { ?x ex:next ?y FILTER NOT EXISTS { ?y ex:next ?z } }",
    "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }",
])
def test_sparql_sees_the_same_state(base, query):
    q = "PREFIX ex: <https://example.org/>\n" + query
    o, c = Overlay(base, DELETES, INSERTS), copy_with_delta(base)
    assert sorted(map(tuple, o.query(q))) == sorted(map(tuple, c.query(q)))


def test_the_base_is_never_modified(base):
    before = set(base)
    o = Overlay(base, DELETES, INSERTS)
    o.remove((EX.a, RDF.type, EX.Box))
    o.add((EX.z, EX.p, EX.q))
    assert set(base) == before


def test_add_and_remove_keep_the_net_change(base):
    o = Overlay(base)
    o.remove((EX.a, EX.next, EX.b))
    o.add((EX.a, EX.next, EX.b))  # undoes the removal
    o.add((EX.n, EX.p, EX.q))
    o.remove((EX.n, EX.p, EX.q))  # undoes the addition
    assert not o.deleted and not o.added and set(o) == set(base)
    with pytest.raises(ValueError):
        o.remove((EX.a, None, None))


def test_prefixes_are_the_base_ones(base):
    assert Overlay(base).namespace_manager is base.namespace_manager
