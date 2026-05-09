"""VersionedReplaceDialog (slice E) — JSON editor + save flow.

Replaces the slice-A skeleton test. Exercises:

* Pre-populated content renders pretty-printed.
* Initial Validate flags pre-populated content as valid.
* Editing to broken JSON is flagged invalid; editing back is valid.
* Save with invalid JSON does not call the save callback.
* Save with valid JSON calls the callback with the parsed dict.
* StorageConnectionError on save → dialog rejects.
* ValidationError on save → ErrorDialog opens, dialog stays open.
* ServerError on save → ErrorDialog opens, dialog stays open.
"""

from __future__ import annotations

import json
from typing import Any

from crmbuilder_v2.ui.base.versioned_replace_dialog import (
    VersionedReplaceDialog,
)
from crmbuilder_v2.ui.exceptions import (
    ServerError,
    StorageConnectionError,
    ValidationError,
)
from PySide6.QtWidgets import QDialog, QPlainTextEdit, QPushButton


def _editor(dialog: VersionedReplaceDialog) -> QPlainTextEdit:
    widget = dialog.findChild(QPlainTextEdit, "payload_editor")
    assert widget is not None
    return widget


def _validate_button(dialog: VersionedReplaceDialog) -> QPushButton:
    btn = dialog.findChild(QPushButton, "validate_button")
    assert btn is not None
    return btn


def _save_button(dialog: VersionedReplaceDialog) -> QPushButton:
    btn = dialog.findChild(QPushButton, "save_button")
    assert btn is not None
    return btn


def test_constructor_renders_pretty_printed_payload(qapp, qtbot):
    payload = {"scope": "v1", "items": [1, 2, 3]}
    dialog = VersionedReplaceDialog(
        payload, save_callback=lambda p: p, title="Test"
    )
    qtbot.addWidget(dialog)
    assert _editor(dialog).toPlainText() == json.dumps(payload, indent=2)


def test_initial_validation_marks_pre_populated_valid(qapp, qtbot):
    dialog = VersionedReplaceDialog(
        {"a": 1}, save_callback=lambda p: p, title="T"
    )
    qtbot.addWidget(dialog)
    assert dialog._validated_payload == {"a": 1}


def test_validate_invalid_json_clears_validation(qapp, qtbot):
    dialog = VersionedReplaceDialog(
        {"a": 1}, save_callback=lambda p: p, title="T"
    )
    qtbot.addWidget(dialog)
    _editor(dialog).setPlainText('{"a": 1')  # missing closing brace
    _validate_button(dialog).click()
    assert dialog._validated_payload is None


def test_validate_round_trip_valid_invalid_valid(qapp, qtbot):
    dialog = VersionedReplaceDialog(
        {"a": 1}, save_callback=lambda p: p, title="T"
    )
    qtbot.addWidget(dialog)
    # Valid → invalid → valid.
    _editor(dialog).setPlainText('{"a": 2}')
    _validate_button(dialog).click()
    assert dialog._validated_payload == {"a": 2}
    _editor(dialog).setPlainText('{"a": 2')
    _validate_button(dialog).click()
    assert dialog._validated_payload is None
    _editor(dialog).setPlainText('{"a": 3}')
    _validate_button(dialog).click()
    assert dialog._validated_payload == {"a": 3}


def test_validate_rejects_top_level_non_dict(qapp, qtbot):
    dialog = VersionedReplaceDialog(
        {"a": 1}, save_callback=lambda p: p, title="T"
    )
    qtbot.addWidget(dialog)
    _editor(dialog).setPlainText("[1, 2, 3]")
    _validate_button(dialog).click()
    assert dialog._validated_payload is None


