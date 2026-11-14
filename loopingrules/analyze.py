"""Static analysis of a rule: which ATTRIBUTES it reads, which it writes --
derived from its own source, not declared by hand. This is the answer to
two things at once: `PRINCIPLES.md`'s named, previously unsolved gap
("declare `watches` too narrow... there is no way to catch this from
here") -- solved by removing the hand-written declaration rather than
checking it, since `Loop.rule` calls `analyze()` itself at registration
time and uses the result AS a rule's gate (see `loopingrules.loop`, "A
rule wakes only when something it reads exists") -- and a "map" of which
rules touch which attributes, without inventing a language to get one.

## Attribute names, not component classes

Under the attribute substrate (`docs/plan-attributes.md`, D8) a rule names
a fact with a **string literal** -- `w.get(e, "cash")`, `w.each("card",
"tags")` -- where the component engine named a class. This walk is the
same walk; the thing it resolves is a `str`, never a `module.__dict__`
lookup. A name is a read when the method reads it, a write when the method
writes it. `spawn`/`destroy` keep their old shape: creating an entity
touches no NAME (`spawn` contributes no read or write), and destroying an
entity names no name either -- `Analysis.destroys` records only that the
rule CAN destroy entities, the same honest limit as before.

## Why AST analysis of plain Python, not a new DSL

A rule is already narrow by convention (`loopingrules.loop`'s own
docstring): a plain function of one `World`, and every write or query it
makes goes through one of the named methods, always called on that one
parameter. `PRINCIPLES.md` also already establishes that rules never call
each other -- "no rule calls another, the only channel between them is
what gets deposited into the shared `World`." So the one thing left to
resolve, to get a sound map out of plain Python, is a same-module helper
a rule calls that ALSO touches the world -- `examples.cards._find_card(w,
name)`, which calls `w.all("card_def")` inside it, is exactly this shape,
and the positive test is built against it.

## The dialect, and refusing what falls outside it

This module does not try to analyze arbitrary Python soundly -- that is
not possible in general (`getattr`, a callable stored in a variable, a
decorator that hides the real signature). It analyzes exactly the dialect
this codebase's rules already happen to be written in: the world parameter
is used only as the receiver of one of the methods below, or passed
positionally/by keyword straight into a plain function defined in the SAME
module (recursed into, one level at a time, arbitrarily deep). The moment
the world parameter is used any other way -- stored in a variable,
forwarded through `*args`, passed to an imported function, a starred call,
an attribute-name argument that is not a string literal -- this raises
`Opaque` rather than silently under-reporting. A rule that trips this
either gets rewritten to fit the dialect, or is carried in a report's own
`opaque` set, honestly labeled "unknown," never folded into "reads/writes
nothing."

## Reading the change log

`w.changes(changed="cash")` (see `docs/plan-memory.md`) is a read whose
genuinely-read name, if any, is the `changed=` argument: when that
argument is a string literal it is attributed as a read, so a rule that
only reacts to changes of one attribute keeps a correct gate; with no
`changed=` at all it contributes no read and the rule falls back to
"called every tick", the safe default, while a non-literal `changed=`
cannot be attributed and is `Opaque`. `w.recent(n)` reads the log too but
names no attribute, so it is the same safe fallback.

## What a rule hard-codes

`literals(fn)` reports every comparison in `fn` of a non-literal
expression against a NUMERIC literal, as `Literal(file, line, value,
expression)` records. `docs/tuning.md`'s design rule -- "a tunable rule
never hard-codes its threshold; it reads an attribute" -- is the reason:
the same AST walk that derives reads can point at the literal a tunable
rule should have turned into a read. This module reports the sites and
stops; whether a given literal is a threshold that SHOULD have been a knob
or a genuinely structural constant is a judgment only the author can make,
so the policy -- and every suppression, with its reason -- lives in the
calibration package's linter, not here. `literals` refuses exactly as
`analyze` does.
"""

from __future__ import annotations

import ast
import collections
import inspect
import textwrap
from typing import Dict, Set


# Which world methods read which names, and where the name sits in the
# call. `entity`-first methods (get/has/set/unset/...) name from index 1;
# the entity-less readers (each/first/all/the/populated) start at 0.
READS = {"each", "get", "all", "the", "first"}
EXISTENCE_READS = {"has", "populated"}
WRITES = {"set", "unset", "add", "remove", "append", "pop", "mark", "unmark"}


