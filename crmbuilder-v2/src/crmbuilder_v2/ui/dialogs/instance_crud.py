"""Instance create / edit / delete dialogs (PI-186 / PRJ-027).

Thin subclasses of the shared ``EntityCrudDialog`` / ``EntityCrudDeleteDialog``
bases. The declarative field schema lives in ``_instance_schema.py``.

* ``InstanceCreateDialog`` — create mode; ``instance_identifier`` is not shown
  (server-assigned). A blank secret sends none.
* ``InstanceEditDialog`` — edit mode; ``instance_identifier`` read-only. Saves
  via PATCH (the base computes a partial diff); a blank secret field produces no
  diff so the stored secret is preserved, while typing a value rotates it.
* ``InstanceDeleteDialog`` — edge-text confirmation: the Delete button stays
  disabled until the operator types the ``INST-NNN`` identifier exactly.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._instance_schema import instance_fields

_IDENTIFIER_FIELD = "instance_identifier"


class InstanceCreateDialog(EntityCrudDialog):
    """Modal create-instance dialog."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            instance_fields(include_identifier=False),
            mode="create",
            title="New instance",
            create_method=client.create_instance,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()


class InstanceEditDialog(EntityCrudDialog):
    """Modal edit-instance dialog."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit instance"
        super().__init__(
            client,
            instance_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_instance,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class InstanceDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting an instance (edge-text confirmation)."""

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
            client.delete_instance,
            entity_label="instance",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(unnamed)'}?\n\n"
            "This soft-deletes the connection. Its stored keyring secret is "
            "left in place. Type the identifier below to confirm."
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
