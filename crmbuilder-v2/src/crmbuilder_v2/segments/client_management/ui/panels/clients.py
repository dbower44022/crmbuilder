"""Clients panel: the organisation above the engagement (PI-512 / REQ-589).

A ``ListDetailPanel`` for the ``client`` record, mirroring the Participants
panel: a master table with a Show-deleted toggle and a New button, a
read-only detail pane with Edit / Delete (or Restore), a right-click context
menu, and an Engagements section where the engagements a client holds are
listed, added and removed. Assigning an engagement here makes this client its
primary; an engagement already held by another client is moved.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.segments.client_management.ui.dialogs.client_crud import (
    ClientCreateDialog,
    ClientDeleteDialog,
    ClientEditDialog,
)
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import (
    CollapsibleSection,
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_log = logging.getLogger("crmbuilder_v2.ui.panels.clients")

_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"
NO_CLIENT_LABEL = "No client"


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _read_only_line(value: str) -> QLineEdit:
    widget = QLineEdit()
    widget.setText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    return widget


def _read_only_text(value: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    widget.setMinimumHeight(80)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class ClientsPanel(ListDetailPanel):
    """Clients panel with read + write surfaces (PI-512 / REQ-589)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Client")
        self._new_button.setObjectName("new_client_button")
        self._new_button.clicked.connect(self._on_new_client_clicked)
        self._action_layout.addWidget(self._new_button)

    # -- ListDetailPanel hooks --------------------------------------------

    def entity_title(self) -> str:
        return "Clients"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_clients(include_deleted=self._include_deleted)
        for r in records:
            r["created_at_display"] = format_timestamp(r.get("client_created_at"))
            r["engagement_count"] = len(r.get("engagements") or [])
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="client_identifier", title="Identifier", width=110),
            ColumnSpec(field="client_name", title="Name"),
            ColumnSpec(field="client_status", title="Status", width=90),
            ColumnSpec(field="engagement_count", title="Engagements", width=110),
            ColumnSpec(field="created_at_display", title="Created", width=140),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("client_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("client_identifier")
        if not identifier:
            return {"engagements": [], "all_engagements": []}
        return {
            "engagements": self._client.list_client_engagements(identifier),
            "all_engagements": self._client.list_engagements(),
        }

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("client_identifier") or ""
        is_deleted = record.get("client_deleted_at") is not None

        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_client_button")
            restore_btn.clicked.connect(lambda _c=False, r=record: self._on_restore_clicked(r))
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_client_button")
        edit_btn.clicked.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_client_button")
            delete_btn.clicked.connect(lambda _c=False, r=record: self._on_delete_clicked(r))
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(_heading_label(record.get("client_name") or "(unnamed)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("client_identifier_value")
        identifier_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("client_name") or "")
        name_value.setObjectName("client_name_value")
        form.addRow(required_label("Name"), name_value)

        status_combo = QComboBox()
        status_combo.setObjectName("client_status_value")
        status_combo.addItems(["active", "inactive"])
        idx = status_combo.findText(record.get("client_status") or "active")
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        form.addRow(required_label("Status"), status_combo)
        outer.addLayout(form)

        notes_value = _read_only_text(record.get("client_notes") or "")
        notes_value.setObjectName("client_notes_value")
        notes_section = CollapsibleSection("Notes", notes_value, expanded=False)
        notes_section.setObjectName("client_notes_toggle")
        outer.addWidget(notes_section)

        outer.addWidget(_separator())
        outer.addWidget(self._build_engagements_section(record, extras))

        outer.addWidget(_separator())
        outer.addWidget(created_updated_section(record, "client_created_at", "client_updated_at"))

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # -- Engagements section ----------------------------------------------

    def _build_engagements_section(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        """The engagements this client holds, with add and remove."""
        identifier = record.get("client_identifier") or ""
        held: list[dict[str, Any]] = extras.get("engagements") or []
        all_engagements: list[dict[str, Any]] = extras.get("all_engagements") or []
        held_ids = {e.get("engagement_identifier") for e in held}

        section = QWidget()
        section.setObjectName("client_engagements_section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Engagements")
        font = QFont(title.font())
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        if not held:
            empty = QLabel("This client holds no engagements.")
            empty.setObjectName("client_engagements_empty")
            layout.addWidget(empty)
        for engagement in held:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            eng_id = engagement.get("engagement_identifier") or ""
            name = engagement.get("engagement_name") or "(unnamed)"
            code = engagement.get("engagement_code") or ""
            marker = " (primary)" if engagement.get("is_primary") else ""
            label = QLabel(f"{eng_id} — {name} ({code}){marker}")
            label.setObjectName(f"client_engagement_{eng_id}")
            row_layout.addWidget(label, stretch=1)
            remove = QPushButton("Remove")
            remove.setObjectName(f"remove_engagement_{eng_id}")
            remove.clicked.connect(
                lambda _c=False, e=eng_id: self._on_remove_engagement(e)
            )
            row_layout.addWidget(remove)
            layout.addWidget(row)

        add_row = QWidget()
        add_layout = QHBoxLayout(add_row)
        add_layout.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        combo.setObjectName("add_engagement_combo")
        for engagement in all_engagements:
            eng_id = engagement.get("engagement_identifier") or ""
            if not eng_id or eng_id in held_ids:
                continue
            if engagement.get("engagement_deleted_at") is not None:
                continue
            combo.addItem(
                f"{eng_id} — {engagement.get('engagement_name') or '(unnamed)'}", eng_id
            )
        add_layout.addWidget(combo, stretch=1)
        add_button = QPushButton("Add engagement")
        add_button.setObjectName("add_engagement_button")
        add_button.setEnabled(combo.count() > 0 and bool(identifier))
        add_button.clicked.connect(
            lambda _c=False: self._on_add_engagement(identifier, combo.currentData())
        )
        add_layout.addWidget(add_button)
        layout.addWidget(add_row)
        return section

    def _on_add_engagement(self, client_identifier: str, engagement_identifier: Any) -> None:
        if not client_identifier or not engagement_identifier:
            return
        try:
            current = self._client.get_engagement_clients(str(engagement_identifier))
            others = [
                c.get("client_identifier")
                for c in current.get("clients") or []
                if c.get("client_identifier") and c.get("client_identifier") != client_identifier
            ]
            self._client.set_engagement_clients(
                str(engagement_identifier),
                [client_identifier, *others],
                primary=client_identifier,
            )
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not assign engagement",
                message="The engagement could not be assigned to this client.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()

    def _on_remove_engagement(self, engagement_identifier: str) -> None:
        selected = self._currently_selected_identifier()
        try:
            current = self._client.get_engagement_clients(engagement_identifier)
            remaining = [
                c.get("client_identifier")
                for c in current.get("clients") or []
                if c.get("client_identifier") and c.get("client_identifier") != selected
            ]
            self._client.set_engagement_clients(engagement_identifier, remaining)
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not remove engagement",
                message="The engagement could not be removed from this client.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()

    # -- Identifier addressing --------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("client_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _currently_selected_identifier(self) -> str | None:
        master = getattr(self, "_master_view", None)
        if master is None:
            return None
        sel_model = master.selectionModel()
        if sel_model is None:
            return None
        index = sel_model.currentIndex()
        if not index.isValid():
            return None
        row = index.row()
        if 0 <= row < len(self._records):
            ident = self._records[row].get("client_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # -- Right-click context menu -----------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        new_action = menu.addAction("New client")
        new_action.triggered.connect(self._on_new_client_clicked)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        if record.get("client_deleted_at") is not None:
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _c=False, r=record: self._on_restore_clicked(r)
            )
        else:
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _c=False, r=record: self._on_delete_clicked(r)
            )
        return menu

    # -- Write-surface click handlers -------------------------------------

    def _on_new_client_clicked(self) -> None:
        dialog = ClientCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("client_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_client(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not load client",
                message="Could not load the latest version of this client.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        dialog = ClientEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("client_identifier") or ""
        name = record.get("client_name") or ""
        if not identifier:
            return
        dialog = ClientDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("client_identifier") or ""
        name = record.get("client_name") or ""
        if not identifier:
            return
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Restore client")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Clients list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_client(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not restore client",
                message="An error occurred while restoring the client. Please try again.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
