"""R1 -- the forge's IR is analyzable WITHOUT the Python AST, totally.

Run: `python -m loopingrules_reflect.r1`

`docs/plan-reflection.md`'s second probe, and the one `analyze.py`'s own
docstring says cannot be done to arbitrary Python: *"This module does not try
to analyze arbitrary Python soundly -- that is not possible in general."*
`analyze` is a PARTIAL function -- it raises `Opaque` the moment a rule leaves
the dialect, because Python is open. The IR is CLOSED (a fixed, small set of
node tags), so reads/writes over it is a TOTAL function: every well-formed
rule is analyzable, and the only refusal is an unknown tag, which is a bug in
the walker, not a gap in the language.

That totality is the whole reason IR-native was chosen (`docs/
plan-reflection.md`): it is what makes an EA safe to mutate rules, because
every mutation has a total, static account of what it reads and writes.

## The result

For `cards`' twelve IR rules, `reads`/`writes`/`negated_reads`/`destroys`
derived from the IR agree with `analyze` on the lowered Python -- the same
claim M0 made for BEHAVIOUR, now made for STRUCTURE.

One finding, and it is the concession ledger showing up in analysis: the
verbatim helper `_status_text` (raw Python, embedded as an escape for
lexing/formatting) is not IR, so its reads cannot be recovered from the IR
alone. The walker therefore REQUIRES a referenced verbatim helper to DECLARE
its reads/writes (`external=`, derived once by `analyze`), and REFUSES -- the
same refuse-rather-than-guess posture as `Opaque` -- when one is not declared.
A closed semantics makes analysis total; it does not make the EDGE disappear,
only forced and named.

## What this does not settle

* **The hash, once more.** This proves analysis; it does not define the rule
  identity `RuleControl` keys on. That is `rule_hash`'s IR-datum hash, still
  to be built (see `docs/plan-reflection.md` and `reflect.rule_hash`).
* **Where the IR lives.** For now it is `loopingrules_forge.m0`. IR-native
  means it should become a frozen engine core (the `circuits.py` precedent);
  this probe deliberately does not move it, and proves the seam first.
* **Loops, mutation, blocking.** The cards IR uses no `while`, no in-place
  mutation of a component field, no tool call. Their analysis, if added, is
  not proven here.
"""

from __future__ import annotations

import collections

import loopingrules.analyze as analyze

from loopingrules_forge import m0


class Unknown(Exception):
    """An IR node the walker does not recognise. A closed semantics has no
    `Opaque` -- only nodes that exist and nodes that do not. This is the
    latter, and it is raised rather than skipped so a gap cannot look like
    "reads nothing."""


Analysis = collections.namedtuple("Analysis", "reads writes negated_reads destroys")


class _Out:
    """A mutable accumulator; `Analysis` is the frozen result handed out."""

    def __init__(self):
        self.reads = set()
        self.writes = set()
        self.negated_reads = set()
        self.destroys = False

KNOWN_EXPR = frozenset({
    "const", "var", "attr", "index", "meth", "call", "helper", "the", "first",
    "get", "all", "each", "bin", "cmp", "and", "or", "not", "isnone",
    "notnone", "cond", "fmt", "list", "tuple",
})
KNOWN_STMT = frozenset({
    "let", "unpack", "for", "if", "attach", "detach", "replace", "spawn",
    "destroy", "append", "continue", "return",
})
# The expression tags that ARE a world read, so negation can mark them.
READ_TAGS = frozenset({"the", "first", "get", "all", "each"})


def _is_absent(node) -> bool:
    """`None`, `()`, `[]` -- the right-hand sides `analyze` reads as absence."""
    return ((node[0] == "const" and node[1] is None)
            or (node[0] in ("list", "tuple") and not node[1]))


def _is_zero(node) -> bool:
    return node[0] == "const" and node[1] == 0


def _scan_expr(e, out, helpers, external, negate=False):
    tag = e[0]
    if tag not in KNOWN_EXPR:
        raise Unknown("expression %r" % (tag,))
    if tag in ("const", "var"):
        return
    if tag in ("the", "first", "all"):
        _read(out, e[1], negate)
        return
    if tag == "each":
        for kind in e[1]:
            _read(out, kind, negate)
        for kind in e[2]:                       # `without=` -- always positive
            _read(out, kind, False)
        return
    if tag == "get":
        _scan_expr(e[1], out, helpers, external)
        _read(out, e[2], negate)
        return
    if tag == "helper":
        name, args = e[1], e[2]
        for arg in args:
            _scan_expr(arg, out, helpers, external)
        if name in helpers:
            _params, body = helpers[name]
            for stmt in body:
                _scan_stmt(stmt, out, helpers, external)
        elif name in external:
            reads, writes, destroys = external[name]
            out.reads |= reads
            out.writes |= writes
            out.destroys = out.destroys or destroys
        else:
            raise Unknown(
                "helper %r is neither IR nor a declared verbatim helper -- "
                "a verbatim helper must DECLARE its reads (see the module "
                "note)" % (name,))
        return
    if tag in ("not", "isnone"):
        _scan_expr(e[1], out, helpers, external, negate=True)
        return
    if tag in ("attr", "notnone"):
        _scan_expr(e[1], out, helpers, external)
        return
    if tag == "index":
        _scan_expr(e[1], out, helpers, external)
        if not isinstance(e[2], int):
            _scan_expr(e[2], out, helpers, external)
        return
    if tag == "meth":
        _scan_expr(e[1], out, helpers, external)
        for arg in e[3]:
            _scan_expr(arg, out, helpers, external)
        return
    if tag == "call":
        for arg in e[2]:
            _scan_expr(arg, out, helpers, external)
        return
    if tag in ("fmt", "list", "tuple"):
        for arg in e[2] if tag == "fmt" else e[1]:
            _scan_expr(arg, out, helpers, external)
        return
    if tag == "bin":
        _scan_expr(e[2], out, helpers, external)
        _scan_expr(e[3], out, helpers, external)
        return
    if tag in ("and", "or"):
        _scan_expr(e[1], out, helpers, external)
        _scan_expr(e[2], out, helpers, external)
        return
    if tag == "cond":
        _scan_expr(e[1], out, helpers, external)
        _scan_expr(e[2], out, helpers, external)
        _scan_expr(e[3], out, helpers, external)
        return
    if tag == "cmp":
        op, left, right = e[1], e[2], e[3]
        _scan_expr(left, out, helpers, external)
        _scan_expr(right, out, helpers, external)
        # `read is None` / `read == None` / `read == []`.
        if op in ("is", "=="):
            if _is_absent(right) and left[0] in READ_TAGS:
                _scan_expr(left, out, helpers, external, negate=True)
            elif _is_absent(left) and right[0] in READ_TAGS:
                _scan_expr(right, out, helpers, external, negate=True)
        # `len(read) == 0`.
        for a, b in ((left, right), (right, left)):
            if a[0] == "call" and a[1] == "len" and _is_zero(b):
                inner = a[2][0]
                if inner[0] in READ_TAGS:
                    _scan_expr(inner, out, helpers, external, negate=True)
        return
    raise Unknown("unhandled expression %r" % (tag,))    # pragma: no cover


