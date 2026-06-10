"""References panel — list-only with filter dropdowns per slice E.

Renders the full ``/references`` list as three columns: Source,
Relationship, Target. Filter dropdowns above the table narrow the view
by source-type and target-type. Source and Target cells are
single-click navigable: clicking emits ``navigate_requested`` so the
main window swaps to the referenced entity's panel.

The panel uses the slice-E ``_has_detail_pane = False`` flag on the
base class — there is no detail pane because each row already conveys
the full reference tuple.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.reference_create import ReferenceCreateDialog
from crmbuilder_v2.ui.dialogs.reference_delete import (
    ReferenceDeleteDialog,
    edge_text,
)
from crmbuilder_v2.ui.widgets.form_helpers import primary_button
from crmbuilder_v2.ui.widgets.link_filter_input import LinkFilterInput

_ALL = "All"

# Width cap for the free-text filter so it does not crowd the type combos
# (mirrors the constrained-input convention in CommitsPanel).
_TEXT_FILTER_WIDTH = 220

# Maps the reference's stored ``source_type`` / ``target_type`` to the
# ``entity_type`` argument the navigation router expects. The two are
# the same vocabulary in v2; the dict is kept explicit for clarity.
_NAVIGABLE_TYPES = frozenset(
    {"charter", "status", "decision", "session", "risk", "planning_item", "topic"}
)


def _format_endpoint(entity_type: str, identifier: str) -> str:
    return f"{entity_type}:{identifier}"


class ReferencesPanel(ListDetailPanel):
    """Read-only list of every reference, with filters and click-navigation."""

    _has_detail_pane = False

    def __init__(self, *args, **kwargs):
        # The combobox widgets are created in ``_filter_strip_widget``
        # which runs during ``_build_ui`` before ``__init__`` completes;
        # initialize here for clarity.
        self._source_filter: QComboBox | None = None
        self._target_filter: QComboBox | None = None
        self._text_filter: LinkFilterInput | None = None
        self._all_records: list[dict[str, Any]] = []
        super().__init__(*args, **kwargs)
        # Connect single-click navigation now that the table exists.
        self._table.clicked.connect(self._on_cell_clicked)
        # New Reference toolbar button (v0.3 slice C — DEC-033).
        self._new_reference_button = primary_button("New Reference")
        self._new_reference_button.setObjectName("new_reference_button")
        self._new_reference_button.clicked.connect(
            self._on_new_reference_clicked
        )
        self._action_layout.addWidget(self._new_reference_button)

    def entity_title(self) -> str:
        return "References"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_references()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="_source_display", title="Source", width=200),
            ColumnSpec(field="relationship", title="Relationship", width=180),
            ColumnSpec(field="_target_display", title="Target", width=200),
        ]

    # ------------------------------------------------------------------
    # Filter strip
    # ------------------------------------------------------------------

    def _filter_strip_widget(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Free-text filter first (PI-116 / WTK-061): debounced narrowing
        # reads before the structured type dropdowns refine. Composes with
        # the combos via AND in ``_apply_filter``.
        self._text_filter = LinkFilterInput(
            object_name="references_panel_filter",
            max_width=_TEXT_FILTER_WIDTH,
        )
        self._text_filter.filterChanged.connect(self._on_text_filter_changed)
        layout.addWidget(self._text_filter)

        layout.addSpacing(12)

        layout.addWidget(QLabel("Source type:"))
        self._source_filter = QComboBox()
        self._source_filter.addItem(_ALL)
        self._source_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._source_filter)

        layout.addSpacing(12)

        layout.addWidget(QLabel("Target type:"))
        self._target_filter = QComboBox()
        self._target_filter.addItem(_ALL)
        self._target_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._target_filter)

        layout.addStretch(1)
        return container

    # ------------------------------------------------------------------
    # Record post-processing
    # ------------------------------------------------------------------

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # Augment each record with display-friendly synthetic fields.
        for r in records:
            r["_source_display"] = _format_endpoint(
                r.get("source_type") or "", r.get("source_id") or ""
            )
            r["_target_display"] = _format_endpoint(
                r.get("target_type") or "", r.get("target_id") or ""
            )

        # Cache the full set, refresh the dropdown options, then return
        # the records that match the current filter selections.
        self._all_records = list(records)
        self._refresh_filter_options(records)
        return self._apply_filter(records)

    def _refresh_filter_options(self, records: list[dict[str, Any]]) -> None:
        sources = sorted({r.get("source_type") or "" for r in records if r.get("source_type")})
        targets = sorted({r.get("target_type") or "" for r in records if r.get("target_type")})
        self._set_combo_items(self._source_filter, sources)
        self._set_combo_items(self._target_filter, targets)

    def _set_combo_items(self, combo: QComboBox | None, values: list[str]) -> None:
        if combo is None:
            return
        previous = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_ALL)
        for v in values:
            combo.addItem(v)
        # Restore previous selection if it still exists; otherwise stay
        # on "All".
        index = combo.findText(previous) if previous else -1
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _apply_filter(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        source_value = self._source_filter.currentText() if self._source_filter else _ALL
        target_value = self._target_filter.currentText() if self._target_filter else _ALL
        # Free text matched case-insensitively against the rendered row
        # fields (source/target display + relationship), ANDed with the
        # type dropdowns.
        text = self._text_filter.text().strip().lower() if self._text_filter else ""

        def keep(r: dict[str, Any]) -> bool:
            if source_value != _ALL and (r.get("source_type") or "") != source_value:
                return False
            if target_value != _ALL and (r.get("target_type") or "") != target_value:
                return False
            if text and not self._matches_text(r, text):
                return False
            return True

        return [r for r in records if keep(r)]

    @staticmethod
    def _matches_text(record: dict[str, Any], text: str) -> bool:
        """True if ``text`` is a substring of any displayed row field."""
        haystack = " ".join(
            (
                record.get("_source_display") or "",
                record.get("relationship") or "",
                record.get("_target_display") or "",
            )
        ).lower()
        return text in haystack

    def _reapply_filters(self) -> None:
        """Re-filter the cached full list and update the model directly.

        Bypasses the base class's fetch path — no network call needed.
        Shared by the dropdown and free-text filter handlers so the two
        always compose against the current state of the other.
        """
        filtered = self._apply_filter(self._all_records)
        self._records = filtered
        self._model.set_records(filtered)
        if not filtered and self._has_active_text_filter():
            query = self._text_filter.text().strip()
            self._status_label.setText(f'No links match "{query}"')
        else:
            self._status_label.setText(f"{len(filtered)} records")

    def _has_active_text_filter(self) -> bool:
        return bool(self._text_filter and self._text_filter.text().strip())

    def _on_filter_changed(self, _index: int) -> None:
        self._reapply_filters()

    def _on_text_filter_changed(self, _text: str) -> None:
        self._reapply_filters()

    # ------------------------------------------------------------------
    # Click-navigation
    # ------------------------------------------------------------------

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        record = self._model.record_at(index.row())
        if record is None:
            return
        # Column 0 = Source, Column 2 = Target. Column 1 is the
        # relationship and not navigable.
        col = index.column()
        if col == 0:
            entity_type = record.get("source_type") or ""
            identifier = record.get("source_id") or ""
        elif col == 2:
            entity_type = record.get("target_type") or ""
            identifier = record.get("target_id") or ""
        else:
            return
        if entity_type not in _NAVIGABLE_TYPES or not identifier:
            return
        self.navigate_requested.emit(entity_type, identifier)

    # ------------------------------------------------------------------
    # Right-click context menu (v0.3 — DEC-036)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New reference")
            new_action.triggered.connect(self._on_new_reference_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        go_source_action = menu.addAction("Go to source")
        go_source_action.triggered.connect(
            lambda _checked=False, r=record: self._navigate_to_endpoint(
                r.get("source_type") or "", r.get("source_id") or ""
            )
        )
        go_target_action = menu.addAction("Go to target")
        go_target_action.triggered.connect(
            lambda _checked=False, r=record: self._navigate_to_endpoint(
                r.get("target_type") or "", r.get("target_id") or ""
            )
        )
        menu.addSeparator()
        delete_action = menu.addAction("Delete reference")
        delete_action.triggered.connect(
            lambda _checked=False, r=record: self._on_delete_reference_clicked(r)
        )
        return menu

    # ------------------------------------------------------------------
    # Write-surface click handlers (v0.3 slice C — DEC-033)
    # ------------------------------------------------------------------

    def _on_new_reference_clicked(self) -> None:
        """Open ``ReferenceCreateDialog`` with no pre-populated source.

        On accept, refresh the panel. The file-watcher would also pick
        up the new reference, but the explicit refresh is a fast-path
        safety net so the row appears immediately.
        """
        dialog = ReferenceCreateDialog(self._client, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_reference_clicked(self, record: dict[str, Any]) -> None:
        """Open ``ReferenceDeleteDialog`` for the given reference row."""
        ref_id = record.get("id")
        if ref_id is None:
            return
        dialog = ReferenceDeleteDialog(
            self._client,
            reference_id=int(ref_id),
            edge=edge_text(record),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _navigate_to_endpoint(self, entity_type: str, identifier: str) -> None:
        """Emit ``navigate_requested`` for one side of a reference edge.

        Mirrors the existing click-to-navigate path used by
        ``_on_cell_clicked``: only navigable entity types fire; missing
        identifiers are no-ops.
        """
        if entity_type not in _NAVIGABLE_TYPES or not identifier:
            return
        self.navigate_requested.emit(entity_type, identifier)

    # ------------------------------------------------------------------
    # render_detail must be defined because ``ListDetailPanel`` declares
    # it abstract, but is never called when ``_has_detail_pane`` is
    # False.
    # ------------------------------------------------------------------

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:  # pragma: no cover
        raise NotImplementedError("ReferencesPanel has no detail pane")
