"""Sessions panel — read-only PRD §4.6 implementation.

Slice D wires the Sessions panel to the storage API. Columns and detail
fields are per PRD §4.6. Reference rendering on the detail pane (e.g.
"Decisions decided in this session") is deferred to a later slice — this
slice only wires the basic record fields.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_LONG_TEXT_MIN_HEIGHT = 80
_LONG_TEXT_FIELDS = (
    ("topics_covered", "Topics Covered"),
    ("summary", "Summary"),
    ("artifacts_produced", "Artifacts Produced"),
    ("in_flight_at_end", "In-Flight at End"),
)


def _label(text: str, *, bold: bool = False, dim: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class SessionsPanel(ListDetailPanel):
    """Read-only Sessions panel."""

    # ------------------------------------------------------------------
    # Right-click context menu (v0.3 — DEC-036)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            # Slice D adds "New session" here; slice B leaves whitespace
            # right-click empty (no menu shown).
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        go_refs_action = menu.addAction("Go to references")
        go_refs_action.triggered.connect(
            lambda _checked=False, r=record: self._show_references_for(r)
        )

        copy_id_action = menu.addAction("Copy identifier")
        copy_id_action.triggered.connect(
            lambda _checked=False, r=record: self._copy_identifier(r)
        )
        return menu

    def _show_references_for(self, record: dict[str, Any]) -> None:
        """Select the row so the detail pane (with ReferencesSection) loads."""
        identifier = record.get("identifier")
        if identifier:
            self.select_record_by_identifier(identifier)

    def _copy_identifier(self, record: dict[str, Any]) -> None:
        """Place the session's identifier on the system clipboard."""
        identifier = record.get("identifier") or ""
        if identifier:
            QApplication.clipboard().setText(identifier)

    # ------------------------------------------------------------------
    # Read-only panel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Sessions"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_sessions()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "session", identifier
            ),
        }

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=120),
            ColumnSpec(field="title", title="Title"),
            ColumnSpec(field="session_date", title="Session Date", width=120),
            ColumnSpec(field="status", title="Status", width=120),
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
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Identifier", _label(record.get("identifier") or ""))
        form.addRow("Session Date", _label(record.get("session_date") or ""))
        form.addRow("Status", _label(record.get("status") or ""))
        outer.addLayout(form)

        outer.addWidget(_separator())

        for field, label_text in _LONG_TEXT_FIELDS:
            outer.addWidget(_label(label_text, bold=True))
            outer.addWidget(_long_text(record.get(field) or ""))

        outer.addWidget(_separator())

        conv_form = QFormLayout()
        conv_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        conv_form.addRow(
            "Conversation Reference",
            _label(record.get("conversation_reference") or "—"),
        )
        outer.addLayout(conv_form)

        outer.addWidget(_separator())
        identifier = record.get("identifier") or ""
        references_section = ReferencesSection(
            "session",
            identifier,
            extras.get("references") or {},
        )
        references_section.navigate_requested.connect(self.navigate_requested)
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll
