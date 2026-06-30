"""Audit capture of enum/multi_enum field option sets — REQ-442 (PI-381).

Unit tests for the introspect-layer helpers that read an EspoCRM enum field's
option list and decide whether it deviates from the canonical design.
"""

from __future__ import annotations

from crmbuilder_v2.introspect.reconcile import (
    _audited_field_attrs,
    _audited_option_set,
    _field_override,
)


def test_audited_option_set_reads_values_and_translated_labels():
    meta = {
        "type": "enum",
        "options": ["open", "closed"],
        "translatedOptions": {"open": "Open", "closed": "Closed out"},
    }
    out = _audited_option_set(meta)
    assert out == [
        {"option_value": "open", "option_label": "Open", "option_order": 0},
        {"option_value": "closed", "option_label": "Closed out", "option_order": 1},
    ]


def test_audited_option_set_label_none_when_untranslated():
    meta = {"type": "enum", "options": ["a"], "translatedOptions": {}}
    assert _audited_option_set(meta) == [
        {"option_value": "a", "option_label": None, "option_order": 0}
    ]


def test_audited_field_attrs_carries_options_for_enum_and_multienum():
    enum_meta = {"type": "enum", "options": ["a"], "translatedOptions": {"a": "A"}}
    assert "field_options" in _audited_field_attrs(enum_meta)
    multi_meta = {"type": "multiEnum", "options": ["x", "y"]}
    attrs = _audited_field_attrs(multi_meta)
    assert attrs["field_type"] == "multi_enum"
    assert [o["option_value"] for o in attrs["field_options"]] == ["x", "y"]


def test_audited_field_attrs_omits_options_for_non_enum():
    assert "field_options" not in _audited_field_attrs({"type": "varchar"})


def test_field_override_records_option_difference():
    canonical = {
        "field_type": "enum",
        "field_options": [{"option_value": "a", "option_label": "A"}],
    }
    audited = _audited_field_attrs(
        {"type": "enum", "options": ["a", "b"], "translatedOptions": {"a": "A"}}
    )
    override = _field_override(canonical, audited)
    assert "field_options" in override
    assert [o["option_value"] for o in override["field_options"]] == ["a", "b"]


def test_field_override_no_record_when_options_match_order_insensitive():
    canonical = {
        "field_type": "enum",
        "field_options": [
            {"option_value": "a", "option_label": "A"},
            {"option_value": "b", "option_label": "B"},
        ],
    }
    audited = _audited_field_attrs(
        {"type": "enum", "options": ["b", "a"],
         "translatedOptions": {"a": "A", "b": "B"}}
    )
    assert "field_options" not in _field_override(canonical, audited)


def test_field_override_records_label_only_drift():
    canonical = {
        "field_type": "enum",
        "field_options": [{"option_value": "a", "option_label": "Apple"}],
    }
    audited = _audited_field_attrs(
        {"type": "enum", "options": ["a"], "translatedOptions": {"a": "Apricot"}}
    )
    assert "field_options" in _field_override(canonical, audited)
