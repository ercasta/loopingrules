"""Operations (precondition -> delta) and their applications."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import lru_cache

from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef, Variable
from rdflib.term import Node

from .patterns import check_pattern
from .project import mint
from .security import check_query
from .store import Triple, prepared, prologue
from .vocab import LR


@dataclass(frozen=True)
class Operation:
    iri: URIRef
    name: str
    where: str
    delete: str = ""
    insert: str = ""

    @property
    def noop(self) -> bool:
        """An operation with no effects (D21): when one of its applications wins, autopilot stops."""
        return not self.delete.strip() and not self.insert.strip()


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

    @property
    def noop(self) -> bool:
        return self.operation.noop


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
        check_pattern(op.where, prefixes, f"operation {op.name}")
        for part in (op.delete, op.insert):
            if part.strip():
                check_query(f"{prefixes}CONSTRUCT {{ {part} }} WHERE {{}}", f"operation {op.name}")
        ops.append(op)
    return sorted(ops, key=lambda o: str(o.iri))


@lru_cache(maxsize=1024)
def _template(text: str, prefixes: str) -> tuple:
    """The triple patterns of a DELETE/INSERT template, parsed once."""
    if not text.strip():
        return ()
    return tuple(prepared(f"{prefixes}CONSTRUCT {{ {text} }} WHERE {{}}").algebra.template)


def _instantiate(template: str, bindings: dict[str, Node], prefixes: str) -> set[Triple]:
    """Fill a template with one solution, with CONSTRUCT semantics, without running a query.

    A triple with an unbound variable, or that would not be valid RDF (literal
    subject, non-IRI predicate), is skipped.
    """
    out: set[Triple] = set()
    for pattern in _template(template, prefixes):
        terms = []
        for x in pattern:
            if isinstance(x, Variable):
                x = bindings.get(str(x))
                if x is None:
                    break
            terms.append(x)
        else:
            s, p, o = terms
            if isinstance(s, Literal) or not isinstance(p, URIRef):
                continue
            out.add((s, p, o))
    return out


def _mint_fresh(triples: set[Triple], bindings: dict) -> set[Triple]:
    """Fresh blank nodes from INSERT templates become minted IRIs (stable across reloads)."""
    bound = set(bindings.values())
    names: dict[BNode, object] = {}
    sub = lambda x: names.setdefault(x, mint()) if isinstance(x, BNode) and x not in bound else x  # noqa: E731
    return {tuple(sub(x) for x in t) for t in triples}


def _app_id(op: Operation, bindings: dict) -> str:
    key = str(op.iri) + "|" + "|".join(f"{k}={v.n3()}" for k, v in sorted(bindings.items()))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _solutions(sheet: Graph, where: str, prefixes: str) -> list[dict[str, Node]]:
    """The solutions of a WHERE pattern, as {variable name: value}.

    rdflib drops solutions that bind nothing, so a pattern without (bound)
    variables would never apply, although SPARQL gives it one empty solution
    when it matches. A marker BIND makes every solution non-empty.
    """
    query = prepared(f"{prefixes}SELECT * WHERE {{ {where}\n BIND(true AS ?{_MARKER}) }}")
    return [{str(k): v for k, v in row.asdict().items() if v is not None and str(k) != _MARKER}
            for row in sheet.query(query)]


_MARKER = "lr__row"


def enumerate_applications(sheet: Graph, ops: list[Operation], model: Graph) -> list[Application]:
    """Every binding of every operation's WHERE, with its effective delta.

    Applications whose effective delta is empty (nothing to delete that exists,
    nothing to insert that is missing) are dropped, except those of no-op
    operations, which are empty by design (D21).
    """
    prefixes = prologue(model, sheet)
    apps: list[Application] = []
    for op in ops:
        for bindings in _solutions(sheet, op.where, prefixes):
            deletes = _instantiate(op.delete, bindings, prefixes)
            if any(isinstance(term, BNode) and term not in bindings.values() for t in deletes for term in t):
                raise ValueError(f"{op.name}: DELETE templates may not introduce blank nodes")
            deletes = {t for t in deletes if t in sheet}
            inserts = _mint_fresh(_instantiate(op.insert, bindings, prefixes), bindings)
            inserts = {t for t in inserts if t not in sheet}
            if not deletes and not inserts and not op.noop:
                continue
            apps.append(Application(_app_id(op, bindings), op, bindings, deletes, inserts))
    return apps
