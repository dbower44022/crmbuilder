"""Tests for the DecisionEditDialog (slice G)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.ui.dialogs.decision_edit import DecisionEditDialog
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import NotFoundError, ValidationError

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7


def _record() -> dict[str, Any]:
    return {
        "identifier": "DEC-007",
        "title": "Universal references pattern",
        "decision_date": "05-06-26",
        "status": "Active",
        "executive_summary": _VALID_EXEC_SUMMARY,
        "context": "ctx",
        "decision": "dec",
        "rationale": "rat",
        "alternatives_considered": "alt",
        "consequences": "csq",
        "supersedes_identifier": None,
        "superseded_by_identifier": None,
    }


def test_construct_pre_populates_from_record(qtbot):
    dialog = DecisionEditDialog(MagicMock(), _record())
    qtbot.addWidget(dialog)

    assert dialog._widgets.identifier.text() == "DEC-007"
    assert dialog._widgets.title.text() == "Universal references pattern"
    assert dialog._widgets.decision_date.date_text() == "05-06-26"
    assert dialog._widgets.status.currentText() == "Active"
    assert dialog._widgets.context.toPlainText() == "ctx"
    assert dialog._widgets.consequences.toPlainText() == "csq"
    assert dialog._widgets.supersedes.text() == ""
    assert dialog._widgets.superseded_by.text() == ""


def test_identifier_is_read_only(qtbot):
    dialog = DecisionEditDialog(MagicMock(), _record())
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.isReadOnly() is True


def test_no_changes_skips_api_and_accepts(qtbot):
    client = MagicMock()
    dialog = DecisionEditDialog(client, _record())
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    client.update_decision.assert_not_called()


def test_single_field_change_sends_one_field_patch(qtbot):
    client = MagicMock()
    client.update_decision.return_value = {"identifier": "DEC-007", "title": "new"}
    dialog = DecisionEditDialog(client, _record())
    qtbot.addWidget(dialog)

    dialog._widgets.title.setText("new title")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    args, kwargs = client.update_decision.call_args
    assert args[0] == "DEC-007"
    body = args[1]
    assert body == {"title": "new title"}


def test_clearing_supersedes_sends_empty_string(qtbot):
    client = MagicMock()
    client.update_decision.return_value = {"identifier": "DEC-007"}
    record = _record()
    record["supersedes_identifier"] = "DEC-005"
    dialog = DecisionEditDialog(client, record)
    qtbot.addWidget(dialog)

    assert dialog._widgets.supersedes.text() == "DEC-005"
    dialog._widgets.supersedes.setText("")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    body = client.update_decision.call_args[0][1]
    assert body == {"supersedes": ""}


def test_setting_supersedes_from_empty_sends_new_value(qtbot):
    client = MagicMock()
    client.update_decision.return_value = {"identifier": "DEC-007"}
    dialog = DecisionEditDialog(client, _record())
    qtbot.addWidget(dialog)

    dialog._widgets.supersedes.setText("DEC-007")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    body = client.update_decision.call_args[0][1]
    assert body == {"supersedes": "DEC-007"}


def test_not_found_shows_dialog_and_accepts(qtbot, monkeypatch):
    captured: dict[str, Any] = {}

    class _Recorder(ErrorDialog):
        def exec(self):  # noqa: A003
            captured["exec_called"] = True
            return 1

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog", _Recorder
    )

    client = MagicMock()
    client.update_decision.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = DecisionEditDialog(client, _record())
    qtbot.addWidget(dialog)
    dialog._widgets.title.setText("changed")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured.get("exec_called") is True


def test_validation_error_handled_inline(qtbot):
    client = MagicMock()
    client.update_decision.side_effect = ValidationError(
        errors=[
            {
                "code": "validation_error",
                "field": "decision_date",
                "message": "bad format",
            }
        ],
        message="Validation failed",
    )
    dialog = DecisionEditDialog(client, _record())
    qtbot.addWidget(dialog)
    # Use a valid-format date so client-side validation passes and the
    # mock's server-side ValidationError is the one surfaced.
    dialog._widgets.decision_date.set_date("05-09-26")

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["decision_date"].text() != "",
        timeout=2000,
    )
    assert dialog._widgets.error_labels["decision_date"].text() == "bad format"
    assert dialog.result() == 0


# test_invalid_decision_date_format_blocks_submission removed in v0.2:
# the calendar widget (DateField, per DEC-026) makes the invalid-format
# input path unreachable; the widget enforces format by construction.


def test_invalid_supersedes_format_blocks_submission(qtbot):
    client = MagicMock()
    dialog = DecisionEditDialog(client, _record())
    qtbot.addWidget(dialog)
    dialog._widgets.supersedes.setText("not-an-id")

    dialog._on_save_clicked()
    assert client.update_decision.call_count == 0
    err = dialog._widgets.error_labels["supersedes"].text()
    assert "DEC-NNN" in err
    assert dialog.result() == 0


def test_empty_supersedes_passes_format_check(qtbot):
    """Empty string is the documented way to clear the FK."""
    client = MagicMock()
    client.update_decision.return_value = {"identifier": "DEC-007"}
    record = _record()
    record["supersedes_identifier"] = "DEC-005"
    dialog = DecisionEditDialog(client, record)
    qtbot.addWidget(dialog)
    dialog._widgets.supersedes.setText("")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    body = client.update_decision.call_args[0][1]
    assert body == {"supersedes": ""}
