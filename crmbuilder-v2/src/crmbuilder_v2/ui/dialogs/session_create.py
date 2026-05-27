"""Session CRUD dialogs (PI-073 / DEC-314 redesign).

Sessions are now first-class lifecycle objects — schedulable, editable,
and stateful through six statuses. The legacy append-only constraint
(DEC-013) is superseded.

This module provides ``SessionCreateDialog``, ``SessionEditDialog``, and
``SessionDeleteDialog``. The create dialog includes an inline workstream-
membership selector (sessions require exactly one outbound
``session_belongs_to_workstream`` edge at every live status).

Filename retained as ``session_create.py`` for branch git-history
continuity; the file now exports edit/delete dialogs alongside create.
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
from crmbuilder_v2.ui.dialogs._session_schema import session_fields
from crmbuilder_v2.ui.exceptions import StorageClientError
from crmbuilder_v2.ui.widgets.form_helpers import required_label

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.session_create")
_IDENTIFIER_FIELD = "session_identifier"


class SessionCreateDialog(EntityCrudDialog):
    """New session. Includes a workstream-membership selector."""

    def __init__(
        self, client: StorageClient, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            client,
            session_fields(include_identifier=False),
            mode="create",
            title="New session",
            create_method=client.create_session,
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
            self._show_error(
                "session_title", "Select a workstream for this session."
            )
            return {}
        try:
            new_id = self._client.next_session_identifier()
        except StorageClientError as exc:
            _log.warning("next_session_identifier failed: %s", exc)
            return body
        body[_IDENTIFIER_FIELD] = new_id
        body["references"] = [
            {
                "source_type": "session",
                "source_id": new_id,
                "target_type": "workstream",
                "target_id": ws_id,
                "relationship": "session_belongs_to_workstream",
            }
        ]
        return body

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()


class SessionEditDialog(EntityCrudDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit session"
        super().__init__(
            client,
            session_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_session,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class SessionDeleteDialog(EntityCrudDeleteDialog):
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
            client.delete_session,
            entity_label="session",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "session; it can be restored from the Show-deleted view."
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
