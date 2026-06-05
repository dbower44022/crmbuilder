"""Term (glossary) create / edit / delete dialogs (PI-061).

Thin subclasses of the shared ``EntityCrudDialog`` / ``EntityCrudDeleteDialog``
bases, following the v0.4 methodology-entity pattern. The declarative field
schema lives in ``_term_schema.py``.

* ``TermCreateDialog`` — create mode; ``identifier`` is not shown
  (server-assigned). Status defaults to ``active``.
* ``TermEditDialog`` — edit mode; ``identifier`` read-only. Saves via PATCH
  (the base computes a partial diff).
* ``TermDeleteDialog`` — confirmation; the term is removed outright (terms have
  no soft-delete).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._term_schema import term_fields

_IDENTIFIER_FIELD = "identifier"


class TermCreateDialog(EntityCrudDialog):
    """Modal create-term dialog (PI-061)."""

    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            term_fields(include_identifier=False),
            mode="create",
            title="New term",
            create_method=client.create_term,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()


class TermEditDialog(EntityCrudDialog):
    """Modal edit-term dialog (PI-061)."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit term"
        super().__init__(
            client,
            term_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_term,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class TermDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a term (PI-061)."""

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
            client.delete_term,
            entity_label="term",
            parent=parent,
        )
