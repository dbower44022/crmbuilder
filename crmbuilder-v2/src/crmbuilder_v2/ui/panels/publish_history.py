"""Publish History panel — PI-266 (PRJ-042 / REQ-293).

Read-only master/detail over the ``/publish-runs`` API: the history of
publishes to a target instance recorded by the publish path (PI-262). Each
``publish_run`` (``PUB-NNN``) carries the run's scope, terminal status, timing,
the pre-publish target backup (REQ-292), and an outcome summary (deploy counts
+ post-publish verification). Runs are written only by the publish service, so
this panel exposes no Create/Edit/Delete — it is monitoring-only.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QModelIndex
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
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp

_STATUS_BADGE = {
    "succeeded": "✓ succeeded",
    "succeeded_with_issues": "⚠ succeeded (issues)",
    "failed": "✗ failed",
    "aborted": "⛔ aborted",
}


def _scope_display(scope: list | None) -> str:
    if not scope:
        return "whole design"
    return f"{len(scope)} program(s)"


def _verification_line(summary: dict | None) -> str:
    """A one-line read of the recorded post-publish verification."""
    verify = (summary or {}).get("verification")
    if not verify:
        return "—"
    if not verify.get("ran"):
        return "not run"
    if not verify.get("conclusive"):
        return "inconclusive"
    if verify.get("all_present"):
        ents = verify.get("entities") or []
        return f"all {len(ents)} object(s) present"
    return "gaps found"


class PublishHistoryPanel(ListDetailPanel):
    """Read-only browse panel for the publish history (PI-266)."""

    def entity_title(self) -> str:
        return "Publish History"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_publish_runs()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="publish_run_identifier", title="Identifier", width=100),
            ColumnSpec(field="instance_identifier", title="Target", width=100),
            ColumnSpec(field="status_display", title="Status", width=170),
            ColumnSpec(field="scope_display", title="Scope", width=130),
            ColumnSpec(field="ended_display", title="Finished", width=150),
        ]

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            status = r.get("publish_run_status") or ""
            r["status_display"] = _STATUS_BADGE.get(status, status)
            r["scope_display"] = _scope_display(r.get("publish_run_scope"))
            r["ended_display"] = format_timestamp(
                r.get("publish_run_ended_at")
            )
        return records

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("publish_run_identifier") or ""
        status = record.get("publish_run_status") or ""
        summary = record.get("publish_run_summary") or {}

        outer.addWidget(heading_label(identifier))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Target instance", read_only_line(
            record.get("instance_identifier") or ""
        ))
        form.addRow("Status", read_only_line(
            _STATUS_BADGE.get(status, status)
        ))
        form.addRow("Scope", read_only_line(
            _scope_display(record.get("publish_run_scope"))
        ))
        form.addRow("Started", read_only_line(
            format_timestamp(record.get("publish_run_started_at")) or "—"
        ))
        form.addRow("Finished", read_only_line(
            format_timestamp(record.get("publish_run_ended_at")) or "—"
        ))
        form.addRow("Verification", read_only_line(
            _verification_line(summary)
        ))
        outer.addLayout(form)

        # Scope detail (the selected program filenames, if a subset publish).
        scope = record.get("publish_run_scope")
        if scope:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Published programs</b>"))
            outer.addWidget(read_only_text("\n".join(scope)))

        # Outcome summary (deploy counts + verification), as recorded.
        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Outcome summary</b>"))
        outer.addWidget(read_only_text(_pretty(summary)))

        # Pre-publish backup snapshot (REQ-292) — the recoverable target state.
        outer.addWidget(separator())
        backup = record.get("publish_run_backup")
        if backup:
            entities = (backup.get("entities") or {}) if isinstance(
                backup, dict
            ) else {}
            outer.addWidget(QLabel(
                f"<b>Pre-publish backup</b> — {len(entities)} entity(ies) "
                f"captured before this publish"
            ))
            outer.addWidget(read_only_text(_pretty(backup)))
        else:
            label = QLabel("No backup was captured for this publish.")
            label.setStyleSheet("color: #888;")
            outer.addWidget(label)

        outer.addWidget(separator())
        outer.addWidget(
            created_updated_section(record, "created_at", "updated_at")
        )

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Identifier-field override (publish_run_identifier, not "identifier")
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("publish_run_identifier") == identifier:
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
            lambda _c=False, r=record: self._copy(
                r.get("publish_run_identifier") or ""
            )
        )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)


def _pretty(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)
