"""Action badge widget (Section 14.10.2).

Stub implementation for Step 15a — fully used in Steps 15b/15c.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class ActionBadge(QLabel):
    """A badge indicating an available or pending action.

    :param action_text: The action label.
    :param parent: Optional parent widget.
    """

    def __init__(self, action_text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if action_text:
            self.set_action(action_text)

    def set_action(self, action_text: str) -> None:
        """Update the badge text.

        :param action_text: The action label.
        """
        self.setText(f" {action_text} ")
        self.setStyleSheet(
            "background-color: #E8EAF6; "
            "color: #283593; "
            "border-radius: 4px; "
            "padding: 2px 8px; "
            "font-size: 11px;"
        )
