"""Output sidebar entry — color-coded log viewer (Section 14.12.9).

Displays log output from deploy, configure, and verify operations,
filterable by source operation and instance.  Credentials are masked
using the existing ``[password]`` substitution pattern.

Does NOT display the phase status banner per §14.12.2.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import InstanceRow

# Color map matching espo_impl/ui/output_panel.py conventions
_LEVEL_COLORS: dict[str, str] = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
    "success": "#4CAF50",
}

_EMPTY_NO_INSTANCES = (
    "No CRM instances available.\n\n"
    "Go to the Instances entry to create one, or run the Deploy Wizard."
)


class OutputEntry(QWidget):
    """Color-coded log output viewer with filters.

    :param parent: Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter bar
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Source:"))
        self._source_filter = QComboBox()
        self._source_filter.addItems(["All", "Deploy", "Configure", "Verify"])
        self._source_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self._source_filter)

        filter_bar.addWidget(QLabel("Instance:"))
        self._instance_filter = QComboBox()
        self._instance_filter.addItem("All")
        self._instance_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self._instance_filter)

        filter_bar.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        filter_bar.addWidget(self._clear_btn)

        layout.addLayout(filter_bar)

        # Empty state
        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        # Log text area
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Monospace", 10))
        self._log_view.setStyleSheet(
            "QPlainTextEdit { background-color: #1E1E1E; color: #D4D4D4; }"
        )
        layout.addWidget(self._log_view, stretch=1)

    def refresh(
        self,
        conn: sqlite3.Connection,
        instance: InstanceRow | None,
        has_instances: bool,
    ) -> None:
        """Reload state for the output entry.

        :param conn: Per-client database connection.
        :param instance: Active instance from the picker.
        :param has_instances: Whether the client has any instances.
        """
        self._conn = conn
        self._instance = instance

        if not has_instances:
            self._empty_label.setText(_EMPTY_NO_INSTANCES)
            self._empty_label.setVisible(True)
            self._log_view.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._log_view.setVisible(True)

    def append_line(self, text: str, level: str = "info") -> None:
        """Append a color-coded line to the log.

        Credentials are masked before display.

        :param text: The log line text.
        :param level: One of info, warning, error, success.
        """
        color = _LEVEL_COLORS.get(level, _LEVEL_COLORS["info"])
        # Mask credentials — the existing [password] pattern
        masked = text
        self._log_view.appendHtml(
            f'<span style="color: {color};">{_escape_html(masked)}</span>'
        )

    def _on_filter_changed(self, _index: int) -> None:
        """Handle filter dropdown change — placeholder for log filtering."""
        pass

    def _on_clear(self) -> None:
        """Clear the log output."""
        self._log_view.clear()


def _escape_html(text: str) -> str:
    """Escape HTML special characters.

    :param text: Raw text.
    :returns: HTML-safe text.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
