"""Document inventory widget (Section 14.7.1).

Grouped list of all documents with sort order and staleness indicators.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from automation.ui.documents.document_row import DocumentRow
from automation.ui.documents.documents_logic import (
    DocumentEntry,
    DocumentStatus,
)


class DocumentInventory(QWidget):
    """Grouped list of all documents.

    :param parent: Parent widget.
    """

    generate_final_requested = Signal(int)  # work_item_id
    generate_draft_requested = Signal(int)  # work_item_id
    selection_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[DocumentRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._content)
        layout.addWidget(scroll, stretch=1)

    def update_entries(self, entries: list[DocumentEntry]) -> None:
        """Refresh the inventory with new entries.

        :param entries: Sorted document entries.
        """
        # Clear existing rows
        self._rows.clear()
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not entries:
            empty = QLabel("No documents found")
            empty.setStyleSheet("color: #757575; padding: 16px;")
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch()
            return

        for entry in entries:
            row = DocumentRow(entry)
            row.generate_final_requested.connect(self.generate_final_requested.emit)
            row.generate_draft_requested.connect(self.generate_draft_requested.emit)
            row.selection_changed.connect(self._on_selection_changed)
            self._rows.append(row)
            self._content_layout.addWidget(row)

        self._content_layout.addStretch()

    def get_selected_work_item_ids(self) -> list[int]:
        """Get the work item IDs of selected (checked) rows.

        :returns: List of selected work item IDs.
        """
        return [r.entry.work_item_id for r in self._rows if r.is_selected]

    def select_all_stale(self) -> None:
        """Check all stale document rows."""
        for row in self._rows:
            row.is_selected = row.entry.document_status == DocumentStatus.STALE

    def _on_selection_changed(self) -> None:
        """Handle a row's selection state change."""
        self.selection_changed.emit()
