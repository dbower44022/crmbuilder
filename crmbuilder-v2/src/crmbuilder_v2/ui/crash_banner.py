"""Subprocess-died banner.

Per PRD section 4.3 / DEC-023, when an owned API subprocess exits
unexpectedly the UI shows a non-modal banner across the top of the
main window with text "Storage server stopped." and a Reconnect
button. Clicking Reconnect emits ``reconnect_requested`` so the
main window can re-run the lifecycle probe-then-spawn sequence.

v0.6 slice E (design pass §2.10) folds the banner into the design
system: danger-default background, white body-medium text, leading
Lucide circle-alert icon, padding 12px × 16px. The semi-transparent
white-on-color button styling is kept as per-widget setStyleSheet
inside this module — the banner is exceptional and doesn't fit any
of the five design-system button categories.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from crmbuilder_v2.ui.icons import lucide
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.selectable_text import (
    copy_to_clipboard,
    make_selectable,
)

_DEFAULT_MESSAGE = "Storage server stopped."


def _banner_button_style() -> str:
    """Build per-widget QSS for banner buttons.

    Semi-transparent white-on-color treatment per design pass §2.10.
    Not part of the five design-system button categories — the banner
    is exceptional, so this lives here rather than in styling.py.
    """
    neutral_0 = t("color.neutral.0")
    return f"""
        QPushButton {{
            background: rgba(255, 255, 255, 38);
            border: 1px solid rgba(255, 255, 255, 64);
            color: {neutral_0};
            padding: {t("space.1")} {t("space.3")};
            border-radius: {t("radius.subtle")};
            font-weight: {t("font.weight.medium")};
            min-width: 0;
        }}
        QPushButton:hover {{
            background: rgba(255, 255, 255, 76);
        }}
        QPushButton:pressed {{
            background: rgba(255, 255, 255, 115);
        }}
    """


class CrashBanner(QWidget):
    """Non-modal banner shown when an owned API subprocess crashes."""

    reconnect_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("crashBanner")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # setAutoFillBackground + palette make the danger background
        # render reliably on the top-level banner widget. QSS-only
        # backgrounds on top-level widgets can be ignored by Qt.
        self.setAutoFillBackground(True)
        palette = self.palette()
        from PySide6.QtGui import QColor
        palette.setColor(QPalette.ColorRole.Window, QColor(t("color.danger.default")))
        self.setPalette(palette)
        self.setStyleSheet(
            f"QWidget#crashBanner {{ background: {t('color.danger.default')}; }}"
        )

        space_3 = int(t("space.3").rstrip("px"))
        space_4 = int(t("space.4").rstrip("px"))
        space_2 = int(t("space.2").rstrip("px"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(space_4, space_3, space_4, space_3)
        layout.setSpacing(space_2)

        icon_label = QLabel()
        icon_label.setPixmap(
            lucide("circle-alert", size=16, color_token="color.neutral.0")
                .pixmap(16, 16)
        )
        layout.addWidget(icon_label)

        self._label = QLabel(_DEFAULT_MESSAGE)
        self._label.setStyleSheet(
            f"color: {t('color.neutral.0')};"
            f" font-size: {t('font.size.body')};"
            f" font-weight: {t('font.weight.medium')};"
        )
        # PI-124: let an operator select the banner text and copy the
        # full message (URL / attempt count / log path) into a bug report.
        make_selectable(self._label)
        layout.addWidget(self._label)

        layout.addStretch(1)

        # Explicit Copy affordance — the banner is not a QMessageBox, so
        # the native context-menu Copy isn't reliably available; a button
        # copies the current message text outright.
        self._copy_button = QPushButton("Copy")
        self._copy_button.setObjectName("crashBannerCopy")
        self._copy_button.setStyleSheet(_banner_button_style())
        self._copy_button.clicked.connect(self._on_copy_clicked)
        layout.addWidget(self._copy_button)

        self._reconnect_button = QPushButton("Reconnect")
        self._reconnect_button.setStyleSheet(_banner_button_style())
        self._reconnect_button.clicked.connect(self._on_reconnect_clicked)
        layout.addWidget(self._reconnect_button)

        self.hide()

    def show_with_message(self, message: str | None = None) -> None:
        """Show the banner with the given message (or the default)."""
        self._label.setText(message or _DEFAULT_MESSAGE)
        self.show()

    def _on_copy_clicked(self) -> None:
        """Copy the current banner message to the clipboard."""
        copy_to_clipboard(self._label.text())

    def _on_reconnect_clicked(self) -> None:
        self.hide()
        self.reconnect_requested.emit()
