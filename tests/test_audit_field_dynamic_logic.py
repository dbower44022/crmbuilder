"""Tests for field-level dynamic-logic audit capture (REQ-123 / PI-170).

The audit reverses EspoCRM ``clientDefs.{Entity}.dynamicLogic.fields``
into the YAML ``requiredWhen`` / ``visibleWhen`` condition expressions —
the inverse of the deploy side's ``render_condition`` →
``dynamicLogicRequired`` / ``dynamicLogicVisible``. Operator vocabulary
and nesting were grounded against the live CBM instance (isTrue, isEmpty,
equals, and/or, implicit-AND multi-item groups). Includes a round-trip
through the deploy validator.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from espo_impl.core.audit_manager import (
    AuditManager,
    AuditOptions,
    AuditReport,
    EntityAuditResult,
    FieldAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.config_loader import ConfigLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(**method_returns: Any) -> MagicMock:
    client = MagicMock()
    profile = MagicMock()
    profile.url = "https://example.test"
    profile.name = "audit-test"
    client.profile = profile
    for name, value in method_returns.items():
        getattr(client, name).return_value = value
    if "get_i18n" not in method_returns:
        client.get_i18n.return_value = (200, {})
    return client


def _manager(client: MagicMock) -> AuditManager:
    return AuditManager(client, AuditOptions(), lambda msg, color: None)


def _report() -> AuditReport:
    return AuditReport(
        source_url="https://example.test",
        source_name="audit-test",
        timestamp="2026-06-13T00:00:00Z",
        output_dir="",
    )


def _entity(*fields: tuple[str, str]) -> EntityAuditResult:
    """Build a Contact entity carrying (api_name, yaml_name) fields."""
    e = EntityAuditResult(
        yaml_name="Contact", espo_name="Contact",
        entity_class=EntityClass.NATIVE, entity_type="Person",
    )
    for api, yaml in fields:
        e.fields.append(FieldAuditResult(
            yaml_name=yaml, api_name=api, field_type="bool",
            label=yaml, properties={},
        ))
    return e


def _client_defs(field_rules: dict) -> dict:
    return {"dynamicLogic": {"fields": field_rules}}


def _apply(field_rules: dict, *fields: tuple[str, str],
           custom: set[str] | None = None):
    client = _client(get_client_defs=(200, _client_defs(field_rules)))
    manager = _manager(client)
    entity = _entity(*fields)
    if custom:
        manager._custom_field_names["Contact"] = custom
    report = _report()
    manager._apply_field_dynamic_logic(entity, report)
    return entity, report


# ---------------------------------------------------------------------------
# operator translation
# ---------------------------------------------------------------------------


def test_is_true_maps_to_equals_true():
    entity, _ = _apply(
        {"active": {"visible": {"conditionGroup": [
            {"type": "isTrue", "attribute": "isFlag"}]}}},
        ("active", "active"),
    )
    assert entity.fields[0].properties["visibleWhen"] == {
        "field": "isFlag", "op": "equals", "value": True,
    }


def test_is_false_maps_to_equals_false():
    entity, _ = _apply(
        {"active": {"required": {"conditionGroup": [
            {"type": "isFalse", "attribute": "isFlag"}]}}},
        ("active", "active"),
    )
    assert entity.fields[0].properties["requiredWhen"] == {
        "field": "isFlag", "op": "equals", "value": False,
    }


def test_empty_maps_to_null_operators():
    entity, _ = _apply(
        {"active": {"visible": {"conditionGroup": [
            {"type": "isEmpty", "attribute": "a"},
            {"type": "isNotEmpty", "attribute": "b"}]}}},
        ("active", "active"),
    )
    # Two top-level items → implicit AND.
    assert entity.fields[0].properties["visibleWhen"] == {"all": [
        {"field": "a", "op": "isNull"},
        {"field": "b", "op": "isNotNull"},
    ]}


def test_explicit_or_group_with_values():
    entity, _ = _apply(
        {"active": {"visible": {"conditionGroup": [{"type": "or", "value": [
            {"type": "equals", "attribute": "status", "value": "On"},
            {"type": "in", "attribute": "tier", "value": ["a", "b"]}]}]}}},
        ("active", "active"),
    )
    assert entity.fields[0].properties["visibleWhen"] == {"any": [
        {"field": "status", "op": "equals", "value": "On"},
        {"field": "tier", "op": "in", "value": ["a", "b"]},
    ]}


def test_custom_attribute_name_is_reversed():
    entity, _ = _apply(
        {"active": {"visible": {"conditionGroup": [
            {"type": "isTrue", "attribute": "cMentorFlag"}]}}},
        ("active", "active"),
        custom={"cMentorFlag"},
    )
    assert entity.fields[0].properties["visibleWhen"]["field"] == "mentorFlag"


# ---------------------------------------------------------------------------
# scope / skip behavior
# ---------------------------------------------------------------------------


def test_readonly_dynamic_logic_is_skipped():
    entity, _ = _apply(
        {"active": {"readOnly": {"conditionGroup": [
            {"type": "isTrue", "attribute": "isFlag"}]}}},
        ("active", "active"),
    )
    props = entity.fields[0].properties
    assert "requiredWhen" not in props and "visibleWhen" not in props


def test_logic_on_uncaptured_field_is_ignored():
    entity, report = _apply(
        {"cGhost": {"visible": {"conditionGroup": [
            {"type": "isTrue", "attribute": "isFlag"}]}}},
        ("active", "active"),
    )
    assert entity.fields[0].properties == {}
    assert report.warnings == []


def test_unknown_operator_poisons_with_warning():
    entity, report = _apply(
        {"active": {"visible": {"conditionGroup": [
            {"type": "weirdOp", "attribute": "x", "value": 1}]}}},
        ("active", "active"),
    )
    assert "visibleWhen" not in entity.fields[0].properties
    assert any("unsupported condition type" in w for w in report.warnings)


def test_both_required_and_visible_captured():
    entity, _ = _apply(
        {"active": {
            "required": {"conditionGroup": [
                {"type": "isNotEmpty", "attribute": "a"}]},
            "visible": {"conditionGroup": [
                {"type": "isEmpty", "attribute": "b"}]}}},
        ("active", "active"),
    )
    props = entity.fields[0].properties
    assert props["requiredWhen"] == {"field": "a", "op": "isNotNull"}
    assert props["visibleWhen"] == {"field": "b", "op": "isNull"}


def test_no_dynamic_logic_block_is_noop():
    client = _client(get_client_defs=(200, {"someOtherKey": 1}))
    manager = _manager(client)
    entity = _entity(("active", "active"))
    manager._apply_field_dynamic_logic(entity, _report())
    assert entity.fields[0].properties == {}


# ---------------------------------------------------------------------------
# Round-trip through the deploy validator
# ---------------------------------------------------------------------------


def test_visible_when_yaml_round_trips_through_validator(tmp_path: Path):
    """Capture via the full path, then load+validate the emitted YAML."""
    client = _client(
        get_entity_field_list=(200, {
            "cActive": {"type": "bool", "isCustom": True},
        }),
        get_client_defs=(200, _client_defs({
            "cActive": {"visible": {"conditionGroup": [
                {"type": "isNotEmpty", "attribute": "firstName"}]}},
        })),
    )
    manager = _manager(client)
    entity = EntityAuditResult(
        yaml_name="Contact", espo_name="Contact",
        entity_class=EntityClass.NATIVE, entity_type="Person",
    )
    report = _report()

    manager._extract_fields(entity, report)
    manager._apply_field_dynamic_logic(entity, report)
    manager._write_yaml_files([entity], [], tmp_path, report)
    assert report.errors == []

    loader = ConfigLoader()
    program = loader.load_program(tmp_path / "Contact.yaml")
    errors = loader.validate_program(program)

    dl_errors = [e for e in errors if "visibleWhen" in e or "When" in e]
    assert dl_errors == [], dl_errors
    fld = next(f for f in program.entities[0].fields if f.name == "active")
    assert fld.visible_when_raw is not None
