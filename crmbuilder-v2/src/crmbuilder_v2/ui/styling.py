"""Minimal QSS stub per DEC-024.

Native Qt look across the application, with a small QSS layer applying
``#1F3864`` as accent color and Arial as the default font. Both come from
the v2 document standards so the v2 UI feels visually adjacent to the v2
documents it represents without committing to a full visual identity.
A real designed visual pass is deferred to v0.2 (or later).
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

ACCENT_COLOR = "#1F3864"
DEFAULT_FONT_FAMILY = "Arial"
DEFAULT_FONT_POINT_SIZE = 10

_QSS = f"""
* {{
    font-family: "{DEFAULT_FONT_FAMILY}";
    font-size: {DEFAULT_FONT_POINT_SIZE}pt;
}}

QListWidget::item:selected {{
    background-color: {ACCENT_COLOR};
    color: white;
}}

QPushButton:focus {{
    border: 1px solid {ACCENT_COLOR};
}}
"""


def apply_stylesheet(app: QApplication) -> None:
    app.setStyleSheet(_QSS)
