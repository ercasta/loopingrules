"""Circuit specs as JSON-shaped data -- the serializer `share.py`'s own
docstring said `circuits.py` needed and could not use `share.py` for.

    data = specs.dump_specs({"rescan": do_rescan_spec})
    problems, loaded = specs.load_specs(data, specs.registry_of(RescanWanted))

A spec is a tree of frozen dataclasses (`circuits.Add`, `circuits.Self`,
...) whose leaves include component CLASSES (`Self(RescanWanted,
"folder")`, `ActionCircuit(require=(RescanWanted,), ...)`). Neither
`World.attach` nor `save`/`share` can hold one: a component field may
not be a `type`. So a spec is not a component, and this module is not a
second `save` -- it is a reader/writer for exactly this closed catalog.

## What the file gets to say, and what it does not

- **Which spec shapes exist is fixed here**, by name, in `_CATALOG`. A
  `{"$spec": "Add", ...}` node resolves through that dict; nothing is
  ever looked up with `getattr` or `importlib` from a name in the file.
  A shape `circuits.py` grows later is not loadable until it is added
  here -- `tests/test_specs.py` fails when the two drift.
- **Which component classes a spec may name is the CALLER's**, through
  `registry` (`{"module:Qualname": class}`), the same policy and the same
  reason as `share.load_pack`: resolving a dotted name out of a
  stranger's file is an import primitive. A name not in the registry
  refuses that whole spec.
- **A tool name (`Call`) is data, not authority.** Loading a spec never
  checks it against anything; `circuits.compile_circuit(spec, tools=...)`
  still raises `KeyError` for a `Call` naming a tool the compiling
  caller did not register, and that remains the one place that decides.
- **`Const.value` is plain data** (None/bool/int/float/str, or a
  tuple/list of them). A class or a spec node there is refused.

Tuples are written `{"$tuple": [...]}` and lists as JSON lists, the same
convention as `save.py`, so a frozen spec round-trips equal to the
original and stays hashable.

Nesting deeper than `MAX_DEPTH` is refused rather than left to blow the
interpreter's recursion limit on a hostile file.
"""

from __future__ import annotations

import dataclasses

from . import circuits
from .save import _name_of

VERSION = 1
MAX_DEPTH = 64

_SPEC_CLASSES = (
    circuits.Self, circuits.Via, circuits.World, circuits.TheEntity,
    circuits.SelfId, circuits.Const, circuits.Add, circuits.Sub,
    circuits.Mul, circuits.Min, circuits.Max, circuits.SafeDiv,
    circuits.Coalesce, circuits.If, circuits.Lower, circuits.Split,
    circuits.At, circuits.Len, circuits.ParseInt, circuits.FindBy,
    circuits.Le, circuits.Lt, circuits.Ge, circuits.Gt, circuits.Eq,
    circuits.Exists, circuits.HasSelf, circuits.And, circuits.Or,
    circuits.Not, circuits.Any, circuits.Forall, circuits.Children,
    circuits.Count, circuits.Format, circuits.Join, circuits.Optional,
    circuits.JoinStrings, circuits.TagCircuit, circuits.ValueCircuit,
    circuits.ReplaceAt, circuits.Destroy, circuits.Spawn, circuits.Call,
    circuits.ActionCircuit,
)
_CATALOG = {cls.__name__: cls for cls in _SPEC_CLASSES}

_RULE_SHAPES = (circuits.TagCircuit, circuits.ValueCircuit, circuits.ActionCircuit)


class SpecError(ValueError):
    """A spec this module will not write or cannot safely read."""


def registry_of(*kinds) -> dict:
    """`{"module:Qualname": class}` for `kinds` -- the shape `load_specs`
    and `decode_spec` want, so a caller does not spell names by hand."""
    return {_name_of(kind): kind for kind in kinds}


# -- writing --------------------------------------------------------------

def _encode(value, depth, in_const):
    if depth > MAX_DEPTH:
        raise SpecError("spec nested deeper than %d" % MAX_DEPTH)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, type):
        if in_const:
            raise SpecError("Const.value cannot hold a class: %r" % (value,))
        return {"$class": _name_of(value)}
    if isinstance(value, tuple):
        return {"$tuple": [_encode(v, depth + 1, in_const) for v in value]}
    if isinstance(value, list):
        return [_encode(v, depth + 1, in_const) for v in value]
    cls = type(value)
    if _CATALOG.get(cls.__name__) is cls:
        if in_const:
            raise SpecError("Const.value cannot hold a spec node: %r" % (value,))
        out = {"$spec": cls.__name__}
        for f in dataclasses.fields(cls):
            out[f.name] = _encode(getattr(value, f.name), depth + 1,
                                  in_const or (cls is circuits.Const))
        return out
    raise SpecError("not a spec value: %r" % (value,))


