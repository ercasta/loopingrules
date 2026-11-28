"""Graph helpers. v0 uses rdflib Graphs directly; this module is the seam for swapping stores later."""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Iterator

from rdflib import Dataset, Graph, URIRef
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.evaluate import evalPart
from rdflib.plugins.sparql.sparql import Query, QueryContext

Triple = tuple  # (s, p, o) of rdflib terms


def copy_graph(g: Graph) -> Graph:
    out = Graph()
    for prefix, ns in g.namespaces():
        out.bind(prefix, ns, override=True)
    out += g
    return out


def apply_delta(g: Graph, deletes: set[Triple], inserts: set[Triple]) -> None:
    for t in deletes:
        g.remove(t)
    for t in inserts:
        g.add(t)


def prologue(*graphs: Graph) -> str:
    """SPARQL PREFIX declarations for every prefix bound in the given graphs."""
    seen: dict[str, str] = {}
    for g in graphs:
        for prefix, ns in g.namespaces():
            seen.setdefault(prefix, str(ns))
    return "".join(f"PREFIX {p}: <{ns}>\n" for p, ns in seen.items())


class NamedView(Graph):
    """A read-only view of `base` under another name, without copying it."""

    def __init__(self, base: Graph, identifier: URIRef):
        super().__init__(identifier=identifier)
        self._base = base

    def triples(self, pattern):  # type: ignore[override]
        return self._base.triples(pattern)

    def __len__(self) -> int:
        return len(self._base)

    def __contains__(self, triple) -> bool:
        return triple in self._base


class NamedGraphs(Dataset):
    """The named graphs a query can reach with GRAPH; each is built on first use.

    A GRAPH with any other name sees an empty graph.
    """

    def __init__(self, makers: dict[URIRef, Callable[[], Graph]]):
        super().__init__()
        self._makers = makers
        self._made: dict[URIRef, Graph] = {}

    def get_context(self, identifier, quoted=False, base=None):  # type: ignore[override]
        if identifier not in self._made:
            make = self._makers.get(identifier)
            self._made[identifier] = make() if make else Graph(identifier=identifier)
        return self._made[identifier]

    def contexts(self, triple=None):  # type: ignore[override]
        return [self.get_context(name) for name in self._makers]


def graph_of(identifier: URIRef, triples) -> Graph:
    g = Graph(identifier=identifier)
    for t in triples:
        g.add(t)
    return g


def select(query: Query, default: Graph, named: NamedGraphs) -> Iterator:
    """Run a prepared SELECT with `default` as the default graph and `named` for GRAPH.

    rdflib can only do this through a Dataset that holds every graph, which would
    mean copying the sheet for each application, so this drives the evaluator
    directly.
    """
    ctx = QueryContext(named, initBindings={})
    ctx.graph = default
    ctx.prologue = query.prologue
    return evalPart(ctx, query.algebra)["bindings"]


@lru_cache(maxsize=2048)
def prepared(text: str) -> Query:
    """Parse a SPARQL query once; rdflib otherwise re-parses the string on every call.

    Parsing was ~80% of autopilot time before this cache (see engine/benchmarks).
    """
    return prepareQuery(text)
