"""PRJ-015 UI usability batch — tests.

Covers the eight enhancements REQ-131..138 / PI-172..179. Each section is
labelled with its requirement/PI. Built incrementally as the items land.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels import _governance_helpers as gh
from crmbuilder_v2.ui.panels.entities import EntitiesPanel
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.panels.projects import ProjectsPanel
from crmbuilder_v2.ui.widgets.references_section import EntityFieldsGridSection
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


# ----------------------------------------------------------------------
# E — REQ-135 / PI-176: every entity list is searchable client-side.
# ----------------------------------------------------------------------


def test_master_search_box_present(qtbot, client_stub):
    panel = FieldsPanel(client_stub)
    qtbot.addWidget(panel)
    assert panel._search_input is not None


def test_master_search_filters_rows(qtbot, api_client):
    ent = _seed_entity(api_client, "Contact")
    _seed_field(api_client, ent, "email")
    _seed_field(api_client, ent, "phone")
    _seed_field(api_client, ent, "mobilePhone")
    panel = FieldsPanel(api_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 3, timeout=3000)

    panel._on_search_changed("phone")
    assert panel._model.rowCount() == 2
    assert {r["field_name"] for r in panel._records} == {"phone", "mobilePhone"}
    assert "of" in panel._status_label.text()

    # The owning-entity column is searchable too (synthetic visible column).
    panel._on_search_changed("Contact")
    assert panel._model.rowCount() == 3

    # Clearing restores the full set.
    panel._on_search_changed("")
    assert panel._model.rowCount() == 3


def test_navigation_clears_active_search(qtbot, api_client):
    ent = _seed_entity(api_client, "Contact")
    f1 = _seed_field(api_client, ent, "email")
    _seed_field(api_client, ent, "phone")
    panel = FieldsPanel(api_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=3000)
    panel._on_search_changed("phone")  # hides "email"
    assert panel._model.rowCount() == 1
    assert panel.select_record_by_identifier(f1["field_identifier"]) is True
    assert panel._search_text == ""
    assert panel._model.rowCount() == 2


def test_search_disabled_where_incompatible():
    from crmbuilder_v2.ui.panels.references import ReferencesPanel
    from crmbuilder_v2.ui.panels.topics import TopicsPanel

    assert TopicsPanel._search_enabled is False
    assert ReferencesPanel._search_enabled is False


# ----------------------------------------------------------------------
# F — REQ-136 / PI-177: sidebar filter + collapsible groups.
# ----------------------------------------------------------------------


def test_sidebar_filter_hides_nonmatching(qtbot):
    from crmbuilder_v2.ui.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.filter_entries("Decisions")
    assert not sb._entry_for_label("Decisions").isHidden()
    assert sb._entry_for_label("Risks").isHidden()
    sb.filter_entries("")
    assert not sb._entry_for_label("Risks").isHidden()


def test_sidebar_group_collapse(qtbot):
    from crmbuilder_v2.ui.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.set_group_collapsed("Governance", True)
    assert sb.is_group_collapsed("Governance")
    assert sb._entry_for_label("Decisions").isHidden()
    sb.set_group_collapsed("Governance", False)
    assert not sb._entry_for_label("Decisions").isHidden()


def test_sidebar_filter_overrides_collapse(qtbot):
    from crmbuilder_v2.ui.sidebar import Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.set_group_collapsed("Governance", True)
    assert sb._entry_for_label("Decisions").isHidden()
    sb.filter_entries("Decisions")
    assert not sb._entry_for_label("Decisions").isHidden()
    sb.filter_entries("")
    assert sb._entry_for_label("Decisions").isHidden()


def test_sidebar_header_click_toggles_collapse(qtbot):
    from crmbuilder_v2.ui.sidebar import _HEADER_ROLE, Sidebar

    sb = Sidebar()
    qtbot.addWidget(sb)
    header = next(
        sb.item(r)
        for r in range(sb.count())
        if sb.item(r).data(_HEADER_ROLE) and sb.item(r).text() == "Governance"
    )
    sb._on_item_clicked(header)
    assert sb.is_group_collapsed("Governance")
    sb._on_item_clicked(header)
    assert not sb.is_group_collapsed("Governance")


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


# ----------------------------------------------------------------------
# C — REQ-133 / PI-174: Entity detail lists its fields with data type.
# ----------------------------------------------------------------------


def test_entity_detail_lists_fields_with_type(qtbot, api_client):
    ent_id = _seed_entity(api_client, "Contact")
    _seed_field(api_client, ent_id, "email")  # field_type enum
    api_client.create_field(
        {
            "field_name": "fullName",
            "field_description": "d",
            "field_type": "text",
            "field_belongs_to_entity_identifier": ent_id,
        }
    )
    panel = EntitiesPanel(api_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    rec = panel._records[0]
    extras = panel.fetch_detail_extras(rec)
    rows = {r["name"]: r for r in extras["field_rows"]}
    assert set(rows) == {"email", "fullName"}
    assert rows["email"]["field_type"] == "enum"
    assert rows["fullName"]["field_type"] == "text"
    detail = panel.render_detail(rec, extras)
    qtbot.addWidget(detail)
    assert detail.findChild(EntityFieldsGridSection) is not None


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
