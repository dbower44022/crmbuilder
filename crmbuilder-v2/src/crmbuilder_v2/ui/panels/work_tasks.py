"""Work Tasks panel — ADO unit-of-execution monitoring surface (WTK-004).

Read-only master/detail over the ``/work-tasks`` API. A ``work_task`` is the
single-area, agent-claimable unit of execution within a Workstream (WTK-
identifier, PI-112 Phase 4b / DEC-342). The v2 desktop UI is monitoring-only
— claim/release and the lifecycle transitions happen agent-side — so this
panel exposes no Create/Edit/Delete affordance.

The panel surfaces the task's ``area`` (the single System ∪ Engagement area
it operates in) and its claim state (``claimed_by`` / ``claimed_at``) as
first-class fields. The detail pane resolves the parent Workstream (via the
``work_task_belongs_to_workstream`` edge) as a navigable link.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.panels._governance_helpers import (
    created_updated_section,
    heading_label,
    lifecycle_timestamps_section,
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.work_tasks")

_LIFECYCLE_TIMESTAMPS = [
    ("Started", "work_task_started_at"),
    ("Completed", "work_task_completed_at"),
]


class WorkTasksPanel(ListDetailPanel):
    """Read-only browse panel for Work Tasks (WTK-004)."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        # No New button — Work Tasks are created by phase specialists / agents.

    def entity_title(self) -> str:
        return "Work Tasks"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_work_tasks()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="work_task_identifier", title="Identifier", width=110),
            ColumnSpec(field="work_task_title", title="Title"),
            ColumnSpec(field="work_task_area", title="Area", width=110),
            ColumnSpec(field="work_task_status", title="Status", width=110),
            ColumnSpec(field="claimed_by_display", title="Claimed by", width=110),
            ColumnSpec(field="updated_at_display", title="Updated", width=140),
        ]

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            r["claimed_by_display"] = r.get("work_task_claimed_by") or "—"
            r["updated_at_display"] = format_timestamp(
                r.get("work_task_updated_at")
            )
        return records

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("work_task_deleted_at") is not None

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("work_task_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "work_task", identifier
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

        identifier = record.get("work_task_identifier") or ""
        references = extras.get("references") or {}

        outer.addWidget(heading_label(record.get("work_task_title") or identifier))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Identifier", read_only_line(identifier))
        form.addRow("Area", read_only_line(record.get("work_task_area") or ""))
        form.addRow("Status", read_only_line(record.get("work_task_status") or ""))
        form.addRow(
            "Claimed by",
            read_only_line(record.get("work_task_claimed_by") or ""),
        )
        form.addRow(
            "Claimed at",
            read_only_line(format_timestamp(record.get("work_task_claimed_at"))),
        )
        outer.addLayout(form)

        # Parent Workstream (work_task_belongs_to_workstream edge).
        parent_ws = self._parent_workstream(references)
        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Workstream</b>"))
        outer.addWidget(
            self._link_or_dim("workstream", parent_ws, "No parent recorded")
        )

        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Description</b>"))
        outer.addWidget(read_only_text(record.get("work_task_description") or ""))

        notes = record.get("work_task_notes")
        if notes:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Internal notes</b>"))
            outer.addWidget(read_only_text(notes))

        outer.addWidget(separator())
        outer.addWidget(
            created_updated_section(
                record, "work_task_created_at", "work_task_updated_at"
            )
        )

        ts_section = lifecycle_timestamps_section(record, _LIFECYCLE_TIMESTAMPS)
        if ts_section is not None:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Lifecycle timestamps</b>"))
            outer.addWidget(ts_section)

        outer.addWidget(separator())
        refs = ReferencesSection(
            "work_task", identifier, references, client=self._client
        )
        # Read-only: edges are authored by the decomposer / agents.
        if hasattr(refs, "set_add_enabled"):
            refs.set_add_enabled(False)
        self._wire_link_section(refs)
        outer.addWidget(refs)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Related-entity helpers
    # ------------------------------------------------------------------

    def _parent_workstream(self, references: dict[str, Any]) -> str:
        """Identifier of the parent Workstream, or "" if no membership edge."""
        for edge in references.get("as_source") or []:
            if edge.get("relationship") == "work_task_belongs_to_workstream":
                return edge.get("target_id") or ""
        return ""

    def _link_or_dim(self, entity_type: str, identifier: str, empty_text: str) -> QLabel:
        """A navigable link to ``entity_type:identifier``, or dim placeholder."""
        if identifier:
            label = QLabel(f'<a href="{entity_type}:{identifier}">{identifier}</a>')
            label.setTextFormat(Qt.TextFormat.RichText)
            label.linkActivated.connect(self._emit_link_navigation)
        else:
            label = QLabel(empty_text or "—")
            label.setStyleSheet("color: #888;")
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
        return label

    # ------------------------------------------------------------------
    # Identifier-field overrides (work_task_identifier, not "identifier")
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("work_task_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        copy_id = menu.addAction("Copy Identifier")
        copy_id.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("work_task_identifier") or "")
        )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
