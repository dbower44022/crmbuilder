"""PI-265: Cost panel — read-only AI-spend monitor (per-release + per-scope breakdowns)."""

from __future__ import annotations

import httpx
from crmbuilder_v2.ui.panels.cost import CostPanel

from .conftest import build_client, envelope_ok

_SUMMARY = {"cost_usd": 21.0, "event_count": 3, "input_tokens": 3_000_000,
            "output_tokens": 0, "cache_write_tokens": 0, "cache_read_tokens": 0}
_BY_RELEASE = [
    {"key": "REL-1", "cost_usd": 18.0, "event_count": 2},
    {"key": "REL-2", "cost_usd": 3.0, "event_count": 1},
]
_BY_AREA = [
    {"key": "storage", "cost_usd": 15.0, "event_count": 1},
    {"key": "api", "cost_usd": 6.0, "event_count": 2},
]
_BY_STAGE = [{"key": "develop", "cost_usd": 15.0, "event_count": 1}]
_EVENTS = [
    {"cost_created_at": "2026-06-22T10:00:00", "cost_source": "claude_cli",
     "cost_model": "claude-opus-4-8", "area": "storage", "stage": "develop",
     "cost_usd": 15.0, "release_identifier": "REL-1"},
]


def _handler():
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/cost/summary":
            return httpx.Response(200, json=envelope_ok(_SUMMARY))
        if path == "/cost/by/release":
            return httpx.Response(200, json=envelope_ok(_BY_RELEASE))
        if path == "/cost/by/area":
            return httpx.Response(200, json=envelope_ok(_BY_AREA))
        if path == "/cost/by/stage":
            return httpx.Response(200, json=envelope_ok(_BY_STAGE))
        if path == "/cost/events":
            return httpx.Response(200, json=envelope_ok(_EVENTS))
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})

    return handler


def test_columns(qtbot):
    panel = CostPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    assert [c.title for c in panel.list_columns()] == ["Scope", "Cost", "Events"]


def test_fetch_records_prepends_engagement_total(qtbot):
    panel = CostPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    rows = panel._post_process_records(panel.fetch_records())
    # The synthetic engagement-wide total leads, then each release.
    assert rows[0]["identifier"] == "(all)"
    assert rows[0]["cost_usd"] == 21.0
    assert rows[0]["cost_display"] == "$21.0000"
    assert [r["identifier"] for r in rows[1:]] == ["REL-1", "REL-2"]


def test_unattributed_release_key_renders(qtbot):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/cost/summary":
            return httpx.Response(200, json=envelope_ok(_SUMMARY))
        if req.url.path == "/cost/by/release":
            return httpx.Response(200, json=envelope_ok([{"key": None, "cost_usd": 2.0,
                                                          "event_count": 1}]))
        return httpx.Response(200, json=envelope_ok([]))

    panel = CostPanel(build_client(handler))
    qtbot.addWidget(panel)
    rows = panel._post_process_records(panel.fetch_records())
    assert rows[1]["identifier"] == "(unattributed)"


def test_detail_extras_filter_by_release(qtbot):
    captured: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(str(req.url))
        path = req.url.path
        if path == "/cost/summary":
            return httpx.Response(200, json=envelope_ok(_SUMMARY))
        if path.startswith("/cost/by/"):
            return httpx.Response(200, json=envelope_ok(_BY_AREA))
        if path == "/cost/events":
            return httpx.Response(200, json=envelope_ok(_EVENTS))
        return httpx.Response(200, json=envelope_ok([]))

    panel = CostPanel(build_client(handler))
    qtbot.addWidget(panel)
    extras = panel.fetch_detail_extras({"identifier": "REL-1"})
    assert "summary" in extras and "by_area" in extras and "events" in extras
    # the release filter is threaded into the scope queries.
    assert any("release_identifier=REL-1" in u for u in captured)


def test_render_detail_builds_for_all_and_release(qtbot):
    panel = CostPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    for ident in ("(all)", "REL-1"):
        rec = {"identifier": ident, "cost_usd": 21.0, "event_count": 3}
        extras = panel.fetch_detail_extras(rec)
        widget = panel.render_detail(rec, extras)
        assert widget is not None
