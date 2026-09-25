"""Top-strip widget showing the active application and opening the picker.

Lives above the sidebar groups inside the sidebar container. Always
visible. Subscribes to :class:`ActiveEngagementContext.active_engagement_changed`
and re-renders on every change. Clicking anywhere on the strip opens
the picker dropdown (slice D step 2).

PI-512 (REQ-589, DEC-1092) and PI-580 (REQ-653, DEC-1155): when a
``client_name_lookup`` is supplied, the strip names the application and the
client that defines it, "Name (CODE) · defined by Client", and the application
alone when no client defines it. The lookup takes the application's
identifier (the engagement row's ``ENG-NNN``) and returns the client name or
``None``; a failing lookup renders the application alone.
"""

from __future__ import annotations

from collections.abc import Callable

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
DEFINED_BY = " · defined by "
PLACEHOLDER_TEXT = "No application selected"


class EngagementTopStrip(QWidget):
    """Active-application display + chevron, click to open picker.

    Emits :pyattr:`clicked` when the user activates the strip; the
    sidebar wiring connects this to the picker dropdown's show method.
    """

    clicked = Signal()

    def __init__(
        self,
        active_context: ActiveEngagementContext,
        parent: QWidget | None = None,
        client_name_lookup: Callable[[str], str | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._active_context = active_context
        self._client_name_lookup = client_name_lookup
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
                f'<span style="color:{_PLACEHOLDER_COLOR};">{PLACEHOLDER_TEXT}</span>'
            )
            return
        name = engagement.engagement_name or "(unnamed)"
        code = engagement.engagement_code or ""
        client_name = self._primary_client_name(engagement.engagement_identifier)
        suffix = (
            f'<span style="color:{_CODE_COLOR};">{_escape(DEFINED_BY)}</span>'
            f"<span>{_escape(client_name)}</span>"
            if client_name
            else ""
        )
        self._label.setText(
            f'<span>{_escape(name)}</span> '
            f'<span style="color:{_CODE_COLOR}; font-size:90%;">'
            f"({_escape(code)})</span>{suffix}"
        )

    def _primary_client_name(self, engagement_identifier: str | None) -> str | None:
        if self._client_name_lookup is None or not engagement_identifier:
            return None
        try:
            value = self._client_name_lookup(engagement_identifier)
        except Exception:  # noqa: BLE001 - the strip must render whatever the store says
            return None
        return value or None

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
