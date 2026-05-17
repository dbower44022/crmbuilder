"""Engagement picker dropdown popup.

Anchored below the top-strip. Lists live engagements first (ordered by
``engagement_last_opened_at`` descending), with the active engagement
pinned to the top of the live tier and marked with a check glyph.
Non-live engagements (``paused`` / ``archived``) follow in muted color.
Soft-deleted engagements are hidden. A footer "Manage engagements…"
row opens the management panel.

Emits :pyattr:`activation_requested(identifier)` when a non-active live
row is clicked, and :pyattr:`manage_requested` when the footer is clicked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.panels.engagements import (
    ACTIVE_GLYPH,
    format_relative_date,
)

_POPUP_BACKGROUND = "#FFFFFF"
_POPUP_BORDER = "#D7DBE3"  # color.neutral.200
_HOVER_BACKGROUND = "#F2F4F8"  # color.neutral.100
_MUTED_COLOR = "#888888"  # color.neutral.500


class EngagementPicker(QWidget):
    """Popup dropdown listing engagements + a Manage footer."""

    activation_requested = Signal(str)
    manage_requested = Signal()

    def __init__(
        self,
        engagements: list[dict[str, Any]],
        active_identifier: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("engagement_picker")
        self.setStyleSheet(
            f"#engagement_picker {{"
            f"  background-color: {_POPUP_BACKGROUND};"
            f"  border: 1px solid {_POPUP_BORDER};"
            f"}}"
        )

        self._active_identifier = active_identifier
        self._rows: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Two-tier ordering (slice D spec §2.2):
        #   1. Live engagements (status=active), with active engagement
        #      pinned at the top of the tier, then by last_opened desc.
        #   2. Non-live (paused/archived) at bottom, muted color.
        # Soft-deleted are filtered out entirely.
        live, non_live = _partition_engagements(engagements, active_identifier)

        for record in live:
            row = self._build_row(record, muted=False)
            layout.addWidget(row)
            self._rows.append(row)

        if live and non_live:
            layout.addWidget(_hairline())

        for record in non_live:
            row = self._build_row(record, muted=True)
            layout.addWidget(row)
            self._rows.append(row)

        # Footer divider + Manage engagements row.
        if live or non_live:
            layout.addWidget(_hairline())
        footer = QPushButton("Manage engagements…")
        footer.setObjectName("manage_engagements_button")
        footer.setFlat(True)
        footer.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.setStyleSheet(_row_style(muted=False))
        footer.clicked.connect(self._on_footer_clicked)
        layout.addWidget(footer)
        self._footer_button = footer

    def _build_row(
        self, record: dict[str, Any], *, muted: bool
    ) -> QPushButton:
        identifier = record.get("engagement_identifier") or ""
        code = record.get("engagement_code") or ""
        name = record.get("engagement_name") or "(unnamed)"
        is_active = identifier == self._active_identifier
        marker = ACTIVE_GLYPH if is_active else "  "
        button = QPushButton(f"{marker}{name} ({code})")
        button.setObjectName(f"engagement_row_{identifier}")
        button.setProperty("engagement_identifier", identifier)
        button.setFlat(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(_row_style(muted=muted))
        button.clicked.connect(
            lambda _checked=False, ident=identifier: self._on_row_clicked(ident)
        )
        return button

    def _on_row_clicked(self, identifier: str) -> None:
        # Clicking the active row just closes the picker.
        if identifier == self._active_identifier:
            self.close()
            return
        self.activation_requested.emit(identifier)
        self.close()

    def _on_footer_clicked(self) -> None:
        self.manage_requested.emit()
        self.close()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def show_below(self, anchor_widget: QWidget) -> None:
        """Position the picker just below ``anchor_widget`` and show it."""
        global_pos = anchor_widget.mapToGlobal(
            QPoint(0, anchor_widget.height())
        )
        self.adjustSize()
        self.setFixedWidth(anchor_widget.width())
        self.move(global_pos)
        self.show()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _partition_engagements(
    engagements: list[dict[str, Any]], active_identifier: str | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (live, non_live) per slice D §2.2 ordering rules."""
    live: list[dict[str, Any]] = []
    non_live: list[dict[str, Any]] = []
    for record in engagements:
        if record.get("engagement_deleted_at") is not None:
            continue
        status = record.get("engagement_status") or "active"
        if status == "active":
            live.append(record)
        else:
            non_live.append(record)
    epoch = datetime.fromtimestamp(0, UTC)

    def _sort_key(r: dict[str, Any]) -> float:
        raw = r.get("engagement_last_opened_at")
        if isinstance(raw, str):
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                return -epoch.timestamp()
        elif isinstance(raw, datetime):
            dt = raw
        else:
            dt = epoch
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return -dt.timestamp()

    live.sort(key=_sort_key)
    non_live.sort(key=_sort_key)

    # Pin the active engagement to the top of the live tier even if it
    # isn't the most-recently-opened (slice D §2.2 wording).
    if active_identifier is not None:
        for i, r in enumerate(live):
            if r.get("engagement_identifier") == active_identifier and i > 0:
                live.insert(0, live.pop(i))
                break

    return live, non_live


def _hairline() -> QFrame:
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.HLine)
    frame.setFixedHeight(1)
    frame.setStyleSheet(f"color: {_POPUP_BORDER}; background-color: {_POPUP_BORDER};")
    return frame


def _row_style(*, muted: bool) -> str:
    color = _MUTED_COLOR if muted else "#222222"
    return (
        "QPushButton {"
        f"  color: {color};"
        "  text-align: left;"
        "  padding: 6px 10px;"
        "  border: none;"
        "  background-color: transparent;"
        "}"
        f"QPushButton:hover {{ background-color: {_HOVER_BACKGROUND}; }}"
    )


# Re-export of the slice C helper so tests can verify date formatting
# without importing the panel.
_ = format_relative_date
