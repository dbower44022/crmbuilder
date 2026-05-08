"""Topics panel — read-only PRD §4.6 implementation.

Renders topics in a hierarchical depth-first order (parent before its
children) with the Name column indented by depth. Orphans (topics
whose declared parent is missing from the loaded set) are surfaced at
depth 0 with an ``(orphan)`` indicator. Cycles are tolerated by
emitting each topic at most once.
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

_INDENT = "    "
_ORPHAN_SUFFIX = " (orphan)"


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


class TopicsPanel(ListDetailPanel):
    """Topics — free-floating concepts with optional parent links."""

    def entity_title(self) -> str:
        return "Topics"

    def fetch_records(self) -> list[dict[str, Any]]:
        raw = self._client.list_topics()
        return self._build_hierarchical_view(raw)

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=120),
            ColumnSpec(field="_display_name", title="Name"),
            ColumnSpec(
                field="parent_topic_identifier",
                title="Parent Topic",
                width=160,
            ),
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

        outer.addWidget(_heading_label(record.get("name") or "(unnamed)"))

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Identifier", _label(record.get("identifier") or ""))
        form.addRow(
            "Parent Topic",
            self._parent_link_or_dash(record.get("parent_topic_identifier")),
        )
        outer.addLayout(form)

        outer.addWidget(_separator())
        outer.addWidget(_label("Description", bold=True))
        outer.addWidget(_long_text(record.get("description") or ""))

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Hierarchy build
    # ------------------------------------------------------------------

    def _build_hierarchical_view(
        self, topics: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        by_identifier: dict[str, dict[str, Any]] = {}
        children: dict[str | None, list[dict[str, Any]]] = {}
        for t in topics:
            ident = t.get("identifier")
            if not ident:
                continue
            by_identifier[ident] = t
        for t in topics:
            parent = t.get("parent_topic_identifier")
            if parent is not None and parent not in by_identifier:
                # Treat as orphan: don't bucket under its declared parent.
                continue
            children.setdefault(parent, []).append(t)
        for bucket in children.values():
            bucket.sort(key=lambda r: r.get("identifier") or "")

        ordered: list[dict[str, Any]] = []
        visited: set[str] = set()

        def walk(topic: dict[str, Any], depth: int) -> None:
            ident = topic.get("identifier")
            if not ident or ident in visited:
                return
            visited.add(ident)
            entry = dict(topic)
            entry["_display_name"] = (
                _INDENT * depth + (topic.get("name") or "")
            )
            ordered.append(entry)
            for child in children.get(ident, []):
                walk(child, depth + 1)

        for root in children.get(None, []):
            walk(root, 0)

        # Append orphans (declared parent missing from the loaded set).
        for t in topics:
            ident = t.get("identifier") or ""
            if not ident or ident in visited:
                continue
            entry = dict(t)
            entry["_display_name"] = (t.get("name") or "") + _ORPHAN_SUFFIX
            ordered.append(entry)
            visited.add(ident)
        return ordered

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parent_link_or_dash(self, identifier: str | None) -> QLabel:
        if not identifier:
            return _label("—", dim=True)
        return self._link_label(
            f'<a href="topic:{identifier}">{identifier}</a>'
        )

    def _link_label(self, html: str) -> QLabel:
        label = QLabel()
        label.setText(html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(False)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        label.setWordWrap(True)
        label.linkActivated.connect(self._emit_link_navigation)
        return label
