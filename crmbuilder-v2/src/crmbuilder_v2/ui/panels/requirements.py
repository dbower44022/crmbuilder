"""Requirements panel — PI-004 cohort methodology entity (v0.5+).

A ``ListDetailPanel`` for the ``requirement`` entity, registered
under the Methodology sidebar group between Processes and CRM
Candidates. Mirrors the slice-C ``EntitiesPanel`` with
requirement-specific adjustments:

* **Five-column master pane** per spec §3.6.2 / acceptance criterion 11
  (Identifier / Name / Priority / Status / Updated). The Priority
  column ships by default; spec §3.6.2 flags it for build-conversation
  review but AC-11 requires the five-column shape.
* **Acceptance-summary editor** in the detail pane between Description
  and Notes per spec §3.6.3.
* **Title-cased Priority combo** ("Must" / "Should" / "Could" / "Won't")
  rendered above Status per spec §3.6.3.
* **All five outbound reference kinds** surface through the shared
  ``ReferencesSection`` widget — the cascading dialog vocab clauses
  from ``vocab.py`` gate which target types are offered.
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
from crmbuilder_v2.ui.dialogs._requirement_schema import status_choices
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.requirement_crud import (
    RequirementCreateDialog,
    RequirementDeleteDialog,
    RequirementEditDialog,
)
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.styling import t as _T
from crmbuilder_v2.ui.widgets.form_helpers import (
    CollapsibleSection,
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.requirements")

_LONG_TEXT_MIN_HEIGHT = 80
_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"
_DESCRIPTION_PLACEHOLDER = "Plain-text description of the capability"
_ACCEPTANCE_PLACEHOLDER = (
    "What 'this is satisfied' looks like at a methodology level"
)

_PRIORITY_DISPLAY = {
    "must": "Must",
    "should": "Should",
    "could": "Could",
    "wont": "Won't",
}


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


class RequirementsPanel(ListDetailPanel):
    """Requirements panel with read + write surfaces (PI-004 cohort)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Requirement")
        self._new_button.setObjectName("new_requirement_button")
        self._new_button.clicked.connect(self._on_new_requirement_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Requirements"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_requirements(
            include_deleted=self._include_deleted
        )

    def list_columns(self) -> list[ColumnSpec]:
        # Five-column master per spec §3.6.2 + AC-11. Priority column
        # ships by default — spec flags it for review but the acceptance
        # criterion explicitly requires the five-column shape.
        return [
            ColumnSpec(
                field="requirement_identifier",
                title="Identifier",
                width=120,
            ),
            ColumnSpec(field="requirement_name", title="Name"),
            ColumnSpec(
                field="requirement_priority", title="Priority", width=100
            ),
            ColumnSpec(
                field="requirement_status", title="Status", width=110
            ),
            ColumnSpec(
                field="requirement_updated_at", title="Updated", width=180
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("requirement_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("requirement_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "requirement", identifier
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

        identifier = record.get("requirement_identifier") or ""
        is_deleted = record.get("requirement_deleted_at") is not None

        # Edit / Delete (or Restore / Edit) action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_requirement_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_requirement_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_requirement_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("requirement_name") or "(unnamed)")
        )

        # Fields 1-3 in section-3.2 order: identifier (read-only label),
        # name, description.
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("requirement_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("requirement_name") or "")
        name_value.setObjectName("requirement_name_value")
        form.addRow(required_label("Name"), name_value)

        description_value = _read_only_text(
            record.get("requirement_description") or "",
            placeholder=_DESCRIPTION_PLACEHOLDER,
        )
        description_value.setObjectName("requirement_description_value")
        form.addRow(required_label("Description"), description_value)

        # Field 4: acceptance summary — sits between description and the
        # collapsible notes section per spec §3.6.3 ordering.
        acceptance_value = _read_only_text(
            record.get("requirement_acceptance_summary") or "",
            placeholder=_ACCEPTANCE_PLACEHOLDER,
        )
        acceptance_value.setObjectName(
            "requirement_acceptance_summary_value"
        )
        form.addRow(required_label("Acceptance summary"), acceptance_value)
        outer.addLayout(form)

        # Field 5: requirement_notes under a collapsible "Internal
        # notes" header, collapsed by default.
        notes_value = _read_only_text(record.get("requirement_notes") or "")
        notes_value.setObjectName("requirement_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("requirement_notes_toggle")
        outer.addWidget(notes_section)

        # Field 6: requirement_priority — combo box with the four MoSCoW
        # values rendered title-cased ("Must" / "Should" / "Could" /
        # "Won't") per spec §3.6.2 / §3.6.3. Priority transitions are
        # unconstrained per spec §3.2.3 — the combo is disabled here
        # because the detail pane is a view (editing goes through the
        # dialog), but the dialog's combo offers all four values.
        priority_row = QFormLayout()
        priority_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_priority = record.get("requirement_priority") or "should"
        priority_combo = QComboBox()
        priority_combo.setObjectName("requirement_priority_value")
        priority_combo.addItems(["Must", "Should", "Could", "Won't"])
        display_priority = _PRIORITY_DISPLAY.get(current_priority, "Should")
        idx = priority_combo.findText(display_priority)
        if idx >= 0:
            priority_combo.setCurrentIndex(idx)
        priority_combo.setEnabled(False)
        priority_row.addRow(required_label("Priority"), priority_combo)
        outer.addLayout(priority_row)

        # Field 7: requirement_status — combo box restricted to the
        # valid successors of the record's current status; disabled
        # because the detail pane is a view (editing goes through the
        # dialog).
        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_status = record.get("requirement_status") or "candidate"
        status_combo = QComboBox()
        status_combo.setObjectName("requirement_status_value")
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

        outer.addWidget(_separator())

        # Field 8: the shared ReferencesSection. Renders all five
        # outbound kinds plus any inbound references (none in v0.5+
        # PI-004 cohort).
        references_section = ReferencesSection(
            "requirement",
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
    # Identifier addressing (requirement uses ``requirement_identifier``)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("requirement_identifier") == identifier:
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
            ident = self._records[row].get("requirement_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New requirement")
            new_action.triggered.connect(self._on_new_requirement_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New requirement")
        new_action.triggered.connect(self._on_new_requirement_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("requirement_deleted_at") is not None:
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

    def _on_new_requirement_clicked(self) -> None:
        dialog = RequirementCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("requirement_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_requirement(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning(
                "Connection lost loading %s for edit: %s", identifier, exc
            )
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning(
                "Requirement error loading %s for edit: %s", identifier, exc
            )
            ErrorDialog(
                title="Could not load requirement",
                message="Could not load the latest version of this requirement.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = RequirementEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("requirement_identifier") or ""
        name = record.get("requirement_name") or ""
        if not identifier:
            return
        dialog = RequirementDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("requirement_identifier") or ""
        name = record.get("requirement_name") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore requirement")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Requirements list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_requirement(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Requirement error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore requirement",
                message=(
                    "An error occurred while restoring the requirement. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
