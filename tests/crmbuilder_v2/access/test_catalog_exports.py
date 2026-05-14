"""Catalog JSON-export hook tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import catalog
from crmbuilder_v2.access.repositories.catalog.exports import (
    catalog_export_dir,
    is_suppressed,
    suppression,
)
from crmbuilder_v2.bootstrap.catalog_loader import load_catalog
from crmbuilder_v2.config import get_settings


_FIXTURE_CATALOG = Path(__file__).resolve().parents[1] / "bootstrap" / "fixtures" / "catalog"


def test_export_dir_path(v2_env):
    s = get_settings()
    expected = s.export_dir / "catalog" / "entities"
    assert catalog_export_dir() == expected


def test_export_entity_writes_file(v2_env):
    """Calling export_entity after a write produces a valid JSON file."""
    body = {
        "catalog_id": "widget",
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
    }
    with session_scope() as s:
        catalog.create_entity(s, payload=body)

    target = catalog_export_dir() / "widget.json"
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["catalog_id"] == "widget"
    assert data["display_name"] == "Widget"


def test_export_format_is_deterministic(v2_env):
    body = {
        "catalog_id": "widget",
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
    }
    with session_scope() as s:
        catalog.create_entity(s, payload=body)
    target = catalog_export_dir() / "widget.json"
    text = target.read_text(encoding="utf-8")
    # Sorted keys, 2-space indent. Verify by reparsing and re-dumping.
    parsed = json.loads(text)
    redumped = json.dumps(parsed, sort_keys=True, indent=2, ensure_ascii=False)
    assert text.rstrip("\n") == redumped


def test_export_updated_on_patch(v2_env):
    body = {
        "catalog_id": "widget",
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
    }
    with session_scope() as s:
        catalog.create_entity(s, payload=body)

    target = catalog_export_dir() / "widget.json"
    initial = json.loads(target.read_text())
    assert initial["display_name"] == "Widget"

    with session_scope() as s:
        catalog.patch_entity(s, "widget", display_name="Big Widget")

    after = json.loads(target.read_text())
    assert after["display_name"] == "Big Widget"


def test_export_removed_on_soft_delete(v2_env):
    body = {
        "catalog_id": "widget",
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
    }
    with session_scope() as s:
        catalog.create_entity(s, payload=body)
    target = catalog_export_dir() / "widget.json"
    assert target.exists()

    with session_scope() as s:
        catalog.delete_entity(s, "widget")
    assert not target.exists()


def test_attribute_write_re_exports_parent(v2_env):
    body = {
        "catalog_id": "widget",
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
    }
    with session_scope() as s:
        catalog.create_entity(s, payload=body)

    with session_scope() as s:
        catalog.create_attribute(
            s,
            "widget",
            payload={
                "name": "color",
                "display_name": "Color",
                "type": "string",
                "required": True,
            },
        )

    target = catalog_export_dir() / "widget.json"
    data = json.loads(target.read_text())
    attr_names = {a["name"] for a in data["attributes"]}
    assert "color" in attr_names


def test_suppression_disables_export(v2_env):
    body = {
        "catalog_id": "widget",
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
    }
    target = catalog_export_dir() / "widget.json"
    assert not target.exists()
    with suppression():
        with session_scope() as s:
            catalog.create_entity(s, payload=body)
    assert not target.exists()  # suppressed → no file written

    # Outside suppression, the next write produces a file.
    with session_scope() as s:
        catalog.patch_entity(s, "widget", display_name="Now Visible")
    assert target.exists()


def test_suppression_resets_after_context(v2_env):
    assert is_suppressed() is False
    with suppression():
        assert is_suppressed() is True
    assert is_suppressed() is False


def test_bulk_regenerate_writes_all_files(v2_env):
    """After loader+suppression, regenerate_all produces one file per entity."""
    with suppression():
        with session_scope() as s:
            load_catalog(s, _FIXTURE_CATALOG)

    # No JSON files yet (suppressed during load).
    if catalog_export_dir().exists():
        existing_files = list(catalog_export_dir().glob("*.json"))
        assert existing_files == []

    with session_scope(export=False) as s:
        report = catalog.regenerate_all_catalog_exports(s)
    assert report["written"] == 5  # 5 fixture entities

    files = sorted(p.name for p in catalog_export_dir().glob("*.json"))
    assert files == [
        "account-nonprofit.json",
        "account.json",
        "contact.json",
        "donation-major-gift.json",
        "donation.json",
    ]


def test_bulk_regenerate_sweeps_stale(v2_env):
    """A JSON file for an entity no longer in the DB is removed by regenerate."""
    catalog_export_dir().mkdir(parents=True, exist_ok=True)
    stale = catalog_export_dir() / "ghost.json"
    stale.write_text('{"catalog_id": "ghost"}\n', encoding="utf-8")
    assert stale.exists()

    with session_scope(export=False) as s:
        report = catalog.regenerate_all_catalog_exports(s)
    assert report["removed"] >= 1
    assert not stale.exists()


def test_full_payload_round_trip(v2_env):
    """Exported JSON shape matches what the read API returns for the same entity."""
    body = {
        "catalog_id": "widget",
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
        "common_synonyms": ["Thing"],
        "systems": [
            {
                "system": "salesforce",
                "name": "Widget__c",
                "is_standard": "false",
            }
        ],
        "sources": [{"title": "x", "url": "https://example.com/x"}],
        "attributes": [
            {
                "name": "color",
                "display_name": "Color",
                "type": "string",
                "presence": [{"system": "salesforce", "status": "custom"}],
            }
        ],
    }
    with session_scope() as s:
        catalog.create_entity(s, payload=body)

    target = catalog_export_dir() / "widget.json"
    file_data = json.loads(target.read_text())
    with session_scope(export=False) as s:
        api_data = catalog.get_entity(s, "widget")
    assert file_data == api_data
