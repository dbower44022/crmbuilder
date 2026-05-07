"""Subprocess-died banner.

Per PRD section 4.3 / DEC-023, when an owned API subprocess exits
unexpectedly the UI shows a non-modal banner across the top of the
main window with text "Storage server stopped." and a Reconnect
button. Clicking Reconnect emits ``reconnect_requested`` so the
main window can re-run the lifecycle probe-then-spawn sequence.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

_DEFAULT_MESSAGE = "Storage server stopped."
_BANNER_HEIGHT = 36
_BANNER_BACKGROUND = "#7A1F1F"


class CrashBanner(QWidget):
    """Non-modal banner shown when an owned API subprocess crashes."""

    reconnect_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("crashBanner")
        self.setFixedHeight(_BANNER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QWidget#crashBanner {{ background-color: {_BANNER_BACKGROUND}; }}"
            f"QWidget#crashBanner QLabel {{ color: white; font-weight: bold; }}"
            f"QWidget#crashBanner QPushButton {{"
            f" color: white; background-color: rgba(255, 255, 255, 0.15);"
            f" border: 1px solid white; padding: 2px 12px; border-radius: 3px;"
            f"}}"
            f"QWidget#crashBanner QPushButton:hover {{"
            f" background-color: rgba(255, 255, 255, 0.30);"
            f"}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(12)

        self._label = QLabel(_DEFAULT_MESSAGE)
        self._reconnect_button = QPushButton("Reconnect")
        self._reconnect_button.setCursor(self._reconnect_button.cursor())
        self._reconnect_button.clicked.connect(self._on_reconnect_clicked)

        layout.addWidget(self._label)
        layout.addStretch(1)
        layout.addWidget(self._reconnect_button)

        self.hide()

    def show_with_message(self, message: str | None = None) -> None:
        """Show the banner with the given message (or the default)."""
        self._label.setText(message or _DEFAULT_MESSAGE)
        self.show()

    def _on_reconnect_clicked(self) -> None:
        self.hide()
        self.reconnect_requested.emit()