def _read(out, kind, negate):
    out.reads.add(kind)
    if negate:
        out.negated_reads.add(kind)


def _scan_stmt(s, out, helpers, external):
    tag = s[0]
    if tag not in KNOWN_STMT:
        raise Unknown("statement %r" % (tag,))
    if tag in ("let", "unpack"):
        _scan_expr(s[2], out, helpers, external)
        return
    if tag == "for":
        _scan_expr(s[1], out, helpers, external)
        for stmt in s[3]:
            _scan_stmt(stmt, out, helpers, external)
        return
    if tag == "if":
        _scan_expr(s[1], out, helpers, external)
        for stmt in s[2] + s[3]:
            _scan_stmt(stmt, out, helpers, external)
        return
    if tag in ("attach", "replace"):
        _scan_expr(s[1], out, helpers, external)
        out.writes.add(s[2])
        for value in s[3].values():
            _scan_expr(value, out, helpers, external)
        return
    if tag == "spawn":
        out.writes.add(s[1])
        for value in s[2].values():
            _scan_expr(value, out, helpers, external)
        return
    if tag == "detach":
        _scan_expr(s[1], out, helpers, external)
        out.writes.add(s[2])
        return
    if tag == "destroy":
        _scan_expr(s[1], out, helpers, external)
        out.destroys = True
        return
    if tag == "append":
        _scan_expr(s[1], out, helpers, external)
        _scan_expr(s[2], out, helpers, external)
        return
    if tag == "return":
        if s[1] is not None:
            _scan_expr(s[1], out, helpers, external)
        return
    if tag == "continue":
        return
    raise Unknown("unhandled statement %r" % (tag,))     # pragma: no cover


def reads_of(body, helpers=None, external=None) -> Analysis:
    """Reads/writes/negated_reads/destroys of one IR rule body -- total over
    the IR, refusing only on an undeclared helper or an unknown node."""
    out = _Out()
    for stmt in body:
        _scan_stmt(stmt, out, helpers or {}, external or {})
    return Analysis(out.reads, out.writes, out.negated_reads, out.destroys)


def _external_helpers(module):
    """The declared reads/writes of the verbatim (non-IR) helpers, derived
    once by `analyze` -- the one place the IR analysis leans on the Python
    analysis it is meant to replace, and only at the edge."""
    out = {}
    for name in m0.VERBATIM:
        fn = getattr(module, name)
        try:
            analysis = analyze.analyze(fn)
        except analyze.Opaque:
            continue
        out[name] = (set(analysis.reads), set(analysis.writes),
                     analysis.destroys)
    return out


def report():
    module = m0.load_emitted(m0.emit_module())
    external = _external_helpers(module)

    rows = []
    agree = 0
    for name in m0.IR:
        got = reads_of(m0.IR[name](), m0.IR_HELPERS, external)
        real = analyze.analyze(getattr(module, name))
        ok = (got.reads == real.reads and got.writes == real.writes
              and got.negated_reads == real.negated_reads
              and got.destroys == real.destroys)
        agree += ok
        rows.append((name, ok, got, real))
    return {"rows": rows, "agree": agree, "total": len(m0.IR),
            "external": tuple(external), "ok": agree == len(m0.IR)}


def main():
    result = report()
    print("== R1: IR analysis without the Python AST", "=" * 30)
    print("  verbatim helpers (declared): %s"
          % (", ".join(result["external"]) or "none"))
    for name, ok, got, real in result["rows"]:
        print("  %-18s %s" % (name, "ok" if ok else "MISMATCH"))
        if not ok:
            print("      ir  reads=%r writes=%r neg=%r destroys=%r"
                  % (sorted(k.__name__ for k in got.reads),
                     sorted(k.__name__ for k in got.writes),
                     sorted(k.__name__ for k in got.negated_reads),
                     got.destroys))
            print("      py  reads=%r writes=%r neg=%r destroys=%r"
                  % (sorted(k.__name__ for k in real.reads),
                     sorted(k.__name__ for k in real.writes),
                     sorted(k.__name__ for k in real.negated_reads),
                     real.destroys))
    print("  %d/%d rules: IR analysis agrees with `analyze`"
          % (result["agree"], result["total"]))
    print("  ALL AS EXPECTED:", result["ok"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
