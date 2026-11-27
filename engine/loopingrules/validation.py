"""SHACL validation via pySHACL."""

from __future__ import annotations

from pyshacl import validate as _validate
from rdflib import RDF, Graph, Namespace

SH = Namespace("http://www.w3.org/ns/shacl#")


def validate(data: Graph, shapes: Graph) -> list[dict]:
    """Return the list of violations (empty if the graph conforms)."""
    _conforms, results, _text = _validate(data, shacl_graph=shapes, inference="none", advanced=True)
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
