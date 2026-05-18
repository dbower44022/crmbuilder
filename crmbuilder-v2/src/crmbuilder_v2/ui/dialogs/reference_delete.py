"""Reference delete confirmation dialog — v0.3 slice C (DEC-033).

Hard-delete confirmation modal. Renders the edge text and the stark
"This cannot be undone through the UI" notice. Confirming sends
``DELETE /references/{id}``. References are immutable identity-wise;
"edit" is delete + create. No tombstone, no Show-deleted toggle, no
Restore.

Mirrors :class:`crmbuilder_v2.ui.base.crud_dialog.EntityCrudDeleteDialog`'s
worker-based pattern but is parameterized by the integer reference id
(rather than a string identifier) and renders a custom edge-text body.
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
from crmbuilder_v2.ui.elevation import apply_dialog_shadow
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.modal_backdrop import attach as _backdrop_attach
from crmbuilder_v2.ui.widgets.modal_backdrop import detach as _backdrop_detach

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.reference_delete")


def edge_text(reference: dict[str, Any]) -> str:
    """Render the human-readable edge text for a reference dict.

    Format: ``"{source_id} → {target_id}: {relationship}"`` — used by
    both the dialog body and any caller logging the deletion. Robust
    against missing fields (renders ``"?"`` placeholders) so a
    malformed reference doesn't crash the dialog construction.
    """
    source_id = reference.get("source_id") or "?"
    target_id = reference.get("target_id") or "?"
    relationship = reference.get("relationship") or "?"
    return f"{source_id} → {target_id}: {relationship}"


class ReferenceDeleteDialog(QDialog):
    """Hard-delete confirmation modal for a reference."""

    def __init__(
        self,
        client: StorageClient,
        *,
        reference_id: int,
        edge: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._reference_id = reference_id
        self._edge = edge
        self._worker = None

        self.setWindowTitle("Delete reference")
        self.setModal(True)
        self.setMinimumWidth(440)
        apply_dialog_shadow(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        self._body_label = QLabel(
            f"Delete the reference [{edge}]?\n\n"
            "This cannot be undone through the UI."
        )
        self._body_label.setObjectName("reference_delete_body_label")
        self._body_label.setWordWrap(True)
        outer.addWidget(self._body_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setDefault(True)
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("reference_delete_button")
        self._delete_btn.setStyleSheet(
            "QPushButton { color: #ffffff; background: #c1272d; padding: 4px 12px; }"
            " QPushButton:disabled { color: #ffffff; background: #b6868a; }"
        )
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self._delete_btn)
        outer.addLayout(button_row)

    # ------------------------------------------------------------------
    # Modal backdrop hooks (v0.6 slice A — DEC-091)
    # ------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802 — Qt naming
        super().showEvent(event)
        _backdrop_attach(self)

    def hideEvent(self, event):  # noqa: N802 — Qt naming
        _backdrop_detach(self)
        super().hideEvent(event)

    def _on_delete_clicked(self) -> None:
        from crmbuilder_v2.ui.workers import run_in_thread

        self._delete_btn.setEnabled(False)
        self._worker = run_in_thread(
            lambda: self._client.delete_reference(self._reference_id),
            on_success=self._on_delete_success,
            on_error=self._on_delete_error,
            parent=self,
        )

    def _on_delete_success(self, _result: Any) -> None:
        self.accept()

    def _on_delete_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during reference delete: %s", exc)
            self.reject()
            return
        if isinstance(exc, NotFoundError):
            # Another writer may have already deleted this reference.
            # Treat as success; the panel refresh after accept() will
            # show the row gone either way.
            _log.info(
                "Reference id=%s already deleted", self._reference_id
            )
            self.accept()
            return
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during reference delete: %s", exc)
            ErrorDialog(
                title="Could not delete reference",
                message=exc.message or str(exc),
                detail=repr(exc),
                parent=self,
            ).exec()
            self._delete_btn.setEnabled(True)
            return
        _log.exception("Unexpected error during reference delete", exc_info=exc)
        ErrorDialog(
            title="Could not delete reference",
            message=str(exc) or exc.__class__.__name__,
            detail=repr(exc),
            parent=self,
        ).exec()
        self._delete_btn.setEnabled(True)
