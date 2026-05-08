"""Tests for the DecisionCreateDialog (slice G)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.access.vocab import DECISION_STATUSES
from crmbuilder_v2.ui.dialogs.decision_create import DecisionCreateDialog
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    ServerError,
    StorageConnectionError,
    ValidationError,
)
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit


def _stub_client():
    return MagicMock()


def _fill_required(dialog: DecisionCreateDialog) -> None:
    dialog._widgets.identifier.setText("DEC-100")
    dialog._widgets.title.setText("Some title")
    dialog._widgets.decision_date.setText("05-08-26")
    # status is preselected to Active.


def test_construct_has_all_eleven_fields(qtbot):
    dialog = DecisionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)

    assert isinstance(dialog._widgets.identifier, QLineEdit)
    assert isinstance(dialog._widgets.title, QLineEdit)
    assert isinstance(dialog._widgets.decision_date, QLineEdit)
    assert isinstance(dialog._widgets.status, QComboBox)
    assert isinstance(dialog._widgets.context, QPlainTextEdit)
    assert isinstance(dialog._widgets.decision, QPlainTextEdit)
    assert isinstance(dialog._widgets.rationale, QPlainTextEdit)
    assert isinstance(dialog._widgets.alternatives_considered, QPlainTextEdit)
    assert isinstance(dialog._widgets.consequences, QPlainTextEdit)
    assert isinstance(dialog._widgets.supersedes, QLineEdit)
    assert isinstance(dialog._widgets.superseded_by, QLineEdit)
    assert dialog._save_btn is not None
    assert dialog._cancel_btn is not None


def test_status_dropdown_sourced_from_vocab(qtbot):
    dialog = DecisionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    items = [
        dialog._widgets.status.itemText(i)
        for i in range(dialog._widgets.status.count())
    ]
    assert items == sorted(DECISION_STATUSES)
    assert dialog._widgets.status.currentText() == "Active"


def test_required_fields_block_submission(qtbot):
    client = _stub_client()
    dialog = DecisionCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._on_save_clicked()

    # No API call.
    client.create_decision.assert_not_called()
    # Inline errors on the four required fields.
    for field in ("identifier", "title", "decision_date"):
        label = dialog._widgets.error_labels[field]
        assert label.text() == "This field is required."


def test_successful_create_accepts_with_identifier(qtbot):
    client = _stub_client()
    client.create_decision.return_value = {
        "identifier": "DEC-100",
        "title": "Some title",
    }
    dialog = DecisionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    assert dialog.created_identifier() == "DEC-100"
    args, kwargs = client.create_decision.call_args
    body = args[0] if args else kwargs.get("body")
    assert body["identifier"] == "DEC-100"
    assert body["title"] == "Some title"
    assert body["decision_date"] == "05-08-26"
    assert body["status"] == "Active"
    # Empty supersedes / superseded_by are skipped from the body.
    assert "supersedes" not in body
    assert "superseded_by" not in body


def test_validation_error_shows_inline(qtbot):
    client = _stub_client()
    client.create_decision.side_effect = ValidationError(
        errors=[
            {
                "code": "validation_error",
                "field": "status",
                "message": "Invalid status value",
            }
        ],
        message="Validation failed",
    )
    dialog = DecisionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    # Trigger save and let the worker complete; dialog stays open.
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["status"].text() != "",
        timeout=2000,
    )
    assert dialog._widgets.error_labels["status"].text() == "Invalid status value"
    assert dialog.result() == 0  # not accepted


def test_conflict_error_shows_inline_on_identifier(qtbot):
    client = _stub_client()
    client.create_decision.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "exists"}],
        message="exists",
    )
    dialog = DecisionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["identifier"].text() != "",
        timeout=2000,
    )
    assert (
        dialog._widgets.error_labels["identifier"].text()
        == "An identifier with this value already exists."
    )


def test_storage_connection_error_rejects_dialog(qtbot):
    client = _stub_client()
    client.create_decision.side_effect = StorageConnectionError("connection lost")
    dialog = DecisionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    with qtbot.waitSignal(dialog.rejected, timeout=2000):
        dialog._on_save_clicked()


def test_server_error_opens_generic_dialog(qtbot, monkeypatch):
    """5xx error opens an ErrorDialog and the create dialog stays open."""
    client = _stub_client()
    client.create_decision.side_effect = ServerError(
        status_code=500, errors=[], message="boom"
    )
    captured: dict[str, Any] = {}

    class _Recorder(ErrorDialog):
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            super().__init__(*args, **kwargs)

        def exec(self):  # noqa: A003 — match base method
            captured["exec_called"] = True
            return 1

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.decision_create.ErrorDialog", _Recorder
    )

    dialog = DecisionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(lambda: captured.get("exec_called") is True, timeout=2000)
    # Dialog stays open (not accepted, not rejected).
    assert dialog.result() == 0
    assert dialog._save_btn.isEnabled() is True
