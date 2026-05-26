"""Process create / edit / delete dialogs (UI v0.4 slice D).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases, following the v0.3 governance-entity
pattern and mirroring ``domain_crud.py`` / ``entity_crud.py``. The
declarative field schema lives in ``_process_schema.py``.

Two process-specific behaviors are wired here on top of the base:

* **Dynamic classification-rationale placeholder.** Per ``process.md``
  section 3.6.3/3.6.4 the ``process_classification_rationale`` field's
  placeholder text changes with the selected ``process_classification``
  value. The base ``FieldSchema`` carries only a static placeholder, so
  both create and edit dialogs connect the classification combo's
  ``currentTextChanged`` to a placeholder update.

* **Edit-mode domain-picker value restoration.** The base populates
  fields from the record *before* ``compute_options`` runs, so the
  ``process_domain_identifier`` ``identifier_picker`` has no entries yet
  when its value is first set and the value is dropped when entries
  land. ``ProcessEditDialog`` re-applies the value after ``super()``
  (entries now populated) and corrects the edit-diff baseline — the
  same after-the-cascade pattern ``ReferenceCreateDialog`` uses for its
  pre-populated source.

* ``ProcessCreateDialog`` — create mode; ``process_identifier`` is not
  shown (server-assigned). ``process_classification`` defaults to
  ``unclassified``; the domain picker defaults to the first live domain
  alphabetically. Per DEC-067's create-then-attach flow the dialog
  creates the process record only — handoffs attach from the detail
  pane afterward.
* ``ProcessEditDialog`` — edit mode; ``process_identifier`` read-only.
  Saves via PATCH; the classification combo is restricted to valid
  successors by the schema's ``compute_options``.
* ``ProcessDeleteDialog`` — edge-text confirmation (``process.md``
  section 3.6.6): the Delete button stays disabled until the operator
  types the ``PROC-NNN`` identifier exactly. Confirmation soft-deletes;
  inbound and outbound handoff references persist per spec 3.4.5.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._process_schema import (
    CLASSIFICATION_RATIONALE_PLACEHOLDERS,
    process_fields,
)

_IDENTIFIER_FIELD = "process_identifier"
_CLASSIFICATION_FIELD = "process_classification"
_RATIONALE_FIELD = "process_classification_rationale"


def _wire_dynamic_rationale_placeholder(dialog: EntityCrudDialog) -> None:
    """Bind the rationale placeholder to the classification combo.

    Per ``process.md`` section 3.6.3 the
    ``process_classification_rationale`` placeholder varies by the
    currently-selected ``process_classification``. The base dialog
    carries only a static placeholder, so we connect the combo's
    ``currentTextChanged`` signal here and seed the initial value.
    """
    combo = dialog._field_widgets.get(_CLASSIFICATION_FIELD)
    rationale = dialog._field_widgets.get(_RATIONALE_FIELD)
    if not isinstance(combo, QComboBox) or not isinstance(
        rationale, QPlainTextEdit
    ):
        return

    def _update(classification: str) -> None:
        placeholder = CLASSIFICATION_RATIONALE_PLACEHOLDERS.get(
            classification.strip(),
            CLASSIFICATION_RATIONALE_PLACEHOLDERS["unclassified"],
        )
        rationale.setPlaceholderText(placeholder)

    combo.currentTextChanged.connect(_update)
    _update(combo.currentText())


class ProcessCreateDialog(EntityCrudDialog):
    """Modal create-process dialog. Per ``process.md`` section 3.6.4."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            process_fields(client, include_identifier=False),
            mode="create",
            title="New process",
            create_method=client.create_process,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        _wire_dynamic_rationale_placeholder(self)

    def created_identifier(self) -> str | None:
        """Identifier of the newly created process, or None if not accepted."""
        return self.saved_identifier()


class ProcessEditDialog(EntityCrudDialog):
    """Modal edit-process dialog. Per ``process.md`` section 3.6.5 and
    ``process-v2.md`` §3.6.5 — grows by including editors for the six
    Phase 3 content fields (v0.8, PI-005) in addition to the v0.4
    fields."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit process"
        super().__init__(
            client,
            process_fields(
                client, include_identifier=True, include_phase3=True
            ),
            mode="edit",
            title=title,
            update_method=client.patch_process,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        # The base populated the domain picker before its cascade ran,
        # so the value was dropped when ``set_entries`` landed. Re-apply
        # it now that the picker has entries, and correct the edit-diff
        # baseline so an unchanged domain isn't reported as a change.
        domain_id = str(record.get("process_domain_identifier") or "")
        if domain_id:
            schema = self._fields_by_key["process_domain_identifier"]
            self._set_widget_value(schema, domain_id)
            self._initial["process_domain_identifier"] = domain_id
        _wire_dynamic_rationale_placeholder(self)


class ProcessDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a process. Per ``process.md`` 3.6.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation: the
    Delete button is disabled until the operator types the process's
    ``PROC-NNN`` identifier exactly into the confirmation field.
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
            client.delete_process,
            entity_label="process",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "process; it can be restored from the Show-deleted view. Any "
            "handoff references are kept."
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
