"""Data Browser main container (Section 14.8).

Registered as the "Data Browser" sidebar entry in RequirementsWindow.
Left-hand navigation tree + right-hand record detail / editor.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from automation.ui.browser.audit_trail import AuditTrail
from automation.ui.browser.browser_logic import BROWSABLE_TABLES
from automation.ui.browser.navigation_tree import NavigationTree
from automation.ui.browser.record_creator import RecordCreator
from automation.ui.browser.record_detail import RecordDetailView
from automation.ui.browser.record_editor import RecordEditor
from automation.ui.common.toast import show_toast

logger = logging.getLogger(__name__)

_IDX_EMPTY = 0
_IDX_DETAIL = 1
_IDX_EDITOR = 2
_IDX_CREATOR = 3
_IDX_AUDIT = 4


class BrowserView(QWidget):
    """The Data Browser — Section 14.8.

    :param parent: Parent widget.
    """

    # Signal for other views to navigate to a record
    navigate_to_record_requested = None  # set by RequirementsWindow

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._current_table: str | None = None
        self._current_id: int | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Left: navigation tree
        self._tree = NavigationTree()
        self._tree.record_selected.connect(self._on_record_selected)
        self._tree.setMaximumWidth(300)

        # Right: content stack
        self._right_stack = QStackedWidget()

        # Index 0: empty state
        empty = QLabel("Select a record from the tree to view its details.")
        empty.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 32px;"
        )
        self._right_stack.addWidget(empty)

        # Index 1: record detail
        self._detail = RecordDetailView()
        self._detail.navigate_to_record.connect(self._navigate_to)
        self._detail.edit_requested.connect(self._on_edit)
        self._detail.delete_requested.connect(self._on_delete_from_detail)
        self._detail.new_record_requested.connect(self._on_new_record)
        self._detail.history_requested.connect(self._on_history)
        self._right_stack.addWidget(self._detail)

        # Index 2: editor (created dynamically)
        self._editor_placeholder = QWidget()
        self._right_stack.addWidget(self._editor_placeholder)

        # Index 3: creator (created dynamically)
        self._creator_placeholder = QWidget()
        self._right_stack.addWidget(self._creator_placeholder)

        # Index 4: audit trail (created dynamically)
        self._audit_placeholder = QWidget()
        self._right_stack.addWidget(self._audit_placeholder)

        # Use splitter for resizable panels
        splitter = QSplitter()
        splitter.addWidget(self._tree)
        splitter.addWidget(self._right_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def refresh(self, conn: sqlite3.Connection) -> None:
        """Rebuild the tree and reset the detail area.

        :param conn: Client database connection.
        """
        self._conn = conn
        self._tree.refresh(conn)
        self._right_stack.setCurrentIndex(_IDX_EMPTY)

    def navigate_to(self, table_name: str, record_id: int) -> None:
        """Navigate to a specific record (called from other views).

        :param table_name: Table name.
        :param record_id: Record ID.
        """
        if self._conn:
            self._tree.select_record(table_name, record_id)
            self._on_record_selected(table_name, record_id)

    def _on_record_selected(self, table_name: str, record_id: int) -> None:
        """Handle tree selection change."""
        self._current_table = table_name
        self._current_id = record_id
        if self._conn:
            self._detail.load_record(self._conn, table_name, record_id)
            self._right_stack.setCurrentIndex(_IDX_DETAIL)

    def _navigate_to(self, table_name: str, record_id: int) -> None:
        """Navigate to a record (from FK link click)."""
        self._tree.select_record(table_name, record_id)
        self._on_record_selected(table_name, record_id)

    def _on_edit(self) -> None:
        """Switch to edit mode."""
        record = self._detail.current_record
        if not record or not self._conn:
            return

        # Replace editor placeholder
        old = self._right_stack.widget(_IDX_EDITOR)
        editor = RecordEditor(self._conn, record)
        editor.save_completed.connect(self._on_save_completed)
        editor.delete_completed.connect(self._on_delete_completed)
        editor.cancelled.connect(self._on_edit_cancelled)
        self._right_stack.removeWidget(old)
        old.deleteLater()
        self._right_stack.insertWidget(_IDX_EDITOR, editor)
        self._right_stack.setCurrentIndex(_IDX_EDITOR)

    def _on_delete_from_detail(self) -> None:
        """Handle delete request from detail view — route through editor."""
        record = self._detail.current_record
        if not record or not self._conn:
            return

        # Create a temporary editor to use its delete flow
        editor = RecordEditor(self._conn, record, parent=self)
        editor.delete_completed.connect(self._on_delete_completed)
        editor._on_delete()
        editor.deleteLater()

    def _on_save_completed(self) -> None:
        """Handle save completion — return to detail view."""
        if self._conn and self._current_table and self._current_id:
            self._detail.load_record(self._conn, self._current_table, self._current_id)
        self._right_stack.setCurrentIndex(_IDX_DETAIL)
        # Refresh tree in case names changed
        if self._conn:
            self._tree.refresh(self._conn)

    def _on_delete_completed(self) -> None:
        """Handle delete completion — return to empty state."""
        self._current_table = None
        self._current_id = None
        self._right_stack.setCurrentIndex(_IDX_EMPTY)
        if self._conn:
            self._tree.refresh(self._conn)

    def _on_edit_cancelled(self) -> None:
        """Handle edit cancellation — return to detail view."""
        self._right_stack.setCurrentIndex(_IDX_DETAIL)

    def _on_new_record(self) -> None:
        """Switch to create mode."""
        if not self._conn or not self._current_table:
            show_toast(self, "Select a table node in the tree first")
            return

        # Determine the table for new record creation
        # Use the current record's table
        table = self._current_table
        if table not in BROWSABLE_TABLES:
            show_toast(self, f"Cannot create records in {table}")
            return

        old = self._right_stack.widget(_IDX_CREATOR)
        creator = RecordCreator(
            self._conn, table,
            context_table=self._current_table,
            context_id=self._current_id,
        )
        creator.create_completed.connect(self._on_create_completed)
        creator.cancelled.connect(self._on_edit_cancelled)
        self._right_stack.removeWidget(old)
        old.deleteLater()
        self._right_stack.insertWidget(_IDX_CREATOR, creator)
        self._right_stack.setCurrentIndex(_IDX_CREATOR)

    def _on_create_completed(self, table_name: str, new_id: int) -> None:
        """Handle create completion — navigate to new record."""
        if self._conn:
            self._tree.refresh(self._conn)
        self._navigate_to(table_name, new_id)

    def _on_history(self) -> None:
        """Show audit trail for current record."""
        if not self._conn or not self._current_table or not self._current_id:
            return

        old = self._right_stack.widget(_IDX_AUDIT)
        audit = AuditTrail(self._conn, self._current_table, self._current_id)
        self._right_stack.removeWidget(old)
        old.deleteLater()
        self._right_stack.insertWidget(_IDX_AUDIT, audit)
        self._right_stack.setCurrentIndex(_IDX_AUDIT)
