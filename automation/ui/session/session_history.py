"""Session history panel (Section 14.4.5).

Shows prior AISession records for the current work item.
Reuses SessionRow from work_item_logic and SessionCard from tab_sessions.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from automation.ui.work_item.tab_sessions import SessionCard
from automation.ui.work_item.work_item_logic import SessionRow


class SessionHistory(QWidget):
    """Previous sessions panel — visible when prior sessions exist.

    :param sessions: List of SessionRow objects.
    :param parent: Parent widget.
    """

    def __init__(self, sessions: list[SessionRow], parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)

        if not sessions:
            self.setVisible(False)
            return

        header = QLabel(f"Previous Sessions ({len(sessions)})")
        header.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1F3864; padding: 4px 0;"
        )
        layout.addWidget(header)

        for session in sessions:
            layout.addWidget(SessionCard(session))

        layout.addStretch()
