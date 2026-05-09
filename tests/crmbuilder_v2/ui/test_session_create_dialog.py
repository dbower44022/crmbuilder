"""Tests for ``SessionCreateDialog`` (v0.3 slice D — DEC-034)."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.access.vocab import SESSION_STATUSES
from crmbuilder_v2.ui.dialogs._session_schema import (
    SESSION_CONVERSATION_REF_PLACEHOLDER,
    SESSION_TOPICS_PLACEHOLDER,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.session_create import (
    SessionCreateDialog,
    compute_next_session_identifier,
)
from crmbuilder_v2.ui.exceptions import ConflictError, ValidationError
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit

# Field key order from PRD §2.4 — this ordering is the contract.
_EXPECTED_FIELD_ORDER = [
    "identifier",
    "session_date",
    "status",
    "title",
    "summary",
    "topics_covered",
    "artifacts_produced",
    "in_flight_at_end",
    "conversation_reference",
]


def _stub_client(sessions: list[dict] | None = None) -> MagicMock:
    client = MagicMock()
    client.list_sessions.return_value = list(sessions or [])
    return client


def _fill_required(dialog: SessionCreateDialog) -> None:
    """Fill every required field with non-empty values.

    The identifier is auto-assigned and read-only; ``session_date``
    defaults to today; ``status`` defaults to "Complete"; the long-text
    fields are explicitly populated so required-field validation passes.
    """
    dialog._widgets.title.setText("Title")
    dialog._widgets.summary.setPlainText("Summary body")
    dialog._widgets.topics_covered.setPlainText("Topics body")
    dialog._widgets.artifacts_produced.setPlainText("Artifacts body")
    dialog._widgets.conversation_reference.setPlainText(
        "Conversation reference body"
    )


# ---------------------------------------------------------------------------
# compute_next_session_identifier
# ---------------------------------------------------------------------------


def test_compute_next_identifier_increments_max():
    sessions = [
        {"identifier": "SES-008"},
        {"identifier": "SES-007"},
        {"identifier": "SES-001"},
    ]
    assert compute_next_session_identifier(sessions) == "SES-009"


def test_compute_next_identifier_empty_list_yields_001():
    assert compute_next_session_identifier([]) == "SES-001"


def test_compute_next_identifier_skips_invalid_records():
    sessions = [
        {"identifier": None},
        {},  # no identifier key at all
        {"identifier": "SES-bogus"},
        {"identifier": "OTHER-005"},
        {"identifier": "SES-002"},
    ]
    assert compute_next_session_identifier(sessions) == "SES-003"


# ---------------------------------------------------------------------------
# Dialog construction / schema
# ---------------------------------------------------------------------------


def test_dialog_has_nine_fields_in_correct_order(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    keys = [schema.key for schema in dialog._fields]
    assert keys == _EXPECTED_FIELD_ORDER


def test_dialog_widget_kinds_match_schema(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    assert isinstance(dialog._widgets.identifier, QLineEdit)
    assert isinstance(dialog._widgets.title, QLineEdit)
    assert isinstance(dialog._widgets.status, QComboBox)
    assert isinstance(dialog._widgets.summary, QPlainTextEdit)
    assert isinstance(dialog._widgets.topics_covered, QPlainTextEdit)
    assert isinstance(dialog._widgets.artifacts_produced, QPlainTextEdit)
    assert isinstance(dialog._widgets.in_flight_at_end, QPlainTextEdit)
    assert isinstance(
        dialog._widgets.conversation_reference, QPlainTextEdit
    )


def test_identifier_auto_assigned_from_latest_session(qtbot):
    client = _stub_client(
        [{"identifier": "SES-008"}, {"identifier": "SES-007"}]
    )
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.text() == "SES-009"


def test_identifier_skips_invalid_records_during_open(qtbot):
    client = _stub_client(
        [
            {"identifier": "SES-005"},
            {"identifier": "SES-bogus"},
            {"identifier": None},
        ]
    )
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.text() == "SES-006"


def test_identifier_is_read_only(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.isReadOnly() is True


def test_session_date_defaults_to_today(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    today_text = date.today().strftime("%m-%d-%y")
    assert dialog._widgets.session_date.date_text() == today_text


def test_status_defaults_to_Complete(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    assert dialog._widgets.status.currentText() == "Complete"


def test_status_combo_bound_to_session_statuses_vocab(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    items = [
        dialog._widgets.status.itemText(i)
        for i in range(dialog._widgets.status.count())
    ]
    assert items == sorted(SESSION_STATUSES)


def test_topics_covered_placeholder_present(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    assert (
        dialog._widgets.topics_covered.placeholderText()
        == SESSION_TOPICS_PLACEHOLDER
    )


def test_conversation_reference_placeholder_present(qtbot):
    dialog = SessionCreateDialog(_stub_client())
    qtbot.addWidget(dialog)
    assert (
        dialog._widgets.conversation_reference.placeholderText()
        == SESSION_CONVERSATION_REF_PLACEHOLDER
    )


# ---------------------------------------------------------------------------
# Save flow
# ---------------------------------------------------------------------------


def test_required_fields_block_save_with_inline_error(qtbot):
    client = _stub_client()
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    # All long-text fields and title are required-empty at construction
    # except identifier (auto), session_date (today), status (Complete).

    dialog._on_save_clicked()

    client.create_session.assert_not_called()
    for f_key in (
        "title",
        "summary",
        "topics_covered",
        "artifacts_produced",
        "conversation_reference",
    ):
        label = dialog._widgets.error_labels[f_key]
        assert label.text() == "This field is required."


def test_in_flight_at_end_optional(qtbot):
    client = _stub_client()
    client.create_session.return_value = {
        "identifier": "SES-001",
        "title": "Title",
    }
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)
    # Leave in_flight_at_end empty.
    assert dialog._widgets.in_flight_at_end.toPlainText() == ""

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    client.create_session.assert_called_once()
    body = client.create_session.call_args[0][0]
    assert body["in_flight_at_end"] == ""


def test_save_calls_client_with_all_field_values(qtbot):
    client = _stub_client([{"identifier": "SES-008"}])
    client.create_session.return_value = {
        "identifier": "SES-009",
        "title": "Title",
    }
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)
    dialog._widgets.in_flight_at_end.setPlainText("Some pending work")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    body = client.create_session.call_args[0][0]
    assert body["identifier"] == "SES-009"
    assert body["title"] == "Title"
    assert body["status"] == "Complete"
    assert body["session_date"] == date.today().strftime("%m-%d-%y")
    assert body["summary"] == "Summary body"
    assert body["topics_covered"] == "Topics body"
    assert body["artifacts_produced"] == "Artifacts body"
    assert body["in_flight_at_end"] == "Some pending work"
    assert body["conversation_reference"] == "Conversation reference body"


def test_save_handles_validation_error_envelope(qtbot):
    client = _stub_client()
    client.create_session.side_effect = ValidationError(
        errors=[
            {
                "code": "validation_error",
                "field": "summary",
                "message": "Summary too short",
            }
        ],
        message="Validation failed",
    )
    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["summary"].text() != "",
        timeout=2000,
    )
    assert (
        dialog._widgets.error_labels["summary"].text()
        == "Summary too short"
    )
    assert dialog.result() == 0


def test_save_handles_identifier_collision_retry(qtbot):
    """A 409 on first save → recompute identifier and retry once."""
    client = _stub_client()
    # First open: SES-008 is the latest, so dialog opens with SES-009.
    # Then another writer creates SES-009 (collision). On retry, the
    # client returns [SES-008, SES-009] so we propose SES-010.
    list_responses = [
        [{"identifier": "SES-008"}],
        [{"identifier": "SES-008"}, {"identifier": "SES-009"}],
    ]
    client.list_sessions.side_effect = lambda: list_responses.pop(0)

    create_responses: list[Any] = [
        ConflictError(
            errors=[{"code": "conflict", "message": "exists"}],
            message="exists",
        ),
        {"identifier": "SES-010", "title": "Title"},
    ]

    def fake_create(_body):
        result = create_responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    client.create_session.side_effect = fake_create

    dialog = SessionCreateDialog(client)
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.text() == "SES-009"

    _fill_required(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    # Two POSTs: first 409, second 201.
    assert client.create_session.call_count == 2
    # Second call was made with the recomputed identifier.
    second_body = client.create_session.call_args_list[1][0][0]
    assert second_body["identifier"] == "SES-010"
    # Dialog ends up showing the new identifier.
    assert dialog._widgets.identifier.text() == "SES-010"
    assert dialog.created_identifier() == "SES-010"


def test_save_repeated_collision_after_retry_shows_inline_error(
    qtbot, monkeypatch
):
    """If the retry also collides, fall back to the base inline error."""
    client = _stub_client([{"identifier": "SES-008"}])
    client.create_session.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "exists"}],
        message="exists",
    )

    captured: dict[str, Any] = {}

    class _StubErrorDialog(ErrorDialog):
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
    qtbot.waitUntil(
        lambda: client.create_session.call_count == 2, timeout=2000
    )
    # Second 409 -> inline identifier error from the base class.
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["identifier"].text() != "",
        timeout=2000,
    )
    assert (
        dialog._widgets.error_labels["identifier"].text()
        == "An identifier with this value already exists."
    )
