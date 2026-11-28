"""Graph helpers. v0 uses rdflib Graphs directly; this module is the seam for swapping stores later."""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Iterator

from rdflib import Dataset, Graph, URIRef
from rdflib.paths import Path
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


class Overlay(Graph):
    """`base` with some triples deleted and others added, without copying `base`.

    `base` must not change while the overlay is in use. Adding to or removing
    from the overlay only changes its own two sets, which always hold the net
    change: `deleted` ⊆ base, `added` ∩ base = ∅.
    """

    def __init__(self, base: Graph, deletes=(), inserts=()):
        super().__init__()
        self.namespace_manager = base.namespace_manager  # same prefixes in messages as the base
        self.base = base
        self.deleted: set[Triple] = set()
        self.added: set[Triple] = set()
        for t in deletes:
            self.remove(t)
        for t in inserts:
            self.add(t)

    def triples(self, pattern):  # type: ignore[override]
        s, p, o = pattern
        if isinstance(p, Path):
            for _s, _o in p.eval(self, s, o):
                yield _s, p, _o
            return
        deleted = self.deleted
        for t in self.base.triples(pattern):
            if t not in deleted:
                yield t
        for t in self.added:
            if (s is None or s == t[0]) and (p is None or p == t[1]) and (o is None or o == t[2]):
                yield t

    def __contains__(self, triple) -> bool:
        if None in triple:
            return any(True for _ in self.triples(triple))
        return triple in self.added or (triple not in self.deleted and triple in self.base)

    def __len__(self) -> int:
        return len(self.base) - len(self.deleted) + len(self.added)

    def add(self, triple):  # type: ignore[override]
        if triple in self.deleted:
            self.deleted.discard(triple)
        elif triple not in self.base:
            self.added.add(triple)
        return self

    def remove(self, triple):  # type: ignore[override]
        if None in triple:
            raise ValueError("Overlay.remove takes a concrete triple, not a pattern")
        if triple in self.added:
            self.added.discard(triple)
        elif triple in self.base:
            self.deleted.add(triple)
        return self


class Union(Graph):
    """A read-only view of `first` plus `second`, without copying either (D28: sheet + knowledge).

    Matching, scoring and validation read through it; writes go to `first` directly.
    """

    def __init__(self, first: Graph, second: Graph):
        super().__init__()
        self.namespace_manager = first.namespace_manager
        self.first, self.second = first, second

    def triples(self, pattern):  # type: ignore[override]
        s, p, o = pattern
        if isinstance(p, Path):
            for _s, _o in p.eval(self, s, o):
                yield _s, p, _o
            return
        yield from self.first.triples(pattern)
        first = self.first
        for t in self.second.triples(pattern):
            if t not in first:
                yield t

    def __contains__(self, triple) -> bool:
        if None in triple:
            return any(True for _ in self.triples(triple))
        return triple in self.first or triple in self.second

    def __len__(self) -> int:
        return len(self.first) + sum(1 for t in self.second if t not in self.first)

    def add(self, triple):  # type: ignore[override]
        raise TypeError("the combined view is read-only: write to the sheet")

    def remove(self, triple):  # type: ignore[override]
        raise TypeError("the combined view is read-only: write to the sheet")


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
