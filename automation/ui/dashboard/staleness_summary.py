"""Staleness summary banner (Section 14.2.6).

Banner shown between summary bar and work queue when completed
work items have stale documents.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class StalenessSummaryBanner(QWidget):
    """Banner showing count of stale work items.

    :param parent: Parent widget.
    """

    view_stale_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self.setStyleSheet(
            "background-color: #FFF3E0; border-radius: 4px; margin: 4px 0px;"
        )

        self._icon = QLabel("!")
        self._icon.setStyleSheet(
            "font-weight: bold; color: #E65100; font-size: 14px; padding: 0px 4px;"
        )
        layout.addWidget(self._icon)

        self._label = QLabel()
        self._label.setStyleSheet("color: #E65100; font-size: 12px;")
        layout.addWidget(self._label)

        layout.addStretch()

        self._view_btn = QPushButton("View Stale Documents")
        self._view_btn.setStyleSheet(
            "color: #E65100; font-size: 11px; border: none; text-decoration: underline;"
        )
        self._view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_btn.clicked.connect(self.view_stale_clicked.emit)
        layout.addWidget(self._view_btn)

        self.setVisible(False)

    def update_count(self, count: int) -> None:
        """Update the staleness count and visibility.

        :param count: Number of stale work items.
        """
        if count > 0:
            self._label.setText(
                f"{count} completed work item{'s' if count != 1 else ''} "
                f"{'have' if count != 1 else 'has'} stale documents"
            )
            self.setVisible(True)
        else:
            self.setVisible(False)
