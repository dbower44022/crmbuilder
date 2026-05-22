"""Deposit events panel — the sixth governance entity type (UI v0.7).

Read-only audit log per ``deposit_event.md`` §3.6: no Create/Edit/Delete/
Restore dialogs (born-terminal append-only), master pane sorts identifier
descending (audit-log deviation), and the right-click context menu is
reduced to ``Copy Identifier`` and ``Copy Log Path`` lightweight read
affordances. The references-section's Add Reference affordance is disabled.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.panels._governance_helpers import (
    heading_label,
    read_only_line,
    separator,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.deposit_events")


class DepositEventsPanel(ListDetailPanel):
    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        # No New button (born-terminal append-only).

    def entity_title(self) -> str:
        return "Deposit Events"

    def fetch_records(self) -> list[dict[str, Any]]:
        # The API already sorts by identifier descending (audit-log shape).
        return self._client.list_deposit_events()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="deposit_event_identifier", title="Identifier", width=110),
            ColumnSpec(field="deposit_event_title", title="Title"),
            ColumnSpec(field="deposit_event_outcome", title="Outcome", width=90),
            ColumnSpec(field="deposit_event_created_at", title="Created", width=180),
        ]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("deposit_event_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {"references": self._client.list_references_touching("deposit_event", identifier)}

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("deposit_event_identifier") or ""
        outer.addWidget(heading_label(record.get("deposit_event_title") or identifier))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        ident_label = QLabel(identifier or "—")
        ident_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Identifier", ident_label)
        outcome = record.get("deposit_event_outcome") or ""
        outcome_label = QLabel(outcome)
        if outcome == "success":
            outcome_label.setStyleSheet("color: #1a7f37; font-weight: bold;")
        elif outcome == "failure":
            outcome_label.setStyleSheet("color: #b22222; font-weight: bold;")
        form.addRow("Outcome", outcome_label)
        form.addRow("Created", read_only_line(record.get("deposit_event_created_at") or ""))
        form.addRow("Description", read_only_line(record.get("deposit_event_description") or ""))
        form.addRow("Log file", read_only_line(record.get("deposit_event_log_file_path") or ""))
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Records written</b>"))
        records_summary = record.get("deposit_event_records_summary") or {}
        if isinstance(records_summary, dict) and records_summary:
            summary_form = QFormLayout()
            summary_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            for key in sorted(records_summary):
                summary_form.addRow(str(key), QLabel(str(records_summary[key])))
            outer.addLayout(summary_form)
        else:
            outer.addWidget(QLabel("(none)"))

        ctx = record.get("deposit_event_apply_context") or {}
        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Apply context</b>"))
        ctx_view = QPlainTextEdit(json.dumps(ctx, indent=2, sort_keys=True))
        ctx_view.setReadOnly(True)
        ctx_view.setMinimumHeight(80)
        outer.addWidget(ctx_view)

        err = record.get("deposit_event_error_info")
        if err:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Error info</b>"))
            err_view = QPlainTextEdit(json.dumps(err, indent=2, sort_keys=True))
            err_view.setReadOnly(True)
            err_view.setMinimumHeight(80)
            outer.addWidget(err_view)

        outer.addWidget(separator())
        refs = ReferencesSection(
            "deposit_event", identifier, extras.get("references") or {}, client=self._client
        )
        # Read-only audit log: disable add affordance if the widget supports it.
        if hasattr(refs, "set_add_enabled"):
            refs.set_add_enabled(False)
        refs.navigate_requested.connect(self.navigate_requested)
        outer.addWidget(refs)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("deposit_event_identifier") == identifier:
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
        ident = self._records[idx.row()].get("deposit_event_identifier")
        return ident if isinstance(ident, str) else None

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        copy_id = menu.addAction("Copy Identifier")
        copy_id.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("deposit_event_identifier") or "")
        )
        copy_path = menu.addAction("Copy Log Path")
        copy_path.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("deposit_event_log_file_path") or "")
        )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