class Opaque(Exception):
    """Raised the moment a rule (or a helper it calls) uses its world
    parameter in a way this module cannot statically account for. Carries
    the rule's own qualified name and a human reason -- refuse rather than
    guess, the same discipline every parse boundary in this codebase
    already applies. See the module docstring's "the dialect"."""


class Analysis:
    """One rule's own reads and writes, derived, not declared.

    `reads`/`writes` are ATTRIBUTE NAMES (strings). `negated_reads` is a
    subset of `reads`: every name this rule's own source tests for ABSENCE
    (`if not w.each("x"):`, `w.first("x") is None`, `len(w.each("x")) ==
    0`, `not w.has(e, "x")`, `not w.populated("x")`) rather than presence.
    `Loop.rule` gates a rule on `reads - negated_reads`, never on `reads`
    itself -- a rule reacting to a name NOT existing (`test_engine.py`'s
    own `pong`, spawning a fresh `Ping` exactly when none is left, is the
    case that found this) would otherwise be gated on the one condition
    that guarantees it has nothing to do. A name appearing BOTH ways is
    excluded everywhere, conservatively.
    """

    def __init__(self) -> None:
        self.reads: Set[str] = set()
        self.negated_reads: Set[str] = set()
        self.writes: Set[str] = set()
        self.destroys: bool = False

    def __repr__(self) -> str:
        return "Analysis(reads=%r, negated_reads=%r, writes=%r, destroys=%r)" % (
            sorted(self.reads), sorted(self.negated_reads),
            sorted(self.writes), self.destroys)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Analysis):
            return NotImplemented
        return (self.reads, self.negated_reads, self.writes, self.destroys) == (
            other.reads, other.negated_reads, other.writes, other.destroys)


def _qualname(fn) -> str:
    module = getattr(fn, "__module__", "") or "?"
    return "%s.%s" % (module.rsplit(".", 1)[-1], getattr(fn, "__name__", "?"))


_CACHE: "dict" = {}


def analyze(fn) -> Analysis:
    """Statically derive what attributes `fn` -- a rule, a plain function
    of one `World` -- reads and writes. Raises `Opaque` the moment `fn`,
    or a same-module helper it calls with the world parameter, falls
    outside the dialect the module docstring names.

    Cached BY FUNCTION OBJECT: the derivation depends only on `fn`'s own
    source, and no caller mutates the returned `Analysis` (callers only
    read it, or take a set difference of it), so a rule registered on many
    loops -- as a replay harness does, thousands of times -- is parsed
    once. A function whose source is unavailable still raises `Opaque` on
    every call; failures are not cached.
    """
    cached = _CACHE.get(fn)
    if cached is not None:
        return cached
    module = inspect.getmodule(fn)
    if module is None:
        raise Opaque(_qualname(fn), "no module found to resolve names against")
    analysis = Analysis()
    _walk_function(fn, module, analysis, set())
    _CACHE[fn] = analysis
    return analysis


# One hard-coded comparison site: `value` is the numeric literal, `line` its
# real line in `file`, `expression` the whole comparison's source -- see
# `literals`.
Literal = collections.namedtuple("Literal", "file line value expression")


def _is_numeric_literal(node) -> bool:
    # `bool` is a subclass of `int`; `x > True` is not a numeric threshold,
    # so it is excluded explicitly rather than folded in by isinstance.
    return (isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool))


_COMPARE_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


def literals(fn) -> tuple:
    """Every place `fn` compares a non-literal expression against a NUMERIC
    literal, as `Literal(file, line, value, expression)` records, in source
    order. `line` is the real file line (decorator-aware). A comparison of
    two literals (`1 < 2`) or of two expressions (`a > b`) is not one of
    these -- only a threshold against a value built at runtime is.

    Raises `Opaque` exactly as `analyze` does: a rule this module cannot
    see cannot be checked for literals either, so the caller must tell "no
    literals" apart from "not looked at".
    """
    analyze(fn)                     # same refusal, and it fills the cache
    tree = _source_tree(fn)
    path = inspect.getsourcefile(fn) or "<unknown>"
    _lines, start = inspect.getsourcelines(fn)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left] + list(node.comparators)
        for op, left, right in zip(node.ops, sides, sides[1:]):
            if not isinstance(op, _COMPARE_OPS):
                continue
            left_lit = _is_numeric_literal(left)
            right_lit = _is_numeric_literal(right)
            if left_lit == right_lit:
                continue            # both literal or neither: not the shape
            found.append(Literal(
                path, start + node.lineno - 1,
                left.value if left_lit else right.value, ast.unparse(node)))
    # `ast.walk` is breadth-first, not source order; sort so a multi-literal
    # rule reports its sites top to bottom, deterministically.
    found.sort(key=lambda site: site.line)
    return tuple(found)


