"""Schema-driven CRUD dialog base classes.

Per DEC-028, v0.2 introduces shared dialog base classes so each entity's
create/edit/delete dialogs are declarative — a list of ``FieldSchema``
descriptors plus a few callbacks — rather than 200-line orchestrations
of widget construction, validation, error envelope handling, and worker
plumbing.

Two base classes:

* ``EntityCrudDialog`` — modal form for create or edit. Builds widgets
  from the field schema, manages inline error labels, runs Save through
  a worker, parses the API's error envelope, and (in edit mode)
  computes a partial PATCH body containing only the fields whose values
  differ from the initial record.

* ``EntityCrudDeleteDialog`` — confirmation modal for delete. Calls the
  provided ``delete_method`` through a worker. Soft-delete-aware: a
  ``ConflictError`` routes to the generic ``ErrorDialog`` as a defensive
  fallback (the v0.1 slice H pattern); ``NotFoundError`` is treated as
  already-deleted and accepts.

Five widget types are supported in this iteration:

* ``"line"`` — ``QLineEdit``.
* ``"text"`` — multi-line ``QPlainTextEdit``.
* ``"combo"`` — ``QComboBox`` populated from a vocab frozenset.
* ``"date"`` — the ``DateField`` widget from ``ui.widgets.date_field``.
* ``"tree_picker"`` — a button that opens ``HierarchicalEntityPicker``
  on click; the button text reflects the current selection.

Slice A migrates v0.1's three decisions dialogs onto the
EntityCrudDialog/EntityCrudDeleteDialog bases without behavior change.
Slices B/C/D introduce risks/planning_items/topics dialogs as further
users; slice E delivers the parallel ``VersionedReplaceDialog`` for
charter and status.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    NotFoundError,
    RequestShapeError,
    StorageClientError,
    StorageConnectionError,
    ValidationError,
)
from crmbuilder_v2.ui.widgets.date_field import DateField
from crmbuilder_v2.ui.widgets.entity_identifier_picker import EntityIdentifierPicker
from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker

_log = logging.getLogger("crmbuilder_v2.ui.base.crud_dialog")

_LONG_TEXT_MIN_HEIGHT = 80
_INLINE_ERROR_STYLE = "color: #B22222;"
_READ_ONLY_STYLE = "color: #666; background: #f4f4f4;"

WidgetKind = Literal["line", "text", "combo", "date", "tree_picker", "identifier_picker"]
DialogMode = Literal["create", "edit"]


@dataclass
class FieldSchema:
    """Declarative descriptor for a single form field.

    Attributes:

    * ``key`` — the field name used in API request bodies. Becomes the
      attribute name used to look up the field's widget.
    * ``label`` — UI label.
    * ``widget`` — one of the WidgetKind values; selects the widget
      type the base will construct.
    * ``required`` — required-field check fires before format validation.
    * ``placeholder`` — placeholder text on line/date widgets.
    * ``vocab`` — for combo widgets, the set of allowed values.
    * ``default`` — for combo widgets, the value to pre-select on Create.
    * ``regex`` — client-side format validator that runs after the
      required-field check passes.
    * ``regex_hint`` — error message rendered inline when the regex
      check fails.
    * ``read_only_on_edit`` — field becomes ``setReadOnly(True)`` on
      Edit mode (typically the identifier).
    * ``read_only`` — field becomes ``setReadOnly(True)`` regardless
      of mode. Used for fields that the dialog auto-assigns and the
      user must not edit (e.g. an auto-generated identifier in a
      create-only dialog). Applies to ``line`` and ``text`` widgets.
    * ``record_field_for_edit`` — when an Edit-mode record carries the
      field's value under a different key (e.g., the decision's
      ``supersedes_identifier`` for a ``supersedes`` field), specify
      the record key here.
    * ``omit_when_empty_in_create`` — when True, an empty value is
      excluded from the create-mode request body. Used for optional
      foreign-key fields where empty means "not set."
    * ``strip_before_compare`` — when True (default), leading/trailing
      whitespace is stripped before computing the Edit-mode diff.
    * ``tree_picker_data`` — callable returning the picker's node list
      (only consulted for widget="tree_picker").
    * ``tree_picker_filter`` — callable returning a selectable
      predicate; consulted on Edit, defaults to "all selectable" on
      Create.
    * ``tree_picker_title`` — picker dialog title.
    * ``depends_on`` — keys of upstream fields whose values feed this
      field's options. v0.3 slice C: when any upstream field changes,
      ``compute_options`` is invoked and the widget's options are
      replaced. If any upstream field has an empty value, this field
      is disabled and its current selection cleared.
    * ``compute_options`` — callable taking the current form-state dict
      (``{field_key: current_value}``) and returning the field's options.
      For ``combo`` widgets the return is ``list[str]``; for
      ``identifier_picker`` widgets it is ``list[tuple[str, str]]``
      ``(identifier, title)``. Read at dialog-open time and on every
      upstream-change event so vocab evolution is picked up without
      UI changes.
    """

    key: str
    label: str
    widget: WidgetKind
    required: bool = False
    placeholder: str | None = None
    vocab: frozenset[str] | None = None
    default: str | None = None
    regex: re.Pattern[str] | None = None
    regex_hint: str | None = None
    read_only_on_edit: bool = False
    read_only: bool = False
    record_field_for_edit: str | None = None
    omit_when_empty_in_create: bool = False
    strip_before_compare: bool = True
    tree_picker_data: Callable[[StorageClient], list[HierarchicalEntityPicker.Node]] | None = None
    tree_picker_filter: (
        Callable[[StorageClient, dict | None], Callable[[HierarchicalEntityPicker.Node], bool]]
        | None
    ) = None
    tree_picker_title: str = "Select"
    depends_on: list[str] | None = None
    compute_options: Callable[[dict[str, str]], list[Any]] | None = None


# ---------------------------------------------------------------------------
# Form construction helpers
# ---------------------------------------------------------------------------


def _make_inline_error() -> QLabel:
    label = QLabel("")
    label.setStyleSheet(_INLINE_ERROR_STYLE)
    label.setWordWrap(True)
    label.setVisible(False)
    return label


def _wrap_with_error(input_widget: QWidget, error_label: QLabel) -> QWidget:
    """Pair a form input with its inline-error label in a vertical container."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.addWidget(input_widget)
    layout.addWidget(error_label)
    return container


