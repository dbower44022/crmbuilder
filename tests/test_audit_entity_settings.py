"""Tests for entity collection-settings audit capture (PI-300 / REQ-340).

EspoCRM stores an entity's default sort, quick-search text-filter fields,
and full-text search configuration under
``entityDefs.<Entity>.collection``. The audit captures these onto the
EntityAuditResult and re-emits them in a ``settings:`` block so they
round-trip through deploy. These tests cover capture, the non-200 noop,
YAML emission, and that the emitted settings parse back identically.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import yaml

from espo_impl.core.audit_manager import (
    AuditManager,
    AuditOptions,
    AuditReport,
    EntityAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.config_loader import ConfigLoader


def _client(**method_returns: Any) -> MagicMock:
    client = MagicMock()
    profile = MagicMock()
    profile.url = "https://example.test"
    profile.name = "audit-test"
    client.profile = profile
    for name, value in method_returns.items():
        getattr(client, name).return_value = value
    return client


def _manager(client: MagicMock) -> AuditManager:
    return AuditManager(client, AuditOptions(), lambda m, c: None)


def _report() -> AuditReport:
    return AuditReport(
        source_url="https://example.test", source_name="audit-test",
        timestamp="2026-06-13T00:00:00Z", output_dir="",
    )


def _entity() -> EntityAuditResult:
    return EntityAuditResult(
        yaml_name="MentorProfile", espo_name="CMentorProfile",
        entity_class=EntityClass.CUSTOM, entity_type="Base",
    )


_COLLECTION = {
    "orderBy": "lastName",
    "order": "asc",
    "textFilterFields": ["name", "mentoringSkills"],
    "fullTextSearch": True,
    "fullTextSearchMinLength": 4,
    # Legacy mirror keys present on a live instance — ignored by capture.
    "sortBy": "lastName",
    "asc": True,
}


# --- capture ---------------------------------------------------------------


def test_extract_entity_settings_captures_collection():
    client = _client(
        get_entity_full_metadata=(200, {"collection": dict(_COLLECTION)})
    )
    mgr = _manager(client)
    entity = _entity()

    mgr._extract_entity_settings(entity, _report())

    assert entity.order_by == "lastName"
    assert entity.order == "asc"
    assert entity.text_filter_fields == ["name", "mentoringSkills"]
    assert entity.full_text_search is True
    assert entity.full_text_search_min_length == 4
    client.get_entity_full_metadata.assert_called_once_with("CMentorProfile")


def test_extract_entity_settings_no_collection_is_noop():
    client = _client(get_entity_full_metadata=(200, {"stream": True}))
    mgr = _manager(client)
    entity = _entity()

    mgr._extract_entity_settings(entity, _report())

    assert entity.order_by is None
    assert entity.text_filter_fields is None
    assert entity.full_text_search is None


def test_extract_entity_settings_non_200_warns():
    client = _client(get_entity_full_metadata=(500, None))
    mgr = _manager(client)
    entity = _entity()
    report = _report()

    mgr._extract_entity_settings(entity, report)

    assert entity.order_by is None
    assert any("collection settings" in w for w in report.warnings)


# --- emission --------------------------------------------------------------


def test_build_entity_yaml_emits_settings_block():
    mgr = _manager(_client())
    entity = _entity()
    entity.order_by = "lastName"
    entity.order = "asc"
    entity.text_filter_fields = ["name", "emailAddress"]
    entity.full_text_search = True

    block = mgr._build_entity_yaml(entity)["entities"]["MentorProfile"]

    assert block["settings"] == {
        "orderBy": "lastName",
        "order": "asc",
        "textFilterFields": ["name", "emailAddress"],
        "fullTextSearch": True,
    }


def test_build_entity_yaml_no_settings_when_uncaptured():
    mgr = _manager(_client())
    entity = _entity()  # no collection settings captured

    block = mgr._build_entity_yaml(entity)["entities"]["MentorProfile"]

    assert "settings" not in block


def test_emitted_settings_round_trip(tmp_path: Path):
    """Audit-emitted settings parse back to the same EntitySettings."""
    mgr = _manager(_client())
    entity = _entity()
    entity.order_by = "createdAt"
    entity.order = "desc"
    entity.text_filter_fields = ["name"]
    entity.full_text_search = True
    entity.full_text_search_min_length = 4

    doc = mgr._build_entity_yaml(entity)
    path = tmp_path / "audited.yaml"
    path.write_text(yaml.safe_dump(doc))

    program = ConfigLoader().load_program(path)
    errors = ConfigLoader().validate_program(program)
    assert not any("settings." in e for e in errors)

    s = program.entities[0].settings
    assert s.orderBy == "createdAt"
    assert s.order == "desc"
    assert s.textFilterFields == ["name"]
    assert s.fullTextSearch is True
    assert s.fullTextSearchMinLength == 4
