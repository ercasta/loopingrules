"""Operations (precondition -> delta) and their applications."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from rdflib import RDF, RDFS, BNode, Graph, URIRef, Variable
from rdflib.term import Node

from .security import check_query
from .store import Triple, prologue
from .vocab import LR


@dataclass(frozen=True)
class Operation:
    iri: URIRef
    name: str
    where: str
    delete: str = ""
    insert: str = ""


@dataclass
class Application:
    id: str
    operation: Operation
    bindings: dict[str, Node]
    deletes: set[Triple]
    inserts: set[Triple]
    # Filled in by the engine:
    valid: bool = True
    violations: list[dict] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.scores.values())


def load_operations(model: Graph) -> list[Operation]:
    prefixes = prologue(model)
    ops = []
    for iri in model.subjects(RDF.type, LR.Operation):
        where = model.value(iri, LR.where)
        if where is None:
            raise ValueError(f"Operation {iri} has no lr:where")
        label = model.value(iri, RDFS.label)
        op = Operation(
            iri=iri,
            name=str(label) if label else model.namespace_manager.normalizeUri(iri),
            where=str(where),
            delete=str(model.value(iri, LR.delete) or ""),
            insert=str(model.value(iri, LR.insert) or ""),
        )
        check_query(f"{prefixes}SELECT * WHERE {{ {op.where} }}", f"operation {op.name}")
        for part in (op.delete, op.insert):
            if part.strip():
                check_query(f"{prefixes}CONSTRUCT {{ {part} }} WHERE {{}}", f"operation {op.name}")
        ops.append(op)
    return sorted(ops, key=lambda o: str(o.iri))


def _instantiate(template: str, bindings: dict, prefixes: str, sheet: Graph) -> set[Triple]:
    if not template.strip():
        return set()
    q = f"{prefixes}CONSTRUCT {{ {template} }} WHERE {{}}"
    return set(sheet.query(q, initBindings=bindings))


def _app_id(op: Operation, bindings: dict) -> str:
    key = str(op.iri) + "|" + "|".join(f"{k}={v.n3()}" for k, v in sorted(bindings.items()))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def enumerate_applications(sheet: Graph, ops: list[Operation], model: Graph) -> list[Application]:
    """Every binding of every operation's WHERE, with its effective delta.

    Applications whose effective delta is empty (nothing to delete that exists,
    nothing to insert that is missing) are dropped.
    """
    prefixes = prologue(model, sheet)
    apps: list[Application] = []
    for op in ops:
        rows = sheet.query(f"{prefixes}SELECT * WHERE {{ {op.where} }}")
        for row in rows:
            bindings = {str(k): v for k, v in row.asdict().items() if v is not None}
            init = {Variable(k): v for k, v in bindings.items()}
            deletes = {t for t in _instantiate(op.delete, init, prefixes, sheet) if t in sheet}
            if any(isinstance(term, BNode) and term not in bindings.values() for t in deletes for term in t):
                raise ValueError(f"{op.name}: DELETE templates may not introduce blank nodes")
            inserts = {t for t in _instantiate(op.insert, init, prefixes, sheet) if t not in sheet}
            if not deletes and not inserts:
                continue
            apps.append(Application(_app_id(op, bindings), op, bindings, deletes, inserts))
    return apps
