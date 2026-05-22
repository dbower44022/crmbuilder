"""Shared widget helpers for the v0.7 governance entity panels.

The six governance panels share enough detail-pane scaffolding (heading,
read-only line/text editors, separators, lifecycle-timestamp section) that
factoring the helpers here avoids ~30 lines of duplication per panel.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

LONG_TEXT_MIN_HEIGHT = 80
READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"


def heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def read_only_line(value: str, *, placeholder: str = "") -> QLineEdit:
    widget = QLineEdit()
    widget.setText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(READ_ONLY_STYLE)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def read_only_text(value: str, *, placeholder: str = "") -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(READ_ONLY_STYLE)
    widget.setMinimumHeight(LONG_TEXT_MIN_HEIGHT)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def lifecycle_timestamps_section(
    record: dict, label_field_pairs: list[tuple[str, str]]
) -> QWidget | None:
    """Return a section rendering non-null lifecycle timestamps, or None.

    ``label_field_pairs`` is a list of ``(display_label, record_field)``
    tuples in display order. Only fields whose value is non-null are
    rendered. Returns ``None`` if no timestamps are populated, so the
    caller can skip the section entirely on a fresh-status record.
    """
    items = [
        (label, record.get(field))
        for label, field in label_field_pairs
        if record.get(field)
    ]
    if not items:
        return None
    container = QWidget()
    layout = QFormLayout(container)
    layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    layout.setContentsMargins(0, 0, 0, 0)
    for label, value in items:
        ts_label = QLabel(str(value))
        ts_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        ts_label.setStyleSheet(READ_ONLY_STYLE)
        layout.addRow(label, ts_label)
    return container
