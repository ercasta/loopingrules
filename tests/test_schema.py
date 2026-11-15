"""The component schema (ADR-10): components are declared; a use is checked
against the declaration, and an undeclared component or field is a Gap.
"""

from __future__ import annotations

import pytest

from loopingrules.schema import Component, Field, Gap, Schema


def _schema():
    s = Schema()
    s.declare(Component("listing", (Field("card", ref="card"),
                                    Field("city", ref="city"),
                                    Field("price"),
                                    Field("tags", kind="set"))))
    s.declare(Component("card", (Field("name"), Field("value"))))
    s.declare(Component("done"))                       # a tag
    return s


def test_a_declared_slot_validates():
    assert _schema().slot("listing", "price") == ("listing", "price")


def test_a_component_only_slot_validates():
    assert _schema().slot("done", None) == ("done", None)


def test_an_undeclared_component_is_a_gap():
    with pytest.raises(Gap):
        _schema().slot("purse", "cash")


def test_an_undeclared_field_is_a_gap():
    with pytest.raises(Gap):
        _schema().slot("listing", "cash")


def test_declaring_a_component_twice_is_an_error():
    s = _schema()
    with pytest.raises(ValueError):
        s.declare(Component("done"))


def test_a_field_kind_is_checked():
    with pytest.raises(ValueError):
        Field("x", kind="whatever")


def test_a_flag_cannot_be_a_reference():
    with pytest.raises(ValueError):
        Field("x", kind="flag", ref="card")


def test_a_component_with_no_fields_is_a_tag():
    assert Component("done").is_tag
    assert not Component("listing", (Field("price"),)).is_tag
