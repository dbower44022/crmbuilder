"""v0.3 slice D: integration tests for SessionsPanel write surfaces.

Per DEC-013 / DEC-034, sessions are append-only and user-authorable
through the UI. This file covers the create-only write surface (toolbar
button, whitespace right-click, refresh integration) and asserts the
absence of any Edit / Delete / Restore affordance on the detail pane
or context menu.
"""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QDialog, QPushButton

from .conftest import build_client, envelope_ok


def _stub_record(identifier: str = "SES-008") -> dict[str, Any]:
    return {
        "identifier": identifier,
        "title": "v0.3 planning",
        "session_date": "05-08-26",
        "status": "Complete",
        "summary": "summary body",
        "topics_covered": "topics body",
        "artifacts_produced": "artifacts body",
        "in_flight_at_end": "",
        "conversation_reference": "ref body",
    }


def _sessions_only_handler(records: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/sessions":
            return httpx.Response(200, json=envelope_ok(records))
        if (
            req.method == "GET"
            and req.url.path.startswith("/references/touching/")
        ):
            return httpx.Response(
                200,
                json=envelope_ok({"as_source": [], "as_target": []}),
            )
        if req.method == "GET" and req.url.path.startswith("/sessions/"):
            ident = req.url.path.split("/", 2)[-1]
            for record in records:
                if record["identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(record))
            return httpx.Response(
                404,
                json={
                    "data": None,
                    "meta": {},
                    "errors": [
                        {"code": "not_found", "message": "missing"}
                    ],
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


# ---------------------------------------------------------------------------
# Toolbar New Session button
# ---------------------------------------------------------------------------


def test_new_session_button_renders_in_toolbar(qtbot):
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    new_btn = panel.findChild(QPushButton, "new_session_button")
    assert new_btn is not None
    assert new_btn.text() == "New Session"


def test_new_session_button_opens_create_dialog(qtbot, monkeypatch):
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    captured = {"opened": False, "client": None, "parent": None}

    class _StubDialog:
        def __init__(self, c, parent=None):
            captured["opened"] = True
            captured["client"] = c
            captured["parent"] = parent

        def exec(self):  # noqa: A003 — match Qt API
            return QDialog.DialogCode.Rejected

        def created_identifier(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.sessions.SessionCreateDialog",
        _StubDialog,
    )

    new_btn = panel.findChild(QPushButton, "new_session_button")
    new_btn.click()

    assert captured["opened"] is True
    assert captured["client"] is client
    assert captured["parent"] is panel


def test_create_dialog_save_selects_new_row_by_identifier(
    qtbot, monkeypatch
):
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    class _StubDialog:
        def __init__(self, c, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

        def created_identifier(self):
            return "SES-009"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.sessions.SessionCreateDialog",
        _StubDialog,
    )

    captured: dict[str, Any] = {}

    def _stub_select(ident):
        captured["selected"] = ident
        return True

    monkeypatch.setattr(
        panel, "select_record_by_identifier", _stub_select
    )

    panel._on_new_session_clicked()

    assert captured["selected"] == "SES-009"


def test_create_dialog_save_without_identifier_falls_back_to_refresh(
    qtbot, monkeypatch
):
    """If the dialog accepts but exposes no identifier, refresh the panel."""
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    class _StubDialog:
        def __init__(self, c, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

        def created_identifier(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.sessions.SessionCreateDialog",
        _StubDialog,
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)

    panel._on_new_session_clicked()

    assert refresh_calls["count"] == 1


# ---------------------------------------------------------------------------
# Whitespace context menu
# ---------------------------------------------------------------------------


def test_context_menu_whitespace_includes_new_session(qtbot):
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    menu = panel._build_context_menu(QModelIndex())
    actions = [a.text() for a in menu.actions()]
    assert actions == ["New session"]


def test_context_menu_whitespace_action_invokes_new_session_handler(
    qtbot, monkeypatch
):
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    captured = {"called": False}

    def _on_clicked():
        captured["called"] = True

    monkeypatch.setattr(panel, "_on_new_session_clicked", _on_clicked)

    # Re-build the menu so the patched handler is bound.
    menu = panel._build_context_menu(QModelIndex())
    new_action = menu.actions()[0]
    new_action.trigger()

    assert captured["called"] is True


# ---------------------------------------------------------------------------
# Row context menu — append-only assertions
# ---------------------------------------------------------------------------


def _seed_table_records(panel: SessionsPanel, records: list[dict]):
    """Populate the panel's master model with records and return the
    QModelIndex of row 0 — used to drive the row context-menu factory."""
    panel._records = records
    panel._model.set_records(records)
    return panel._model.index(0, 0)


def test_context_menu_row_does_not_include_edit_or_delete(qtbot):
    """Row right-click stays read-only per DEC-013 / DEC-034."""
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    index = _seed_table_records(panel, [_stub_record()])
    menu = panel._build_context_menu(index)
    actions = [a.text() for a in menu.actions()]
    assert actions == ["Go to references", "Copy identifier"]
    assert "Edit" not in actions
    assert "Delete" not in actions
    assert "Restore" not in actions


# ---------------------------------------------------------------------------
# Detail pane — append-only assertions
# ---------------------------------------------------------------------------


def _select_first_row(qtbot, panel: SessionsPanel) -> None:
    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._model.rowCount() == 1, timeout=2000
    )
    panel._select_row(0)
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget() is not panel._loading_detail
        and panel._detail_stack.currentWidget() is not panel._empty_detail,
        timeout=2000,
    )


def test_detail_pane_has_no_edit_button(qtbot):
    record = _stub_record()
    client = build_client(_sessions_only_handler([record]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    _select_first_row(qtbot, panel)
    detail = panel._detail_stack.currentWidget()

    # Walk every QPushButton in the detail tree; assert none read "Edit"
    # or carry an edit-style objectName. A blanket scan is safer than a
    # findChild on a single name because future styling changes could
    # introduce different identifiers.
    for btn in detail.findChildren(QPushButton):
        text = (btn.text() or "").strip().lower()
        name = (btn.objectName() or "").lower()
        assert text != "edit"
        assert "edit" not in name


def test_detail_pane_has_no_delete_button(qtbot):
    record = _stub_record()
    client = build_client(_sessions_only_handler([record]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    _select_first_row(qtbot, panel)
    detail = panel._detail_stack.currentWidget()

    # The ReferencesSection on the detail pane carries its own per-row
    # "Delete" affordance for individual references; skip buttons that
    # belong to that subtree (those delete *references*, not the
    # *session* record itself).
    refs_section = detail.findChild(ReferencesSection)
    refs_descendants = (
        set(refs_section.findChildren(QPushButton))
        if refs_section is not None
        else set()
    )

    for btn in detail.findChildren(QPushButton):
        if btn in refs_descendants:
            continue
        text = (btn.text() or "").strip().lower()
        name = (btn.objectName() or "").lower()
        assert text != "delete"
        assert "delete" not in name


def test_detail_pane_has_no_restore_button(qtbot):
    record = _stub_record()
    client = build_client(_sessions_only_handler([record]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    _select_first_row(qtbot, panel)
    detail = panel._detail_stack.currentWidget()

    for btn in detail.findChildren(QPushButton):
        text = (btn.text() or "").strip().lower()
        name = (btn.objectName() or "").lower()
        assert text != "restore"
        assert "restore" not in name
