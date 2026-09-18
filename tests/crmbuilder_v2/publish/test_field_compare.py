"""Tests for comparing a declared field against the live one
(REQ-609 / PI-522).
"""

from __future__ import annotations

from crmbuilder_v2.publish.field_compare import compare_field


def test_a_field_that_matches_needs_nothing_written() -> None:
    declared = {"type": "varchar", "label": "Region", "maxLength": 100}
    live = {"type": "varchar", "label": "Region", "maxLength": 100}
    result = compare_field(declared, live)
    assert result.matches
    assert result.differences == []


def test_a_differing_property_is_named_with_both_values() -> None:
    result = compare_field(
        {"type": "varchar", "label": "Region"},
        {"type": "varchar", "label": "Area"},
    )
    assert not result.matches
    assert result.differences == ["label"]
    assert "'Region'" in result.detail_text
    assert "'Area'" in result.detail_text


def test_a_different_kind_is_a_conflict_not_an_update() -> None:
    """Changing a field's type on a live instance discards its data."""
    result = compare_field(
        {"type": "enum", "label": "Stage"}, {"type": "varchar", "label": "Stage"}
    )
    assert result.kind_conflict
    assert not result.matches
    assert result.differences == ["type"]
    assert "discards its data" in result.detail_text


def test_a_kind_conflict_stops_the_comparison_there() -> None:
    """Nothing else is worth saying about a field that must be left alone."""
    result = compare_field(
        {"type": "enum", "label": "Stage", "required": True},
        {"type": "varchar", "label": "Something else", "required": False},
    )
    assert result.differences == ["type"]


# --- lists of allowed values ------------------------------------------------


def test_missing_values_are_named() -> None:
    result = compare_field(
        {"type": "enum", "options": ["Mentor", "Mentee", "Staff"]},
        {"type": "enum", "options": ["Staff"]},
    )
    assert result.differences == ["options"]
    assert "missing from the instance: [Mentor, Mentee]" in result.detail_text


def test_extra_values_on_the_instance_are_named() -> None:
    result = compare_field(
        {"type": "enum", "options": ["Mentor"]},
        {"type": "enum", "options": ["Mentor", "Retired"]},
    )
    assert "on the instance but not declared: [Retired]" in result.detail_text


def test_the_same_values_in_a_different_order_still_differ() -> None:
    """The platform preserves the order, so the order is part of the design."""
    result = compare_field(
        {"type": "enum", "options": ["Mentor", "Mentee"]},
        {"type": "enum", "options": ["Mentee", "Mentor"]},
    )
    assert result.differences == ["options"]
    assert "different order" in result.detail_text


def test_a_non_list_value_does_not_break_the_breakdown() -> None:
    result = compare_field(
        {"type": "enum", "options": ["Mentor"]}, {"type": "enum", "options": None}
    )
    assert result.differences == ["options"]


# --- what could not be checked ----------------------------------------------


def test_a_property_the_design_does_not_declare_is_unknown_not_matching() -> None:
    result = compare_field(
        {"type": "varchar", "label": "Region"},
        {"type": "varchar", "label": "Region", "required": True},
    )
    assert result.matches
    assert not result.conclusive
    assert [u.property for u in result.unknowns if u.property == "required"]
    assert "the design does not declare it" in result.unknowns[0].message


def test_a_property_the_instance_does_not_report_is_unknown() -> None:
    result = compare_field(
        {"type": "varchar", "label": "Region", "audited": True},
        {"type": "varchar", "label": "Region"},
    )
    unknown = [u for u in result.unknowns if u.property == "audited"]
    assert unknown and "the instance did not report it" in unknown[0].message


def test_matching_and_conclusive_are_different_answers() -> None:
    """The distinction is the point: "nothing seen to differ" is not
    "nothing differs" when things could not be seen."""
    fully_known = compare_field(
        {
            "type": "varchar",
            "label": "Region",
            "required": False,
            "default": None,
            "readOnly": False,
            "audited": False,
            "min": None,
            "max": None,
            "maxLength": 100,
        },
        {
            "type": "varchar",
            "label": "Region",
            "required": False,
            "readOnly": False,
            "audited": False,
            "maxLength": 100,
        },
    )
    # ``default``, ``min`` and ``max`` are undeclared, so still not conclusive.
    assert fully_known.matches and not fully_known.conclusive
    assert {u.property for u in fully_known.unknowns} == {"default", "min", "max"}


def test_an_unknown_is_never_reported_as_a_difference() -> None:
    result = compare_field({"type": "varchar"}, {"type": "varchar"})
    assert result.differences == []
    assert result.unknowns


# --- per-kind properties ----------------------------------------------------


def test_value_list_properties_are_compared_only_for_those_kinds() -> None:
    result = compare_field(
        {"type": "varchar", "label": "Region", "options": ["A"]},
        {"type": "varchar", "label": "Region"},
    )
    assert "options" not in result.differences
    assert "options" not in {u.property for u in result.unknowns}


def test_a_mirrored_field_compares_its_link_and_the_field_it_mirrors() -> None:
    result = compare_field(
        {"type": "foreign", "link": "account", "field": "name"},
        {"type": "foreign", "link": "account", "field": "website"},
    )
    assert result.differences == ["field"]
    assert "'name'" in result.detail_text