def encode_spec(spec) -> dict:
    """One spec as a JSON-shaped dict. Raises `SpecError` for anything
    that is not the closed catalog (a lambda, an instance of some other
    class, a class inside `Const.value`)."""
    if not isinstance(spec, tuple(_SPEC_CLASSES)):
        raise SpecError("not a spec: %r" % (spec,))
    return _encode(spec, 0, False)


def dump_specs(specs: dict) -> dict:
    """`{name: spec}` as one JSON-shaped pack, header included. Only the
    three rule shapes (`TagCircuit`/`ValueCircuit`/`ActionCircuit`) may be
    top-level -- what `circuits.compile_circuit` accepts."""
    out = {}
    for name, spec in specs.items():
        if not isinstance(name, str):
            raise SpecError("spec name must be a string: %r" % (name,))
        if not isinstance(spec, _RULE_SHAPES):
            raise SpecError("%s: %s is not a rule shape" % (name, type(spec).__name__))
        out[name] = encode_spec(spec)
    return {"version": VERSION, "specs": out}


# -- reading --------------------------------------------------------------

def _decode(data, registry, depth, in_const):
    if depth > MAX_DEPTH:
        raise SpecError("spec nested deeper than %d" % MAX_DEPTH)
    if data is None or isinstance(data, (bool, int, float, str)):
        return data
    if isinstance(data, list):
        return [_decode(v, registry, depth + 1, in_const) for v in data]
    if not isinstance(data, dict):
        raise SpecError("unexpected %s in a spec" % type(data).__name__)
    if "$tuple" in data:
        if set(data) != {"$tuple"} or not isinstance(data["$tuple"], list):
            raise SpecError("malformed $tuple node")
        return tuple(_decode(v, registry, depth + 1, in_const) for v in data["$tuple"])
    if "$class" in data:
        if set(data) != {"$class"} or not isinstance(data["$class"], str):
            raise SpecError("malformed $class node")
        if in_const:
            raise SpecError("Const.value cannot hold a class")
        kind = registry.get(data["$class"])
        if kind is None:
            raise SpecError("%s: not in the importing registry" % data["$class"])
        if not isinstance(kind, type):
            raise SpecError("%s: registry value is not a class" % data["$class"])
        return kind
    if "$spec" in data:
        if in_const:
            raise SpecError("Const.value cannot hold a spec node")
        name = data["$spec"]
        cls = _CATALOG.get(name) if isinstance(name, str) else None
        if cls is None:
            raise SpecError("unknown spec shape %r" % (name,))
        fields = {f.name: f for f in dataclasses.fields(cls)}
        given = {k: v for k, v in data.items() if k != "$spec"}
        extra = set(given) - set(fields)
        if extra:
            raise SpecError("%s: unknown field(s) %s" % (name, sorted(extra)))
        missing = [n for n, f in fields.items()
                   if n not in given and f.default is dataclasses.MISSING
                   and f.default_factory is dataclasses.MISSING]
        if missing:
            raise SpecError("%s: missing field(s) %s" % (name, missing))
        kwargs = {k: _decode(v, registry, depth + 1, in_const or cls is circuits.Const)
                  for k, v in given.items()}
        return cls(**kwargs)
    raise SpecError("object with none of $spec/$class/$tuple in a spec")


def decode_spec(data, registry: dict):
    """One spec back from `encode_spec`'s shape. Raises `SpecError` for an
    unknown shape, a class name not in `registry`, a field that does not
    belong, a missing required field, or nesting past `MAX_DEPTH`."""
    try:
        spec = _decode(data, registry, 0, False)
    except RecursionError:
        raise SpecError("spec nested too deeply")
    if not isinstance(spec, tuple(_SPEC_CLASSES)):
        raise SpecError("top level is not a spec")
    return spec


def load_specs(data: dict, registry: dict):
    """`dump_specs`' pack -> `(problems, {name: spec})`. A spec that
    cannot be read safely is skipped and named in `problems`, the same
    policy as `share.load_pack`, never half-loaded. A wrong-version or
    malformed pack yields no specs and one problem."""
    if not isinstance(data, dict) or data.get("version") != VERSION:
        got = data.get("version") if isinstance(data, dict) else None
        return ["pack is version %r, this module is version %d" % (got, VERSION)], {}
    raw = data.get("specs")
    if not isinstance(raw, dict):
        return ["pack has no 'specs' mapping"], {}
    problems, loaded = [], {}
    for name, body in raw.items():
        try:
            spec = decode_spec(body, registry)
            if not isinstance(spec, _RULE_SHAPES):
                raise SpecError("%s is not a rule shape" % type(spec).__name__)
        except SpecError as e:
            problems.append("%s: %s -- skipped" % (name, e))
            continue
        loaded[name] = spec
    return problems, loaded
