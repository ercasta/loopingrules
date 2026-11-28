"""SHACL validation via pySHACL, in full or only where a change can matter."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyshacl import validate as _validate
from rdflib import RDF, RDFS, BNode, Graph, Literal, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")


def validate(data: Graph, shapes: Graph, focus: list | None = None) -> list[dict]:
    """Return the list of violations (empty if the graph conforms).

    With `focus`, only those nodes are validated, against the shapes that target them.
    """
    if focus is not None and not focus:
        return []  # pySHACL reads an empty list as "every node"
    _conforms, results, _text = _validate(data, shacl_graph=shapes, inference="none", advanced=True,
                                         inplace=True,  # read-only: no inference, so no copy needed
                                         focus_nodes=focus)
    out = []
    for r in results.subjects(RDF.type, SH.ValidationResult):
        def v(p):
            x = results.value(r, p)
            return x.n3(data.namespace_manager) if x is not None else None
        out.append({
            "focus": v(SH.focusNode),
            "path": v(SH.resultPath),
            "value": v(SH.value),
            "component": v(SH.sourceConstraintComponent),
            "severity": v(SH.resultSeverity),
            "message": str(results.value(r, SH.resultMessage) or ""),
        })
    return out


def violation_key(v: dict) -> tuple:
    return (v["focus"], v["path"], v["value"], v["component"])


# --- incremental validation ---------------------------------------------------------
# A change can only alter the results of the nodes it touches. For a "local" shape, one
# whose paths are a predicate or its inverse, and whose constraints look only at the
# focus node's own values, those are:
#   - the subjects and objects of the changed triples (targets, values, inverse values);
#   - for sh:class, the nodes whose value is a changed node (its rdf:type may have
#     changed): one step back along a path that has a class constraint.
# Every other shape (complex paths, sh:node, logical or SPARQL constraints, rules) is
# validated in full, on its own.

# Predicates a local shape may use (constraints on the focus node and its direct values,
# targets, and annotations).
_LOCAL = {RDF.type, RDF.first, RDF.rest, RDFS.label, RDFS.comment} | {SH[n] for n in (
    "property path inversePath targetClass targetNode targetSubjectsOf targetObjectsOf "
    "minCount maxCount datatype class in pattern flags nodeKind minLength maxLength "
    "minInclusive maxInclusive minExclusive maxExclusive hasValue languageIn uniqueLang "
    "closed ignoredProperties equals disjoint lessThan lessThanOrEquals "
    "name description message severity order group defaultValue deactivated").split()}
_ROOT_TYPES = {SH.NodeShape, SH.PropertyShape}
_ROOT_PROPS = {SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf, SH.property, SH.path}


@dataclass
class ShapeSplit:
    """The model's shapes, split for incremental validation (see validate_change)."""
    local: Graph
    other: Graph
    class_paths: set = field(default_factory=set)      # predicates p of [ sh:path p ; sh:class … ]
    class_inverse: set = field(default_factory=set)    # predicates p of [ sh:path [ sh:inversePath p ] ; sh:class … ]


def _closure(g: Graph, root, shapes: set) -> set:
    """The root's triples, and those of what it reaches: blank nodes (property shapes,
    lists) and other shapes it names (sh:property <iri>, sh:node <iri>, …)."""
    out, todo, seen = set(), [root], {root}
    while todo:
        node = todo.pop()
        for t in g.triples((node, None, None)):
            out.add(t)
            o = t[2]
            if (isinstance(o, BNode) or o in shapes) and o not in seen:
                seen.add(o)
                todo.append(o)
    return out


def split_shapes(shapes: Graph) -> ShapeSplit:
    roots = {s for s, o in shapes.subject_objects(RDF.type) if o in _ROOT_TYPES}
    roots |= {s for p in _ROOT_PROPS for s in shapes.subjects(p, None)}
    nested = {o for s in roots for o in shapes.objects(s, SH.property)}
    split = ShapeSplit(Graph(), Graph())
    for g in (split.local, split.other):
        for prefix, ns in shapes.namespaces():
            g.bind(prefix, ns)
    for root in roots - nested:
        triples = _closure(shapes, root, roots)
        local = all(p in _LOCAL for _, p, _ in triples)
        paths = [(s, o) for s, p, o in triples if p == SH.path]
        for s, path in paths:
            if isinstance(path, BNode):  # only [ sh:inversePath <p> ] is local
                inner = list(shapes.predicate_objects(path))
                if not (len(inner) == 1 and inner[0][0] == SH.inversePath and isinstance(inner[0][1], URIRef)):
                    local = False
        target = split.local if local else split.other
        for t in triples:
            target.add(t)
        if local:
            for s, path in paths:
                if (s, SH["class"], None) in shapes:
                    if isinstance(path, URIRef):
                        split.class_paths.add(path)
                    else:
                        split.class_inverse.add(shapes.value(path, SH.inversePath))
    return split


def affected_nodes(state: Graph, changed: set, split: ShapeSplit) -> list | None:
    """The nodes whose results a change can alter, for the local shapes; None: validate in full."""
    nodes: set = set()
    subjects = set()
    for s, p, o in changed:
        if p == RDFS.subClassOf:
            return None  # class targets and sh:class follow subclasses in the data
        nodes.add(s)
        subjects.add(s)
        if not isinstance(o, Literal):
            nodes.add(o)
    if split.class_paths or split.class_inverse:
        # Links to a changed node: in the base (indexed lookups), and among the added
        # triples (one scan). Asking an Overlay for (?, p, n) scans its added triples on
        # every call. Removed links need nothing: their subjects are changed nodes already.
        base = getattr(state, "base", state)
        added = getattr(state, "added", ())
        for n in subjects:
            for p in split.class_paths:
                nodes.update(base.subjects(p, n))
            for p in split.class_inverse:
                nodes.update(base.objects(n, p))
        for s, p, o in added:
            if p in split.class_paths and o in subjects:
                nodes.add(s)
            if p in split.class_inverse and s in subjects:
                nodes.add(o)
    if any(isinstance(n, BNode) for n in nodes):
        return None  # pySHACL only focuses on IRIs
    return sorted(nodes)


def validate_change(state: Graph, changed: set, shapes: Graph, split: ShapeSplit) -> list[dict]:
    """The violations of `state` that a change (`changed`: its deleted and inserted triples)
    could have caused: the local shapes at the affected nodes, the others in full. Every
    violation the change adds is among them; violations elsewhere were there before."""
    nodes = affected_nodes(state, changed, split)
    if nodes is None:
        return validate(state, shapes)
    found = validate(state, split.local, focus=nodes) if len(split.local) else []
    if len(split.other):
        found += validate(state, split.other)
    unique = {violation_key(v): v for v in found}  # a shape both groups reach reports twice
    return list(unique.values())
