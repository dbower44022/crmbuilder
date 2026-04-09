"""Work Item Detail container (Section 14.3).

Persistent header + tabbed detail area with four tabs.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from automation.ui.mode_integration.deployment_guidance import (
    get_guidance_message,
)
from automation.ui.work_item.header import WorkItemHeader
from automation.ui.work_item.header_actions import HeaderActions
from automation.ui.work_item.tab_dependencies import DependenciesTab
from automation.ui.work_item.tab_documents import DocumentsTab
from automation.ui.work_item.tab_impacts import ImpactsTab
from automation.ui.work_item.tab_sessions import SessionsTab
from automation.ui.work_item.work_item_logic import (
    load_dependencies,
    load_documents,
    load_impacts,
    load_sessions,
    load_work_item,
)


class WorkItemDetailView(QWidget):
    """The Work Item Detail view — Section 14.3.

    :param parent: Parent widget.
    """

    navigate_to_item = Signal(int)
    item_changed = Signal()  # Emitted after a state-changing action

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._work_item_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        self._header = WorkItemHeader()
        layout.addWidget(self._header)

        # Action buttons
        self._actions = HeaderActions()
        self._actions.action_completed.connect(self._on_action_completed)
        layout.addWidget(self._actions)

        # Deployment guidance banner (hidden by default)
        self._guidance_banner = QLabel()
        self._guidance_banner.setStyleSheet(
            "font-size: 12px; color: #1565C0; background-color: #E3F2FD; "
            "padding: 10px; border-radius: 4px; margin: 4px 8px;"
        )
        self._guidance_banner.setWordWrap(True)
        self._guidance_banner.setVisible(False)
        layout.addWidget(self._guidance_banner)

        # Tabbed area
        self._tabs = QTabWidget()
        self._dep_tab = DependenciesTab()
        self._dep_tab.navigate_to_item.connect(self.navigate_to_item.emit)
        self._session_tab = SessionsTab()
        self._doc_tab = DocumentsTab()
        self._impact_tab = ImpactsTab()

        self._tabs.addTab(self._dep_tab, "Dependencies")
        self._tabs.addTab(self._session_tab, "Sessions")
        self._tabs.addTab(self._doc_tab, "Documents")
        self._tabs.addTab(self._impact_tab, "Impacts")

        layout.addWidget(self._tabs, stretch=1)

    def load_item(self, work_item_id: int, conn: sqlite3.Connection) -> None:
        """Load and display a work item.

        :param work_item_id: The work item ID.
        :param conn: Client database connection.
        """
        self._conn = conn
        self._work_item_id = work_item_id
        self._refresh()

    def _refresh(self) -> None:
        """Reload all data for the current work item."""
        if not self._conn or not self._work_item_id:
            return

        item = load_work_item(self._conn, self._work_item_id)
        if not item:
            return

        self._header.update_item(item)
        self._actions.set_context(item, self._conn)

        # Deployment guidance (Section 14.9.2)
        guidance = get_guidance_message(item.item_type)
        if guidance:
            self._guidance_banner.setText(guidance)
            self._guidance_banner.setVisible(True)
        else:
            self._guidance_banner.setVisible(False)

        # Dependencies
        deps = load_dependencies(self._conn, self._work_item_id)
        self._dep_tab.update_dependencies(deps, item.status)

        # Sessions
        sessions = load_sessions(self._conn, self._work_item_id)
        self._session_tab.update_sessions(sessions, self._work_item_id)

        # Documents
        docs = load_documents(self._conn, self._work_item_id)
        self._doc_tab.update_documents(docs, work_item_id=self._work_item_id)

        # Impacts
        impacts = load_impacts(self._conn, self._work_item_id)
        self._impact_tab.update_impacts(impacts)

    def _on_action_completed(self) -> None:
        """Refresh after a state-changing action."""
        self._refresh()
        self.item_changed.emit()
