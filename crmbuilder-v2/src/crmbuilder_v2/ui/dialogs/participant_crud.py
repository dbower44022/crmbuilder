"""Participant create / edit / delete dialogs (REL-069 / PI-391).

Thin subclasses of the shared ``EntityCrudDialog`` / ``EntityCrudDeleteDialog``
bases, mirroring ``persona_crud.py``. The declarative field schema lives in
``_participant_schema.py``. The create dialog omits ``participant_identifier``
(server-assigned); the edit dialog shows it read-only and saves via PATCH. Delete
uses edge-text confirmation and soft-deletes; the persona backing edge persists.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._participant_schema import participant_fields

_IDENTIFIER_FIELD = "participant_identifier"


class ParticipantCreateDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            client,
            participant_fields(include_identifier=False),
            mode="create",
            title="New participant",
            create_method=client.create_participant,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()


class ParticipantEditDialog(EntityCrudDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit participant"
        super().__init__(
            client,
            participant_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_participant,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class ParticipantDeleteDialog(EntityCrudDeleteDialog):
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
            client.delete_participant,
            entity_label="participant",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(unnamed)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "participant; it can be restored from the Show-deleted view. Any "
            "persona backing is kept."
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
