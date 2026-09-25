"""Engagement create / edit dialogs (UI v0.5 slice C).

Thin subclasses of the shared ``EntityCrudDialog`` base, mirroring the
v0.4 methodology-entity dialog pattern. The declarative field schema
lives in ``_engagement_schema.py``.

* ``EngagementCreateDialog`` — create mode. Fields per
  ``engagement.md`` §3.6.3 / PRD §5.1: code (writeable, regex hint
  visible, with format validation), name, purpose, status (default
  ``active``).

* ``EngagementEditDialog`` — edit mode. ``engagement_identifier`` and
  ``engagement_code`` are read-only (the code field carries a tooltip
  reading "Engagement code cannot be changed after creation."); all
  other fields editable. PATCH-only on submit — the base computes a
  partial diff against the pre-fill values.

(The vestigial ``engagement_export_dir`` field and its directory-browser
/ emphasis / non-existent-path-confirm affordances were dropped in the
PI-β follow-on pass, after PI-β removed the snapshot/export machinery.)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QWidget

from crmbuilder_v2.segments.client_management.ui.dialogs._engagement_schema import (
    DEFINING_CLIENT_KEY,
    client_choice_label,
    engagement_fields_create,
    engagement_fields_edit,
)
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient

_IDENTIFIER_FIELD = "engagement_identifier"


def _clients_for_choice(client: StorageClient) -> list[dict[str, Any]]:
    """The live clients the defining-client combo offers; an unreachable
    store yields an empty list and the field is then omitted."""
    try:
        return [c for c in client.list_clients() if c.get("client_deleted_at") is None]
    except Exception:  # noqa: BLE001 - the dialog must still open
        return []


class _DefiningClientMixin:
    """Maps the defining-client combo label back to its ``CLI-NNN`` and
    pre-selects the record's current client on edit (PI-580)."""

    _clients: list[dict[str, Any]]

    def _build_request_body(self) -> dict[str, Any]:  # type: ignore[override]
        body = super()._build_request_body()  # type: ignore[misc]
        label = body.get(DEFINING_CLIENT_KEY)
        if isinstance(label, str):
            for c in self._clients:
                if client_choice_label(c) == label:
                    body[DEFINING_CLIENT_KEY] = c["client_identifier"]
                    break
        return body


class EngagementCreateDialog(_DefiningClientMixin, EntityCrudDialog):
    """Modal create-application dialog (PI-580 / REQ-653).

    Creates the engagement row read as an application: it asks for the
    client that defines it and its visibility beside the code, name,
    purpose and status. Activation/selection is a client-side context
    change handled by the Applications panel.
    """

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        self._clients = _clients_for_choice(client)
        super().__init__(
            client,
            engagement_fields_create(self._clients or None),
            mode="create",
            title="New application",
            create_method=client.create_engagement,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created engagement, or None if not accepted."""
        return self.saved_identifier()


class EngagementEditDialog(_DefiningClientMixin, EntityCrudDialog):
    """Modal edit-application dialog. ``code`` read-only with explanatory
    tooltip; the defining client and the visibility can be changed."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit application"
        self._clients = _clients_for_choice(client)
        prepared = dict(record)
        current = record.get(DEFINING_CLIENT_KEY)
        for c in self._clients:
            if c.get("client_identifier") == current:
                prepared[DEFINING_CLIENT_KEY] = client_choice_label(c)
                break
        super().__init__(
            client,
            engagement_fields_edit(self._clients or None),
            mode="edit",
            title=title,
            update_method=client.patch_engagement,
            record=prepared,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        # The code field is locked because rename requires a per-engagement
        # DB file move; that work is v0.6+.
        code_widget = self._field_widgets.get("engagement_code")
        if isinstance(code_widget, QLineEdit):
            code_widget.setToolTip(
                "Application code cannot be changed after creation."
            )