class FormWidgets:
    """Adapter that exposes the form widgets as both dict and attribute.

    Internal callers use ``self._widgets[key]`` (dict lookup); the v0.1
    decision-dialog tests use ``self._widgets.identifier`` and
    ``self._widgets.value_for("identifier")``. The adapter satisfies
    both shapes, plus a small set of value/error helpers preserved from
    the v0.1 ``DecisionFormWidgets`` dataclass.
    """

    def __init__(
        self,
        widgets: dict[str, QWidget],
        error_labels: dict[str, QLabel],
        *,
        tree_picker_selections: dict[str, str | None] | None = None,
    ) -> None:
        self._widgets = widgets
        self._error_labels = error_labels
        self._tree_picker_selections = tree_picker_selections or {}

    # Dict-style.
    def __getitem__(self, key: str) -> QWidget:
        return self._widgets[key]

    def __setitem__(self, key: str, widget: QWidget) -> None:
        self._widgets[key] = widget

    def __contains__(self, key: object) -> bool:
        return key in self._widgets

    def keys(self):
        return self._widgets.keys()

    # Attribute-style. ``__getattr__`` is only consulted when normal
    # attribute lookup fails, so the explicit attributes above (and any
    # method names) are not shadowed.
    def __getattr__(self, name: str) -> QWidget:
        if name.startswith("_"):
            raise AttributeError(name)
        widgets = self.__dict__.get("_widgets") or {}
        if name in widgets:
            return widgets[name]
        raise AttributeError(name)

    @property
    def error_labels(self) -> dict[str, QLabel]:
        return self._error_labels

    def widget_for(self, field: str) -> QWidget | None:
        return self._widgets.get(field)

    def value_for(self, field: str) -> str:
        widget = self._widgets.get(field)
        if widget is None:
            return self._tree_picker_selections.get(field) or ""
        if isinstance(widget, EntityIdentifierPicker):
            return widget.selected_identifier() or ""
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, DateField):
            return widget.date_text()
        if isinstance(widget, QPushButton):
            # tree_picker selection is tracked separately.
            return self._tree_picker_selections.get(field) or ""
        return ""

    def set_value(self, field: str, value: str) -> None:
        widget = self._widgets.get(field)
        if widget is None:
            return
        if isinstance(widget, EntityIdentifierPicker):
            for index in range(widget.count()):
                if widget.itemData(index) == value:
                    widget.setCurrentIndex(index)
                    return
            widget.setEditText(value)
            return
        if isinstance(widget, QLineEdit):
            widget.setText(value)
            return
        if isinstance(widget, QPlainTextEdit):
            widget.setPlainText(value)
            return
        if isinstance(widget, QComboBox):
            idx = widget.findText(value)
            if idx >= 0:
                widget.setCurrentIndex(idx)
            else:
                widget.setEditText(value)
            return
        if isinstance(widget, DateField):
            widget.set_date(value)
            return
        if isinstance(widget, QPushButton):
            self._tree_picker_selections[field] = value or None
            widget.setText(value if value else "(no selection)")

    def show_error(self, field: str, message: str) -> None:
        label = self._error_labels.get(field)
        if label is None:
            return
        label.setText(message)
        label.setVisible(True)

    def clear_error(self, field: str) -> None:
        label = self._error_labels.get(field)
        if label is None:
            return
        label.setText("")
        label.setVisible(False)

    def clear_all_errors(self) -> None:
        for field_key in self._error_labels:
            self.clear_error(field_key)


