"""Sessions panel — append-only write surface (PRD §4.6, v0.3 §4.4).

v0.1 slice D wired the read-only surface (columns, detail fields, list
fetch). v0.3 slice D adds the create-only write surface per DEC-034:
a ``New Session`` toolbar button, a whitespace right-click ``New
session`` action, and the ``SessionCreateDialog`` it launches. Per
DEC-013 / DEC-034, sessions remain append-only — no Edit, no Delete,
no Restore appears anywhere on this panel.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.session_create import SessionCreateDialog
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
    """Append-only Sessions panel — read + create-only writes."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        self._new_session_button = QPushButton("New Session")
        self._new_session_button.setObjectName("new_session_button")
        self._new_session_button.clicked.connect(
            self._on_new_session_clicked
        )
        self._action_layout.addWidget(self._new_session_button)

    # ------------------------------------------------------------------
    # Right-click context menu (v0.3 — DEC-036, slice D)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New session")
            new_action.triggered.connect(self._on_new_session_clicked)
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

    # ------------------------------------------------------------------
    # New Session click handler (v0.3 slice D — DEC-034)
    # ------------------------------------------------------------------

    def _on_new_session_clicked(self) -> None:
        dialog = SessionCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

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
            client=self._client,
        )
        references_section.navigate_requested.connect(self.navigate_requested)
        references_section.references_changed.connect(self.refresh)
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll
