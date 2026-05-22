"""Work ticket create / edit / delete dialogs (UI v0.7)."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._work_ticket_schema import work_ticket_fields

_IDENTIFIER_FIELD = "work_ticket_identifier"


class WorkTicketCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            work_ticket_fields(include_identifier=False),
            mode="create",
            title="New work ticket",
            create_method=client.create_work_ticket,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class WorkTicketEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit work ticket"
        super().__init__(
            client,
            work_ticket_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_work_ticket,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class WorkTicketDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client, identifier, title, client.delete_work_ticket,
            entity_label="work ticket", parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "work ticket; it can be restored from the Show-deleted view."
        )
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setPlaceholderText(identifier)
        self._confirm_edit.textChanged.connect(self._on_confirm_text_changed)
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(layout.count() - 1, self._confirm_edit)
        self._delete_btn.setEnabled(False)

    def _on_confirm_text_changed(self, text: str) -> None:
        self._delete_btn.setEnabled(text.strip() == self._identifier)
