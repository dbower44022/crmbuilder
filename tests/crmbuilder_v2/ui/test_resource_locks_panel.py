"""PI-225: Resource Locks panel — held-lock monitor + reclaim/release actions."""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.resource_locks import ResourceLocksPanel
from PySide6.QtWidgets import QLineEdit, QPushButton

from .conftest import build_client, envelope_ok


def _lock(resource: str, holder: str) -> dict[str, Any]:
    return {
        "id": abs(hash(resource)) % 10000,
        "resource_name": resource,
        "holder": holder,
        "acquired_at": "2026-06-18T09:30:00",
        "released_at": None,
    }


_LOCKS = [
    _lock("crmbuilder-v2/migrations", "ado-wtk-200"),
    _lock("migration-chain", "ado-wtk-200"),
    _lock("crmbuilder-v2/src/crmbuilder_v2/access/locks.py", "ado-wtk-201"),
]


def _handler(locks=_LOCKS, *, captured: list | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        method = req.method
        if captured is not None and method == "POST":
            captured.append((path, req.content.decode()))
        if method == "GET" and path == "/locks":
            return httpx.Response(200, json=envelope_ok(locks))
        if method == "POST" and path == "/locks/reclaim":
            return httpx.Response(200, json=envelope_ok(locks))
        if method == "POST" and path == "/locks/release":
            return httpx.Response(200, json=envelope_ok(locks[0]))
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})

    return handler


def test_columns(qtbot):
    panel = ResourceLocksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    assert [c.title for c in panel.list_columns()] == ["Resource", "Holder", "Acquired"]


def test_records_load_and_synthetic_fields(qtbot):
    panel = ResourceLocksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 3, timeout=3000)
    processed = panel._post_process_records([dict(r) for r in _LOCKS])
    # Synthetic identifier mirrors the resource name (drives base selection).
    assert processed[0]["identifier"] == "crmbuilder-v2/migrations"
    # Acquired column is formatted, not the raw ISO string.
    assert processed[0]["acquired_at_display"] != _LOCKS[0]["acquired_at"]


def test_detail_shows_fields_and_actions(qtbot):
    panel = ResourceLocksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_LOCKS[0], {})
    qtbot.addWidget(detail)
    line_edits = [w.text() for w in detail.findChildren(QLineEdit)]
    assert "crmbuilder-v2/migrations" in line_edits
    assert "ado-wtk-200" in line_edits
    assert detail.findChild(QPushButton, "lock_reclaim_button") is not None
    assert detail.findChild(QPushButton, "lock_release_button") is not None


def test_reclaim_confirmed_issues_post(qtbot, monkeypatch):
    captured: list = []
    panel = ResourceLocksPanel(build_client(_handler(captured=captured)))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_LOCKS[0], {})
    qtbot.addWidget(detail)
    monkeypatch.setattr(panel, "_confirm", lambda *a, **k: True)
    panel._do_reclaim("ado-wtk-200")
    qtbot.waitUntil(lambda: any(c[0] == "/locks/reclaim" for c in captured), timeout=3000)
    assert '"holder":"ado-wtk-200"' in captured[0][1]


def test_reclaim_cancelled_issues_no_post(qtbot, monkeypatch):
    captured: list = []
    panel = ResourceLocksPanel(build_client(_handler(captured=captured)))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_LOCKS[0], {})
    qtbot.addWidget(detail)
    monkeypatch.setattr(panel, "_confirm", lambda *a, **k: False)
    panel._do_reclaim("ado-wtk-200")
    assert captured == []


def test_release_confirmed_issues_post(qtbot, monkeypatch):
    captured: list = []
    panel = ResourceLocksPanel(build_client(_handler(captured=captured)))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_LOCKS[0], {})
    qtbot.addWidget(detail)
    monkeypatch.setattr(panel, "_confirm", lambda *a, **k: True)
    panel._do_release("ado-wtk-200", "crmbuilder-v2/migrations")
    qtbot.waitUntil(lambda: any(c[0] == "/locks/release" for c in captured), timeout=3000)
    body = captured[0][1]
    assert '"holder":"ado-wtk-200"' in body
    assert '"resource":"crmbuilder-v2/migrations"' in body


def test_reclaim_without_holder_shows_message(qtbot):
    panel = ResourceLocksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail({"resource_name": "x", "holder": "", "acquired_at": None}, {})
    qtbot.addWidget(detail)
    panel._do_reclaim("")
    assert "no holder" in panel._action_status.text()


def test_client_list_locks_request_shape(qtbot):
    captured: list = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append((req.method, req.url.path, req.url.query.decode()))
        return httpx.Response(200, json=envelope_ok(_LOCKS))

    client = build_client(handler)
    client.list_locks(holder="ado-wtk-200")
    assert captured[0][1] == "/locks"
    assert "holder=ado-wtk-200" in captured[0][2]
