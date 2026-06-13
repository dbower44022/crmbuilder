"""Close-out payloads panel — the fifth governance entity type (UI v0.7)."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import (
    CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS,
    CLOSE_OUT_PAYLOAD_STATUSES,
)
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.close_out_payload_crud import (
    CloseOutPayloadCreateDialog,
    CloseOutPayloadDeleteDialog,
    CloseOutPayloadEditDialog,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import (
    created_updated_section,
    heading_label,
    lifecycle_timestamps_section,
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import (
    CollapsibleSection,
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_log = logging.getLogger("crmbuilder_v2.ui.panels.close_out_payloads")

_LIFECYCLE_TIMESTAMPS = [
    ("Ready", "close_out_payload_ready_at"),
    ("Applied", "close_out_payload_applied_at"),
    ("Cancelled", "close_out_payload_cancelled_at"),
    ("Superseded", "close_out_payload_superseded_at"),
]


def _status_choices(current: str | None) -> list[str]:
    current = current or "drafted"
    if current not in CLOSE_OUT_PAYLOAD_STATUSES:
        return sorted(CLOSE_OUT_PAYLOAD_STATUSES)
    return sorted(
        {current} | set(CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS.get(current, frozenset()))
    )


class CloseOutPayloadsPanel(ListDetailPanel):
    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Close-Out Payload")
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)

    def entity_title(self) -> str:
        return "Close-Out Payloads"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_close_out_payloads(
            include_deleted=self._include_deleted
        )
        # PI-108: formatted Created/Updated synthetic columns.
        for r in records:
            r["created_at_display"] = format_timestamp(
                r.get("close_out_payload_created_at")
            )
            r["updated_at_display"] = format_timestamp(
                r.get("close_out_payload_updated_at")
            )
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="close_out_payload_identifier", title="Identifier", width=110),
            ColumnSpec(field="close_out_payload_title", title="Title"),
            ColumnSpec(field="close_out_payload_status", title="Status", width=110),
            ColumnSpec(field="created_at_display", title="Created", width=140),
            ColumnSpec(field="updated_at_display", title="Updated", width=140),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("close_out_payload_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("close_out_payload_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {"references": self._client.list_references_touching("close_out_payload", identifier)}

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("close_out_payload_identifier") or ""
        is_deleted = record.get("close_out_payload_deleted_at") is not None

        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.clicked.connect(lambda _c=False, r=record: self._on_restore_clicked(r))
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.clicked.connect(lambda _c=False, r=record: self._on_delete_clicked(r))
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(strip)

        outer.addWidget(heading_label(record.get("close_out_payload_title") or "(untitled)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        ident_label = QLabel(identifier or "—")
        ident_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Identifier", ident_label)
        form.addRow(required_label("Title"), read_only_line(record.get("close_out_payload_title") or ""))
        form.addRow(required_label("Description"), read_only_text(record.get("close_out_payload_description") or ""))
        form.addRow(required_label("File path"), read_only_line(record.get("close_out_payload_file_path") or ""))
        outer.addLayout(form)

        outer.addWidget(CollapsibleSection(
            "Internal notes",
            read_only_text(record.get("close_out_payload_notes") or ""),
            expanded=False,
        ))

        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_status = record.get("close_out_payload_status") or "drafted"
        status_combo = QComboBox()
        status_combo.addItems(_status_choices(current_status))
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        status_row.addRow(required_label("Status"), status_combo)
        outer.addLayout(status_row)

        # PI-108: created / last-edited audit timestamps.
        outer.addWidget(separator())
        outer.addWidget(
            created_updated_section(
                record,
                "close_out_payload_created_at",
                "close_out_payload_updated_at",
            )
        )

        ts_section = lifecycle_timestamps_section(record, _LIFECYCLE_TIMESTAMPS)
        if ts_section is not None:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Lifecycle timestamps</b>"))
            outer.addWidget(ts_section)

        outer.addWidget(separator())
        refs = ReferencesSection(
            "close_out_payload", identifier, extras.get("references") or {}, client=self._client
        )
        self._wire_link_section(refs)
        refs.references_changed.connect(self.refresh)
        outer.addWidget(refs)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("close_out_payload_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _currently_selected_identifier(self) -> str | None:
        master = getattr(self, "_master_view", None)
        if master is None:
            return None
        sel = master.selectionModel()
        if sel is None:
            return None
        idx = sel.currentIndex()
        if not idx.isValid() or not (0 <= idx.row() < len(self._records)):
            return None
        ident = self._records[idx.row()].get("close_out_payload_identifier")
        return ident if isinstance(ident, str) else None

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        new_action = menu.addAction("New close-out payload")
        new_action.triggered.connect(self._on_new_clicked)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        if record.get("close_out_payload_deleted_at") is not None:
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(lambda _c=False, r=record: self._on_restore_clicked(r))
        else:
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda _c=False, r=record: self._on_delete_clicked(r))
        return menu

    def _on_new_clicked(self) -> None:
        dialog = CloseOutPayloadCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.saved_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("close_out_payload_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_close_out_payload(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(title="Could not load payload", message=str(exc), parent=self).exec()
            return
        dialog = CloseOutPayloadEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("close_out_payload_identifier") or ""
        title = record.get("close_out_payload_title") or ""
        if not identifier:
            return
        dialog = CloseOutPayloadDeleteDialog(self._client, identifier, title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("close_out_payload_identifier") or ""
        if not identifier:
            return
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Restore close-out payload")
        confirm.setText(f"Restore {identifier}?")
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_close_out_payload(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(title="Could not restore", message=str(exc), parent=self).exec()
            return
        self.refresh()
