"""Top-strip widget showing the active engagement and opening the picker.

Lives above the sidebar groups inside the sidebar container. Always
visible. Subscribes to :class:`ActiveEngagementContext.active_engagement_changed`
and re-renders on every change. Clicking anywhere on the strip opens
the picker dropdown (slice D step 2).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext

_STRIP_HEIGHT = 48
_STRIP_BACKGROUND = "#F2F4F8"  # color.neutral.100 stand-in
_STRIP_BORDER_BOTTOM = "#D7DBE3"  # color.neutral.200 stand-in
_CODE_COLOR = "#888888"  # color.neutral.500 stand-in
_PLACEHOLDER_COLOR = "#888888"

_CHEVRON_GLYPH = "▾"


class EngagementTopStrip(QWidget):
    """Active-engagement display + chevron, click to open picker.

    Emits :pyattr:`clicked` when the user activates the strip; the
    sidebar wiring connects this to the picker dropdown's show method.
    """

    clicked = Signal()

    def __init__(
        self,
        active_context: ActiveEngagementContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._active_context = active_context
        self.setObjectName("engagement_top_strip")
        self.setFixedHeight(_STRIP_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "#engagement_top_strip {"
            f"  background-color: {_STRIP_BACKGROUND};"
            f"  border-bottom: 1px solid {_STRIP_BORDER_BOTTOM};"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._label = QLabel("")
        self._label.setObjectName("engagement_top_strip_label")
        self._label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._label, stretch=1)

        self._chevron = QLabel(_CHEVRON_GLYPH)
        self._chevron.setObjectName("engagement_top_strip_chevron")
        font = QFont(self._chevron.font())
        font.setBold(True)
        self._chevron.setFont(font)
        layout.addWidget(self._chevron)

        active_context.active_engagement_changed.connect(self._on_engagement_changed)
        self._render(active_context.engagement())

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, engagement) -> None:
        if engagement is None:
            self._label.setText(
                f'<span style="color:{_PLACEHOLDER_COLOR};">No engagement selected</span>'
            )
            return
        name = engagement.engagement_name or "(unnamed)"
        code = engagement.engagement_code or ""
        self._label.setText(
            f'<span>{_escape(name)}</span> '
            f'<span style="color:{_CODE_COLOR}; font-size:90%;">'
            f"({_escape(code)})</span>"
        )

    def _on_engagement_changed(self, engagement) -> None:
        self._render(engagement)

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
