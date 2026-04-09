"""Collapsible groups of FK back-references (Section 14.8.2).

Shows records that reference the currently selected record.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.browser.browser_logic import RelatedGroup


class RelatedRecordsPanel(QWidget):
    """Collapsible panel showing records that reference the current record.

    :param group: Related records group data.
    :param conn: Database connection (for display column resolution).
    :param parent: Parent widget.
    """

    navigate_to_record = Signal(str, int)  # table_name, record_id

    def __init__(
        self, group: RelatedGroup, conn: sqlite3.Connection, parent=None
    ) -> None:
        super().__init__(parent)
        self._group = group
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)

        # Header with count and toggle
        header = QPushButton(
            f"▼ {group.table_name} via {group.fk_column} ({len(group.records)})"
        )
        header.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #1F3864; "
            "border: none; text-align: left; padding: 4px;"
        )
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.clicked.connect(self._toggle)
        layout.addWidget(header)
        self._header = header

        # Records container
        self._records_widget = QWidget()
        records_layout = QVBoxLayout(self._records_widget)
        records_layout.setContentsMargins(16, 0, 0, 0)

        for record in group.records:
            record_id = record.get("id")
            display_value = record.get(group.display_column, f"#{record_id}")
            link = QPushButton(f"{display_value} (#{record_id})")
            link.setStyleSheet(
                "font-size: 11px; border: none; color: #1565C0; "
                "text-decoration: underline; padding: 2px 0; text-align: left;"
            )
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            table = group.table_name
            rid = record_id
            link.clicked.connect(
                lambda checked, t=table, i=rid: self.navigate_to_record.emit(t, i)
            )
            records_layout.addWidget(link)

        layout.addWidget(self._records_widget)

    def _toggle(self) -> None:
        """Toggle expanded/collapsed state."""
        self._expanded = not self._expanded
        self._records_widget.setVisible(self._expanded)
        prefix = "▼" if self._expanded else "▶"
        g = self._group
        self._header.setText(
            f"{prefix} {g.table_name} via {g.fk_column} ({len(g.records)})"
        )
