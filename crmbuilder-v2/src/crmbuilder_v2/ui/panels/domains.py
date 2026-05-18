"""Domains panel — the first methodology entity type (UI v0.4 slice B).

A ``ListDetailPanel`` for the ``domain`` entity, registered as the first
entry under the Methodology sidebar group. Mirrors the v0.3
governance-entity panels (Decisions is the closest template): a master
table with a Show-deleted toggle and a New button, a structured
read-only detail pane with Edit/Delete (or Restore) actions, and a
right-click context menu.

Detail pane layout follows ``domain.md`` section 3.6.3: identifier
(read-only label), name, purpose, description (read-only editors),
``domain_notes`` under a collapsible "Internal notes" header collapsed
by default, status, and the shared ``ReferencesSection`` widget. The
section renders inbound references only — ``domain`` has no outgoing
references in v0.4; the inbound side populates as slices C and D bring
entity and process records that reference domains.
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
from crmbuilder_v2.ui.dialogs._domain_schema import status_choices
from crmbuilder_v2.ui.dialogs.domain_crud import (
    DomainCreateDialog,
    DomainDeleteDialog,
    DomainEditDialog,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
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

_log = logging.getLogger("crmbuilder_v2.ui.panels.domains")

_LONG_TEXT_MIN_HEIGHT = 80
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


class DomainsPanel(ListDetailPanel):
    """Domains panel with read + write surfaces (UI v0.4 slice B)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Domain")
        self._new_button.setObjectName("new_domain_button")
        self._new_button.clicked.connect(self._on_new_domain_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Domains"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_domains(include_deleted=self._include_deleted)

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(
                field="domain_identifier", title="Identifier", width=120
            ),
            ColumnSpec(field="domain_name", title="Name"),
            ColumnSpec(field="domain_status", title="Status", width=110),
            ColumnSpec(
                field="domain_updated_at", title="Updated", width=180
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("domain_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("domain_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "domain", identifier
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

        identifier = record.get("domain_identifier") or ""
        is_deleted = record.get("domain_deleted_at") is not None

        # Edit / Delete (or Restore / Edit) action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_domain_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_domain_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_domain_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(_heading_label(record.get("domain_name") or "(unnamed)"))

        # Fields 1-4 in section-3.2 order: identifier (read-only label),
        # name, purpose, description.
        form = QFormLayout()
        # v0.6 slice C: label-above form layout per design pass §2.4.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("domain_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("domain_name") or "")
        name_value.setObjectName("domain_name_value")
        form.addRow(required_label("Name"), name_value)

        purpose_value = _read_only_line(
            record.get("domain_purpose") or "", placeholder="One sentence"
        )
        purpose_value.setObjectName("domain_purpose_value")
        form.addRow(required_label("Purpose"), purpose_value)

        description_value = _read_only_text(
            record.get("domain_description") or "",
            placeholder="Brief paragraph",
        )
        description_value.setObjectName("domain_description_value")
        form.addRow(required_label("Description"), description_value)
        outer.addLayout(form)

        # Field 5: domain_notes under a collapsible "Internal notes"
        # header, collapsed by default (the deliberate UX cue that notes
        # are internal consultant scratchpad, not client-facing). v0.6
        # slice C: replaces the flat QToolButton with the design pass
        # §2.4 chevron + label treatment via CollapsibleSection.
        notes_value = _read_only_text(record.get("domain_notes") or "")
        notes_value.setObjectName("domain_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("domain_notes_toggle")
        outer.addWidget(notes_section)

        # Field 6: domain_status — combo box restricted to the valid
        # successors of the record's current status; disabled because
        # the detail pane is a view (editing goes through the dialog).
        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        current_status = record.get("domain_status") or "candidate"
        status_combo = QComboBox()
        status_combo.setObjectName("domain_status_value")
        status_combo.addItems(status_choices(current_status))
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        # v0.6 slice C: "Valid transitions" hint caption below the
        # status combo per design pass §2.4. Empty for terminal states.
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

        # Field 7: the shared ReferencesSection. ``domain`` has no
        # outgoing references in v0.4; the inbound side populates as
        # slices C/D register entity/process → domain relationship kinds.
        references_section = ReferencesSection(
            "domain",
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
    # Identifier addressing (domain uses ``domain_identifier``, not the
    # base's ``identifier`` key)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("domain_identifier") == identifier:
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
            ident = self._records[row].get("domain_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New domain")
            new_action.triggered.connect(self._on_new_domain_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New domain")
        new_action.triggered.connect(self._on_new_domain_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("domain_deleted_at") is not None:
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

    def _on_new_domain_clicked(self) -> None:
        dialog = DomainCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("domain_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_domain(identifier)
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
                title="Could not load domain",
                message="Could not load the latest version of this domain.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = DomainEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("domain_identifier") or ""
        name = record.get("domain_name") or ""
        if not identifier:
            return
        dialog = DomainDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("domain_identifier") or ""
        name = record.get("domain_name") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore domain")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Domains list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_domain(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Domain error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore domain",
                message=(
                    "An error occurred while restoring the domain. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
