"""Decisions panel — smoke-grade implementation.

Slice C exercises the entire data-layer stack end-to-end with a
minimum-viable Decisions panel: three columns in the master list and a
read-only JSON dump in the detail pane. Slice D replaces this with the
full PRD §4.6 column set and a formatted detail view; slice G adds
create/edit/delete dialogs.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import QPlainTextEdit, QWidget

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel


class DecisionsPanel(ListDetailPanel):
    def entity_title(self) -> str:
        return "Decisions"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_decisions()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=120),
            ColumnSpec(field="title", title="Title"),
            ColumnSpec(field="status", title="Status", width=100),
        ]

    def render_detail(self, record: dict[str, Any]) -> QWidget:
        widget = QPlainTextEdit()
        widget.setReadOnly(True)
        widget.setPlainText(json.dumps(record, indent=2, default=str))
        return widget
