"""Learnings panel — the registry ``learning`` entity (PI-330 / REQ-367).

Full create/edit/delete for learnings plus promotion: a learning can be promoted
to a skill or to a governance rule. Promoting to an enforced rule requires an
explicit human-approval acknowledgement (the Needs-Attention hard line),
enforced by the promote dialog.
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
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.registry_crud import (
    LearningCreateDialog,
    LearningDeleteDialog,
    LearningEditDialog,
    PromoteToRuleDialog,
    PromoteToSkillDialog,
)
from crmbuilder_v2.ui.exceptions import StorageClientError, StorageConnectionError
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.panels._registry_panel_base import (
    RegistryCrudPanel,
    field_label,
    heading_label,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.form_helpers import destructive_button


class LearningsPanel(RegistryCrudPanel):
    new_button_label = "New Learning"
    entity_noun = "learning"

    def entity_title(self) -> str:
        return "Learnings"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_learnings()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=100),
            ColumnSpec(field="area", title="Area", width=140),
            ColumnSpec(field="tier", title="Tier", width=100),
            ColumnSpec(field="category", title="Category", width=110),
            ColumnSpec(field="scope", title="Scope", width=110),
            ColumnSpec(field="status", title="Status", width=90),
        ]

    def _new_dialog(self) -> QDialog:
        return LearningCreateDialog(self._client, self)

    def _edit_dialog(self, record: dict[str, Any]) -> QDialog:
        return LearningEditDialog(self._client, record, self)

    def _delete_dialog(self, identifier: str, label: str) -> QDialog:
        return LearningDeleteDialog(self._client, identifier, label, self)

    def _fetch_one(self, identifier: str) -> dict[str, Any]:
        return self._client.get_learning(identifier)

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
        skill_btn = QPushButton("Promote to skill…")
        skill_btn.clicked.connect(lambda _c=False, r=record: self._promote_to_skill(r))
        strip_layout.addWidget(skill_btn)
        rule_btn = QPushButton("Promote to rule…")
        rule_btn.clicked.connect(lambda _c=False, r=record: self._promote_to_rule(r))
        strip_layout.addWidget(rule_btn)
        delete_btn = destructive_button("Delete")
        delete_btn.clicked.connect(lambda _c=False, r=record: self._on_delete_clicked(r))
        strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(strip)

        outer.addWidget(heading_label(record.get("identifier") or "(learning)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Area", field_label(record.get("area") or ""))
        form.addRow("Tier", field_label(record.get("tier") or ""))
        form.addRow("Category", field_label(record.get("category") or ""))
        form.addRow("Scope", field_label(record.get("scope") or "system"))
        form.addRow("Status", field_label(record.get("status") or ""))
        form.addRow("Confidence", field_label(str(record.get("confidence") or 0)))
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(field_label("Content"))
        outer.addWidget(read_only_text(record.get("content") or ""))

        outer.addWidget(separator())
        outer.addWidget(created_updated_section(record, "created_at", "updated_at"))
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # --- promotion ------------------------------------------------------

    def _promote_to_skill(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        dialog = PromoteToSkillDialog(record, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        body = dialog.body()
        if body is None:
            return
        if self._call(lambda: self._client.promote_learning_to_skill(identifier, body)):
            self.refresh()

    def _promote_to_rule(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        dialog = PromoteToRuleDialog(record, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        body = dialog.body()
        if body is None:
            return
        if self._call(lambda: self._client.promote_learning_to_rule(identifier, body)):
            self.refresh()

    def _call(self, fn) -> bool:
        """Run an API call, routing errors; return True on success."""
        try:
            fn()
            return True
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return False
        except StorageClientError as exc:
            ErrorDialog(
                title="Action failed",
                message="The registry action could not be completed.",
                detail=str(exc),
                parent=self,
            ).exec()
            return False
