"""Manual config create / edit / delete dialogs (PI-004 cohort, v0.5+).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases, following the v0.3 governance-entity
pattern and mirroring ``requirement_crud.py``. The declarative field
schema lives in ``_manual_config_schema.py``.

* ``ManualConfigCreateDialog`` — create mode; ``manual_config_identifier``
  is not shown (server-assigned). Status defaults to ``candidate``.
  Per spec §3.6.4's create-then-attach flow the dialog creates the
  manual_config record only — there are no reference multi-selects;
  the user attaches references via the detail pane's "Add reference"
  affordance after the record exists.
* ``ManualConfigEditDialog`` — edit mode; ``manual_config_identifier``
  read-only. Saves via PATCH; the status combo is restricted to valid
  successors by the schema's ``compute_options``. Transitioning into
  ``completed`` without populating ``manual_config_completed_by``
  surfaces the dedicated 422 inline (status-combo-driven Mark-Completed
  UX per spec §3.6.5; dedicated button alternative deferred per §3.8.1).
* ``ManualConfigDeleteDialog`` — edge-text confirmation per spec
  §3.6.6: the Delete button stays disabled until the operator types
  the ``MCF-NNN`` identifier exactly. Confirmation soft-deletes;
  outbound references persist per spec §3.4.6.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._manual_config_schema import (
    manual_config_fields,
)

_IDENTIFIER_FIELD = "manual_config_identifier"


class ManualConfigCreateDialog(EntityCrudDialog):
    """Modal create-manual_config dialog. Per ``manual_config.md`` §3.6.4."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            manual_config_fields(include_identifier=False),
            mode="create",
            title="New manual config",
            create_method=client.create_manual_config,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created manual_config, or None."""
        return self.saved_identifier()


class ManualConfigEditDialog(EntityCrudDialog):
    """Modal edit-manual_config dialog. Per ``manual_config.md`` §3.6.5."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = (
            f"Edit {identifier}" if identifier else "Edit manual config"
        )
        super().__init__(
            client,
            manual_config_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_manual_config,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class ManualConfigDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a manual_config. Per spec §3.6.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation: the
    Delete button is disabled until the operator types the manual_config's
    ``MCF-NNN`` identifier exactly into the confirmation field.
    """

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
            client.delete_manual_config,
            entity_label="manual_config",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes "
            "the manual config; it can be restored from the Show-deleted "
            "view. All outbound references are kept."
        )
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setObjectName("delete_confirm_edit")
        self._confirm_edit.setPlaceholderText(identifier)
        self._confirm_edit.textChanged.connect(self._on_confirm_text_changed)
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            # Insert just above the Cancel/Delete button row (the last
            # item the base added).
            layout.insertWidget(layout.count() - 1, self._confirm_edit)
        self._delete_btn.setEnabled(False)

    def _on_confirm_text_changed(self, text: str) -> None:
        self._delete_btn.setEnabled(text.strip() == self._identifier)
