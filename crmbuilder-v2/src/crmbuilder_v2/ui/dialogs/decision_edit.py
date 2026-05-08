"""Decision edit dialog.

Wired in slice G. Same shape as the create dialog, pre-populated; the
identifier field is read-only. See PRD section 4.8.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._decision_form import (
    LONG_TEXT_FIELDS,
    build_decision_form,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
    ValidationError,
)
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.decision_edit")

_TEXT_FIELDS_FROM_RECORD = (
    "title",
    "decision_date",
    "status",
    *(field for field, _ in LONG_TEXT_FIELDS),
)


class DecisionEditDialog(QDialog):
    """Modal edit-decision dialog. Per PRD §4.8."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._record = record
        self._identifier = str(record.get("identifier") or "")
        self._initial: dict[str, str] = {}
        self._worker = None

        self.setWindowTitle(
            f"Edit {self._identifier}" if self._identifier else "Edit decision"
        )
        self.setModal(True)
        self.setMinimumWidth(560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        form, widgets = build_decision_form(self)
        self._form = form
        self._widgets = widgets
        outer.addLayout(form)

        # Identifier is read-only; pre-populate.
        self._widgets.identifier.setText(self._identifier)
        self._widgets.identifier.setReadOnly(True)
        self._widgets.identifier.setStyleSheet("color: #666; background: #f4f4f4;")

        self._populate_from_record(record)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save_clicked)
        button_row.addWidget(self._save_btn)
        outer.addLayout(button_row)

        self._widgets.title.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------------------------------
    # Pre-population
    # ------------------------------------------------------------------

    def _populate_from_record(self, record: dict[str, Any]) -> None:
        for field in _TEXT_FIELDS_FROM_RECORD:
            value = record.get(field)
            value = "" if value is None else str(value)
            self._widgets.set_value(field, value)
            self._initial[field] = value

        # supersedes / superseded_by come in via *_identifier on the
        # enriched record dict.
        supersedes = record.get("supersedes_identifier") or ""
        superseded_by = record.get("superseded_by_identifier") or ""
        self._widgets.set_value("supersedes", supersedes)
        self._widgets.set_value("superseded_by", superseded_by)
        self._initial["supersedes"] = supersedes
        self._initial["superseded_by"] = superseded_by

    # ------------------------------------------------------------------
    # Save flow
    # ------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        self._widgets.clear_all_errors()
        if not self._validate_required():
            return

        diff = self._compute_diff()
        if not diff:
            self.accept()
            return

        self._save_btn.setEnabled(False)
        self._worker = run_in_thread(
            lambda: self._client.update_decision(self._identifier, diff),
            on_success=self._on_update_success,
            on_error=self._on_update_error,
            parent=self,
        )

    def _validate_required(self) -> bool:
        ok = True
        for field in ("title", "decision_date", "status"):
            value = self._widgets.value_for(field).strip()
            if not value:
                self._widgets.show_error(field, "This field is required.")
                ok = False
        return ok

    def _compute_diff(self) -> dict[str, Any]:
        """Return only the fields whose values differ from the initial snapshot."""
        diff: dict[str, Any] = {}
        for field in _TEXT_FIELDS_FROM_RECORD:
            current = self._widgets.value_for(field)
            if current != self._initial.get(field, ""):
                diff[field] = current
        for field in ("supersedes", "superseded_by"):
            current = self._widgets.value_for(field).strip()
            if current != self._initial.get(field, ""):
                diff[field] = current
        return diff

    def _on_update_success(self, _result: Any) -> None:
        self._save_btn.setEnabled(True)
        self.accept()

    def _on_update_error(self, exc: Exception) -> None:
        self._save_btn.setEnabled(True)

        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during decision update: %s", exc)
            self.reject()
            return

        if isinstance(exc, NotFoundError):
            ErrorDialog(
                title="Decision not found",
                message=(
                    "This decision was deleted while the dialog was open. "
                    "The list will refresh."
                ),
                parent=self,
            ).exec()
            self.accept()
            return

        if isinstance(exc, ConflictError):
            # Most likely cause for edit: supersedes_id resolution.
            ErrorDialog(
                title="Could not save decision",
                message=exc.message or "Conflict",
                detail=repr(exc),
                parent=self,
            ).exec()
            return

        if isinstance(exc, ValidationError):
            field_errors = exc.field_errors()
            unmapped = []
            for field, message in field_errors.items():
                if field in self._widgets.error_labels:
                    self._widgets.show_error(field, message)
                else:
                    unmapped.append((field, message))
            if not field_errors or unmapped:
                msg = exc.message or "Validation failed."
                if unmapped:
                    detail = "\n".join(
                        f"{field}: {message}" for field, message in unmapped
                    )
                else:
                    detail = None
                ErrorDialog(
                    title="Could not save decision",
                    message=msg,
                    detail=detail,
                    parent=self,
                ).exec()
            return

        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during decision update: %s", exc)
            ErrorDialog(
                title="Could not save decision",
                message=exc.message or str(exc),
                detail=repr(exc),
                parent=self,
            ).exec()
            return

        _log.exception("Unexpected error during decision update", exc_info=exc)
        ErrorDialog(
            title="Could not save decision",
            message=str(exc) or exc.__class__.__name__,
            detail=repr(exc),
            parent=self,
        ).exec()
