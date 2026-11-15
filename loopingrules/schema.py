"""The component schema: the *declared* half of ADR-10.

A **component** is a declared schema -- a name (model-qualified -- `market.purse`
and `cards.purse` never collide) and a set of **fields**. A component with no
fields is a **tag**. Data lives in named components on an entity
(`entity -> {component -> {field -> value}}`); the World stores it but does not
enforce this declaration (it enforces shape, and nothing else -- see
`loopingrules.world`). The declaration is the artifact `analyze`, the linter and
the forge check a USE against: a field used but not declared is a **blocking
gap** (D8's read-without-writer discipline), the same way an unmapped clause is.

This module is deliberately tiny and declarative. It is not a type system
(`PRINCIPLES.md`: values are primitives only, semantics lives in the name): a
`Field` names a `kind` (the verbs it takes) and, if it is a reference, the
component it targets -- never a value type.
"""

from __future__ import annotations

from dataclasses import dataclass, field as _dc_field
from typing import Dict, Optional, Tuple

KINDS = ("singular", "set", "sequence", "flag")


@dataclass(frozen=True)
class Field:
    """One field of a component: its name, its kind, and -- if it is a
    reference -- the component it targets. `ref` is the *component* name, not a
    value type; a field holds a scalar, a reference, or a flat list, and never a
    structured value."""

    name: str
    kind: str = "singular"
    ref: Optional[str] = None

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError("a field kind is one of %r, not %r"
                             % (KINDS, self.kind))
        if self.kind == "flag" and self.ref is not None:
            raise ValueError("a flag field cannot be a reference: %r" % self.name)


@dataclass(frozen=True)
class Component:
    """A declared component: a (model-qualified) name and its fields, in
    declaration order. A component with no fields is a tag."""

    name: str
    fields: Tuple[Field, ...] = ()

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError("component %r has no field %r" % (self.name, name))

    def has(self, name: str) -> bool:
        return any(f.name == name for f in self.fields)

    @property
    def is_tag(self) -> bool:
        return not self.fields


@dataclass
class Schema:
    """A set of component declarations, by name. `slot(component, field)`
    is the check a use is measured against: an undeclared component or field is
    a `Gap`, refused rather than guessed."""

    components: Dict[str, Component] = _dc_field(default_factory=dict)

    def declare(self, component: Component) -> Component:
        if component.name in self.components:
            raise ValueError("component %r is already declared" % component.name)
        self.components[component.name] = component
        return component

    def component(self, name: str) -> Component:
        try:
            return self.components[name]
        except KeyError:
            raise Gap("component %r is not declared" % name) from None

    def slot(self, component: str, field: Optional[str]) -> Tuple[str, Optional[str]]:
        """Validate a `(component, field)` slot against the declarations and
        return it. `field=None` asks only that the component is declared (a tag,
        or a component-only read). An undeclared component or field is a
        `Gap` -- the blocking gap D8 names, never a silent pass."""
        declared = self.component(component)
        if field is not None and not declared.has(field):
            raise Gap("field %r is not declared on component %r"
                      % (field, component))
        return (component, field)


class Gap(Exception):
    """A use that names a component or field the schema does not declare. The
    forge's read-without-writer gap, at the schema grain: refusible, never
    guessed (ADR-1, D8)."""


def slot_str(slot: Tuple[str, Optional[str]]) -> str:
    """A slot as ONE storable string -- `"trader.cash"`, or `"done"` for a
    component-level slot. The store cannot hold a tuple (`_lower` refuses a
    structured value), so a slot that has to be written down -- a `RuleCard`'s
    `reads`, say -- is encoded this way rather than as a pair."""
    component, field = slot
    return component if field is None else "%s.%s" % (component, field)


def parse_slot(text: str) -> Tuple[str, Optional[str]]:
    """The inverse of `slot_str` -- splitting on the LAST dot, so a
    model-qualified component name (`market.purse.cash`) survives."""
    if "." not in text:
        return (text, None)
    component, _dot, field = text.rpartition(".")
    return (component, field)
