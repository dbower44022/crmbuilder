"""Tests for ReferenceDeleteDialog — v0.3 slice C (DEC-033)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
from crmbuilder_v2.ui.dialogs.reference_delete import (
    ReferenceDeleteDialog,
    edge_text,
)
from crmbuilder_v2.ui.exceptions import NotFoundError, StorageConnectionError
from PySide6.QtWidgets import QLabel

from .conftest import build_client


def _success_handler() -> callable:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": {"id": 7}, "meta": {}, "errors": None}
        )

    return handler


def test_edge_text_renders_full_tuple():
    record = {
        "source_id": "SES-008",
        "target_id": "DEC-032",
        "relationship": "decided_in",
    }
    assert edge_text(record) == "SES-008 → DEC-032: decided_in"


def test_edge_text_handles_missing_fields():
    assert edge_text({}) == "? → ?: ?"


def test_dialog_body_includes_edge_text(qapp, qtbot):
    client = build_client(_success_handler())
    dialog = ReferenceDeleteDialog(
        client,
        reference_id=42,
        edge="SES-008 → DEC-032: decided_in",
    )
    qtbot.addWidget(dialog)
    body_label = dialog.findChild(QLabel, "reference_delete_body_label")
    assert body_label is not None
    text = body_label.text()
    assert "SES-008 → DEC-032: decided_in" in text
    assert "cannot be undone" in text


def test_cancel_does_not_call_delete(qapp, qtbot):
    client = MagicMock()
    dialog = ReferenceDeleteDialog(
        client, reference_id=42, edge="x → y: refs"
    )
    qtbot.addWidget(dialog)
    dialog.reject()
    client.delete_reference.assert_not_called()


def test_confirm_calls_client_delete_reference(qapp, qtbot):
    client = MagicMock()
    client.delete_reference.return_value = None
    dialog = ReferenceDeleteDialog(
        client, reference_id=42, edge="x → y: refs"
    )
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()
    client.delete_reference.assert_called_once_with(42)


def test_confirm_treats_not_found_as_already_deleted(qapp, qtbot):
    client = MagicMock()
    client.delete_reference.side_effect = NotFoundError("reference", "42")
    dialog = ReferenceDeleteDialog(
        client, reference_id=42, edge="x → y: refs"
    )
    qtbot.addWidget(dialog)
    # NotFoundError treated as already-deleted: dialog accepts so panel
    # refreshes.
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()


def test_confirm_connection_error_rejects(qapp, qtbot):
    client = MagicMock()
    client.delete_reference.side_effect = StorageConnectionError(
        "connection lost"
    )
    dialog = ReferenceDeleteDialog(
        client, reference_id=42, edge="x → y: refs"
    )
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.rejected, timeout=2000):
        dialog._on_delete_clicked()


def test_confirm_domain_error_keeps_dialog_open(qapp, qtbot, monkeypatch):
    """A non-fatal domain error opens an ErrorDialog; the main dialog
    stays open and re-enables the Delete button so the user can retry."""
    from crmbuilder_v2.ui.exceptions import StorageClientError

    client = MagicMock()
    client.delete_reference.side_effect = StorageClientError(
        message="something went wrong"
    )

    captured: list[bool] = []

    class _StubError:
        def __init__(self, *_a, **_kw):
            captured.append(True)

        def exec(self):  # noqa: A003
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_delete.ErrorDialog", _StubError
    )

    dialog = ReferenceDeleteDialog(
        client, reference_id=42, edge="x → y: refs"
    )
    qtbot.addWidget(dialog)

    # No accept/reject expected; instead the worker fires _on_delete_error.
    dialog._on_delete_clicked()
    # Wait for the worker thread to finish before asserting state.
    qtbot.waitUntil(lambda: bool(captured), timeout=2000)
    assert captured == [True]
    assert dialog._delete_btn.isEnabled() is True
