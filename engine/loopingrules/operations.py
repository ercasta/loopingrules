"""Operations (precondition -> delta) and their applications (designs D3, D21, D22).

An operation:
    lr:where     the pattern whose solutions are the candidate actions (D23 subset)
    lr:params    the variables that identify an action; default: every variable
    lr:requires  named guards (ASK patterns), checked per action with the parameters bound
    lr:delete / lr:insert
                 templates instantiated with every solution of the action, unioned
    lr:steps     further steps, in order, each [ lr:where ; lr:delete ; lr:insert ],
                 each seeing the state the previous ones left; only the parameters
                 carry over from one step to the next
    lr:ensures   named postconditions (ASK patterns) on the resulting state
An operation with no effects is a no-op: when it wins, autopilot stops (D21).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from functools import lru_cache

from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef, Variable
from rdflib.collection import Collection
from rdflib.term import Node

from .patterns import check_pattern
from .project import mint
from .security import check_query
from .store import Triple, apply_delta, copy_graph, prepared, prologue
from .vocab import LR


@dataclass(frozen=True)
class Condition:
    """A named ASK pattern: a guard (lr:requires) or a postcondition (lr:ensures)."""
    label: str
    ask: str


@dataclass(frozen=True)
class Step:
    where: str = ""  # empty: the step runs once, with the parameters only
    delete: str = ""
    insert: str = ""


@dataclass(frozen=True)
class Operation:
    iri: URIRef
    name: str
    where: str
    delete: str = ""
    insert: str = ""
    params: tuple[str, ...] | None = None  # None: every variable of a solution is a parameter
    requires: tuple[Condition, ...] = ()
    ensures: tuple[Condition, ...] = ()
    steps: tuple[Step, ...] = ()

    @property
    def noop(self) -> bool:
        """An operation with no effects (D21): when one of its applications wins, autopilot stops."""
        return not self.delete.strip() and not self.insert.strip() and not self.steps


@dataclass
class Application:
    id: str
    operation: Operation
    bindings: dict[str, Node]  # the parameters
    deletes: set[Triple]
    inserts: set[Triple]
    # Filled in by the engine (or here, for an application a guard blocks):
    valid: bool = True
    violations: list[dict] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.scores.values())

    @property
    def noop(self) -> bool:
        return self.operation.noop


# --- loading ------------------------------------------------------------------

def load_operations(model: Graph) -> list[Operation]:
    prefixes = prologue(model)
    ops = []
    for iri in model.subjects(RDF.type, LR.Operation):
        where = model.value(iri, LR.where)
        if where is None:
            raise ValueError(f"Operation {iri} has no lr:where")
        label = model.value(iri, RDFS.label)
        name = str(label) if label else model.namespace_manager.normalizeUri(iri)
        what = f"operation {name}"
        op = Operation(
            iri=iri,
            name=name,
            where=str(where),
            delete=str(model.value(iri, LR.delete) or ""),
            insert=str(model.value(iri, LR.insert) or ""),
            params=_params(model, iri),
            requires=_conditions(model, iri, LR.requires),
            ensures=_conditions(model, iri, LR.ensures),
            steps=_steps(model, iri, what),
        )
        _check_pattern(op.where, prefixes, what)
        if op.params is not None:
            visible = {str(v) for v in prepared(f"{prefixes}SELECT * WHERE {{ {op.where} }}").algebra.PV}
            missing = [p for p in op.params if p not in visible]
            if missing:
                raise ValueError(f"{what}: lr:params {', '.join('?' + p for p in missing)} "
                                 "not bound by lr:where")
        for c in op.requires + op.ensures:
            _check_pattern(c.ask, prefixes, f"{what}, condition {c.label!r}")
        for step in (Step("", op.delete, op.insert),) + op.steps:
            if step.where.strip():
                _check_pattern(step.where, prefixes, f"{what}, step")
            for part, is_delete in ((step.delete, True), (step.insert, False)):
                if part.strip():
                    check_query(f"{prefixes}CONSTRUCT {{ {part} }} WHERE {{}}", what)
                    if is_delete and any(isinstance(x, BNode) for t in _template(part, prefixes) for x in t):
                        raise ValueError(f"{what}: DELETE templates may not introduce blank nodes")
        ops.append(op)
    return sorted(ops, key=lambda o: str(o.iri))


def _check_pattern(pattern: str, prefixes: str, what: str) -> None:
    check_query(f"{prefixes}SELECT * WHERE {{ {pattern} }}", what)
    check_pattern(pattern, prefixes, what)


def _params(model: Graph, iri: URIRef) -> tuple[str, ...] | None:
    """lr:params "a b" or "?a, ?b", possibly repeated."""
    values = list(model.objects(iri, LR.params))
    if not values:
        return None
    names: list[str] = []
    for v in values:
        for n in re.split(r"[\s,]+", str(v).strip()):
            n = n.lstrip("?")
            if n and n not in names:
                names.append(n)
    return tuple(names)


def _conditions(model: Graph, iri: URIRef, prop: URIRef) -> tuple[Condition, ...]:
    """[ rdfs:label "…" ; lr:ask "…" ], or just the pattern as a string (labelled by itself)."""
    out = []
    for node in model.objects(iri, prop):
        if isinstance(node, Literal):
            out.append(Condition(" ".join(str(node).split()), str(node)))
            continue
        ask = model.value(node, LR.ask)
        if ask is None:
            raise ValueError(f"{model.namespace_manager.normalizeUri(iri)}: a condition has no lr:ask")
        label = model.value(node, RDFS.label)
        out.append(Condition(str(label) if label else " ".join(str(ask).split()), str(ask)))
    return tuple(sorted(out, key=lambda c: c.label))


def _steps(model: Graph, iri: URIRef, what: str) -> tuple[Step, ...]:
    head = model.value(iri, LR.steps)
    if head is None:
        return ()
    steps = []
    for node in Collection(model, head):
        step = Step(str(model.value(node, LR.where) or ""), str(model.value(node, LR.delete) or ""),
                    str(model.value(node, LR.insert) or ""))
        if not step.delete.strip() and not step.insert.strip():
            raise ValueError(f"{what}: every step needs an lr:delete or an lr:insert")
        steps.append(step)
    return tuple(steps)


# --- templates --------------------------------------------------------------

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


# --- matching ---------------------------------------------------------------

_MARKER = "lr__row"


def _solutions(graph: Graph, where: str, prefixes: str, bound: dict | None = None) -> list[dict[str, Node]]:
    """The solutions of a WHERE pattern, as {variable name: value}.

    rdflib drops solutions that bind nothing, so a pattern without (bound)
    variables would never apply, although SPARQL gives it one empty solution
    when it matches. A marker BIND makes every solution non-empty.
    """
    query = prepared(f"{prefixes}SELECT * WHERE {{ {where}\n BIND(true AS ?{_MARKER}) }}")
    rows = graph.query(query, initBindings=bound) if bound else graph.query(query)
    return [{str(k): v for k, v in row.asdict().items() if v is not None and str(k) != _MARKER}
            for row in rows]


def holds(graph: Graph, condition: Condition, bindings: dict[str, Node], prefixes: str) -> bool:
    query = prepared(f"{prefixes}ASK {{ {condition.ask} }}")
    return bool(graph.query(query, initBindings=bindings).askAnswer)


def condition_violation(kind: str, condition: Condition) -> dict:
    """A failed guard or postcondition, shaped like a SHACL violation."""
    return {"focus": None, "path": None, "value": None, "component": kind, "severity": None,
            "message": condition.label}


def _app_id(op: Operation, bindings: dict) -> str:
    key = str(op.iri) + "|" + "|".join(f"{k}={v.n3()}" for k, v in sorted(bindings.items()))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


class _Delta:
    """The net change to `base` made by a sequence of deletes and inserts."""

    def __init__(self, base: Graph):
        self.base = base
        self.deleted: set[Triple] = set()
        self.added: set[Triple] = set()

    def apply(self, deletes: set[Triple], inserts: set[Triple]) -> None:
        """SPARQL Update order: every delete, then every insert."""
        for t in deletes:
            if t in self.added:
                self.added.discard(t)
            elif t in self.base:
                self.deleted.add(t)
        for t in inserts:
            if t in self.deleted:
                self.deleted.discard(t)
            elif t not in self.base:
                self.added.add(t)


def _step_delta(delete: str, insert: str, rows: list[dict], prefixes: str) -> tuple[set, set]:
    """One step's templates instantiated with every row, unioned."""
    deletes: set[Triple] = set()
    inserts: set[Triple] = set()
    for row in rows:
        deletes |= _instantiate(delete, row, prefixes)
        inserts |= _mint_fresh(_instantiate(insert, row, prefixes), row)
    return deletes, inserts


