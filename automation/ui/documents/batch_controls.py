"""Batch regeneration controls (Section 14.7.5).

Multi-select and Regenerate Selected controls for the Documents view.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)

_SECONDARY_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)


class BatchControls(QWidget):
    """Batch regeneration controls.

    :param parent: Parent widget.
    """

    regenerate_selected = Signal()  # Emitted when Regenerate Selected is clicked
    select_all_stale = Signal()  # Emitted when Select All Stale is clicked

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._count_label = QLabel("0 selected")
        self._count_label.setStyleSheet("font-size: 12px; color: #757575;")
        layout.addWidget(self._count_label)

        self._select_stale_btn = QPushButton("Select All Stale")
        self._select_stale_btn.setStyleSheet(_SECONDARY_STYLE)
        self._select_stale_btn.clicked.connect(self.select_all_stale.emit)
        layout.addWidget(self._select_stale_btn)

        self._regenerate_btn = QPushButton("Regenerate Selected")
        self._regenerate_btn.setStyleSheet(_PRIMARY_STYLE)
        self._regenerate_btn.clicked.connect(self.regenerate_selected.emit)
        layout.addWidget(self._regenerate_btn)

        layout.addStretch()

        # Progress indicator (hidden by default)
        self._progress_label = QLabel()
        self._progress_label.setStyleSheet("font-size: 11px; color: #1565C0;")
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)

    def update_selection_count(self, count: int) -> None:
        """Update the selection count display.

        :param count: Number of selected documents.
        """
        self._count_label.setText(f"{count} selected")

    def set_progress(self, message: str) -> None:
        """Show a progress message during batch generation.

        :param message: Progress message.
        """
        self._progress_label.setText(message)
        self._progress_label.setVisible(bool(message))

    def show_summary(self, success: int, skipped: int, failures: int) -> None:
        """Show the batch summary.

        :param success: Number of successful generations.
        :param skipped: Number of skipped generations.
        :param failures: Number of failed generations.
        """
        parts = [f"{success} succeeded"]
        if skipped:
            parts.append(f"{skipped} skipped")
        if failures:
            parts.append(f"{failures} failed")
        self._progress_label.setText("Batch complete: " + ", ".join(parts))
        self._progress_label.setVisible(True)
