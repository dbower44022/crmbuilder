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
from crmbuilder_v2.ui.dialogs.project_crud import (
    ProjectCreateDialog,
    ProjectEditDialog,
)
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.close_out_payloads import CloseOutPayloadsPanel
from crmbuilder_v2.ui.panels.conversations import ConversationsPanel
from crmbuilder_v2.ui.panels.deposit_events import DepositEventsPanel
from crmbuilder_v2.ui.panels.reference_books import ReferenceBooksPanel
from crmbuilder_v2.ui.panels.work_tickets import WorkTicketsPanel
from crmbuilder_v2.ui.panels.projects import ProjectsPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def gov_client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    # PI-β: mirror the desktop, which sends the active engagement as the
    # X-Engagement header on every request, so scoped reads/writes resolve
    # v2_env's seeded ENG-001 through the per-request scope middleware
    # (the TestClient runs the app in a portal thread that does not inherit
    # the test thread's active-engagement ContextVar).
    sc.set_active_engagement("ENG-001")
    return sc


def _wait_loaded(qtbot, panel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# Reusable executive_summary satisfying the 200-800 char requirement
# introduced by PI-074/PI-075 (sessions) and PI-102 (planning items,
# decisions). Conversations belong to a session under the PI-073 redesign.
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _make_session(client: StorageClient) -> str:
    """Create a minimal valid session and return its identifier.

    Conversations are topical sub-units within a session (PI-073), so the
    governance fixtures that previously hung a conversation off a workstream
    now hang it off a session via ``conversation_belongs_to_session``. A
    session itself requires exactly one ``session_belongs_to_project``
    edge, so this helper provisions the parent workstream first.
    """
    ws = client.create_project(
        {"project_name": "WS", "project_purpose": "p", "project_description": "d"}
    )["project_identifier"]
    result = client.create_session({
        "session_title": "S",
        "session_description": "d",
        "session_medium": "chat",
        "session_executive_summary": _EXEC_SUMMARY,
        "session_identifier": "SES-001",
        "references": [{
            "source_type": "session", "source_id": "SES-001",
            "target_type": "project", "target_id": ws,
            "relationship": "session_belongs_to_project",
        }],
    })
    return result["session_identifier"]


def test_sidebar_governance_group_appends_six_new_entries():
    six = (
        "Projects",
        "Conversations",
        "Reference Books",
        "Work Tickets",
        "Close-Out Payloads",
        "Deposit Events",
    )
    for label, entries in SIDEBAR_GROUPS:
        if label == "Governance":
            # The six v0.7 entries are contiguous and end at "Deposit
            # Events"; PI-031 later appended "Commits" after them.
            idx = entries.index("Deposit Events")
            assert entries[idx - 5 : idx + 1] == six
            return
    raise AssertionError("Governance group not found in sidebar")


def test_entity_type_to_sidebar_label_covers_governance():
    for entity_type in (
        "project",
        "conversation",
        "reference_book",
        "work_ticket",
        "close_out_payload",
        "deposit_event",
    ):
        assert entity_type in ENTITY_TYPE_TO_SIDEBAR_LABEL


# --- workstreams ------------------------------------------------------------


def test_workstreams_panel_boots_and_lists(qtbot, gov_client):
    panel = ProjectsPanel(gov_client)
    qtbot.addWidget(panel)
    assert panel.entity_title() == "Projects"
    cols = [c.field for c in panel.list_columns()]
    assert cols[:2] == ["project_identifier", "project_name"]
    _wait_loaded(qtbot, panel, 0)
    gov_client.create_project(
        {"project_name": "W", "project_purpose": "p", "project_description": "d"}
    )
    _wait_loaded(qtbot, panel, 1)


def test_workstream_dialogs_construct(qtbot, gov_client):
    create = ProjectCreateDialog(gov_client)
    qtbot.addWidget(create)
    record = gov_client.create_project(
        {"project_name": "X", "project_purpose": "p", "project_description": "d"}
    )
    edit = ProjectEditDialog(gov_client, record)
    qtbot.addWidget(edit)


# --- conversations ----------------------------------------------------------


def test_conversations_panel_boots_with_membership(qtbot, gov_client):
    sess = _make_session(gov_client)
    gov_client.create_conversation({
        "conversation_title": "C1",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": "CNV-001",
        "references": [{
            "source_type": "conversation", "source_id": "CNV-001",
            "target_type": "session", "target_id": sess,
            "relationship": "conversation_belongs_to_session",
        }],
    })
    panel = ConversationsPanel(gov_client)
    qtbot.addWidget(panel)
    _wait_loaded(qtbot, panel, 1)


def test_conversation_create_dialog_populates_session_picker(qtbot, gov_client):
    # PI-073: a conversation belongs to a session, so the create dialog's
    # membership picker is now a session picker fed by list_sessions().
    _make_session(gov_client)
    dialog = ConversationCreateDialog(gov_client)
    qtbot.addWidget(dialog)
    # 1 placeholder + 1 session
    assert dialog._session_combo.count() == 2


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
        "reference_book_kind": "project_master_plan",
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
    sess = _make_session(gov_client)
    gov_client.create_conversation({
        "conversation_title": "C",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": "CNV-001",
        "references": [{
            "source_type": "conversation", "source_id": "CNV-001",
            "target_type": "session", "target_id": sess,
            "relationship": "conversation_belongs_to_session",
        }],
    })
    dialog = CloseOutPayloadCreateDialog(gov_client)
    qtbot.addWidget(dialog)
    assert dialog._conv_combo.count() == 2  # placeholder + 1 conv


def test_cop_edit_dialog_constructs(qtbot, gov_client):
    # Manually create a COP with a conversation produced edge.
    sess = _make_session(gov_client)
    conv = gov_client.create_conversation({
        "conversation_title": "C",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": "CNV-001",
        "references": [{
            "source_type": "conversation", "source_id": "CNV-001",
            "target_type": "session", "target_id": sess,
            "relationship": "conversation_belongs_to_session",
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
