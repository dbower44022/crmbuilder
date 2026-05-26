"""Processes panel — the third methodology entity type (UI v0.4 slice D).

A ``ListDetailPanel`` for the ``process`` entity, registered as the
third entry under the Methodology sidebar group (after Entities).
Mirrors slice B/C's panels with process-specific adjustments.

Process-specific detail-pane shape per ``process.md`` section 3.6.3:

* No status field — ``process_classification`` carries the lifecycle;
  the master pane's third column is "Classification".
* ``process_domain_identifier`` renders as a read-only domain line. If
  the referenced domain is missing or soft-deleted, an inline warning
  is shown above it (spec section 3.4.5 / PRD 4.5 — re-affiliation
  warning); the operator clicks Edit to re-affiliate.
* ``process_classification_rationale`` carries a placeholder that
  varies by the record's current classification.
* The shared ``ReferencesSection`` renders the bidirectional
  ``process_hands_off_to_process`` edges with the direction
  sub-headings relabelled "Hands off to" (outbound) and "Receives
  from" (inbound).
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
from crmbuilder_v2.ui.dialogs._process_schema import (
    CLASSIFICATION_RATIONALE_PLACEHOLDERS,
    classification_choices,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.process_crud import (
    ProcessCreateDialog,
    ProcessDeleteDialog,
    ProcessEditDialog,
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
from crmbuilder_v2.ui.widgets.warning_callout import WarningCallout

_log = logging.getLogger("crmbuilder_v2.ui.panels.processes")

_LONG_TEXT_MIN_HEIGHT = 80
_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"
_PURPOSE_PLACEHOLDER = "One sentence — what does this process do?"

# Phase 3 detailed-process sections (v0.8, PI-005, process-v2.md §3.6.3).
# Six collapsible sub-sections rendered below the v0.4 classification-
# rationale row and above the Internal notes section. Each entry is
# (field_key, label, placeholder).
_PHASE3_SECTION_SPECS: list[tuple[str, str, str]] = [
    (
        "process_steps",
        "Steps",
        "Numbered or bulleted list of process steps in execution order",
    ),
    (
        "process_triggers",
        "Triggers",
        "What initiates this process",
    ),
    (
        "process_outcomes",
        "Outcomes",
        (
            "What success looks like — state changes, records created, "
            "communications sent"
        ),
    ),
    (
        "process_edge_cases",
        "Edge Cases",
        "Known exceptions, error paths, retry semantics",
    ),
    (
        "process_frequency",
        "Frequency",
        "How often this process runs",
    ),
    (
        "process_duration_estimate",
        "Duration",
        "Typical wall-clock duration",
    ),
]


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


class ProcessesPanel(ListDetailPanel):
    """Processes panel with read + write surfaces (UI v0.4 slice D)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Process")
        self._new_button.setObjectName("new_process_button")
        self._new_button.clicked.connect(self._on_new_process_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Processes"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_processes(
            include_deleted=self._include_deleted
        )

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(
                field="process_identifier", title="Identifier", width=120
            ),
            ColumnSpec(field="process_name", title="Name"),
            ColumnSpec(
                field="process_classification",
                title="Classification",
                width=140,
            ),
            ColumnSpec(
                field="process_updated_at", title="Updated", width=180
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("process_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("process_identifier")
        domain_identifier = record.get("process_domain_identifier") or ""
        extras: dict[str, Any] = {
            "references": {"as_source": [], "as_target": []},
            "domain": None,
        }
        if identifier:
            extras["references"] = self._client.list_references_touching(
                "process", identifier
            )
        if domain_identifier:
            # ``get_domain`` 404s a missing-or-soft-deleted domain; that
            # is exactly the stale-FK condition the detail pane warns
            # about, so a NotFoundError leaves ``domain`` as None.
            try:
                extras["domain"] = self._client.get_domain(domain_identifier)
            except NotFoundError:
                extras["domain"] = None
            except StorageClientError:
                extras["domain"] = None
        return extras

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("process_identifier") or ""
        is_deleted = record.get("process_deleted_at") is not None
        domain_identifier = record.get("process_domain_identifier") or ""
        domain_record = extras.get("domain")

        # Edit / Delete (or Restore / Edit) action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_process_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_process_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_process_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("process_name") or "(unnamed)")
        )

        # Fields 1-2: identifier (read-only label), name.
        form = QFormLayout()
        # v0.6 slice C: label-above form layout per design pass §2.4.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("process_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("process_name") or "")
        name_value.setObjectName("process_name_value")
        form.addRow(required_label("Name"), name_value)

        # Field 3: process_domain_identifier. Rendered as a read-only
        # line ("DOM-NNN — Domain Name" when the FK resolves to a live
        # domain). A stale FK (missing or soft-deleted target) shows an
        # inline warning above the line per spec section 3.4.5.
        if domain_identifier and domain_record is None:
            warning = WarningCallout(
                f"This process's domain ({domain_identifier}) is "
                "missing or deleted. Click Edit to re-affiliate the "
                "process, or restore the domain."
            )
            warning.setObjectName("process_domain_warning")
            form.addRow("", warning)

        if domain_record is not None:
            domain_display = (
                f"{domain_identifier} — "
                f"{domain_record.get('domain_name') or ''}"
            )
        else:
            domain_display = domain_identifier or "—"
        domain_value = _read_only_line(domain_display)
        domain_value.setObjectName("process_domain_identifier_value")
        form.addRow(required_label("Domain"), domain_value)

        # Field 4: process_purpose.
        purpose_value = _read_only_text(
            record.get("process_purpose") or "",
            placeholder=_PURPOSE_PLACEHOLDER,
        )
        purpose_value.setObjectName("process_purpose_value")
        form.addRow(required_label("Purpose"), purpose_value)
        outer.addLayout(form)

        # Field 5: process_classification — combo box restricted to the
        # valid successors of the record's current classification;
        # disabled because the detail pane is a view.
        classification_row = QFormLayout()
        classification_row.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapAllRows
        )
        current_classification = (
            record.get("process_classification") or "unclassified"
        )
        classification_combo = QComboBox()
        classification_combo.setObjectName("process_classification_value")
        classification_combo.addItems(
            classification_choices(current_classification)
        )
        idx = classification_combo.findText(current_classification)
        if idx >= 0:
            classification_combo.setCurrentIndex(idx)
        classification_combo.setEnabled(False)
        # v0.6 slice C: "Valid transitions" hint caption below the
        # classification combo per design pass §2.4. ``classification``
        # is the process equivalent of ``status`` on Domains/Entities/
        # CRM Candidates; the same hint pattern applies.
        successors = sorted(
            set(classification_choices(current_classification))
            - {current_classification}
        )
        classification_container = QWidget()
        classification_layout = QVBoxLayout(classification_container)
        classification_layout.setContentsMargins(0, 0, 0, 0)
        classification_layout.setSpacing(int(_T("space.1").rstrip("px")))
        classification_layout.addWidget(classification_combo)
        classification_hint = QLabel(
            f"Valid transitions: {', '.join(successors)}"
            if successors
            else ""
        )
        classification_hint.setObjectName("statusHintCaption")
        classification_layout.addWidget(classification_hint)
        classification_row.addRow(
            required_label("Classification"), classification_container
        )
        outer.addLayout(classification_row)

        # Field 6: process_classification_rationale — read-only multi-line
        # with a placeholder that varies by the current classification.
        rationale_row = QFormLayout()
        rationale_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        rationale_value = _read_only_text(
            record.get("process_classification_rationale") or "",
            placeholder=CLASSIFICATION_RATIONALE_PLACEHOLDERS.get(
                current_classification,
                CLASSIFICATION_RATIONALE_PLACEHOLDERS["unclassified"],
            ),
        )
        rationale_value.setObjectName("process_classification_rationale_value")
        rationale_row.addRow("Classification rationale", rationale_value)
        outer.addLayout(rationale_row)

        # v0.8 Phase 3 detailed-process sections (PI-005, process-v2.md
        # §3.6.3). Always visible group header; each of the six
        # sub-sections defaults expanded when its column has non-
        # whitespace content and collapsed when it is NULL or empty.
        outer.addWidget(_separator())
        phase3_header = QLabel("Phase 3 — Detailed Process Definition")
        phase3_header.setObjectName("phase3_sections_header")
        phase3_font = QFont(phase3_header.font())
        phase3_font.setBold(True)
        phase3_header.setFont(phase3_font)
        outer.addWidget(phase3_header)
        for field_key, label, placeholder in _PHASE3_SECTION_SPECS:
            raw_value = record.get(field_key)
            value = raw_value if isinstance(raw_value, str) else ""
            body = _read_only_text(value, placeholder=placeholder)
            body.setObjectName(f"{field_key}_value")
            section = CollapsibleSection(
                label, body, expanded=bool(value.strip())
            )
            section.setObjectName(f"{field_key}_section")
            outer.addWidget(section)

        # Field 7: process_notes under a collapsible "Internal notes"
        # header, collapsed by default. v0.6 slice C: replaces the flat
        # QToolButton with the design pass §2.4 chevron + label
        # treatment via CollapsibleSection.
        notes_value = _read_only_text(record.get("process_notes") or "")
        notes_value.setObjectName("process_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("process_notes_toggle")
        outer.addWidget(notes_section)

        outer.addWidget(_separator())

        # Field 8: the shared ReferencesSection, with the direction
        # sub-headings relabelled for the directional
        # ``process_hands_off_to_process`` edges — "Hands off to" for
        # outbound (this process is the source/producer), "Receives
        # from" for inbound (this process is the target/consumer).
        references_section = ReferencesSection(
            "process",
            identifier,
            extras.get("references") or {},
            client=self._client,
            inbound_label="Receives from",
            outbound_label="Hands off to",
        )
        references_section.navigate_requested.connect(self.navigate_requested)
        references_section.references_changed.connect(self.refresh)
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Identifier addressing (process uses ``process_identifier``, not the
    # base's ``identifier`` key)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("process_identifier") == identifier:
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
            ident = self._records[row].get("process_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New process")
            new_action.triggered.connect(self._on_new_process_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New process")
        new_action.triggered.connect(self._on_new_process_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("process_deleted_at") is not None:
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

    def _on_new_process_clicked(self) -> None:
        dialog = ProcessCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("process_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_process(identifier)
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
                "Process error loading %s for edit: %s", identifier, exc
            )
            ErrorDialog(
                title="Could not load process",
                message="Could not load the latest version of this process.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = ProcessEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("process_identifier") or ""
        name = record.get("process_name") or ""
        if not identifier:
            return
        dialog = ProcessDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("process_identifier") or ""
        name = record.get("process_name") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore process")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Processes list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_process(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Process error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore process",
                message=(
                    "An error occurred while restoring the process. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
