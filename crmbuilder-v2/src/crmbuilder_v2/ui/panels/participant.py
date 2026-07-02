"""Participants panel — the engagement-participant methodology entity (REL-069 / PI-391).

A ``ListDetailPanel`` for the ``participant`` entity, registered under the
Methodology sidebar group (after Personas). Mirrors ``PersonasPanel``: a master
table with a Show-deleted toggle and a New button, a read-only detail pane with
Edit / Delete (or Restore) actions, a right-click context menu, and the shared
``ReferencesSection`` showing the participant's persona backing
(``persona_backed_by_participant``). Renaming a placeholder participant to a real
person is an ordinary Edit.
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

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.participant_crud import (
    ParticipantCreateDialog,
    ParticipantDeleteDialog,
    ParticipantEditDialog,
)
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
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_log = logging.getLogger("crmbuilder_v2.ui.panels.participant")

_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _read_only_line(value: str, *, placeholder: str = "") -> QLineEdit:
    widget = QLineEdit()
    widget.setText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    if placeholder:
        widget.setPlaceholderText(placeholder)
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


class ParticipantsPanel(ListDetailPanel):
    """Participants panel with read + write surfaces (REL-069 / PI-391)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Participant")
        self._new_button.setObjectName("new_participant_button")
        self._new_button.clicked.connect(self._on_new_participant_clicked)
        self._action_layout.addWidget(self._new_button)

    # -- ListDetailPanel hooks --------------------------------------------

    def entity_title(self) -> str:
        return "Participants"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_participants(
            include_deleted=self._include_deleted
        )
        for r in records:
            r["created_at_display"] = format_timestamp(
                r.get("participant_created_at")
            )
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(
                field="participant_identifier", title="Identifier", width=110
            ),
            ColumnSpec(field="participant_name", title="Name"),
            ColumnSpec(field="participant_role_kind", title="Role", width=200),
            ColumnSpec(field="participant_status", title="Status", width=90),
            ColumnSpec(field="created_at_display", title="Created", width=140),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("participant_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("participant_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "participant", identifier
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

        identifier = record.get("participant_identifier") or ""
        is_deleted = record.get("participant_deleted_at") is not None

        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_participant_button")
            restore_btn.clicked.connect(
                lambda _c=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_participant_button")
        edit_btn.clicked.connect(
            lambda _c=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_participant_button")
            delete_btn.clicked.connect(
                lambda _c=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("participant_name") or "(unnamed)")
        )

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("participant_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("participant_name") or "")
        name_value.setObjectName("participant_name_value")
        form.addRow(required_label("Name"), name_value)

        role_value = _read_only_line(record.get("participant_role_kind") or "")
        role_value.setObjectName("participant_role_kind_value")
        form.addRow(required_label("Role"), role_value)

        affiliation_value = _read_only_line(
            record.get("participant_affiliation") or ""
        )
        affiliation_value.setObjectName("participant_affiliation_value")
        form.addRow("Affiliation", affiliation_value)

        contact_value = _read_only_line(record.get("participant_contact") or "")
        contact_value.setObjectName("participant_contact_value")
        form.addRow("Contact", contact_value)

        status_combo = QComboBox()
        status_combo.setObjectName("participant_status_value")
        status_combo.addItems(["active", "inactive"])
        current_status = record.get("participant_status") or "active"
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        form.addRow(required_label("Status"), status_combo)
        outer.addLayout(form)

        notes_value = _read_only_text(record.get("participant_notes") or "")
        notes_value.setObjectName("participant_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("participant_notes_toggle")
        outer.addWidget(notes_section)

        outer.addWidget(_separator())
        outer.addWidget(
            created_updated_section(
                record, "participant_created_at", "participant_updated_at"
            )
        )

        outer.addWidget(_separator())
        references_section = ReferencesSection(
            "participant",
            identifier,
            extras.get("references") or {},
            client=self._client,
        )
        self._wire_link_section(references_section)
        references_section.references_changed.connect(self.refresh)
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # -- Identifier addressing --------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("participant_identifier") == identifier:
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
            ident = self._records[row].get("participant_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # -- Right-click context menu -----------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New participant")
            new_action.triggered.connect(self._on_new_participant_clicked)
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        new_action = menu.addAction("New participant")
        new_action.triggered.connect(self._on_new_participant_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _c=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("participant_deleted_at") is not None:
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

    def _on_new_participant_clicked(self) -> None:
        dialog = ParticipantCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("participant_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_participant(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost loading %s for edit: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Participant error loading %s for edit: %s", identifier, exc)
            ErrorDialog(
                title="Could not load participant",
                message="Could not load the latest version of this participant.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        dialog = ParticipantEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("participant_identifier") or ""
        name = record.get("participant_name") or ""
        if not identifier:
            return
        dialog = ParticipantDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("participant_identifier") or ""
        name = record.get("participant_name") or ""
        if not identifier:
            return
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Restore participant")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Participants list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_participant(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Participant error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore participant",
                message=(
                    "An error occurred while restoring the participant. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
