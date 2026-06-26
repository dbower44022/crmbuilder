"""Agent Profiles panel — the registry centrepiece (PI-330 / REQ-367).

A master/detail panel over the ``agent_profile`` entity. The list shows every
agent (area × tier) with its system/engagement scope; the detail pane provides:

* full create / edit / delete of the profile and an "Edit capability
  description…" JSON action;
* **binding management** — the bound skills and governance rules, each with a
  Remove control, plus Add pickers (the ``agent_profile_has_skill`` /
  ``agent_profile_governed_by_rule`` edges);
* an **effective-contract preview** — the resolver's composed contract (system
  defaults merged with a chosen engagement's overrides/disables/overlay
  learnings), re-resolved live from an engagement selector.

Skills, rules, and learnings have their own panels; this one is where an agent's
configuration — its prompt, its bound capabilities, and how an engagement
customises it — is assembled and inspected.
"""

from __future__ import annotations

import json
import logging
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
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.registry_crud import (
    AgentProfileCreateDialog,
    AgentProfileDeleteDialog,
    AgentProfileEditDialog,
    BindingPickerDialog,
    JsonFieldDialog,
)
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
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

_log = logging.getLogger("crmbuilder_v2.ui.panels.agent_profiles")

_SKILL_EDGE = "agent_profile_has_skill"
_RULE_EDGE = "agent_profile_governed_by_rule"
_SYSTEM_ONLY = "__system_only__"  # bogus engagement → resolver yields system rows only


