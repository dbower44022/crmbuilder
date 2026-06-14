"""Shared detail-pane widget helpers for the V2 entity panels.

Originally factored for the six v0.7 governance panels (heading, read-only
line/text editors, separators, lifecycle-timestamp section); the
``created_updated_section`` helper (PI-108) is shared by every first-class
entity panel — governance and methodology alike — so the module is now
general panel detail scaffolding rather than governance-specific.
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

from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp

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
    # REQ-134 (PI-175): a single-line read-only field truncates values too
    # long for its width. Mirror the full value into the tooltip so the
    # whole content is revealed on hover. Applies to every short read-only
    # field across all panels that use this helper.
    if value:
        widget.setToolTip(value)
    return widget


def read_only_text(value: str, *, placeholder: str = "") -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(READ_ONLY_STYLE)
    widget.setMinimumHeight(LONG_TEXT_MIN_HEIGHT)
    widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    if value:
        widget.setToolTip(value)
    return widget


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def created_updated_section(
    record: dict,
    created_field: str,
    updated_field: str | None = None,
) -> QWidget:
    """Return a 'Created' / 'Last Updated' audit-timestamp section (PI-108).

    Renders each value through :func:`format_timestamp` (local
    ``YYYY-MM-DD HH:MM``, em dash for missing/unparseable). ``created_field``
    / ``updated_field`` are the record's prefixed column keys (e.g.
    ``domain_created_at``). Pass ``updated_field=None`` for immutable /
    append-only types (deposit_event, topic, charter, status, …): the Last
    Updated row then renders ``—`` and the type keeps no ``updated_at``.
    """
    container = QWidget()
    layout = QFormLayout(container)
    layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    layout.setContentsMargins(0, 0, 0, 0)
    created = QLabel(format_timestamp(record.get(created_field)))
    created.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    created.setStyleSheet(READ_ONLY_STYLE)
    layout.addRow("Created", created)
    updated_value = record.get(updated_field) if updated_field else None
    updated = QLabel(format_timestamp(updated_value))
    updated.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    updated.setStyleSheet(READ_ONLY_STYLE)
    layout.addRow("Last Updated", updated)
    return container


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
