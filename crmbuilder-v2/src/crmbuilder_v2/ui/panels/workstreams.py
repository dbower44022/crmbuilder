"""Workstreams panel — ADO delivery-phase monitoring surface (WTK-004).

Read-only master/detail over the ``/workstreams`` API. A ``workstream``
here is the PI-112 / DEC-343 delivery phase: a single phase (Architecture,
Development, …) of one Planning Item, identified ``WSK-``. The v2 desktop
UI is monitoring-only — creation and the lifecycle transitions go through
the API/agents — so this panel exposes no Create/Edit/Delete affordance.

The ``needs_attention`` human-escape flag (DEC-359) is the trust-critical
signal: it is surfaced both as a synthetic master-pane column and, when set,
as a prominent banner at the top of the detail pane carrying its reason. The
detail pane also resolves the parent Planning Item (via the
``workstream_belongs_to_planning_item`` edge) and renders the Work Tasks that
belong to the workstream (the inbound ``work_task_belongs_to_workstream``
edges) as an inline grid (PI-120 / WTK-076) — one row per child showing its
identifier, title, area, status, and claim state — reusing the References
grid via :class:`WorkTaskGridSection`.
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
from crmbuilder_v2.ui.widgets.references_section import (
    ReferencesSection,
    WorkTaskGridSection,
)

_log = logging.getLogger("crmbuilder_v2.ui.panels.workstreams")

_ATTENTION_YES = "⚠ Yes"
_ATTENTION_NO = "—"

# Attention banner styling — accent-red so the human-escape flag reads at a
# glance in an otherwise neutral detail pane.
_ATTENTION_BANNER_STYLE = (
    "color: #842029; background: #f8d7da; border: 1px solid #f5c2c7;"
    " border-radius: 4px; padding: 6px 8px;"
)

_LIFECYCLE_TIMESTAMPS = [
    ("Started", "workstream_started_at"),
    ("Completed", "workstream_completed_at"),
]


class WorkstreamsPanel(ListDetailPanel):
    """Read-only browse panel for Workstreams (WTK-004)."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        # No New button — Workstreams are created by the decomposer / agents.

    def entity_title(self) -> str:
        return "Workstreams"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_workstreams()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="workstream_identifier", title="Identifier", width=110),
            ColumnSpec(field="workstream_phase_type", title="Phase", width=120),
            ColumnSpec(field="workstream_title", title="Title"),
            ColumnSpec(field="workstream_status", title="Status", width=110),
            ColumnSpec(field="needs_attention_display", title="Attention", width=90),
            ColumnSpec(field="updated_at_display", title="Updated", width=140),
        ]

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            r["needs_attention_display"] = (
                _ATTENTION_YES if r.get("workstream_needs_attention") else _ATTENTION_NO
            )
            r["updated_at_display"] = format_timestamp(
                r.get("workstream_updated_at")
            )
        return records

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("workstream_deleted_at") is not None

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("workstream_identifier")
        if not identifier:
            return {
                "references": {"as_source": [], "as_target": []},
                "child_work_tasks": [],
            }
        references = self._client.list_references_touching("workstream", identifier)
        return {
            "references": references,
            "child_work_tasks": self._load_child_work_tasks(references),
        }

    def _load_child_work_tasks(
        self, references: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Join the membership edges with the child Work Task records.

        The child set is the inbound ``work_task_belongs_to_workstream`` edges
        (the membership source of truth); the records supply the two fields the
        edge summary omits — ``work_task_area`` and claim state (PI-120 §3.3).
        Runs on the ``fetch_detail_extras`` worker thread. Degrades gracefully:
        a child whose record can't be loaded keeps its identifier and renders
        the missing fields as the dash sentinel.
        """
        child_ids = sorted(
            edge.get("source_id") or ""
            for edge in (references.get("as_target") or [])
            if edge.get("relationship") == "work_task_belongs_to_workstream"
        )
        child_ids = [cid for cid in child_ids if cid]
        if not child_ids:
            return []
        tasks_by_id: dict[str, dict[str, Any]] = {}
        try:
            tasks_by_id = {
                t.get("work_task_identifier"): t
                for t in self._client.list_work_tasks()
            }
        except Exception:  # noqa: BLE001 — degrade to edge-only rows
            _log.warning(
                "Could not load Work Task records for child grid", exc_info=True
            )
        return [
            tasks_by_id.get(cid, {"work_task_identifier": cid}) for cid in child_ids
        ]

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("workstream_identifier") or ""
        references = extras.get("references") or {}

        outer.addWidget(heading_label(record.get("workstream_title") or identifier))

        # needs_attention banner (DEC-359) — the trust-critical human-escape
        # flag, surfaced prominently with its reason when set.
        if record.get("workstream_needs_attention"):
            reason = record.get("workstream_needs_attention_reason") or "(no reason given)"
            banner = QLabel(f"⚠ Needs attention — {reason}")
            banner.setObjectName("workstream_needs_attention_banner")
            banner.setWordWrap(True)
            banner.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            banner.setStyleSheet(_ATTENTION_BANNER_STYLE)
            outer.addWidget(banner)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Identifier", read_only_line(identifier))
        form.addRow("Phase", read_only_line(record.get("workstream_phase_type") or ""))
        form.addRow("Status", read_only_line(record.get("workstream_status") or ""))
        form.addRow(
            "Needs attention",
            read_only_line(
                "Yes" if record.get("workstream_needs_attention") else "No"
            ),
        )
        outer.addLayout(form)

        # Parent Planning Item (workstream_belongs_to_planning_item edge).
        parent_pi = self._parent_planning_item(references)
        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Planning Item</b>"))
        outer.addWidget(self._link_or_dim("planning_item", parent_pi, "No parent recorded"))

        # Work Tasks belonging to this workstream (inbound
        # work_task_belongs_to_workstream edges).
        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Work Tasks</b>"))
        outer.addWidget(self._work_tasks_section(extras))

        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Description</b>"))
        outer.addWidget(read_only_text(record.get("workstream_description") or ""))

        notes = record.get("workstream_notes")
        if notes:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Internal notes</b>"))
            outer.addWidget(read_only_text(notes))

        outer.addWidget(separator())
        outer.addWidget(
            created_updated_section(
                record, "workstream_created_at", "workstream_updated_at"
            )
        )

        ts_section = lifecycle_timestamps_section(record, _LIFECYCLE_TIMESTAMPS)
        if ts_section is not None:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Lifecycle timestamps</b>"))
            outer.addWidget(ts_section)

        outer.addWidget(separator())
        refs = ReferencesSection(
            "workstream", identifier, references, client=self._client
        )
        # Read-only: edges are authored by the decomposer / agents.
        if hasattr(refs, "set_add_enabled"):
            refs.set_add_enabled(False)
        refs.navigate_requested.connect(self.navigate_requested)
        outer.addWidget(refs)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Related-entity helpers
    # ------------------------------------------------------------------

    def _parent_planning_item(self, references: dict[str, Any]) -> str:
        """Identifier of the parent PI, or "" if no membership edge present."""
        for edge in references.get("as_source") or []:
            if edge.get("relationship") == "workstream_belongs_to_planning_item":
                return edge.get("target_id") or ""
        return ""

    def _work_tasks_section(self, extras: dict[str, Any]) -> QWidget:
        """Render the child Work Tasks as an inline grid (PI-120 / WTK-076).

        One row per child Work Task — identifier, title, area, status, claim
        state — reusing the References grid via :class:`WorkTaskGridSection`.
        The empty case preserves the prior dim ``"No Work Tasks recorded."``
        label rather than building an empty grid.
        """
        rows = [
            self._work_task_row(rec)
            for rec in (extras.get("child_work_tasks") or [])
        ]
        rows = [r for r in rows if r["identifier"]]
        if not rows:
            empty = QLabel("No Work Tasks recorded.")
            empty.setStyleSheet("color: #888;")
            return empty
        identifier = ""
        grid = WorkTaskGridSection(
            "workstream", identifier, rows, client=self._client
        )
        grid.set_add_enabled(False)
        grid.navigate_requested.connect(self.navigate_requested)
        return grid

    @staticmethod
    def _work_task_row(record: dict[str, Any]) -> dict[str, Any]:
        """Build one Work Task grid row from a (possibly partial) record.

        Carries the five display fields plus the ``other_type``/``other_id``
        bookkeeping the grid's generic nav/preview paths expect. Claim state is
        a single derived string — ``"Claimed · {who}"`` / ``"Unclaimed"`` — when
        the record was loaded; a degraded (edge-only) record leaves area and
        claim state ``None`` so the grid renders them as the dash sentinel.
        """
        ident = record.get("work_task_identifier") or ""
        row: dict[str, Any] = {
            "identifier": ident,
            "title": record.get("work_task_title"),
            "area": record.get("work_task_area"),
            "status": record.get("work_task_status"),
            "claim_state": None,
            "other_type": "work_task",
            "other_id": ident,
        }
        if "work_task_claimed_by" in record:
            who = record.get("work_task_claimed_by")
            row["claim_state"] = f"Claimed · {who}" if who else "Unclaimed"
        return row

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
    # Identifier-field overrides (workstream_identifier, not "identifier")
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("workstream_identifier") == identifier:
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
            lambda _c=False, r=record: self._copy(r.get("workstream_identifier") or "")
        )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
