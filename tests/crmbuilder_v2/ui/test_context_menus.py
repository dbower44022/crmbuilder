"""Right-click context-menu sweep tests across every entity panel.

DEC-036 makes right-click context menus uniform across every entity
row. Slice B's contract is that each panel surfaces the documented
action set per the v0.3 PRD §4.2 / slice B prompt action map. These
tests assert action-label parity for both the row-context and
whitespace-context paths.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.topics import _IDENTIFIER_ROLE, TopicsPanel
from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import QApplication, QMenu

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _action_labels(menu: QMenu) -> list[str]:
    return [a.text() for a in menu.actions()]


def _seed_table_records(panel, records: list[dict[str, Any]]) -> QModelIndex:
    """Install records on the panel's _RecordTableModel and return the
    model index for the first row.
    """
    panel._records = list(records)
    panel._model.set_records(records)
    return panel._model.index(0, 0)


def _seed_tree_record(panel, record: dict[str, Any]) -> QModelIndex:
    """Install a single root-level item on TopicsPanel's tree model and
    return its model index.
    """
    panel._records = [record]
    panel._tree_model.clear()
    panel._tree_model.setHorizontalHeaderLabels(["Topic"])
    item = QStandardItem(
        f"{record.get('identifier')} — {record.get('name') or ''}"
    )
    item.setEditable(False)
    item.setData(record.get("identifier"), _IDENTIFIER_ROLE)
    panel._tree_model.appendRow(item)
    panel._items_by_identifier = {record["identifier"]: item}
    return item.index()


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def test_decisions_context_menu_whitespace(qtbot, client_stub):
    panel = DecisionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert _action_labels(menu) == ["New decision"]


def test_decisions_context_menu_active_row(qtbot, client_stub):
    panel = DecisionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {"identifier": "DEC-007", "title": "Test", "status": "Active"}
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    # Separator entries have empty text; assert non-separator labels.
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert labels == ["Edit", "Delete", "Show references"]


def test_decisions_context_menu_deleted_row_shows_restore(qtbot, client_stub):
    panel = DecisionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {"identifier": "DEC-007", "title": "Test", "status": "Deleted"}
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert labels == ["Edit", "Restore", "Show references"]


def test_decisions_context_menu_separator_between_write_and_read(
    qtbot, client_stub
):
    """v0.3 slice E micro-adjust: a visual separator distinguishes the
    write actions (Edit / Delete or Restore) from the read action
    (Show references), mirroring the References panel's hierarchy.
    """
    panel = DecisionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {"identifier": "DEC-007", "title": "Test", "status": "Active"}
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    actions = list(menu.actions())
    # Find the separator and assert it sits between "Delete" and "Show references".
    separator_indices = [i for i, a in enumerate(actions) if a.isSeparator()]
    assert len(separator_indices) == 1
    sep = separator_indices[0]
    assert actions[sep - 1].text() == "Delete"
    assert actions[sep + 1].text() == "Show references"


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def test_sessions_context_menu_whitespace_offers_new_session(
    qtbot, client_stub
):
    panel = SessionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    # v0.3 slice D — DEC-034 authorizes user-authored sessions.
    assert _action_labels(menu) == ["New session"]


def test_sessions_context_menu_row(qtbot, client_stub):
    panel = SessionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {"identifier": "SES-008", "title": "v0.3 planning"}
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["Go to references", "Copy identifier"]


def test_sessions_copy_identifier_writes_clipboard(qtbot, client_stub):
    panel = SessionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {"identifier": "SES-008", "title": "v0.3 planning"}
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    copy_action = next(a for a in menu.actions() if a.text() == "Copy identifier")
    QApplication.clipboard().clear()
    copy_action.trigger()
    assert QApplication.clipboard().text() == "SES-008"


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


def test_risks_context_menu_whitespace(qtbot, client_stub):
    panel = RisksPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert _action_labels(menu) == ["New risk"]


def test_risks_context_menu_row(qtbot, client_stub):
    panel = RisksPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {
        "identifier": "RISK-001",
        "title": "Test risk",
        "probability": "Low",
        "impact": "Low",
        "status": "Open",
    }
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["Edit", "Delete"]


# ---------------------------------------------------------------------------
# Planning Items
# ---------------------------------------------------------------------------


def test_planning_items_context_menu_whitespace(qtbot, client_stub):
    panel = PlanningItemsPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert _action_labels(menu) == ["New planning item"]


def test_planning_items_context_menu_row(qtbot, client_stub):
    panel = PlanningItemsPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {
        "identifier": "PI-001",
        "title": "Styling pass",
        "item_type": "pending_work",
        "status": "Open",
    }
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["Edit", "Delete"]


# ---------------------------------------------------------------------------
# Topics (QTreeView)
# ---------------------------------------------------------------------------


def test_topics_context_menu_whitespace(qtbot, client_stub):
    panel = TopicsPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert _action_labels(menu) == ["New topic"]


def test_topics_context_menu_row(qtbot, client_stub):
    panel = TopicsPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {
        "identifier": "TOP-1",
        "name": "Test topic",
        "parent_topic_identifier": None,
        "description": "",
    }
    index = _seed_tree_record(panel, record)
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["Edit", "Delete"]


# ---------------------------------------------------------------------------
# References (list-only panel, slice B has no whitespace action)
# ---------------------------------------------------------------------------


def test_references_context_menu_whitespace_includes_new_reference(
    qtbot, client_stub
):
    """v0.3 slice C adds "New reference" to the whitespace context."""
    panel = ReferencesPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert _action_labels(menu) == ["New reference"]


def test_references_context_menu_row_includes_delete(qtbot, client_stub):
    """v0.3 slice C extends row context with "Delete reference"."""
    panel = ReferencesPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {
        "id": 1,
        "source_type": "session",
        "source_id": "SES-008",
        "target_type": "decision",
        "target_id": "DEC-032",
        "relationship": "decided_in",
        "_source_display": "session:SES-008",
        "_target_display": "decision:DEC-032",
    }
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    # Separator entries have empty text; assert non-separator labels.
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert labels == ["Go to source", "Go to target", "Delete reference"]


def test_references_go_to_source_emits_navigation(qtbot, client_stub):
    panel = ReferencesPanel(client=client_stub)
    qtbot.addWidget(panel)
    record = {
        "id": 1,
        "source_type": "session",
        "source_id": "SES-008",
        "target_type": "decision",
        "target_id": "DEC-032",
        "relationship_kind": "decided_in",
        "_source_display": "session:SES-008",
        "_target_display": "decision:DEC-032",
    }
    index = _seed_table_records(panel, [record])
    menu = panel._build_context_menu(index)
    captured: list[tuple[str, str]] = []
    panel.navigate_requested.connect(lambda t, i: captured.append((t, i)))
    next(a for a in menu.actions() if a.text() == "Go to source").trigger()
    assert captured == [("session", "SES-008")]


# ---------------------------------------------------------------------------
# Charter / Status (versioned panels)
# ---------------------------------------------------------------------------


def _seed_versioned_record(
    panel, version: int, is_current: bool, payload: dict | None = None
) -> QModelIndex:
    record = {
        "id": version,
        "version": version,
        "created_at": "2026-05-09T00:00:00",
        "is_current": is_current,
        "payload": payload or {},
    }
    # VersionedPanel post-processes records to add _current_marker.
    processed = panel._post_process_records([record])
    panel._records = processed
    panel._model.set_records(processed)
    return panel._model.index(0, 0)


def test_charter_context_menu_whitespace(qtbot, client_stub):
    panel = CharterPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert _action_labels(menu) == ["New version"]


def test_charter_context_menu_current_version(qtbot, client_stub):
    panel = CharterPanel(client=client_stub)
    qtbot.addWidget(panel)
    index = _seed_versioned_record(panel, version=2, is_current=True)
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["View payload"]


def test_charter_context_menu_non_current_version(qtbot, client_stub):
    panel = CharterPanel(client=client_stub)
    qtbot.addWidget(panel)
    index = _seed_versioned_record(panel, version=1, is_current=False)
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["Make Current", "View payload"]


def test_status_context_menu_whitespace(qtbot, client_stub):
    panel = StatusPanel(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert _action_labels(menu) == ["New version"]


def test_status_context_menu_current_version(qtbot, client_stub):
    panel = StatusPanel(client=client_stub)
    qtbot.addWidget(panel)
    index = _seed_versioned_record(panel, version=9, is_current=True)
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["View payload"]


def test_status_context_menu_non_current_version(qtbot, client_stub):
    panel = StatusPanel(client=client_stub)
    qtbot.addWidget(panel)
    index = _seed_versioned_record(panel, version=8, is_current=False)
    menu = panel._build_context_menu(index)
    assert _action_labels(menu) == ["Make Current", "View payload"]


# ---------------------------------------------------------------------------
# Sessions smoke test (lives here because Sessions has no panel-writes file)
# ---------------------------------------------------------------------------


def test_sessions_panel_right_click_invokes_context_menu_factory(
    qtbot, client_stub
):
    """Right-click on the SessionsPanel master view calls the factory."""
    from unittest.mock import patch

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QMenu

    panel = SessionsPanel(client=client_stub)
    qtbot.addWidget(panel)
    # Use return_value=QMenu() so the slot's blocking menu.exec() branch
    # (taken when the factory returns a non-empty menu) is skipped — the
    # smoke test only needs to confirm the factory is invoked.
    empty_menu = QMenu(panel)
    with patch.object(
        panel, "_build_context_menu", return_value=empty_menu
    ) as spy:
        panel._master_view.customContextMenuRequested.emit(QPoint(10, 10))
        assert spy.called
