"""Startup splash screen.

Shown while the storage server is starting. Per DEC-023, the v2 UI
spawns ``crmbuilder-v2-api`` if no API responds to ``GET /health``; the
splash covers the wait. In slice A the splash is shown briefly as a
smoke check that it renders; lifecycle integration lands in slice B.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from crmbuilder_v2.ui.styling import (
    ACCENT_COLOR,
    DEFAULT_FONT_FAMILY,
)

_SPLASH_WIDTH = 400
_SPLASH_HEIGHT = 200
_SPLASH_MESSAGE = "Starting storage server…"


def _build_pixmap() -> QPixmap:
    pixmap = QPixmap(_SPLASH_WIDTH, _SPLASH_HEIGHT)
    pixmap.fill(QColor(ACCENT_COLOR))
    painter = QPainter(pixmap)
    try:
        painter.setPen(Qt.GlobalColor.white)
        font = QFont(DEFAULT_FONT_FAMILY, 14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, _SPLASH_MESSAGE)
    finally:
        painter.end()
    return pixmap


class Splash(QSplashScreen):
    """A simple colored splash with a centered message."""

    def __init__(self):
        super().__init__(_build_pixmap())
