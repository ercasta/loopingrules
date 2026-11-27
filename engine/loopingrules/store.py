"""Graph helpers. v0 uses rdflib Graphs directly; this module is the seam for swapping stores later."""

from __future__ import annotations

from rdflib import Graph

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
