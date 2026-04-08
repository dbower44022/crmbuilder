"""Stage 2 — Parse (Section 14.5.3).

Displays parse errors with line/character position information.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StageParse(QWidget):
    """Stage 2 — Parse error display.

    Only shown when a parse error occurs. Success auto-advances.

    :param error_message: The parse error description.
    :param parent: Parent widget.
    """

    retry_requested = Signal = None  # Set externally

    def __init__(self, error_message: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Parse Error")
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #C62828; padding: 8px 0;"
        )
        layout.addWidget(header)

        error_label = QLabel(error_message)
        error_label.setStyleSheet(
            "font-size: 12px; color: #C62828; padding: 8px; "
            "background-color: #FFEBEE; border-radius: 4px;"
        )
        error_label.setWordWrap(True)
        layout.addWidget(error_label)

        hint = QLabel(
            "You can edit the pasted text and retry parsing, or cancel the import."
        )
        hint.setStyleSheet("font-size: 11px; color: #757575; padding: 4px 8px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()
