"""Decision create dialog.

Wired in slice G. See PRD section 4.7 for the input layout and save
behavior, including the inline-error mapping for HTTP 400 / 409.
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
    DECISION_DATE_HINT,
    DECISION_DATE_RE,
    IDENTIFIER_HINT,
    IDENTIFIER_RE,
    SUPERSEDES_HINT,
    SUPERSEDES_RE,
    build_decision_form,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    StorageClientError,
    StorageConnectionError,
    ValidationError,
)
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.decision_create")

_REQUIRED_FIELDS = ("identifier", "title", "decision_date", "status")


class DecisionCreateDialog(QDialog):
    """Modal create-decision dialog. Per PRD §4.7."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._created_identifier: str | None = None
        self._worker = None

        self.setWindowTitle("New decision")
        self.setModal(True)
        self.setMinimumWidth(560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        form, widgets = build_decision_form(self)
        self._form = form
        self._widgets = widgets
        outer.addLayout(form)

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

        # First focus.
        self._widgets.identifier.setFocus(Qt.FocusReason.OtherFocusReason)

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self._created_identifier

    # ------------------------------------------------------------------
    # Save flow
    # ------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        self._widgets.clear_all_errors()
        if not self._validate_required():
            return
        if not self._validate_formats():
            return

        body = self._build_request_body()
        self._save_btn.setEnabled(False)
        self._worker = run_in_thread(
            lambda: self._client.create_decision(body),
            on_success=self._on_create_success,
            on_error=self._on_create_error,
            parent=self,
        )

    def _validate_required(self) -> bool:
        ok = True
        for field in _REQUIRED_FIELDS:
            value = self._widgets.value_for(field).strip()
            if not value:
                self._widgets.show_error(field, "This field is required.")
                ok = False
        return ok

    def _validate_formats(self) -> bool:
        """Format checks that fire after required-field checks pass."""
        ok = True
        identifier = self._widgets.value_for("identifier").strip()
        if identifier and not IDENTIFIER_RE.match(identifier):
            self._widgets.show_error("identifier", IDENTIFIER_HINT)
            ok = False
        date_value = self._widgets.value_for("decision_date").strip()
        if date_value and not DECISION_DATE_RE.match(date_value):
            self._widgets.show_error("decision_date", DECISION_DATE_HINT)
            ok = False
        for field in ("supersedes", "superseded_by"):
            value = self._widgets.value_for(field).strip()
            if value and not SUPERSEDES_RE.match(value):
                self._widgets.show_error(field, SUPERSEDES_HINT)
                ok = False
        return ok

    def _build_request_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "identifier": self._widgets.value_for("identifier").strip(),
            "title": self._widgets.value_for("title"),
            "decision_date": self._widgets.value_for("decision_date").strip(),
            "status": self._widgets.value_for("status"),
            "context": self._widgets.value_for("context"),
            "decision": self._widgets.value_for("decision"),
            "rationale": self._widgets.value_for("rationale"),
            "alternatives_considered": self._widgets.value_for(
                "alternatives_considered"
            ),
            "consequences": self._widgets.value_for("consequences"),
        }
        # Skip empty supersedes / superseded_by so the API treats them as
        # not-set (None on the input model).
        supersedes = self._widgets.value_for("supersedes").strip()
        if supersedes:
            body["supersedes"] = supersedes
        superseded_by = self._widgets.value_for("superseded_by").strip()
        if superseded_by:
            body["superseded_by"] = superseded_by
        return body

    def _on_create_success(self, result: Any) -> None:
        self._save_btn.setEnabled(True)
        if isinstance(result, dict):
            self._created_identifier = result.get("identifier") or self._widgets.value_for(
                "identifier"
            ).strip()
        else:
            self._created_identifier = self._widgets.value_for("identifier").strip()
        self.accept()

    def _on_create_error(self, exc: Exception) -> None:
        self._save_btn.setEnabled(True)

        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during decision create: %s", exc)
            self.reject()
            return

        if isinstance(exc, ConflictError):
            self._widgets.show_error(
                "identifier",
                "An identifier with this value already exists.",
            )
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
                    title="Could not create decision",
                    message=msg,
                    detail=detail,
                    parent=self,
                ).exec()
            return

        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during decision create: %s", exc)
            ErrorDialog(
                title="Could not create decision",
                message=exc.message or str(exc),
                detail=repr(exc),
                parent=self,
            ).exec()
            return

        _log.exception("Unexpected error during decision create", exc_info=exc)
        ErrorDialog(
            title="Could not create decision",
            message=str(exc) or exc.__class__.__name__,
            detail=repr(exc),
            parent=self,
        ).exec()
