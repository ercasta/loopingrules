"""Static analysis of a rule: which component types it reads, which it
writes -- derived from its own source, not declared by hand. This is the
answer to two things at once: `PRINCIPLES.md`'s named, previously
unsolved gap ("declare `watches` too narrow... there is no way to catch
this from here") and a "map" of which rules touch which components,
without inventing a language to get one.

## Why AST analysis of plain Python, not a new DSL

A rule is already narrow by convention (`loopingrules.loop`'s own
docstring): a plain function of one `World`, and every write or query it
makes goes through one of eleven named methods, always called on that one
parameter. `PRINCIPLES.md` also already establishes that rules never call
each other -- "no rule calls another, the only channel between them is
what gets deposited into the shared `World`." So the one thing left to
resolve, to get a sound map out of plain Python, is a same-module helper
a rule calls that ALSO touches the world -- `examples.cards._find_card(w,
name)`, which calls `w.all(CardDef)` inside it, is exactly this shape,
and the positive test below is built against it.

## The dialect, and refusing what falls outside it

This module does not try to analyze arbitrary Python soundly -- that is
not possible in general (`getattr`, a callable stored in a variable, a
decorator that hides the real signature). It analyzes exactly the
dialect this codebase's rules already happen to be written in: the world
parameter is used only as the receiver of one of the methods below, or
passed positionally/by keyword straight into a plain function defined in
the SAME module (recursed into, one level at a time, arbitrarily deep).
The moment the world parameter is used any other way -- stored in a
variable, forwarded through `*args`, passed to an imported function, a
starred call, a component argument that is not a literal `Kind(...)` or
a bare `Kind` name -- this raises `Opaque` rather than silently
under-reporting. A rule that trips this either gets rewritten to fit the
dialect, or is carried in a report's own `opaque` set, honestly labeled
"unknown," never folded into "reads/writes nothing." That is the same
refuse-rather-than-guess discipline every parse boundary in this
codebase already applies (`examples.cards._parse_int`, `_find_card`);
this module just applies it to source code instead of a typed line.

`destroy(entity)` is a deliberate, named exception to "every write is
attributed to a Kind": it takes no component-type argument at all, so
nothing here claims to know which types an entity it destroys was
carrying. `Analysis.destroys` records only that the rule CAN destroy
entities -- a real limit on the map, not a silent one.

## Two named exceptions: `reply` and `propose`

`loopingrules.world.reply`/`propose` are cross-module by construction --
every domain's own `reply_*`/`propose_*` rule calls them from
`loopingrules.world`, never from its own module, so the "same module
only" rule above would make every one of them `Opaque` for no reason
that matters: unlike an arbitrary imported helper, what these two write
is exactly what the README already promises never changes quietly
(`reply` spawns a `Reply`; `propose` spawns a `Proposal(occasion)` plus
whatever components it was given). They are special-cased below by
identity, not by name -- a domain's own function that happens to be
called `reply` is not this one and is analyzed like any other helper.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Dict, Set

from .world import Proposal, Reply, propose as _CORE_PROPOSE, reply as _CORE_REPLY


READS = {"each", "get", "all", "the", "first"}
EXISTENCE_READS = {"has", "get_all", "populated"}
WRITES_INSTANCE = {"attach", "replace", "spawn"}   # args are `Kind(...)` calls
WRITES_KIND = {"detach"}                            # args are bare `Kind` names
WRITES_VALUE = {"remove"}                           # one arg, a `Kind(...)` call


class Opaque(Exception):
    """Raised the moment a rule (or a helper it calls) uses its world
    parameter in a way this module cannot statically account for. Carries
    the rule's own qualified name and a human reason -- refuse rather
    than guess, the same discipline every parse boundary in this codebase
    already applies. See the module docstring's "the dialect.\""""


class Analysis:
    """One rule's own reads and writes, derived, not declared."""

    def __init__(self) -> None:
        self.reads: Set[type] = set()
        self.writes: Set[type] = set()
        self.destroys: bool = False

    def __repr__(self) -> str:
        return "Analysis(reads=%r, writes=%r, destroys=%r)" % (
            sorted(k.__name__ for k in self.reads),
            sorted(k.__name__ for k in self.writes),
            self.destroys)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Analysis):
            return NotImplemented
        return (self.reads, self.writes, self.destroys) == (
            other.reads, other.writes, other.destroys)


