"""Color-coded monospace output panel."""

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

COLOR_MAP: dict[str, str] = {
    "green": "#4CAF50",
    "red": "#F44336",
    "yellow": "#FFC107",
    "gray": "#9E9E9E",
    "white": "#D4D4D4",
}


class OutputPanel(QWidget):
    """Scrollable, read-only output panel with color-coded monospace text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the output panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Monospace", 10))
        self.text_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self.text_edit)

    def append_line(self, message: str, color: str = "white") -> None:
        """Append a color-coded line to the output.

        :param message: Text to display.
        :param color: Color key from COLOR_MAP.
        """
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        hex_color = COLOR_MAP.get(color, COLOR_MAP["white"])
        fmt.setForeground(QColor(hex_color))
        fmt.setFont(QFont("Monospace", 10))

        if not self.text_edit.document().isEmpty():
            cursor.insertText("\n", fmt)
        cursor.insertText(message, fmt)

        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def clear(self) -> None:
        """Clear all output text."""
        self.text_edit.clear()
