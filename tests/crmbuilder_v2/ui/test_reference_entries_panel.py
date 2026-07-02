"""Reference Entries panel + dialog UI tests — REL-016 / PI-067 (REQ-402).

Covers the "Reference Entries" Methodology sidebar entry, the bespoke
create/edit dialogs (with per-kind JSON content authoring + validation), and the
panel list/detail — end to end against a real per-test DB.
"""

from __future__ import annotations

import json

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.reference_entry_crud import (
    ReferenceEntryCreateDialog,
    ReferenceEntryEditDialog,
)
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.reference_entries import ReferenceEntriesPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def ref_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _wait_rows(qtbot, panel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# --- wiring ---------------------------------------------------------------


def test_reference_entries_in_methodology_group():
    groups = dict(SIDEBAR_GROUPS)
    assert "Reference Entries" in groups["Methodology"]


def test_entity_label_registered():
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["reference_entry"] == "Reference Entries"


# --- create dialog --------------------------------------------------------


def test_create_domain_knowledge_via_dialog(qtbot, ref_client):
    dialog = ReferenceEntryCreateDialog(ref_client)
    qtbot.addWidget(dialog)
    dialog._name.setText("Nonprofit Mentoring")
    # kind defaults to domain_knowledge; fill the body template.
    dialog._content.setPlainText(json.dumps({"body": "How mentoring works."}))
    dialog._keywords.setText("mentoring, mentor")
    dialog._on_save()
    assert dialog.created_identifier() == "RFE-001"
    rows = ref_client.list_reference_entries()
    assert rows[0]["name"] == "Nonprofit Mentoring"
    assert rows[0]["trigger_keywords"] == ["mentoring", "mentor"]


def test_create_invalid_json_shows_error(qtbot, ref_client):
    dialog = ReferenceEntryCreateDialog(ref_client)
    qtbot.addWidget(dialog)
    dialog._name.setText("Bad")
    dialog._content.setPlainText("{not valid json")
    dialog._on_save()
    assert dialog.created_identifier() is None
    assert dialog._error.text()  # inline error shown
    assert ref_client.list_reference_entries() == []


def test_create_domain_knowledge_missing_body_shows_error(qtbot, ref_client):
    dialog = ReferenceEntryCreateDialog(ref_client)
    qtbot.addWidget(dialog)
    dialog._name.setText("NoBody")
    dialog._content.setPlainText(json.dumps({"notes": "x"}))
    dialog._on_save()
    # Server rejects (domain_knowledge needs a body) → surfaced inline, not created.
    assert dialog.created_identifier() is None
    assert dialog._error.text()  # server rejection surfaced inline


def test_create_organization_structure_via_dialog(qtbot, ref_client):
    dialog = ReferenceEntryCreateDialog(ref_client)
    qtbot.addWidget(dialog)
    dialog._name.setText("Foundation Shape")
    dialog._kind.setCurrentText("organization_structure")
    dialog._content.setPlainText(
        json.dumps(
            {
                "typical_entities": ["Grant", "Grantee"],
                "typical_relationships": ["A Grant is awarded to a Grantee"],
            }
        )
    )
    dialog._on_save()
    assert dialog.created_identifier() == "RFE-001"
    rows = ref_client.list_reference_entries(kind="organization_structure")
    assert rows[0]["name"] == "Foundation Shape"


def test_kind_change_swaps_content_template(qtbot, ref_client):
    dialog = ReferenceEntryCreateDialog(ref_client)
    qtbot.addWidget(dialog)
    # Editor starts on the domain_knowledge template; switching kind swaps it.
    dialog._kind.setCurrentText("inventory_items")
    parsed = json.loads(dialog._content.toPlainText())
    assert set(parsed) == {"entities", "personas", "processes"}


# --- edit dialog ----------------------------------------------------------


def test_edit_dialog_updates_name(qtbot, ref_client):
    created = ref_client.create_reference_entry(
        {"name": "Old", "kind": "domain_knowledge", "content": {"body": "x"}}
    )
    dialog = ReferenceEntryEditDialog(ref_client, created)
    qtbot.addWidget(dialog)
    dialog._name.setText("New")
    dialog._on_save()
    assert ref_client.get_reference_entry(created["identifier"])["name"] == "New"


# --- panel list + detail --------------------------------------------------


def test_panel_lists_and_renders_detail(qtbot, ref_client):
    ref_client.create_reference_entry(
        {
            "name": "Mentoring",
            "kind": "domain_knowledge",
            "content": {"body": "How mentoring works."},
            "trigger_keywords": ["mentoring"],
        }
    )
    panel = ReferenceEntriesPanel(ref_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    record = ref_client.get_reference_entry("RFE-001")
    widget = panel.render_detail(record, {})
    assert widget is not None
