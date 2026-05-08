"""Minimal QSS stub per DEC-024.

Native Qt look across the application, with a small QSS layer applying
``#1F3864`` as accent color and Arial as the default font. Both come from
the v2 document standards so the v2 UI feels visually adjacent to the v2
documents it represents without committing to a full visual identity.
A full designed visual pass is deferred to v0.2 (or later).

Slice H refined the stub for consistency: navy accent on selection
highlights and focus borders, deep red for inline error labels, and
Arial 10pt as the global default. Inline error labels in the decision
dialogs use ``ERROR_TEXT_COLOR`` directly via setStyleSheet — they are
authored in QLabel.setStyleSheet so a single rule suffices here for
documentation only.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

ACCENT_COLOR = "#1F3864"
ACCENT_HOVER = "#2A4880"
ERROR_TEXT_COLOR = "#B22222"
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

QListWidget::item:hover {{
    background-color: #E8ECF5;
}}

QTableView {{
    selection-background-color: {ACCENT_COLOR};
    selection-color: white;
    alternate-background-color: #F5F7FB;
}}

QTableView QHeaderView::section {{
    background-color: #E8ECF5;
    padding: 4px 8px;
    border: 0;
    border-bottom: 1px solid #C0C7D6;
    font-weight: bold;
}}

QPushButton:focus {{
    border: 1px solid {ACCENT_COLOR};
    outline: none;
}}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT_COLOR};
}}

QLabel[role="error"] {{
    color: {ERROR_TEXT_COLOR};
}}
"""


def apply_stylesheet(app: QApplication) -> None:
    app.setStyleSheet(_QSS)