def _qualname(fn) -> str:
    module = getattr(fn, "__module__", "") or "?"
    return "%s.%s" % (module.rsplit(".", 1)[-1], getattr(fn, "__name__", "?"))


def analyze(fn) -> Analysis:
    """Statically derive what component types `fn` -- a rule, a plain
    function of one `World` -- reads and writes. Raises `Opaque` the
    moment `fn`, or a same-module helper it calls with the world
    parameter, falls outside the dialect the module docstring names.
    """
    module = inspect.getmodule(fn)
    if module is None:
        raise Opaque(_qualname(fn), "no module found to resolve names against")
    analysis = Analysis()
    _walk_function(fn, module, analysis, set())
    return analysis


def check_watches(fn, watches, stable=()) -> None:
    """Raise `ValueError` if `analyze(fn)` reads a component type that is
    named in neither `watches` nor `stable`.

    `watches` takes the same shape `Loop.rule(watches=...)` does. `stable`
    is the escape hatch a strict "reads subset of watches" check needs to
    be usable at all: run bare (`stable=()`) against `examples.cards`'s
    own thirteen rules and TWELVE of them raise, every one a false
    alarm -- `tag_affordable` reads `Purse`/`RiskProfile` without
    watching either, and `tests/test_examples_cards.py`'s own
    `test_watches_tag_affordable_wakes_on_listing_then_notices_a_purse_
    only_change` already PROVES that is safe, on purpose: both are
    singletons `install()` seeds once, before any tick runs, and never
    removed after, so they can never be the reason a rule was wrongly
    asleep -- only a type that could be ABSENT and then APPEAR later can
    cause that failure, and `watches` only ever needs to name the ones
    that gate whether the rule has anything to do at all (see
    `loopingrules.loop`'s own module note on `watches`). This module has
    no way to know, from a rule's source alone, which of its reads are
    that kind of permanent background fact and which are a real gap --
    that is exactly the "there is no way to catch this from here" this
    check exists to help with, not resolve unaided, so it asks the
    caller to say which types are stable the same way a rule author
    already says which types wake the rule up. Pass the domain's own
    install-time singletons (and anything else proven never absent once
    seeded) as `stable=`, and this check is precise rather than merely
    loud.
    """
    declared = (watches,) if isinstance(watches, type) else tuple(watches)
    known = (stable,) if isinstance(stable, type) else tuple(stable)
    missing = analyze(fn).reads - set(declared) - set(known)
    if missing:
        raise ValueError(
            "%s reads %s but watches=%r (stable=%r) does not name it -- "
            "the rule may go dormant while that is the only thing that "
            "changed" % (_qualname(fn), sorted(k.__name__ for k in missing),
                         declared, known))


class Report:
    """`component_map()`'s own result: for every component type seen,
    which rules (by qualified name) read it and which write it -- plus
    `opaque`, the rules this could not analyze at all, each with why.
    A type absent from `opaque` and absent from both `reads`/`writes`
    was never mentioned by any rule given; a rule name present in
    `opaque` is deliberately absent from `reads`/`writes` too, even for
    the part of it that WAS resolved before the point it wasn't -- a
    partial map is worse here than an honest "unknown.\""""

    def __init__(self) -> None:
        self.reads: Dict[type, Set[str]] = {}
        self.writes: Dict[type, Set[str]] = {}
        self.destroys: Set[str] = set()
        self.opaque: Dict[str, str] = {}

    def __repr__(self) -> str:
        return "Report(reads=%d kinds, writes=%d kinds, opaque=%r)" % (
            len(self.reads), len(self.writes), self.opaque)