class Report:
    """`attribute_map()`'s own result: for every attribute name seen, which
    rules (by qualified name) read it and which write it -- plus `opaque`,
    the rules this could not analyze at all, each with why. A name absent
    from `opaque` and absent from both `reads`/`writes` was never mentioned
    by any rule given; a rule name present in `opaque` is deliberately
    absent from `reads`/`writes` too, even for the part of it that WAS
    resolved before the point it wasn't -- a partial map is worse here than
    an honest "unknown."
    """

    def __init__(self) -> None:
        self.reads: Dict[str, Set[str]] = {}
        self.writes: Dict[str, Set[str]] = {}
        self.destroys: Set[str] = set()
        self.opaque: Dict[str, str] = {}

    def __repr__(self) -> str:
        return "Report(reads=%d names, writes=%d names, opaque=%r)" % (
            len(self.reads), len(self.writes), self.opaque)


def attribute_map(*functions) -> Report:
    """Build a `Report` by `analyze`-ing every function given. A function
    that raises `Opaque` is recorded under `Report.opaque` by its own
    qualified name and reason, never silently treated as reading or
    writing nothing -- see the module docstring.
    """
    report = Report()
    for fn in functions:
        name = _qualname(fn)
        try:
            analysis = analyze(fn)
        except Opaque as exc:
            report.opaque[name] = str(exc)
            continue
        for attr in analysis.reads:
            report.reads.setdefault(attr, set()).add(name)
        for attr in analysis.writes:
            report.writes.setdefault(attr, set()).add(name)
        if analysis.destroys:
            report.destroys.add(name)
    return report


# -- the walk ----------------------------------------------------------

