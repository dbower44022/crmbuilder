"""Tests for the standalone non-modal detail-window manager (PI-121 / WTK-079).

The manager spawns one non-modal, persistent window per "Open <item type>"
invocation, hosting a factory-built ``ListDetailPanel`` pre-selected to the
target record. These tests use a stub panel (whose ``select_record_by_identifier``
records the call instead of firing a worker) and a stub factory so the manager
is exercised in isolation, off the network.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.detail_window_manager import (
    DetailWindowManager,
    StandaloneDetailWindow,
)
from PySide6.QtWidgets import QMainWindow, QWidget


class _StubPanel(ListDetailPanel):
    """Minimal real ``ListDetailPanel`` for the isinstance gate.

    Overrides ``select_record_by_identifier`` to record the identifier rather
    than trigger a refresh worker, so the manager can be tested synchronously.
    """

    def __init__(self, client):
        super().__init__(client)
        self.selected: list[str] = []

    def entity_title(self) -> str:
        return "Stub"

    def fetch_records(self):
        return []

    def list_columns(self):
        return [ColumnSpec("identifier", "Identifier")]

    def render_detail(self, record, extras):
        return QWidget()

    def select_record_by_identifier(self, identifier: str) -> bool:
        self.selected.append(identifier)
        return True


class _ParentWindow(QMainWindow):
    """Parent stub exposing the ``_on_panel_connection_lost`` forward target."""

    def __init__(self):
        super().__init__()
        self.connection_lost_messages: list[str] = []

    def _on_panel_connection_lost(self, message: str) -> None:
        self.connection_lost_messages.append(message)


def _make_manager(qtbot, *, factory=None):
    """Build a manager over stubs; return (manager, parent, panels, nav_calls).

    ``panels`` accumulates every panel the default factory builds (in order);
    ``nav_calls`` records ``navigate_router`` invocations.
    """
    parent = _ParentWindow()
    qtbot.addWidget(parent)
    panels: list[_StubPanel] = []
    nav_calls: list[tuple[str, str]] = []

    def default_factory(label, client):
        panel = _StubPanel(client)
        panels.append(panel)
        return panel

    manager = DetailWindowManager(
        client=MagicMock(),
        panel_factory=factory or default_factory,
        navigate_router=lambda t, i: nav_calls.append((t, i)),
        parent_window=parent,
    )
    return manager, parent, panels, nav_calls


def test_open_spawns_non_modal_preselected_window(qapp, qtbot):
    manager, _parent, panels, _nav = _make_manager(qtbot)
    window = manager.open("work_task", "WTK-001")
    assert isinstance(window, StandaloneDetailWindow)
    qtbot.addWidget(window)
    # Non-modal: shown with show(), so it is not modal and the originator stays
    # interactive.
    assert window.isVisible()
    assert window.isModal() is False
    # Central widget is the factory-built panel, pre-selected to the record.
    assert window.panel is panels[0]
    assert panels[0].selected == ["WTK-001"]
    # Title derived from the entity type + identifier.
    assert window.windowTitle() == "Work Task WTK-001"
    assert manager.open_windows == [window]


def test_multiple_windows_coexist_at_offset_positions(qapp, qtbot):
    manager, _parent, _panels, _nav = _make_manager(qtbot)
    first = manager.open("work_task", "WTK-001")
    second = manager.open("planning_item", "PI-007")
    qtbot.addWidget(first)
    qtbot.addWidget(second)
    assert first is not second
    assert len(manager.open_windows) == 2
    assert first.isVisible() and second.isVisible()
    # Cascade: the second window is offset from the first, not stacked exactly.
    assert second.pos() != first.pos()


def test_close_drops_reference(qapp, qtbot):
    manager, _parent, _panels, _nav = _make_manager(qtbot)
    window = manager.open("work_task", "WTK-001")
    assert window in manager.open_windows
    closed_args: list[object] = []
    window.closed.connect(closed_args.append)
    window.close()
    assert closed_args == [window]
    assert window not in manager.open_windows
    assert manager.open_windows == []


def test_unknown_type_noops(qapp, qtbot):
    manager, _parent, panels, _nav = _make_manager(qtbot)
    assert manager.open("nonsense", "X-1") is None
    # The factory was never reached and no window was tracked.
    assert panels == []
    assert manager.open_windows == []


def test_non_openable_type_noops(qapp, qtbot):
    # Factory returns a plain widget (e.g. Chat / a placeholder), not a panel.
    def factory(label, client):
        return QWidget()

    manager, _parent, _panels, _nav = _make_manager(qtbot, factory=factory)
    assert manager.open("work_task", "WTK-001") is None
    assert manager.open_windows == []


def test_standalone_navigate_routes_to_main_router(qapp, qtbot):
    manager, _parent, panels, nav = _make_manager(qtbot)
    window = manager.open("work_task", "WTK-001")
    qtbot.addWidget(window)
    # A "Go to" inside the standalone panel navigates the MAIN window.
    panels[0].navigate_requested.emit("decision", "DEC-009")
    assert nav == [("decision", "DEC-009")]


def test_standalone_open_spawns_sibling(qapp, qtbot):
    manager, _parent, _panels, _nav = _make_manager(qtbot)
    first = manager.open("work_task", "WTK-001")
    qtbot.addWidget(first)
    # An "Open" inside the standalone panel spawns a SIBLING window.
    first.panel.open_requested.emit("planning_item", "PI-003")
    assert len(manager.open_windows) == 2
    sibling = manager.open_windows[1]
    qtbot.addWidget(sibling)
    assert sibling.windowTitle() == "Planning Item PI-003"


def test_standalone_connection_lost_forwards_to_parent(qapp, qtbot):
    manager, parent, panels, _nav = _make_manager(qtbot)
    window = manager.open("work_task", "WTK-001")
    qtbot.addWidget(window)
    panels[0].connection_lost.emit("boom")
    assert parent.connection_lost_messages == ["boom"]
