"""v0.2 slice D: integration tests for TopicsPanel write surfaces."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtWidgets import QDialog, QPushButton

from .conftest import build_client, envelope_ok


def _stub_record(identifier: str = "TOP-001") -> dict[str, Any]:
    return {
        "identifier": identifier,
        "name": "Storage system",
        "description": "the v2 store",
        "parent_topic_identifier": None,
    }


def _topics_only_handler(records: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/topics":
            return httpx.Response(200, json=envelope_ok(records))
        if (
            req.method == "GET"
            and req.url.path.startswith("/references/touching/")
        ):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        if req.method == "GET" and req.url.path.startswith("/topics/"):
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


def test_toolbar_new_topic_button_present(qtbot):
    client = build_client(_topics_only_handler([]))
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    new_btn = panel.findChild(QPushButton, "new_topic_button")
    assert new_btn is not None
    assert new_btn.text() == "New Topic"


def test_toolbar_new_topic_button_opens_create_dialog(qtbot, monkeypatch):
    client = build_client(_topics_only_handler([]))
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    new_btn = panel.findChild(QPushButton, "new_topic_button")
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
        "crmbuilder_v2.ui.panels.topics.TopicCreateDialog", _StubDialog
    )

    new_btn.click()

    assert captured["opened"] is True
    assert captured["client"] is client
    assert captured["parent"] is panel


def test_successful_create_calls_select_record_by_identifier(qtbot, monkeypatch):
    client = build_client(_topics_only_handler([]))
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    class _StubDialog:
        def __init__(self, c, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

        def created_identifier(self):
            return "TOP-100"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.topics.TopicCreateDialog", _StubDialog
    )

    captured: dict[str, Any] = {}

    def _stub_select(ident):
        captured["selected"] = ident
        return True

    monkeypatch.setattr(panel, "select_record_by_identifier", _stub_select)

    panel._on_new_clicked()

    assert captured["selected"] == "TOP-100"


def test_detail_pane_has_edit_and_delete_buttons(qtbot):
    record = _stub_record()
    client = build_client(_topics_only_handler([record]))
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._tree_model.rowCount() == 1, timeout=2000)

    panel._select_by_identifier("TOP-001")
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget() is not panel._loading_detail
        and panel._detail_stack.currentWidget() is not panel._empty_detail,
        timeout=2000,
    )

    detail = panel._detail_stack.currentWidget()
    edit_btn = detail.findChild(QPushButton, "edit_topic_button")
    delete_btn = detail.findChild(QPushButton, "delete_topic_button")
    assert edit_btn is not None
    assert delete_btn is not None


def test_references_section_present_on_detail_pane(qtbot):
    record = _stub_record()
    client = build_client(_topics_only_handler([record]))
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._tree_model.rowCount() == 1, timeout=2000)
    panel._select_by_identifier("TOP-001")
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget() is not panel._loading_detail
        and panel._detail_stack.currentWidget() is not panel._empty_detail,
        timeout=2000,
    )

    detail = panel._detail_stack.currentWidget()
    section = detail.findChild(ReferencesSection)
    assert section is not None


def test_edit_click_fetches_fresh_record_and_opens_edit_dialog(qtbot, monkeypatch):
    record = _stub_record()
    fresh = dict(record)
    fresh["name"] = "Updated name"
    client = MagicMock()
    client.get_topic.return_value = fresh

    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    captured: dict[str, Any] = {}

    class _StubEdit:
        def __init__(self, c, rec, parent=None):
            captured["client"] = c
            captured["record"] = rec
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.topics.TopicEditDialog", _StubEdit
    )

    panel._on_edit_clicked(record)

    client.get_topic.assert_called_once_with("TOP-001")
    assert captured["record"] is fresh


def test_successful_edit_triggers_panel_refresh(qtbot, monkeypatch):
    record = _stub_record()
    client = MagicMock()
    client.get_topic.return_value = record

    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    class _StubEdit:
        def __init__(self, c, rec, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.topics.TopicEditDialog", _StubEdit
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)

    panel._on_edit_clicked(record)

    assert refresh_calls["count"] == 1


def test_delete_click_opens_dialog_with_identifier_and_name(qtbot, monkeypatch):
    record = _stub_record()
    client = MagicMock()
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    captured: dict[str, Any] = {}

    class _StubDelete:
        def __init__(self, c, identifier, title, parent=None):
            captured["client"] = c
            captured["identifier"] = identifier
            captured["title"] = title
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.topics.TopicDeleteDialog", _StubDelete
    )

    panel._on_delete_clicked(record)

    assert captured["identifier"] == "TOP-001"
    assert captured["title"] == "Storage system"


def test_successful_delete_triggers_panel_refresh(qtbot, monkeypatch):
    record = _stub_record()
    client = MagicMock()
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    class _StubDelete:
        def __init__(self, c, identifier, title, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.topics.TopicDeleteDialog", _StubDelete
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)

    panel._on_delete_clicked(record)

    assert refresh_calls["count"] == 1


def test_select_record_by_identifier_through_pending_select(qtbot):
    """When the new topic isn't yet in the items map, refresh() picks it up."""
    initial: list[dict] = []
    after_create = [_stub_record("TOP-100")]
    state = {"records": initial}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/topics":
            return httpx.Response(200, json=envelope_ok(state["records"]))
        if (
            req.method == "GET"
            and req.url.path.startswith("/references/touching/")
        ):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        if req.method == "GET" and req.url.path.startswith("/topics/"):
            ident = req.url.path.split("/", 2)[-1]
            for r in state["records"]:
                if r["identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(r))
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "no route"}],
            },
        )

    client = build_client(handler)
    panel = TopicsPanel(client)
    qtbot.addWidget(panel)

    # Simulate a successful create: the panel doesn't yet have the new
    # topic in its items map. select_record_by_identifier should fall
    # through to a refresh that finds it.
    state["records"] = after_create
    found_immediately = panel.select_record_by_identifier("TOP-100")
    assert found_immediately is False  # not yet in the items map
    qtbot.waitUntil(
        lambda: panel._items_by_identifier.get("TOP-100") is not None,
        timeout=2000,
    )
    current = panel._table.selectionModel().currentIndex()
    item = panel._tree_model.itemFromIndex(current)
    from crmbuilder_v2.ui.panels.topics import _IDENTIFIER_ROLE
    assert item.data(_IDENTIFIER_ROLE) == "TOP-100"
