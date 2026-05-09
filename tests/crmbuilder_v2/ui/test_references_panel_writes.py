"""References panel write integration tests — v0.3 slice C.

Covers the New Reference toolbar button, the new-reference whitespace
right-click action, and the delete-reference row right-click action.
The dialog and confirmation modal are stubbed so the panel-side flow
(button → dialog → refresh on accept) is what's being tested.
"""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QDialog, QPushButton

from .conftest import build_client, envelope_ok


def _refs_handler(initial: list[dict[str, Any]]):
    state: dict[str, Any] = {"refs": list(initial)}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/references":
            return httpx.Response(200, json=envelope_ok(list(state["refs"])))
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

    return handler, state


def _ref(
    *,
    ref_id: int = 1,
    source: str = "session:SES-008",
    target: str = "decision:DEC-032",
    relationship: str = "decided_in",
) -> dict[str, Any]:
    source_type, source_id = source.split(":")
    target_type, target_id = target.split(":")
    return {
        "id": ref_id,
        "source_type": source_type,
        "source_id": source_id,
        "target_type": target_type,
        "target_id": target_id,
        "relationship": relationship,
    }


# ---------------------------------------------------------------------------
# Toolbar button
# ---------------------------------------------------------------------------


def test_panel_toolbar_has_new_reference_button(qtbot):
    handler, _ = _refs_handler([])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)
    btn = panel.findChild(QPushButton, "new_reference_button")
    assert btn is not None
    assert btn.text() == "New Reference"


def test_new_reference_click_opens_create_dialog(qtbot, monkeypatch):
    handler, _ = _refs_handler([])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)

    captured: dict[str, Any] = {}

    class _StubDialog:
        def __init__(self, client, parent=None, **kwargs):
            captured["client"] = client
            captured["parent"] = parent
            captured["kwargs"] = kwargs

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.references.ReferenceCreateDialog", _StubDialog
    )
    btn = panel.findChild(QPushButton, "new_reference_button")
    btn.click()
    assert captured["parent"] is panel
    # No pre_populated_source on toolbar-driven create.
    assert captured["kwargs"].get("pre_populated_source") is None


def test_new_reference_dialog_accept_refreshes_panel(qtbot, monkeypatch):
    handler, _ = _refs_handler([])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)

    class _AcceptingDialog:
        def __init__(self, client, parent=None, **kwargs):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.references.ReferenceCreateDialog",
        _AcceptingDialog,
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)
    panel._on_new_reference_clicked()
    assert refresh_calls["count"] == 1


# ---------------------------------------------------------------------------
# Right-click delete-reference flow
# ---------------------------------------------------------------------------


def test_row_right_click_offers_delete_reference(qtbot):
    handler, _ = _refs_handler([_ref()])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=2000)

    index = panel._model.index(0, 0)
    menu = panel._build_context_menu(index)
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "Delete reference" in labels


def test_delete_reference_action_opens_delete_dialog(qtbot, monkeypatch):
    handler, _ = _refs_handler([_ref(ref_id=42)])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=2000)

    captured: dict[str, Any] = {}

    class _StubDialog:
        def __init__(self, client, *, reference_id, edge, parent=None):
            captured["reference_id"] = reference_id
            captured["edge"] = edge
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.references.ReferenceDeleteDialog", _StubDialog
    )
    panel._on_delete_reference_clicked(_ref(ref_id=42))
    assert captured["reference_id"] == 42
    assert captured["edge"] == "SES-008 → DEC-032: decided_in"
    assert captured["parent"] is panel


def test_delete_reference_dialog_accept_refreshes_panel(qtbot, monkeypatch):
    handler, _ = _refs_handler([_ref()])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)

    class _AcceptingDialog:
        def __init__(self, client, *, reference_id, edge, parent=None):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.references.ReferenceDeleteDialog",
        _AcceptingDialog,
    )

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1

    monkeypatch.setattr(panel, "refresh", _refresh)
    panel._on_delete_reference_clicked(_ref(ref_id=7))
    assert refresh_calls["count"] == 1


def test_delete_reference_skipped_when_record_lacks_id(qtbot, monkeypatch):
    """Defensive: a row missing the integer id (corrupt data) is a no-op."""
    handler, _ = _refs_handler([])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)

    captured: list[bool] = []

    class _ShouldNotFire:
        def __init__(self, *_a, **_kw):
            captured.append(True)

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.references.ReferenceDeleteDialog",
        _ShouldNotFire,
    )
    record = _ref()
    record.pop("id", None)
    panel._on_delete_reference_clicked(record)
    assert captured == []


def test_whitespace_right_click_new_action_invokes_create_handler(
    qtbot, monkeypatch
):
    handler, _ = _refs_handler([])
    panel = ReferencesPanel(build_client(handler))
    qtbot.addWidget(panel)

    captured: list[bool] = []

    class _StubDialog:
        def __init__(self, client, parent=None, **_kwargs):
            captured.append(True)

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.references.ReferenceCreateDialog", _StubDialog
    )
    menu = panel._build_context_menu(QModelIndex())
    new_action = next(a for a in menu.actions() if a.text() == "New reference")
    new_action.trigger()
    assert captured == [True]
