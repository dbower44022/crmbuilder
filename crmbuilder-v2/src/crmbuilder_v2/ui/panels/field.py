"""Fields panel — the sixth methodology entity type (v0.5+, PI-004
first slice).

A ``ListDetailPanel`` for the ``field`` entity, registered as the
sixth entry under the Methodology sidebar group (after Personas, which
took the position #5 the field.md §3.6.1 spec originally reserved
for fields — re-keyed up by one because persona shipped first).
Mirrors the slice-C ``EntitiesPanel`` with field-specific
adjustments: a master table with a Show-deleted toggle and a New
button, a structured read-only detail pane with Edit/Delete (or
Restore) actions, and a right-click context menu.

Detail pane layout follows ``field.md`` §3.6.3: identifier
(read-only label), name, parent-entity (read-only label resolved
from the live ``field_belongs_to_entity`` edge), description, type
(read-only combo), required (read-only checkbox), notes under a
collapsible "Internal notes" section header collapsed by default,
status, and the shared ``ReferencesSection`` widget.

# TODO: master-pane primary grouping by parent entity per field.md
# §3.6.2 (PI-004 follow-on slice). v1 ships with a flat
# identifier-sorted list; at CBM-redo scale (200+ fields) the grouped
# view becomes the default.

# TODO: "Move to entity" reparenting affordance per field.md §3.6.5
# / PI-053. v1 ships with parent-entity displayed as a read-only
# label and no edit affordance.
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
from crmbuilder_v2.ui.dialogs._field_schema import status_choices
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.field_crud import (
    FieldCreateDialog,
    FieldDeleteDialog,
    FieldEditDialog,
)
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.styling import t as _T
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import (
    CollapsibleSection,
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_log = logging.getLogger("crmbuilder_v2.ui.panels.field")

_LONG_TEXT_MIN_HEIGHT = 80
_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"
_DESCRIPTION_PLACEHOLDER = (
    "Brief description of what this field conceptually represents"
)


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


def _read_only_text(value: str, *, placeholder: str = "") -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def _resolve_parent_entity_identifier(client, field_identifier: str) -> str:
    """Look up the live ``field_belongs_to_entity`` edge's target.

    Returns an empty string if the lookup fails or the field has no
    edge (e.g. the soft-deleted state).
    """
    if not field_identifier:
        return ""
    try:
        refs = client.list_references_touching("field", field_identifier)
    except Exception:  # noqa: BLE001 — degrade to empty label
        _log.exception(
            "Could not resolve parent entity for %s", field_identifier
        )
        return ""
    for ref in refs.get("as_source", []):
        if ref.get("relationship") == "field_belongs_to_entity":
            return ref.get("target_id", "") or ""
    return ""


class FieldsPanel(ListDetailPanel):
    """Fields panel with read + write surfaces (v0.5+, PI-004 first slice)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Field")
        self._new_button.setObjectName("new_field_button")
        self._new_button.clicked.connect(self._on_new_field_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Fields"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_fields(
            include_deleted=self._include_deleted
        )
        # PI-108: formatted Created synthetic column for the master pane.
        for r in records:
            r["created_at_display"] = format_timestamp(r.get("field_created_at"))
        return records

    def list_columns(self) -> list[ColumnSpec]:
        # Per field.md §3.6.2: six columns; entity-grouping deferred
        # (flat identifier-sorted list in v1).
        return [
            ColumnSpec(
                field="field_identifier", title="Identifier", width=120
            ),
            ColumnSpec(field="field_name", title="Name"),
            ColumnSpec(field="field_type", title="Type", width=110),
            ColumnSpec(field="field_status", title="Status", width=110),
            ColumnSpec(
                field="created_at_display", title="Created", width=140
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("field_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("field_identifier")
        if not identifier:
            return {
                "references": {"as_source": [], "as_target": []},
                "parent_entity_identifier": "",
            }
        refs = self._client.list_references_touching("field", identifier)
        parent_id = ""
        for ref in refs.get("as_source", []):
            if ref.get("relationship") == "field_belongs_to_entity":
                parent_id = ref.get("target_id", "") or ""
                break
        # Soft-deleted fields have no live edge; surface the stash
        # column instead so the detail pane shows the entity the
        # field was attached to before deletion.
        if not parent_id:
            parent_id = (
                record.get("field_previous_parent_entity_identifier") or ""
            )
        return {
            "references": refs,
            "parent_entity_identifier": parent_id,
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

        identifier = record.get("field_identifier") or ""
        is_deleted = record.get("field_deleted_at") is not None

        # Edit / Delete (or Restore / Edit) action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_field_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_field_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_field_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("field_name") or "(unnamed)")
        )

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        # Field 1: identifier (read-only label).
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("field_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        # Field 2: name.
        name_value = _read_only_line(record.get("field_name") or "")
        name_value.setObjectName("field_name_value")
        form.addRow(required_label("Name"), name_value)

        # Field 3: parent entity (rendered outside ReferencesSection per
        # spec §3.6.3 — the mandatory 1:1 edge is conceptually part of
        # the field's identity, not a peer relationship).
        parent_id = extras.get("parent_entity_identifier") or ""
        parent_label = QLabel(parent_id or "—")
        parent_label.setObjectName("field_parent_entity_value")
        parent_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        # TODO: Move to entity affordance per field.md §3.6.5 / PI-053
        # — deferred to follow-on slice.
        form.addRow(required_label("Parent entity"), parent_label)

        # Field 4: description.
        description_value = _read_only_text(
            record.get("field_description") or "",
            placeholder=_DESCRIPTION_PLACEHOLDER,
        )
        description_value.setObjectName("field_description_value")
        form.addRow(required_label("Description"), description_value)

        # Field 5: type — read-only combo.
        type_value = _read_only_line(record.get("field_type") or "")
        type_value.setObjectName("field_type_value")
        form.addRow(required_label("Type"), type_value)

        # Field 6: required — read-only checkbox.
        required_checkbox = QCheckBox("Required for every record")
        required_checkbox.setObjectName("field_required_value")
        required_checkbox.setChecked(bool(record.get("field_required")))
        required_checkbox.setEnabled(False)
        form.addRow("", required_checkbox)

        outer.addLayout(form)

        # Field 7: notes under a collapsible "Internal notes" header,
        # collapsed by default per spec §3.6.3.
        notes_value = _read_only_text(record.get("field_notes") or "")
        notes_value.setObjectName("field_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("field_notes_toggle")
        outer.addWidget(notes_section)

        # Field 8: status combo restricted to valid successors; disabled
        # because the detail pane is a view (editing goes through the
        # dialog).
        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_status = record.get("field_status") or "candidate"
        status_combo = QComboBox()
        status_combo.setObjectName("field_status_value")
        status_combo.addItems(status_choices(current_status))
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        successors = sorted(
            set(status_choices(current_status)) - {current_status}
        )
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(int(_T("space.1").rstrip("px")))
        status_layout.addWidget(status_combo)
        status_hint = QLabel(
            f"Valid transitions: {', '.join(successors)}"
            if successors
            else ""
        )
        status_hint.setObjectName("statusHintCaption")
        status_layout.addWidget(status_hint)
        status_row.addRow(required_label("Status"), status_container)
        outer.addLayout(status_row)

        # PI-108: created / last-edited audit timestamps.
        outer.addWidget(_separator())
        outer.addWidget(
            created_updated_section(
                record, "field_created_at", "field_updated_at"
            )
        )

        outer.addWidget(_separator())

        # Field 9: shared ReferencesSection. In v0.5 there are no
        # inbound kinds declared (PI-005 process growth will register
        # `process_touches_field` when it lands); the widget is still
        # always present per spec §3.6.3.
        references_section = ReferencesSection(
            "field",
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

    # ------------------------------------------------------------------
    # Identifier addressing (field uses ``field_identifier``, not the
    # base's ``identifier`` key)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("field_identifier") == identifier:
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
            ident = self._records[row].get("field_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New field")
            new_action.triggered.connect(self._on_new_field_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New field")
        new_action.triggered.connect(self._on_new_field_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("field_deleted_at") is not None:
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
        else:
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
        return menu

    # ------------------------------------------------------------------
    # Write-surface click handlers
    # ------------------------------------------------------------------

    def _on_new_field_clicked(self) -> None:
        dialog = FieldCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("field_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_field(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost loading %s for edit: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Field error loading %s for edit: %s", identifier, exc)
            ErrorDialog(
                title="Could not load field",
                message="Could not load the latest version of this field.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = FieldEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("field_identifier") or ""
        name = record.get("field_name") or ""
        if not identifier:
            return
        dialog = FieldDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("field_identifier") or ""
        name = record.get("field_name") or ""
        if not identifier:
            return
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Restore field")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Fields list with its "
            "parent-entity edge restored."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_field(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Field error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore field",
                message=(
                    "An error occurred while restoring the field. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
