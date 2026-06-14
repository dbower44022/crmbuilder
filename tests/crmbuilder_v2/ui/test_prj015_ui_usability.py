"""PRJ-015 UI usability batch — tests.

Covers the eight enhancements REQ-131..138 / PI-172..179. Each section is
labelled with its requirement/PI. Built incrementally as the items land.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels import _governance_helpers as gh
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.panels.projects import ProjectsPanel
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QLabel, QLineEdit, QPlainTextEdit


@pytest.fixture
def api_client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    sc.set_active_engagement("ENG-001")
    return sc


# ----------------------------------------------------------------------
# D — REQ-134 / PI-175: short read-only fields reveal full content on
# hover; project purpose wraps rather than truncating.
# ----------------------------------------------------------------------


def test_read_only_line_sets_full_value_tooltip(qapp):
    long = "x" * 300
    w = gh.read_only_line(long)
    assert w.toolTip() == long


def test_read_only_line_no_tooltip_when_empty(qapp):
    assert gh.read_only_line("").toolTip() == ""


def test_read_only_text_wraps_and_tooltips(qapp):
    long = "y" * 300
    w = gh.read_only_text(long)
    assert w.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
    assert w.toolTip() == long


def _find(widget, cls):
    return widget.findChildren(cls)


def _seed_entity(c: StorageClient, name: str = "Contact") -> str:
    return c.create_entity(
        {"entity_name": name, "entity_description": "seed"}
    )["entity_identifier"]


def _seed_field(c: StorageClient, ent_id: str, name: str = "email") -> dict:
    return c.create_field(
        {
            "field_name": name,
            "field_description": "d",
            "field_type": "enum",
            "field_belongs_to_entity_identifier": ent_id,
        }
    )


# ----------------------------------------------------------------------
# A — REQ-131 / PI-172: Fields list shows the owning entity's name.
# ----------------------------------------------------------------------


def test_fields_grid_has_entity_column(qtbot, client_stub):
    panel = FieldsPanel(client_stub)
    qtbot.addWidget(panel)
    cols = {c.field: c.title for c in panel.list_columns()}
    assert cols.get("parent_entity_name") == "Entity"


def test_fields_record_carries_owning_entity_name(qtbot, api_client):
    ent_id = _seed_entity(api_client, "Contact")
    _seed_field(api_client, ent_id, "email")
    panel = FieldsPanel(api_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    rec = panel._records[0]
    assert rec["parent_entity_identifier"] == ent_id
    assert rec["parent_entity_name"] == "Contact"


# ----------------------------------------------------------------------
# B — REQ-132 / PI-173: Field detail shows parent entity name + identifier.
# ----------------------------------------------------------------------


def test_field_detail_shows_entity_name_and_identifier(qtbot, api_client):
    ent_id = _seed_entity(api_client, "Contact")
    field = _seed_field(api_client, ent_id, "email")
    panel = FieldsPanel(api_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    rec = panel._records[0]
    extras = panel.fetch_detail_extras(rec)
    assert extras["parent_entity_name"] == "Contact"
    detail = panel.render_detail(rec, extras)
    qtbot.addWidget(detail)
    label = detail.findChild(QLabel, "field_parent_entity_value")
    assert label is not None
    assert label.text() == f"Contact ({ent_id})"


def test_project_purpose_renders_as_wrapping_widget(qtbot, client_stub):
    panel = ProjectsPanel(client_stub)
    qtbot.addWidget(panel)
    purpose = "A purpose sentence that is quite a lot longer than one line " * 3
    record = {
        "project_identifier": "PRJ-999",
        "project_name": "Test",
        "project_status": "planned",
        "project_purpose": purpose,
        "project_description": "desc",
    }
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )
    qtbot.addWidget(detail)
    # The purpose value must live in a wrapping QPlainTextEdit (not a
    # single-line QLineEdit that would truncate it).
    plain_texts = [
        w.toPlainText() for w in _find(detail, QPlainTextEdit)
    ]
    assert purpose in plain_texts
    line_texts = [w.text() for w in _find(detail, QLineEdit)]
    assert purpose not in line_texts
