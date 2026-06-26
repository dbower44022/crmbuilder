"""Skills panel — the registry ``skill`` entity (PI-330 / REQ-367).

A ``ListDetailPanel`` with full create/edit/delete for skills, plus an
"Edit I/O contract…" action that edits the JSON ``io_contract`` column. Skills
are system/shared with a nullable engagement scope (shown in the Scope column).
"""

from __future__ import annotations

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
from crmbuilder_v2.ui.dialogs.registry_crud import (
    JsonFieldDialog,
    SkillCreateDialog,
    SkillDeleteDialog,
    SkillEditDialog,
)
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.panels._registry_panel_base import (
    RegistryCrudPanel,
    field_label,
    heading_label,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.form_helpers import destructive_button


class SkillsPanel(RegistryCrudPanel):
    new_button_label = "New Skill"
    entity_noun = "skill"

    def entity_title(self) -> str:
        return "Skills"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_skills()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=100),
            ColumnSpec(field="name", title="Name"),
            ColumnSpec(field="kind", title="Kind", width=100),
            ColumnSpec(field="scope", title="Scope", width=110),
            ColumnSpec(field="status", title="Status", width=90),
        ]

    def _new_dialog(self) -> QDialog:
        return SkillCreateDialog(self._client, self)

    def _edit_dialog(self, record: dict[str, Any]) -> QDialog:
        return SkillEditDialog(self._client, record, self)

    def _delete_dialog(self, identifier: str, label: str) -> QDialog:
        return SkillDeleteDialog(self._client, identifier, label, self)

    def _fetch_one(self, identifier: str) -> dict[str, Any]:
        return self._client.get_skill(identifier)

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
        json_btn = QPushButton("Edit I/O contract…")
        json_btn.clicked.connect(lambda _c=False, r=record: self._edit_io_contract(r))
        strip_layout.addWidget(json_btn)
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
        form.addRow("Scope", field_label(record.get("scope") or "system"))
        form.addRow("Status", field_label(record.get("status") or ""))
        form.addRow("Version", field_label(str(record.get("version") or "")))
        form.addRow("Backing callable", field_label(record.get("backing_callable") or "—"))
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(field_label("Description"))
        outer.addWidget(read_only_text(record.get("description") or ""))

        io_contract = record.get("io_contract")
        if io_contract:
            import json as _json

            outer.addWidget(field_label("I/O contract", dim=True))
            outer.addWidget(read_only_text(_json.dumps(io_contract, indent=2)))

        outer.addWidget(separator())
        outer.addWidget(created_updated_section(record, "created_at", "updated_at"))
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _edit_io_contract(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        dialog = JsonFieldDialog(
            self._client.patch_skill,
            identifier,
            "io_contract",
            "I/O contract",
            record.get("io_contract"),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
