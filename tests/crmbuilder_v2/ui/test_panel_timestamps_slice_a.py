"""PI-108 Slice A: created/last-edited timestamps on the raw-ISO panels.

Covers the shared created_updated_section helper plus the Sessions /
Workstreams / Conversations / Commits panels (the ones that previously showed
a raw, unformatted updated_at or nothing).
"""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.panels.conversations import ConversationsPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.workstreams import WorkstreamsPanel
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from PySide6.QtWidgets import QLabel

from .conftest import build_client, envelope_ok

_CREATED = "2026-05-29T23:35:53.169304"
_UPDATED = "2026-05-30T08:15:00.000000"


# --- shared helper ---------------------------------------------------------


def test_created_updated_section_formats_both(qtbot):
    w = created_updated_section(
        {"x_created_at": _CREATED, "x_updated_at": _UPDATED},
        "x_created_at",
        "x_updated_at",
    )
    qtbot.addWidget(w)
    texts = {lbl.text() for lbl in w.findChildren(QLabel)}
    assert "Created" in texts
    assert "Last Updated" in texts
    assert format_timestamp(_CREATED) in texts
    assert format_timestamp(_UPDATED) in texts


def test_created_updated_section_immutable_renders_em_dash(qtbot):
    # updated_field=None → Last Updated is em dash (immutable types).
    w = created_updated_section({"x_created_at": _CREATED}, "x_created_at", None)
    qtbot.addWidget(w)
    texts = [lbl.text() for lbl in w.findChildren(QLabel)]
    assert format_timestamp(_CREATED) in texts
    assert "—" in texts


# --- per-panel synthetic column + formatting -------------------------------


def _list_handler(path: str, records: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == path:
            return httpx.Response(200, json=envelope_ok(records))
        return httpx.Response(200, json=envelope_ok([]))

    return handler


def _rec(prefix: str, ident_field: str) -> dict[str, Any]:
    return {
        ident_field: f"{prefix}-001",
        f"{prefix.lower()}_created_at": _CREATED,
        f"{prefix.lower()}_updated_at": _UPDATED,
    }


def test_sessions_created_column_formatted(qtbot):
    rec = {
        "session_identifier": "SES-001",
        "session_created_at": _CREATED,
        "session_updated_at": _UPDATED,
    }
    panel = SessionsPanel(build_client(_list_handler("/sessions", [rec])))
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert "Created" in titles and "Updated" in titles
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["updated_at_display"] == format_timestamp(_UPDATED)
    assert out[0]["created_at_display"] != _CREATED


def test_workstreams_created_column_formatted(qtbot):
    rec = {
        "workstream_identifier": "WS-001",
        "workstream_created_at": _CREATED,
        "workstream_updated_at": _UPDATED,
    }
    panel = WorkstreamsPanel(build_client(_list_handler("/workstreams", [rec])))
    qtbot.addWidget(panel)
    assert "Created" in [c.title for c in panel.list_columns()]
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)


def test_conversations_created_column_formatted(qtbot):
    rec = {
        "conversation_identifier": "CNV-001",
        "conversation_created_at": _CREATED,
        "conversation_updated_at": _UPDATED,
    }
    panel = ConversationsPanel(build_client(_list_handler("/conversations", [rec])))
    qtbot.addWidget(panel)
    assert "Created" in [c.title for c in panel.list_columns()]
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["created_at_display"] != _CREATED
