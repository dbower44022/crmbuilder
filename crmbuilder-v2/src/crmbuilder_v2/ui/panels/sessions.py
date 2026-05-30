"""Sessions panel — PI-073 / DEC-314 redesign.

Sessions are now the medium-agnostic communication container (Claude.ai
chat / email / phone / zoom / in_person / slack / other) with a
schedulable, stateful six-status lifecycle. Replaces the legacy
append-only panel — supports create / edit / delete / restore now.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QApplication,
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
    SESSION_STATUS_TRANSITIONS,
    SESSION_STATUSES,
)
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.session_create import (
    SessionCreateDialog,
    SessionDeleteDialog,
    SessionEditDialog,
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

_log = logging.getLogger("crmbuilder_v2.ui.panels.sessions")

_LIFECYCLE_TIMESTAMPS = [
    ("Scheduled for", "session_scheduled_for"),
    ("Started", "session_started_at"),
    ("Ended", "session_ended_at"),
    ("In flight at", "session_in_flight_at"),
    ("Completed", "session_completed_at"),
    ("Cancelled", "session_cancelled_at"),
    ("Not started", "session_not_started_at"),
    ("Superseded", "session_superseded_at"),
]


def _status_choices(current: str | None) -> list[str]:
    current = current or "planned"
    if current not in SESSION_STATUSES:
        return sorted(SESSION_STATUSES)
    return sorted(
        {current} | set(SESSION_STATUS_TRANSITIONS.get(current, frozenset()))
    )


def _format_json_value(value: Any) -> str:
    """Render a JSON-typed field (participants list, medium_metadata dict)."""
    if value is None or value == [] or value == {}:
        return "—"
    try:
        return json.dumps(value, indent=2)
    except TypeError:
        return str(value)


class SessionsPanel(ListDetailPanel):
    """Sessions panel — full lifecycle CRUD per the redesigned model."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Session")
        self._new_button.setObjectName("new_session_button")
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)

    def entity_title(self) -> str:
        return "Sessions"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_sessions(include_deleted=self._include_deleted)
        # PI-108: formatted Created/Updated synthetic columns (the list model
        # stringifies the column field verbatim, so format here).
        for r in records:
            r["created_at_display"] = format_timestamp(r.get("session_created_at"))
            r["updated_at_display"] = format_timestamp(r.get("session_updated_at"))
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="session_identifier", title="Identifier", width=120),
            ColumnSpec(field="session_title", title="Title"),
            ColumnSpec(field="session_medium", title="Medium", width=100),
            ColumnSpec(field="session_status", title="Status", width=120),
            ColumnSpec(field="created_at_display", title="Created", width=140),
            ColumnSpec(field="updated_at_display", title="Updated", width=140),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("session_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("session_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "session", identifier
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

        identifier = record.get("session_identifier") or ""
        is_deleted = record.get("session_deleted_at") is not None

        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.clicked.connect(
                lambda _c=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(
            lambda _c=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.clicked.connect(
                lambda _c=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(strip)

        outer.addWidget(heading_label(record.get("session_title") or "(untitled)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        ident_label = QLabel(identifier or "—")
        ident_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Identifier", ident_label)
        form.addRow(
            required_label("Title"),
            read_only_line(record.get("session_title") or ""),
        )
        form.addRow(
            required_label("Medium"),
            read_only_line(record.get("session_medium") or ""),
        )
        executive_summary = record.get("session_executive_summary") or ""
        form.addRow(
            "Executive Summary",
            read_only_text(executive_summary) if executive_summary else read_only_line("—"),
        )
        form.addRow(
            required_label("Description"),
            read_only_text(record.get("session_description") or ""),
        )
        outer.addLayout(form)

        # Status (read-only summary; transitions happen via Edit dialog)
        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_status = record.get("session_status") or "planned"
        status_combo = QComboBox()
        status_combo.addItems(_status_choices(current_status))
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        status_row.addRow(required_label("Status"), status_combo)
        outer.addLayout(status_row)

        # Participants + medium-specific metadata (collapsible)
        participants_text = _format_json_value(record.get("session_participants"))
        if participants_text != "—":
            outer.addWidget(CollapsibleSection(
                "Participants",
                read_only_text(participants_text),
                expanded=False,
            ))
        metadata_text = _format_json_value(record.get("session_medium_metadata"))
        if metadata_text != "—":
            outer.addWidget(CollapsibleSection(
                "Medium metadata",
                read_only_text(metadata_text),
                expanded=False,
            ))

        # Internal notes
        outer.addWidget(CollapsibleSection(
            "Internal notes",
            read_only_text(record.get("session_notes") or ""),
            expanded=False,
        ))

        # PI-108: created / last-edited audit timestamps.
        outer.addWidget(separator())
        outer.addWidget(
            created_updated_section(record, "session_created_at", "session_updated_at")
        )

        # Lifecycle timestamps
        ts_section = lifecycle_timestamps_section(record, _LIFECYCLE_TIMESTAMPS)
        if ts_section is not None:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Lifecycle timestamps</b>"))
            outer.addWidget(ts_section)

        outer.addWidget(separator())
        refs = ReferencesSection(
            "session",
            identifier,
            extras.get("references") or {},
            client=self._client,
        )
        refs.navigate_requested.connect(self.navigate_requested)
        refs.references_changed.connect(self.refresh)
        outer.addWidget(refs)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("session_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    # ------------------------------------------------------------------
    # Right-click context menu
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        new_action = menu.addAction("New session")
        new_action.triggered.connect(self._on_new_clicked)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        if record.get("session_deleted_at") is not None:
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _c=False, r=record: self._on_restore_clicked(r)
            )
        else:
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _c=False, r=record: self._on_delete_clicked(r)
            )
        copy_id_action = menu.addAction("Copy identifier")
        copy_id_action.triggered.connect(
            lambda _c=False, r=record: self._copy_identifier(r)
        )
        return menu

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_new_clicked(self) -> None:
        dialog = SessionCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.saved_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("session_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_session(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            ErrorDialog(title="Could not load session", message=str(exc), parent=self).exec()
            return
        dialog = SessionEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("session_identifier") or ""
        title = record.get("session_title") or ""
        if not identifier:
            return
        dialog = SessionDeleteDialog(self._client, identifier, title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("session_identifier") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore session")
        confirm.setText(f"Restore {identifier}?")
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_session(identifier)
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

    def _copy_identifier(self, record: dict[str, Any]) -> None:
        identifier = record.get("session_identifier") or ""
        if identifier:
            QApplication.clipboard().setText(identifier)
