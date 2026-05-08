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


def test_conflict_replaces_body_and_hides_delete_button(qtbot):
    client = MagicMock()
    client.delete_decision.side_effect = ConflictError(
        errors=[
            {"code": "conflict", "message": "referenced by SES-004, REF-12"}
        ],
        message="referenced by SES-004, REF-12",
    )
    dialog = DecisionDeleteDialog(client, "DEC-018", "Some title")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dialog._on_delete_clicked()
    qtbot.waitUntil(
        lambda: dialog._cancel_btn.text() == "Close",
        timeout=2000,
    )

    assert dialog._delete_btn.isVisible() is False
    assert "referenced" in dialog._body_label.text()
    assert dialog._cancel_btn.text() == "Close"


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
