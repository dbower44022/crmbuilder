"""Conflict severity indicators (Section 14.10.3).

Stub implementation for Step 15a — fully used in Steps 15b/15c.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class SeverityIndicator(QLabel):
    """A colored indicator for conflict severity.

    :param severity: e.g. "high", "medium", "low".
    :param parent: Optional parent widget.
    """

    SEVERITY_COLORS: dict[str, dict[str, str]] = {
        "high": {"bg": "#FFCDD2", "fg": "#B71C1C"},
        "medium": {"bg": "#FFE0B2", "fg": "#E65100"},
        "low": {"bg": "#FFF9C4", "fg": "#F57F17"},
    }

    def __init__(self, severity: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if severity:
            self.set_severity(severity)

    def set_severity(self, severity: str) -> None:
        """Update the indicator.

        :param severity: Severity level string.
        """
        colors = self.SEVERITY_COLORS.get(
            severity, {"bg": "#E0E0E0", "fg": "#616161"}
        )
        self.setText(f" {severity.title()} ")
        self.setStyleSheet(
            f"background-color: {colors['bg']}; "
            f"color: {colors['fg']}; "
            f"border-radius: 4px; "
            f"padding: 2px 6px; "
            f"font-size: 11px;"
        )
