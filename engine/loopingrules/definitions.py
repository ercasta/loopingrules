"""Everything is SPO (design D28): sort a project's or a pack's triples by convention.

Definitions are recognised by their type: the manifest (lr:Package), operations
(lr:Operation), shapes (sh:NodeShape, sh:PropertyShape, or a subject with a SHACL
target or sh:property / sh:path) and controllers (lr:Controller). A definition
includes the blank nodes reachable from it (sh:property [ … ], lr:steps ( … ), …).
Every other triple is knowledge: read-only facts beside the sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import RDF, BNode, Graph, Namespace, URIRef

from .vocab import LR

SH = Namespace("http://www.w3.org/ns/shacl#")

DEFINITION_TYPES = {LR.Package, LR.Operation, LR.Controller, SH.NodeShape, SH.PropertyShape}
SHAPE_PROPERTIES = {SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf, SH.property, SH.path}


def _copy_prefixes(src: Graph, dst: Graph) -> Graph:
    for prefix, ns in src.namespaces():
        dst.bind(prefix, ns, override=True)
    return dst


def roots(g: Graph) -> set:
    """The subjects that are definitions."""
    out = {s for s, o in g.subject_objects(RDF.type) if o in DEFINITION_TYPES}
    out |= {s for p in SHAPE_PROPERTIES for s in g.subjects(p, None)}
    return out


def split(g: Graph, source: str = "") -> tuple[Graph, Graph]:
    """(definitions, knowledge). Raises ValueError if the knowledge has blank nodes."""
    inside = set(roots(g))
    todo = list(inside)
    while todo:  # follow blank nodes: they belong to the definition that points at them
        node = todo.pop()
        for o in g.objects(node, None):
            if isinstance(o, BNode) and o not in inside:
                inside.add(o)
                todo.append(o)
    defs, know = _copy_prefixes(g, Graph()), _copy_prefixes(g, Graph())
    for t in g:
        (defs if t[0] in inside else know).add(t)
    bad = next((t for t in know if any(isinstance(x, BNode) for x in t)), None)
    if bad is not None:
        raise ValueError(f"{source or 'knowledge'}: knowledge may not use blank nodes; give them IRIs "
                         f"(it isn't journaled, so its names must be the same on every load): "
                         f"{' '.join(x.n3(g.namespace_manager) for x in bad)}")
    return defs, know


@dataclass
class Source:
    """One project or pack: its definitions and its knowledge."""
    name: str  # "project", or the pack's title
    layer: str | None  # None for the project's own files
    definitions: Graph
    knowledge: Graph
    defined: set = field(default_factory=set)  # IRIs of the definitions (for conflicts)


def source(name: str, layer: str | None, g: Graph) -> Source:
    defs, know = split(g, name)
    defined = {s for s in roots(g) if isinstance(s, URIRef) and (s, RDF.type, LR.Package) not in g}
    return Source(name, layer, defs, know, defined)


def conflicts(sources: list[Source]) -> list[str]:
    """Definitions or prefixes that two sources disagree on (both are refused)."""
    problems = []
    owner: dict = {}
    for src in sources:
        for iri in src.defined:
            if iri in owner and owner[iri] != src.name:
                problems.append(f"{iri.n3()} is defined both in {owner[iri]} and in {src.name}")
            owner.setdefault(iri, src.name)
    defaults = {(p, str(ns)) for p, ns in Graph().namespaces()}  # rdflib's own bindings
    bound: dict[str, tuple[str, str]] = {}
    for src in sources:
        for g in (src.definitions, src.knowledge):
            for prefix, ns in g.namespaces():
                if not prefix or (prefix, str(ns)) in defaults:
                    continue
                seen = bound.setdefault(prefix, (str(ns), src.name))
                if seen[0] != str(ns) and seen[1] != src.name:
                    problems.append(f"prefix {prefix}: means <{seen[0]}> in {seen[1]} "
                                    f"but <{ns}> in {src.name}")
    return sorted(set(problems))
