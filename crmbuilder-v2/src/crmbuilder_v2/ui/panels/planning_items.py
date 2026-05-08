"""Planning items panel — read-only PRD §4.6 implementation.

Lists every planning item with PRD §4.6 columns (identifier, title,
item_type, status). The detail pane renders the basic record fields
plus the long-form description. Reference rendering on planning items
defers to a future slice.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel


def _label(text: str, *, bold: bool = False, dim: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )
    label.setWordWrap(True)
    if bold:
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
    if dim:
        label.setStyleSheet("color: #888;")
    return label


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _long_text(content: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setPlainText(content or "")
    widget.setMinimumHeight(80)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class PlanningItemsPanel(ListDetailPanel):
    """Planning items — questions, decisions, todos, ideas tracked through resolution."""

    def entity_title(self) -> str:
        return "Planning Items"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_planning_items()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=120),
            ColumnSpec(field="title", title="Title"),
            ColumnSpec(field="item_type", title="Type", width=140),
            ColumnSpec(field="status", title="Status", width=100),
        ]

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        outer.addWidget(_heading_label(record.get("title") or "(untitled)"))

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Identifier", _label(record.get("identifier") or ""))
        form.addRow("Type", _label(record.get("item_type") or ""))
        form.addRow("Status", _label(record.get("status") or ""))
        resolution_ref = record.get("resolution_reference")
        form.addRow(
            "Resolution Reference",
            _label(resolution_ref) if resolution_ref else _label("—", dim=True),
        )
        outer.addLayout(form)

        outer.addWidget(_separator())
        outer.addWidget(_label("Description", bold=True))
        outer.addWidget(_long_text(record.get("description") or ""))

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll
