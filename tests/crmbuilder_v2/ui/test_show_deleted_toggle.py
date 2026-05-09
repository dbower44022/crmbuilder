"""v0.2 slice F: Show-deleted toggle and Restore affordance on the Decisions panel."""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QPushButton

from .conftest import build_client, envelope_ok


def _record(identifier: str, status: str = "Active") -> dict[str, Any]:
    return {
        "identifier": identifier,
        "title": f"{identifier} title",
        "decision_date": "05-08-26",
        "status": status,
        "context": "",
        "decision": "",
        "rationale": "",
        "alternatives_considered": "",
        "consequences": "",
        "supersedes_identifier": None,
        "superseded_by_identifier": None,
    }


def _handler(active: list[dict], deleted: list[dict]):
    """Return a handler that mirrors the API's filtering by include_deleted."""
    captured: dict[str, list[dict[str, str]]] = {"queries": []}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/decisions":
            captured["queries"].append(dict(req.url.params))
            include_deleted = req.url.params.get("include_deleted") == "true"
            data = active + deleted if include_deleted else active
            return httpx.Response(200, json=envelope_ok(data))
        if req.method == "GET" and req.url.path.startswith(
            "/references/touching/"
        ):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        if req.method == "GET" and req.url.path.startswith("/decisions/"):
            ident = req.url.path.split("/", 2)[-1]
            for r in active + deleted:
                if r["identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(r))
            return httpx.Response(
                404,
                json={
                    "data": None,
                    "meta": {},
                    "errors": [{"code": "not_found", "message": "missing"}],
                },
            )
        if req.method == "PATCH" and req.url.path.startswith("/decisions/"):
            ident = req.url.path.split("/", 2)[-1]
            for r in deleted:
                if r["identifier"] == ident:
                    r["status"] = "Active"
                    active.append(r)
                    deleted.remove(r)
                    return httpx.Response(200, json=envelope_ok(r))
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

    return handler, captured


def test_show_deleted_checkbox_present_in_toolbar(qtbot, qapp):
    handler, _ = _handler([_record("DEC-001")], [])
    client = build_client(handler)
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)
    check = panel.findChild(QCheckBox, "show_deleted_check")
    assert check is not None
    assert check.text() == "Show deleted"
    assert check.isChecked() is False


def test_default_refresh_does_not_include_deleted(qtbot, qapp):
    handler, captured = _handler([_record("DEC-001")], [_record("DEC-002", "Deleted")])
    client = build_client(handler)
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() > 0)
    # Last GET /decisions had no include_deleted query.
    decisions_queries = [
        q for q in captured["queries"]
    ]
    assert decisions_queries, "no /decisions calls observed"
    assert "include_deleted" not in decisions_queries[-1]
    # Only the active decision is rendered.
    assert panel._model.rowCount() == 1


def test_toggle_on_includes_deleted_and_renders_strikethrough(qtbot, qapp):
    handler, captured = _handler(
        [_record("DEC-001")], [_record("DEC-002", "Deleted")]
    )
    client = build_client(handler)
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)
    check = panel.findChild(QCheckBox, "show_deleted_check")
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() > 0)
    check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2)
    # The most recent /decisions call should carry the param.
    assert captured["queries"][-1].get("include_deleted") == "true"
    # The deleted row's font should be strikethrough.
    rows_by_id = {
        panel._model.record_at(r)["identifier"]: r
        for r in range(panel._model.rowCount())
    }
    deleted_row = rows_by_id["DEC-002"]
    active_row = rows_by_id["DEC-001"]
    deleted_font = panel._model.data(
        panel._model.index(deleted_row, 0), Qt.ItemDataRole.FontRole
    )
    active_font = panel._model.data(
        panel._model.index(active_row, 0), Qt.ItemDataRole.FontRole
    )
    assert isinstance(deleted_font, QFont)
    assert deleted_font.strikeOut() is True
    # Active row should not have a strikethrough font (predicate returns False).
    assert active_font is None or active_font.strikeOut() is False


def test_detail_pane_on_deleted_record_shows_restore_and_edit(qtbot, qapp):
    handler, _ = _handler([], [_record("DEC-002", "Deleted")])
    client = build_client(handler)
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)
    check = panel.findChild(QCheckBox, "show_deleted_check")
    check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1)
    # Render the detail pane directly with the deleted record.
    record = panel._model.record_at(0)
    detail = panel.render_detail(record, {"references": {"as_source": [], "as_target": []}})
    qtbot.addWidget(detail)
    assert detail.findChild(QPushButton, "restore_decision_button") is not None
    assert detail.findChild(QPushButton, "edit_decision_button") is not None
    assert detail.findChild(QPushButton, "delete_decision_button") is None


def test_detail_pane_on_active_record_shows_edit_and_delete(qtbot, qapp):
    handler, _ = _handler([_record("DEC-001")], [])
    client = build_client(handler)
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1)
    record = panel._model.record_at(0)
    detail = panel.render_detail(record, {"references": {"as_source": [], "as_target": []}})
    qtbot.addWidget(detail)
    assert detail.findChild(QPushButton, "edit_decision_button") is not None
    assert detail.findChild(QPushButton, "delete_decision_button") is not None
    assert detail.findChild(QPushButton, "restore_decision_button") is None


def test_restore_click_confirms_then_calls_restore_decision(qtbot, qapp, monkeypatch):
    handler, _ = _handler([], [_record("DEC-002", "Deleted")])
    client = build_client(handler)
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    # Auto-confirm the QMessageBox.
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)

    called: dict[str, str] = {}

    def fake_restore(identifier: str):
        called["identifier"] = identifier
        return {"identifier": identifier, "status": "Active"}

    monkeypatch.setattr(client, "restore_decision", fake_restore)

    record = _record("DEC-002", "Deleted")
    panel._on_restore_clicked(record)
    assert called["identifier"] == "DEC-002"


def test_restore_click_declined_does_not_call_restore(qtbot, qapp, monkeypatch):
    handler, _ = _handler([], [_record("DEC-002", "Deleted")])
    client = build_client(handler)
    panel = DecisionsPanel(client)
    qtbot.addWidget(panel)

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)

    called: dict[str, str] = {}

    def fake_restore(identifier: str):
        called["identifier"] = identifier
        return {"identifier": identifier, "status": "Active"}

    monkeypatch.setattr(client, "restore_decision", fake_restore)

    panel._on_restore_clicked(_record("DEC-002", "Deleted"))
    assert "identifier" not in called
