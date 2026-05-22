"""Conversation create / edit / delete dialogs (UI v0.7).

The create dialog adds an inline workstream-membership selector (per
``conversation.md`` §3.6.4): conversations require exactly one outbound
``conversation_belongs_to_workstream`` edge at every status, so the dialog
fetches the next ``CONV-NNN`` identifier, lets the user pick a workstream,
and submits the create body with the explicit identifier plus the membership
edge in the ``references`` array.
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
from crmbuilder_v2.ui.dialogs._conversation_schema import conversation_fields
from crmbuilder_v2.ui.exceptions import StorageClientError
from crmbuilder_v2.ui.widgets.form_helpers import required_label

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.conversation_crud")
_IDENTIFIER_FIELD = "conversation_identifier"


class ConversationCreateDialog(EntityCrudDialog):
    """New conversation. Includes a workstream-membership selector."""

    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            conversation_fields(include_identifier=False),
            mode="create",
            title="New conversation",
            create_method=client.create_conversation,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        self._workstream_combo = QComboBox()
        try:
            workstreams = client.list_workstreams()
        except StorageClientError as exc:
            _log.warning("Could not list workstreams: %s", exc)
            workstreams = []
        self._workstream_combo.addItem("(select a workstream)", None)
        for ws in workstreams:
            ident = ws.get("workstream_identifier")
            name = ws.get("workstream_name") or ""
            if ident:
                self._workstream_combo.addItem(f"{ident} — {name}", ident)
        # Insert the picker as the first row of the form.
        self._form.insertRow(0, required_label("Workstream"), self._workstream_combo)

    def _build_create_body(self) -> dict[str, Any]:
        body = super()._build_create_body()
        ws_id = self._workstream_combo.currentData()
        if not ws_id:
            # Surface inline on the title row (no dedicated error label
            # for the picker; fall through to server 422 if it slips).
            self._show_error(
                "conversation_title", "Select a workstream for this conversation."
            )
            return {}
        try:
            new_id = self._client.next_conversation_identifier()
        except StorageClientError as exc:
            _log.warning("next_conversation_identifier failed: %s", exc)
            return body
        body[_IDENTIFIER_FIELD] = new_id
        body["references"] = [
            {
                "source_type": "conversation",
                "source_id": new_id,
                "target_type": "workstream",
                "target_id": ws_id,
                "relationship": "conversation_belongs_to_workstream",
            }
        ]
        return body


class ConversationEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit conversation"
        super().__init__(
            client,
            conversation_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_conversation,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class ConversationDeleteDialog(EntityCrudDeleteDialog):
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
            client.delete_conversation,
            entity_label="conversation",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "conversation; it can be restored from the Show-deleted view."
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
