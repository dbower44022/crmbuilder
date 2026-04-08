"""Post-commit review actions (Section 14.6.2).

Per-impact action controls: No Action Needed, Flag for Revision, Acknowledge.
All updates wrapped in transaction().
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from automation.ui.impact.impact_logic import ImpactDisplayRow, mark_impact_reviewed

_BTN_STYLE = (
    "QPushButton {{ background-color: {bg}; color: {fg}; "
    "border-radius: 3px; padding: 4px 8px; font-size: 10px; }} "
    "QPushButton:hover {{ background-color: {hover}; }}"
)

_NO_ACTION_STYLE = _BTN_STYLE.format(bg="#E8F5E9", fg="#2E7D32", hover="#C8E6C9")
_FLAG_STYLE = _BTN_STYLE.format(bg="#FFEBEE", fg="#C62828", hover="#FFCDD2")
_ACK_STYLE = _BTN_STYLE.format(bg="#E3F2FD", fg="#1565C0", hover="#BBDEFB")


class ReviewActions(QWidget):
    """Review action controls for a single ChangeImpact record.

    :param impact: The impact data.
    :param conn: Client database connection.
    :param parent: Parent widget.
    """

    reviewed = Signal(int, bool)  # (impact_id, action_required)

    def __init__(
        self,
        impact: ImpactDisplayRow,
        conn: sqlite3.Connection,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._impact = impact
        self._conn = conn

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if impact.reviewed:
            # Already reviewed — no actions
            return

        if impact.requires_review:
            # Two buttons: No Action Needed, Flag for Revision
            no_action_btn = QPushButton("No Action Needed")
            no_action_btn.setStyleSheet(_NO_ACTION_STYLE)
            no_action_btn.clicked.connect(lambda: self._do_review(False))
            layout.addWidget(no_action_btn)

            flag_btn = QPushButton("Flag for Revision")
            flag_btn.setStyleSheet(_FLAG_STYLE)
            flag_btn.clicked.connect(lambda: self._do_review(True))
            layout.addWidget(flag_btn)
        else:
            # One button: Acknowledge
            ack_btn = QPushButton("Acknowledge")
            ack_btn.setStyleSheet(_ACK_STYLE)
            ack_btn.clicked.connect(lambda: self._do_review(False))
            layout.addWidget(ack_btn)

    def _do_review(self, action_required: bool) -> None:
        """Execute the review action and update the database."""
        mark_impact_reviewed(self._conn, self._impact.id, action_required)
        self.reviewed.emit(self._impact.id, action_required)

        # Replace buttons with status text
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        from PySide6.QtWidgets import QLabel

        if action_required:
            label = QLabel("Flagged for Revision")
            label.setStyleSheet("font-size: 10px; color: #C62828; font-weight: bold;")
        else:
            label = QLabel("Reviewed — No Action Needed")
            label.setStyleSheet("font-size: 10px; color: #2E7D32; font-weight: bold;")
        self.layout().addWidget(label)