def test_save_with_invalid_json_does_not_call_callback(qapp, qtbot):
    calls: list[Any] = []
    dialog = VersionedReplaceDialog(
        {"a": 1}, save_callback=lambda p: calls.append(p) or p, title="T"
    )
    qtbot.addWidget(dialog)
    _editor(dialog).setPlainText('{"oops"')
    _save_button(dialog).click()
    qapp.processEvents()
    assert calls == []
    # Dialog still open.
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_save_with_valid_json_calls_callback_with_parsed_dict(qapp, qtbot):
    calls: list[dict] = []

    def cb(payload):
        calls.append(payload)
        return {"version": 2, "is_current": True, "payload": payload}

    dialog = VersionedReplaceDialog(
        {"a": 1}, save_callback=cb, title="T"
    )
    qtbot.addWidget(dialog)
    _editor(dialog).setPlainText('{"a": 2, "b": "x"}')
    _save_button(dialog).click()
    qtbot.waitUntil(
        lambda: dialog.result() == QDialog.DialogCode.Accepted, timeout=2000
    )
    assert calls == [{"a": 2, "b": "x"}]


def test_save_storage_connection_error_rejects_dialog(qapp, qtbot):
    def cb(_payload):
        raise StorageConnectionError("boom")

    dialog = VersionedReplaceDialog({"a": 1}, save_callback=cb, title="T")
    qtbot.addWidget(dialog)
    _save_button(dialog).click()
    qtbot.waitUntil(
        lambda: dialog.result() == QDialog.DialogCode.Rejected, timeout=2000
    )


def test_save_validation_error_with_field_errors_renders_inline(
    qapp, qtbot, monkeypatch
):
    """Slice F polish item 10: per-field validation errors render inline
    below the editor instead of opening an ErrorDialog.
    """
    def cb(_payload):
        raise ValidationError(
            errors=[
                {"field": "scope", "message": "must be string"},
                {"field": "phase", "message": "unknown phase"},
            ],
            message="Validation failed",
        )

    error_dialogs: list[Any] = []

    class _StubError:
        def __init__(self, *a, **kw):
            error_dialogs.append((a, kw))

        def exec(self):  # noqa: A003
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.versioned_replace_dialog.ErrorDialog",
        _StubError,
    )

    dialog = VersionedReplaceDialog({"a": 1}, save_callback=cb, title="T")
    qtbot.addWidget(dialog)
    _save_button(dialog).click()
    qtbot.waitUntil(
        lambda: dialog._validated_payload is None
        and "scope" in dialog._validation_status.text(),
        timeout=2000,
    )
    # Dialog stays open. ErrorDialog is NOT used for field-level errors.
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert _save_button(dialog).isEnabled()
    assert error_dialogs == []
    # Both field errors are rendered.
    text = dialog._validation_status.text()
    assert "scope" in text
    assert "must be string" in text
    assert "phase" in text
    assert "unknown phase" in text


def test_save_validation_error_without_field_errors_falls_back_to_dialog(
    qapp, qtbot, monkeypatch
):
    """A ValidationError carrying no per-field details still opens the
    ErrorDialog fallback (e.g., a top-level message-only error envelope).
    """
    def cb(_payload):
        raise ValidationError(
            errors=[{"message": "schema mismatch"}],
            message="Validation failed",
        )

    error_dialogs: list[Any] = []

    class _StubError:
        def __init__(self, *a, **kw):
            error_dialogs.append((a, kw))

        def exec(self):  # noqa: A003
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.versioned_replace_dialog.ErrorDialog",
        _StubError,
    )

    dialog = VersionedReplaceDialog({"a": 1}, save_callback=cb, title="T")
    qtbot.addWidget(dialog)
    _save_button(dialog).click()
    qtbot.waitUntil(lambda: len(error_dialogs) == 1, timeout=2000)
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert _save_button(dialog).isEnabled()


def test_save_server_error_keeps_dialog_open(qapp, qtbot, monkeypatch):
    def cb(_payload):
        raise ServerError(status_code=500, errors=[], message="server boom")

    error_dialogs: list[Any] = []

    class _StubError:
        def __init__(self, *a, **kw):
            error_dialogs.append((a, kw))

        def exec(self):  # noqa: A003
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.versioned_replace_dialog.ErrorDialog",
        _StubError,
    )

    dialog = VersionedReplaceDialog({"a": 1}, save_callback=cb, title="T")
    qtbot.addWidget(dialog)
    _save_button(dialog).click()
    qtbot.waitUntil(lambda: len(error_dialogs) == 1, timeout=2000)
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert _save_button(dialog).isEnabled()
