"""Domain create / edit / delete dialogs (UI v0.4 slice B).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases, following the v0.3 governance-entity
pattern. The declarative field schema lives in ``_domain_schema.py``.

* ``DomainCreateDialog`` — create mode; ``domain_identifier`` is not
  shown (server-assigned). Status defaults to ``candidate``.
* ``DomainEditDialog`` — edit mode; ``domain_identifier`` read-only.
  Saves via PATCH (the base computes a partial diff); the status combo
  is restricted to valid successors by the schema's ``compute_options``.
* ``DomainDeleteDialog`` — edge-text confirmation (``domain.md``
  section 3.6.6): the Delete button stays disabled until the operator
  types the ``DOM-NNN`` identifier exactly. Confirmation soft-deletes.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._domain_schema import domain_fields

_IDENTIFIER_FIELD = "domain_identifier"


class DomainCreateDialog(EntityCrudDialog):
    """Modal create-domain dialog. Per ``domain.md`` section 3.6.4."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            domain_fields(include_identifier=False),
            mode="create",
            title="New domain",
            create_method=client.create_domain,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created domain, or None if not accepted."""
        return self.saved_identifier()


class DomainEditDialog(EntityCrudDialog):
    """Modal edit-domain dialog. Per ``domain.md`` section 3.6.5."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit domain"
        super().__init__(
            client,
            domain_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_domain,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class DomainDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a domain. Per ``domain.md`` 3.6.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation: the
    Delete button is disabled until the operator types the domain's
    ``DOM-NNN`` identifier exactly into the confirmation field.
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
            client.delete_domain,
            entity_label="domain",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "domain; it can be restored from the Show-deleted view."
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
