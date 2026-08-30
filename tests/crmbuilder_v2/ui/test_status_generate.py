"""PI-433 / REQ-527: StatusPanel Generate Version flow."""

from __future__ import annotations

import json
from typing import Any

import httpx
from crmbuilder_v2.ui.dialogs.status_generate import StatusGenerateDialog
from crmbuilder_v2.ui.panels.status import StatusPanel
from PySide6.QtWidgets import QPlainTextEdit, QPushButton

from .conftest import build_client, envelope_ok


def _preview(narrative: str | None = None) -> dict[str, Any]:
    return {
        "title": "Test status",
        "phase": "No project in flight",
        "version_label": "0.7.0",
        "metadata": {},
        "active_work": narrative or "",
        "generated": {"in_flight_projects": []},
    }


def _handler(calls: list[tuple[str, str, Any]]):
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        calls.append((req.method, req.url.path, body))
        if req.method == "GET" and req.url.path == "/status/versions":
            return httpx.Response(200, json=envelope_ok([]))
        if req.method == "GET" and req.url.path == "/status/preview":
            return httpx.Response(
                200, json=envelope_ok(_preview(req.url.params.get("narrative")))
            )
        if req.method == "POST" and req.url.path == "/status/generate":
            return httpx.Response(
                200,
                json=envelope_ok(
                    {"version": 1, "is_current": True, "payload": _preview(body.get("narrative"))}
                ),
            )
        if req.url.path.startswith("/references/touching/"):
            return httpx.Response(200, json=envelope_ok({"as_source": [], "as_target": []}))
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": []})

    return handler


def test_toolbar_has_generate_button(qtbot):
    client = build_client(_handler([]))
    panel = StatusPanel(client)
    qtbot.addWidget(panel)
    btn = panel.findChild(QPushButton, "generate_status_version_button")
    assert btn is not None
    assert btn.text() == "Generate Version"


def test_dialog_previews_then_generates_with_narrative(qtbot):
    calls: list[tuple[str, str, Any]] = []
    client = build_client(_handler(calls))
    dialog = StatusGenerateDialog(client)
    qtbot.addWidget(dialog)
    preview = dialog.findChild(QPlainTextEdit, "payload_preview")
    qtbot.waitUntil(lambda: "generated" in preview.toPlainText(), timeout=3000)

    dialog.findChild(QPlainTextEdit, "narrative_editor").setPlainText("shipped X")
    dialog.findChild(QPushButton, "save_button").click()
    qtbot.waitUntil(
        lambda: any(m == "POST" and p == "/status/generate" for m, p, _ in calls),
        timeout=3000,
    )
    post = next(b for m, p, b in calls if m == "POST" and p == "/status/generate")
    assert post == {"narrative": "shipped X"}
