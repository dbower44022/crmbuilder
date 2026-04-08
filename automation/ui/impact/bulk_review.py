"""Bulk review controls (Section 14.6.3).

Bulk action bar for table groups with multiple unreviewed impacts.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from automation.ui.impact.impact_logic import (
    ImpactDisplayRow,
    mark_impacts_reviewed_bulk,
)


class BulkReviewBar(QWidget):
    """Bulk action bar for a table group.

    Shown when the group contains multiple unreviewed impacts.

    :param impacts: All impacts in this table group.
    :param conn: Client database connection.
    :param parent: Parent widget.
    """

    bulk_reviewed = Signal()  # Emitted after any bulk action

    def __init__(
        self,
        impacts: list[ImpactDisplayRow],
        conn: sqlite3.Connection,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn

        # Separate unreviewed requires-review and informational
        self._review_ids = [
            i.id for i in impacts if not i.reviewed and i.requires_review
        ]
        self._info_ids = [
            i.id for i in impacts if not i.reviewed and not i.requires_review
        ]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 8, 2)
        layout.setSpacing(8)

        # Only show if there are multiple unreviewed
        unreviewed_total = len(self._review_ids) + len(self._info_ids)
        if unreviewed_total < 2:
            self.setVisible(False)
            return

        label = QLabel("Bulk:")
        label.setStyleSheet("font-size: 10px; color: #757575;")
        layout.addWidget(label)

        if self._review_ids:
            btn = QPushButton(f"Mark All — No Action Needed ({len(self._review_ids)})")
            btn.setStyleSheet(
                "QPushButton { background-color: #E8F5E9; color: #2E7D32; "
                "border-radius: 3px; padding: 3px 8px; font-size: 10px; } "
                "QPushButton:hover { background-color: #C8E6C9; }"
            )
            btn.clicked.connect(self._mark_all_no_action)
            layout.addWidget(btn)

        if self._info_ids:
            btn = QPushButton(f"Mark All — Acknowledge ({len(self._info_ids)})")
            btn.setStyleSheet(
                "QPushButton { background-color: #E3F2FD; color: #1565C0; "
                "border-radius: 3px; padding: 3px 8px; font-size: 10px; } "
                "QPushButton:hover { background-color: #BBDEFB; }"
            )
            btn.clicked.connect(self._mark_all_acknowledge)
            layout.addWidget(btn)

        layout.addStretch()

    def _mark_all_no_action(self) -> None:
        mark_impacts_reviewed_bulk(self._conn, self._review_ids, action_required=False)
        self._review_ids.clear()
        self.bulk_reviewed.emit()

    def _mark_all_acknowledge(self) -> None:
        mark_impacts_reviewed_bulk(self._conn, self._info_ids, action_required=False)
        self._info_ids.clear()
        self.bulk_reviewed.emit()
