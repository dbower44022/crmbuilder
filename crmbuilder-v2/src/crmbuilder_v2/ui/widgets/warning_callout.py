"""WarningCallout — inline panel-level warning row.

Single-row callout with leading Lucide icon and warning text per
design pass §2.9. Used for informational warnings (not hard
errors) — e.g., the Processes panel's soft-deleted-domain
message.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from crmbuilder_v2.ui.icons import lucide
from crmbuilder_v2.ui.styling import t


class WarningCallout(QWidget):
    """Inline warning row: Lucide icon + amber-toned label."""

    def __init__(
        self,
        text: str = "",
        *,
        icon_name: str = "circle-alert",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        space_2 = int(t("space.2").rstrip("px"))
        layout.setSpacing(space_2)

        self._icon_label = QLabel()
        self._icon_label.setPixmap(
            lucide(icon_name, size=14, color_token="color.warning.default")
                .pixmap(14, 14)
        )
        layout.addWidget(self._icon_label)

        self._text_label = QLabel(text)
        self._text_label.setObjectName("warningCalloutText")
        self._text_label.setWordWrap(True)
        layout.addWidget(self._text_label, stretch=1)

    def setText(self, text: str) -> None:
        self._text_label.setText(text)

    def text(self) -> str:
        return self._text_label.text()
