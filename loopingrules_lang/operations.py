"""YAML operations -> Python rule functions.

The authoring half of ADR-11: an **operation** is a capability -- a guard and a
set of effects over declared components -- and the engine **applies** it. This
module compiles the textual form to a plain ``def operation(w)`` the existing
``Loop`` runs (ADR-7's "render Python first"; the IR fold comes later).

The operator set is deliberately **closed and small**, grown only at the operation
that collides (ADR-2's discipline). An operation is::

    name:    the operation's name (model-qualified at install)
    when:    op-level conditions over SINGLETON slots -- false => do nothing
    match:   {component, fields?, without?} -- the entities it iterates
    reduce:  {op: argmin|argmax, field, unique?} -- the one winner among the
             matches; `unique: true` returns NO winner on a tie (abstain)
    effect:  an ordered list of verbs

Conditions are ``{slot|field, op, value?}`` with op one of
present/absent/eq/ne/gt/ge/lt/le. ``field:`` names a field of the current match;
``slot:`` names a singleton slot ``component.field``. A VALUE is a literal, or
``{field: n}``, ``{slot: c.f}``, or ``{sub|add|mul|div: [value, value]}``.

Effects: ``set``/``unmark``/``mark``/``add``/``remove``/``spawn``/``destroy``/
``clear``/``emit``, each with an optional ``target:`` (``match`` -- the default,
``winner``, ``losers``, or ``{component: c}`` for the oldest entity carrying it)
and an optional per-target ``when:``. (``target:``, not ``on:`` -- YAML 1.1
resolves a bare ``on`` key to boolean ``True``.) ``emit: {request: <capability>,
with: {<arg>: <value>}}`` writes the capability's OWN request component
(``<capability>_request``) -- named, schema-checked arguments the harness answers
between ticks (ADR-11 §3).

Rendered operations are **closures**: ``analyze`` cannot read their source (the
calls use bound variables), so ``Loop.rule`` gets ``Opaque`` and would run them
ungated -- the harness therefore sets the gate itself from ``match.component``
(the compiler knows it). ``reflect.identity`` hashes SOURCE, so generated
operations share a hash today; harmless until a control channel names one (the
known ``rule_hash`` collision).
"""

from __future__ import annotations

import collections

from loopingrules import schema

Operation = collections.namedtuple("Operation", "name fn gate used")

_VERBS = ("set", "mark", "unmark", "add", "remove", "spawn", "destroy", "clear",
          "emit")
_ARITH = (("sub", lambda a, b: a - b), ("add", lambda a, b: a + b),
          ("mul", lambda a, b: a * b), ("div", lambda a, b: a / b))


class _Missing:
    __slots__ = ()


_MISSING = _Missing()


class _Match:
    """One matched entity and the fields the operation bound for it."""

    __slots__ = ("entity", "fields")

    def __init__(self, entity, fields):
        self.entity = entity
        self.fields = fields


# -- reading ---------------------------------------------------------------

def _singleton(w, text):
    """`do.what` -> the value on the oldest entity carrying it (or `_MISSING`);
    a bare `component` -> `True` if any entity carries it."""
    component, field = schema.parse_slot(text)
    if field is None:
        return True if w.populated(component) else _MISSING
    row = w.first(component, field)
    return _MISSING if row is None else row[1]


def _value(w, row, spec):
    """Evaluate a VALUE spec in the context of `row` (the current match)."""
    if isinstance(spec, dict):
        if "field" in spec:
            return _MISSING if row is None else row.fields.get(spec["field"], _MISSING)
        if "slot" in spec:
            return _singleton(w, spec["slot"])
        for name, fn in _ARITH:
            if name in spec:
                args = spec[name]
                a, b = _value(w, row, args[0]), _value(w, row, args[1])
                return _MISSING if a is _MISSING or b is _MISSING else fn(a, b)
        raise ValueError("unknown value spec %r" % (spec,))
    return spec


def _compare(op, left, right):
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if right is _MISSING:
        return False
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    raise ValueError("unknown condition op %r" % (op,))


def _cond(w, row, cond):
    op = cond["op"]
    if "field" in cond:
        left = _MISSING if row is None else row.fields.get(cond["field"], _MISSING)
    elif "slot" in cond:
        left = _singleton(w, cond["slot"])
    else:
        raise ValueError("a condition needs `field:` or `slot:`")
    if op == "present":
        return left is not _MISSING
    if op == "absent":
        return left is _MISSING
    if left is _MISSING:
        return False
    return _compare(op, left, _value(w, row, cond.get("value")))


def _all_true(w, row, conditions):
    for cond in conditions:
        if not _cond(w, row, cond):
            return False
    return True


# -- matching and reducing --------------------------------------------------

def _collect(w, match):
    if match is None:
        return []
    component = match["component"]
    fields = tuple(match.get("fields") or ())
    without = tuple(match.get("without") or ())
    out = []
    for row in w.each(component, *fields, without=without):
        out.append(_Match(row[0], dict(zip(fields, row[1:]))))
    return out


