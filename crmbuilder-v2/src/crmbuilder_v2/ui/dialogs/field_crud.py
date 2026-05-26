"""Field create / edit / delete dialogs (v0.5+, PI-004 first slice).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases, following the v0.4 methodology-entity
pattern and mirroring ``entity_crud.py``. The declarative field schema
lives in ``_field_schema.py``.

* ``FieldCreateDialog`` — create mode; ``field_identifier`` is not
  shown (server-assigned). Status defaults to ``candidate``; type
  defaults to ``text``; required defaults to ``false``. The
  parent-entity picker is REQUIRED per ``field.md`` §3.5.4 — the
  dialog POSTs ``field_belongs_to_entity_identifier`` along with the
  field row and the access layer creates the row + edge atomically.
* ``FieldEditDialog`` — edit mode; ``field_identifier`` read-only;
  parent-entity NOT in the schema (re-parenting per spec §3.6.5 /
  PI-053 is deferred to a follow-on slice). Saves via PATCH (the base
  computes a partial diff); the status combo is restricted to valid
  successors by the schema's ``compute_options``.
* ``FieldDeleteDialog`` — edge-text confirmation per ``field.md``
  §3.6.6: the Delete button stays disabled until the operator types
  the ``FLD-NNN`` identifier exactly. Confirmation soft-deletes the
  field and atomically detaches the parent-entity edge.

The ``field_required`` schema entry is modelled as a string combo
over ``("false", "true")`` because the EntityCrudDialog base supports
only string-valued widgets. Both subclasses override the
request-body construction to coerce these strings to Python booleans
before submitting.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._field_schema import field_fields

_IDENTIFIER_FIELD = "field_identifier"


def _coerce_required_value(body: dict[str, Any]) -> dict[str, Any]:
    """Convert ``field_required`` string ("true"/"false") to Python bool."""
    if "field_required" in body:
        value = body["field_required"]
        if isinstance(value, str):
            body["field_required"] = value.strip().lower() == "true"
    return body


def _normalize_record_for_edit(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``record`` with ``field_required`` as the string
    the combo widget expects (``"true"``/``"false"``)."""
    out = dict(record)
    raw = out.get("field_required")
    if isinstance(raw, bool):
        out["field_required"] = "true" if raw else "false"
    return out


class FieldCreateDialog(EntityCrudDialog):
    """Modal create-field dialog. Per ``field.md`` §3.6.4."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            field_fields(
                include_identifier=False,
                include_parent_entity=True,
                client=client,
            ),
            mode="create",
            title="New field",
            create_method=client.create_field,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def _build_create_body(self) -> dict[str, Any]:  # type: ignore[override]
        body = super()._build_create_body()
        return _coerce_required_value(body)

    def created_identifier(self) -> str | None:
        """Identifier of the newly created field, or None if not accepted."""
        return self.saved_identifier()


class FieldEditDialog(EntityCrudDialog):
    """Modal edit-field dialog. Per ``field.md`` §3.6.5."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit field"
        normalised = _normalize_record_for_edit(record)
        super().__init__(
            client,
            field_fields(
                include_identifier=True,
                include_parent_entity=False,
            ),
            mode="edit",
            title=title,
            update_method=client.patch_field,
            record=normalised,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def _build_edit_diff(self) -> dict[str, Any]:  # type: ignore[override]
        diff = super()._build_edit_diff()
        return _coerce_required_value(diff)


class FieldDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a field. Per ``field.md`` §3.6.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation: the
    Delete button is disabled until the operator types the field's
    ``FLD-NNN`` identifier exactly into the confirmation field.
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
            client.delete_field,
            entity_label="field",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(unnamed)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "field and atomically detaches its parent-entity edge; both "
            "are restored together when the field is restored from the "
            "Show-deleted view."
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
