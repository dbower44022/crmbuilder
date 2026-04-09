"""Expandable staleness summary per document row (Section 14.7.2).

Shows change count and summary, expandable to individual ChangeLog entries.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from automation.ui.documents.documents_logic import DocumentEntry


class StalenessExpansion(QWidget):
    """Expandable staleness detail below a stale document row.

    :param entry: The stale document entry.
    :param parent: Parent widget.
    """

    def __init__(self, entry: DocumentEntry, parent=None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 0, 8, 4)

        # Summary line
        summary_row = QWidget()
        from PySide6.QtWidgets import QHBoxLayout
        summary_layout = QHBoxLayout(summary_row)
        summary_layout.setContentsMargins(0, 0, 0, 0)

        count_label = QLabel(
            f"{entry.change_count} change{'s' if entry.change_count != 1 else ''} "
            f"since last generation"
        )
        count_label.setStyleSheet("font-size: 11px; color: #E65100;")
        summary_layout.addWidget(count_label)

        self._toggle_btn = QPushButton("Show Details")
        self._toggle_btn.setStyleSheet(
            "font-size: 10px; border: none; color: #1565C0; "
            "text-decoration: underline; padding: 0;"
        )
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        summary_layout.addWidget(self._toggle_btn)
        summary_layout.addStretch()

        layout.addWidget(summary_row)

        # Change summary (collapsed by default)
        self._detail_widget = QLabel(entry.change_summary)
        self._detail_widget.setStyleSheet(
            "font-size: 10px; color: #757575; padding: 4px 0;"
        )
        self._detail_widget.setWordWrap(True)
        self._detail_widget.setVisible(False)
        layout.addWidget(self._detail_widget)

    def _toggle(self) -> None:
        """Toggle the expanded state."""
        self._expanded = not self._expanded
        self._detail_widget.setVisible(self._expanded)
        self._toggle_btn.setText("Hide Details" if self._expanded else "Show Details")
