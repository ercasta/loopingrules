"""Matching operation patterns on a pyoxigraph mirror of sheet + knowledge (optional).

rdflib evaluates SPARQL in pure Python, and operation patterns (D23) with nested
FILTER NOT EXISTS over knowledge are where autopilot spends most of its time.
pyoxigraph evaluates the same patterns natively, 8-15x faster on the benchmarks.

- Only operation WHEREs and guards (lr:requires) run here. Steps, postconditions,
  controllers and SHACL read per-application overlays and stay on rdflib.
- The mirror holds the knowledge, loaded once, and is synced with the sheet before
  each enumeration by diffing it against the last snapshot. That's O(sheet), but it
  can't miss a write path (edits, tools, undo, acks).
- Terms map back to the very rdflib terms they came from, so templates instantiate
  exactly what is in the sheet.
- Patterns are security-checked at load time (security.check_query) as before.

pyoxigraph is a native module: it is optional (`pip install loopingrules[fast]`),
and some builds are blocked by Windows Smart App Control. When it is missing or
can't load, `make_matcher` returns the rdflib matcher. LR_MATCHER=rdflib forces it.
"""

from __future__ import annotations

import os
from typing import Protocol

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.term import Node

try:
    import pyoxigraph as ox
    _missing = ""
except ImportError as e:  # not installed, or its DLL blocked (Smart App Control raises ImportError too)
    ox = None
    _missing = ("pyoxigraph is not installed" if isinstance(e, ModuleNotFoundError)
                else f"pyoxigraph can't load ({e}); on Windows, try pyoxigraph==0.5.0")

_XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"


class Matcher(Protocol):
    def solutions(self, where: str, prefixes: str) -> list[dict[str, Node]]: ...
    def holds(self, ask: str, bindings: dict[str, Node], prefixes: str) -> bool: ...


class RdflibMatcher:
    """Evaluates patterns on an rdflib graph (the sheet + knowledge view)."""

    def __init__(self, graph: Graph):
        self.graph = graph

    def solutions(self, where, prefixes):
        from .operations import _solutions
        return _solutions(self.graph, where, prefixes)

    def holds(self, ask, bindings, prefixes):
        from .operations import _holds
        return _holds(self.graph, ask, bindings, prefixes)


class Mirror:
    """A pyoxigraph store kept equal to sheet Ã¢Ë†Âª knowledge."""

    def __init__(self, knowledge: Graph):
        self.store = ox.Store()
        self.knowledge = set(knowledge)
        self.back: dict = {}  # oxigraph term (as stored) -> the rdflib term it came from
        self.to: dict = {}  # rdflib literal -> its oxigraph term, as stored
        self._canon = ox.Store()  # to learn how the store writes a typed literal
        self.store.bulk_extend(ox.Quad(*map(self._to, t)) for t in self.knowledge)
        self.snapshot: set = set()
        self.unsupported: set[str] = set()  # queries oxigraph can't parse: they run on rdflib
        self._fallback: RdflibMatcher | None = None

    # --- terms ---------------------------------------------------------------
    def _to(self, t: Node):
        if isinstance(t, URIRef):
            o = ox.NamedNode(str(t))
        elif isinstance(t, BNode):
            o = ox.BlankNode(str(t))
        elif isinstance(t, Literal):
            if t.language:
                o = ox.Literal(str(t), language=t.language)
            elif t.datatype is not None:
                o = self.to.get(t)
                if o is None:
                    o = self.to[t] = self._canonical(ox.Literal(str(t), datatype=ox.NamedNode(str(t.datatype))))
            else:
                o = ox.Literal(str(t))
        else:
            raise TypeError(f"unsupported term {t!r}")
        self.back.setdefault(o, t)
        return o

    def _canonical(self, lit):
        """The store writes some typed literals in canonical form ("1.50"^^xsd:decimal as
        "1.5"), so the term it returns is not the one it was given. Two sheet literals
        with the same canonical form are one term in the mirror (rare: not handled)."""
        x = ox.NamedNode("urn:lr:canon")
        self._canon.add(ox.Quad(x, x, lit))
        (q,) = list(self._canon)
        self._canon.remove(q)
        return q.object

    def _from(self, o) -> Node:
        t = self.back.get(o)
        if t is not None:
            return t
        if isinstance(o, ox.NamedNode):
            return URIRef(o.value)
        if isinstance(o, ox.BlankNode):
            return BNode(o.value)
        if o.language:
            return Literal(o.value, lang=o.language)
        dt = o.datatype.value
        return Literal(o.value, datatype=None if dt == _XSD_STRING else URIRef(dt))

    # --- sync ----------------------------------------------------------------
    def sync(self, sheet: Graph, view: Graph) -> "Mirror":
        current = set(sheet)
        for t in current - self.snapshot:
            self.store.add(ox.Quad(*map(self._to, t)))
        for t in self.snapshot - current:
            if t not in self.knowledge:
                self.store.remove(ox.Quad(*map(self._to, t)))
        self.snapshot = current
        self._fallback = RdflibMatcher(view)
        return self

    # --- queries -------------------------------------------------------------
    def _query(self, text: str, **kw):
        if text in self.unsupported:
            return None
        try:
            return self.store.query(text, **kw)
        except SyntaxError:
            self.unsupported.add(text)
            return None

    def solutions(self, where, prefixes):
        res = self._query(f"{prefixes}SELECT * WHERE {{ {where} }}")
        if res is None:
            return self._fallback.solutions(where, prefixes)
        names = [v.value for v in res.variables]
        out = []
        for sol in res:
            row = {}
            for n in names:
                v = sol[n]
                if v is not None:
                    row[n] = self._from(v)
            out.append(row)
        return out

    def holds(self, ask, bindings, prefixes):
        # rdflib binds the parameters everywhere, also inside FILTER (NOT) EXISTS. oxigraph's
        # substitutions only take variables in scope, so the parameters are joined in with
        # VALUES, which also reaches the filters. VALUES can't hold blank nodes: rdflib then.
        res = None
        if not any(isinstance(v, BNode) for v in bindings.values()):
            names = sorted(bindings)
            values = ""
            if names:
                row = " ".join(str(self._to(bindings[n])) for n in names)
                values = f"VALUES ({' '.join('?' + n for n in names)}) {{ ({row}) }}\n"
            res = self._query(f"{prefixes}ASK {{ {values}{ask} }}")
        if res is None:
            return self._fallback.holds(ask, bindings, prefixes)
        return bool(res)


def available() -> bool:
    return ox is not None and os.environ.get("LR_MATCHER", "").lower() != "rdflib"


def describe() -> str:
    """Which matcher the engine uses, and why: for `lr` to print and for bug reports."""
    if available():
        return f"oxigraph {ox.__version__}"
    return "rdflib (" + (_missing or "LR_MATCHER=rdflib") + ")"


def make_mirror(knowledge: Graph) -> Mirror | None:
    return Mirror(knowledge) if available() else None
