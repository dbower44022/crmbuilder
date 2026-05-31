"""Tests for the Session create/edit/delete dialogs (PI-073 / DEC-314 redesign).

Sessions are the medium-agnostic communication container. The dialog is
now schema-driven on ``EntityCrudDialog`` (DEC-028) rather than the old
bespoke v0.3 slice D implementation. Required fields per ``session-v2.md``
§3.2: ``session_title``, ``session_description``, ``session_executive_summary``
(200-800 chars, PI-075/PI-102), ``session_medium`` (vocab), and
``session_status`` (vocab). The create dialog prepends a required
workstream-membership selector; the identifier is server-assigned via
``client.next_session_identifier()`` and attached to the create body
alongside the ``session_belongs_to_project`` reference edge.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.access.vocab import SESSION_MEDIUMS, SESSION_STATUSES
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.session_create import (
    SessionCreateDialog,
    SessionDeleteDialog,
    SessionEditDialog,
)
from crmbuilder_v2.ui.exceptions import ConflictError, NotFoundError, ValidationError
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit

# A valid 200-800 character executive summary reused across the suite.
_VALID_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)

# Field key order from the create schema — workstream selector is inserted
# as row 0 by the dialog and is not part of the FieldSchema list.
_EXPECTED_FIELD_ORDER = [
    "session_title",
    "session_description",
    "session_executive_summary",
    "session_medium",
    "session_status",
    "session_notes",
]


def _stub_client(
    *,
    next_identifier: str = "SES-009",
    workstreams: list[dict] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.next_session_identifier.return_value = next_identifier
    client.list_projects.return_value = list(
        workstreams
        if workstreams is not None
        else [{"project_identifier": "PRJ-001", "project_name": "Schema"}]
    )
    return client


def _select_workstream(dialog: SessionCreateDialog, identifier: str = "PRJ-001") -> None:
    combo = dialog._workstream_combo
    for index in range(combo.count()):
        if combo.itemData(index) == identifier:
            combo.setCurrentIndex(index)
            return
    raise AssertionError(f"workstream {identifier} not in combo")


def _fill_required(dialog: SessionCreateDialog) -> None:
    """Fill every required field with valid values.

    ``session_medium`` defaults to ``chat`` and ``session_status`` defaults
    to ``planned`` via the schema; the title, description, and executive
    summary are explicitly populated so required-field and length
    validation pass. A workstream is selected so the create body builds.
    """
    dialog._widgets.session_title.setText("Title")
    dialog._widgets.session_description.setPlainText("Description body")
    dialog._widgets.session_executive_summary.setPlainText(_VALID_EXEC_SUMMARY)
    _select_workstream(dialog)


# ---------------------------------------------------------------------------
# Dialog construction / schema
# ---------------------------------------------------------------------------


def test_dialog_has_expected_fields_in_correct_order(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    keys = [schema.key for schema in dialog._fields]
    assert keys == _EXPECTED_FIELD_ORDER


def test_dialog_widget_kinds_match_schema(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    assert isinstance(dialog._widgets.session_title, QLineEdit)
    assert isinstance(dialog._widgets.session_description, QPlainTextEdit)
    assert isinstance(
        dialog._widgets.session_executive_summary, QPlainTextEdit
    )
    assert isinstance(dialog._widgets.session_medium, QComboBox)
    assert isinstance(dialog._widgets.session_status, QComboBox)
    assert isinstance(dialog._widgets.session_notes, QPlainTextEdit)


def test_create_mode_has_no_identifier_field(qtbot):
    # In create mode the identifier is server-assigned; the schema omits it.
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    assert "session_identifier" not in dialog._widgets


def test_workstream_selector_present_with_options(qtbot):
    client = _stub_client(
        workstreams=[
            {"project_identifier": "PRJ-001", "project_name": "Schema"},
            {"project_identifier": "PRJ-002", "project_name": "Other"},
        ]
    )
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    values = [
        dialog._workstream_combo.itemData(i)
        for i in range(dialog._workstream_combo.count())
    ]
    # The placeholder (None) plus the two workstreams.
    assert values == [None, "PRJ-001", "PRJ-002"]


def test_medium_combo_bound_to_session_mediums_vocab(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    items = [
        dialog._widgets.session_medium.itemText(i)
        for i in range(dialog._widgets.session_medium.count())
    ]
    assert items == sorted(SESSION_MEDIUMS)
    assert dialog._widgets.session_medium.currentText() == "chat"


def test_status_combo_bound_to_session_statuses_vocab(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    items = [
        dialog._widgets.session_status.itemText(i)
        for i in range(dialog._widgets.session_status.count())
    ]
    # The status field is transition-aware (compute_options=status_choices):
    # from the default "planned" the offered choices are "planned" plus its
    # legal transitions, which excludes "complete". Every offered value is a
    # member of the SESSION_STATUSES vocab.
    assert set(items) <= set(SESSION_STATUSES)
    assert items == sorted(
        {"planned", "in_flight", "cancelled", "not_started", "superseded"}
    )
    assert dialog._widgets.session_status.currentText() == "planned"


# ---------------------------------------------------------------------------
# Save flow
# ---------------------------------------------------------------------------


def test_required_fields_block_save_with_inline_error(qtbot):
    client = _stub_client()
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    # Title, description, and executive_summary are required-empty at
    # construction; medium and status carry schema defaults.

    dialog._on_save_clicked()

    client.create_session.assert_not_called()
    for f_key in (
        "session_title",
        "session_description",
        "session_executive_summary",
    ):
        label = dialog._widgets.error_labels[f_key]
        assert label.text() == "This field is required."


def test_short_executive_summary_blocks_save(qtbot):
    client = _stub_client()
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    dialog._widgets.session_title.setText("Title")
    dialog._widgets.session_description.setPlainText("Description body")
    dialog._widgets.session_executive_summary.setPlainText("too short")
    _select_workstream(dialog)

    dialog._on_save_clicked()

    client.create_session.assert_not_called()
    err = dialog._widgets.error_labels["session_executive_summary"].text()
    assert "200-800 characters" in err


def test_missing_workstream_blocks_save(qtbot):
    client = _stub_client()
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    dialog._widgets.session_title.setText("Title")
    dialog._widgets.session_description.setPlainText("Description body")
    dialog._widgets.session_executive_summary.setPlainText(_VALID_EXEC_SUMMARY)
    # Leave the workstream combo on its placeholder (None).

    dialog._on_save_clicked()

    client.create_session.assert_not_called()
    assert (
        dialog._widgets.error_labels["session_title"].text()
        == "Select a workstream for this session."
    )


def test_session_notes_optional(qtbot):
    client = _stub_client()
    client.create_session.return_value = {
        "session_identifier": "SES-009",
        "session_title": "Title",
    }
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)
    # Leave session_notes empty.
    assert dialog._widgets.session_notes.toPlainText() == ""

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    client.create_session.assert_called_once()
    body = client.create_session.call_args[0][0]
    assert body["session_notes"] == ""


def test_save_calls_client_with_all_field_values(qtbot):
    client = _stub_client(next_identifier="SES-009")
    client.create_session.return_value = {
        "session_identifier": "SES-009",
        "session_title": "Title",
    }
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)
    dialog._widgets.session_notes.setPlainText("Some pending work")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    body = client.create_session.call_args[0][0]
    # Identifier is server-assigned via next_session_identifier and attached.
    assert body["session_identifier"] == "SES-009"
    assert body["session_title"] == "Title"
    assert body["session_description"] == "Description body"
    assert body["session_executive_summary"] == _VALID_EXEC_SUMMARY
    assert body["session_medium"] == "chat"
    assert body["session_status"] == "planned"
    assert body["session_notes"] == "Some pending work"
    # The workstream-membership edge is attached to the create body.
    assert body["references"] == [
        {
            "source_type": "session",
            "source_id": "SES-009",
            "target_type": "project",
            "target_id": "PRJ-001",
            "relationship": "session_belongs_to_project",
        }
    ]


def test_save_uses_server_assigned_identifier(qtbot):
    client = _stub_client(next_identifier="SES-042")
    client.create_session.return_value = {
        "session_identifier": "SES-042",
        "session_title": "Title",
    }
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    client.next_session_identifier.assert_called_once()
    body = client.create_session.call_args[0][0]
    assert body["session_identifier"] == "SES-042"
    assert dialog.created_identifier() == "SES-042"


def test_save_handles_validation_error_envelope(qtbot):
    client = _stub_client()
    client.create_session.side_effect = ValidationError(
        errors=[
            {
                "code": "validation_error",
                "field": "session_description",
                "message": "Description too short",
            }
        ],
        message="Validation failed",
    )
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["session_description"].text()
        != "",
        timeout=2000,
    )
    assert (
        dialog._widgets.error_labels["session_description"].text()
        == "Description too short"
    )
    assert dialog.result() == 0


def test_save_conflict_routes_to_error_dialog(qtbot, monkeypatch):
    """The create schema has no identifier field, so a 409 falls back to
    the generic ErrorDialog rather than an inline identifier error."""
    client = _stub_client()
    client.create_session.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "exists"}],
        message="exists",
    )

    captured: dict[str, Any] = {}

    class _StubErrorDialog:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def exec(self):  # noqa: A003 — match Qt API
            captured["exec"] = True
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog", _StubErrorDialog
    )

    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(lambda: captured.get("exec") is True, timeout=2000)
    assert captured["title"] == "Could not save"


# ---------------------------------------------------------------------------
# SessionEditDialog
# ---------------------------------------------------------------------------


def _record() -> dict[str, Any]:
    return {
        "session_identifier": "SES-001",
        "session_title": "Kickoff chat",
        "session_description": "Description body",
        "session_executive_summary": _VALID_EXEC_SUMMARY,
        "session_medium": "chat",
        "session_status": "planned",
        "session_notes": "notes body",
    }


def test_edit_construct_pre_populates_from_record(qtbot):
    dialog = SessionEditDialog(_stub_client(), _record())
    qtbot.addWidget(dialog)
    assert dialog._widgets.session_identifier.text() == "SES-001"
    assert dialog._widgets.session_title.text() == "Kickoff chat"
    assert (
        dialog._widgets.session_description.toPlainText() == "Description body"
    )
    assert dialog._widgets.session_medium.currentText() == "chat"
    assert dialog._widgets.session_status.currentText() == "planned"
    assert dialog._widgets.session_notes.toPlainText() == "notes body"


def test_edit_identifier_is_read_only(qtbot):
    dialog = SessionEditDialog(_stub_client(), _record())
    qtbot.addWidget(dialog)
    assert dialog._widgets.session_identifier.isReadOnly() is True


def test_edit_single_field_change_sends_one_field_patch(qtbot):
    client = _stub_client()
    client.patch_session.return_value = {
        "session_identifier": "SES-001",
        "session_title": "new",
    }
    dialog = SessionEditDialog(client, _record())
    qtbot.addWidget(dialog)
    dialog._widgets.session_title.setText("new title")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    args, _kwargs = client.patch_session.call_args
    assert args[0] == "SES-001"
    assert args[1] == {"session_title": "new title"}


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
    client.patch_session.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = SessionEditDialog(client, _record())
    qtbot.addWidget(dialog)
    dialog._widgets.session_title.setText("changed")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured.get("exec_called") is True


# ---------------------------------------------------------------------------
# SessionDeleteDialog
# ---------------------------------------------------------------------------


def test_delete_construct_shows_identifier_and_title(qtbot):
    dialog = SessionDeleteDialog(_stub_client(), "SES-001", "Kickoff chat")
    qtbot.addWidget(dialog)
    text = dialog._body_label.text()
    assert "SES-001" in text
    assert "Kickoff chat" in text


def test_delete_requires_typed_identifier(qtbot):
    dialog = SessionDeleteDialog(_stub_client(), "SES-001", "Kickoff chat")
    qtbot.addWidget(dialog)
    # Delete is disabled until the identifier is typed back.
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("SES-001")
    assert dialog._delete_btn.isEnabled() is True


def test_delete_successful_accepts(qtbot):
    client = _stub_client()
    client.delete_session.return_value = {"session_identifier": "SES-001"}
    dialog = SessionDeleteDialog(client, "SES-001", "Kickoff chat")
    qtbot.addWidget(dialog)
    dialog._confirm_edit.setText("SES-001")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()

    client.delete_session.assert_called_once_with("SES-001")
