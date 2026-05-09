"""Risks panel — PRD §4.6 list/detail + v0.2 §4.2 write surfaces.

Slice D wired the read-only panel. v0.2 slice B adds the write
surface: a "New Risk" toolbar button plus Edit and Delete buttons in
the detail pane that open the create/edit/delete dialogs. The shared
``ReferencesSection`` widget renders inbound and outbound references
for the selected risk on the detail pane.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.risk_create import RiskCreateDialog
from crmbuilder_v2.ui.dialogs.risk_delete import RiskDeleteDialog
from crmbuilder_v2.ui.dialogs.risk_edit import RiskEditDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.risks")

_LONG_TEXT_MIN_HEIGHT = 80
_LONG_TEXT_FIELDS = (
    ("description", "Description"),
    ("response_plan", "Response Plan"),
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


class RisksPanel(ListDetailPanel):
    """Risks panel with read + write surfaces (v0.2 slice B)."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        self._new_button = QPushButton("New Risk")
        self._new_button.setObjectName("new_risk_button")
        self._new_button.clicked.connect(self._on_new_risk_clicked)
        self._action_layout.addWidget(self._new_button)

    def entity_title(self) -> str:
        return "Risks"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_risks()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=120),
            ColumnSpec(field="title", title="Title"),
            ColumnSpec(field="probability", title="Probability", width=100),
            ColumnSpec(field="impact", title="Impact", width=100),
            ColumnSpec(field="status", title="Status", width=120),
        ]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "risk", identifier
            ),
        }

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        button_strip = QWidget()
        button_strip_layout = QHBoxLayout(button_strip)
        button_strip_layout.setContentsMargins(0, 0, 0, 0)
        button_strip_layout.setSpacing(6)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_risk_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        button_strip_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("delete_risk_button")
        delete_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_delete_clicked(r)
        )
        button_strip_layout.addWidget(delete_btn)
        button_strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(_heading_label(record.get("title") or "(untitled)"))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Identifier", _label(record.get("identifier") or ""))
        form.addRow("Probability", _label(record.get("probability") or ""))
        form.addRow("Impact", _label(record.get("impact") or ""))
        form.addRow("Status", _label(record.get("status") or ""))
        outer.addLayout(form)

        outer.addWidget(_separator())

        for field, label_text in _LONG_TEXT_FIELDS:
            if field not in record:
                continue
            outer.addWidget(_label(label_text, bold=True))
            outer.addWidget(_long_text(record.get(field) or ""))

        outer.addWidget(_separator())
        identifier = record.get("identifier") or ""
        references_section = ReferencesSection(
            "risk",
            identifier,
            extras.get("references") or {},
        )
        references_section.navigate_requested.connect(self.navigate_requested)
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Right-click context menu (v0.3 — DEC-036)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New risk")
            new_action.triggered.connect(self._on_new_risk_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(
            lambda _checked=False, r=record: self._on_delete_clicked(r)
        )
        return menu

    # ------------------------------------------------------------------
    # Write-surface click handlers (v0.2 slice B)
    # ------------------------------------------------------------------

    def _on_new_risk_clicked(self) -> None:
        dialog = RiskCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_risk(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost loading %s for edit: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Domain error loading %s for edit: %s", identifier, exc)
            ErrorDialog(
                title="Could not load risk",
                message="Could not load the latest version of this risk.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = RiskEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier") or ""
        title = record.get("title") or ""
        if not identifier:
            return
        dialog = RiskDeleteDialog(self._client, identifier, title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
