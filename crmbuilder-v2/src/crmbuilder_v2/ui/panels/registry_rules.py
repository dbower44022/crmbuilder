"""Governance Rules panel — the registry ``governance_rule`` entity (PI-330).

Full create/edit/delete for governance rules plus an "Edit predicate…" action
for the JSON ``predicate`` column. Rules are system/shared with a nullable
engagement scope; an engagement-scoped rule whose ``rule_type`` is
``disable:<id-or-rule_type>`` suppresses a system rule for that engagement, and
an engagement rule sharing a system rule's ``rule_type`` overrides it.

Effective view (REQ-537 / PI-441): a ``View:`` selector on the control line
switches between *All stored rules* (every row, as stored) and *Effective for
<active engagement>* — the override-resolved ruleset from
``GET /governance-rules?resolution=effective`` (PI-435), where an override
displaces the system default of the same ``rule_type`` and carries ``shadows``.
The Shadows column and the detail pane's ``Supersedes`` / ``Superseded by``
rows (REQ-538, read from the ``supersedes`` reference edges) make a client's
deviations from the defaults visible where the rule is inspected.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
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
from crmbuilder_v2.ui.exceptions import StorageClientError
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.panels._registry_panel_base import (
    RegistryCrudPanel,
    field_label,
    heading_label,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.form_helpers import destructive_button

VIEW_ALL = "all"
VIEW_EFFECTIVE = "effective"
_SUPERSEDES = "supersedes"


class GovernanceRulesPanel(RegistryCrudPanel):
    new_button_label = "New Rule"
    entity_noun = "governance rule"

    def __init__(self, client, parent=None):
        # The view selector is built inside ``_build_ui`` (via
        # ``_filter_strip_widget``), so its state must exist first.
        self._view_mode = VIEW_ALL
        self._view_combo: QComboBox | None = None
        super().__init__(client, parent)

    def entity_title(self) -> str:
        return "Governance Rules"

    @property
    def view_mode(self) -> str:
        """``VIEW_ALL`` (stored rows) or ``VIEW_EFFECTIVE`` (override-resolved)."""
        return self._view_mode

    def fetch_records(self) -> list[dict[str, Any]]:
        if self._view_mode == VIEW_EFFECTIVE:
            return self._client.list_governance_rules(resolution="effective")
        return self._client.list_governance_rules()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=100),
            ColumnSpec(field="rule_type", title="Rule type", width=160),
            ColumnSpec(field="enforcement", title="Enforcement", width=150),
            ColumnSpec(field="applies_to", title="Audience", width=110),
            ColumnSpec(field="applies_when", title="Moment", width=120),
            ColumnSpec(field="scope", title="Scope", width=110),
            ColumnSpec(field="status", title="Status", width=90),
            ColumnSpec(field="shadows_display", title="Shadows", width=140),
        ]

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # REQ-537: the effective view annotates each override with the system
        # defaults it displaces; the stored-rows view has no such field.
        for record in records:
            shadows = record.get("shadows") or []
            record["shadows_display"] = ", ".join(shadows)
        return records

    # --- view selector (REQ-537) ------------------------------------------

    def _filter_strip_widget(self) -> QWidget | None:
        base = super()._filter_strip_widget()
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("View:"))
        self._view_combo = QComboBox()
        self._view_combo.setObjectName("rules_view_combo")
        self._view_combo.addItem("All stored rules", VIEW_ALL)
        engagement = self._client.active_engagement() or "system"
        self._view_combo.addItem(f"Effective for {engagement}", VIEW_EFFECTIVE)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        layout.addWidget(self._view_combo)
        if base is not None:
            layout.addWidget(base)
        return container

    def _on_view_changed(self, _index: int) -> None:
        if self._view_combo is None:
            return
        mode = self._view_combo.currentData()
        if mode != self._view_mode:
            self._view_mode = mode
            self.refresh()

    # --- supersedes provenance (REQ-538) ---------------------------------

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        """Both directions of the ``supersedes`` edges touching this rule.

        ``supersedes``: identifiers of the system defaults this override
        displaces. ``superseded_by``: ``(identifier, scope)`` pairs for the
        engagement overrides that displace this default. Runs off the UI thread.
        """
        identifier = record.get("identifier")
        if not identifier:
            return {}
        touching = self._client.list_references_touching("governance_rule", identifier)
        supersedes = [
            edge["target_id"]
            for edge in touching["as_source"]
            if edge.get("relationship") == _SUPERSEDES
            and edge.get("target_type") == "governance_rule"
        ]
        superseded_by: list[tuple[str, str | None]] = []
        for edge in touching["as_target"]:
            if edge.get("relationship") != _SUPERSEDES or edge.get("source_type") != "governance_rule":
                continue
            source_id = edge["source_id"]
            try:
                scope = self._client.get_governance_rule(source_id).get("scope")
            except StorageClientError:
                scope = None
            superseded_by.append((source_id, scope))
        return {"supersedes": supersedes, "superseded_by": superseded_by}

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
        form.addRow("Audience", field_label(record.get("applies_to") or "all"))
        form.addRow("Moment", field_label(record.get("applies_when") or "always"))
        form.addRow("Scope", field_label(record.get("scope") or "system"))
        form.addRow("Status", field_label(record.get("status") or ""))
        form.addRow("Version", field_label(str(record.get("version") or "")))
        # REQ-537 / REQ-538: what this rule displaces, and what displaces it.
        shadows = record.get("shadows") or []
        if shadows:
            form.addRow("Shadows", field_label(", ".join(shadows)))
        supersedes = extras.get("supersedes") or []
        if supersedes:
            form.addRow("Supersedes", field_label(", ".join(supersedes)))
        superseded_by = extras.get("superseded_by") or []
        if superseded_by:
            form.addRow(
                "Superseded by",
                field_label(
                    ", ".join(
                        f"{ident} ({scope})" if scope else ident
                        for ident, scope in superseded_by
                    )
                ),
            )
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
