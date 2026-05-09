"""Tests for the Risk create/edit/delete dialogs (v0.2 slice B)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.access.vocab import (
    RISK_IMPACTS,
    RISK_PROBABILITIES,
    RISK_STATUSES,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.risk_create import RiskCreateDialog
from crmbuilder_v2.ui.dialogs.risk_delete import RiskDeleteDialog
from crmbuilder_v2.ui.dialogs.risk_edit import RiskEditDialog
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit


def _stub_client() -> MagicMock:
    return MagicMock()


def _record() -> dict[str, Any]:
    return {
        "identifier": "RSK-001",
        "title": "Schema drift",
        "description": "desc",
        "probability": "Low",
        "impact": "Medium",
        "response_plan": "plan",
        "status": "Open",
    }


def _fill_required(dialog: RiskCreateDialog) -> None:
    dialog._widgets.identifier.setText("RSK-001")
    dialog._widgets.title.setText("Schema drift")
    # probability and impact have no default; pick the first item.
    dialog._widgets.probability.setCurrentIndex(0)
    dialog._widgets.impact.setCurrentIndex(0)
    # status defaults to Open via the schema.


# ---------------------------------------------------------------------------
# RiskCreateDialog
# ---------------------------------------------------------------------------


def test_construct_has_all_seven_fields(qtbot):
    dialog = RiskCreateDialog(_stub_client())
    qtbot.addWidget(dialog)

    assert isinstance(dialog._widgets.identifier, QLineEdit)
    assert isinstance(dialog._widgets.title, QLineEdit)
    assert isinstance(dialog._widgets.description, QPlainTextEdit)
    assert isinstance(dialog._widgets.probability, QComboBox)
    assert isinstance(dialog._widgets.impact, QComboBox)
    assert isinstance(dialog._widgets.status, QComboBox)
    assert isinstance(dialog._widgets.response_plan, QPlainTextEdit)
    assert dialog._save_btn is not None
    assert dialog._cancel_btn is not None


def test_combo_widgets_bound_to_correct_vocab(qtbot):
    dialog = RiskCreateDialog(_stub_client())
    qtbot.addWidget(dialog)

    probability_items = [
        dialog._widgets.probability.itemText(i)
        for i in range(dialog._widgets.probability.count())
    ]
    impact_items = [
        dialog._widgets.impact.itemText(i)
        for i in range(dialog._widgets.impact.count())
    ]
    status_items = [
        dialog._widgets.status.itemText(i)
        for i in range(dialog._widgets.status.count())
    ]
    assert probability_items == sorted(RISK_PROBABILITIES)
    assert impact_items == sorted(RISK_IMPACTS)
    assert status_items == sorted(RISK_STATUSES)
    assert dialog._widgets.status.currentText() == "Open"


def test_required_fields_block_submission(qtbot):
    client = _stub_client()
    dialog = RiskCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._on_save_clicked()

    client.create_risk.assert_not_called()
    for field in ("identifier", "title"):
        label = dialog._widgets.error_labels[field]
        assert label.text() == "This field is required."


def test_invalid_identifier_format_blocks_submission(qtbot):
    client = _stub_client()
    dialog = RiskCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._widgets.identifier.setText("abc")
    dialog._widgets.title.setText("title")

    dialog._on_save_clicked()

    assert client.create_risk.call_count == 0
    err = dialog._widgets.error_labels["identifier"].text()
    assert "RSK-NNN" in err
    assert dialog.result() == 0


def test_successful_create_accepts_with_identifier(qtbot):
    client = _stub_client()
    client.create_risk.return_value = {
        "identifier": "RSK-001",
        "title": "Schema drift",
    }
    dialog = RiskCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    assert dialog.created_identifier() == "RSK-001"
    args, _kwargs = client.create_risk.call_args
    body = args[0]
    assert body["identifier"] == "RSK-001"
    assert body["title"] == "Schema drift"
    assert body["status"] == "Open"
    assert "probability" in body
    assert "impact" in body


def test_validation_error_shows_inline(qtbot):
    client = _stub_client()
    client.create_risk.side_effect = ValidationError(
        errors=[
            {
                "code": "validation_error",
                "field": "probability",
                "message": "Invalid probability",
            }
        ],
        message="Validation failed",
    )
    dialog = RiskCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["probability"].text() != "",
        timeout=2000,
    )
    assert (
        dialog._widgets.error_labels["probability"].text()
        == "Invalid probability"
    )
    assert dialog.result() == 0


def test_conflict_error_shows_inline_on_identifier(qtbot):
    client = _stub_client()
    client.create_risk.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "exists"}],
        message="exists",
    )
    dialog = RiskCreateDialog(client)
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


# ---------------------------------------------------------------------------
# RiskEditDialog
# ---------------------------------------------------------------------------


def test_edit_construct_pre_populates_from_record(qtbot):
    dialog = RiskEditDialog(_stub_client(), _record())
    qtbot.addWidget(dialog)

    assert dialog._widgets.identifier.text() == "RSK-001"
    assert dialog._widgets.title.text() == "Schema drift"
    assert dialog._widgets.description.toPlainText() == "desc"
    assert dialog._widgets.probability.currentText() == "Low"
    assert dialog._widgets.impact.currentText() == "Medium"
    assert dialog._widgets.status.currentText() == "Open"
    assert dialog._widgets.response_plan.toPlainText() == "plan"


def test_edit_identifier_is_read_only(qtbot):
    dialog = RiskEditDialog(_stub_client(), _record())
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.isReadOnly() is True


def test_edit_no_changes_skips_api_and_accepts(qtbot):
    client = _stub_client()
    dialog = RiskEditDialog(client, _record())
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    client.update_risk.assert_not_called()


def test_edit_single_field_change_sends_one_field_patch(qtbot):
    client = _stub_client()
    client.update_risk.return_value = {"identifier": "RSK-001", "title": "new"}
    dialog = RiskEditDialog(client, _record())
    qtbot.addWidget(dialog)

    dialog._widgets.title.setText("new title")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    args, _kwargs = client.update_risk.call_args
    assert args[0] == "RSK-001"
    body = args[1]
    assert body == {"title": "new title"}


def test_edit_not_found_shows_dialog_and_accepts(qtbot, monkeypatch):
    captured: dict[str, Any] = {}

    class _Recorder(ErrorDialog):
        def exec(self):  # noqa: A003
            captured["exec_called"] = True
            return 1

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog", _Recorder
    )

    client = _stub_client()
    client.update_risk.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = RiskEditDialog(client, _record())
    qtbot.addWidget(dialog)
    dialog._widgets.title.setText("changed")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured.get("exec_called") is True


# ---------------------------------------------------------------------------
# RiskDeleteDialog
# ---------------------------------------------------------------------------


def test_delete_construct_shows_identifier_and_title(qtbot):
    dialog = RiskDeleteDialog(_stub_client(), "RSK-001", "Schema drift")
    qtbot.addWidget(dialog)
    text = dialog._body_label.text()
    assert "RSK-001" in text
    assert "Schema drift" in text
    assert "cannot be undone" in text


def test_delete_successful_accepts(qtbot):
    client = _stub_client()
    client.delete_risk.return_value = {"identifier": "RSK-001"}
    dialog = RiskDeleteDialog(client, "RSK-001", "Schema drift")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()

    client.delete_risk.assert_called_once_with("RSK-001")


def test_delete_conflict_routes_to_error_dialog(qtbot, monkeypatch):
    """If a 409 surfaces (e.g., risk is referenced), the dialog falls back
    to the generic ErrorDialog and the body is unchanged."""
    client = _stub_client()
    client.delete_risk.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "referenced by SES-006"}],
        message="referenced by SES-006",
    )

    captured: dict[str, Any] = {}

    class _StubErrorDialog:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def exec(self):
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog", _StubErrorDialog
    )

    dialog = RiskDeleteDialog(client, "RSK-001", "Schema drift")
    qtbot.addWidget(dialog)
    dialog._on_delete_clicked()
    qtbot.waitUntil(lambda: "title" in captured, timeout=2000)

    assert captured["title"] == "Could not delete risk"
    assert "cannot be undone" in dialog._body_label.text()
    assert dialog._delete_btn.isHidden() is False
    assert dialog._delete_btn.isEnabled() is True


def test_delete_not_found_treated_as_success(qtbot):
    client = _stub_client()
    client.delete_risk.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = RiskDeleteDialog(client, "RSK-001", "title")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()
