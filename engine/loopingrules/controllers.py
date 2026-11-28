"""Controllers: SPARQL SELECT queries that score a (resulting) state."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, RDFS, Graph, URIRef

from .security import check_query
from .store import prepared, prologue
from .vocab import LR


@dataclass
class Controller:
    iri: URIRef
    name: str
    query: str
    active: bool = True
    layer: str | None = None  # the controller pack it comes from, None for the project's own
    weight: float = 1.0  # lr:weight; an application's total is the sum of weight * score (D23)

    def score(self, state: Graph, prefixes: str) -> float:
        rows = list(state.query(prepared(prefixes + self.query)))
        if not rows:
            return 0.0
        value = rows[0].asdict().get("score")
        if value is None:
            return 0.0
        try:
            return float(value.toPython())
        except (TypeError, ValueError) as e:
            raise ValueError(f"Controller {self.name}: ?score is not numeric: {value!r}") from e


def _weight(value, name: str) -> float:
    if value is None:
        return 1.0
    try:
        w = float(value.toPython())
    except (TypeError, ValueError, AttributeError):
        w = float("nan")
    if w != w or w in (float("inf"), float("-inf")):
        raise ValueError(f"Controller {name}: lr:weight must be a finite number, got {value!r}")
    return w


def load_controllers(g: Graph, layer: str | None = None) -> list[Controller]:
    out = []
    for iri in g.subjects(RDF.type, LR.Controller):
        q = g.value(iri, LR.query)
        if q is None:
            raise ValueError(f"Controller {iri} has no lr:query")
        label = g.value(iri, RDFS.label)
        active = g.value(iri, LR.active)
        name = str(label) if label else g.namespace_manager.normalizeUri(iri)
        check_query(prologue(g) + str(q), f"controller {name}")
        out.append(Controller(
            iri=iri,
            name=name,
            query=str(q),
            active=True if active is None else bool(active.toPython()),
            layer=layer,
            weight=_weight(g.value(iri, LR.weight), name),
        ))
    return sorted(out, key=lambda c: str(c.iri))
