"""Persona create / edit / delete dialogs (v0.5+, PI-003).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases, following the v0.4 methodology-entity
pattern and mirroring ``entity_crud.py``. The declarative field schema
lives in ``_persona_schema.py``.

* ``PersonaCreateDialog`` — create mode; ``persona_identifier`` is not
  shown (server-assigned). Status defaults to ``candidate``. Per the
  v0.4 DEC-067 create-then-attach precedent (adopted unchanged in this
  v0.5+ build for cross-entity-type consistency) the dialog creates
  the persona record only — there is no domain-affiliation multi-select
  or entity-realization single-select; the user attaches
  ``persona_scopes_to_domain`` and ``persona_realized_as_entity``
  references from the detail pane's "Add reference" affordance after
  the record exists.
* ``PersonaEditDialog`` — edit mode; ``persona_identifier`` read-only.
  Saves via PATCH (the base computes a partial diff); the status combo
  is restricted to valid successors by the schema's
  ``compute_options``.
* ``PersonaDeleteDialog`` — edge-text confirmation (``persona.md``
  §3.6.6): the Delete button stays disabled until the operator types
  the ``PER-NNN`` identifier exactly. Confirmation soft-deletes;
  outbound ``persona_scopes_to_domain`` and
  ``persona_realized_as_entity`` references persist per spec §3.4.6.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._persona_schema import persona_fields

_IDENTIFIER_FIELD = "persona_identifier"


class PersonaCreateDialog(EntityCrudDialog):
    """Modal create-persona dialog. Per ``persona.md`` §3.6.4."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            persona_fields(include_identifier=False),
            mode="create",
            title="New persona",
            create_method=client.create_persona,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created persona, or None if not accepted."""
        return self.saved_identifier()


class PersonaEditDialog(EntityCrudDialog):
    """Modal edit-persona dialog. Per ``persona.md`` §3.6.5."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit persona"
        super().__init__(
            client,
            persona_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_persona,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class PersonaDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a persona. Per ``persona.md``
    §3.6.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation: the
    Delete button is disabled until the operator types the persona's
    ``PER-NNN`` identifier exactly into the confirmation field.
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
            client.delete_persona,
            entity_label="persona",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes "
            "the persona; it can be restored from the Show-deleted "
            "view. Any domain affiliations and entity realizations are "
            "kept."
        )
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setObjectName("delete_confirm_edit")
        self._confirm_edit.setPlaceholderText(identifier)
        self._confirm_edit.textChanged.connect(self._on_confirm_text_changed)
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            # Insert just above the Cancel/Delete button row (the last
            # item the base added).
            layout.insertWidget(layout.count() - 1, self._confirm_edit)
        self._delete_btn.setEnabled(False)

    def _on_confirm_text_changed(self, text: str) -> None:
        self._delete_btn.setEnabled(text.strip() == self._identifier)