def _effects(sheet: Graph, op: Operation, rows: list[dict], params: dict, prefixes: str) -> _Delta:
    delta = _Delta(sheet)
    delta.apply(*_step_delta(op.delete, op.insert, rows, prefixes))
    if not op.steps:
        return delta
    # Later steps query the state the earlier ones left. A working copy for now;
    # an overlay would avoid copying the sheet (handoff, performance step 2).
    state = copy_graph(sheet)
    apply_delta(state, delta.deleted, delta.added)
    for step in op.steps:
        step_rows = _solutions(state, step.where, prefixes, params) if step.where.strip() else [dict(params)]
        deletes, inserts = _step_delta(step.delete, step.insert, step_rows, prefixes)
        deletes = {t for t in deletes if t in state}
        inserts = {t for t in inserts if t not in state}
        apply_delta(state, deletes, inserts)
        delta.apply(deletes, inserts)
    return delta


def enumerate_applications(sheet: Graph, ops: list[Operation], model: Graph) -> list[Application]:
    """One application per parameter tuple of every operation, with its effective delta.

    - Solutions that share a parameter tuple are merged, and their instantiated
      effects are unioned (SPARQL Update semantics with the parameters bound).
    - An application whose guard (lr:requires) fails is returned invalid, without a delta.
    - Applications whose effective delta is empty are dropped, except those of
      no-op operations, which are empty by design (D21).
    """
    prefixes = prologue(model, sheet)
    apps: list[Application] = []
    for op in ops:
        groups: dict[tuple, tuple[dict, list[dict]]] = {}
        for row in _solutions(sheet, op.where, prefixes):
            params = row if op.params is None else {p: row[p] for p in op.params if p in row}
            groups.setdefault(tuple(sorted(params.items())), (params, []))[1].append(row)
        for params, rows in groups.values():
            app_id = _app_id(op, params)
            failed = [c for c in op.requires if not holds(sheet, c, params, prefixes)]
            if failed:
                apps.append(Application(app_id, op, params, set(), set(), valid=False,
                                        violations=[condition_violation("lr:requires", c) for c in failed]))
                continue
            delta = _effects(sheet, op, rows, params, prefixes)
            if not delta.deleted and not delta.added and not op.noop:
                continue
            apps.append(Application(app_id, op, params, delta.deleted, delta.added))
    return apps
