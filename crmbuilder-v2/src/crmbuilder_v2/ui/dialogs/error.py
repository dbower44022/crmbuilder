"""Generic error dialog.

Wired in slice G. Used by the create/edit/delete flows for unexpected
errors that don't map to inline field validation (5xx, 422, no-field
400, and unexpected exceptions).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_BANNER_STYLE = "color: #1F3864; font-weight: bold;"


class ErrorDialog(QDialog):
    """Generic modal error dialog.

    Used by the decision dialogs for:

    * 5xx ``ServerError`` responses
    * 422 ``RequestShapeError`` responses (programmer error)
    * Any 400/409 where the API's error envelope does NOT carry a
      ``field`` key
    * Any unexpected exception caught while submitting

    Constructor signature is intentionally permissive so dialogs can
    pass through whatever they have.
    """

    def __init__(
        self,
        title: str,
        message: str,
        detail: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._detail_widget: QPlainTextEdit | None = None
        self._detail_button: QPushButton | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title_label = QLabel(title)
        title_font = QFont(title_label.font())
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title_label.setFont(title_font)
        title_label.setStyleSheet(_BANNER_STYLE)
        outer.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setMinimumWidth(360)
        message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        outer.addWidget(message_label)

        if detail:
            self._detail_button = QPushButton("Show details")
            self._detail_button.setCheckable(True)
            self._detail_button.setObjectName("error_detail_toggle")
            outer.addWidget(self._detail_button, alignment=Qt.AlignmentFlag.AlignLeft)

            self._detail_widget = QPlainTextEdit(detail)
            self._detail_widget.setReadOnly(True)
            self._detail_widget.setObjectName("error_detail_text")
            self._detail_widget.setMinimumHeight(100)
            self._detail_widget.setVisible(False)
            outer.addWidget(self._detail_widget)

            self._detail_button.toggled.connect(self._on_detail_toggled)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        outer.addWidget(button_box)

    def _on_detail_toggled(self, checked: bool) -> None:
        if self._detail_widget is None or self._detail_button is None:
            return
        self._detail_widget.setVisible(checked)
        self._detail_button.setText("Hide details" if checked else "Show details")