# ---------------------------------------------------------------------------
# EntityCrudDialog
# ---------------------------------------------------------------------------


class EntityCrudDialog(QDialog):
    """Schema-driven create/edit dialog.

    The dialog renders a ``QFormLayout`` from the supplied field schema,
    manages inline error labels, wires Save to a worker that calls the
    appropriate client method (``create_method`` on Create,
    ``update_method`` on Edit), and routes API errors per the standard
    matrix:

    * ``ValidationError`` with field-keyed errors → inline; field-less
      errors → ``ErrorDialog``.
    * ``ConflictError`` → inline on the identifier field if the schema
      has one with ``key="identifier"``; otherwise ``ErrorDialog``.
    * ``NotFoundError`` (Edit only) → ``ErrorDialog`` with a
      "deleted while open" message, then accepts so the panel refreshes.
    * ``StorageConnectionError`` → ``self.reject()`` (the main window's
      crash banner takes over).
    * Any other ``StorageClientError`` → ``ErrorDialog``.
    """

    def __init__(
        self,
        client: StorageClient,
        fields: list[FieldSchema],
        *,
        mode: DialogMode,
        title: str,
        create_method: Callable[[dict], dict] | None = None,
        update_method: Callable[[str, dict], dict] | None = None,
        record: dict[str, Any] | None = None,
        identifier_field: str = "identifier",
        identifier_value: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if mode == "create" and create_method is None:
            raise ValueError("EntityCrudDialog mode='create' requires create_method")
        if mode == "edit" and update_method is None:
            raise ValueError("EntityCrudDialog mode='edit' requires update_method")
        if mode == "edit" and record is None:
            raise ValueError("EntityCrudDialog mode='edit' requires record")

        self._client = client
        self._fields = list(fields)
        self._fields_by_key = {f.key: f for f in self._fields}
        self._mode: DialogMode = mode
        self._record: dict[str, Any] = dict(record) if record is not None else {}
        self._create_method = create_method
        self._update_method = update_method
        self._identifier_field = identifier_field
        if identifier_value is not None:
            self._identifier_value = identifier_value
        else:
            self._identifier_value = str(self._record.get(identifier_field) or "")
        self._saved_identifier: str | None = None
        self._initial: dict[str, str] = {}
        self._tree_picker_selections: dict[str, str | None] = {}
        self._error_labels: dict[str, QLabel] = {}
        self._field_widgets: dict[str, QWidget] = {}
        self._widgets = FormWidgets(
            self._field_widgets,
            self._error_labels,
            tree_picker_selections=self._tree_picker_selections,
        )
        self._worker = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        self._form = QFormLayout()
        self._form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        for schema in self._fields:
            widget = self._build_input(schema)
            error_label = _make_inline_error()
            self._error_labels[schema.key] = error_label
            self._widgets[schema.key] = widget
            self._wire_clear_on_change(schema, widget)
            self._form.addRow(schema.label, _wrap_with_error(widget, error_label))
        outer.addLayout(self._form)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)
        self._save_btn = QPushButton("Save")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save_clicked)
        button_row.addWidget(self._save_btn)
        outer.addLayout(button_row)

        if self._mode == "edit":
            self._populate_from_record()
            self._record_initial_values()
        else:
            self._record_initial_values()

        # Wire cascading dependencies (v0.3 slice C — DEC-033). When any
        # upstream field changes, downstream fields with ``depends_on``
        # repopulate via ``compute_options``. Initial population runs
        # once now so pre-populated source values feed the dependent
        # fields immediately.
        self._wire_cascade()
        self._refresh_dependent_fields()

        self._set_initial_focus()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def saved_identifier(self) -> str | None:
        return self._saved_identifier

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_input(self, schema: FieldSchema) -> QWidget:
        if schema.widget == "line":
            widget = QLineEdit()
            if schema.placeholder:
                widget.setPlaceholderText(schema.placeholder)
            if self._mode == "create" and schema.default:
                widget.setText(schema.default)
            if schema.read_only or (
                self._mode == "edit" and schema.read_only_on_edit
            ):
                widget.setReadOnly(True)
                widget.setStyleSheet(_READ_ONLY_STYLE)
            return widget

        if schema.widget == "text":
            widget = QPlainTextEdit()
            widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
            if schema.placeholder:
                widget.setPlaceholderText(schema.placeholder)
            if schema.read_only:
                widget.setReadOnly(True)
                widget.setStyleSheet(_READ_ONLY_STYLE)
            return widget

        if schema.widget == "combo":
            widget = QComboBox()
            vocab = sorted(schema.vocab or ())
            for value in vocab:
                widget.addItem(value)
            if self._mode == "create" and schema.default and schema.default in (schema.vocab or set()):
                idx = widget.findText(schema.default)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            return widget

        if schema.widget == "date":
            widget = DateField()
            return widget

        if schema.widget == "tree_picker":
            widget = QPushButton("(no selection)")
            widget.setProperty("schema_key", schema.key)
            widget.clicked.connect(
                lambda _checked=False, k=schema.key: self._on_tree_picker_clicked(k)
            )
            self._tree_picker_selections[schema.key] = None
            return widget

        if schema.widget == "identifier_picker":
            widget = EntityIdentifierPicker()
            if schema.placeholder:
                widget.lineEdit().setPlaceholderText(schema.placeholder)
            return widget

        raise ValueError(f"Unsupported widget kind: {schema.widget}")

    def _wire_clear_on_change(self, schema: FieldSchema, widget: QWidget) -> None:
        """Clear the inline error label when the user starts editing a field."""
        key = schema.key

        def clear(_payload=None, k=key) -> None:
            self._clear_error(k)

        if isinstance(widget, EntityIdentifierPicker):
            # Order matters: this isinstance must come before the
            # QComboBox check below, since EntityIdentifierPicker
            # inherits from QComboBox.
            widget.editTextChanged.connect(clear)
            widget.selection_changed.connect(lambda _id=None, _k=key: self._clear_error(_k))
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(clear)
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(clear)
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(clear)
        elif isinstance(widget, DateField):
            widget.dateChanged.connect(clear)
        # tree_picker buttons clear their error when a selection is made;
        # see _on_tree_picker_clicked.

    def _set_initial_focus(self) -> None:
        # On Create: focus the identifier field if present, else the
        # first non-readonly widget. On Edit: focus the first editable
        # field (typically title since identifier is read-only).
        for schema in self._fields:
            if self._mode == "edit" and schema.read_only_on_edit:
                continue
            widget = self._widgets[schema.key]
            if isinstance(widget, (QLineEdit, QPlainTextEdit, QComboBox, DateField)):
                widget.setFocus(Qt.FocusReason.OtherFocusReason)
                return

    # ------------------------------------------------------------------
    # Pre-population (Edit mode)
    # ------------------------------------------------------------------

    def _populate_from_record(self) -> None:
        for schema in self._fields:
            record_key = schema.record_field_for_edit or schema.key
            raw = self._record.get(record_key)
            value = "" if raw is None else str(raw)
            self._set_widget_value(schema, value)

    def _record_initial_values(self) -> None:
        for schema in self._fields:
            self._initial[schema.key] = self._current_value(schema)

    # ------------------------------------------------------------------
    # Widget value access
    # ------------------------------------------------------------------

    def _current_value(self, schema: FieldSchema) -> str:
        widget = self._widgets[schema.key]
        if isinstance(widget, EntityIdentifierPicker):
            # EntityIdentifierPicker inherits from QComboBox; check
            # first so we get the resolved identifier, not the visible
            # display text.
            return widget.selected_identifier() or ""
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, DateField):
            return widget.date_text()
        if schema.widget == "tree_picker":
            return self._tree_picker_selections.get(schema.key) or ""
        return ""

    def _set_widget_value(self, schema: FieldSchema, value: str) -> None:
        widget = self._widgets[schema.key]
        if isinstance(widget, EntityIdentifierPicker):
            # If the value matches a known entry's identifier, select it;
            # otherwise treat it as free-text in the editable line edit.
            for index in range(widget.count()):
                if widget.itemData(index) == value:
                    widget.setCurrentIndex(index)
                    return
            widget.setEditText(value)
            return
        if isinstance(widget, QLineEdit):
            widget.setText(value)
            return
        if isinstance(widget, QPlainTextEdit):
            widget.setPlainText(value)
            return
        if isinstance(widget, QComboBox):
            idx = widget.findText(value)
            if idx >= 0:
                widget.setCurrentIndex(idx)
            else:
                widget.setEditText(value)
            return
        if isinstance(widget, DateField):
            widget.set_date(value)
            return
        if schema.widget == "tree_picker":
            self._tree_picker_selections[schema.key] = value or None
            self._update_tree_picker_label(schema.key, value)
            return

    # ------------------------------------------------------------------
    # Cascading dependencies (v0.3 slice C — DEC-033)
    # ------------------------------------------------------------------

    def _wire_cascade(self) -> None:
        """Subscribe each ``depends_on`` field to its upstream signals.

        When an upstream field changes, all dependents repopulate via
        :meth:`_refresh_dependent_fields`. Identifier-picker upstreams
        emit ``selection_changed`` on item activation; combo upstreams
        emit ``currentTextChanged`` on any selection change. The
        downstream-update path is deliberately broad: any change anywhere
        upstream re-runs every dependent ``compute_options``. The total
        work is small (the form has only a handful of fields).
        """
        for schema in self._fields:
            if not schema.depends_on:
                continue
            for upstream_key in schema.depends_on:
                upstream = self._widgets.get(upstream_key) if hasattr(
                    self._widgets, "get"
                ) else self._field_widgets.get(upstream_key)
                if upstream is None:
                    _log.warning(
                        "Field %s depends on unknown upstream %s",
                        schema.key,
                        upstream_key,
                    )
                    continue
                if isinstance(upstream, EntityIdentifierPicker):
                    upstream.selection_changed.connect(
                        lambda _id=None: self._refresh_dependent_fields()
                    )
                    upstream.editTextChanged.connect(
                        lambda _t=None: self._refresh_dependent_fields()
                    )
                elif isinstance(upstream, QComboBox):
                    upstream.currentTextChanged.connect(
                        lambda _t=None: self._refresh_dependent_fields()
                    )

    def _refresh_dependent_fields(self) -> None:
        """Re-run ``compute_options`` for every field that has it.

        For fields with ``depends_on`` upstream keys: disable and clear
        if any upstream is empty; populate and enable if all upstreams
        have values. For fields with ``compute_options`` but no
        ``depends_on`` (or an empty list): populate unconditionally —
        the field is dynamic but has no gating dependencies.

        The form state is re-snapshotted inside the loop so each
        field sees its upstream's just-populated value. The schema
        list order is topological by convention (every field's
        ``depends_on`` references only earlier-listed fields), so a
        single forward pass is sufficient.
        """
        for schema in self._fields:
            if schema.compute_options is None:
                continue
            widget = self._field_widgets.get(schema.key)
            if widget is None:
                continue
            state = self._form_state()
            depends = schema.depends_on or []
            upstream_complete = all(
                bool(state.get(upstream_key, "").strip())
                for upstream_key in depends
            )
            if depends and not upstream_complete:
                self._set_field_enabled(schema, False)
                self._clear_widget_options(schema)
                continue
            try:
                options = schema.compute_options(state)
            except Exception:  # noqa: BLE001 — UI affordance; degrade to disabled
                _log.exception(
                    "compute_options failed for field %s", schema.key
                )
                self._set_field_enabled(schema, False)
                self._clear_widget_options(schema)
                continue
            self._populate_widget_options(schema, options)
            self._set_field_enabled(schema, True)

    def _set_field_enabled(self, schema: FieldSchema, enabled: bool) -> None:
        widget = self._field_widgets.get(schema.key)
        if widget is None:
            return
        widget.setEnabled(enabled)

    def _clear_widget_options(self, schema: FieldSchema) -> None:
        widget = self._field_widgets.get(schema.key)
        if widget is None:
            return
        with QSignalBlocker(widget):
            if isinstance(widget, EntityIdentifierPicker):
                widget.set_entries([])
            elif isinstance(widget, QComboBox):
                widget.clear()

    def _populate_widget_options(
        self, schema: FieldSchema, options: list[Any]
    ) -> None:
        widget = self._field_widgets.get(schema.key)
        if widget is None:
            return
        # Block signals while we mutate the model so cascade-driven
        # repopulation does not fire ``currentTextChanged`` /
        # ``editTextChanged`` storms that re-trigger ``_refresh_-
        # dependent_fields`` recursively. The blocker auto-restores
        # signal state when the ``with`` block exits.
        with QSignalBlocker(widget):
            if isinstance(widget, EntityIdentifierPicker):
                entries: list[tuple[str, str]] = []
                for opt in options:
                    if isinstance(opt, tuple) and len(opt) >= 2:
                        entries.append((str(opt[0]), str(opt[1])))
                    elif isinstance(opt, str):
                        entries.append((opt, ""))
                current = widget.selected_identifier()
                widget.set_entries(entries)
                if current is not None:
                    self._set_widget_value(schema, current)
            elif isinstance(widget, QComboBox):
                current = widget.currentText()
                widget.clear()
                for opt in options:
                    widget.addItem(str(opt))
                if current:
                    idx = widget.findText(current)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    else:
                        widget.setCurrentIndex(-1)

    def _form_state(self) -> dict[str, str]:
        """Snapshot of current values across every field, keyed by schema key."""
        return {
            schema.key: self._current_value(schema) for schema in self._fields
        }

    def set_field_enabled(self, key: str, enabled: bool) -> None:
        """Public helper for subclasses to disable/enable a specific field.

        Used by ``ReferenceCreateDialog`` to lock the source fields
        when the dialog is opened with ``pre_populated_source``.
        """
        widget = self._field_widgets.get(key)
        if widget is not None:
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Tree picker
    # ------------------------------------------------------------------

    def _on_tree_picker_clicked(self, key: str) -> None:
        schema = self._fields_by_key[key]
        if schema.tree_picker_data is None:
            _log.warning("Tree picker clicked but no data callback for %s", key)
            return
        try:
            nodes = schema.tree_picker_data(self._client)
        except Exception as exc:  # noqa: BLE001 — the picker is a UI affordance; failures degrade to no-op + error dialog
            _log.exception("Could not load tree picker data for %s", key)
            ErrorDialog(
                title="Could not load options",
                message="Could not load the available options.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        selectable = None
        if schema.tree_picker_filter is not None:
            try:
                selectable = schema.tree_picker_filter(self._client, self._record or None)
            except Exception:  # noqa: BLE001 — same UI-affordance reasoning
                _log.exception("Could not build tree picker filter for %s", key)
                selectable = None

        current = self._tree_picker_selections.get(key)
        picker = HierarchicalEntityPicker(
            nodes,
            selectable=selectable,
            title=schema.tree_picker_title,
            current_id=current,
            parent=self,
        )
        result = picker.exec()
        if result != QDialog.DialogCode.Accepted:
            return
        new_value = picker.selected_id() or ""
        self._tree_picker_selections[key] = new_value or None
        self._update_tree_picker_label(key, new_value)
        self._clear_error(key)

    def _update_tree_picker_label(self, key: str, value: str) -> None:
        widget = self._widgets[key]
        if not isinstance(widget, QPushButton):
            return
        widget.setText(value if value else "(no selection)")

    # ------------------------------------------------------------------
    # Error labels
    # ------------------------------------------------------------------

    def _show_error(self, key: str, message: str) -> None:
        label = self._error_labels.get(key)
        if label is None:
            return
        label.setText(message)
        label.setVisible(True)

    def _clear_error(self, key: str) -> None:
        label = self._error_labels.get(key)
        if label is None:
            return
        label.setText("")
        label.setVisible(False)

    def _clear_all_errors(self) -> None:
        for key in self._error_labels:
            self._clear_error(key)

    # ------------------------------------------------------------------
    # Save flow
    # ------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        self._clear_all_errors()
        if not self._validate_required():
            return
        if not self._validate_formats():
            return
        body = self._build_request_body()
        if self._mode == "edit" and not body:
            self.accept()
            return
        self._save_btn.setEnabled(False)
        if self._mode == "create":
            assert self._create_method is not None
            self._worker = self._submit(lambda: self._create_method(body))
        else:
            assert self._update_method is not None
            identifier = self._identifier_value
            self._worker = self._submit(
                lambda: self._update_method(identifier, body)
            )

    def _validate_required(self) -> bool:
        ok = True
        for schema in self._fields:
            if not schema.required:
                continue
            value = self._current_value(schema).strip()
            if not value:
                self._show_error(schema.key, "This field is required.")
                ok = False
        return ok

    def _validate_formats(self) -> bool:
        ok = True
        for schema in self._fields:
            if schema.regex is None:
                continue
            value = self._current_value(schema).strip()
            if not value:
                # required-field check has already enforced presence; an
                # empty optional field is valid by convention.
                continue
            if not schema.regex.match(value):
                hint = schema.regex_hint or "Invalid format."
                self._show_error(schema.key, hint)
                ok = False
        return ok

    def _build_request_body(self) -> dict[str, Any]:
        if self._mode == "create":
            return self._build_create_body()
        return self._build_edit_diff()

    def _build_create_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        for schema in self._fields:
            value = self._current_value(schema)
            if schema.strip_before_compare and isinstance(value, str):
                value = value.strip() if schema.widget in {"line", "tree_picker"} else value
            if (
                schema.omit_when_empty_in_create
                and isinstance(value, str)
                and not value.strip()
            ):
                continue
            body[schema.key] = value
        return body

    def _build_edit_diff(self) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        for schema in self._fields:
            if self._mode == "edit" and schema.read_only_on_edit:
                continue
            current = self._current_value(schema)
            initial = self._initial.get(schema.key, "")
            if schema.strip_before_compare:
                current_cmp = current.strip() if schema.widget in {"line", "tree_picker"} else current
                initial_cmp = initial.strip() if schema.widget in {"line", "tree_picker"} else initial
            else:
                current_cmp = current
                initial_cmp = initial
            if current_cmp != initial_cmp:
                diff[schema.key] = current_cmp
        return diff

    def _submit(self, callable_: Callable[[], Any]):
        from crmbuilder_v2.ui.workers import run_in_thread

        return run_in_thread(
            callable_,
            on_success=self._on_save_success,
            on_error=self._on_save_error,
            parent=self,
        )

    def _on_save_success(self, result: Any) -> None:
        self._save_btn.setEnabled(True)
        if isinstance(result, dict):
            identifier = result.get(self._identifier_field) or self._identifier_value
        else:
            identifier = self._identifier_value
        if not identifier and self._mode == "create":
            # Pull the identifier from the form if the API didn't echo it.
            schema = self._fields_by_key.get(self._identifier_field)
            if schema is not None:
                identifier = self._current_value(schema).strip()
        self._saved_identifier = identifier or None
        self.accept()

    def _on_save_error(self, exc: Exception) -> None:
        self._save_btn.setEnabled(True)
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during save: %s", exc)
            self.reject()
            return
        if isinstance(exc, NotFoundError) and self._mode == "edit":
            ErrorDialog(
                title="Record not found",
                message=(
                    "This record was deleted while the dialog was open. "
                    "The list will refresh."
                ),
                parent=self,
            ).exec()
            self.accept()
            return
        if isinstance(exc, ConflictError):
            # Most likely cause on Create: duplicate identifier. On Edit:
            # FK resolution failure (e.g., supersedes target doesn't
            # exist).
            if self._mode == "create" and self._identifier_field in self._error_labels:
                self._show_error(
                    self._identifier_field,
                    "An identifier with this value already exists.",
                )
                return
            ErrorDialog(
                title="Could not save",
                message=exc.message or "Conflict",
                detail=repr(exc),
                parent=self,
            ).exec()
            return
        if isinstance(exc, (ValidationError, RequestShapeError)):
            # 400 ValidationError and 422 RequestShapeError carry the
            # same per-field error shape; surface mapped fields inline,
            # route the rest to the generic dialog.
            field_errors = exc.field_errors()
            unmapped: list[tuple[str, str]] = []
            for f_key, message in field_errors.items():
                if f_key in self._error_labels:
                    self._show_error(f_key, message)
                else:
                    unmapped.append((f_key, message))
            if not field_errors or unmapped:
                detail = (
                    "\n".join(f"{k}: {v}" for k, v in unmapped)
                    if unmapped
                    else None
                )
                ErrorDialog(
                    title="Could not save",
                    message=exc.message or "Validation failed.",
                    detail=detail,
                    parent=self,
                ).exec()
            return
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during save: %s", exc)
            ErrorDialog(
                title="Could not save",
                message=exc.message or str(exc),
                detail=repr(exc),
                parent=self,
            ).exec()
            return
        _log.exception("Unexpected error during save", exc_info=exc)
        ErrorDialog(
            title="Could not save",
            message=str(exc) or exc.__class__.__name__,
            detail=repr(exc),
            parent=self,
        ).exec()


# ---------------------------------------------------------------------------
# EntityCrudDeleteDialog
# ---------------------------------------------------------------------------


class EntityCrudDeleteDialog(QDialog):
    """Confirmation dialog for deleting an entity record.

    Calls the supplied ``delete_method`` through a worker. Soft-delete-
    aware per v0.1 slice H: ``ConflictError`` routes to ``ErrorDialog``
    as a defensive fallback (under normal operation, soft-delete never
    conflicts because referential integrity is preserved by construction).
    ``NotFoundError`` is treated as already-deleted and the dialog
    accepts so the calling panel refreshes.
    """

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        delete_method: Callable[[str], dict],
        *,
        entity_label: str = "record",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._identifier = identifier
        self._title = title
        self._delete_method = delete_method
        self._entity_label = entity_label
        self._worker = None

        self.setWindowTitle(f"Delete {entity_label}")
        self.setModal(True)
        self.setMinimumWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        self._body_label = QLabel(
            f"Delete {identifier} — {title}? This cannot be undone."
        )
        self._body_label.setObjectName("delete_body_label")
        self._body_label.setWordWrap(True)
        outer.addWidget(self._body_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setDefault(True)
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("delete_button")
        self._delete_btn.setStyleSheet(
            "QPushButton { color: #ffffff; background: #c1272d; padding: 4px 12px; }"
            " QPushButton:disabled { color: #ffffff; background: #b6868a; }"
        )
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self._delete_btn)
        outer.addLayout(button_row)

    def _on_delete_clicked(self) -> None:
        from crmbuilder_v2.ui.workers import run_in_thread

        self._delete_btn.setEnabled(False)
        self._worker = run_in_thread(
            lambda: self._delete_method(self._identifier),
            on_success=self._on_delete_success,
            on_error=self._on_delete_error,
            parent=self,
        )

    def _on_delete_success(self, _result: Any) -> None:
        self.accept()

    def _on_delete_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during delete: %s", exc)
            self.reject()
            return
        if isinstance(exc, NotFoundError):
            _log.info("%s %s already deleted", self._entity_label, self._identifier)
            self.accept()
            return
        if isinstance(exc, ConflictError):
            _log.warning("Unexpected 409 during delete: %s", exc)
            ErrorDialog(
                title=f"Could not delete {self._entity_label}",
                message=exc.message or str(exc),
                detail=repr(exc),
                parent=self,
            ).exec()
            self._delete_btn.setEnabled(True)
            return
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during delete: %s", exc)
            ErrorDialog(
                title=f"Could not delete {self._entity_label}",
                message=exc.message or str(exc),
                detail=repr(exc),
                parent=self,
            ).exec()
            self._delete_btn.setEnabled(True)
            return
        _log.exception("Unexpected error during delete", exc_info=exc)
        ErrorDialog(
            title=f"Could not delete {self._entity_label}",
            message=str(exc) or exc.__class__.__name__,
            detail=repr(exc),
            parent=self,
        ).exec()
        self._delete_btn.setEnabled(True)


# Keep ``field`` available even though it's only used in metaprogramming
# elsewhere; the import suppresses an unused-import warning in tooling.
_ = field