def _summarize_item(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("identifier", "name", "rule_type", "body", "content"):
            if item.get(key):
                return str(item[key])
        return json.dumps(item)[:80]
    return str(item)


class AgentProfilesPanel(RegistryCrudPanel):
    new_button_label = "New Agent Profile"
    entity_noun = "agent profile"

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        # Live references to the contract-preview widgets for the selected row.
        self._contract_profile_id: str | None = None
        self._contract_combo: QComboBox | None = None
        self._contract_view: QWidget | None = None

    # --- display hooks --------------------------------------------------

    def entity_title(self) -> str:
        return "Agent Profiles"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_agent_profiles()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=100),
            ColumnSpec(field="area", title="Area", width=140),
            ColumnSpec(field="tier", title="Tier", width=110),
            ColumnSpec(field="scope", title="Scope", width=110),
            ColumnSpec(field="status", title="Status", width=90),
        ]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("identifier") or ""
        bindings = self._client.get_agent_profile_bindings(identifier)
        all_skills = self._client.list_skills()
        all_rules = self._client.list_governance_rules()
        engagements = []
        try:
            for eng in self._client.list_engagements():
                ident = eng.get("engagement_identifier") or eng.get("identifier")
                if ident:
                    engagements.append(str(ident))
        except StorageClientError:
            pass
        contract = self._resolve_contract(identifier, None)
        return {
            "bindings": bindings,
            "all_skills": all_skills,
            "all_rules": all_rules,
            "engagements": engagements,
            "contract": contract,
        }

    # --- registry hooks -------------------------------------------------

    def _new_dialog(self) -> QDialog:
        return AgentProfileCreateDialog(self._client, self)

    def _edit_dialog(self, record: dict[str, Any]) -> QDialog:
        return AgentProfileEditDialog(self._client, record, self)

    def _delete_dialog(self, identifier: str, label: str) -> QDialog:
        return AgentProfileDeleteDialog(self._client, identifier, label, self)

    def _fetch_one(self, identifier: str) -> dict[str, Any]:
        return self._client.get_agent_profile(identifier)

    def _record_label(self, record: dict[str, Any]) -> str:
        area = record.get("area") or ""
        tier = record.get("tier") or ""
        return f"{record.get('identifier')} ({area}/{tier})"

    # --- detail rendering ----------------------------------------------

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        identifier = record.get("identifier") or ""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Action strip.
        strip = QWidget()
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(0, 0, 0, 0)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda _c=False, r=record: self._on_edit_clicked(r))
        sl.addWidget(edit_btn)
        cap_btn = QPushButton("Edit capability description…")
        cap_btn.clicked.connect(lambda _c=False, r=record: self._edit_capability(r))
        sl.addWidget(cap_btn)
        del_btn = destructive_button("Delete")
        del_btn.clicked.connect(lambda _c=False, r=record: self._on_delete_clicked(r))
        sl.addWidget(del_btn)
        sl.addStretch(1)
        outer.addWidget(strip)

        outer.addWidget(heading_label(f"{identifier} — {record.get('area')}/{record.get('tier')}"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Area", field_label(record.get("area") or ""))
        form.addRow("Tier", field_label(record.get("tier") or ""))
        form.addRow("Technology", field_label(record.get("technology") or "—"))
        form.addRow("Scope", field_label(record.get("scope") or "system"))
        form.addRow("Status", field_label(record.get("status") or ""))
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(field_label("System prompt"))
        outer.addWidget(read_only_text(record.get("description") or ""))

        capability = record.get("capability_description")
        if capability:
            outer.addWidget(field_label("Capability description", dim=True))
            outer.addWidget(read_only_text(json.dumps(capability, indent=2)))

        bindings = extras.get("bindings") or {}
        skill_labels = {s["identifier"]: s.get("name") or s["identifier"] for s in extras.get("all_skills", [])}
        rule_labels = {
            r["identifier"]: (r.get("rule_type") or (r.get("body") or "")[:50] or r["identifier"])
            for r in extras.get("all_rules", [])
        }

        outer.addWidget(separator())
        outer.addLayout(
            self._bindings_section(
                identifier,
                "Bound skills",
                bindings.get("skills") or [],
                skill_labels,
                _SKILL_EDGE,
                add_handler=self._add_skill,
            )
        )

        outer.addWidget(separator())
        outer.addLayout(
            self._bindings_section(
                identifier,
                "Bound governance rules",
                bindings.get("governance_rules") or [],
                rule_labels,
                _RULE_EDGE,
                add_handler=self._add_rule,
            )
        )

        outer.addWidget(separator())
        outer.addWidget(self._contract_section(identifier, extras))

        outer.addWidget(separator())
        outer.addWidget(created_updated_section(record, "created_at", "updated_at"))
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _bindings_section(
        self,
        profile_id: str,
        title: str,
        bound: list[dict[str, Any]],
        labels: dict[str, str],
        relationship: str,
        *,
        add_handler,
    ) -> QVBoxLayout:
        box = QVBoxLayout()
        header = QHBoxLayout()
        header.addWidget(field_label(f"{title} ({len(bound)})"))
        header.addStretch(1)
        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(lambda _c=False: add_handler(profile_id))
        header.addWidget(add_btn)
        box.addLayout(header)

        if not bound:
            box.addWidget(field_label("(none bound)", dim=True))
        for entry in bound:
            target = entry.get("identifier")
            row = QHBoxLayout()
            row.addWidget(field_label(f"{target} — {labels.get(target, target)}"))
            row.addStretch(1)
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(
                lambda _c=False, t=target, rel=relationship, pid=profile_id: self._remove_binding(
                    pid, t, rel
                )
            )
            row.addWidget(remove_btn)
            box.addLayout(row)
        return box

    def _contract_section(self, profile_id: str, extras: dict[str, Any]) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        header.addWidget(field_label("Effective contract (resolved)"))
        header.addStretch(1)
        header.addWidget(QLabel("Engagement:"))
        combo = QComboBox()
        combo.addItem("System defaults only", _SYSTEM_ONLY)
        for eng in extras.get("engagements", []):
            combo.addItem(eng, eng)
        active = self._client.active_engagement()
        if active:
            idx = combo.findData(active)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(self._on_contract_engagement_changed)
        header.addWidget(combo)
        layout.addLayout(header)

        view = read_only_text(self._format_contract(extras.get("contract") or {}))
        view.setMinimumHeight(220)
        layout.addWidget(view)

        # Stash live references so the combo can re-resolve in place.
        self._contract_profile_id = profile_id
        self._contract_combo = combo
        self._contract_view = view
        return wrapper

    def _on_contract_engagement_changed(self, _index: int) -> None:
        if self._contract_combo is None or self._contract_view is None:
            return
        profile_id = self._contract_profile_id or ""
        engagement = self._contract_combo.currentData()
        contract = self._resolve_contract(profile_id, engagement)
        # ``_contract_view`` is the QPlainTextEdit from ``read_only_text``.
        self._contract_view.setPlainText(self._format_contract(contract))

    def _resolve_contract(self, profile_id: str, engagement: str | None) -> dict[str, Any]:
        try:
            return self._client.get_agent_profile_contract(
                profile_id, engagement=engagement
            )
        except (StorageClientError, StorageConnectionError) as exc:
            _log.warning("Could not resolve contract for %s: %s", profile_id, exc)
            return {"_error": str(exc)}

    @staticmethod
    def _format_contract(contract: dict[str, Any]) -> str:
        if "_error" in contract:
            return f"(could not resolve contract: {contract['_error']})"
        if not contract:
            return "(no contract)"
        lines = [
            f"version_stamp: {contract.get('version_stamp')}",
            f"scope: {contract.get('scope')}    engagement_id: {contract.get('engagement_id')}",
        ]
        for title, key in (
            ("TOOLS", "tools"),
            ("ADVISORY RULES", "advisory_rules"),
            ("ENFORCED RULESET", "enforced_ruleset"),
            ("ACTIVE LEARNINGS", "active_learnings"),
        ):
            items = contract.get(key) or []
            lines.append(f"\n{title} ({len(items)}):")
            for item in items:
                lines.append(f"  - {_summarize_item(item)}")
        lines.append("\nSYSTEM PROMPT:\n" + (contract.get("system_prompt") or ""))
        return "\n".join(lines)

    # --- binding actions ------------------------------------------------

    def _add_skill(self, profile_id: str) -> None:
        skills = self._call(self._client.list_skills) or []
        bound = self._bound_ids(profile_id, "skills")
        candidates = [
            (s["identifier"], s.get("name") or s["identifier"])
            for s in skills
            if s["identifier"] not in bound and s.get("status") != "retired"
        ]
        self._pick_and_bind(
            "Bind a skill", candidates, lambda sid: self._client.add_agent_profile_skill(profile_id, sid), profile_id
        )

    def _add_rule(self, profile_id: str) -> None:
        rules = self._call(self._client.list_governance_rules) or []
        bound = self._bound_ids(profile_id, "governance_rules")
        candidates = [
            (r["identifier"], r.get("rule_type") or (r.get("body") or "")[:50] or r["identifier"])
            for r in rules
            if r["identifier"] not in bound and r.get("status") != "retired"
        ]
        self._pick_and_bind(
            "Bind a governance rule", candidates, lambda rid: self._client.add_agent_profile_rule(profile_id, rid), profile_id
        )

    def _bound_ids(self, profile_id: str, key: str) -> set[str]:
        bindings = self._call(lambda: self._client.get_agent_profile_bindings(profile_id)) or {}
        return {e["identifier"] for e in (bindings.get(key) or [])}

    def _pick_and_bind(self, title, candidates, bind_fn, profile_id) -> None:
        dialog = BindingPickerDialog(title, candidates, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target = dialog.selected_identifier()
        if not target:
            return
        if self._call(lambda: bind_fn(target)):
            self._reload_detail(profile_id)

    def _remove_binding(self, profile_id: str, target_id: str, relationship: str) -> None:
        if self._call(
            lambda: self._client.remove_agent_profile_binding(profile_id, target_id, relationship)
        ):
            self._reload_detail(profile_id)

    # --- helpers --------------------------------------------------------

    def _edit_capability(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        dialog = JsonFieldDialog(
            self._client.patch_agent_profile,
            identifier,
            "capability_description",
            "Capability description",
            record.get("capability_description"),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_detail(identifier)

    def _reload_detail(self, identifier: str) -> None:
        """Re-render the detail pane for ``identifier`` with fresh data."""
        try:
            fresh = self._client.get_agent_profile(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError:
            self.refresh()
            return
        self._begin_detail_load(fresh)

    def _call(self, fn):
        """Run an API call, routing errors; return the result or None on error."""
        try:
            return fn()
        except StorageConnectionError as exc:
            self.connection_lost.emit(str(exc))
            return None
        except StorageClientError as exc:
            ErrorDialog(
                title="Action failed",
                message="The registry action could not be completed.",
                detail=str(exc),
                parent=self,
            ).exec()
            return None
