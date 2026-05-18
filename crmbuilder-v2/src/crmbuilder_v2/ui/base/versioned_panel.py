"""Versioned-content panel base.

Wired in slice E. Variant of ``ListDetailPanel`` for the two v2
entities that fit a singletons-with-history pattern: charter and
status. The list shows ``version`` + ``created_at`` + a current-version
marker; the detail pane renders the selected version's ``payload`` as a
structured key/value form.

Subclasses implement ``entity_title()`` and ``fetch_records()``. The
base class:

* Adds a synthetic ``_current_marker`` field to each record (✓ for the
  current version, empty otherwise) via ``_post_process_records``.
* Auto-selects the current version row on first successful load so the
  user lands on the most recent payload immediately.
* Overrides ``render_detail`` to render the inline ``payload`` dict.
* Overrides ``fetch_detail_extras`` to return ``{}`` — versioned
  records carry their payload inline, so no extra fetch is needed.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel

_CURRENT_MARK = "✓"
_LONG_STRING_THRESHOLD = 80
_LONG_TEXT_MIN_HEIGHT = 80


class VersionedPanel(ListDetailPanel):
    """List/detail panel for singleton entities with full version history.

    Charter and status share this shape: every write creates a new row
    with an incremented ``version``; the most recent has ``is_current``
    True. The list renders newest-first (the API orders that way); the
    detail shows the version's payload.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_select_done = False

    # ------------------------------------------------------------------
    # Right-click context menu (v0.3 — DEC-036)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        """Versioned panels share a uniform menu shape.

        Whitespace right-click: ``New version``. Row right-click: ``Make
        Current`` (only on non-current rows) plus ``View payload``
        (always). Subclasses don't override this; they only provide the
        ``_on_new_version_clicked`` and ``_on_make_current(version)``
        slots, which already exist on :class:`CharterPanel` and
        :class:`StatusPanel`.
        """
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New version")
            new_action.triggered.connect(self._on_new_version_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        if not record.get("is_current"):
            version = record.get("version")
            if version is not None:
                make_current_action = menu.addAction("Make Current")
                make_current_action.triggered.connect(
                    lambda _checked=False, v=version: self._on_make_current(v)
                )

        view_payload_action = menu.addAction("View payload")
        view_payload_action.triggered.connect(
            lambda _checked=False, r=record: self._on_view_payload_clicked(r)
        )
        return menu

    def _on_view_payload_clicked(self, record: dict[str, Any]) -> None:
        """Open a small read-only modal showing the version's payload as JSON.

        v0.3 slice B addition. Implementation cost is small (~25 lines)
        per the slice prompt; the modal stays in this base class so both
        ``CharterPanel`` and ``StatusPanel`` get it for free.
        """
        version = record.get("version", "?")
        payload = record.get("payload") or {}
        try:
            text = json.dumps(payload, indent=2, sort_keys=True)
        except (TypeError, ValueError):
            text = repr(payload)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self.entity_title()} — version {version} payload")
        dialog.resize(720, 540)
        layout = QVBoxLayout(dialog)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)
        editor.setFont(QFont("monospace"))
        layout.addWidget(editor, stretch=1)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(dialog.reject)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        dialog.exec()

    # ------------------------------------------------------------------
    # ListDetailPanel overrides
    # ------------------------------------------------------------------

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="version", title="Version", width=80),
            ColumnSpec(field="created_at", title="Created", width=200),
            ColumnSpec(field="_current_marker", title="Current", width=80),
        ]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        return {}

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        return self._render_payload(record.get("payload") or {})

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            r["_current_marker"] = _CURRENT_MARK if r.get("is_current") else ""
        return records

    def _on_fetch_success(self, result: list[dict[str, Any]]) -> None:
        super()._on_fetch_success(result)
        # Auto-select the current version row on first successful load.
        if self._initial_select_done:
            return
        if not self._records:
            return
        for row, record in enumerate(self._records):
            if record.get("is_current"):
                self._select_row(row)
                self._initial_select_done = True
                return
        # No current row found (unusual); still mark done so we don't
        # override later user selection.
        self._initial_select_done = True

    # ------------------------------------------------------------------
    # Payload rendering
    # ------------------------------------------------------------------

    def _render_payload(self, payload: dict[str, Any]) -> QWidget:
        """Render the payload as a scrollable form. Used by the default
        ``render_detail`` implementation.

        Subclasses that compose additional widgets (e.g. action buttons,
        references section) typically call :meth:`_build_payload_form`
        directly instead and embed the result in their own layout.
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        outer.addWidget(self._build_payload_form(payload))
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _build_payload_form(self, payload: dict[str, Any]) -> QWidget:
        """Return a non-scrollable widget containing the payload form.

        Empty payloads render as a dimmed ``(empty payload)`` placeholder.
        """
        if not payload:
            empty = QLabel("(empty payload)")
            empty.setStyleSheet("color: #888;")
            return empty

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(6)

        form = QFormLayout()
        # v0.6 slice C: label-above form layout per design pass §2.4.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        for key, value in payload.items():
            label_text = _humanize_key(key)
            field_widget = _payload_value_widget(value)
            form.addRow(_form_label(label_text), field_widget)

        wrapper_layout.addLayout(form)
        return wrapper


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------


def _humanize_key(key: str) -> str:
    return key.replace("_", " ").title()


def _form_label(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(label.font())
    font.setBold(True)
    label.setFont(font)
    return label


def _payload_value_widget(value: Any) -> QWidget:
    if isinstance(value, str):
        if len(value) > _LONG_STRING_THRESHOLD or "\n" in value:
            return _long_text_widget(value)
        return _short_label(value)
    if isinstance(value, (dict, list)):
        return _long_text_widget(json.dumps(value, indent=2))
    if value is None:
        return _short_label("—", dim=True)
    return _short_label(str(value))


def _short_label(text: str, *, dim: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )
    label.setWordWrap(True)
    if dim:
        label.setStyleSheet("color: #888;")
    return label


def _long_text_widget(content: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setPlainText(content)
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    return widget
