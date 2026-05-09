"""Append-only Sessions create dialog (v0.3 slice D — DEC-034).

Per DEC-013, every Claude.ai conversation produces exactly one
session record (append-only — no edit, no delete, no restore, no
draft mode). DEC-034 authorizes user-authored sessions through the
UI; this dialog is the corresponding write surface.

The identifier is auto-assigned at dialog-open time by reading the
existing sessions list and incrementing the highest ``SES-NNN``. On
a collision (another writer beat us between the list read and the
POST), the dialog recomputes the next identifier once and retries
the save transparently before surfacing an inline error.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._session_schema import session_fields_create
from crmbuilder_v2.ui.exceptions import ConflictError

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.session_create")


def compute_next_session_identifier(
    sessions: list[dict],
) -> str:
    """Return the next ``SES-NNN`` after the highest existing identifier.

    Records with malformed identifiers (missing ``SES-`` prefix or
    non-numeric suffix) are skipped. An empty list yields ``SES-001``.
    """
    max_n = 0
    for record in sessions:
        ident = record.get("identifier") or ""
        if not isinstance(ident, str) or not ident.startswith("SES-"):
            continue
        suffix = ident[len("SES-") :]
        try:
            n = int(suffix)
        except ValueError:
            continue
        if n > max_n:
            max_n = n
    return f"SES-{max_n + 1:03d}"


class SessionCreateDialog(EntityCrudDialog):
    """Modal create-session dialog. Append-only per DEC-013 / DEC-034."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        next_identifier = compute_next_session_identifier(
            client.list_sessions()
        )
        super().__init__(
            client,
            session_fields_create(identifier=next_identifier),
            mode="create",
            title="New Session",
            create_method=client.create_session,
            parent=parent,
        )
        self._collision_retry_attempted = False

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()

    # ------------------------------------------------------------------
    # Identifier-collision retry
    # ------------------------------------------------------------------

    def _on_save_error(self, exc: Exception) -> None:
        """Recompute identifier and resubmit on a one-shot collision retry.

        A ``ConflictError`` on a session create almost certainly means
        another writer claimed our auto-assigned ``SES-NNN`` between
        the list read at dialog-open and the POST. Recomputing once
        from a fresh list and resubmitting is the natural recovery —
        the user wrote a session, not a specific identifier. If the
        retry also collides, fall back to the base class's inline
        error rendering so the user can see something is genuinely
        wrong rather than spinning forever.
        """
        if (
            isinstance(exc, ConflictError)
            and not self._collision_retry_attempted
        ):
            self._collision_retry_attempted = True
            try:
                fresh_id = compute_next_session_identifier(
                    self._client.list_sessions()
                )
            except Exception:  # noqa: BLE001 — degrade to default error path
                _log.exception(
                    "Could not recompute session identifier after collision"
                )
                super()._on_save_error(exc)
                return
            self._widgets.set_value("identifier", fresh_id)
            # Re-run the save flow with the new identifier. ``_on_save_clicked``
            # rebuilds the request body from current widget values.
            self._on_save_clicked()
            return
        super()._on_save_error(exc)
