"""Fields panel / dialog tests — v0.5+ (PI-004 first slice).

Covers ``field.md`` §3.7 acceptance criteria 10, 12, 14 smoke-level:
the "Fields" sidebar entry under Methodology, the master-pane
columns, and the detail pane renders for an empty and a seeded
state.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.refresh import _FILENAME_TO_ENTITY_TYPE
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def field_client(v2_env) -> StorageClient:
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed_entity(c: StorageClient, name: str = "Contact") -> str:
    body = {"entity_name": name, "entity_description": "seed"}
    return c.create_entity(body)["entity_identifier"]


def _seed_field(c: StorageClient, ent_id: str, name: str = "email") -> dict:
    body = {
        "field_name": name,
        "field_description": "d",
        "field_type": "text",
        "field_belongs_to_entity_identifier": ent_id,
    }
    return c.create_field(body)


def test_fields_appears_in_methodology_group():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert "Fields" in methodology


def test_entity_type_map_has_field_entry():
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL.get("field") == "Fields"


def test_fields_json_refresh_mapping_present():
    assert _FILENAME_TO_ENTITY_TYPE.get("fields.json") == "field"


def test_panel_renders_with_no_fields(qtbot, field_client):
    panel = FieldsPanel(field_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 0, timeout=3000)


def test_panel_renders_with_one_field(qtbot, field_client):
    ent_id = _seed_entity(field_client)
    _seed_field(field_client, ent_id)
    panel = FieldsPanel(field_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    # Master shows the field.
    assert panel._model.rowCount() == 1
    # Selecting the row triggers fetch_detail_extras and render_detail;
    # we just check the extras include the parent entity identifier
    # via the helper directly.
    extras = panel.fetch_detail_extras(panel._records[0])
    assert extras["parent_entity_identifier"] == ent_id
