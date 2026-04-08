"""Stage 1 — Receive (Section 14.5.2).

Large text area for pasting JSON output from AI session.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StageReceive(QWidget):
    """Stage 1 — Receive: paste JSON output.

    :param previous_raw_output: If the AISession already has raw_output from
        a previous attempt, offer to reload it.
    :param parent: Parent widget.
    """

    parse_requested = Signal(str)  # raw_text

    def __init__(self, previous_raw_output: str | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Reload notification
        if previous_raw_output:
            reload_bar = QWidget()
            reload_layout = QHBoxLayout(reload_bar)
            reload_layout.setContentsMargins(0, 0, 0, 4)
            msg = QLabel("Previous output found from a cancelled import.")
            msg.setStyleSheet("font-size: 11px; color: #E65100;")
            reload_layout.addWidget(msg)
            reload_btn = QPushButton("Reload")
            reload_btn.setStyleSheet("font-size: 11px;")
            reload_btn.clicked.connect(
                lambda: self._text_area.setPlainText(previous_raw_output)
            )
            reload_layout.addWidget(reload_btn)
            dismiss_btn = QPushButton("Start Fresh")
            dismiss_btn.setStyleSheet("font-size: 11px;")
            dismiss_btn.clicked.connect(reload_bar.hide)
            reload_layout.addWidget(dismiss_btn)
            reload_layout.addStretch()
            layout.addWidget(reload_bar)

        # Text area
        self._text_area = QPlainTextEdit()
        self._text_area.setPlaceholderText(
            "Paste the JSON output from your AI session"
        )
        self._text_area.setStyleSheet(
            "font-family: monospace; font-size: 12px; "
            "border: 1px solid #BDBDBD; border-radius: 4px; padding: 8px;"
        )
        layout.addWidget(self._text_area, stretch=1)

        # Error label (hidden initially)
        self._error_label = QLabel()
        self._error_label.setStyleSheet(
            "font-size: 11px; color: #C62828; padding: 4px 8px;"
        )
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Parse button
        parse_btn = QPushButton("Parse")
        parse_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "border-radius: 4px; padding: 8px 16px; font-size: 13px; } "
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        parse_btn.clicked.connect(self._on_parse)
        layout.addWidget(parse_btn)

    def _on_parse(self) -> None:
        """Validate input and emit parse_requested."""
        text = self._text_area.toPlainText().strip()
        if not text:
            self._error_label.setText(
                "No content to parse. Paste the JSON block from the AI session."
            )
            self._error_label.setVisible(True)
            return

        self._error_label.setVisible(False)
        self.parse_requested.emit(text)

    def get_text(self) -> str:
        """Return the current text content."""
        return self._text_area.toPlainText()
