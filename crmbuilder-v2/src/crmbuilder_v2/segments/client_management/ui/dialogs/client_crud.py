"""Client create / edit / delete dialogs (PI-512 / REQ-589).

Thin subclasses of the shared ``EntityCrudDialog`` / ``EntityCrudDeleteDialog``
bases, mirroring ``participant_crud.py``. The create dialog omits
``client_identifier`` (server-assigned); the edit dialog shows it read-only and
saves via PATCH. Delete uses edge-text confirmation and soft-deletes; the store
refuses the delete while the client still holds engagements (DEC-1092).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.segments.client_management.ui.dialogs._client_schema import (
    client_fields,
)
from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient

_IDENTIFIER_FIELD = "client_identifier"


class ClientCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            client_fields(include_identifier=False),
            mode="create",
            title="New client",
            create_method=client.create_client,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()


class ClientEditDialog(EntityCrudDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit client"
        super().__init__(
            client,
            client_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_client,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class ClientDeleteDialog(EntityCrudDeleteDialog):
    """Delete confirmation with edge-text confirmation (type the identifier)."""

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
            client.delete_client,
            entity_label="client",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(unnamed)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the client; "
            "it can be restored from the Show-deleted view. A client that still "
            "defines applications is refused: unlink them first."
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
