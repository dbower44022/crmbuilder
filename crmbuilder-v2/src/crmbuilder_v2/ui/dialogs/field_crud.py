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

from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import FIELD_FORMATS, FIELD_NUMERIC_SCALES
from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._field_schema import field_fields
from crmbuilder_v2.ui.widgets.field_options_editor import FieldOptionsEditor
from crmbuilder_v2.ui.widgets.form_helpers import CollapsibleSection

_IDENTIFIER_FIELD = "field_identifier"

# PRJ-025 PI-182 §7 — the scalar intrinsic keys, in their dialog-render
# order. Built in ``_FieldIntrinsicsMixin._build_extra_body_content`` and
# read back by ``_scalar_intrinsic_values`` for the create / patch body.
_TEXT_INTRINSICS = ("field_tooltip", "field_usage_summary")
_LINE_INTRINSICS = ("field_default_value", "field_min", "field_max")
_BOOL_INTRINSICS = (
    "field_read_only",
    "field_unique",
    "field_externally_populated",
)


def _coerce_required_value(body: dict[str, Any]) -> dict[str, Any]:
    """Convert ``field_required`` string ("true"/"false") to Python bool."""
    if "field_required" in body:
        value = body["field_required"]
        if isinstance(value, str):
            body["field_required"] = value.strip().lower() == "true"
    return body


def _normalize_record_for_edit(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``record`` with ``field_required`` as the string
    the combo widget expects (``"true"``/``"false"``).

    ``field_options`` and the §7 scalar intrinsics are passed through
    untouched — the intrinsics mixin reads them straight off the record.
    """
    out = dict(record)
    raw = out.get("field_required")
    if isinstance(raw, bool):
        out["field_required"] = "true" if raw else "false"
    return out


def _normalize_options(options: list[dict[str, Any]]) -> list[tuple]:
    """Comparable form of an option list (order-sensitive)."""
    return [
        (
            o.get("option_value"),
            o.get("option_label") or None,
            o.get("option_order"),
        )
        for o in options
    ]


def _blank_combo(values) -> QComboBox:
    """Combo with a leading blank ("unset") entry then the sorted vocab."""
    combo = QComboBox()
    combo.addItem("")
    for value in sorted(values):
        combo.addItem(value)
    return combo


class _FieldIntrinsicsMixin:
    """Shared §7 intrinsic inputs + ``field_options`` editor.

    Mixed into both field dialogs. Builds the grouped, collapsed-by-
    default "Constraints, display & options" section via the
    ``EntityCrudDialog`` extra-body hook, exposes the scalar values for
    the request body, and holds the ``FieldOptionsEditor``. The scalar
    booleans are real ``QCheckBox`` widgets (this content is hand-built,
    not schema-driven, so no string-combo workaround is needed); the
    nullable text/combo intrinsics coerce empty input to ``None``.
    """

    _record: dict[str, Any]
    _mode: str

    def _build_extra_body_content(self, body_layout: QVBoxLayout) -> None:
        self._intrinsic_widgets: dict[str, QWidget] = {}
        self._options_editor = FieldOptionsEditor()

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        tooltip = QPlainTextEdit()
        tooltip.setMinimumHeight(60)
        self._intrinsic_widgets["field_tooltip"] = tooltip
        form.addRow("Tooltip", tooltip)

        usage = QPlainTextEdit()
        usage.setMinimumHeight(60)
        self._intrinsic_widgets["field_usage_summary"] = usage
        form.addRow("Usage summary", usage)

        default_value = QLineEdit()
        self._intrinsic_widgets["field_default_value"] = default_value
        form.addRow("Default value", default_value)

        fmt = _blank_combo(FIELD_FORMATS)
        self._intrinsic_widgets["field_format"] = fmt
        form.addRow("Format", fmt)

        scale = _blank_combo(FIELD_NUMERIC_SCALES)
        self._intrinsic_widgets["field_numeric_scale"] = scale
        form.addRow("Numeric scale", scale)

        max_length = QLineEdit()
        max_length.setValidator(QIntValidator(0, 1_000_000, max_length))
        self._intrinsic_widgets["field_max_length"] = max_length
        form.addRow("Max length", max_length)

        field_min = QLineEdit()
        self._intrinsic_widgets["field_min"] = field_min
        form.addRow("Min", field_min)

        field_max = QLineEdit()
        self._intrinsic_widgets["field_max"] = field_max
        form.addRow("Max", field_max)

        read_only = QCheckBox("Read-only")
        self._intrinsic_widgets["field_read_only"] = read_only
        form.addRow("", read_only)

        unique = QCheckBox("Unique")
        self._intrinsic_widgets["field_unique"] = unique
        form.addRow("", unique)

        externally_populated = QCheckBox("Externally populated")
        self._intrinsic_widgets["field_externally_populated"] = (
            externally_populated
        )
        form.addRow("", externally_populated)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(8)
        inner_layout.addLayout(form)
        options_label = QLabel("Options (enum / multi-enum)")
        options_label.setObjectName("field_options_heading")
        inner_layout.addWidget(options_label)
        inner_layout.addWidget(self._options_editor)

        self._populate_intrinsics_from_record()
        expanded = self._mode == "edit" and self._has_any_intrinsic()
        section = CollapsibleSection(
            "Constraints, display & options", inner, expanded=expanded
        )
        section.setObjectName("field_intrinsics_section")
        body_layout.addWidget(section)

        # Capture initial state for the edit-mode diff (no-op on create).
        self._initial_intrinsics = self._scalar_intrinsic_values()
        self._initial_options = self._options_editor.options()

    # ------------------------------------------------------------------
    # Value access
    # ------------------------------------------------------------------

    def _scalar_intrinsic_values(self) -> dict[str, Any]:
        w = self._intrinsic_widgets
        values: dict[str, Any] = {}
        for key in _TEXT_INTRINSICS:
            values[key] = w[key].toPlainText().strip() or None
        for key in _LINE_INTRINSICS:
            values[key] = w[key].text().strip() or None
        values["field_format"] = w["field_format"].currentText().strip() or None
        values["field_numeric_scale"] = (
            w["field_numeric_scale"].currentText().strip() or None
        )
        ml_text = w["field_max_length"].text().strip()
        values["field_max_length"] = int(ml_text) if ml_text else None
        for key in _BOOL_INTRINSICS:
            values[key] = w[key].isChecked()
        return values

    def _populate_intrinsics_from_record(self) -> None:
        r = self._record
        w = self._intrinsic_widgets
        for key in _TEXT_INTRINSICS:
            w[key].setPlainText(str(r.get(key) or ""))
        for key in _LINE_INTRINSICS:
            w[key].setText(str(r.get(key) or ""))
        self._set_combo(w["field_format"], r.get("field_format"))
        self._set_combo(w["field_numeric_scale"], r.get("field_numeric_scale"))
        ml = r.get("field_max_length")
        w["field_max_length"].setText("" if ml is None else str(ml))
        for key in _BOOL_INTRINSICS:
            w[key].setChecked(bool(r.get(key)))
        self._options_editor.set_options(r.get("field_options") or [])

    def _has_any_intrinsic(self) -> bool:
        values = self._scalar_intrinsic_values()
        if any(
            v not in (None, False) for v in values.values()
        ):
            return True
        return bool(self._options_editor.options())

    @staticmethod
    def _set_combo(combo: QComboBox, value: Any) -> None:
        text = "" if value is None else str(value)
        idx = combo.findText(text)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    # ------------------------------------------------------------------
    # Body assembly
    # ------------------------------------------------------------------

    def _augment_create_body(self, body: dict[str, Any]) -> dict[str, Any]:
        body.update(self._scalar_intrinsic_values())
        body["field_options"] = self._options_editor.options()
        return body

    def _augment_edit_diff(self, diff: dict[str, Any]) -> dict[str, Any]:
        current = self._scalar_intrinsic_values()
        for key, value in current.items():
            if value != self._initial_intrinsics.get(key):
                diff[key] = value
        current_opts = self._options_editor.options()
        if _normalize_options(current_opts) != _normalize_options(
            self._initial_options
        ):
            diff["field_options"] = current_opts
        return diff


class FieldCreateDialog(_FieldIntrinsicsMixin, EntityCrudDialog):
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
        body = _coerce_required_value(super()._build_create_body())
        return self._augment_create_body(body)

    def created_identifier(self) -> str | None:
        """Identifier of the newly created field, or None if not accepted."""
        return self.saved_identifier()


class FieldEditDialog(_FieldIntrinsicsMixin, EntityCrudDialog):
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
        diff = _coerce_required_value(super()._build_edit_diff())
        return self._augment_edit_diff(diff)


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
