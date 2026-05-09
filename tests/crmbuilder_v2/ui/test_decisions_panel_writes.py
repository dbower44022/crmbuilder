"""Slice G: integration tests for DecisionsPanel write surfaces."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from PySide6.QtWidgets import QDialog, QPushButton

from .conftest import build_client, envelope_ok


def _stub_record(identifier: str = "DEC-007") -> dict[str, Any]:
    return {
        "identifier": identifier,
        "title": "Universal references pattern",
        "decision_date": "05-06-26",
        "status": "Active",
        "context": "ctx",
        "decision": "dec",
        "rationale": "rat",
        "alternatives_considered": "alt",
        "consequences": "csq",
        "supersedes_identifier": None,
        "superseded_by_identifier": None,
    }


def _decisions_only_handler(records: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/decisions":
            return httpx.Response(200, json=envelope_ok(records))
        if (
            req.method == "GET"
            and req.url.path.startswith("/references/touching/")
        ):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        if req.method == "GET" and req.url.path.startswith("/decisions/"):
            ident = req.url.path.split("/", 2)[-1]
            for record in records:
                if record["identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(record))
            return httpx.Response(
                404,
                json={
                    "data": None,
                    "meta": {},
                    "errors": [{"code": "not_found", "message": "missing"}],
                },
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


def test_toolbar_new_decision_button_opens_create_dialog(qtbot, monkeypatch):
    client = build_client(_decisions_only_handler([]))
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    new_btn = panel.findChild(QPushButton, "new_decision_button")
    assert new_btn is not None

    captured = {"opened": False, "client": None, "parent": None}

    class _StubDialog:
        def __init__(self, c, parent=None):
            captured["opened"] = True
            captured["client"] = c
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

        def created_identifier(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.decisions.DecisionCreateDialog", _StubDialog
    )

    new_btn.click()

    assert captured["opened"] is True
    assert captured["client"] is client
    assert captured["parent"] is panel


def test_successful_create_calls_select_record_by_identifier(qtbot, monkeypatch):
    client = build_client(_decisions_only_handler([]))
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    class _StubDialog:
        def __init__(self, c, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

        def created_identifier(self):
            return "DEC-100"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.decisions.DecisionCreateDialog", _StubDialog
    )

    captured = {}

    def _stub_select(ident):
        captured["selected"] = ident
        return True

    monkeypatch.setattr(panel, "select_record_by_identifier", _stub_select)

    panel._on_new_decision_clicked()

    assert captured["selected"] == "DEC-100"


def test_detail_pane_has_edit_and_delete_buttons(qtbot):
    record = _stub_record()
    client = build_client(_decisions_only_handler([record]))
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=2000)

    panel._select_row(0)
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget() is not panel._loading_detail
        and panel._detail_stack.currentWidget() is not panel._empty_detail,
        timeout=2000,
    )

    detail = panel._detail_stack.currentWidget()
    edit_btn = detail.findChild(QPushButton, "edit_decision_button")
    delete_btn = detail.findChild(QPushButton, "delete_decision_button")
    assert edit_btn is not None
    assert delete_btn is not None


def test_edit_click_fetches_fresh_record_and_opens_edit_dialog(qtbot, monkeypatch):
    record = _stub_record()
    fresh = dict(record)
    fresh["title"] = "Updated title"
    client = MagicMock()
    client.get_decision.return_value = fresh

    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    captured = {}

    class _StubEdit:
        def __init__(self, c, rec, parent=None):
            captured["client"] = c
            captured["record"] = rec
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.decisions.DecisionEditDialog", _StubEdit
    )

    panel._on_edit_clicked(record)

    client.get_decision.assert_called_once_with("DEC-007")
    assert captured["record"] is fresh


def test_successful_edit_triggers_panel_refresh(qtbot, monkeypatch):
    record = _stub_record()
    client = MagicMock()
    client.get_decision.return_value = record

    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    class _StubEdit:
        def __init__(self, c, rec, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.decisions.DecisionEditDialog", _StubEdit
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)

    panel._on_edit_clicked(record)

    assert refresh_calls["count"] == 1


def test_delete_click_opens_dialog_with_identifier_and_title(qtbot, monkeypatch):
    record = _stub_record()
    client = MagicMock()
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    captured = {}

    class _StubDelete:
        def __init__(self, c, identifier, title, parent=None):
            captured["client"] = c
            captured["identifier"] = identifier
            captured["title"] = title
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.decisions.DecisionDeleteDialog", _StubDelete
    )

    panel._on_delete_clicked(record)

    assert captured["identifier"] == "DEC-007"
    assert captured["title"] == "Universal references pattern"


def test_successful_delete_triggers_panel_refresh(qtbot, monkeypatch):
    record = _stub_record()
    client = MagicMock()
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    class _StubDelete:
        def __init__(self, c, identifier, title, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.decisions.DecisionDeleteDialog", _StubDelete
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)

    panel._on_delete_clicked(record)

    assert refresh_calls["count"] == 1


def test_decisions_panel_right_click_invokes_context_menu_factory(
    qtbot, client_stub
):
    """v0.3 slice B: right-click on the master view calls _build_context_menu."""
    from unittest.mock import patch

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QMenu

    panel = DecisionsPanel(client=client_stub)
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
