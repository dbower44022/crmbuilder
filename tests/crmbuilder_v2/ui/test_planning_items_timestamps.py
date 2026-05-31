"""PI-107: planning_item created/updated timestamps surfaced in the panel."""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from PySide6.QtWidgets import QLabel

from .conftest import build_client, envelope_ok

_CREATED = "2026-05-29T23:35:53.169304"
_UPDATED = "2026-05-30T08:15:00.000000"


def _record(identifier: str = "PI-107") -> dict[str, Any]:
    return {
        "identifier": identifier,
        "title": "Surface timestamps",
        "description": "desc",
        "item_type": "pending_work",
        "status": "Draft",
        "resolution_reference": None,
        "executive_summary": "summary",
        "created_at": _CREATED,
        "updated_at": _UPDATED,
    }


def _handler(records: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/planning-items":
            return httpx.Response(200, json=envelope_ok(records))
        if req.method == "GET" and req.url.path.startswith("/references/touching/"):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        return httpx.Response(
            404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]}
        )

    return handler


def test_created_column_present_and_formatted(qtbot):
    client = build_client(_handler([_record()]))
    panel = PlanningItemsPanel(client)
    qtbot.addWidget(panel)

    titles = [c.title for c in panel.list_columns()]
    assert "Created" in titles

    records = panel.fetch_records()
    assert records[0]["created_at_display"] == format_timestamp(_CREATED)
    # The synthetic field must not be the raw ISO string.
    assert records[0]["created_at_display"] != _CREATED


def test_detail_pane_shows_created_and_updated(qtbot):
    client = build_client(_handler([_record()]))
    panel = PlanningItemsPanel(client)
    qtbot.addWidget(panel)

    detail = panel.render_detail(
        _record(), {"references": {"as_source": [], "as_target": []}}
    )
    label_texts = {w.text() for w in detail.findChildren(QLabel)}
    assert "Created" in label_texts
    assert "Last Updated" in label_texts
    assert format_timestamp(_CREATED) in label_texts
    assert format_timestamp(_UPDATED) in label_texts


def test_detail_pane_missing_timestamps_render_em_dash(qtbot):
    client = build_client(_handler([_record()]))
    panel = PlanningItemsPanel(client)
    qtbot.addWidget(panel)

    record = _record()
    record["created_at"] = None
    record["updated_at"] = None
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )
    label_texts = [w.text() for w in detail.findChildren(QLabel)]
    # Both the Created and Last Updated value labels fall back to "—".
    assert label_texts.count("—") >= 2
