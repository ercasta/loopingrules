"""SHACL-driven suggestions for editing the sheet (design D15).

Given what the user has typed so far (subject, maybe predicate), derive from the
loaded shapes which predicates make sense for the subject and which objects make
sense for the (subject, predicate) pair.

Supported shape features: sh:targetClass, sh:targetNode, sh:property with an IRI
sh:path, sh:minCount, sh:maxCount, sh:class, sh:datatype, sh:in, sh:nodeKind,
sh:pattern, sh:name, sh:description.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import XSD

from .validation import SH


@dataclass
class PropertyRule:
    path: URIRef
    min_count: int = 0
    max_count: int | None = None
    cls: URIRef | None = None
    datatype: URIRef | None = None
    values: list = field(default_factory=list)  # sh:in
    node_kind: URIRef | None = None
    pattern: str | None = None
    name: str | None = None
    description: str | None = None

    def merge(self, other: "PropertyRule") -> None:
        """Combine two shapes constraining the same path (most restrictive wins)."""
        self.min_count = max(self.min_count, other.min_count)
        if other.max_count is not None:
            self.max_count = other.max_count if self.max_count is None else min(self.max_count, other.max_count)
        for attr in ("cls", "datatype", "node_kind", "pattern", "name", "description"):
            if getattr(self, attr) is None:
                setattr(self, attr, getattr(other, attr))
        self.values = self.values or other.values


def _int(g: Graph, s, p) -> int | None:
    v = g.value(s, p)
    return int(v) if v is not None else None


def _rule(shapes: Graph, ps) -> PropertyRule | None:
    path = shapes.value(ps, SH.path)
    if not isinstance(path, URIRef):
        return None  # complex paths are not suggested
    in_list = shapes.value(ps, SH["in"])
    text = lambda p: str(shapes.value(ps, p)) if shapes.value(ps, p) is not None else None  # noqa: E731
    return PropertyRule(
        path=path,
        min_count=_int(shapes, ps, SH.minCount) or 0,
        max_count=_int(shapes, ps, SH.maxCount),
        cls=shapes.value(ps, SH["class"]),
        datatype=shapes.value(ps, SH.datatype),
        values=list(Collection(shapes, in_list)) if in_list is not None else [],
        node_kind=shapes.value(ps, SH.nodeKind),
        pattern=text(SH.pattern),
        name=text(SH.name),
        description=text(SH.description),
    )


class Suggester:
    def __init__(self, shapes: Graph, sheet: Graph):
        self.shapes = shapes
        self.sheet = sheet

    # --- shape lookup ---------------------------------------------------
    def target_classes(self) -> list[URIRef]:
        return sorted({c for c in self.shapes.objects(None, SH.targetClass) if isinstance(c, URIRef)})

    def rules_for(self, subject) -> dict[URIRef, PropertyRule]:
        types = set(self.sheet.objects(subject, RDF.type))
        node_shapes = {ns for ns, c in self.shapes.subject_objects(SH.targetClass) if c in types}
        node_shapes |= set(self.shapes.subjects(SH.targetNode, subject))
        rules: dict[URIRef, PropertyRule] = {}
        for ns in node_shapes:
            for ps in self.shapes.objects(ns, SH.property):
                r = _rule(self.shapes, ps)
                if r is None:
                    continue
                if r.path in rules:
                    rules[r.path].merge(r)
                else:
                    rules[r.path] = r
        return rules

    # --- suggestions ----------------------------------------------------
    def predicates(self, subject) -> list[dict]:
        """Predicates for `subject`, most useful first: missing required, allowed, full."""
        out = []
        if not any(self.sheet.objects(subject, RDF.type)):
            out.append({"term": RDF.type, "status": "missing", "hint": "give it a type to get suggestions"})
        else:
            out.append({"term": RDF.type, "status": "ok", "hint": "type"})
        for path, r in self.rules_for(subject).items():
            count = len(list(self.sheet.objects(subject, path)))
            status = ("missing" if count < r.min_count
                      else "full" if r.max_count is not None and count >= r.max_count
                      else "ok")
            out.append({"term": path, "status": status, "count": count,
                        "min": r.min_count, "max": r.max_count,
                        "hint": r.description or r.name or _describe(r), "rule": r})
        order = {"missing": 0, "ok": 1, "full": 2}
        return sorted(out, key=lambda x: order[x["status"]])

    def missing(self, subject) -> list[dict]:
        return [p for p in self.predicates(subject) if p["status"] == "missing"]

    def objects(self, subject, predicate) -> dict:
        """Object suggestions for (subject, predicate), plus constraints for the input."""
        if predicate == RDF.type:
            return {"values": [{"term": c, "hint": "shape target"} for c in self.target_classes()],
                    "constraint": {"kind": "iri"}}
        rule = self.rules_for(subject).get(predicate) if subject is not None else None
        if rule is None:
            seen = sorted(set(self.sheet.objects(None, predicate)), key=lambda t: t.n3())
            return {"values": [{"term": t, "hint": "used before"} for t in seen[:50]], "constraint": {}}

        constraint: dict = {}
        values: list[dict] = []
        if rule.values:
            values = [{"term": v, "hint": "allowed value (sh:in)"} for v in rule.values]
            constraint["kind"] = "enum"
        elif rule.cls is not None:
            instances = sorted(set(self.sheet.subjects(RDF.type, rule.cls)), key=lambda t: t.n3())
            values = [{"term": i, "hint": f"instance of {self._short(rule.cls)}"} for i in instances]
            constraint["kind"] = "iri"
            constraint["class"] = self._short(rule.cls)
        elif rule.datatype is not None:
            constraint["kind"] = "literal"
            constraint["datatype"] = self._short(rule.datatype)
            if rule.datatype == XSD.boolean:
                values = [{"term": Literal(True), "hint": "xsd:boolean"}, {"term": Literal(False), "hint": "xsd:boolean"}]
        if rule.node_kind is not None:
            constraint["nodeKind"] = self._short(rule.node_kind)
        if rule.pattern:
            constraint["pattern"] = rule.pattern
        if rule.max_count is not None:
            count = len(list(self.sheet.objects(subject, predicate)))
            if count >= rule.max_count:
                constraint["full"] = f"already has {count} (max {rule.max_count})"
        return {"values": values, "constraint": constraint, "hint": rule.description or rule.name}

    def _short(self, t) -> str:
        return t.n3(self.sheet.namespace_manager)


def _describe(r: PropertyRule) -> str:
    parts = []
    if r.datatype is not None:
        parts.append(r.datatype.split("#")[-1])
    if r.cls is not None:
        parts.append("→ " + r.cls.split("#")[-1].split("/")[-1])
    if r.values:
        parts.append("one of " + ", ".join(str(v).split("#")[-1] for v in r.values))
    card = f"{r.min_count}..{'*' if r.max_count is None else r.max_count}"
    parts.append(card)
    return " · ".join(parts)

