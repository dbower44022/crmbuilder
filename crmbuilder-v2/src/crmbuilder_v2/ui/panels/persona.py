"""Personas panel — the fifth methodology entity type (v0.5+, PI-003).

A ``ListDetailPanel`` for the ``persona`` entity, registered as the
fifth entry under the Methodology sidebar group (after CRM Candidates).
Mirrors the slice-C ``EntitiesPanel`` with persona-specific
adjustments: a master table with a Show-deleted toggle and a New
button, a structured read-only detail pane with Edit/Delete (or
Restore) actions, and a right-click context menu.

Detail pane layout follows ``persona.md`` §3.6.3: identifier
(read-only label), name, role summary (read-only multi-line with
placeholder), ``persona_responsibilities`` under a collapsible
"Responsibilities" section header **expanded by default** (the field
is optional, but when populated it carries client-visible content
distinct from the consultant scratchpad), ``persona_notes`` under a
collapsible "Internal notes" section header collapsed by default,
status, and the shared ``ReferencesSection`` widget.

This is the **first methodology panel surfacing two outgoing
reference kinds** — ``persona_scopes_to_domain`` (persona-to-domain
affiliations) and ``persona_realized_as_entity`` (persona-to-entity
realization). No master-pane Domains or Realized-as columns ship in
v0.5+ per ``persona.md`` §3.6.2 (PI-007 / PI-009 enablers).
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
from crmbuilder_v2.ui.dialogs._persona_schema import status_choices
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.persona_crud import (
    PersonaCreateDialog,
    PersonaDeleteDialog,
    PersonaEditDialog,
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

_log = logging.getLogger("crmbuilder_v2.ui.panels.persona")

_LONG_TEXT_MIN_HEIGHT = 80
_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"
_ROLE_SUMMARY_PLACEHOLDER = (
    "Brief description of what this role does in the organization"
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


class PersonasPanel(ListDetailPanel):
    """Personas panel with read + write surfaces (v0.5+, PI-003)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Persona")
        self._new_button.setObjectName("new_persona_button")
        self._new_button.clicked.connect(self._on_new_persona_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Personas"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_personas(
            include_deleted=self._include_deleted
        )
        # PI-108: formatted Created synthetic column for the master pane.
        for r in records:
            r["created_at_display"] = format_timestamp(
                r.get("persona_created_at")
            )
        return records

    def list_columns(self) -> list[ColumnSpec]:
        # Per persona.md §3.6.2: four columns; no Domains or
        # Realized-as columns in v0.5+ (deferred to PI-007/PI-009).
        return [
            ColumnSpec(
                field="persona_identifier", title="Identifier", width=120
            ),
            ColumnSpec(field="persona_name", title="Name"),
            ColumnSpec(field="persona_status", title="Status", width=110),
            ColumnSpec(
                field="created_at_display", title="Created", width=140
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("persona_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("persona_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "persona", identifier
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

        identifier = record.get("persona_identifier") or ""
        is_deleted = record.get("persona_deleted_at") is not None

        # Edit / Delete (or Restore / Edit) action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_persona_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_persona_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_persona_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("persona_name") or "(unnamed)")
        )

        # Fields 1-3 in section-3.2 order: identifier (read-only label),
        # name, role summary.
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("persona_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("persona_name") or "")
        name_value.setObjectName("persona_name_value")
        form.addRow(required_label("Name"), name_value)

        role_summary_value = _read_only_text(
            record.get("persona_role_summary") or "",
            placeholder=_ROLE_SUMMARY_PLACEHOLDER,
        )
        role_summary_value.setObjectName("persona_role_summary_value")
        form.addRow(required_label("Role summary"), role_summary_value)
        outer.addLayout(form)

        # Field 4: persona_responsibilities under a collapsible
        # "Responsibilities" header, **expanded by default** per
        # persona.md §3.6.3 (the field is optional, but when populated
        # it carries client-facing content distinct from the consultant
        # scratchpad).
        responsibilities_value = _read_only_text(
            record.get("persona_responsibilities") or ""
        )
        responsibilities_value.setObjectName("persona_responsibilities_value")
        responsibilities_section = CollapsibleSection(
            "Responsibilities", responsibilities_value, expanded=True
        )
        responsibilities_section.setObjectName(
            "persona_responsibilities_toggle"
        )
        outer.addWidget(responsibilities_section)

        # Field 5: persona_notes under a collapsible "Internal notes"
        # header, collapsed by default per persona.md §3.6.3.
        notes_value = _read_only_text(record.get("persona_notes") or "")
        notes_value.setObjectName("persona_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("persona_notes_toggle")
        outer.addWidget(notes_section)

        # Field 6: persona_status — combo box restricted to the valid
        # successors of the record's current status; disabled because
        # the detail pane is a view (editing goes through the dialog).
        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_status = record.get("persona_status") or "candidate"
        status_combo = QComboBox()
        status_combo.setObjectName("persona_status_value")
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
                record, "persona_created_at", "persona_updated_at"
            )
        )

        outer.addWidget(_separator())

        # Field 7: the shared ReferencesSection. The first methodology
        # panel to render *two* outgoing reference kinds —
        # ``persona_scopes_to_domain`` and ``persona_realized_as_entity``
        # — attached from the "Add reference" affordance. The widget is
        # always present for v0.5+ inbound kinds too (none declared yet
        # by source-side specs; PI-005 process growth will register
        # ``process_performed_by_persona`` when it lands).
        references_section = ReferencesSection(
            "persona",
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

    # ------------------------------------------------------------------
    # Identifier addressing (persona uses ``persona_identifier``, not the
    # base's ``identifier`` key)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("persona_identifier") == identifier:
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
            ident = self._records[row].get("persona_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New persona")
            new_action.triggered.connect(self._on_new_persona_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New persona")
        new_action.triggered.connect(self._on_new_persona_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("persona_deleted_at") is not None:
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

    def _on_new_persona_clicked(self) -> None:
        dialog = PersonaCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("persona_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_persona(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost loading %s for edit: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Persona error loading %s for edit: %s", identifier, exc)
            ErrorDialog(
                title="Could not load persona",
                message="Could not load the latest version of this persona.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = PersonaEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("persona_identifier") or ""
        name = record.get("persona_name") or ""
        if not identifier:
            return
        dialog = PersonaDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("persona_identifier") or ""
        name = record.get("persona_name") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore persona")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Personas list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_persona(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Persona error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore persona",
                message=(
                    "An error occurred while restoring the persona. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
