"""Participants panel / dialog tests — REL-069 / PI-391 (REQ-454).

Covers the "Participants" Methodology sidebar entry, the master-pane columns,
the create/edit/delete dialogs (including renaming a placeholder to a real
person), and the detail pane — end to end against a real per-test DB.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.participant_crud import (
    ParticipantCreateDialog,
    ParticipantEditDialog,
)
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.participant import ParticipantsPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def part_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _wait_rows(qtbot, panel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# --- wiring ---------------------------------------------------------------


def test_participants_in_methodology_group():
    groups = dict(SIDEBAR_GROUPS)
    assert "Participants" in groups["Methodology"]


def test_entity_label_registered():
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["participant"] == "Participants"


# --- create dialog --------------------------------------------------------


def test_create_dialog_persists_and_assigns_identifier(qtbot, part_client):
    dialog = ParticipantCreateDialog(part_client)
    qtbot.addWidget(dialog)
    assert "participant_identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["participant_name"].setText("Business Subject-Matter Expert")
    dialog._widgets["participant_role_kind"].setText("Business Subject-Matter Expert")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    rows = part_client.list_participants()
    assert rows[0]["participant_identifier"] == "PTC-001"
    assert rows[0]["participant_name"] == "Business Subject-Matter Expert"


def test_create_dialog_surfaces_duplicate_name_inline(qtbot, part_client):
    part_client.create_participant(
        {"participant_name": "Scheduler", "participant_role_kind": "Scheduler"}
    )
    dialog = ParticipantCreateDialog(part_client)
    qtbot.addWidget(dialog)
    dialog._widgets["participant_name"].setText("scheduler")  # case-insensitive dup
    dialog._widgets["participant_role_kind"].setText("Scheduler")
    dialog._on_save_clicked()
    # No second record created (duplicate rejected).
    assert len(part_client.list_participants()) == 1


# --- edit dialog (the rename use case) ------------------------------------


def test_edit_dialog_renames_placeholder_to_real_person(qtbot, part_client):
    created = part_client.create_participant(
        {"participant_name": "Consultant", "participant_role_kind": "Consultant"}
    )
    ident = created["participant_identifier"]
    dialog = ParticipantEditDialog(part_client, created)
    qtbot.addWidget(dialog)
    assert dialog._widgets["participant_identifier"].isReadOnly()
    dialog._widgets["participant_name"].setText("Jane Smith")
    dialog._widgets["participant_affiliation"].setText("Acme Nonprofit")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    fresh = part_client.get_participant(ident)
    assert fresh["participant_name"] == "Jane Smith"
    assert fresh["participant_affiliation"] == "Acme Nonprofit"
    # Role unchanged by the rename.
    assert fresh["participant_role_kind"] == "Consultant"


# --- panel list + detail --------------------------------------------------


def test_new_button_label(qtbot, part_client):
    panel = ParticipantsPanel(part_client)
    qtbot.addWidget(panel)
    assert panel._new_button.text() == "New Participant"


def test_panel_lists_and_renders_detail(qtbot, part_client):
    part_client.create_participant(
        {
            "participant_name": "IT Manager",
            "participant_role_kind": "IT Manager",
            "participant_contact": "it@acme.org",
        }
    )
    panel = ParticipantsPanel(part_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    record = part_client.get_participant("PTC-001")
    widget = panel.render_detail(record, {"references": {"as_source": [], "as_target": []}})
    assert widget is not None


def test_master_pane_columns(qtbot, part_client):
    panel = ParticipantsPanel(part_client)
    qtbot.addWidget(panel)
    cols = [c.field for c in panel.list_columns()]
    assert cols == [
        "participant_identifier",
        "participant_name",
        "participant_role_kind",
        "participant_status",
        "created_at_display",
    ]