def component_map(*functions) -> Report:
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
        for kind in analysis.reads:
            report.reads.setdefault(kind, set()).add(name)
        for kind in analysis.writes:
            report.writes.setdefault(kind, set()).add(name)
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

    def resolve_class(node):
        if isinstance(node, ast.Name) and isinstance(
                module.__dict__.get(node.id), type):
            handled_names.add(id(node))
            return module.__dict__[node.id]
        return None

    def resolve_kind_list(node):
        elts = node.elts if isinstance(node, (ast.Tuple, ast.List)) else [node]
        kinds = []
        for elt in elts:
            kind = resolve_class(elt)
            if kind is None:
                raise Opaque(_qualname(fn),
                             "cannot resolve a component type from %r" %
                             ast.unparse(elt))
            kinds.append(kind)
        return kinds

    def resolve_instance_class(node):
        # `Kind(...)` -- a freshly-built component. Anything else (a bare
        # variable, a comprehension, a starred value) cannot be traced to
        # a type without evaluating it, so it is Opaque, not guessed at.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return resolve_class(node.func)
        return None

    def handle_world_method(call, method):
        args = call.args
        if any(isinstance(a, ast.Starred) for a in args) or any(
                kw.arg is None for kw in call.keywords):
            raise Opaque(_qualname(fn),
                         "%s(...) called with a starred/**-argument -- "
                         "cannot enumerate its component types" % method)
        if method in READS:
            start = 1 if method == "get" else 0
            for a in args[start:]:
                kind = resolve_class(a)
                if kind is None:
                    raise Opaque(_qualname(fn),
                                 "%s(...) argument is not a literal "
                                 "component type: %r" % (method, ast.unparse(a)))
                analysis.reads.add(kind)
            for kw in call.keywords:
                if kw.arg == "without":
                    analysis.reads.update(resolve_kind_list(kw.value))
        elif method in EXISTENCE_READS:
            start = 1 if method in ("get_all", "has") else 0
            for a in args[start:]:
                kind = resolve_class(a)
                if kind is None:
                    raise Opaque(_qualname(fn),
                                 "%s(...) argument is not a literal "
                                 "component type: %r" % (method, ast.unparse(a)))
                analysis.reads.add(kind)
        elif method in WRITES_INSTANCE:
            start = 1 if method in ("attach", "replace") else 0
            for a in args[start:]:
                kind = resolve_instance_class(a)
                if kind is None:
                    raise Opaque(_qualname(fn),
                                 "%s(...) argument is not a freshly-built "
                                 "component (`Kind(...)`): %r" %
                                 (method, ast.unparse(a)))
                handled_names.add(id(a.func))
                analysis.writes.add(kind)
        elif method in WRITES_KIND:
            for a in args[1:]:
                kind = resolve_class(a)
                if kind is None:
                    raise Opaque(_qualname(fn),
                                 "detach(...) argument is not a bare "
                                 "component type: %r" % ast.unparse(a))
                analysis.writes.add(kind)
        elif method in WRITES_VALUE:
            if len(args) < 2:
                raise Opaque(_qualname(fn), "remove(...) missing its value")
            kind = resolve_instance_class(args[1])
            if kind is None:
                raise Opaque(_qualname(fn),
                             "remove(...) argument is not a freshly-built "
                             "component (`Kind(...)`): %r" % ast.unparse(args[1]))
            handled_names.add(id(args[1].func))
            analysis.writes.add(kind)
        elif method == "destroy":
            analysis.destroys = True
        elif method in ("entity", "learn", "revision"):
            pass
        else:
            raise Opaque(_qualname(fn),
                         "unknown world method %r -- this module's own "
                         "vocabulary of world methods may be out of date" %
                         method)

    def mark_world_args(call):
        for a in call.args:
            if isinstance(a, ast.Name) and a.id == world_name:
                handled_names.add(id(a))
        for kw in call.keywords:
            if isinstance(kw.value, ast.Name) and kw.value.id == world_name:
                handled_names.add(id(kw.value))

    def handle_helper_call(call):
        callee = module.__dict__.get(call.func.id)
        if callee is _CORE_REPLY:
            # reply(w, text, channel="user") -- always spawns a Reply,
            # per the README's own promise for this vocabulary. See the
            # module docstring's "Two named exceptions."
            analysis.writes.add(Reply)
            mark_world_args(call)
            return
        if callee is _CORE_PROPOSE:
            # propose(w, occasion, *components) -- always spawns a
            # Proposal(occasion), plus whatever components it was
            # handed, each of which must still be a literal `Kind(...)`
            # to be attributed -- the same discipline `spawn` itself
            # gets, not a free pass just because it arrived via propose.
            analysis.writes.add(Proposal)
            for a in call.args[2:]:
                kind = resolve_instance_class(a)
                if kind is None:
                    raise Opaque(_qualname(fn),
                                 "propose(...) component is not a "
                                 "freshly-built component (`Kind(...)`): "
                                 "%r" % ast.unparse(a))
                analysis.writes.add(kind)
            mark_world_args(call)
            return
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
