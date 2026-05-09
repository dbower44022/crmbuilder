"""Tests for the Planning Item create/edit/delete dialogs (v0.2 slice C)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.access.vocab import (
    PLANNING_ITEM_STATUSES,
    PLANNING_ITEM_TYPES,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.planning_item_create import PlanningItemCreateDialog
from crmbuilder_v2.ui.dialogs.planning_item_delete import PlanningItemDeleteDialog
from crmbuilder_v2.ui.dialogs.planning_item_edit import PlanningItemEditDialog
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
        "identifier": "PI-001",
        "title": "Pacing dimension",
        "description": "desc",
        "item_type": "planning_dimension",
        "status": "Open",
        "resolution_reference": "DEC-027",
    }


def _fill_required(dialog: PlanningItemCreateDialog) -> None:
    dialog._widgets.identifier.setText("PI-001")
    dialog._widgets.title.setText("Pacing dimension")
    # item_type has no default; pick the first item.
    dialog._widgets.item_type.setCurrentIndex(0)
    # status defaults to Open via the schema.


# ---------------------------------------------------------------------------
# PlanningItemCreateDialog
# ---------------------------------------------------------------------------


def test_construct_has_all_six_fields(qtbot):
    dialog = PlanningItemCreateDialog(_stub_client())
    qtbot.addWidget(dialog)

    assert isinstance(dialog._widgets.identifier, QLineEdit)
    assert isinstance(dialog._widgets.title, QLineEdit)
    assert isinstance(dialog._widgets.description, QPlainTextEdit)
    assert isinstance(dialog._widgets.item_type, QComboBox)
    assert isinstance(dialog._widgets.status, QComboBox)
    assert isinstance(dialog._widgets.resolution_reference, QLineEdit)
    assert dialog._save_btn is not None
    assert dialog._cancel_btn is not None


def test_combo_widgets_bound_to_correct_vocab(qtbot):
    dialog = PlanningItemCreateDialog(_stub_client())
    qtbot.addWidget(dialog)

    type_items = [
        dialog._widgets.item_type.itemText(i)
        for i in range(dialog._widgets.item_type.count())
    ]
    status_items = [
        dialog._widgets.status.itemText(i)
        for i in range(dialog._widgets.status.count())
    ]
    assert type_items == sorted(PLANNING_ITEM_TYPES)
    assert status_items == sorted(PLANNING_ITEM_STATUSES)
    assert dialog._widgets.status.currentText() == "Open"


def test_required_fields_block_submission(qtbot):
    client = _stub_client()
    dialog = PlanningItemCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._on_save_clicked()

    client.create_planning_item.assert_not_called()
    for field in ("identifier", "title"):
        label = dialog._widgets.error_labels[field]
        assert label.text() == "This field is required."


def test_invalid_identifier_format_blocks_submission(qtbot):
    client = _stub_client()
    dialog = PlanningItemCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._widgets.identifier.setText("abc")
    dialog._widgets.title.setText("title")

    dialog._on_save_clicked()

    assert client.create_planning_item.call_count == 0
    err = dialog._widgets.error_labels["identifier"].text()
    assert "PI-NNN" in err
    assert dialog.result() == 0


def test_successful_create_accepts_with_identifier(qtbot):
    client = _stub_client()
    client.create_planning_item.return_value = {
        "identifier": "PI-001",
        "title": "Pacing dimension",
    }
    dialog = PlanningItemCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    assert dialog.created_identifier() == "PI-001"
    args, _kwargs = client.create_planning_item.call_args
    body = args[0]
    assert body["identifier"] == "PI-001"
    assert body["title"] == "Pacing dimension"
    assert body["status"] == "Open"
    assert "item_type" in body
    # Empty resolution_reference is omitted on create.
    assert "resolution_reference" not in body


def test_validation_error_shows_inline(qtbot):
    client = _stub_client()
    client.create_planning_item.side_effect = ValidationError(
        errors=[
            {
                "code": "validation_error",
                "field": "item_type",
                "message": "Invalid type",
            }
        ],
        message="Validation failed",
    )
    dialog = PlanningItemCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["item_type"].text() != "",
        timeout=2000,
    )
    assert dialog._widgets.error_labels["item_type"].text() == "Invalid type"
    assert dialog.result() == 0


def test_conflict_error_shows_inline_on_identifier(qtbot):
    client = _stub_client()
    client.create_planning_item.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "exists"}],
        message="exists",
    )
    dialog = PlanningItemCreateDialog(client)
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
# PlanningItemEditDialog
# ---------------------------------------------------------------------------


def test_edit_construct_pre_populates_from_record(qtbot):
    dialog = PlanningItemEditDialog(_stub_client(), _record())
    qtbot.addWidget(dialog)

    assert dialog._widgets.identifier.text() == "PI-001"
    assert dialog._widgets.title.text() == "Pacing dimension"
    assert dialog._widgets.description.toPlainText() == "desc"
    assert dialog._widgets.item_type.currentText() == "planning_dimension"
    assert dialog._widgets.status.currentText() == "Open"
    assert dialog._widgets.resolution_reference.text() == "DEC-027"


def test_edit_identifier_is_read_only(qtbot):
    dialog = PlanningItemEditDialog(_stub_client(), _record())
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.isReadOnly() is True


def test_edit_no_changes_skips_api_and_accepts(qtbot):
    client = _stub_client()
    dialog = PlanningItemEditDialog(client, _record())
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    client.update_planning_item.assert_not_called()


def test_edit_single_field_change_sends_one_field_patch(qtbot):
    client = _stub_client()
    client.update_planning_item.return_value = {
        "identifier": "PI-001",
        "title": "new",
    }
    dialog = PlanningItemEditDialog(client, _record())
    qtbot.addWidget(dialog)

    dialog._widgets.title.setText("new title")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    args, _kwargs = client.update_planning_item.call_args
    assert args[0] == "PI-001"
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
    client.update_planning_item.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = PlanningItemEditDialog(client, _record())
    qtbot.addWidget(dialog)
    dialog._widgets.title.setText("changed")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured.get("exec_called") is True


# ---------------------------------------------------------------------------
# PlanningItemDeleteDialog
# ---------------------------------------------------------------------------


def test_delete_construct_shows_identifier_and_title(qtbot):
    dialog = PlanningItemDeleteDialog(_stub_client(), "PI-001", "Pacing dimension")
    qtbot.addWidget(dialog)
    text = dialog._body_label.text()
    assert "PI-001" in text
    assert "Pacing dimension" in text
    assert "cannot be undone" in text


def test_delete_successful_accepts(qtbot):
    client = _stub_client()
    client.delete_planning_item.return_value = {"identifier": "PI-001"}
    dialog = PlanningItemDeleteDialog(client, "PI-001", "Pacing dimension")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()

    client.delete_planning_item.assert_called_once_with("PI-001")


def test_delete_conflict_routes_to_error_dialog(qtbot, monkeypatch):
    """If a 409 surfaces (e.g., planning item is referenced), the dialog
    falls back to the generic ErrorDialog and the body is unchanged."""
    client = _stub_client()
    client.delete_planning_item.side_effect = ConflictError(
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

    dialog = PlanningItemDeleteDialog(client, "PI-001", "Pacing dimension")
    qtbot.addWidget(dialog)
    dialog._on_delete_clicked()
    qtbot.waitUntil(lambda: "title" in captured, timeout=2000)

    assert captured["title"] == "Could not delete planning item"
    assert "cannot be undone" in dialog._body_label.text()
    assert dialog._delete_btn.isHidden() is False
    assert dialog._delete_btn.isEnabled() is True


def test_delete_not_found_treated_as_success(qtbot):
    client = _stub_client()
    client.delete_planning_item.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = PlanningItemDeleteDialog(client, "PI-001", "title")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()
