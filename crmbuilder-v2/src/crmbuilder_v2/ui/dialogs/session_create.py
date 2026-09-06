"""Session CRUD dialogs (PI-073 / DEC-314 redesign).

Sessions are now first-class lifecycle objects — schedulable, editable,
and stateful through six statuses. The legacy append-only constraint
(DEC-013) is superseded.

This module provides ``SessionCreateDialog``, ``SessionEditDialog``, and
``SessionDeleteDialog``. The create dialog includes an inline workstream-
membership selector (sessions require exactly one outbound
``session_belongs_to_project`` edge at every live status).

Filename retained as ``session_create.py`` for branch git-history
continuity; the file now exports edit/delete dialogs alongside create.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
#: The opening question every surface asks (PI-488, plan Part 4).
OPENING_QUESTION = "What do you want to do today?"
_DEFAULT_EXAMPLES = (
    "Define new business processes",
    "Add or change a field or screen in an existing application",
    "Upgrade the platform to the latest version",
)


class SessionCreateDialog(EntityCrudDialog):
    """New session. Includes a workstream-membership selector.

    Since PI-488 (REQ-576) the dialog asks the opening question first. When
    the user answers it, the session is created through the session-open
    operation — the server classifies the answer into a kind of work, says
    the confirmation line back (the *Say it back* button previews it without
    a write), and records the answer, the kind of work and the phase segments
    on the session. Left empty, the dialog creates a plain session as before.
    """

    def __init__(
        self, client: StorageClient, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            client,
            session_fields(include_identifier=False),
            mode="create",
            title="New session",
            create_method=self._create_session,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        self._last_confirmation_line: str | None = None
        self._opening_answer_edit = QLineEdit()
        self._opening_answer_edit.setPlaceholderText(
            "e.g. " + "; ".join(self._opening_examples(client))
        )
        self._say_back_btn = QPushButton("Say it back")
        self._say_back_btn.setToolTip(
            "Show what the system understood before the session is created."
        )
        self._say_back_btn.clicked.connect(self._on_say_back_clicked)
        self._confirmation_label = QLabel("")
        self._confirmation_label.setWordWrap(True)
        self._confirmation_label.setObjectName("sessionOpeningConfirmation")
        say_back_row = QWidget()
        say_back_layout = QHBoxLayout(say_back_row)
        say_back_layout.setContentsMargins(0, 0, 0, 0)
        say_back_layout.addWidget(self._say_back_btn)
        say_back_layout.addWidget(self._confirmation_label, 1)
        self._form.insertRow(0, required_label(OPENING_QUESTION), self._opening_answer_edit)
        self._form.insertRow(1, "", say_back_row)
        self._workstream_combo = QComboBox()
        try:
            workstreams = client.list_projects()
        except StorageClientError as exc:
            _log.warning("Could not list workstreams: %s", exc)
            workstreams = []
        self._workstream_combo.addItem("(select a workstream)", None)
        for ws in workstreams:
            ident = ws.get("project_identifier")
            name = ws.get("project_name") or ""
            if ident:
                self._workstream_combo.addItem(f"{ident} — {name}", ident)
        # Insert the picker after the opening question rows.
        self._form.insertRow(2, required_label("Project"), self._workstream_combo)

    # --- the opening question (PI-488) ---------------------------------------------

    @staticmethod
    def _opening_examples(client: StorageClient) -> list[str]:
        """Three or four example kinds of work drawn from the catalogue."""
        try:
            opening = client.get_session_opening()
        except StorageClientError as exc:
            _log.warning("Could not read the session opening: %s", exc)
            return list(_DEFAULT_EXAMPLES)
        examples = opening.get("examples") if isinstance(opening, dict) else None
        if isinstance(examples, list) and 3 <= len(examples) <= 4 and all(
            isinstance(e, str) for e in examples
        ):
            return examples
        return list(_DEFAULT_EXAMPLES)

    def opening_answer(self) -> str:
        return self._opening_answer_edit.text().strip()

    def confirmation_line(self) -> str | None:
        """The line the system said back for the created session, if any."""
        return self._last_confirmation_line

    def _on_say_back_clicked(self) -> None:
        answer = self.opening_answer()
        if not answer:
            self._confirmation_label.setText(
                "Type what you want to do today, then press Say it back."
            )
            return
        try:
            opening = self._client.get_session_opening(answer=answer)
        except StorageClientError as exc:
            _log.warning("Could not preview the opening answer: %s", exc)
            self._confirmation_label.setText(
                "The store could not be reached; the session can still be created."
            )
            return
        preview = opening.get("preview") if isinstance(opening, dict) else None
        line = ""
        if isinstance(preview, dict):
            line = preview.get("confirmation_line") or preview.get("first_line") or ""
        self._confirmation_label.setText(line or "No answer was recognised.")

    def _create_session(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create through the session-open operation when the opening question
        was answered; through the plain create otherwise."""
        if "opening_answer" not in body:
            return self._client.create_session(body)
        result = self._client.open_session(body)
        self._last_confirmation_line = result.get("confirmation_line") or result.get("first_line")
        session = result.get("session")
        return session if isinstance(session, dict) else result

    def _build_create_body(self) -> dict[str, Any]:
        body = super()._build_create_body()
        ws_id = self._workstream_combo.currentData()
        if not ws_id:
            self._show_error(
                "session_title", "Select a workstream for this session."
            )
            return {}
        answer = self.opening_answer()
        if answer:
            # The session-open operation records the answer, the kind of work,
            # the confirmation line and the phase segments (REQ-576); the form's
            # own fields ride along as overrides.
            open_body: dict[str, Any] = {
                "opening_answer": answer,
                "project_identifier": ws_id,
                "medium": body.get("session_medium") or "chat",
                "title": body.get("session_title") or None,
                "description": body.get("session_description") or None,
                "executive_summary": body.get("session_executive_summary") or None,
                "notes": body.get("session_notes") or None,
            }
            return {k: v for k, v in open_body.items() if v is not None}
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
                "target_type": "project",
                "target_id": ws_id,
                "relationship": "session_belongs_to_project",
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
