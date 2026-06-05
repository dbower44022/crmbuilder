"""Glossary panel — the term entity (PI-061).

A flat ``ListDetailPanel`` for the ``term`` entity, registered under the
Methodology sidebar group. Terms are migrated out of
``specifications/glossary.md`` into V2 records; this panel is the read/edit
surface. Terms are listed by name (alphabetical, the glossary's natural
ordering); the detail pane shows the full definition and the new/edit/delete
write surface. ``term`` is a system/shared entity with a nullable
``engagement_id`` scope — the ``scope`` value (``system`` or an engagement
identifier) is surfaced read-only in the detail pane.
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
from crmbuilder_v2.ui.dialogs.term_crud import (
    TermCreateDialog,
    TermDeleteDialog,
    TermEditDialog,
)
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.widgets.form_helpers import (
    destructive_button,
    primary_button,
    required_label,
)

_log = logging.getLogger("crmbuilder_v2.ui.panels.glossary")

_LONG_TEXT_MIN_HEIGHT = 80


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _label(text: str, *, dim: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    if dim:
        label.setStyleSheet("color: #888;")
    return label


def _read_only_text(value: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class GlossaryPanel(ListDetailPanel):
    """Glossary panel — the term entity with read + write surfaces (PI-061)."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        self._new_button = primary_button("New Term")
        self._new_button.setObjectName("new_term_button")
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Glossary"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_terms()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=110),
            ColumnSpec(field="name", title="Term"),
            ColumnSpec(field="scope", title="Scope", width=110),
            ColumnSpec(field="status", title="Status", width=90),
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

        # Edit / Delete action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_term_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        delete_btn = destructive_button("Delete")
        delete_btn.setObjectName("delete_term_button")
        delete_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_delete_clicked(r)
        )
        strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(_heading_label(record.get("name") or "(unnamed)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Identifier", _label(record.get("identifier") or "—"))
        form.addRow("Scope", _label(record.get("scope") or "system"))
        form.addRow("Status", _label(record.get("status") or ""))
        outer.addLayout(form)

        outer.addWidget(_separator())
        outer.addWidget(required_label("Definition"))
        outer.addWidget(_read_only_text(record.get("definition") or ""))

        for label_text, key in (
            ("Scope (where it applies)", "usage_scope"),
            ("Examples", "examples"),
            ("Distinguishing notes", "distinguishing_notes"),
            ("Related terms", "related_terms"),
        ):
            value = record.get(key)
            if value:
                outer.addWidget(_label(label_text, dim=True))
                outer.addWidget(_read_only_text(value))

        outer.addWidget(_separator())
        outer.addWidget(
            created_updated_section(record, "created_at", "updated_at")
        )

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Right-click context menu
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        new_action = menu.addAction("New term")
        new_action.triggered.connect(self._on_new_clicked)
        if not index.isValid():
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
    # Write-surface click handlers
    # ------------------------------------------------------------------

    def _on_new_clicked(self) -> None:
        dialog = TermCreateDialog(self._client, self)
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
            fresh = self._client.get_term(identifier)
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
                title="Could not load term",
                message="Could not load the latest version of this term.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = TermEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier") or ""
        name = record.get("name") or ""
        if not identifier:
            return
        dialog = TermDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
