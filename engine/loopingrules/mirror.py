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

    def step_solutions(self, state, where, prefixes, bindings):
        from .operations import _solutions
        return _solutions(state, where, prefixes, bindings)


class Mirror:
    """A pyoxigraph store kept equal to sheet + knowledge."""

    def __init__(self, knowledge: Graph):
        self.store = ox.Store()
        self.knowledge = set(knowledge)
        self.back: dict = {}  # oxigraph term (as stored) -> the rdflib term it came from
        self.to: dict = {}  # rdflib literal -> its oxigraph term, as stored
        self._canon = ox.Store()  # to learn how the store writes a typed literal
        self.store.bulk_extend(ox.Quad(*map(self._to, t)) for t in self.knowledge)
        self.snapshot: set = set()
        self.unsupported: set[str] = set()  # queries oxigraph can't parse: they run on rdflib
        self.scope: dict[str, set[str]] = {}  # pattern -> its in-scope variables
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

    def _bind(self, pattern: str, prefixes: str, bindings: dict) -> tuple[str, dict] | None:
        """How to bind `bindings` in `pattern`, as rdflib's initBindings do: everywhere.

        - Variables in scope go in as oxigraph substitutions, which bind them inside
          UNION branches too. (A VALUES join is evaluated after the union: a step with a
          UNION took 31 ms instead of 0.4.)
        - oxigraph refuses substitutions for variables not in scope, e.g. ones that only
          appear inside FILTER NOT EXISTS: those are joined in with VALUES, which reaches
          the filters.
        Returns (VALUES text, substitutions), or None if a blank node would need VALUES.
        """
        if not bindings:
            return "", {}
        if pattern not in self.scope:
            res = self._query(f"{prefixes}SELECT * WHERE {{ {pattern} }} LIMIT 0")
            self.scope[pattern] = {v.value for v in res.variables} if res is not None else set()
        scope = self.scope[pattern]
        subs = {ox.Variable(k): self._to(v) for k, v in bindings.items() if k in scope}
        rest = sorted(k for k in bindings if k not in scope)
        if any(isinstance(bindings[k], BNode) for k in rest):
            return None
        values = ""
        if rest:
            row = " ".join(str(self._to(bindings[k])) for k in rest)
            values = f"VALUES ({' '.join('?' + k for k in rest)}) {{ ({row}) }}\n"
        return values, subs

    def solutions(self, where, prefixes, bindings=None):
        """With `bindings` (a step), None when oxigraph can't answer: the caller falls back."""
        bound = self._bind(where, prefixes, bindings or {})
        res = None
        if bound is not None:
            res = self._query(f"{prefixes}SELECT * WHERE {{ {bound[0]}{where} }}", substitutions=bound[1])
        if res is None:
            return None if bindings is not None else self._fallback.solutions(where, prefixes)
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
        bound = self._bind(ask, prefixes, bindings)
        res = None
        if bound is not None:
            res = self._query(f"{prefixes}ASK {{ {bound[0]}{ask} }}", substitutions=bound[1])
        if res is None:
            return self._fallback.holds(ask, bindings, prefixes)
        return bool(res)

    def step_solutions(self, state, where, prefixes, bindings):
        """A step's solutions on `state`, an Overlay of the view: its net delta is applied
        to the mirror for the query, then reverted."""
        deleted = [ox.Quad(*map(self._to, t)) for t in state.deleted]
        added = [ox.Quad(*map(self._to, t)) for t in state.added]
        for q in deleted:
            self.store.remove(q)
        self.store.extend(added)
        try:
            rows = self.solutions(where, prefixes, bindings)
        finally:
            for q in added:
                self.store.remove(q)
            self.store.extend(deleted)
        if rows is None:  # a blank-node binding, or a pattern oxigraph can't parse
            from .operations import _solutions
            rows = _solutions(state, where, prefixes, bindings)
        return rows


def available() -> bool:
    return ox is not None and os.environ.get("LR_MATCHER", "").lower() != "rdflib"


def describe() -> str:
    """Which matcher the engine uses, and why: for `lr` to print and for bug reports."""
    if available():
        return f"oxigraph {ox.__version__}"
    return "rdflib (" + (_missing or "LR_MATCHER=rdflib") + ")"


def make_mirror(knowledge: Graph) -> Mirror | None:
    return Mirror(knowledge) if available() else None
