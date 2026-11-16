"""YAML component declarations -> `loopingrules.schema`.

The declared half of ADR-10, from text. A component is a name and its fields; a
component with no fields is a **tag**. Field kinds are the schema's own
(`singular`/`set`/`sequence`/`flag`); a field may be a reference (`ref:` names
the component it targets). An undeclared use is a `loopingrules.schema.Gap`.

::

    components:
      candidate: {worth: singular, name: singular}
      do: {what: singular, limit: singular, affordable: flag}
      excluded: {}          # a tag
"""

from __future__ import annotations

from loopingrules import schema


def parse(doc) -> schema.Schema:
    declared = schema.Schema()
    for name, body in (doc or {}).items():
        declared.declare(schema.Component(name, _fields(body)))
    return declared


def _fields(body):
    if not body:
        return ()
    if isinstance(body, dict) and "fields" in body:
        body = body["fields"] or {}
    out = []
    for name, spec in body.items():
        if spec is None:
            out.append(schema.Field(name))
        elif isinstance(spec, str):
            out.append(schema.Field(name, kind=spec))
        elif isinstance(spec, dict):
            out.append(schema.Field(name, kind=spec.get("kind", "singular"),
                                    ref=spec.get("ref")))
        else:
            raise ValueError("field %r: expected a kind, a mapping, or nothing, "
                             "not %r" % (name, spec))
    return tuple(out)
