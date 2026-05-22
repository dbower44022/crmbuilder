"""Close-out payload create / edit / delete dialogs (UI v0.7).

The create dialog adds an inline producing-conversation selector: a
close_out_payload must carry exactly one outbound
``close_out_payload_produced_by_conversation`` edge at every status, so the
dialog fetches the next ``COP-NNN``, prompts for a conversation, and submits
the create with the explicit identifier plus the production edge.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import QComboBox, QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._close_out_payload_schema import (
    close_out_payload_fields,
)
from crmbuilder_v2.ui.exceptions import StorageClientError
from crmbuilder_v2.ui.widgets.form_helpers import required_label

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.close_out_payload_crud")
_IDENTIFIER_FIELD = "close_out_payload_identifier"


class CloseOutPayloadCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            close_out_payload_fields(include_identifier=False),
            mode="create",
            title="New close-out payload",
            create_method=client.create_close_out_payload,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        self._conv_combo = QComboBox()
        try:
            conversations = client.list_conversations()
        except StorageClientError as exc:
            _log.warning("Could not list conversations: %s", exc)
            conversations = []
        self._conv_combo.addItem("(select a conversation)", None)
        for conv in conversations:
            ident = conv.get("conversation_identifier")
            title = conv.get("conversation_title") or ""
            if ident:
                self._conv_combo.addItem(f"{ident} — {title}", ident)
        self._form.insertRow(0, required_label("Produced by conversation"), self._conv_combo)

    def _build_create_body(self) -> dict[str, Any]:
        body = super()._build_create_body()
        conv_id = self._conv_combo.currentData()
        if not conv_id:
            self._show_error(
                "close_out_payload_title",
                "Select a producing conversation.",
            )
            return {}
        try:
            new_id = self._client.next_close_out_payload_identifier()
        except StorageClientError as exc:
            _log.warning("next_close_out_payload_identifier failed: %s", exc)
            return body
        body[_IDENTIFIER_FIELD] = new_id
        body["references"] = [
            {
                "source_type": "close_out_payload",
                "source_id": new_id,
                "target_type": "conversation",
                "target_id": conv_id,
                "relationship": "close_out_payload_produced_by_conversation",
            }
        ]
        return body


class CloseOutPayloadEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit close-out payload"
        super().__init__(
            client,
            close_out_payload_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_close_out_payload,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class CloseOutPayloadDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client, identifier, title, client.delete_close_out_payload,
            entity_label="close-out payload", parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "payload; it can be restored from the Show-deleted view."
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
