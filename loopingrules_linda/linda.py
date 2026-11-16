"""`loopingrules_linda` -- a SPIKE: a minimal, faithful Linda tuple space.

Kept so `docs/patterns-oblivious-composition.md` §7 can *check* its own claim --
that the substrate's keyed, conjoined match does something Linda's positional
template does not -- instead of asserting it. Like `loopingrules_islands` and
`loopingrules_forge`, this is a spike: deliberately absent from
`pyproject.toml`'s `packages=`, pinned by `tests/test_linda.py`, and it exists to
be falsified.

Linda (Gelernter, 1985) is a *coordination* language: a shared associative store
of **tuples** and generative operations over it -- `out` (put), `rd` (read a
matching tuple, leaving it), `in_` (read a matching tuple, removing it; Linda's
`in`), and `eval` (put a tuple with a pending process -- not implemented here). A
**template** is a tuple whose elements are **actuals** (matched by value),
**formals** (`Var`, binding, with a repeated name enforcing equality), or a
wildcard (`ANY`). Matching is associative and **positional**: a tuple matches a
template iff same arity and every element matches.

`rd`/`in_` BLOCK until a match (the A/B's M4 axis); `rdp`/`inp` are the
non-blocking probe extensions some implementations add, and are how this spike
expresses an absence test (M2).
"""

from __future__ import annotations

import time


class _Any:
    """The wildcard: matches any element, binds nothing."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "?"


ANY = _Any()


class Var:
    """A formal: binds the element; a REPEATED name must bind an equal value."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return "?%s" % self.name

    def __eq__(self, other) -> bool:
        return isinstance(other, Var) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("Var", self.name))


class Blocked(Exception):
    """`rd`/`in_` found no match before its timeout (basic Linda would block
    forever; a bounded wait is what makes it testable)."""


def _match(template, tup, bindings):
    """A new bindings dict if `tup` matches `template`, else `None`."""
    if len(template) != len(tup):
        return None
    out = dict(bindings)
    for pattern, value in zip(template, tup):
        if isinstance(pattern, Var):
            seen = out.get(pattern.name, _UNSET)
            if seen is _UNSET:
                out[pattern.name] = value
            elif seen != value:
                return None
        elif pattern is ANY:
            continue
        elif pattern != value:
            return None
    return out


class _Unset:
    __slots__ = ()


_UNSET = _Unset()


class TupleSpace:
    """A shared associative store of tuples, and the four generative ops."""

    def __init__(self) -> None:
        self._tuples = []

    def __len__(self) -> int:
        return len(self._tuples)

    def tuples(self) -> "list":
        """Every tuple, oldest first, as a plain list (a snapshot)."""
        return list(self._tuples)

    def out(self, *fields) -> "TupleSpace":
        """Put the tuple `fields`. Always succeeds."""
        self._tuples.append(tuple(fields))
        return self

    def _find(self, template):
        for index, tup in enumerate(self._tuples):
            bindings = _match(tuple(template), tup, {})
            if bindings is not None:
                return index, tup, bindings
        return None

    def all(self, *template) -> "list":
        """Every `(tuple, bindings)` matching `template`, oldest first -- a
        non-destructive SCAN (no equivalent primitive in Linda; the absence of
        an index is the point)."""
        out = []
        for tup in self._tuples:
            bindings = _match(tuple(template), tup, {})
            if bindings is not None:
                out.append((tup, bindings))
        return out

    def rdp(self, *template):
        """Non-blocking read: `(tuple, bindings)`, or `None`."""
        found = self._find(template)
        return None if found is None else (found[1], found[2])

    def inp(self, *template):
        """Non-blocking take: `(tuple, bindings)`, or `None`."""
        found = self._find(template)
        if found is None:
            return None
        index, tup, bindings = found
        del self._tuples[index]
        return (tup, bindings)

    def rd(self, *template, timeout: float = 0.05, interval: float = 0.001):
        """Blocking read: the first matching `(tuple, bindings)`, or raise
        `Blocked` if none appears within `timeout`."""
        deadline = time.monotonic() + timeout
        while True:
            found = self.rdp(*template)
            if found is not None:
                return found
            if time.monotonic() >= deadline:
                raise Blocked("no tuple matched %r" % (tuple(template),))
            time.sleep(interval)

    def in_(self, *template, timeout: float = 0.05, interval: float = 0.001):
        """Blocking take: the first matching `(tuple, bindings)`, removed, or
        raise `Blocked` (this is Linda's `in`)."""
        deadline = time.monotonic() + timeout
        while True:
            found = self.inp(*template)
            if found is not None:
                return found
            if time.monotonic() >= deadline:
                raise Blocked("no tuple matched %r" % (tuple(template),))
            time.sleep(interval)
