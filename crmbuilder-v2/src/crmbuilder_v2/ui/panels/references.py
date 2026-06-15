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

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QTreeView,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.reference_create import ReferenceCreateDialog
from crmbuilder_v2.ui.dialogs.reference_delete import (
    ReferenceDeleteDialog,
    edge_text,
)
from crmbuilder_v2.ui.widgets.form_helpers import (
    primary_button,
    text_link_button,
)
from crmbuilder_v2.ui.widgets.grouping_tree_model import GroupingTreeModel
from crmbuilder_v2.ui.widgets.link_filter_input import LinkFilterInput
from crmbuilder_v2.ui.widgets.multi_sort_header import MultiSortHeaderView
from crmbuilder_v2.ui.widgets.multi_sort_proxy import MultiSortProxyModel
from crmbuilder_v2.ui.widgets.references_section import _pretty_entity_type

_ALL = "All"

# Group-by control (PI-117 / WTK-068). Label → record key; the first
# entry restores the flat list. Driven by the columns this panel shows.
_GROUP_NONE = "(none)"
_GROUP_OPTIONS: list[tuple[str, str]] = [
    (_GROUP_NONE, ""),
    ("Source type", "source_type"),
    ("Relationship", "relationship"),
    ("Target type", "target_type"),
]

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
    # REQ-135 (PI-176): this panel already owns a free-text filter in its
    # filter strip (plus source/target/relationship combos), so it opts out of
    # the base toolbar search to avoid two competing filter inputs.
    _search_enabled = False

    def __init__(self, *args, **kwargs):
        # The combobox widgets are created in ``_filter_strip_widget``
        # which runs during ``_build_ui`` before ``__init__`` completes;
        # initialize here for clarity.
        self._source_filter: QComboBox | None = None
        self._target_filter: QComboBox | None = None
        self._text_filter: LinkFilterInput | None = None
        self._group_combo: QComboBox | None = None
        self._all_records: list[dict[str, Any]] = []
        self._proxy: MultiSortProxyModel | None = None
        self._group_model: GroupingTreeModel | None = None
        self._tree: QTreeView | None = None
        super().__init__(*args, **kwargs)

        # PI-117 / WTK-068: bring header-click single- AND multi-column sort
        # to this previously list-only panel. A MultiSortProxyModel sits
        # between the base _RecordTableModel and the master view; since
        # _RecordTableModel exposes only DisplayRole, sort case-insensitively
        # over the Source / Relationship / Target string columns.
        self._proxy = MultiSortProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(False)
        sort_header = MultiSortHeaderView(Qt.Orientation.Horizontal, self._table)
        sort_header.setStretchLastSection(True)
        self._table.setHorizontalHeader(sort_header)
        sort_header.attach_proxy(self._proxy)
        self._proxy.sortKeysChanged.connect(self._on_sort_keys_changed)

        # Grouped tree presentation (PI-117): a sibling of the table, shown
        # only while a group key is active.
        self._tree = self._build_group_tree()
        self.layout().addWidget(self._tree, stretch=1)
        self._tree.setVisible(False)

        # Connect single-click navigation now that the table exists.
        self._table.clicked.connect(self._on_cell_clicked)
        # New Reference toolbar button (v0.3 slice C — DEC-033).
        self._new_reference_button = primary_button("New Reference")
        self._new_reference_button.setObjectName("new_reference_button")
        self._new_reference_button.clicked.connect(
            self._on_new_reference_clicked
        )
        self._action_layout.addWidget(self._new_reference_button)

        # Inline linked-record preview (PI-118 / WTK-071).
        self._preview = None
        self._install_preview()

    def _build_group_tree(self) -> QTreeView:
        tree = QTreeView(self)
        tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.setAlternatingRowColors(True)
        tree.setUniformRowHeights(True)
        tree.clicked.connect(self._on_cell_clicked)
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(
            self._on_tree_context_menu_requested
        )
        return tree

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

        layout.addSpacing(12)

        # Group-by control (PI-117 / WTK-068), composing with the filters.
        layout.addWidget(QLabel("Group by:"))
        self._group_combo = QComboBox()
        self._group_combo.setObjectName("references_panel_group_combo")
        for label, _key in _GROUP_OPTIONS:
            self._group_combo.addItem(label)
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        layout.addWidget(self._group_combo)

        self._expand_all_link = text_link_button("Expand all")
        self._expand_all_link.setObjectName("references_panel_expand_all")
        self._expand_all_link.clicked.connect(self._on_expand_all)
        self._collapse_all_link = text_link_button("Collapse all")
        self._collapse_all_link.setObjectName("references_panel_collapse_all")
        self._collapse_all_link.clicked.connect(self._on_collapse_all)
        self._expand_all_link.setVisible(False)
        self._collapse_all_link.setVisible(False)
        layout.addWidget(self._expand_all_link)
        layout.addWidget(self._collapse_all_link)

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
        always compose against the current state of the other. When a group
        key is active the grouped tree is rebuilt from the filtered+sorted
        rows so sort/group stay composed with the filters (§3.8).
        """
        filtered = self._apply_filter(self._all_records)
        self._records = filtered
        self._model.set_records(filtered)
        if self._is_grouped():
            self._rebuild_tree()
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
        record = self._record_at_index(index)
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

    def _record_at_index(
        self, index: QModelIndex
    ) -> dict[str, Any] | None:
        """Resolve a record from an index on whichever view emitted it.

        Indices arrive from the proxy-backed table, the grouped tree, or
        (in tests / direct calls) the source ``_RecordTableModel``. Each is
        mapped back to the underlying record so navigation, context menus,
        and delete act on the correct edge regardless of presentation.
        """
        if not index.isValid():
            return None
        model = index.model()
        if self._group_model is not None and model is self._group_model:
            return self._group_model.row_dict(index)
        if self._proxy is not None and model is self._proxy:
            source = self._proxy.mapToSource(index)
            return self._model.record_at(source.row())
        # Source-model index (tests pass these directly).
        return self._model.record_at(index.row())

    # ------------------------------------------------------------------
    # Right-click context menu (v0.3 — DEC-036)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        # Opening a context menu dismisses any open preview card (§3.6).
        if getattr(self, "_preview", None) is not None:
            self._preview.dismiss()
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
        self._append_open_endpoint_action(
            menu, record.get("source_type") or "", record.get("source_id") or ""
        )
        go_target_action = menu.addAction("Go to target")
        go_target_action.triggered.connect(
            lambda _checked=False, r=record: self._navigate_to_endpoint(
                r.get("target_type") or "", r.get("target_id") or ""
            )
        )
        self._append_open_endpoint_action(
            menu, record.get("target_type") or "", record.get("target_id") or ""
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

    def _append_open_endpoint_action(
        self, menu: QMenu, entity_type: str, identifier: str
    ) -> None:
        """Append an "Open <Pretty Type>" action for one edge endpoint.

        The standalone-window counterpart placed right after each "Go to
        <side>" entry (PI-121 / WTK-080), additive over the in-place
        navigation: triggering it emits :attr:`open_requested` so the host's
        detail-window manager opens that record's full detail view in a
        separate, non-modal window without leaving the references list. The
        label is derived from the endpoint's type via
        :func:`_pretty_entity_type`, so a ``planning_item`` endpoint reads
        "Open Planning Item". Skipped for non-navigable types or a missing
        identifier — the same gate as ``_navigate_to_endpoint`` — so the
        label always names a real, openable type.
        """
        if entity_type not in _NAVIGABLE_TYPES or not identifier:
            return
        open_action = menu.addAction(f"Open {_pretty_entity_type(entity_type)}")
        open_action.triggered.connect(
            lambda _checked=False, et=entity_type, i=identifier:
            self._open_endpoint(et, i)
        )

    def _open_endpoint(self, entity_type: str, identifier: str) -> None:
        """Emit ``open_requested`` for one side of a reference edge.

        The "Open <item type>" counterpart to :meth:`_navigate_to_endpoint`:
        instead of swapping the main window to the endpoint's panel, the host
        spawns a separate, non-modal detail window for that record. Same
        navigability gate so non-openable types are inert.
        """
        if entity_type not in _NAVIGABLE_TYPES or not identifier:
            return
        self.open_requested.emit(entity_type, identifier)

    # ------------------------------------------------------------------
    # Sort + Group (PI-117 / WTK-068)
    # ------------------------------------------------------------------

    def _is_grouped(self) -> bool:
        return self._group_combo is not None and self._group_combo.currentIndex() > 0

    def _group_field(self) -> str:
        return _GROUP_OPTIONS[self._group_combo.currentIndex()][1]

    def _group_value(self, record: dict[str, Any]) -> str:
        value = record.get(self._group_field())
        return str(value) if value not in (None, "") else _GROUP_NONE

    def _cell_display(self, record: dict[str, Any], column: int) -> str:
        """Render a record's cell for ``column`` exactly as the flat list."""
        spec = self.list_columns()[column]
        value = record.get(spec.field)
        return "" if value is None else str(value)

    def _ordered_visible_records(self) -> list[dict[str, Any]]:
        """The proxy's currently-visible records in sorted order."""
        if self._proxy is None:
            return list(self._records)
        rows: list[dict[str, Any]] = []
        for r in range(self._proxy.rowCount()):
            source = self._proxy.mapToSource(self._proxy.index(r, 0))
            record = self._model.record_at(source.row())
            if record is not None:
                rows.append(record)
        return rows

    def _on_group_changed(self, _index: int) -> None:
        if self._tree is None:
            return
        if self._is_grouped():
            self._rebuild_tree()
            self._table.setVisible(False)
            self._tree.setVisible(True)
            self._expand_all_link.setVisible(True)
            self._collapse_all_link.setVisible(True)
        else:
            self._group_model = None
            self._tree.setVisible(False)
            self._table.setVisible(True)
            self._expand_all_link.setVisible(False)
            self._collapse_all_link.setVisible(False)

    def _on_sort_keys_changed(self) -> None:
        # A header sort while grouped must re-order rows within groups.
        if self._is_grouped():
            self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        if self._tree is None:
            return
        rows = self._ordered_visible_records()
        headers = [spec.title for spec in self.list_columns()]
        if self._group_model is None:
            self._group_model = GroupingTreeModel(
                rows, headers, self._group_value, self._cell_display, self
            )
            self._tree.setModel(self._group_model)
        else:
            self._group_model.set_rows(rows)
        self._tree.expandAll()
        self._tree.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._tree.header().setStretchLastSection(True)

    def _on_expand_all(self) -> None:
        if self._tree is not None:
            self._tree.expandAll()

    def _on_collapse_all(self) -> None:
        if self._tree is not None:
            self._tree.collapseAll()

    def _on_tree_context_menu_requested(self, position) -> None:
        if self._tree is None:
            return
        index = self._tree.indexAt(position)
        menu = self._build_context_menu(index)
        if menu.actions():
            menu.exec(self._tree.viewport().mapToGlobal(position))

    # ------------------------------------------------------------------
    # Inline linked-record preview (PI-118 / WTK-071)
    # ------------------------------------------------------------------

    def _install_preview(self) -> None:
        """Wire the column-aware hover/keyboard inline preview.

        Additive over the PI-116/PI-117 rebuild: one ``PreviewController``,
        shared by the table and the grouped tree (both route through
        :meth:`_record_at_index`), fed by a *column-aware* extractor that
        previews the Source endpoint (col 0) or Target endpoint (col 2) and
        offers no card for the non-navigable Relationship column (col 1),
        mirroring the existing click-navigation. Any sort / group / filter
        change dismisses an open card (§3.7).
        """
        # Lazy import keeps the preview module's top-level ``_fmt_dt`` import
        # off this panel's load path.
        from crmbuilder_v2.ui.widgets.linked_record_preview import (
            PreviewController,
        )

        self._preview = PreviewController(
            self,
            self._record_at_index,
            self._client,
            self._preview_target,
            # The panel is column-aware: anchor the peek button on the hovered
            # Source/Target cell, not the whole row (§3.2 / §4.3).
            cell_anchored=True,
        )
        self._preview.attach_view(self._table)
        if self._tree is not None:
            self._preview.attach_view(self._tree)
        # Dismiss on any reorder / regroup / refilter (§3.7).
        if self._proxy is not None:
            self._proxy.sortKeysChanged.connect(self._preview.dismiss)
        if self._group_combo is not None:
            self._group_combo.currentIndexChanged.connect(self._preview.dismiss)
        if self._text_filter is not None:
            self._text_filter.filterChanged.connect(self._preview.dismiss)
        if self._source_filter is not None:
            self._source_filter.currentIndexChanged.connect(self._preview.dismiss)
        if self._target_filter is not None:
            self._target_filter.currentIndexChanged.connect(self._preview.dismiss)

    def _preview_target(
        self, record: dict[str, Any], column: int
    ) -> tuple[str, str, str | None, str | None] | None:
        """Column-aware endpoint selection for the preview controller.

        Returns ``(entity_type, identifier, title, relationship)`` for the
        Source (col 0) or Target (col 2) endpoint, or ``None`` for the
        Relationship column (col 1) — consistent with that column not being
        click-navigable. ``title`` / ``relationship`` are ``None``: the
        standalone card opens header-only and is filled by the enrichment read.
        """
        if column == 0:
            entity_type = record.get("source_type") or ""
            identifier = record.get("source_id") or ""
        elif column == 2:
            entity_type = record.get("target_type") or ""
            identifier = record.get("target_id") or ""
        else:
            return None
        if not entity_type or not identifier:
            return None
        return (entity_type, identifier, None, None)

    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        """Tear down the preview controller's workers, then the base panel."""
        if self._preview is not None:
            self._preview.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # render_detail must be defined because ``ListDetailPanel`` declares
    # it abstract, but is never called when ``_has_detail_pane`` is
    # False.
    # ------------------------------------------------------------------

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:  # pragma: no cover
        raise NotImplementedError("ReferencesPanel has no detail pane")
