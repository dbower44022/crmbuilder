"""Skills panel — the registry ``skill`` entity (PI-330 / REQ-367).

A ``ListDetailPanel`` with full create/edit/delete for skills, plus an
"Edit I/O contract…" action that edits the JSON ``io_contract`` column. Skills
are system/shared with a nullable engagement scope (shown in the Scope column).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
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
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

# Secondary (warm-orange) button chrome — gray reads as disabled.
_SECONDARY_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; border-radius: 4px; "
    "padding: 6px 14px; } QPushButton:hover { background-color: #FB8C00; }"
)


class SkillsPanel(RegistryCrudPanel):
    new_button_label = "New Skill"
    entity_noun = "skill"

    def __init__(self, client: Any, parent: QWidget | None = None) -> None:
        super().__init__(client, parent)
        # Scan the local skill roots and import any SKILL.md definitions as
        # registry skills (REQ-421 / PI-362). Sits beside "New Skill".
        self._scan_button = QPushButton("Scan local skills…")
        self._scan_button.setObjectName("scan_local_skills_button")
        self._scan_button.setStyleSheet(_SECONDARY_STYLE)
        self._scan_button.clicked.connect(self._on_scan_clicked)
        self._action_layout.addWidget(self._scan_button)

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

    def _on_scan_clicked(self) -> None:
        """Run the local-skill scan and report a found/imported/skipped summary."""
        self.setCursor(Qt.CursorShape.BusyCursor)
        try:
            result = self._client.scan_skills()
        except Exception as exc:  # noqa: BLE001 — surface any failure to the operator
            self.unsetCursor()
            CopyableMessageBox.warning(
                self, "Scan local skills", f"The scan could not run: {exc}"
            )
            return
        self.unsetCursor()
        self._report_scan(result)
        self.refresh()

    def _report_scan(self, result: dict[str, Any]) -> None:
        counts = result.get("counts", {})
        imported = result.get("imported", [])
        errors = result.get("errors", [])
        lines = [
            f"Found {counts.get('found', 0)} local skill file(s).",
            f"Imported {counts.get('imported', 0)} new skill(s).",
        ]
        if imported:
            lines.append(
                "  • "
                + "\n  • ".join(
                    f"{i.get('name')} ({i.get('identifier')})" for i in imported
                )
            )
        lines.append(
            f"Skipped {counts.get('skipped', 0)} already in the registry."
        )
        if errors:
            lines.append(
                f"{counts.get('errors', 0)} could not be imported:\n  • "
                + "\n  • ".join(
                    f"{e.get('path')}: {e.get('error')}" for e in errors
                )
            )
        roots = result.get("roots", [])
        if roots:
            lines.append("\nSearched: " + ", ".join(roots))
        CopyableMessageBox.information(
            self, "Scan local skills", "\n".join(lines)
        )
