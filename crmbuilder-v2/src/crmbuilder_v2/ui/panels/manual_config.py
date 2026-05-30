"""Manual Config panel — PI-004 cohort methodology entity (v0.5+).

A ``ListDetailPanel`` for the ``manual_config`` entity, registered as
the tail entry under the Methodology sidebar group (after Fields).
Mirrors the requirement panel pattern with manual_config-specific
adjustments per ``manual_config.md`` v1.0:

* **Five-column master pane** per spec §3.6.2 + AC-12 (Identifier /
  Name / Category / Status / Updated). Category ships as a master
  column because it is a single scalar on the table (no batched join
  required) and category-at-a-glance is high-value for the consultant
  scanning what kinds of manual action are pending.
* **Detail-pane completion-field reveal** per spec §3.6.3: the
  ``manual_config_completed_at`` and ``manual_config_completed_by``
  rows are rendered only when the record's status is ``completed``.
  Other statuses omit the section entirely (the fields are null and
  not part of the active visual).
* **Four outbound reference kinds** surface through the shared
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
from crmbuilder_v2.ui.dialogs._manual_config_schema import status_choices
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.manual_config_crud import (
    ManualConfigCreateDialog,
    ManualConfigDeleteDialog,
    ManualConfigEditDialog,
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

_log = logging.getLogger("crmbuilder_v2.ui.panels.manual_config")

_LONG_TEXT_MIN_HEIGHT = 80
_INSTRUCTIONS_MIN_HEIGHT = 120
_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"
_DESCRIPTION_PLACEHOLDER = (
    "Brief description of what the manual config is and why it exists"
)
_INSTRUCTIONS_PLACEHOLDER = "Step-by-step instructions for the operator"


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


def _read_only_text(
    value: str, *, placeholder: str = "", min_height: int = _LONG_TEXT_MIN_HEIGHT
) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    widget.setMinimumHeight(min_height)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class ManualConfigPanel(ListDetailPanel):
    """Manual Configs panel with read + write surfaces (PI-004 cohort)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Manual Config")
        self._new_button.setObjectName("new_manual_config_button")
        self._new_button.clicked.connect(self._on_new_manual_config_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Manual Configs"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_manual_configs(
            include_deleted=self._include_deleted
        )
        # PI-108: formatted Created synthetic column for the master pane.
        for r in records:
            r["created_at_display"] = format_timestamp(
                r.get("manual_config_created_at")
            )
        return records

    def list_columns(self) -> list[ColumnSpec]:
        # Five-column master pane per spec §3.6.2 + AC-12. Category
        # ships as a master column because it is a scalar field on the
        # entity table (no batched join required) and category-at-a-
        # glance is high-value for the consultant.
        return [
            ColumnSpec(
                field="manual_config_identifier",
                title="Identifier",
                width=120,
            ),
            ColumnSpec(field="manual_config_name", title="Name"),
            ColumnSpec(
                field="manual_config_category",
                title="Category",
                width=160,
            ),
            ColumnSpec(
                field="manual_config_status", title="Status", width=110
            ),
            ColumnSpec(
                field="created_at_display",
                title="Created",
                width=140,
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("manual_config_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("manual_config_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "manual_config", identifier
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

        identifier = record.get("manual_config_identifier") or ""
        is_deleted = record.get("manual_config_deleted_at") is not None
        current_status = record.get("manual_config_status") or "candidate"

        # Edit / Delete (or Restore / Edit) action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_manual_config_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_manual_config_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_manual_config_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("manual_config_name") or "(unnamed)")
        )

        # Fields 1-5 in section-3.2 order: identifier (read-only label),
        # name, category (read-only line), description, instructions.
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("manual_config_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("manual_config_name") or "")
        name_value.setObjectName("manual_config_name_value")
        form.addRow(required_label("Name"), name_value)

        category_value = _read_only_line(
            record.get("manual_config_category") or ""
        )
        category_value.setObjectName("manual_config_category_value")
        form.addRow(required_label("Category"), category_value)

        description_value = _read_only_text(
            record.get("manual_config_description") or "",
            placeholder=_DESCRIPTION_PLACEHOLDER,
        )
        description_value.setObjectName("manual_config_description_value")
        form.addRow(required_label("Description"), description_value)

        instructions_value = _read_only_text(
            record.get("manual_config_instructions") or "",
            placeholder=_INSTRUCTIONS_PLACEHOLDER,
            min_height=_INSTRUCTIONS_MIN_HEIGHT,
        )
        instructions_value.setObjectName("manual_config_instructions_value")
        form.addRow(required_label("Instructions"), instructions_value)
        outer.addLayout(form)

        # Field 6: manual_config_notes under a collapsible "Internal
        # notes" header, collapsed by default — matches domain_notes /
        # entity_notes posture (consultant scratchpad).
        notes_value = _read_only_text(
            record.get("manual_config_notes") or ""
        )
        notes_value.setObjectName("manual_config_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("manual_config_notes_toggle")
        outer.addWidget(notes_section)

        # Field 7: manual_config_status — combo box restricted to the
        # valid successors of the record's current status; disabled
        # because the detail pane is a view (editing goes through the
        # dialog).
        status_row = QFormLayout()
        status_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        status_combo = QComboBox()
        status_combo.setObjectName("manual_config_status_value")
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
            else "Terminal status (no further transitions)"
        )
        status_hint.setObjectName("statusHintCaption")
        status_layout.addWidget(status_hint)
        status_row.addRow(required_label("Status"), status_container)
        outer.addLayout(status_row)

        # Fields 8-9: conditional completion section per spec §3.6.3.
        # Rendered only when status is ``completed`` — for other
        # statuses the section is omitted entirely (the fields are null
        # and not part of the active visual). The completion timestamp
        # renders as an ISO string; the completed-by value as plain
        # text. Both are read-only since the detail pane is a view.
        if current_status == "completed":
            completion_form = QFormLayout()
            completion_form.setRowWrapPolicy(
                QFormLayout.RowWrapPolicy.WrapAllRows
            )
            completion_form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
            )
            completed_at_raw = record.get("manual_config_completed_at") or ""
            # Some payloads carry the timestamp as a Python datetime
            # (when this panel runs against an in-process client); the
            # REST client serialises to ISO already. Coerce to string
            # either way.
            completed_at_str = (
                completed_at_raw
                if isinstance(completed_at_raw, str)
                else str(completed_at_raw)
            )
            completed_at_value = _read_only_line(completed_at_str)
            completed_at_value.setObjectName(
                "manual_config_completed_at_value"
            )
            completion_form.addRow(
                required_label("Completed at"), completed_at_value
            )

            completed_by_value = _read_only_line(
                record.get("manual_config_completed_by") or ""
            )
            completed_by_value.setObjectName(
                "manual_config_completed_by_value"
            )
            completion_form.addRow(
                required_label("Completed by"), completed_by_value
            )
            outer.addLayout(completion_form)

        # PI-108: created / last-edited audit timestamps.
        outer.addWidget(_separator())
        outer.addWidget(
            created_updated_section(
                record,
                "manual_config_created_at",
                "manual_config_updated_at",
            )
        )

        outer.addWidget(_separator())

        # Field 10: the shared ReferencesSection. Renders the four
        # outbound kinds plus any inbound ``test_spec_verifies_manual_config``
        # references once ``test_spec`` lands.
        references_section = ReferencesSection(
            "manual_config",
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
    # Identifier addressing (manual_config uses ``manual_config_identifier``)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("manual_config_identifier") == identifier:
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
            ident = self._records[row].get("manual_config_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New manual config")
            new_action.triggered.connect(self._on_new_manual_config_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New manual config")
        new_action.triggered.connect(self._on_new_manual_config_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("manual_config_deleted_at") is not None:
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

    def _on_new_manual_config_clicked(self) -> None:
        dialog = ManualConfigCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("manual_config_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_manual_config(identifier)
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
                "Manual config error loading %s for edit: %s",
                identifier,
                exc,
            )
            ErrorDialog(
                title="Could not load manual config",
                message=(
                    "Could not load the latest version of this manual "
                    "config."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = ManualConfigEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("manual_config_identifier") or ""
        name = record.get("manual_config_name") or ""
        if not identifier:
            return
        dialog = ManualConfigDeleteDialog(
            self._client, identifier, name, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("manual_config_identifier") or ""
        name = record.get("manual_config_name") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore manual config")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Manual Configs list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_manual_config(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning(
                "Manual config error restoring %s: %s", identifier, exc
            )
            ErrorDialog(
                title="Could not restore manual config",
                message=(
                    "An error occurred while restoring the manual "
                    "config. Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()
