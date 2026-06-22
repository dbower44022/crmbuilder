"""Cost panel — read-only AI-spend visibility (PI-265 / PRJ-041, REQ-307).

The surfacing for the cost telemetry the spend surfaces record (PI-263 / PI-264). A
master/detail browse over the ``/cost`` aggregations: the master list is the per-release
spend (highest first) plus a synthetic **(all)** row for the whole engagement; selecting
a row shows that scope's total, its breakdown by area and by stage, and its most recent
events. Read-only — cost is recorded automatically by the scheduler/fleet, never here.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
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
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp

# Sentinel identifier for the synthetic engagement-wide total row.
_ALL = "(all)"
_UNATTRIBUTED = "(unattributed)"
_DIM_STYLE = "color: #888;"


def _money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.4f}"
    except (TypeError, ValueError):
        return "$0.0000"


class CostPanel(ListDetailPanel):
    """Read-only AI-spend monitor: per-release spend + per-scope breakdowns (PI-265)."""

    def entity_title(self) -> str:
        return "Cost"

    def fetch_records(self) -> list[dict[str, Any]]:
        # The per-release breakdown is the master list; a synthetic (all) row carries
        # the engagement-wide total so the top row is the whole-engagement dashboard.
        summary = self._client.cost_summary()
        by_release = self._client.cost_by("release")
        total_row = {
            "key": _ALL,
            "cost_usd": summary.get("cost_usd", 0.0),
            "event_count": summary.get("event_count", 0),
        }
        return [total_row, *by_release]

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            key = r.get("key")
            r["identifier"] = _ALL if key == _ALL else (key or _UNATTRIBUTED)
            r["cost_display"] = _money(r.get("cost_usd"))
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Scope"),
            ColumnSpec(field="cost_display", title="Cost", width=120),
            ColumnSpec(field="event_count", title="Events", width=90),
        ]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        # (all) → engagement-wide (no release filter); else filter to that release.
        key = record.get("identifier")
        release = None if key in (_ALL, _UNATTRIBUTED) else key
        filt = {} if release is None else {"release_identifier": release}
        return {
            "summary": self._client.cost_summary(**filt),
            "by_area": self._client.cost_by("area", **filt),
            "by_stage": self._client.cost_by("stage", **filt),
            "events": self._client.cost_events(limit=25, **filt),
        }

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scope = record.get("identifier") or _ALL
        summary = extras.get("summary") or {}
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        title = "All spend (this engagement)" if scope == _ALL else f"Release {scope}"
        outer.addWidget(heading_label(title))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Total cost", read_only_line(_money(summary.get("cost_usd"))))
        form.addRow("Events", read_only_line(str(summary.get("event_count", 0))))
        form.addRow(
            "Tokens (in / out)",
            read_only_line(
                f"{summary.get('input_tokens', 0):,} / {summary.get('output_tokens', 0):,}"
            ),
        )
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(self._breakdown("By area", extras.get("by_area") or []))
        outer.addWidget(self._breakdown("By stage", extras.get("by_stage") or []))

        outer.addWidget(separator())
        outer.addWidget(self._recent(extras.get("events") or []))

        outer.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def _breakdown(self, title: str, rows: list[dict[str, Any]]) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        head = QLabel(title)
        head.setStyleSheet("font-weight: bold;")
        layout.addWidget(head)
        if not rows:
            empty = QLabel("none")
            empty.setStyleSheet(_DIM_STYLE)
            layout.addWidget(empty)
            return box
        for r in rows:
            key = r.get("key") or _UNATTRIBUTED
            line = QLabel(f"{key}: {_money(r.get('cost_usd'))} ({r.get('event_count', 0)})")
            layout.addWidget(line)
        return box

    def _recent(self, events: list[dict[str, Any]]) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        head = QLabel("Recent events")
        head.setStyleSheet("font-weight: bold;")
        layout.addWidget(head)
        if not events:
            empty = QLabel("none")
            empty.setStyleSheet(_DIM_STYLE)
            layout.addWidget(empty)
            return box
        for e in events:
            when = format_timestamp(e.get("cost_created_at"))
            parts = [
                when,
                e.get("cost_source") or "",
                e.get("cost_model") or "",
                e.get("area") or "",
                e.get("stage") or "",
                _money(e.get("cost_usd")),
            ]
            layout.addWidget(QLabel(" · ".join(p for p in parts if p)))
        return box
