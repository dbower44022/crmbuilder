"""Conversation create / edit / delete dialogs.

Per PI-073 / DEC-314, conversations are topical sub-units within a
session. The create dialog adds an inline session-membership selector:
conversations require exactly one outbound
``conversation_belongs_to_session`` edge at every status, so the dialog
fetches the next ``CNV-NNN`` identifier, lets the user pick a session,
and submits the create body with the explicit identifier plus the
membership edge in the ``references`` array.
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
    """New conversation. Includes a session-membership selector."""

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
        self._session_combo = QComboBox()
        try:
            sessions = client.list_sessions()
        except StorageClientError as exc:
            _log.warning("Could not list sessions: %s", exc)
            sessions = []
        self._session_combo.addItem("(select a session)", None)
        for sess in sessions:
            ident = sess.get("session_identifier")
            title = sess.get("session_title") or ""
            if ident:
                self._session_combo.addItem(f"{ident} — {title}", ident)
        # Insert the picker as the first row of the form.
        self._form.insertRow(0, required_label("Session"), self._session_combo)

    def _build_create_body(self) -> dict[str, Any]:
        body = super()._build_create_body()
        sess_id = self._session_combo.currentData()
        if not sess_id:
            # Surface inline on the title row (no dedicated error label
            # for the picker; fall through to server 422 if it slips).
            self._show_error(
                "conversation_title", "Select a session for this conversation."
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
                "target_type": "session",
                "target_id": sess_id,
                "relationship": "conversation_belongs_to_session",
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
