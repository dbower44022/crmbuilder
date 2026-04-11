"""Deployment tab placeholder stub.

Renders a placeholder empty state until Prompt C replaces it with the
full Deployment tab implementation.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DeploymentTabStub(QWidget):
    """Placeholder widget for the Deployment tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        message = QLabel(
            "The Deployment tab will be rebuilt in a forthcoming release.\n\n"
            "Deployment, configuration, and verification are temporarily\n"
            "unavailable from main."
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet(
            "font-size: 16px; color: #757575; line-height: 1.6;"
        )
        layout.addWidget(message)
