"""CRM Candidates panel — the fourth methodology entity type (UI v0.4 slice E).

A ``ListDetailPanel`` for the ``crm_candidate`` entity, registered as
the fourth (and final) entry under the Methodology sidebar group.
Mirrors slice B's ``DomainsPanel`` — ``crm_candidate`` has no required
FK and no outgoing references, so the panel shape is the closest of
the four methodology entity types to slice B's template.

Detail pane layout follows ``crm_candidate.md`` section 3.6.3:
identifier (read-only label), name (read-only line), fit-reason
(read-only multi-line text), ``crm_candidate_notes`` under a
collapsible "Internal notes" header collapsed by default, status, and
the shared ``ReferencesSection`` widget. The section renders inbound
references only — ``crm_candidate`` has no outgoing references in
v0.4; the inbound side populates as governance entities (decisions,
sessions) cite this candidate via ``is_about`` / ``references`` /
``decided_in`` per spec section 3.3.2.

Default sort is identifier-ascending per DEC-072. Terminal-state
records (``selected``, ``declined``, ``removed``) interleave with
``active`` records by identifier in v0.4; status-then-identifier
ordering (Option B) is reserved as a v0.5+ candidate gated on
CBM-redo signal.
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs._crm_candidate_schema import status_choices
from crmbuilder_v2.ui.dialogs.crm_candidate_crud import (
    CrmCandidateCreateDialog,
    CrmCandidateDeleteDialog,
    CrmCandidateEditDialog,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    RequestShapeError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.crm_candidates")

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


class CrmCandidatesPanel(ListDetailPanel):
    """CRM Candidates panel with read + write surfaces (UI v0.4 slice E)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = QPushButton("New CRM Candidate")
        self._new_button.setObjectName("new_crm_candidate_button")
        self._new_button.clicked.connect(self._on_new_crm_candidate_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "CRM Candidates"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_crm_candidates(
            include_deleted=self._include_deleted
        )

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(
                field="crm_candidate_identifier", title="Identifier", width=120
            ),
            ColumnSpec(field="crm_candidate_name", title="Name"),
            ColumnSpec(
                field="crm_candidate_status", title="Status", width=110
            ),
            ColumnSpec(
                field="crm_candidate_updated_at", title="Updated", width=180
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("crm_candidate_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("crm_candidate_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "crm_candidate", identifier
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

        identifier = record.get("crm_candidate_identifier") or ""
        is_deleted = record.get("crm_candidate_deleted_at") is not None

        # Edit / Delete (or Restore / Edit) action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_crm_candidate_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_crm_candidate_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = QPushButton("Delete")
            delete_btn.setObjectName("delete_crm_candidate_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("crm_candidate_name") or "(unnamed)")
        )

        # Fields 1-3 in section-3.2 order: identifier (read-only label),
        # name, fit-reason.
        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("crm_candidate_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("crm_candidate_name") or "")
        name_value.setObjectName("crm_candidate_name_value")
        form.addRow("Name", name_value)

        fit_reason_value = _read_only_text(
            record.get("crm_candidate_fit_reason") or "",
            placeholder=(
                "What about this CRM made it worth considering for the engagement"
            ),
        )
        fit_reason_value.setObjectName("crm_candidate_fit_reason_value")
        form.addRow("Fit reason", fit_reason_value)
        outer.addLayout(form)

        # Field 4: crm_candidate_notes under a collapsible "Internal
        # notes" header, collapsed by default — internal consultant
        # scratchpad, not part of any client-facing render.
        notes_toggle = QToolButton()
        notes_toggle.setObjectName("crm_candidate_notes_toggle")
        notes_toggle.setText("Internal notes")
        notes_toggle.setCheckable(True)
        notes_toggle.setChecked(False)
        notes_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        notes_toggle.setArrowType(Qt.ArrowType.RightArrow)
        notes_toggle.setStyleSheet("QToolButton { border: none; }")
        notes_value = _read_only_text(record.get("crm_candidate_notes") or "")
        notes_value.setObjectName("crm_candidate_notes_value")
        notes_value.setVisible(False)

        def _toggle_notes(checked: bool, w=notes_value, t=notes_toggle) -> None:
            w.setVisible(checked)
            t.setArrowType(
                Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
            )

        notes_toggle.toggled.connect(_toggle_notes)
        outer.addWidget(notes_toggle)
        outer.addWidget(notes_value)

        # Field 5: crm_candidate_status — combo box restricted to the
        # valid successors of the record's current status; disabled
        # because the detail pane is a view (editing goes through the
        # dialog). For terminal-state records the combo shows only the
        # current value, effectively read-only.
        status_row = QFormLayout()
        status_row.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        current_status = record.get("crm_candidate_status") or "active"
        status_combo = QComboBox()
        status_combo.setObjectName("crm_candidate_status_value")
        status_combo.addItems(status_choices(current_status))
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        status_row.addRow("Status", status_combo)
        outer.addLayout(status_row)

        outer.addWidget(_separator())

        # Field 6: the shared ReferencesSection. ``crm_candidate`` has
        # no outgoing references in v0.4; the inbound side populates
        # as governance entities cite this candidate per spec 3.3.2.
        references_section = ReferencesSection(
            "crm_candidate",
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
    # Identifier addressing (crm_candidate uses ``crm_candidate_identifier``)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("crm_candidate_identifier") == identifier:
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
            ident = self._records[row].get("crm_candidate_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New CRM candidate")
            new_action.triggered.connect(self._on_new_crm_candidate_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New CRM candidate")
        new_action.triggered.connect(self._on_new_crm_candidate_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("crm_candidate_deleted_at") is not None:
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

    def _on_new_crm_candidate_clicked(self) -> None:
        dialog = CrmCandidateCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("crm_candidate_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_crm_candidate(identifier)
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
                "Domain error loading %s for edit: %s", identifier, exc
            )
            ErrorDialog(
                title="Could not load CRM candidate",
                message=(
                    "Could not load the latest version of this CRM "
                    "candidate."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = CrmCandidateEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("crm_candidate_identifier") or ""
        name = record.get("crm_candidate_name") or ""
        if not identifier:
            return
        dialog = CrmCandidateDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("crm_candidate_identifier") or ""
        name = record.get("crm_candidate_name") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore CRM candidate")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default CRM Candidates list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_crm_candidate(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except RequestShapeError as exc:
            # Includes the singleton-``selected`` conflict on restore.
            payload = exc.dedicated_error
            if (
                isinstance(payload, dict)
                and payload.get("error") == "selected_candidate_already_exists"
            ):
                existing = str(payload.get("existing") or "another candidate")
                ErrorDialog(
                    title="Could not restore CRM candidate",
                    message=(
                        f"Cannot restore {identifier}: it is marked "
                        f"selected, and {existing} is already selected. "
                        "Change the live selected record's status first, "
                        "or delete it, before restoring this one."
                    ),
                    detail=str(exc),
                    parent=self,
                ).exec()
                self.refresh()
                return
            _log.warning("Validation error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore CRM candidate",
                message=exc.message or str(exc),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        except StorageClientError as exc:
            _log.warning("Domain error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore CRM candidate",
                message=(
                    "An error occurred while restoring the CRM candidate. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
