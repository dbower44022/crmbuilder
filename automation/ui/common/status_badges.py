"""Status badge widget (Section 14.10.1).

Renders a colored badge for work item statuses.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

# Status colors — derived from the project's existing palette
# with distinct colors for each workflow state.
STATUS_COLORS: dict[str, dict[str, str]] = {
    "not_started": {"bg": "#E0E0E0", "fg": "#616161", "label": "Not Started"},
    "ready": {"bg": "#E3F2FD", "fg": "#1565C0", "label": "Ready"},
    "in_progress": {"bg": "#FFF3E0", "fg": "#E65100", "label": "In Progress"},
    "complete": {"bg": "#E8F5E9", "fg": "#2E7D32", "label": "Complete"},
    "blocked": {"bg": "#FFEBEE", "fg": "#C62828", "label": "Blocked"},
}


class StatusBadge(QLabel):
    """A colored badge showing a work item status.

    :param status: One of not_started, ready, in_progress, complete, blocked.
    :param parent: Optional parent widget.
    """

    def __init__(self, status: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if status:
            self.set_status(status)

    def set_status(self, status: str) -> None:
        """Update the badge to reflect a new status.

        :param status: The status string.
        """
        colors = STATUS_COLORS.get(status, STATUS_COLORS["not_started"])
        self.setText(f" {colors['label']} ")
        self.setStyleSheet(
            f"background-color: {colors['bg']}; "
            f"color: {colors['fg']}; "
            f"border-radius: 4px; "
            f"padding: 2px 8px; "
            f"font-weight: bold; "
            f"font-size: 11px;"
        )
