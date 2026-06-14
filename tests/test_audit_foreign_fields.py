"""Tests for foreign-field audit capture (REQ-121 / PI-169).

A foreign field mirrors a scalar from a linked entity (schema §6.8).
The audit must read its ``link`` and ``field`` back from metadata and
emit a valid ``type: foreign`` YAML field, dropping any ``required``
flag (the deploy validator rejects ``required: true`` on a mirror).
Includes a round-trip: the emitted YAML must pass the deploy validator.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from espo_impl.core.audit_manager import (
    AuditManager,
    AuditOptions,
    AuditReport,
    EntityAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.config_loader import ConfigLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**method_returns: Any) -> MagicMock:
    client = MagicMock()
    profile = MagicMock()
    profile.url = "https://example.test"
    profile.name = "audit-test"
    client.profile = profile
    for name, value in method_returns.items():
        getattr(client, name).return_value = value
    # Labels degrade to the field name when i18n is empty.
    if "get_i18n" not in method_returns:
        client.get_i18n.return_value = (200, {})
    return client


def _make_manager(
    client: MagicMock, options: AuditOptions | None = None
) -> AuditManager:
    return AuditManager(
        client=client,
        options=options or AuditOptions(),
        callback=lambda msg, color: None,
    )


def _report() -> AuditReport:
    return AuditReport(
        source_url="https://example.test",
        source_name="audit-test",
        timestamp="2026-06-13T00:00:00Z",
        output_dir="",
    )


def _entity() -> EntityAuditResult:
    # Native Contact so _build_entity_yaml emits no entity-create block;
    # the foreign field is captured because its metadata is isCustom.
    return EntityAuditResult(
        yaml_name="Contact",
        espo_name="Contact",
        entity_class=EntityClass.NATIVE,
        entity_type="Person",
    )


def _foreign_meta(**over: Any) -> dict[str, Any]:
    meta = {
        "type": "foreign",
        "isCustom": True,
        "readOnly": True,
        "link": "account",
        "field": "type",
        "view": "views/fields/foreign",
    }
    meta.update(over)
    return meta


# ---------------------------------------------------------------------------
# _extract_fields — foreign capture
# ---------------------------------------------------------------------------


def test_foreign_field_captures_link_and_field():
    client = _make_client(
        get_entity_field_list=(200, {"cMirrorType": _foreign_meta()}),
    )
    manager = _make_manager(client)
    entity = _entity()

    manager._extract_fields(entity, _report())

    assert len(entity.fields) == 1
    fld = entity.fields[0]
    assert fld.yaml_name == "mirrorType"  # c-prefix stripped
    assert fld.field_type == "foreign"
    assert fld.properties["link"] == "account"
    assert fld.properties["field"] == "type"


def test_foreign_field_drops_required():
    client = _make_client(
        get_entity_field_list=(200, {
            "cMirrorType": _foreign_meta(required=True),
        }),
    )
    manager = _make_manager(client)
    entity = _entity()

    manager._extract_fields(entity, _report())

    assert "required" not in entity.fields[0].properties


def test_foreign_field_verbatim_cprefixed_link_preserved():
    # On a native entity a custom link is c-prefixed; emit it verbatim
    # (the deploy re-applies the c-prefix on the relationship side).
    client = _make_client(
        get_entity_field_list=(200, {
            "cCompanyPartnerType": _foreign_meta(
                link="cCompanyPartnerProfile", field="partnershipType"
            ),
        }),
    )
    manager = _make_manager(client)
    entity = _entity()

    manager._extract_fields(entity, _report())

    props = entity.fields[0].properties
    assert props["link"] == "cCompanyPartnerProfile"
    assert props["field"] == "partnershipType"


def test_foreign_field_missing_field_warns():
    client = _make_client(
        get_entity_field_list=(200, {
            "cBroken": _foreign_meta(field=None),
        }),
    )
    manager = _make_manager(client)
    entity = _entity()
    report = _report()

    manager._extract_fields(entity, report)

    props = entity.fields[0].properties
    assert props.get("link") == "account"
    assert "field" not in props
    assert any("missing link/field" in w for w in report.warnings)


def test_non_foreign_field_unaffected():
    client = _make_client(
        get_entity_field_list=(200, {
            "cNote": {"type": "varchar", "isCustom": True, "maxLength": 50},
        }),
    )
    manager = _make_manager(client)
    entity = _entity()

    manager._extract_fields(entity, _report())

    props = entity.fields[0].properties
    assert "link" not in props
    assert "field" not in props
    assert props["maxLength"] == 50


# ---------------------------------------------------------------------------
# Round-trip: emitted YAML must pass the deploy validator
# ---------------------------------------------------------------------------


def test_foreign_field_yaml_round_trips_through_validator(tmp_path: Path):
    client = _make_client(
        get_entity_field_list=(200, {"cMirrorType": _foreign_meta()}),
    )
    manager = _make_manager(client)
    entity = _entity()
    report = _report()

    manager._extract_fields(entity, report)
    manager._write_yaml_files([entity], [], tmp_path, report)
    assert report.errors == []

    loader = ConfigLoader()
    program = loader.load_program(tmp_path / "Contact.yaml")
    errors = loader.validate_program(program)

    foreign_errors = [e for e in errors if "foreign" in e.lower()]
    assert foreign_errors == [], foreign_errors

    fld = next(
        f for f in program.entities[0].fields if f.name == "mirrorType"
    )
    assert fld.type == "foreign"
    assert fld.link == "account"
    assert fld.foreign_field == "type"
