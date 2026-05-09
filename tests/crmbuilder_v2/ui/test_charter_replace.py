"""Slice E (v0.2): integration tests for CharterPanel replace flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
from crmbuilder_v2.ui.panels.charter import CharterPanel
from PySide6.QtWidgets import QDialog, QPushButton

from .conftest import build_client, envelope_ok


def _versions(*, with_two: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "id": 2,
            "version": 2,
            "is_current": True,
            "created_at": "2026-05-01T12:00:00",
            "payload": {"scope": "v2"},
        }
    ]
    if with_two:
        rows.insert(
            0,
            {
                "id": 1,
                "version": 1,
                "is_current": False,
                "created_at": "2026-04-01T12:00:00",
                "payload": {"scope": "v1"},
            },
        )
        rows = [rows[1], rows[0]]
    return rows


def _charter_handler(rows: list[dict[str, Any]]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/charter/versions":
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
    client = build_client(_charter_handler(_versions()))
    panel = CharterPanel(client)
    qtbot.addWidget(panel)
    btn = panel.findChild(QPushButton, "new_charter_version_button")
    assert btn is not None


def test_new_version_click_opens_dialog_with_current_payload(qtbot, monkeypatch):
    client = build_client(_charter_handler(_versions()))
    panel = CharterPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    captured: dict[str, Any] = {}

    class _StubDialog:
        def __init__(self, c, payload, parent=None):
            captured["client"] = c
            captured["payload"] = payload
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.charter.CharterReplaceDialog", _StubDialog
    )
    panel._on_new_version_clicked()

    assert captured["payload"] == {"scope": "v2"}
    assert captured["parent"] is panel


def test_new_version_with_no_current_opens_error(qtbot, monkeypatch):
    client = build_client(_charter_handler([]))
    panel = CharterPanel(client)
    qtbot.addWidget(panel)
    panel._records = []  # no current

    error_dialogs: list[Any] = []

    class _StubError:
        def __init__(self, *a, **kw):
            error_dialogs.append((a, kw))

        def exec(self):  # noqa: A003
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.charter.ErrorDialog", _StubError
    )
    panel._on_new_version_clicked()
    assert len(error_dialogs) == 1


def test_successful_new_version_triggers_refresh(qtbot, monkeypatch):
    client = build_client(_charter_handler(_versions()))
    panel = CharterPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    class _StubDialog:
        def __init__(self, c, payload, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.charter.CharterReplaceDialog", _StubDialog
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)
    panel._on_new_version_clicked()
    assert refresh_calls["count"] == 1


def test_make_current_button_renders_for_non_current_version(qtbot):
    client = build_client(_charter_handler(_versions()))
    panel = CharterPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    # Find the v1 (not current) record and select it.
    target_row = next(
        i for i, r in enumerate(panel._records) if r["version"] == 1
    )
    panel._select_row(target_row)
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget()
        is not panel._loading_detail
        and panel._detail_stack.currentWidget() is not panel._empty_detail,
        timeout=2000,
    )
    detail = panel._detail_stack.currentWidget()
    btn = detail.findChild(QPushButton, "make_current_button")
    assert btn is not None


def test_make_current_button_absent_for_current_version(qtbot):
    client = build_client(_charter_handler(_versions()))
    panel = CharterPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    target_row = next(
        i for i, r in enumerate(panel._records) if r["version"] == 2
    )
    panel._select_row(target_row)
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget()
        is not panel._loading_detail
        and panel._detail_stack.currentWidget() is not panel._empty_detail,
        timeout=2000,
    )
    detail = panel._detail_stack.currentWidget()
    btn = detail.findChild(QPushButton, "make_current_button")
    assert btn is None


def test_make_current_confirmation_yes_calls_client(qtbot, monkeypatch):
    client = MagicMock()
    client.list_charter_versions.return_value = _versions()
    client.list_references_touching.return_value = {
        "as_source": [],
        "as_target": [],
    }
    client.make_charter_version_current.return_value = {
        "version": 1,
        "is_current": True,
        "payload": {"scope": "v1"},
    }

    panel = CharterPanel(client)
    qtbot.addWidget(panel)

    # Stub QMessageBox.exec to always return Yes.
    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.charter.QMessageBox.exec",
        lambda self: __import__(
            "PySide6.QtWidgets", fromlist=["QMessageBox"]
        ).QMessageBox.StandardButton.Yes,
    )

    panel._on_make_current(1)

    qtbot.waitUntil(
        lambda: client.make_charter_version_current.called, timeout=2000
    )
    client.make_charter_version_current.assert_called_once_with(1)


def test_make_current_confirmation_no_does_not_call_client(qtbot, monkeypatch):
    client = MagicMock()
    panel = CharterPanel(client)
    qtbot.addWidget(panel)

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.charter.QMessageBox.exec",
        lambda self: __import__(
            "PySide6.QtWidgets", fromlist=["QMessageBox"]
        ).QMessageBox.StandardButton.No,
    )

    panel._on_make_current(1)
    assert not client.make_charter_version_current.called


def test_references_section_renders_on_detail_pane(qtbot):
    client = build_client(_charter_handler(_versions()))
    panel = CharterPanel(client)
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


def test_charter_panel_right_click_invokes_context_menu_factory(
    qtbot, client_stub
):
    """v0.3 slice B: right-click on the master view calls _build_context_menu."""
    from unittest.mock import patch

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QMenu

    panel = CharterPanel(client=client_stub)
    qtbot.addWidget(panel)
    # Use return_value=QMenu() so the slot's blocking menu.exec() branch
    # (taken when the factory returns a non-empty menu) is skipped — the
    # smoke test only needs to confirm the factory is invoked.
    empty_menu = QMenu(panel)
    with patch.object(
        panel, "_build_context_menu", return_value=empty_menu
    ) as spy:
        panel._master_view.customContextMenuRequested.emit(QPoint(10, 10))
        assert spy.called
