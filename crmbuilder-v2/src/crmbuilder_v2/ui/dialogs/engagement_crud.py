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

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._engagement_schema import (
    engagement_fields_create,
    engagement_fields_edit,
)

_IDENTIFIER_FIELD = "engagement_identifier"


class EngagementCreateDialog(EntityCrudDialog):
    """Modal create-engagement dialog (slice C — engagement row only).

    Per ``engagement.md`` §3.6.3. Creates the engagement registry row;
    activation/selection is a client-side context change handled by the
    Engagements panel.
    """

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            engagement_fields_create(),
            mode="create",
            title="New engagement",
            create_method=client.create_engagement,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created engagement, or None if not accepted."""
        return self.saved_identifier()


class EngagementEditDialog(EntityCrudDialog):
    """Modal edit-engagement dialog. ``code`` read-only with explanatory tooltip."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit engagement"
        super().__init__(
            client,
            engagement_fields_edit(),
            mode="edit",
            title=title,
            update_method=client.patch_engagement,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        # The code field is locked because rename requires a per-engagement
        # DB file move; that work is v0.6+.
        code_widget = self._field_widgets.get("engagement_code")
        if isinstance(code_widget, QLineEdit):
            code_widget.setToolTip(
                "Engagement code cannot be changed after creation."
            )
