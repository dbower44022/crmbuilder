"""Tests for the DecisionDeleteDialog (slice G)."""

from __future__ import annotations

from unittest.mock import MagicMock

from crmbuilder_v2.ui.dialogs.decision_delete import DecisionDeleteDialog
from crmbuilder_v2.ui.exceptions import ConflictError, NotFoundError


def test_construct_shows_identifier_and_title(qtbot):
    dialog = DecisionDeleteDialog(
        MagicMock(), "DEC-007", "Universal references pattern"
    )
    qtbot.addWidget(dialog)
    text = dialog._body_label.text()
    assert "DEC-007" in text
    assert "Universal references pattern" in text
    assert "cannot be undone" in text


def test_successful_delete_accepts(qtbot):
    client = MagicMock()
    client.delete_decision.return_value = {"identifier": "DEC-007"}
    dialog = DecisionDeleteDialog(client, "DEC-007", "title")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()

    client.delete_decision.assert_called_once_with("DEC-007")


def test_conflict_routes_to_error_dialog(qtbot, monkeypatch):
    """Soft-delete never conflicts; if a 409 ever surfaces, the dialog falls
    back to the generic ErrorDialog instead of replacing the body."""
    client = MagicMock()
    client.delete_decision.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "unexpected 409"}],
        message="unexpected 409",
    )

    captured: dict = {}

    class _StubErrorDialog:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def exec(self):
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog",
        _StubErrorDialog,
    )

    dialog = DecisionDeleteDialog(client, "DEC-018", "Some title")
    qtbot.addWidget(dialog)
    dialog._on_delete_clicked()
    qtbot.waitUntil(lambda: "title" in captured, timeout=2000)

    assert captured["title"] == "Could not delete decision"
    # Body label is unchanged — body-replacement path is gone.
    assert "cannot be undone" in dialog._body_label.text()
    # Delete button isn't hidden (the body-replacement path used .hide()),
    # and is re-enabled for retry.
    assert dialog._delete_btn.isHidden() is False
    assert dialog._delete_btn.isEnabled() is True
    # Cancel button label is unchanged (body-replacement path renamed it to "Close").
    assert dialog._cancel_btn.text() == "Cancel"


def test_not_found_treated_as_success(qtbot):
    client = MagicMock()
    client.delete_decision.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = DecisionDeleteDialog(client, "DEC-007", "title")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()
