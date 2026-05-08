"""Decision delete confirmation dialog.

Wired in slice G. See PRD section 4.9 for the confirmation copy and
HTTP 409 behavior.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.decision_delete")


class DecisionDeleteDialog(QDialog):
    """Confirmation dialog for deleting a decision. Per PRD §4.9."""

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._identifier = identifier
        self._title = title
        self._worker = None

        self.setWindowTitle("Delete decision")
        self.setModal(True)
        self.setMinimumWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        self._body_label = QLabel(
            f"Delete {identifier} — {title}? This cannot be undone."
        )
        self._body_label.setObjectName("delete_body_label")
        self._body_label.setWordWrap(True)
        outer.addWidget(self._body_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setDefault(True)
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("delete_button")
        self._delete_btn.setStyleSheet(
            "QPushButton { color: #ffffff; background: #c1272d; padding: 4px 12px; }"
            " QPushButton:disabled { color: #ffffff; background: #b6868a; }"
        )
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self._delete_btn)
        outer.addLayout(button_row)

    def _on_delete_clicked(self) -> None:
        self._delete_btn.setEnabled(False)
        self._worker = run_in_thread(
            lambda: self._client.delete_decision(self._identifier),
            on_success=self._on_delete_success,
            on_error=self._on_delete_error,
            parent=self,
        )

    def _on_delete_success(self, _result: Any) -> None:
        self.accept()

    def _on_delete_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during decision delete: %s", exc)
            self.reject()
            return

        if isinstance(exc, NotFoundError):
            # Already deleted by another writer; treat as success.
            _log.info("Decision %s already deleted", self._identifier)
            self.accept()
            return

        if isinstance(exc, ConflictError):
            detail = exc.message or "other records reference this decision"
            self._body_label.setText(
                f"{self._identifier} cannot be deleted because it is "
                f"referenced by other records: {detail}."
            )
            self._delete_btn.hide()
            self._cancel_btn.setText("Close")
            return

        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during decision delete: %s", exc)
            ErrorDialog(
                title="Could not delete decision",
                message=exc.message or str(exc),
                detail=repr(exc),
                parent=self,
            ).exec()
            self._delete_btn.setEnabled(True)
            return

        _log.exception("Unexpected error during decision delete", exc_info=exc)
        ErrorDialog(
            title="Could not delete decision",
            message=str(exc) or exc.__class__.__name__,
            detail=repr(exc),
            parent=self,
        ).exec()
        self._delete_btn.setEnabled(True)
