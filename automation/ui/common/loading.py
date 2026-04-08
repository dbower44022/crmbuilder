"""Loading state widgets (Section 14.10.10).

Spinner and placeholder for async data loading.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LoadingIndicator(QWidget):
    """A loading placeholder with a spinner-style message.

    :param message: Loading message to display.
    :param parent: Parent widget.
    """

    def __init__(self, message: str = "Loading...", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label = QLabel(message)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "color: #757575; font-size: 14px; padding: 20px;"
        )
        layout.addWidget(self._label)

    def set_message(self, message: str) -> None:
        """Update the loading message.

        :param message: New message text.
        """
        self._label.setText(message)
