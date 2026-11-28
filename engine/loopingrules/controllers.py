"""Controllers: SPARQL SELECT queries that score an application (design D20).

A controller query runs against one application:
- the default graph is the resulting state;
- GRAPH lr:before is the current sheet (not copied);
- GRAPH lr:inserted / GRAPH lr:deleted hold the effective delta;
- GRAPH lr:action describes the action:
      lr:this lr:operation <op> ; lr:binds [ lr:var "name" ; lr:value <node> ] .
Named graphs are built only if a query reaches them.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef, Variable

from .operations import Application
from .security import check_query
from .store import NamedGraphs, NamedView, graph_of, prepared, prologue, select
from .vocab import LR

_SCORE = Variable("score")


def scoring_view(sheet: Graph, app: Application) -> NamedGraphs:
    """The named graphs every controller sees for one application."""
    def action() -> Graph:
        g = Graph(identifier=LR.action)
        g.add((LR.this, LR.operation, app.operation.iri))
        for name, value in sorted(app.bindings.items()):
            b = BNode()
            g.add((LR.this, LR.binds, b))
            g.add((b, LR.var, Literal(name)))
            g.add((b, LR.value, value))
        return g

    return NamedGraphs({
        LR.before: lambda: NamedView(sheet, LR.before),
        LR.inserted: lambda: graph_of(LR.inserted, app.inserts),
        LR.deleted: lambda: graph_of(LR.deleted, app.deletes),
        LR.action: action,
    })


@dataclass
class Controller:
    iri: URIRef
    name: str
    query: str
    active: bool = True
    layer: str | None = None  # the controller pack it comes from, None for the project's own
    weight: float = 1.0  # lr:weight; an application's total is the sum of weight * score (D23)

    def score(self, state: Graph, view: NamedGraphs, prefixes: str) -> float:
        """The ?score of the first row, or 0 when there is no row or no ?score."""
        row = next(iter(select(prepared(prefixes + self.query), state, view)), None)
        value = row.get(_SCORE) if row is not None else None
        if value is None:
            return 0.0
        try:
            return float(value.toPython())
        except (TypeError, ValueError, AttributeError) as e:
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
        if prepared(prologue(g) + str(q)).algebra.name != "SelectQuery":
            raise ValueError(f"Controller {name}: lr:query must be a SELECT returning ?score")
        out.append(Controller(
            iri=iri,
            name=name,
            query=str(q),
            active=True if active is None else bool(active.toPython()),
            layer=layer,
            weight=_weight(g.value(iri, LR.weight), name),
        ))
    return sorted(out, key=lambda c: str(c.iri))
