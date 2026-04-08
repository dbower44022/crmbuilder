"""Toast notifications (Section 14.10.9).

Non-modal transient notifications that auto-dismiss.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


class Toast(QLabel):
    """A transient notification that auto-dismisses.

    :param message: The message to display.
    :param duration_ms: How long to show the toast (default 3000ms).
    :param parent: Parent widget.
    """

    def __init__(
        self, message: str, duration_ms: int = 3000, parent: QWidget | None = None
    ) -> None:
        super().__init__(message, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background-color: #323232; "
            "color: #FFFFFF; "
            "border-radius: 6px; "
            "padding: 10px 20px; "
            "font-size: 13px;"
        )
        self.setWindowFlags(
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self.adjustSize()
        QTimer.singleShot(duration_ms, self._dismiss)

    def show_at_bottom(self, parent: QWidget) -> None:
        """Position and show the toast at the bottom center of parent.

        :param parent: Widget to position relative to.
        """
        parent_rect = parent.rect()
        x = parent.mapToGlobal(parent_rect.center()).x() - self.width() // 2
        y = parent.mapToGlobal(parent_rect.bottomLeft()).y() - self.height() - 20
        self.move(x, y)
        self.show()

    def _dismiss(self) -> None:
        """Auto-dismiss the toast."""
        self.close()
        self.deleteLater()


def show_toast(
    parent: QWidget, message: str, duration_ms: int = 3000
) -> Toast:
    """Show a toast notification at the bottom of the parent widget.

    :param parent: Parent widget to position relative to.
    :param message: Message text.
    :param duration_ms: Duration in milliseconds.
    :returns: The Toast widget (for testing or early dismissal).
    """
    toast = Toast(message, duration_ms, parent)
    toast.show_at_bottom(parent)
    return toast