def _source_tree(fn):
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError) as exc:
        raise Opaque(_qualname(fn), "no source available: %s" % exc) from exc
    tree = ast.parse(textwrap.dedent(source)).body[0]
    if not isinstance(tree, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise Opaque(_qualname(fn), "source is not a plain function")
    return tree


def _walk_function(fn, module, analysis: Analysis, seen: set,
                    world_name: "str | None" = None) -> None:
    if fn in seen:
        return
    seen.add(fn)
    tree = _source_tree(fn)
    params = [a.arg for a in tree.args.args]
    if world_name is None:
        if not params:
            raise Opaque(_qualname(fn),
                         "no parameters -- cannot tell which one is the World")
        world_name = params[0]

    handled_names: "set[int]" = set()   # id() of Name nodes already accounted for
    parents = {id(child): node for node in ast.walk(tree)
              for child in ast.iter_child_nodes(node)}

    def _is_negated(call) -> bool:
        """Whether `call` -- a world-read this walk just resolved -- is
        tested for ABSENCE rather than presence: `not call`, `call is
        None`/`call == None`, `call == []`, or `len(call) == 0`. See
        `Analysis.negated_reads`' own docstring for why this matters."""
        parent = parents.get(id(call))
        if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not):
            return True
        if isinstance(parent, ast.Compare) and len(parent.ops) == 1:
            op = parent.ops[0]
            other = (parent.comparators[0] if parent.left is call
                    else parent.left)
            if isinstance(op, (ast.Is, ast.Eq)):
                if isinstance(other, ast.Constant) and other.value is None:
                    return True
                if isinstance(other, (ast.List, ast.Tuple)) and not other.elts:
                    return True
        if (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                and parent.func.id == "len"):
            grandparent = parents.get(id(parent))
            if isinstance(grandparent, ast.Compare) and len(grandparent.ops) == 1:
                op = grandparent.ops[0]
                other = (grandparent.comparators[0] if grandparent.left is parent
                        else grandparent.left)
                if (isinstance(op, ast.Eq) and isinstance(other, ast.Constant)
                        and other.value == 0):
                    return True
        return False

    def resolve_name(node) -> str:
        # A name is a str literal, full stop. Anything else (a variable, a
        # concatenation, a class) cannot be resolved without evaluating it,
        # so it is Opaque, not guessed at.
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            handled_names.add(id(node))
            return node.value
        raise Opaque(_qualname(fn),
                     "an attribute name must be a string literal: %r"
                     % ast.unparse(node))

    def resolve_name_list(node):
        elts = node.elts if isinstance(node, (ast.Tuple, ast.List)) else [node]
        return [resolve_name(elt) for elt in elts]

    def handle_world_method(call, method):
        args = call.args
        if any(isinstance(a, ast.Starred) for a in args) or any(
                kw.arg is None for kw in call.keywords):
            raise Opaque(_qualname(fn),
                         "%s(...) called with a starred/**-argument -- "
                         "cannot enumerate its attribute names" % method)
        names = []
        if method in READS or method in EXISTENCE_READS:
            # Where the NAME arguments sit: `get(entity, name[, default])`
            # names from index 1 and only index 1; `has(entity, *names)`
            # from index 1 to the end; the entity-less readers start at 0.
            if method == "get":
                window = args[1:2]
            elif method == "has":
                window = args[1:]
            elif method in ("all", "the"):
                window = args[0:1]
            else:                       # each, first, populated
                window = args[0:]
            for a in window:
                names.append(resolve_name(a))
            analysis.reads.update(names)
            for kw in call.keywords:
                if kw.arg == "without":
                    analysis.reads.update(resolve_name_list(kw.value))
            if names and _is_negated(call):
                analysis.negated_reads.update(names)
        elif method in WRITES:
            window = args[1:2]
            for a in window:
                analysis.writes.add(resolve_name(a))
        elif method == "spawn":
            pass                        # creating an entity touches no name
        elif method == "destroy":
            analysis.destroys = True
        elif method == "changes":
            for kw in call.keywords:
                if kw.arg != "changed":
                    continue
                analysis.reads.add(resolve_name(kw.value))
        elif method in ("recent", "entity", "revision", "attributes", "show",
                        "alive"):
            pass                        # reads the world, names no attribute
        else:
            raise Opaque(_qualname(fn),
                         "unknown world method %r -- this module's own "
                         "vocabulary of world methods may be out of date"
                         % method)

    def mark_world_args(call):
        for a in call.args:
            if isinstance(a, ast.Name) and a.id == world_name:
                handled_names.add(id(a))
        for kw in call.keywords:
            if isinstance(kw.value, ast.Name) and kw.value.id == world_name:
                handled_names.add(id(kw.value))

    def handle_helper_call(call):
        callee = module.__dict__.get(call.func.id)
        if not inspect.isfunction(callee) or callee.__module__ != module.__name__:
            raise Opaque(_qualname(fn),
                         "%r is not a plain function defined in this "
                         "module -- cannot follow the world parameter "
                         "into it" % call.func.id)
        matched = None
        callee_params = [a.arg for a in ast.parse(
            textwrap.dedent(inspect.getsource(callee))).body[0].args.args]
        for index, a in enumerate(call.args):
            if isinstance(a, ast.Name) and a.id == world_name:
                matched = callee_params[index] if index < len(callee_params) else None
                handled_names.add(id(a))
                break
        if matched is None:
            for kw in call.keywords:
                if isinstance(kw.value, ast.Name) and kw.value.id == world_name:
                    matched = kw.arg
                    handled_names.add(id(kw.value))
                    break
        if matched is None:
            return    # `w` was not actually passed to this call at all
        _walk_function(callee, module, analysis, seen, world_name=matched)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == world_name):
            handled_names.add(id(func.value))
            handle_world_method(node, func.attr)
        elif isinstance(func, ast.Name):
            if any(isinstance(a, ast.Name) and a.id == world_name
                   for a in node.args) or any(
                    isinstance(kw.value, ast.Name) and kw.value.id == world_name
                    for kw in node.keywords):
                handle_helper_call(node)

    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and node.id == world_name
                and isinstance(node.ctx, ast.Load) and id(node) not in handled_names):
            raise Opaque(_qualname(fn),
                         "the world parameter %r is used in a way this "
                         "module cannot account for (line %s)" %
                         (world_name, getattr(node, "lineno", "?")))
