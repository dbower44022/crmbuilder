"""Slice E (v0.2): integration tests for StatusPanel replace flow.

Mirror of test_charter_replace.py.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
from crmbuilder_v2.ui.panels.status import StatusPanel
from PySide6.QtWidgets import QDialog, QPushButton

from .conftest import build_client, envelope_ok


def _versions() -> list[dict[str, Any]]:
    return [
        {
            "id": 2,
            "version": 2,
            "is_current": True,
            "created_at": "2026-05-01T12:00:00",
            "payload": {"phase": "Build"},
        },
        {
            "id": 1,
            "version": 1,
            "is_current": False,
            "created_at": "2026-04-01T12:00:00",
            "payload": {"phase": "Plan"},
        },
    ]


def _status_handler(rows: list[dict[str, Any]]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/status/versions":
            return httpx.Response(200, json=envelope_ok(rows))
        if req.method == "GET" and req.url.path.startswith("/references/touching/"):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "no route"}],
            },
        )

    return handler


def test_toolbar_has_new_version_button(qtbot):
    client = build_client(_status_handler(_versions()))
    panel = StatusPanel(client)
    qtbot.addWidget(panel)
    btn = panel.findChild(QPushButton, "new_status_version_button")
    assert btn is not None


def test_new_version_click_opens_dialog_with_current_payload(qtbot, monkeypatch):
    client = build_client(_status_handler(_versions()))
    panel = StatusPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    captured: dict[str, Any] = {}

    class _StubDialog:
        def __init__(self, c, payload, parent=None):
            captured["client"] = c
            captured["payload"] = payload

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.status.StatusReplaceDialog", _StubDialog
    )
    panel._on_new_version_clicked()
    assert captured["payload"] == {"phase": "Build"}


def test_successful_new_version_triggers_refresh(qtbot, monkeypatch):
    client = build_client(_status_handler(_versions()))
    panel = StatusPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    class _StubDialog:
        def __init__(self, c, payload, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.status.StatusReplaceDialog", _StubDialog
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)
    panel._on_new_version_clicked()
    assert refresh_calls["count"] == 1


def test_make_current_yes_calls_client(qtbot, monkeypatch):
    client = MagicMock()
    client.list_status_versions.return_value = _versions()
    client.list_references_touching.return_value = {
        "as_source": [],
        "as_target": [],
    }
    client.make_status_version_current.return_value = {
        "version": 1,
        "is_current": True,
    }

    panel = StatusPanel(client)
    qtbot.addWidget(panel)

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.status.QMessageBox.exec",
        lambda self: __import__(
            "PySide6.QtWidgets", fromlist=["QMessageBox"]
        ).QMessageBox.StandardButton.Yes,
    )
    panel._on_make_current(1)
    qtbot.waitUntil(
        lambda: client.make_status_version_current.called, timeout=2000
    )
    client.make_status_version_current.assert_called_once_with(1)


def test_references_section_renders_on_detail_pane(qtbot):
    client = build_client(_status_handler(_versions()))
    panel = StatusPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    panel._select_row(0)
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget()
        is not panel._loading_detail
        and panel._detail_stack.currentWidget() is not panel._empty_detail,
        timeout=2000,
    )
    detail = panel._detail_stack.currentWidget()
    from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

    found = detail.findChildren(ReferencesSection)
    assert len(found) == 1
