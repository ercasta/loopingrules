"""Controllers: SPARQL SELECT queries that score a (resulting) state."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, RDFS, Graph, URIRef

from .store import prologue
from .vocab import LR


@dataclass
class Controller:
    iri: URIRef
    name: str
    query: str
    active: bool = True

    def score(self, state: Graph, prefixes: str) -> float:
        rows = list(state.query(prefixes + self.query))
        if not rows:
            return 0.0
        value = rows[0].asdict().get("score")
        if value is None:
            return 0.0
        try:
            return float(value.toPython())
        except (TypeError, ValueError) as e:
            raise ValueError(f"Controller {self.name}: ?score is not numeric: {value!r}") from e


def load_controllers(g: Graph) -> list[Controller]:
    out = []
    for iri in g.subjects(RDF.type, LR.Controller):
        q = g.value(iri, LR.query)
        if q is None:
            raise ValueError(f"Controller {iri} has no lr:query")
        label = g.value(iri, RDFS.label)
        active = g.value(iri, LR.active)
        out.append(Controller(
            iri=iri,
            name=str(label) if label else g.namespace_manager.normalizeUri(iri),
            query=str(q),
            active=True if active is None else bool(active.toPython()),
        ))
    return sorted(out, key=lambda c: str(c.iri))
