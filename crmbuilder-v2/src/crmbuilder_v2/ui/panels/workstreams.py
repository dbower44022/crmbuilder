"""Workstreams panel — the first governance entity type (UI v0.7).

ListDetailPanel for ``workstream`` records. Per ``workstream.md`` §3.6:
four-column master pane (Identifier / Name / Status / Updated), detail pane
with the lifecycle-timestamps section conditional on non-null values, and the
shared ReferencesSection.
"""

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
    WORKSTREAM_STATUS_TRANSITIONS,
    WORKSTREAM_STATUSES,
)
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.workstream_crud import (
    WorkstreamCreateDialog,
    WorkstreamDeleteDialog,
    WorkstreamEditDialog,
)
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

_log = logging.getLogger("crmbuilder_v2.ui.panels.workstreams")

_LIFECYCLE_TIMESTAMPS = [
    ("Started", "workstream_started_at"),
    ("Completed", "workstream_completed_at"),
    ("Cancelled", "workstream_cancelled_at"),
    ("Superseded", "workstream_superseded_at"),
]


def _status_choices(current: str | None) -> list[str]:
    current = current or "planned"
    if current not in WORKSTREAM_STATUSES:
        return sorted(WORKSTREAM_STATUSES)
    return sorted(
        {current} | set(WORKSTREAM_STATUS_TRANSITIONS.get(current, frozenset()))
    )


class WorkstreamsPanel(ListDetailPanel):
    """Workstreams panel with read + write surfaces (UI v0.7)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Workstream")
        self._new_button.setObjectName("new_workstream_button")
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)

    def entity_title(self) -> str:
        return "Workstreams"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_workstreams(include_deleted=self._include_deleted)
        # PI-108: formatted Created/Updated synthetic columns.
        for r in records:
            r["created_at_display"] = format_timestamp(r.get("workstream_created_at"))
            r["updated_at_display"] = format_timestamp(r.get("workstream_updated_at"))
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="workstream_identifier", title="Identifier", width=120),
            ColumnSpec(field="workstream_name", title="Name"),
            ColumnSpec(field="workstream_status", title="Status", width=110),
            ColumnSpec(field="created_at_display", title="Created", width=140),
            ColumnSpec(field="updated_at_display", title="Updated", width=140),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("workstream_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("workstream_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "workstream", identifier
            ),
        }

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("workstream_identifier") or ""
        is_deleted = record.get("workstream_deleted_at") is not None

        # Action strip.
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

        outer.addWidget(heading_label(record.get("workstream_name") or "(unnamed)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        ident_label = QLabel(identifier or "—")
        ident_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Identifier", ident_label)
        form.addRow(required_label("Name"), read_only_line(record.get("workstream_name") or ""))
        form.addRow(required_label("Purpose"), read_only_line(
            record.get("workstream_purpose") or "", placeholder="One sentence"))
        form.addRow(required_label("Description"), read_only_text(
            record.get("workstream_description") or "",
            placeholder="Paragraph describing the workstream"))
        outer.addLayout(form)

        notes_section = CollapsibleSection(
            "Internal notes",
            read_only_text(record.get("workstream_notes") or ""),
            expanded=False,
        )
        outer.addWidget(notes_section)

        # Status combo (disabled, showing valid transitions hint).
        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_status = record.get("workstream_status") or "planned"
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
                record, "workstream_created_at", "workstream_updated_at"
            )
        )

        ts_section = lifecycle_timestamps_section(record, _LIFECYCLE_TIMESTAMPS)
        if ts_section is not None:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Lifecycle timestamps</b>"))
            outer.addWidget(ts_section)

        outer.addWidget(separator())
        refs = ReferencesSection(
            "workstream", identifier, extras.get("references") or {}, client=self._client
        )
        refs.navigate_requested.connect(self.navigate_requested)
        refs.references_changed.connect(self.refresh)
        outer.addWidget(refs)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # Identifier addressing.
    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("workstream_identifier") == identifier:
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
        ident = self._records[idx.row()].get("workstream_identifier")
        return ident if isinstance(ident, str) else None

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        new_action = menu.addAction("New workstream")
        new_action.triggered.connect(self._on_new_clicked)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        if record.get("workstream_deleted_at") is not None:
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

    def _on_new_clicked(self) -> None:
        dialog = WorkstreamCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.saved_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("workstream_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_workstream(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not load workstream", message=str(exc), parent=self
            ).exec()
            return
        dialog = WorkstreamEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("workstream_identifier") or ""
        name = record.get("workstream_name") or ""
        if not identifier:
            return
        dialog = WorkstreamDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("workstream_identifier") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore workstream")
        confirm.setText(f"Restore {identifier}?")
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_workstream(identifier)
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
