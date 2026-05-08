"""Main window — sidebar + stacked content area, with crash banner.

Per DEC-021 the main window structure is a sidebar (left, fixed-width)
plus a ``QStackedWidget`` (right, swapping per selection). Slice B added
the lifecycle ownership and crash banner. Slice C threads the
``StorageClient`` through the constructor, replaces the Decisions
placeholder with a live ``DecisionsPanel``, and wires panel-level
``connection_lost`` to the same crash banner the lifecycle uses. Slice
D added Sessions and Risks. Slice E completes the round-2 read-only
panels: Charter, Status, Topics, Planning Items, References — every
sidebar entry now routes to a real panel.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.crash_banner import CrashBanner
from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle
from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES, Sidebar

_log = logging.getLogger("crmbuilder_v2.ui.main_window")
_DEFAULT_ENTRY = "Decisions"

# Maps reference ``entity_type`` values (as stored in the database) to
# sidebar entry labels so the navigation router can resolve cross-panel
# link clicks. References are not first-class navigable entities and so
# do not appear here.
ENTITY_TYPE_TO_SIDEBAR_LABEL: dict[str, str] = {
    "charter": "Charter",
    "status": "Status",
    "decision": "Decisions",
    "session": "Sessions",
    "risk": "Risks",
    "planning_item": "Planning Items",
    "topic": "Topics",
}


class MainWindow(QMainWindow):
    """Top-level window containing the crash banner, sidebar, and content stack."""

    def __init__(self, lifecycle: ServerLifecycle, client: StorageClient):
        super().__init__()
        self.setWindowTitle("CRMBuilder v2")
        self.resize(1200, 800)

        self._lifecycle = lifecycle
        self._client = client
        self._sidebar = Sidebar()
        self._stack = QStackedWidget()
        self._crash_banner = CrashBanner()
        self._pages_by_entry: dict[str, int] = {}

        for entry in SIDEBAR_ENTRIES:
            if entry == "Charter":
                page: QWidget = CharterPanel(self._client)
            elif entry == "Status":
                page = StatusPanel(self._client)
            elif entry == "Decisions":
                page = DecisionsPanel(self._client)
            elif entry == "Sessions":
                page = SessionsPanel(self._client)
            elif entry == "Risks":
                page = RisksPanel(self._client)
            elif entry == "Planning Items":
                page = PlanningItemsPanel(self._client)
            elif entry == "Topics":
                page = TopicsPanel(self._client)
            elif entry == "References":
                page = ReferencesPanel(self._client)
            else:
                placeholder = QLabel(
                    f"Panel for {entry} — not yet implemented."
                )
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setObjectName(
                    f"placeholder_{entry.lower().replace(' ', '_')}"
                )
                page = placeholder
            if isinstance(page, ListDetailPanel):
                page.connection_lost.connect(self._on_panel_connection_lost)
                page.navigate_requested.connect(self._on_navigate_requested)
            index = self._stack.addWidget(page)
            self._pages_by_entry[entry] = index

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._sidebar)
        content_layout.addWidget(self._stack, stretch=1)
        self._content_widget = content_widget

        container = QWidget()
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self._crash_banner)
        outer_layout.addWidget(content_widget, stretch=1)
        self.setCentralWidget(container)

        self._sidebar.selection_changed.connect(self._on_sidebar_selected)
        self._crash_banner.reconnect_requested.connect(self._on_reconnect_requested)
        self._lifecycle.ready.connect(self._on_lifecycle_ready)

        self._build_menu_bar()

        default_row = list(SIDEBAR_ENTRIES).index(_DEFAULT_ENTRY)
        self._sidebar.setCurrentRow(default_row)

    def handle_crash(self, stderr_text: str) -> None:
        """Slot for ``ServerLifecycle.crashed``: show banner, disable content."""
        if stderr_text:
            _log.warning(
                "Storage server stopped; captured output:\n%s", stderr_text
            )
        else:
            _log.warning("Storage server stopped (no captured output)")
        self._crash_banner.show_with_message("Storage server stopped.")
        self._set_content_enabled(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        try:
            self._lifecycle.terminate()
        except Exception:
            _log.exception("Lifecycle terminate failed during closeEvent")
        try:
            self._client.close()
        except Exception:
            _log.exception("StorageClient close failed during closeEvent")
        super().closeEvent(event)

    def _on_sidebar_selected(self, entry: str) -> None:
        index = self._pages_by_entry.get(entry)
        if index is not None:
            self._stack.setCurrentIndex(index)

    def _on_reconnect_requested(self) -> None:
        _log.info("Reconnect requested; restarting lifecycle")
        self._lifecycle.start()

    def _on_lifecycle_ready(self) -> None:
        # Fires on initial readiness AND on successful reconnect.
        if self._crash_banner.isVisible():
            self._crash_banner.hide()
        self._set_content_enabled(True)
        self._refresh_current_panel()

    def _on_panel_connection_lost(self, message: str) -> None:
        _log.warning("Panel reported connection lost: %s", message)
        self._crash_banner.show_with_message("Storage server unreachable.")
        self._set_content_enabled(False)

    def _on_navigate_requested(self, entity_type: str, identifier: str) -> None:
        """Route a panel-emitted link click to the appropriate sidebar entry."""
        label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type)
        if label is None or label not in self._pages_by_entry:
            _log.warning(
                "Navigation requested for unknown entity_type=%s identifier=%s",
                entity_type,
                identifier,
            )
            return
        index = self._pages_by_entry[label]
        target = self._stack.widget(index)
        # Switch the sidebar selection so it visually matches the swap;
        # this also routes through ``_on_sidebar_selected`` which sets
        # the stack page.
        try:
            row = list(SIDEBAR_ENTRIES).index(label)
        except ValueError:
            _log.warning("Sidebar entry %s missing from SIDEBAR_ENTRIES", label)
            return
        self._sidebar.setCurrentRow(row)
        if isinstance(target, ListDetailPanel):
            target.select_record_by_identifier(identifier)

    def _refresh_current_panel(self) -> None:
        widget = self._stack.currentWidget()
        if isinstance(widget, ListDetailPanel):
            widget.refresh()

    def _set_content_enabled(self, enabled: bool) -> None:
        self._sidebar.setEnabled(enabled)
        self._stack.setEnabled(enabled)

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.setEnabled(False)
        help_menu.addAction(about_action)
