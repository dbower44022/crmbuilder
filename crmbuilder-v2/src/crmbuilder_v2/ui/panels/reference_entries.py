"""Reference Entries panel — the cross-engagement reference library (REL-016 / PI-067).

A ``RegistryCrudPanel`` with create/edit/delete for reference entries (Domain
Knowledge / Organization Structure / Inventory Items), plus "Edit content…" and
"Edit keywords…" actions that edit the JSON ``content`` / ``trigger_keywords``
columns via ``JsonFieldDialog``. Entries are system/shared with a nullable
engagement scope (shown in the Scope column).
"""

from __future__ import annotations

import json as _json
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec
from crmbuilder_v2.ui.dialogs.reference_entry_crud import (
    ReferenceEntryCreateDialog,
    ReferenceEntryDeleteDialog,
    ReferenceEntryEditDialog,
)
from crmbuilder_v2.ui.dialogs.registry_crud import JsonFieldDialog
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.panels._registry_panel_base import (
    RegistryCrudPanel,
    field_label,
    heading_label,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.form_helpers import destructive_button


class ReferenceEntriesPanel(RegistryCrudPanel):
    new_button_label = "New Reference Entry"
    entity_noun = "reference entry"

    def entity_title(self) -> str:
        return "Reference Entries"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_reference_entries()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=100),
            ColumnSpec(field="name", title="Name"),
            ColumnSpec(field="kind", title="Kind", width=170),
            ColumnSpec(field="applies_to", title="Applies to", width=160),
            ColumnSpec(field="scope", title="Scope", width=100),
            ColumnSpec(field="status", title="Status", width=80),
        ]

    def _new_dialog(self) -> QDialog:
        return ReferenceEntryCreateDialog(self._client, self)

    def _edit_dialog(self, record: dict[str, Any]) -> QDialog:
        return ReferenceEntryEditDialog(self._client, record, self)

    def _delete_dialog(self, identifier: str, label: str) -> QDialog:
        return ReferenceEntryDeleteDialog(self._client, identifier, label, self)

    def _fetch_one(self, identifier: str) -> dict[str, Any]:
        return self._client.get_reference_entry(identifier)

    def _record_label(self, record: dict[str, Any]) -> str:
        return str(record.get("name") or record.get("identifier") or "")

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        strip_layout.addWidget(edit_btn)
        content_btn = QPushButton("Edit content…")
        content_btn.clicked.connect(lambda _c=False, r=record: self._edit_json(r, "content", "Content"))
        strip_layout.addWidget(content_btn)
        kw_btn = QPushButton("Edit keywords…")
        kw_btn.clicked.connect(
            lambda _c=False, r=record: self._edit_json(r, "trigger_keywords", "Trigger keywords")
        )
        strip_layout.addWidget(kw_btn)
        delete_btn = destructive_button("Delete")
        delete_btn.clicked.connect(lambda _c=False, r=record: self._on_delete_clicked(r))
        strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(strip)

        outer.addWidget(heading_label(record.get("name") or "(unnamed)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Identifier", field_label(record.get("identifier") or "—"))
        form.addRow("Kind", field_label(record.get("kind") or ""))
        form.addRow("Applies to", field_label(record.get("applies_to") or "—"))
        form.addRow("Scope", field_label(record.get("scope") or "system"))
        form.addRow("Status", field_label(record.get("status") or ""))
        keywords = record.get("trigger_keywords") or []
        form.addRow(
            "Trigger keywords",
            field_label(", ".join(keywords) if isinstance(keywords, list) and keywords else "—"),
        )
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(field_label("Content"))
        content = record.get("content")
        outer.addWidget(
            read_only_text(_json.dumps(content, indent=2) if content else "")
        )

        outer.addWidget(separator())
        outer.addWidget(created_updated_section(record, "created_at", "updated_at"))
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _edit_json(self, record: dict[str, Any], field_key: str, label: str) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        dialog = JsonFieldDialog(
            self._client.patch_reference_entry,
            identifier,
            field_key,
            label,
            record.get(field_key),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
