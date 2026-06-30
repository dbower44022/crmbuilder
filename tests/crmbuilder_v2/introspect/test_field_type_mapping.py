"""EspoCRM -> engine-neutral field-type mapping — PI-374 (REQ-435/436/437)."""

from __future__ import annotations

from crmbuilder_v2.introspect.reconcile import (
    _audited_field_attrs,
    _map_field_type,
    is_unmapped_field_type,
)


def test_foreign_maps_to_distinct_foreign_kind():
    """REQ-435: an EspoCRM 'foreign' field maps to neutral 'foreign', not 'derived'
    (which would surface as text)."""
    assert _map_field_type("foreign") == "foreign"
    assert _audited_field_attrs({"type": "foreign"})["field_type"] == "foreign"


def test_formula_still_maps_to_derived():
    """A formula field stays 'derived' — only 'foreign' was split out."""
    assert _map_field_type("formula") == "derived"


def test_unrecognised_type_falls_back_to_text_but_is_flagged():
    """REQ-437: an unmapped source kind still records (as text) but is reported
    via is_unmapped_field_type so it can be surfaced for review."""
    assert _map_field_type("someNewEspoType") == "text"
    assert is_unmapped_field_type("someNewEspoType") is True
    # A recognised kind is not flagged.
    assert is_unmapped_field_type("foreign") is False
    assert is_unmapped_field_type("varchar") is False


def test_foreign_field_attrs_do_not_assume_text_result_type():
    """REQ-436: the audit no longer assumes a foreign field's mirrored value is
    text — _audited_field_attrs reports the kind as foreign and carries no
    hardcoded result type (the create path leaves it unset until known)."""
    attrs = _audited_field_attrs({"type": "foreign"})
    assert attrs["field_type"] == "foreign"
    assert "field_derived_result_type" not in attrs
