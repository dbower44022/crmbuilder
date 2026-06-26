"""Governance Rules panel — the registry ``governance_rule`` entity (PI-330).

Full create/edit/delete for governance rules plus an "Edit predicate…" action
for the JSON ``predicate`` column. Rules are system/shared with a nullable
engagement scope; an engagement-scoped rule whose ``rule_type`` is
``disable:<id-or-rule_type>`` suppresses a system rule for that engagement, and
an engagement rule sharing a system rule's ``rule_type`` overrides it.
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
    GovernanceRuleCreateDialog,
    GovernanceRuleDeleteDialog,
    GovernanceRuleEditDialog,
    JsonFieldDialog,
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


class GovernanceRulesPanel(RegistryCrudPanel):
    new_button_label = "New Rule"
    entity_noun = "governance rule"

    def entity_title(self) -> str:
        return "Governance Rules"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_governance_rules()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=100),
            ColumnSpec(field="rule_type", title="Rule type", width=160),
            ColumnSpec(field="enforcement", title="Enforcement", width=150),
            ColumnSpec(field="scope", title="Scope", width=110),
            ColumnSpec(field="status", title="Status", width=90),
        ]

    def _new_dialog(self) -> QDialog:
        return GovernanceRuleCreateDialog(self._client, self)

    def _edit_dialog(self, record: dict[str, Any]) -> QDialog:
        return GovernanceRuleEditDialog(self._client, record, self)

    def _delete_dialog(self, identifier: str, label: str) -> QDialog:
        return GovernanceRuleDeleteDialog(self._client, identifier, label, self)

    def _fetch_one(self, identifier: str) -> dict[str, Any]:
        return self._client.get_governance_rule(identifier)

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
        json_btn = QPushButton("Edit predicate…")
        json_btn.clicked.connect(lambda _c=False, r=record: self._edit_predicate(r))
        strip_layout.addWidget(json_btn)
        delete_btn = destructive_button("Delete")
        delete_btn.clicked.connect(lambda _c=False, r=record: self._on_delete_clicked(r))
        strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(strip)

        outer.addWidget(heading_label(record.get("identifier") or "(rule)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Rule type", field_label(record.get("rule_type") or "—"))
        form.addRow("Enforcement", field_label(record.get("enforcement") or ""))
        form.addRow("Severity", field_label(record.get("severity") or "—"))
        form.addRow("Scope", field_label(record.get("scope") or "system"))
        form.addRow("Status", field_label(record.get("status") or ""))
        form.addRow("Version", field_label(str(record.get("version") or "")))
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(field_label("Rule body"))
        outer.addWidget(read_only_text(record.get("body") or ""))

        predicate = record.get("predicate")
        if predicate:
            import json as _json

            outer.addWidget(field_label("Predicate", dim=True))
            outer.addWidget(read_only_text(_json.dumps(predicate, indent=2)))

        outer.addWidget(separator())
        outer.addWidget(created_updated_section(record, "created_at", "updated_at"))
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _edit_predicate(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        dialog = JsonFieldDialog(
            self._client.patch_governance_rule,
            identifier,
            "predicate",
            "Predicate",
            record.get("predicate"),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
