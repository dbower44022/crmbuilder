"""ChangeLog history panel (Section 14.8.7).

Shows ChangeLog entries for the selected record, ordered by timestamp descending.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from automation.ui.browser.browser_logic import ChangeLogEntry, load_change_log


class AuditTrail(QWidget):
    """Collapsible panel showing ChangeLog entries for a record.

    :param conn: Database connection.
    :param table_name: Table of the record.
    :param record_id: Record ID.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        record_id: int,
        parent=None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        header = QLabel(f"History — {table_name} #{record_id}")
        header.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1F3864; padding: 4px;"
        )
        layout.addWidget(header)

        entries = load_change_log(conn, table_name, record_id)

        if not entries:
            empty = QLabel("No history recorded")
            empty.setStyleSheet("color: #757575; padding: 8px;")
            layout.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content_layout = QVBoxLayout(content)
            content_layout.setContentsMargins(0, 0, 0, 0)

            for entry in entries:
                card = _ChangeLogCard(entry)
                content_layout.addWidget(card)

            content_layout.addStretch()
            scroll.setWidget(content)
            layout.addWidget(scroll, stretch=1)


class _ChangeLogCard(QWidget):
    """A single ChangeLog entry display."""

    def __init__(self, entry: ChangeLogEntry, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header: timestamp + change type + source
        header = QLabel(
            f"{entry.changed_at}  |  {entry.change_type}  |  {entry.source_label}"
        )
        header.setStyleSheet("font-size: 11px; font-weight: bold; color: #424242;")
        layout.addWidget(header)

        # Field detail (for updates)
        if entry.field_name:
            detail = QLabel(
                f"{entry.field_name}: {entry.old_value or '—'} → {entry.new_value or '—'}"
            )
            detail.setStyleSheet("font-size: 11px; color: #616161;")
            detail.setWordWrap(True)
            layout.addWidget(detail)

        # Rationale
        if entry.rationale:
            rationale = QLabel(f"Rationale: {entry.rationale}")
            rationale.setStyleSheet("font-size: 10px; color: #757575; font-style: italic;")
            rationale.setWordWrap(True)
            layout.addWidget(rationale)

        self.setStyleSheet(
            "background-color: #FAFAFA; border: 1px solid #E0E0E0; "
            "border-radius: 3px; margin: 2px 0;"
        )
