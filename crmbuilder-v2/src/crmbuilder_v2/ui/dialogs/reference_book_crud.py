"""Reference book create / edit / delete dialogs (UI v0.7)."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._reference_book_schema import reference_book_fields

_IDENTIFIER_FIELD = "reference_book_identifier"


class ReferenceBookCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            reference_book_fields(include_identifier=False),
            mode="create",
            title="New reference book",
            create_method=client.create_reference_book,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class ReferenceBookEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit reference book"
        super().__init__(
            client,
            reference_book_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_reference_book,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class ReferenceBookDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client, identifier, title, client.delete_reference_book,
            entity_label="reference book", parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "reference book; it can be restored from the Show-deleted view."
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
