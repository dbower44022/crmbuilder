"""SessionsPanel write-surface integration tests — PI-073 / DEC-314.

Originally written against the legacy append-only model (DEC-013 /
DEC-034), where sessions were user-authorable but never editable. The
PI-073 / DEC-314 redesign makes sessions the medium-agnostic
communication container with a schedulable, stateful six-status
lifecycle, and the panel now supports the full create / edit / delete /
restore surface. These tests are updated to the new model: they cover
the create write surface (toolbar button, whitespace right-click,
refresh integration) and assert that the row context menu and detail
pane now expose the lifecycle affordances (Edit / Delete / Restore) the
redesign introduced.
"""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QDialog, QPushButton

from .conftest import build_client, envelope_ok

# A valid executive summary (200-800 chars) per the PI-102 schema.
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _stub_record(identifier: str = "SES-008") -> dict[str, Any]:
    return {
        "session_identifier": identifier,
        "session_title": "v0.3 planning",
        "session_description": "session description body",
        "session_medium": "chat",
        "session_status": "complete",
        "session_executive_summary": _EXEC_SUMMARY,
        "session_notes": "internal notes body",
        "session_participants": [],
        "session_medium_metadata": {},
        "session_deleted_at": None,
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
                if record["session_identifier"] == ident:
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

        def saved_identifier(self):
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

        def saved_identifier(self):
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

    panel._on_new_clicked()

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

        def saved_identifier(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.sessions.SessionCreateDialog",
        _StubDialog,
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)

    panel._on_new_clicked()

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

    monkeypatch.setattr(panel, "_on_new_clicked", _on_clicked)

    # Re-build the menu so the patched handler is bound.
    menu = panel._build_context_menu(QModelIndex())
    new_action = menu.actions()[0]
    new_action.trigger()

    assert captured["called"] is True


# ---------------------------------------------------------------------------
# Row context menu — lifecycle CRUD assertions (PI-073 / DEC-314)
# ---------------------------------------------------------------------------


def _seed_table_records(panel: SessionsPanel, records: list[dict]):
    """Populate the panel's master model with records and return the
    QModelIndex of row 0 — used to drive the row context-menu factory."""
    panel._records = records
    panel._model.set_records(records)
    return panel._model.index(0, 0)


def test_context_menu_row_includes_lifecycle_actions(qtbot):
    """Row right-click now exposes the editable lifecycle surface
    introduced by the PI-073 / DEC-314 redesign (Edit / Delete), in
    addition to the always-present New session and Copy identifier."""
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    index = _seed_table_records(panel, [_stub_record()])
    menu = panel._build_context_menu(index)
    actions = [a.text() for a in menu.actions()]
    assert actions == ["New session", "Edit", "Delete", "Copy identifier"]
    assert "Edit" in actions
    assert "Delete" in actions
    # A live (non-deleted) record offers Delete, not Restore.
    assert "Restore" not in actions


def test_context_menu_deleted_row_offers_restore(qtbot):
    """A soft-deleted row offers Restore instead of Delete."""
    client = build_client(_sessions_only_handler([]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    deleted = _stub_record()
    deleted["session_deleted_at"] = "2026-05-29T00:00:00"
    index = _seed_table_records(panel, [deleted])
    menu = panel._build_context_menu(index)
    actions = [a.text() for a in menu.actions()]
    assert actions == ["New session", "Edit", "Restore", "Copy identifier"]
    assert "Delete" not in actions


# ---------------------------------------------------------------------------
# Detail pane — lifecycle CRUD assertions (PI-073 / DEC-314)
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


def test_detail_pane_has_edit_button(qtbot):
    record = _stub_record()
    client = build_client(_sessions_only_handler([record]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    _select_first_row(qtbot, panel)
    detail = panel._detail_stack.currentWidget()

    # The redesigned detail pane carries an Edit affordance. Walk every
    # QPushButton in the detail tree and assert one reads "Edit".
    texts = [
        (btn.text() or "").strip().lower()
        for btn in detail.findChildren(QPushButton)
    ]
    assert "edit" in texts


def test_detail_pane_has_delete_button(qtbot):
    record = _stub_record()
    client = build_client(_sessions_only_handler([record]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    _select_first_row(qtbot, panel)
    detail = panel._detail_stack.currentWidget()

    # The ReferencesSection on the detail pane carries its own per-row
    # "Delete" affordance for individual references; the session-level
    # Delete button lives outside that subtree. A live (non-deleted)
    # record exposes a session-level Delete.
    refs_section = detail.findChild(ReferencesSection)
    refs_descendants = (
        set(refs_section.findChildren(QPushButton))
        if refs_section is not None
        else set()
    )

    session_level_texts = [
        (btn.text() or "").strip().lower()
        for btn in detail.findChildren(QPushButton)
        if btn not in refs_descendants
    ]
    assert "delete" in session_level_texts


def test_detail_pane_deleted_record_has_restore_button(qtbot):
    record = _stub_record()
    record["session_deleted_at"] = "2026-05-29T00:00:00"
    client = build_client(_sessions_only_handler([record]))
    panel = SessionsPanel(client)
    qtbot.addWidget(panel)

    _select_first_row(qtbot, panel)
    detail = panel._detail_stack.currentWidget()

    texts = [
        (btn.text() or "").strip().lower()
        for btn in detail.findChildren(QPushButton)
    ]
    assert "restore" in texts