def _reduce(w, reduce, matches):
    if reduce is None:
        return None
    op = reduce["op"]
    if op not in ("argmin", "argmax"):
        raise ValueError("reduce op is argmin/argmax, not %r" % (op,))
    field = reduce["field"]
    best = None
    ties = 0
    for match in matches:
        if field not in match.fields:
            continue
        if best is None:
            best, ties = match, 1
            continue
        value, best_value = match.fields[field], best.fields[field]
        if (value < best_value) if op == "argmin" else (value > best_value):
            best, ties = match, 1
        elif value == best_value:
            ties += 1
    if reduce.get("unique") and ties > 1:
        return None          # a TIE has no winner -- abstain, do not pick arbitrarily
    return best


# -- applying ---------------------------------------------------------------

def _targets(w, matches, winner, payload):
    target = payload.get("target") if isinstance(payload, dict) else None
    if target == "winner":
        return [(winner, winner.entity)] if winner is not None else []
    if target == "losers":
        return [(match, match.entity) for match in matches if match is not winner]
    if isinstance(target, dict) and "component" in target:
        row = w.first(target["component"])
        return [(None, row[0])] if row is not None else []
    return [(match, match.entity) for match in matches]


def _do(w, verb, payload, entity, row):
    if verb in ("mark", "unmark", "clear"):
        component = payload if isinstance(payload, str) else payload["component"]
        if verb == "mark":
            w.mark(entity, component)
        else:
            w.unmark(entity, component)
    elif verb == "set":
        w.set(entity, payload["component"], payload["field"],
              _value(w, row, payload.get("value")))
    elif verb == "add":
        w.add(entity, payload["component"], payload["field"],
              _value(w, row, payload.get("value")))
    elif verb == "remove":
        w.remove(entity, payload["component"], payload["field"],
                 _value(w, row, payload.get("value")))


def _apply_effect(w, matches, winner, effect):
    verb = None
    for candidate in _VERBS:
        if candidate in effect:
            verb = candidate
            break
    if verb is None:
        raise ValueError("an effect needs one of %r" % (_VERBS,))
    payload = effect[verb]
    if verb == "spawn":
        component = payload if isinstance(payload, str) else payload["component"]
        w.mark(w.spawn(), component)
        return
    if verb == "emit":
        capability = payload["request"]
        component = capability + "_request"
        for row, entity in _targets(w, matches, winner, payload):
            for name, spec in (payload.get("with") or {}).items():
                w.set(entity, component, name, _value(w, row, spec))
        return
    if verb == "clear":
        # Retract the role from EVERY holder except the winner -- not only from the
        # current matches. Otherwise a role left on a candidate that later became
        # EXCLUDED (so is no longer matched) would survive, and two entities would
        # carry `chosen`.
        component = payload if isinstance(payload, str) else payload["component"]
        winner_entity = winner.entity if winner is not None else None
        for entity, in w.each(component):
            if entity != winner_entity:
                w.unmark(entity, component)
        return
    for row, entity in _targets(w, matches, winner, payload):
        if "when" in effect and not _all_true(w, row, effect["when"]):
            continue
        if verb == "destroy":
            w.destroy(entity)
        else:
            _do(w, verb, payload, entity, row)


# -- what an operation names (for a declared-schema check) ------------------

def _used_components(node):
    """Every component name an operation mentions -- so an undeclared one is a
    `loopingrules.schema.Gap` at load time, not a silent no-op at run time."""
    found = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "component" and isinstance(value, str):
                found.add(value)
            elif key == "slot" and isinstance(value, str):
                found.add(schema.parse_slot(value)[0])
            elif key == "without":
                found.update(v for v in (value or ()) if isinstance(v, str))
            elif key in ("mark", "unmark", "clear", "spawn") and isinstance(value, str):
                found.add(value)
            elif key == "emit":
                request = value.get("request") if isinstance(value, dict) else None
                if isinstance(request, str):
                    # the request component is the CAPABILITY's own vocabulary
                    found.add(request + "_request")
                found |= _used_components(value)
            else:
                found |= _used_components(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            found |= _used_components(item)
    return found


# -- the compiler -----------------------------------------------------------

def parse(specs):
    return [compile_operation(spec) for spec in specs]


def compile_operation(spec):
    name = spec["name"]
    when = tuple(spec.get("when") or ())
    match = spec.get("match")
    reduce = spec.get("reduce")
    effects = tuple(spec.get("effect") or ())

    def operation(w):
        if when and not _all_true(w, None, when):
            return
        matches = _collect(w, match)
        winner = _reduce(w, reduce, matches)
        for effect in effects:
            _apply_effect(w, matches, winner, effect)

    operation.__name__ = name
    operation.__qualname__ = name
    return Operation(name=name, fn=operation, gate=_gate_components(spec),
                     used=frozenset(_used_components(spec)))


def _gate_components(spec) -> tuple:
    """The components whose presence should wake the operation: the op-level
    `when` slots AND the match component. Gating on `match.component` alone would
    put a choose operation to sleep until its subject exists, so it could not mark
    its directive resolved before a tool had loaded the subject."""
    names = set()
    for cond in spec.get("when") or ():
        slot = cond.get("slot")
        if isinstance(slot, str):
            names.add(schema.parse_slot(slot)[0])
    match = spec.get("match")
    if match:
        names.add(match["component"])
    return tuple(sorted(names))
