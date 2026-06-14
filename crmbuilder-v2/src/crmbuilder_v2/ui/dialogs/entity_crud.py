"""Entity create / edit / delete dialogs (UI v0.4 slice C).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases, following the v0.3 governance-entity
pattern and mirroring ``domain_crud.py``. The declarative field schema
lives in ``_entity_schema.py``.

* ``EntityCreateDialog`` — create mode; ``entity_identifier`` is not
  shown (server-assigned). Status defaults to ``candidate``. Per
  DEC-067's create-then-attach flow the dialog creates the entity
  record only — there is no domain-affiliation multi-select; the user
  attaches ``entity_scopes_to_domain`` references from the detail
  pane's "Add reference" affordance after the record exists.
* ``EntityEditDialog`` — edit mode; ``entity_identifier`` read-only.
  Saves via PATCH (the base computes a partial diff); the status combo
  is restricted to valid successors by the schema's ``compute_options``.
* ``EntityDeleteDialog`` — edge-text confirmation (``entity.md``
  section 3.6.6): the Delete button stays disabled until the operator
  types the ``ENT-NNN`` identifier exactly. Confirmation soft-deletes;
  outbound ``entity_scopes_to_domain`` references persist per spec
  section 3.4.6.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._entity_schema import entity_fields

_IDENTIFIER_FIELD = "entity_identifier"


def _coerce_track_activity(body: dict[str, Any]) -> dict[str, Any]:
    """Convert ``entity_track_activity`` string ("true"/"false") to bool.

    The PRJ-025 PI-182 §6 ``entity_track_activity`` intrinsic is modelled
    as a string combo (the EntityCrudDialog base only supports string
    widgets); the access layer expects a Python bool. Mirrors the
    ``field_required`` coercion in ``field_crud.py``."""
    if "entity_track_activity" in body:
        value = body["entity_track_activity"]
        if isinstance(value, str):
            body["entity_track_activity"] = value.strip().lower() == "true"
    return body


class EntityCreateDialog(EntityCrudDialog):
    """Modal create-entity dialog. Per ``entity.md`` section 3.6.4."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            entity_fields(include_identifier=False),
            mode="create",
            title="New entity",
            create_method=client.create_entity,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def _build_create_body(self) -> dict[str, Any]:  # type: ignore[override]
        return _coerce_track_activity(super()._build_create_body())

    def created_identifier(self) -> str | None:
        """Identifier of the newly created entity, or None if not accepted."""
        return self.saved_identifier()


class EntityEditDialog(EntityCrudDialog):
    """Modal edit-entity dialog. Per ``entity.md`` section 3.6.5."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit entity"
        normalised = dict(record)
        raw = normalised.get("entity_track_activity")
        if isinstance(raw, bool):
            normalised["entity_track_activity"] = "true" if raw else "false"
        super().__init__(
            client,
            entity_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_entity,
            record=normalised,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def _build_edit_diff(self) -> dict[str, Any]:  # type: ignore[override]
        return _coerce_track_activity(super()._build_edit_diff())


class EntityDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting an entity. Per ``entity.md`` 3.6.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation: the
    Delete button is disabled until the operator types the entity's
    ``ENT-NNN`` identifier exactly into the confirmation field.
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
            client.delete_entity,
            entity_label="entity",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "entity; it can be restored from the Show-deleted view. Any "
            "domain affiliations are kept."
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
