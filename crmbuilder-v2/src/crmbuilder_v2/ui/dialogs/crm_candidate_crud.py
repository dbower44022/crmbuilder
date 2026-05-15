"""CRM Candidate create / edit / delete dialogs (UI v0.4 slice E).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases, following the v0.3 governance-entity
pattern. The declarative field schema lives in
``_crm_candidate_schema.py``.

* ``CrmCandidateCreateDialog`` — create mode;
  ``crm_candidate_identifier`` is not shown (server-assigned).
  Status defaults to ``active``. Singleton-``selected`` violations
  surface inline on the status field per PRD section 4.6.
* ``CrmCandidateEditDialog`` — edit mode;
  ``crm_candidate_identifier`` read-only. Saves via PATCH (the base
  computes a partial diff); the status combo is restricted to valid
  successors by the schema's ``compute_options``. Terminal-state
  records show only the current value in their combo (effectively
  read-only post-transition).
* ``CrmCandidateDeleteDialog`` — edge-text confirmation
  (``crm_candidate.md`` section 3.6.6): the Delete button stays
  disabled until the operator types the ``CRM-NNN`` identifier
  exactly. The dialog body distinguishes soft-delete-for-authoring-
  error from transition-to-``removed`` per PRD section 4.6.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._crm_candidate_schema import (
    crm_candidate_fields,
)
from crmbuilder_v2.ui.exceptions import RequestShapeError

_IDENTIFIER_FIELD = "crm_candidate_identifier"
_STATUS_FIELD = "crm_candidate_status"


def _surface_singleton_inline(
    dialog: EntityCrudDialog, exc: Exception
) -> bool:
    """If ``exc`` is a singleton-``selected`` conflict, surface inline.

    Returns True when the error was handled (the dialog should not
    fall through to its generic error path); False otherwise. The
    inline message reads "CRM-NNN is already selected — change its
    status first." per PRD section 4.6.
    """
    if not isinstance(exc, RequestShapeError):
        return False
    payload = exc.dedicated_error
    if not isinstance(payload, dict):
        return False
    if payload.get("error") != "selected_candidate_already_exists":
        return False
    existing = str(payload.get("existing") or "another candidate")
    dialog._show_error(  # noqa: SLF001 — accessing protected helper by design
        _STATUS_FIELD,
        f"{existing} is already selected — change its status first.",
    )
    dialog._save_btn.setEnabled(True)  # noqa: SLF001
    return True


class CrmCandidateCreateDialog(EntityCrudDialog):
    """Modal create-crm_candidate dialog. Per ``crm_candidate.md`` section 3.6.4."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            crm_candidate_fields(include_identifier=False),
            mode="create",
            title="New CRM candidate",
            create_method=client.create_crm_candidate,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()

    def _on_save_error(self, exc: Exception) -> None:
        if _surface_singleton_inline(self, exc):
            return
        super()._on_save_error(exc)


class CrmCandidateEditDialog(EntityCrudDialog):
    """Modal edit-crm_candidate dialog. Per ``crm_candidate.md`` section 3.6.5."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = (
            f"Edit {identifier}" if identifier else "Edit CRM candidate"
        )
        super().__init__(
            client,
            crm_candidate_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_crm_candidate,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def _on_save_error(self, exc: Exception) -> None:
        if _surface_singleton_inline(self, exc):
            return
        super()._on_save_error(exc)


class CrmCandidateDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a crm_candidate. Per spec 3.6.6 + PRD 4.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation:
    the Delete button is disabled until the operator types the
    ``CRM-NNN`` identifier exactly into the confirmation field. The
    body label includes a clarifying note distinguishing soft-delete-
    for-authoring-error from transition-to-``removed`` per PRD section
    4.6.
    """

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            identifier,
            title,
            client.delete_crm_candidate,
            entity_label="CRM candidate",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(unnamed)'}?\n\n"
            "Delete soft-deletes this record as an authoring-error "
            "correction. If this CRM was legitimately in the candidate "
            "set and you want to pull it from further iterations, "
            "change its Status to Removed instead.\n\n"
            "Type the identifier below to confirm."
        )
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setObjectName("delete_confirm_edit")
        self._confirm_edit.setPlaceholderText(identifier)
        self._confirm_edit.textChanged.connect(self._on_confirm_text_changed)
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(layout.count() - 1, self._confirm_edit)
        self._delete_btn.setEnabled(False)

    def _on_confirm_text_changed(self, text: str) -> None:
        self._delete_btn.setEnabled(text.strip() == self._identifier)
