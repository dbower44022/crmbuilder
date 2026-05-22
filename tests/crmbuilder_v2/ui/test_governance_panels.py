"""Governance panel smoke tests — UI v0.7 Slice C.

Boots each of the six new panels against a real TestClient + per-test DB,
verifies the master pane refreshes with the expected columns and title,
asserts the sidebar entries are present in the Governance group, and
constructs each create/edit/delete dialog (read-only smoke for the
deposit_event panel, which has no dialogs).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.close_out_payload_crud import (
    CloseOutPayloadCreateDialog,
    CloseOutPayloadEditDialog,
)
from crmbuilder_v2.ui.dialogs.conversation_crud import (
    ConversationCreateDialog,
    ConversationEditDialog,
)
from crmbuilder_v2.ui.dialogs.reference_book_crud import (
    ReferenceBookCreateDialog,
    ReferenceBookEditDialog,
)
from crmbuilder_v2.ui.dialogs.work_ticket_crud import (
    WorkTicketCreateDialog,
    WorkTicketEditDialog,
)
from crmbuilder_v2.ui.dialogs.workstream_crud import (
    WorkstreamCreateDialog,
    WorkstreamEditDialog,
)
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.close_out_payloads import CloseOutPayloadsPanel
from crmbuilder_v2.ui.panels.conversations import ConversationsPanel
from crmbuilder_v2.ui.panels.deposit_events import DepositEventsPanel
from crmbuilder_v2.ui.panels.reference_books import ReferenceBooksPanel
from crmbuilder_v2.ui.panels.work_tickets import WorkTicketsPanel
from crmbuilder_v2.ui.panels.workstreams import WorkstreamsPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def gov_client(v2_env) -> StorageClient:
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _wait_loaded(qtbot, panel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


def test_sidebar_governance_group_appends_six_new_entries():
    for label, entries in SIDEBAR_GROUPS:
        if label == "Governance":
            tail = entries[-6:]
            assert tail == (
                "Workstreams",
                "Conversations",
                "Reference Books",
                "Work Tickets",
                "Close-Out Payloads",
                "Deposit Events",
            )
            return
    raise AssertionError("Governance group not found in sidebar")


def test_entity_type_to_sidebar_label_covers_governance():
    for entity_type in (
        "workstream",
        "conversation",
        "reference_book",
        "work_ticket",
        "close_out_payload",
        "deposit_event",
    ):
        assert entity_type in ENTITY_TYPE_TO_SIDEBAR_LABEL


# --- workstreams ------------------------------------------------------------


def test_workstreams_panel_boots_and_lists(qtbot, gov_client):
    panel = WorkstreamsPanel(gov_client)
    qtbot.addWidget(panel)
    assert panel.entity_title() == "Workstreams"
    cols = [c.field for c in panel.list_columns()]
    assert cols[:2] == ["workstream_identifier", "workstream_name"]
    _wait_loaded(qtbot, panel, 0)
    gov_client.create_workstream(
        {"workstream_name": "W", "workstream_purpose": "p", "workstream_description": "d"}
    )
    _wait_loaded(qtbot, panel, 1)


def test_workstream_dialogs_construct(qtbot, gov_client):
    create = WorkstreamCreateDialog(gov_client)
    qtbot.addWidget(create)
    record = gov_client.create_workstream(
        {"workstream_name": "X", "workstream_purpose": "p", "workstream_description": "d"}
    )
    edit = WorkstreamEditDialog(gov_client, record)
    qtbot.addWidget(edit)


# --- conversations ----------------------------------------------------------


def test_conversations_panel_boots_with_membership(qtbot, gov_client):
    ws = gov_client.create_workstream(
        {"workstream_name": "WS", "workstream_purpose": "p", "workstream_description": "d"}
    )["workstream_identifier"]
    gov_client.create_conversation({
        "conversation_title": "C1",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": "CONV-001",
        "references": [{
            "source_type": "conversation", "source_id": "CONV-001",
            "target_type": "workstream", "target_id": ws,
            "relationship": "conversation_belongs_to_workstream",
        }],
    })
    panel = ConversationsPanel(gov_client)
    qtbot.addWidget(panel)
    _wait_loaded(qtbot, panel, 1)


def test_conversation_create_dialog_populates_workstream_picker(qtbot, gov_client):
    gov_client.create_workstream(
        {"workstream_name": "WS A", "workstream_purpose": "p", "workstream_description": "d"}
    )
    dialog = ConversationCreateDialog(gov_client)
    qtbot.addWidget(dialog)
    # 1 placeholder + 1 workstream
    assert dialog._workstream_combo.count() == 2


# --- reference_books --------------------------------------------------------


def test_reference_books_panel_boots(qtbot, gov_client):
    panel = ReferenceBooksPanel(gov_client)
    qtbot.addWidget(panel)
    assert panel.entity_title() == "Reference Books"
    _wait_loaded(qtbot, panel, 0)


def test_reference_book_dialog_constructs(qtbot, gov_client):
    dialog = ReferenceBookCreateDialog(gov_client)
    qtbot.addWidget(dialog)
    record = gov_client.create_reference_book({
        "reference_book_title": "Plan",
        "reference_book_description": "d",
        "reference_book_kind": "workstream_master_plan",
        "reference_book_file_path": "PRDs/p.md",
    })
    edit = ReferenceBookEditDialog(gov_client, record)
    qtbot.addWidget(edit)


# --- work_tickets -----------------------------------------------------------


def test_work_tickets_panel_boots(qtbot, gov_client):
    panel = WorkTicketsPanel(gov_client)
    qtbot.addWidget(panel)
    assert panel.entity_title() == "Work Tickets"
    _wait_loaded(qtbot, panel, 0)


def test_work_ticket_dialog_constructs(qtbot, gov_client):
    dialog = WorkTicketCreateDialog(gov_client)
    qtbot.addWidget(dialog)
    record = gov_client.create_work_ticket({
        "work_ticket_title": "K",
        "work_ticket_description": "d",
        "work_ticket_kind": "kickoff_prompt",
        "work_ticket_file_path": "PRDs/k.md",
    })
    edit = WorkTicketEditDialog(gov_client, record)
    qtbot.addWidget(edit)


# --- close_out_payloads -----------------------------------------------------


def test_close_out_payloads_panel_boots(qtbot, gov_client):
    panel = CloseOutPayloadsPanel(gov_client)
    qtbot.addWidget(panel)
    assert panel.entity_title() == "Close-Out Payloads"
    _wait_loaded(qtbot, panel, 0)


def test_cop_create_dialog_populates_conversation_picker(qtbot, gov_client):
    ws = gov_client.create_workstream(
        {"workstream_name": "WS", "workstream_purpose": "p", "workstream_description": "d"}
    )["workstream_identifier"]
    gov_client.create_conversation({
        "conversation_title": "C",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": "CONV-001",
        "references": [{
            "source_type": "conversation", "source_id": "CONV-001",
            "target_type": "workstream", "target_id": ws,
            "relationship": "conversation_belongs_to_workstream",
        }],
    })
    dialog = CloseOutPayloadCreateDialog(gov_client)
    qtbot.addWidget(dialog)
    assert dialog._conv_combo.count() == 2  # placeholder + 1 conv


def test_cop_edit_dialog_constructs(qtbot, gov_client):
    # Manually create a COP with a conversation produced edge.
    ws = gov_client.create_workstream(
        {"workstream_name": "WS", "workstream_purpose": "p", "workstream_description": "d"}
    )["workstream_identifier"]
    conv = gov_client.create_conversation({
        "conversation_title": "C",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": "CONV-001",
        "references": [{
            "source_type": "conversation", "source_id": "CONV-001",
            "target_type": "workstream", "target_id": ws,
            "relationship": "conversation_belongs_to_workstream",
        }],
    })["conversation_identifier"]
    record = gov_client.create_close_out_payload({
        "close_out_payload_title": "P",
        "close_out_payload_description": "d",
        "close_out_payload_file_path": "close-out-payloads/x.json",
        "close_out_payload_identifier": "COP-001",
        "references": [{
            "source_type": "close_out_payload", "source_id": "COP-001",
            "target_type": "conversation", "target_id": conv,
            "relationship": "close_out_payload_produced_by_conversation",
        }],
    })
    dialog = CloseOutPayloadEditDialog(gov_client, record)
    qtbot.addWidget(dialog)


# --- deposit_events (read-only) ---------------------------------------------


def test_deposit_events_panel_is_read_only(qtbot, gov_client):
    panel = DepositEventsPanel(gov_client)
    qtbot.addWidget(panel)
    assert panel.entity_title() == "Deposit Events"
    # No New button on the toolbar (born-terminal append-only).
    assert not hasattr(panel, "_new_button")
    _wait_loaded(qtbot, panel, 0)
