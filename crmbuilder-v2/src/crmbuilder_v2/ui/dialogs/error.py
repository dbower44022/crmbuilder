"""Generic error dialog.

Wired in slice G. Used by the create/edit/delete flows for unexpected
errors that don't map to inline field validation (5xx, 422, no-field
400, and unexpected exceptions).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.elevation import apply_dialog_shadow
from crmbuilder_v2.ui.icons import lucide
from crmbuilder_v2.ui.widgets.modal_backdrop import attach as _backdrop_attach
from crmbuilder_v2.ui.widgets.modal_backdrop import detach as _backdrop_detach


class ErrorDialog(QDialog):
    """Generic modal error dialog.

    Used by the decision dialogs for:

    * 5xx ``ServerError`` responses
    * 422 ``RequestShapeError`` responses (programmer error)
    * Any 400/409 where the API's error envelope does NOT carry a
      ``field`` key
    * Any unexpected exception caught while submitting
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
        apply_dialog_shadow(self)
        self._detail_widget: QPlainTextEdit | None = None
        self._detail_button: QPushButton | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)

        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(
            lucide("circle-x", size=18, color_token="color.danger.default")
                .pixmap(18, 18)
        )
        header_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        title_label = QLabel(title)
        title_label.setObjectName("errorDialogHeader")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label, stretch=1)

        outer.addWidget(header_row)

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

    # ------------------------------------------------------------------
    # Modal backdrop hooks (v0.6 slice A — DEC-091)
    # ------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802 — Qt naming
        super().showEvent(event)
        _backdrop_attach(self)

    def hideEvent(self, event):  # noqa: N802 — Qt naming
        _backdrop_detach(self)
        super().hideEvent(event)
