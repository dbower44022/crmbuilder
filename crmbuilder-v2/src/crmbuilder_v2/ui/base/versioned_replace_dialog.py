"""VersionedReplaceDialog — JSON payload editor for versioned-replace
entities (charter, status). Per ui-PRD-v0.2.md §4.5 and DEC-029.

The dialog is intentionally schema-blind: it presents the current
payload as pretty-printed JSON in a monospace editor, validates that
the editor text is JSON-parseable (and a top-level object), and submits
the parsed dict via a save callback. Charter and Status share the
dialog framework with different save callbacks.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
    ValidationError,
)
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.base.versioned_replace_dialog")

_DEFAULT_DIALOG_WIDTH = 800
_DEFAULT_DIALOG_HEIGHT = 700


class VersionedReplaceDialog(QDialog):
    """Modal JSON editor for replacing a versioned entity's payload.

    Construction parameters:

    * ``current_payload`` — the dict pre-populated as pretty-printed JSON.
    * ``save_callback`` — invoked on Save (through a worker thread) with
      the parsed payload dict; should return the created version record.
    * ``title`` — window title and header text.
    * ``parent`` — optional parent widget.

    Layout:

    * Header label.
    * Monospace ``QPlainTextEdit`` showing the payload.
    * Validate button + status label.
    * Save / Cancel button bar.

    Validate parses the editor text as JSON. Valid → status label shows
    "Valid JSON"; invalid → status label shows "Invalid JSON: <error>"
    and Save is blocked until the editor is fixed and re-validated.

    Save runs Validate first; if valid, calls ``save_callback`` through
    a worker. On success → ``accept()``. On
    ``StorageConnectionError`` → ``reject()`` (the main window's crash
    banner takes over). ``ValidationError`` → ``ErrorDialog`` with the
    API's error envelope detail; the dialog stays open so the user can
    fix the payload. Other ``StorageClientError`` → ``ErrorDialog``;
    the dialog stays open.
    """

    def __init__(
        self,
        current_payload: dict,
        save_callback: Callable[[dict], dict],
        *,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(_DEFAULT_DIALOG_WIDTH, _DEFAULT_DIALOG_HEIGHT)
        self._save_callback = save_callback
        self._title = title
        self._validated_payload: dict | None = None
        self._in_flight_workers: list[object] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        header = QLabel(title)
        header_font = QFont(header.font())
        header_font.setBold(True)
        header_font.setPointSize(header_font.pointSize() + 1)
        header.setFont(header_font)
        outer.addWidget(header)

        self._editor = QPlainTextEdit()
        self._editor.setObjectName("payload_editor")
        editor_font = QFont("Monaco")
        editor_font.setStyleHint(QFont.StyleHint.Monospace)
        editor_font.setPointSize(10)
        self._editor.setFont(editor_font)
        self._editor.setPlainText(
            json.dumps(current_payload, indent=2, sort_keys=False)
        )
        outer.addWidget(self._editor, stretch=1)

        validate_row = QHBoxLayout()
        validate_row.setContentsMargins(0, 0, 0, 0)
        validate_row.setSpacing(8)
        self._validate_btn = QPushButton("Validate")
        self._validate_btn.setObjectName("validate_button")
        self._validate_btn.clicked.connect(self._on_validate)
        validate_row.addWidget(self._validate_btn)
        self._validation_status = QLabel("")
        self._validation_status.setObjectName("validation_status")
        self._validation_status.setTextFormat(Qt.TextFormat.RichText)
        self._validation_status.setWordWrap(True)
        validate_row.addWidget(self._validation_status, 1)
        outer.addLayout(validate_row)

        self._editor.textChanged.connect(self._invalidate_prior_validation)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._save_btn = button_box.button(QDialogButtonBox.StandardButton.Save)
        self._save_btn.setObjectName("save_button")
        self._save_btn.clicked.connect(self._on_save)
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setObjectName("cancel_button")
        button_box.rejected.connect(self.reject)
        outer.addWidget(button_box)

        # Initial validation of the pre-populated content.
        self._on_validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _on_validate(self) -> None:
        text = self._editor.toPlainText()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            self._set_status_invalid(
                f"Invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}"
            )
            return
        if not isinstance(parsed, dict):
            self._set_status_invalid(
                "Top-level value must be an object (dict)."
            )
            return
        self._set_status_valid("Valid JSON.")
        self._validated_payload = parsed

    def _invalidate_prior_validation(self) -> None:
        if self._validated_payload is None:
            return
        self._validated_payload = None
        self._validation_status.setText(
            "<span style='color: gray;'>(modified — re-validate before saving)</span>"
        )

    def _set_status_invalid(self, message: str) -> None:
        self._validation_status.setText(
            f"<span style='color: #B22222;'>{message}</span>"
        )
        self._validated_payload = None

    def _set_status_valid(self, message: str) -> None:
        self._validation_status.setText(
            f"<span style='color: #1F3864;'>{message}</span>"
        )

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        # Always re-validate at submit time; user may have edited since
        # the last Validate click.
        self._on_validate()
        if self._validated_payload is None:
            return
        payload = self._validated_payload
        self._save_btn.setEnabled(False)
        worker = run_in_thread(
            lambda: self._save_callback(payload),
            on_success=self._on_save_success,
            on_error=self._on_save_error,
            parent=self,
        )
        self._in_flight_workers.append(worker)

    def _on_save_success(self, _result: object) -> None:
        self.accept()

    def _on_save_error(self, exc: BaseException) -> None:
        self._save_btn.setEnabled(True)
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost saving versioned replace: %s", exc)
            self.reject()
            return
        if isinstance(exc, ValidationError):
            ErrorDialog(
                "Invalid payload",
                "The payload was rejected by the server.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error saving versioned replace: %s", exc)
            ErrorDialog(
                "Could not save",
                "An error occurred while saving the new version.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        _log.exception("Unexpected error saving versioned replace", exc_info=exc)
        ErrorDialog(
            "Unexpected error",
            "An unexpected error occurred.",
            detail=repr(exc),
            parent=self,
        ).exec()

    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        for worker in list(self._in_flight_workers):
            try:
                worker.wait(2000)
            except Exception:
                _log.exception("Worker.wait failed during dialog teardown")
        super().closeEvent(event)
