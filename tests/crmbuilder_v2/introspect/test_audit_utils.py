"""Unit tests for ``crmbuilder_v2.introspect.audit_utils`` (PI-187)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.introspect.audit_utils import (
    NATIVE_BASE_FIELDS,
    NATIVE_COMPANY_FIELDS,
    NATIVE_ENTITIES,
    NATIVE_EVENT_FIELDS,
    NATIVE_PERSON_FIELDS,
    SYSTEM_FIELDS,
    EntityClass,
    FieldClass,
    classify_entity,
    classify_field,
    get_native_fields_for_type,
    get_yaml_entity_name,
    strip_entity_c_prefix,
    strip_field_c_prefix,
)

# --- strip_field_c_prefix ---------------------------------------------------


@pytest.mark.parametrize(
    ("api_name", "expected"),
    [
        ("cContactType", "contactType"),
        ("cMentorStatus", "mentorStatus"),
        ("contactType", "contactType"),  # already natural
        ("name", "name"),  # native scalar, untouched
        ("c", "c"),  # too short
        ("created", "created"),  # 'c' not followed by uppercase
    ],
)
def test_strip_field_c_prefix(api_name: str, expected: str) -> None:
    assert strip_field_c_prefix(api_name) == expected


# --- strip_entity_c_prefix / get_yaml_entity_name ---------------------------


@pytest.mark.parametrize(
    ("api_name", "expected"),
    [
        ("CEngagement", "Engagement"),
        ("CSession", "Session"),
        ("CWorkshopAttendance", "WorkshopAttendance"),
        ("Contact", "Contact"),  # native, untouched
        ("Account", "Account"),  # native, untouched
        ("CXyz", "Xyz"),  # C + uppercase pattern -> stripped
        ("Custom", "Custom"),  # C + lowercase second char -> untouched
        ("Country", "Country"),  # C + lowercase second char -> untouched
        ("Case", "Case"),  # native, untouched despite C-uppercase shape
    ],
)
def test_strip_entity_c_prefix(api_name: str, expected: str) -> None:
    assert strip_entity_c_prefix(api_name) == expected


def test_strip_entity_c_prefix_non_pattern_unchanged() -> None:
    # Second char not uppercase -> unchanged.
    assert strip_entity_c_prefix("Engagement") == "Engagement"
    assert strip_entity_c_prefix("") == ""


def test_get_yaml_entity_name_delegates() -> None:
    assert get_yaml_entity_name("CEngagement") == "Engagement"
    assert get_yaml_entity_name("Contact") == "Contact"


# --- classify_entity --------------------------------------------------------


def test_classify_entity_system_scope() -> None:
    # In the system-scope denylist regardless of meta.
    assert (
        classify_entity("EmailTemplate", {"entity": True, "customizable": True})
        == EntityClass.SYSTEM
    )


def test_classify_entity_custom() -> None:
    meta = {"entity": True, "customizable": True, "isCustom": True}
    assert classify_entity("CEngagement", meta) == EntityClass.CUSTOM


def test_classify_entity_native() -> None:
    meta = {"entity": True, "customizable": True, "isCustom": False}
    assert classify_entity("Contact", meta) == EntityClass.NATIVE


def test_classify_entity_non_entity_is_system() -> None:
    assert (
        classify_entity("SomeScope", {"entity": False, "customizable": True})
        == EntityClass.SYSTEM
    )


def test_classify_entity_non_customizable_is_system() -> None:
    assert (
        classify_entity("SomeScope", {"entity": True, "customizable": False})
        == EntityClass.SYSTEM
    )


def test_classify_entity_unknown_customizable_native_is_system() -> None:
    # entity+customizable, not custom, not in NATIVE_ENTITIES -> system.
    meta = {"entity": True, "customizable": True, "isCustom": False}
    assert classify_entity("MysteryEntity", meta) == EntityClass.SYSTEM


# --- classify_field ---------------------------------------------------------


def test_classify_field_system() -> None:
    assert classify_field("createdAt", {}) == FieldClass.SYSTEM
    assert classify_field("id", {}) == FieldClass.SYSTEM


def test_classify_field_custom_by_meta() -> None:
    assert classify_field("contactType", {"isCustom": True}) == FieldClass.CUSTOM


def test_classify_field_custom_by_prefix() -> None:
    assert classify_field("cContactType", {}) == FieldClass.CUSTOM


def test_classify_field_native_by_type() -> None:
    assert (
        classify_field("firstName", {}, entity_type="Person")
        == FieldClass.NATIVE
    )
    assert (
        classify_field("industry", {}, entity_type="Company")
        == FieldClass.NATIVE
    )


def test_classify_field_default_native() -> None:
    # Unknown field, no custom marker, not a system field -> native default.
    assert classify_field("somethingElse", {}) == FieldClass.NATIVE
    assert (
        classify_field("unknownField", {}, entity_type="Person")
        == FieldClass.NATIVE
    )


def test_classify_field_system_beats_custom_marker() -> None:
    # System fields are classified system even if isCustom were set.
    assert classify_field("createdAt", {"isCustom": True}) == FieldClass.SYSTEM


# --- get_native_fields_for_type ---------------------------------------------


@pytest.mark.parametrize(
    ("entity_type", "expected"),
    [
        ("Person", NATIVE_PERSON_FIELDS),
        ("Company", NATIVE_COMPANY_FIELDS),
        ("Event", NATIVE_EVENT_FIELDS),
        ("Base", NATIVE_BASE_FIELDS),
    ],
)
def test_get_native_fields_for_type(entity_type: str, expected: set) -> None:
    assert get_native_fields_for_type(entity_type) == expected


def test_get_native_fields_for_type_unknown_and_none() -> None:
    assert get_native_fields_for_type(None) == set()
    assert get_native_fields_for_type("Bogus") == set()


# --- catalogs ---------------------------------------------------------------


def test_catalog_membership_sanity() -> None:
    assert "id" in SYSTEM_FIELDS
    assert "firstName" in NATIVE_PERSON_FIELDS
    assert "industry" in NATIVE_COMPANY_FIELDS
    assert "dateStart" in NATIVE_EVENT_FIELDS
    assert NATIVE_BASE_FIELDS == {"name", "description"}


def test_native_entities_includes_core_natives() -> None:
    for name in ("Contact", "Account", "Lead", "User", "Team"):
        assert name in NATIVE_ENTITIES
    # The introspect copy must not pull in any Qt dependency.
    assert "Engagement" not in NATIVE_ENTITIES
