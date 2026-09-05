"""Master/detail panel base.

Wired in slice C; extended in slice D with a ``fetch_detail_extras``
hook (for off-thread fetching of records needed by the detail pane,
e.g. inbound references), a ``navigate_requested`` signal (for
cross-panel link clicks), and ``select_record_by_identifier`` (for
the navigation router to jump to a row). Slice E adds the
``_has_detail_pane`` class flag (for list-only panels like References),
the ``_filter_strip_widget`` hook (for filter dropdowns above the
table), and the ``_post_process_records`` hook (for synthetic columns).
REQ-528 (PI-434) adds header-click column sorting and a generic
column-value filter selector rendered by the default
``_filter_strip_widget``. REQ-534 (PI-436) reshapes the toolbar into a
header row (title, refresh, count) and a control line directly above
the grid — filter strip on the left, search in the middle, and three
ranked action buttons on the right (most used, second most used, and an
``Actions`` dropdown listing every action, led by those two), with
``Edit`` and ``View`` guaranteed on every panel.

Per PRD §4.5 every entity panel uses a master/detail layout — list of
records on the left, detail of the selected record on the right. This
module provides the abstract base class with the toolbar, list pane,
detail pane, refresh wiring, status label, in-flight worker tracking,
and the new detail-extras flow. Subclasses implement
``entity_title()``, ``fetch_records()``, ``list_columns()``, and
``render_detail(record, extras)``. Subclasses optionally override
``fetch_detail_extras(record)`` to supply additional data.

Connection-loss policy (PRD §4.11): a ``StorageConnectionError`` from
either ``fetch_records()`` or ``fetch_detail_extras()`` is promoted to
the ``connection_lost`` signal so the main window can surface the
existing crash banner. Domain errors (``ValidationError``,
``NotFoundError``, etc.) stay inline — in the status label for refresh,
or as a small banner at the top of the detail pane for extras.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Any, ClassVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.form_helpers import icon_button
from crmbuilder_v2.ui.widgets.link_filter_input import LinkFilterInput
from crmbuilder_v2.ui.widgets.master_pane_delegate import MasterPaneDelegate
from crmbuilder_v2.ui.widgets.multi_sort_proxy import compare_values
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.list_detail_panel")

_STATUS_ERROR_MAX = 80
# Default master/detail split per design pass §2.2 — 45/55. The
# splitter accepts any two positive integers in the same ratio; using
# 450/550 keeps the math obvious.
_INITIAL_LIST_WIDTH = 450
_INITIAL_DETAIL_WIDTH = 550
# Splitter handle width per design pass §2.2 (space.3 = 12px).
_SPLITTER_HANDLE_WIDTH = 12
# Outer panel padding per design pass §2.2 (space.4 = 16px).
_PANEL_OUTER_PADDING = 16
# REQ-528 (PI-434): sentinel first entry of the filter-value dropdown.
_FILTER_ALL = "All"


@dataclass(frozen=True)
class ColumnSpec:
    """Spec for a single column in the master list.

    ``field`` is the dict key in each record. ``title`` is the column
    header text. ``width`` is the initial pixel width; ``None`` lets
    the column stretch.
    """

    field: str
    title: str
    width: int | None = None


class _RecordTableModel(QAbstractTableModel):
    """Lightweight model backing the master list."""

    def __init__(
        self,
        columns: list[ColumnSpec],
        parent: QWidget | None = None,
        *,
        strikethrough_predicate: Callable[[dict[str, Any]], bool] | None = None,
    ):
        super().__init__(parent)
        self._columns = columns
        self._records: list[dict[str, Any]] = []
        self._strikethrough_predicate = strikethrough_predicate

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def record_at(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def rowCount(self, _parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._records)

    def columnCount(self, _parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            record = self._records[index.row()]
            spec = self._columns[index.column()]
            value = record.get(spec.field)
            if value is None:
                return ""
            return str(value)
        if role == Qt.ItemDataRole.FontRole and self._strikethrough_predicate:
            record = self._records[index.row()]
            if self._strikethrough_predicate(record):
                font = QFont()
                font.setStrikeOut(True)
                return font
            return None
        return None

    def headerData(  # noqa: N802 (Qt naming)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section].title
        return None


class ListDetailPanel(QWidget):
    """Abstract base for master/detail entity panels.

    Subclasses MUST implement: ``entity_title``, ``fetch_records``,
    ``list_columns``, ``render_detail``. ``fetch_records`` is invoked
    on a worker thread, so it should call only ``StorageClient`` and
    other thread-safe operations — no Qt widget access. The same
    applies to the optional ``fetch_detail_extras`` hook.

    Signals:

    * ``connection_lost(str)`` — emitted when a refresh OR a
      detail-extras fetch raises ``StorageConnectionError``. The main
      window connects this to the existing crash banner.
    * ``navigate_requested(str, str)`` — emitted by subclasses (via
      ``_emit_link_navigation``) when a user clicks a cross-entity
      link in the detail pane. Args are (entity_type, identifier).
    * ``open_requested(str, str)`` — bubbled up from a detail-pane link
      grid's "Open <item type>" action (PI-121 / WTK-079). The main
      window opens the related record's full detail view in a separate,
      non-modal window. Args are (entity_type, identifier).
    """

    connection_lost = Signal(str)
    navigate_requested = Signal(str, str)
    open_requested = Signal(str, str)
    # REQ-526 / PI-432: fires with the full (unfiltered) record count after
    # every successful refresh, so a phase tab can derive its step markers
    # from data the panel already fetched — no extra requests.
    records_loaded = Signal(int)

    # Subclasses can set ``False`` to render list-only with no detail
    # pane (no splitter, no detail-extras flow). The toolbar and master
    # list still appear; subclasses may also insert a filter strip
    # between the toolbar and the table by overriding
    # ``_filter_strip_widget``. Used by the slice-E ReferencesPanel.
    _has_detail_pane: ClassVar[bool] = True

    # REQ-135 (PI-176): a debounced toolbar search box that narrows the master
    # list client-side across the visible columns of the already-loaded
    # records. On by default for every list panel; subclasses whose master view
    # is not the default ``_RecordTableModel`` (the tree-backed TopicsPanel) or
    # that already carry their own filter strip (ReferencesPanel) set ``False``.
    _search_enabled: ClassVar[bool] = True

    # REQ-528 (PI-434): the generic filter selector (column picker +
    # distinct-value dropdown) rendered by the default
    # ``_filter_strip_widget``. On by default for every table-backed panel;
    # the tree-backed TopicsPanel opts out (a single-column hierarchy has no
    # flat rows to filter). Panels that override ``_filter_strip_widget``
    # (References, Commits) replace the generic strip with their own.
    _column_filter_enabled: ClassVar[bool] = True

    # REQ-534 (PI-436): optional per-panel ranking of the control-line
    # actions by label, most used first. Labels named here float to the
    # top of the ranked list (buttons one and two, then the dropdown) in
    # this order; unnamed actions keep their declared order behind them.
    # Default ranking without it: the panel's own toolbar actions (its
    # ``New X`` button and any siblings, in the order they were added),
    # then ``Edit``, then ``View``.
    _action_priority: ClassVar[tuple[str, ...]] = ()

    # REQ-534 (PI-436): the reference ``entity_type`` the ``View`` action
    # passes to ``open_requested`` so the main window opens the selected
    # record in a standalone detail window (PI-121). Stamped per instance by
    # ``panel_registry.build_panel`` from the entity-type → label map;
    # ``None`` makes ``View`` explain that no detail window is available.
    view_entity_type: str | None = None

    # v0.6 slice B: master-pane delegate (DEC-093). Default is the
    # shared :class:`MasterPaneDelegate`; the Topics panel overrides
    # to :class:`MasterPaneTreeDelegate`. Centralized registration in
    # ``_build_ui`` covers every subclass automatically.
    master_pane_delegate_cls: ClassVar[type[QStyledItemDelegate]] = (
        MasterPaneDelegate
    )

    def __init__(self, client: StorageClient, parent: QWidget | None = None):
        super().__init__(parent)
        # v0.6 slice A: project-level QSS reads this object name to apply
        # the panel chrome background (color.neutral.50) per design pass §2.2.
        self.setObjectName("listDetailPanel")
        self._client = client
        self._records: list[dict[str, Any]] = []
        # REQ-135 (PI-176): the full post-processed record set; ``_records`` is
        # the currently-displayed (search-filtered) view of it.
        self._all_records: list[dict[str, Any]] = []
        self._search_text: str = ""
        self._search_input: LinkFilterInput | None = None
        # REQ-528 (PI-434): generic column-value filter + header-click sort
        # state. The combos are created in ``_filter_strip_widget`` (which
        # runs during ``_build_ui``), so initialize first.
        self._filter_column_combo: QComboBox | None = None
        self._filter_value_combo: QComboBox | None = None
        self._column_filter_value: str | None = None
        self._sort_column: int | None = None
        self._sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
        # REQ-534 (PI-436): control-line action cluster. ``_ranked_actions``
        # is (label, button) in rank order, recomputed by
        # ``_arrange_control_actions``; ``_dropdown_source_menu`` keeps the
        # row context menu alive while its actions are borrowed by the
        # ``Actions`` dropdown or triggered by the ``Edit`` button.
        self._ranked_actions: list[tuple[str, QPushButton]] = []
        self._dropdown_source_menu: QMenu | None = None
        self._filter_strip: QWidget | None = None
        self._refresh_counter = 0
        self._detail_counter = 0
        self._in_flight_workers: list[Any] = []
        # Maps id(worker) → token. Tokens identify which refresh or
        # detail-selection produced the result so stale (out-of-order)
        # results are ignored.
        self._refresh_tokens: dict[int, int] = {}
        self._detail_tokens: dict[int, int] = {}
        # Side-band store of the record each detail token was looking
        # at, so success/error callbacks can re-read it without trusting
        # cross-thread state. Cleared in ``_on_worker_finished``.
        self._detail_records: dict[int, dict[str, Any]] = {}
        # When set, the next successful refresh attempts to select the
        # row whose record has this identifier. Used by
        # ``select_record_by_identifier`` for cross-panel navigation
        # before the panel has been refreshed.
        self._pending_select_identifier: str | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # Subclass extension points
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        raise NotImplementedError

    def fetch_records(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_columns(self) -> list[ColumnSpec]:
        raise NotImplementedError

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return extra data needed for the detail pane.

        Called on a worker thread (off the UI thread). Default returns
        ``{}``. Subclasses override to fetch additional records.
        Subclasses that don't override receive ``extras={}`` in
        ``render_detail``.
        """
        return {}

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        raise NotImplementedError

    def _filter_strip_widget(self) -> QWidget | None:
        """Return the optional filter strip for the left of the control line.

        Default (REQ-528 / PI-434): a generic filter selector — a column
        picker plus a distinct-value dropdown. REQ-534 places it at the
        left of the control line directly above the grid header. Choosing a value narrows the list to rows matching it
        in the chosen column; ``All`` restores every row. Composes with
        the REQ-135 toolbar search by AND (see ``_filtered_records``).
        Subclasses may override to provide bespoke strips (References,
        Commits) or return ``None``; panels with no flat row set opt out
        via ``_column_filter_enabled``.
        """
        if not self._column_filter_enabled:
            return None
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Filter:"))
        self._filter_column_combo = QComboBox()
        self._filter_column_combo.setObjectName("grid_filter_column_combo")
        for spec in self.list_columns():
            self._filter_column_combo.addItem(spec.title, spec.field)
        layout.addWidget(self._filter_column_combo)

        self._filter_value_combo = QComboBox()
        self._filter_value_combo.setObjectName("grid_filter_value_combo")
        self._filter_value_combo.addItem(_FILTER_ALL)
        layout.addWidget(self._filter_value_combo)

        # Connect AFTER populating: the first ``addItem`` on an empty combo
        # emits ``currentIndexChanged`` (-1 → 0), which must not fire the
        # apply path while ``_build_ui`` is still mid-construction.
        self._filter_column_combo.currentIndexChanged.connect(
            self._on_filter_column_changed
        )
        self._filter_value_combo.currentIndexChanged.connect(
            self._on_filter_value_changed
        )

        layout.addStretch(1)
        return container

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        """Return True if this record should render with strikethrough.

        Default ``False``. Subclasses (e.g. the Decisions panel with the
        Show-deleted toggle) override to mark deleted rows visually.
        """
        return False

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Hook for subclasses to augment fetched records before display.

        Called on the UI thread between ``fetch_records`` (worker) and
        the table-model update. Default returns the input unchanged.
        Used by ``VersionedPanel`` to set a synthetic ``_current_marker``
        field, and by ``ReferencesPanel`` to set synthetic
        ``_source_display`` / ``_target_display`` fields.
        """
        return records

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Trigger a fresh fetch. Stale results from prior in-flight
        refreshes are ignored — only the latest token's result is
        applied. Slots are bound methods of this QObject so Qt routes
        them onto the main thread automatically.
        """
        self._refresh_counter += 1
        token = self._refresh_counter
        self._status_label.setText("Loading…")
        worker = run_in_thread(
            self.fetch_records,
            on_success=self._on_fetch_success,
            on_error=self._on_fetch_error,
            parent=self,
        )
        self._refresh_tokens[id(worker)] = token
        self._in_flight_workers.append(worker)
        worker.finished.connect(self._on_worker_finished)

    # ------------------------------------------------------------------
    # Client-side search (REQ-135 / PI-176)
    # ------------------------------------------------------------------

    def _filtered_records(self) -> list[dict[str, Any]]:
        """The current search-filtered view of ``self._all_records``.

        Matches the (case-insensitive) query as a substring of the
        concatenated visible-column values. An empty query returns the
        full set.
        """
        records = list(self._all_records)
        # REQ-528 (PI-434): the column-value filter selector narrows first.
        if self._filter_column_combo is not None:
            field = self._filter_column_combo.currentData()
            value = self._column_filter_value
            if field and value is not None:
                records = [
                    r
                    for r in records
                    if r.get(field) is not None and str(r.get(field)) == value
                ]
        query = self._search_text.strip().lower()
        if not query:
            return records
        fields = [spec.field for spec in self.list_columns()]
        matched: list[dict[str, Any]] = []
        for record in records:
            haystack = " ".join(
                str(record.get(field) or "") for field in fields
            ).lower()
            if query in haystack:
                matched.append(record)
        return matched

    def _update_count_status(self) -> None:
        total = len(self._all_records)
        shown = len(self._records)
        if shown != total:
            self._status_label.setText(f"{shown} of {total} records")
        else:
            self._status_label.setText(f"{total} records")

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._reapply_view()

    def _clear_search(self) -> None:
        """Reset the search box and restore the full list (no debounce)."""
        self._search_text = ""
        if self._search_input is not None:
            self._search_input.blockSignals(True)
            self._search_input.clear()
            self._search_input.blockSignals(False)
        self._records = self._display_records()
        if hasattr(self._model, "set_records"):
            self._model.set_records(self._records)
        self._update_count_status()

    # ------------------------------------------------------------------
    # Column-value filter + header-click sort (REQ-528 / PI-434)
    # ------------------------------------------------------------------

    def _on_filter_column_changed(self, _index: int) -> None:
        """A new filter column resets the value to ``All`` and repopulates
        the value dropdown with that column's distinct values."""
        self._column_filter_value = None
        self._refresh_filter_value_options()
        self._reapply_view()

    def _on_filter_value_changed(self, _index: int) -> None:
        combo = self._filter_value_combo
        if combo is None:
            return
        text = combo.currentText()
        self._column_filter_value = None if text == _FILTER_ALL else text
        self._reapply_view()

    def _refresh_filter_value_options(self) -> None:
        """Repopulate the value dropdown with the distinct display values
        of the selected filter column, preserving the current selection
        when it survives (the Commits combo-preservation pattern). No-op
        for panels without the generic strip.
        """
        combo = self._filter_value_combo
        column_combo = self._filter_column_combo
        if combo is None or column_combo is None:
            return
        field = column_combo.currentData()
        values: list[str] = []
        if field:
            values = sorted(
                {
                    str(r.get(field))
                    for r in self._all_records
                    if r.get(field) not in (None, "")
                },
                key=str.lower,
            )
        previous = (
            self._column_filter_value
            if self._column_filter_value is not None
            else _FILTER_ALL
        )
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_FILTER_ALL)
        for value in values:
            combo.addItem(value)
        index = combo.findText(previous)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)
        if index < 0:
            self._column_filter_value = None

    def _on_header_section_clicked(self, column: int) -> None:
        """Sort by ``column`` ascending; a second click on the same column
        toggles descending. The Qt sort indicator tracks the active key."""
        if self._sort_column == column:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sort_column = column
            self._sort_order = Qt.SortOrder.AscendingOrder
        header = self._master_view.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, self._sort_order)
        self._reapply_view()

    def _sorted_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply the active header sort; no active sort keeps source order.

        The sort happens on the panel's record list *before* the model
        reset — never via ``setSortingEnabled``/``model.sort`` — so the
        row→record mapping (``record_at``, selection preservation,
        ``_select_by_identifier``) stays intact. Comparison reuses the
        shared :func:`compare_values` (``None`` last, case-insensitive).
        """
        column = self._sort_column
        columns = self.list_columns()
        if column is None or not 0 <= column < len(columns):
            return records
        field = columns[column].field
        ordered = sorted(
            records,
            key=cmp_to_key(
                lambda a, b: compare_values(a.get(field), b.get(field))
            ),
        )
        if self._sort_order == Qt.SortOrder.DescendingOrder:
            ordered.reverse()
        return ordered

    def _display_records(self) -> list[dict[str, Any]]:
        """The displayed row set: filters (column value + search), then sort."""
        return self._sorted_records(self._filtered_records())

    def _reapply_view(self) -> None:
        """Re-derive the displayed rows from ``_all_records``, preserving
        the selection when its row survives the filter/sort change."""
        prior_selected_id = self._currently_selected_identifier()
        self._records = self._display_records()
        if hasattr(self._model, "set_records"):
            self._model.set_records(self._records)
        self._update_count_status()
        if prior_selected_id is not None and self._select_by_identifier(
            prior_selected_id
        ):
            return
        self._show_empty_detail()

    def set_enabled_state(self, enabled: bool) -> None:
        """Enable/disable the entire panel surface.

        Called by ``MainWindow`` on lifecycle transitions. When
        re-enabling, triggers a fresh refresh so the user sees current
        data after a reconnect.
        """
        self._toolbar_widget.setEnabled(enabled)
        self._table.setEnabled(enabled)
        if self._detail_stack is not None:
            self._detail_stack.setEnabled(enabled)
        if enabled:
            self.refresh()

    def select_record_by_identifier(self, identifier: str) -> bool:
        """Select the row whose record has this identifier.

        If the record is already loaded, selects it immediately and
        returns True. Otherwise schedules a select-on-next-refresh and
        triggers a refresh, returning False.

        Subclasses can override ``_select_by_identifier`` to provide
        a custom selection path (e.g., a tree panel addressing items
        by an identifier→item map rather than by row index).
        """
        # REQ-135 (PI-176): clear any active search so a navigation target the
        # filter currently hides becomes selectable.
        if self._search_text:
            self._clear_search()
        if self._select_by_identifier(identifier):
            return True
        self._pending_select_identifier = identifier
        self.refresh()
        return False

    def _select_by_identifier(self, identifier: str) -> bool:
        """Select the in-memory record with this identifier; return True on hit.

        Default walks ``self._records`` by row and calls ``_select_row``,
        which is correct for table-style panels. Tree-style panels (e.g.,
        Topics) override to look the item up via an identifier→item map.
        Returns ``False`` if the identifier is not in the in-memory list.
        """
        for row, record in enumerate(self._records):
            if record.get("identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def drain_workers(self) -> None:
        """Block until in-flight worker threads finish, so they never outlive the
        widget (a QThread touching a deleted C++ widget aborts the process).

        Exposed as a method (not just inlined in ``closeEvent``) because a panel
        hosted inside a top-level window does **not** receive a ``closeEvent``
        when that window closes — Qt delivers ``closeEvent`` only to the window,
        not its children — so the host must call this explicitly before the
        window's ``WA_DeleteOnClose`` deletes the panel. See
        ``StandaloneDetailWindow.closeEvent`` (PI-121 teardown-crash fix).
        """
        for worker in list(self._in_flight_workers):
            try:
                worker.wait(2000)
            except Exception:
                _log.exception("Worker.wait failed during panel teardown")

    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        """Wait for in-flight workers so subprocess threads don't outlive the widget."""
        self.drain_workers()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Subclass helpers
    # ------------------------------------------------------------------

    def _emit_link_navigation(self, href: str) -> None:
        """Parse an ``"entity_type:identifier"`` href and emit ``navigate_requested``.

        Subclasses connect their ``QLabel.linkActivated`` signals to
        this method so detail-pane links route through the main
        window's navigation router.
        """
        if ":" not in href:
            return
        entity_type, _, identifier = href.partition(":")
        if not entity_type or not identifier:
            return
        self.navigate_requested.emit(entity_type, identifier)

    def _wire_link_section(self, section: QWidget) -> None:
        """Forward a detail-pane link grid's navigation signals to this panel.

        Connects both ``navigate_requested`` ("Go to" / double-click) and
        ``open_requested`` ("Open <item type>", PI-121 / WTK-079) from a
        ``ReferencesSection``-family grid up to this panel's own signals, which
        ``MainWindow`` in turn routes to its navigation router and detail-window
        manager. The single seam for any future grid signal — call it from each
        panel that embeds a link grid instead of wiring the signals one by one.
        """
        section.navigate_requested.connect(self.navigate_requested)
        section.open_requested.connect(self.open_requested)

    # ------------------------------------------------------------------
    # Factory methods (v0.3 — DEC-035)
    # ------------------------------------------------------------------

    def _create_master_widget(self) -> QAbstractItemView:
        """Factory for the master pane's view widget.

        Override to use a non-default widget type (e.g., ``QTreeView`` for
        hierarchical entities). The default returns a ``QTableView``
        configured with the same default policies the v0.2 implementation
        applied inline in ``_build_ui``.

        Subclasses may optionally pre-install a model on the returned
        widget. If a model is already set when ``_build_ui`` receives the
        widget, the base skips its default ``_RecordTableModel``
        installation; ``TopicsPanel`` exercises this mode by installing
        its ``QStandardItemModel`` here.
        """
        view = QTableView(self)
        view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.verticalHeader().setVisible(False)
        view.horizontalHeader().setStretchLastSection(True)
        view.setAlternatingRowColors(True)
        return view

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        """Factory for the right-click context menu.

        Override to add entity-specific actions. The default returns an
        empty ``QMenu``, which the base treats as "no menu shown" — the
        ``customContextMenuRequested`` handler silently returns when the
        menu has no actions.
        """
        return QMenu(self)

    def _status_action_spec(
        self, record: dict[str, Any]
    ) -> tuple[str, list[str], Callable[[str], None]] | None:
        """Lifecycle status quick-action spec, or ``None`` (REQ-137 / PI-178).

        Subclasses whose entity has a lifecycle status return
        ``(current_status, [valid_next_state, ...], apply_fn)`` where
        ``apply_fn(new_state)`` performs the transition and refreshes. The
        base :meth:`_append_status_menu` turns it into a "Set status" submenu
        so a status can be advanced from the list without the edit dialog.
        Default returns ``None`` (no status actions).
        """
        return None

    def _append_status_menu(
        self, menu: QMenu, record: dict[str, Any] | None
    ) -> None:
        """Append a "Set status" submenu of valid next states, if any."""
        if record is None:
            return
        spec = self._status_action_spec(record)
        if not spec:
            return
        _current, next_states, apply_fn = spec
        if not next_states:
            return
        submenu = menu.addMenu("Set status")
        for state in next_states:
            action = submenu.addAction(state)
            action.triggered.connect(
                lambda _checked=False, s=state: apply_fn(s)
            )

    def _record_at_index(
        self, index: QModelIndex
    ) -> dict[str, Any] | None:
        """Look up the record dict at the given master-view index.

        The default implementation works for any model that exposes a
        ``record_at(row)`` method (the base ``_RecordTableModel`` does).
        Subclasses with a non-table model (e.g. ``TopicsPanel`` with a
        ``QStandardItemModel`` tree) override this to map an index to a
        record dict via their own lookup.
        """
        if not index.isValid():
            return None
        record_at = getattr(self._model, "record_at", None)
        if record_at is None:
            return None
        return record_at(index.row())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            _PANEL_OUTER_PADDING,
            _PANEL_OUTER_PADDING,
            _PANEL_OUTER_PADDING,
            _PANEL_OUTER_PADDING,
        )
        outer.setSpacing(6)

        # REQ-534 (PI-436): the toolbar carries the header row and the
        # control line (filter | search | ranked actions); the filter strip
        # now lives inside it rather than as a third row.
        self._toolbar_widget = self._build_toolbar()
        outer.addWidget(self._toolbar_widget)

        self._master_view = self._create_master_widget()
        # Backwards-compat alias: subclasses (and tests) reference the
        # master view via ``self._table``; preserved per v0.3 slice A.
        self._table = self._master_view

        # Wire right-click context-menu factory (v0.3 — DEC-035 / DEC-036).
        self._master_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._master_view.customContextMenuRequested.connect(
            self._on_context_menu_requested
        )

        # Default model installation: only if the factory didn't pre-install
        # one. Subclasses with a custom model (e.g. TopicsPanel's
        # ``QStandardItemModel`` tree) skip this branch.
        columns = self.list_columns()
        if self._master_view.model() is None:
            self._model = _RecordTableModel(
                columns,
                self,
                strikethrough_predicate=self._strikethrough_for_record,
            )
            self._master_view.setModel(self._model)
            for col_idx, spec in enumerate(columns):
                if spec.width is not None:
                    self._master_view.setColumnWidth(col_idx, spec.width)
            # REQ-528 (PI-434): header-click sorting. Clicks route through
            # the panel — not ``setSortingEnabled``, which would ask the
            # model itself to sort and break the row→record mapping — and
            # the sort is applied to ``self._records`` before each model
            # reset. Panels that pre-install their own model (Topics tree)
            # or replace the header (References) are unaffected.
            header = self._master_view.horizontalHeader()
            header.setSectionsClickable(True)
            header.sectionClicked.connect(self._on_header_section_clicked)
        else:
            self._model = self._master_view.model()
        # Wire selection AFTER model is set so currentChanged fires.
        self._master_view.selectionModel().currentChanged.connect(
            self._on_current_changed
        )

        # v0.6 slice B: install the shared master-pane delegate per
        # DEC-093. The delegate reads soft-deleted state via the
        # panel's _strikethrough_for_record hook (the same predicate
        # the table model uses), and the identifier column is detected
        # by walking list_columns() for the "identifier" field.
        ident_col: int | None = None
        for col_idx, spec in enumerate(columns):
            if spec.field == "identifier":
                ident_col = col_idx
                break

        def _record_for_index(idx: QModelIndex) -> dict | None:
            return self._record_at_index(idx)

        def _is_soft_deleted(idx: QModelIndex) -> bool:
            record = self._record_at_index(idx)
            if record is None:
                return False
            return bool(self._strikethrough_for_record(record))

        delegate = self.master_pane_delegate_cls(
            self._master_view,
            record_for_index=_record_for_index,
            is_soft_deleted=_is_soft_deleted,
            identifier_column_index=ident_col,
        )
        self._master_view.setItemDelegate(delegate)
        # Hold a reference so the delegate isn't garbage-collected.
        self._master_pane_delegate = delegate

        if self._has_detail_pane:
            self._detail_stack = QStackedWidget()
            self._empty_detail = QLabel("Select a record to see its detail.")
            self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._detail_stack.addWidget(self._empty_detail)

            self._loading_detail = QLabel("Loading detail…")
            self._loading_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._detail_stack.addWidget(self._loading_detail)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setHandleWidth(_SPLITTER_HANDLE_WIDTH)
            splitter.addWidget(self._master_view)
            splitter.addWidget(self._detail_stack)
            splitter.setSizes([_INITIAL_LIST_WIDTH, _INITIAL_DETAIL_WIDTH])
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)

            outer.addWidget(splitter, stretch=1)
        else:
            # List-only layout. No splitter, no detail pane.
            self._detail_stack = None
            self._empty_detail = None
            self._loading_detail = None
            outer.addWidget(self._master_view, stretch=1)

    def _on_context_menu_requested(self, position: QPoint) -> None:
        """Slot wired to ``customContextMenuRequested`` on the master view.

        Calls ``_build_context_menu`` and pops the resulting menu at the
        cursor position. Empty menus (the default factory's return) are
        silently ignored — no menu is shown.
        """
        index = self._master_view.indexAt(position)
        menu = self._build_context_menu(index)
        if menu.actions():
            menu.exec(self._master_view.viewport().mapToGlobal(position))

    def _build_toolbar(self) -> QWidget:
        """Build the two-row toolbar (REQ-534 / PI-436).

        Row one is the header — title, icon-only refresh, record count.
        Row two is the control line directly above the grid: the filter
        strip on the left, the search box in the middle, and the ranked
        action cluster (button one, button two, ``Actions`` dropdown) on
        the right.
        """
        toolbar = QWidget()
        rows = QVBoxLayout(toolbar)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(6)

        # --- Header row -------------------------------------------------
        header = QWidget()
        header.setObjectName("grid_header_row")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = QLabel(self.entity_title())
        title_font = QFont(title_label.font())
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        # v0.6 slice D: panel toolbar refresh is icon-only per design
        # pass §2.5. The Lucide rotate-ccw glyph carries the meaning;
        # tooltip surfaces the label on hover.
        self._refresh_button = icon_button("rotate-ccw", tooltip="Refresh")
        self._refresh_button.clicked.connect(self.refresh)
        header_layout.addWidget(self._refresh_button)

        self._status_label = QLabel("")
        header_layout.addWidget(self._status_label)
        header_layout.addStretch(1)
        rows.addWidget(header)

        # --- Control line -----------------------------------------------
        control = QWidget()
        control.setObjectName("grid_control_row")
        self._control_row_layout = QHBoxLayout(control)
        self._control_row_layout.setContentsMargins(0, 0, 0, 0)
        self._control_row_layout.setSpacing(8)

        # Left: the filter strip (generic selector, or a subclass's own).
        self._filter_strip = self._filter_strip_widget()
        if self._filter_strip is not None:
            self._control_row_layout.addWidget(self._filter_strip)
        self._control_row_layout.addStretch(1)

        # Middle: REQ-135 (PI-176) debounced client-side search.
        if self._search_enabled:
            self._search_input = LinkFilterInput(
                object_name="master_search_input", max_width=240
            )
            self._search_input.setPlaceholderText("Search…")
            self._search_input.filterChanged.connect(self._on_search_changed)
            self._control_row_layout.addWidget(self._search_input)
        self._control_row_layout.addStretch(1)

        # Right: the ranked action cluster.
        self._control_row_layout.addWidget(self._build_action_cluster())
        rows.addWidget(control)

        return toolbar

    # ------------------------------------------------------------------
    # Control-line action cluster (REQ-534 / PI-436)
    # ------------------------------------------------------------------

    def _build_action_cluster(self) -> QWidget:
        """Build the right-hand cluster: subclass action slot, ``Edit``,
        ``View`` and the ``Actions`` dropdown.

        Subclasses keep adding their own buttons to ``_action_layout``
        (the long-standing "New X" contract); ``_arrange_control_actions``
        later decides which two of all the actions stay visible as
        buttons one and two. The dropdown's menu is rebuilt on every open
        so it always reflects the current selection.
        """
        cluster = QWidget()
        cluster.setObjectName("grid_action_cluster")
        layout = QHBoxLayout(cluster)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Slot for subclass action buttons (e.g., "New Decision" in slice G).
        self._action_layout = QHBoxLayout()
        self._action_layout.setContentsMargins(0, 0, 0, 0)
        self._action_layout.setSpacing(4)
        action_container = QWidget()
        action_container.setLayout(self._action_layout)
        layout.addWidget(action_container)

        self._edit_button = QPushButton("Edit")
        self._edit_button.setObjectName("grid_edit_button")
        self._edit_button.clicked.connect(self._on_edit_action)
        layout.addWidget(self._edit_button)

        self._view_button = QPushButton("View")
        self._view_button.setObjectName("grid_view_button")
        self._view_button.clicked.connect(self._on_view_action)
        layout.addWidget(self._view_button)

        self._actions_button = QPushButton("Actions")
        self._actions_button.setObjectName("grid_actions_button")
        self._actions_menu = QMenu(self._actions_button)
        self._actions_menu.aboutToShow.connect(self._rebuild_actions_menu)
        self._actions_button.setMenu(self._actions_menu)
        layout.addWidget(self._actions_button)
        return cluster

    def _has_action_cluster(self) -> bool:
        """True when ``_build_action_cluster`` ran.

        A subclass that replaces ``_build_ui`` wholesale (``ReviewPanel``)
        never builds the control line, so the cluster's widgets do not
        exist on it; the show-time arrangement must tolerate that opt-out
        (REQ-566).
        """
        return hasattr(self, "_action_layout")

    def _subclass_action_buttons(self) -> list[QPushButton]:
        """The buttons a subclass placed in ``_action_layout``, in order."""
        buttons: list[QPushButton] = []
        for i in range(self._action_layout.count()):
            item = self._action_layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QPushButton):
                buttons.append(widget)
        return buttons

    def _arrange_control_actions(self) -> list[tuple[str, QPushButton]]:
        """Rank every control-line action and show the top two as buttons.

        Rank order: the subclass's toolbar buttons in declared order, then
        ``Edit``, then ``View`` — re-ordered by ``_action_priority`` when a
        panel names its most-used actions. Ranks one and two stay visible
        as buttons; the rest are hidden (never disabled) and remain
        reachable through the ``Actions`` dropdown. Returns the ranked
        ``(label, button)`` list. Idempotent; runs on show and before every
        dropdown open so late-added buttons are picked up. A panel without
        the action cluster (custom ``_build_ui``) returns an empty list.
        """
        if not self._has_action_cluster():
            self._ranked_actions = []
            return []
        entries: list[tuple[str, QPushButton]] = [
            (button.text(), button) for button in self._subclass_action_buttons()
        ]
        entries.append(("Edit", self._edit_button))
        entries.append(("View", self._view_button))
        priority = [label.strip().lower() for label in self._action_priority]

        def _rank(entry: tuple[str, QPushButton]) -> int:
            label = entry[0].strip().lower()
            return priority.index(label) if label in priority else len(priority)

        entries.sort(key=_rank)  # stable: declared order survives ties
        for position, (_label, button) in enumerate(entries):
            button.setVisible(position < 2)
        self._ranked_actions = entries
        return entries

    def showEvent(self, event):  # noqa: N802 (Qt naming)
        """Arrange the control-line actions once the subclass has added its
        toolbar buttons (they arrive after the base ``__init__``)."""
        self._arrange_control_actions()
        super().showEvent(event)

    def _current_master_index(self) -> QModelIndex:
        sel_model = self._master_view.selectionModel()
        if sel_model is None:
            return QModelIndex()
        return sel_model.currentIndex()

    def _rebuild_actions_menu(self) -> None:
        """Populate the ``Actions`` dropdown for the current selection.

        The first entries are the ranked actions (so the top two mirror
        buttons one and two); after a separator come the remaining
        row-context-menu actions for the selected record, deduplicated by
        label. The context menu is kept alive on the panel so its borrowed
        actions stay valid while the dropdown is open.
        """
        ranked = self._arrange_control_actions()
        menu = self._actions_menu
        menu.clear()
        seen: set[str] = set()
        for label, button in ranked:
            action = menu.addAction(label)
            action.triggered.connect(lambda _checked=False, b=button: b.click())
            seen.add(label.strip().lower())
        source = self._build_context_menu(self._current_master_index())
        self._dropdown_source_menu = source
        extras = [
            action
            for action in source.actions()
            if not action.isSeparator()
            and action.text().strip().lower() not in seen
        ]
        if extras:
            menu.addSeparator()
            menu.addActions(extras)

    def _on_edit_action(self) -> None:
        """``Edit``: trigger the row context menu's Edit action for the
        selected record, or explain why nothing opened (PRF-006 — the
        button is never disabled)."""
        index = self._current_master_index()
        if not index.isValid() or self._record_at_index(index) is None:
            self._status_label.setText("Select a record to edit.")
            return
        source = self._build_context_menu(index)
        self._dropdown_source_menu = source
        for action in source.actions():
            if action.text().strip().lower().startswith("edit"):
                action.trigger()
                return
        self._status_label.setText(
            f"{self.entity_title()} records cannot be edited from this list."
        )

    def _on_view_action(self) -> None:
        """``View``: open the selected record in a standalone detail window
        via ``open_requested`` (PI-121), or explain why it cannot."""
        record = self._record_at_index(self._current_master_index())
        if record is None:
            self._status_label.setText("Select a record to view.")
            return
        identifier = record.get("identifier")
        if self.view_entity_type and identifier:
            self.open_requested.emit(self.view_entity_type, str(identifier))
            return
        self._status_label.setText(
            "No detail window is available for this list."
        )

    def _on_fetch_success(self, result: list[dict[str, Any]]) -> None:
        if not self._sender_is_current_refresh():
            return
        # Capture the currently-selected identifier before replacing the
        # model. This protects two paths: (1) cross-panel navigation,
        # where ``_on_navigate_requested`` selects the target row
        # synchronously while the sidebar's refresh is still in flight,
        # and (2) any incidental refresh that races with a click.
        # Without this, ``set_records`` + ``_show_empty_detail`` would
        # blow the user's selection away on every refresh.
        prior_selected_id = self._currently_selected_identifier()
        raw = list(result) if isinstance(result, list) else []
        # REQ-135 (PI-176): keep the full set; display the search-filtered view.
        self._all_records = self._post_process_records(raw)
        # REQ-528 (PI-434): sync the filter-value dropdown with the fresh
        # rows before deriving the displayed (filtered + sorted) view.
        self._refresh_filter_value_options()
        self._records = self._display_records()
        self._model.set_records(self._records)
        # Header sizing: stretch the last column; the rest use the spec width
        # or resize to contents.
        header = self._table.horizontalHeader()
        for col_idx, spec in enumerate(self.list_columns()):
            if spec.width is None:
                header.setSectionResizeMode(
                    col_idx, QHeaderView.ResizeMode.Stretch
                )
        self._update_count_status()
        self.records_loaded.emit(len(self._all_records))
        # Decide which row to select after the refresh:
        #   1. An explicit pending identifier (from cross-panel navigation
        #      that arrived after the refresh started).
        #   2. The prior selection if its row still exists.
        #   3. No selection — show the empty detail placeholder.
        pending = self._pending_select_identifier
        self._pending_select_identifier = None
        desired = pending if pending is not None else prior_selected_id
        if desired is not None and self._select_by_identifier(desired):
            return
        self._show_empty_detail()

    def _on_fetch_error(self, exc: Exception) -> None:
        if not self._sender_is_current_refresh():
            return
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during refresh: %s", exc)
            self._status_label.setText("Connection lost")
            self.connection_lost.emit(str(exc))
            return
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during refresh: %s", exc)
            text = f"Error: {exc.message}"
            if len(text) > _STATUS_ERROR_MAX:
                text = text[: _STATUS_ERROR_MAX - 1] + "…"
            self._status_label.setText(text)
            return
        # Unexpected: treat as a domain-style error.
        _log.exception("Unexpected error during refresh", exc_info=exc)
        self._status_label.setText(f"Error: {exc!s}"[:_STATUS_ERROR_MAX])

    def _on_current_changed(
        self, current: QModelIndex, _previous: QModelIndex
    ) -> None:
        if not self._has_detail_pane:
            return
        if not current.isValid():
            self._show_empty_detail()
            return
        record = self._model.record_at(current.row())
        if record is None:
            self._show_empty_detail()
            return
        self._begin_detail_load(record)

    def _begin_detail_load(self, record: dict[str, Any]) -> None:
        """Show the loading placeholder and kick off a detail-extras worker."""
        self._detail_counter += 1
        token = self._detail_counter
        self._detail_stack.setCurrentWidget(self._loading_detail)
        # Capture the record by closure so the worker callable doesn't
        # reach back into Qt state from a worker thread.
        captured = record

        def _do_fetch():
            return self.fetch_detail_extras(captured)

        worker = run_in_thread(
            _do_fetch,
            on_success=self._on_detail_success,
            on_error=self._on_detail_error,
            parent=self,
        )
        self._detail_tokens[id(worker)] = token
        self._detail_records[id(worker)] = record
        self._in_flight_workers.append(worker)
        worker.finished.connect(self._on_worker_finished)

    def _on_detail_success(self, extras: Any) -> None:
        sender = self.sender()
        if not self._sender_is_current_detail():
            return
        record = self._detail_records.get(id(sender)) if sender else None
        if record is None:
            return
        if not isinstance(extras, dict):
            extras = {}
        widget = self.render_detail(record, extras)
        self._install_detail_widget(widget)

    def _on_detail_error(self, exc: Exception) -> None:
        sender = self.sender()
        if not self._sender_is_current_detail():
            return
        record = self._detail_records.get(id(sender)) if sender else None
        if record is None:
            return
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during detail-extras fetch: %s", exc)
            self.connection_lost.emit(str(exc))
            return
        # Domain or unexpected error: still render the detail with empty
        # extras so the user sees the basic record fields, and prepend
        # an inline error indicator above it.
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during detail-extras fetch: %s", exc)
            message = exc.message
        else:
            _log.exception(
                "Unexpected error during detail-extras fetch", exc_info=exc
            )
            message = str(exc)
        rendered = self.render_detail(record, {})
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(4)
        warning = QLabel(f"Detail extras unavailable: {message}")
        warning.setObjectName("detail_extras_error")
        warning.setStyleSheet("color: #b76e00; padding: 4px;")
        warning.setWordWrap(True)
        wrapper_layout.addWidget(warning)
        wrapper_layout.addWidget(rendered, stretch=1)
        self._install_detail_widget(wrapper)

    def _install_detail_widget(self, widget: QWidget) -> None:
        # Remove any non-placeholder widgets we previously installed.
        # The first two stack pages are _empty_detail and _loading_detail.
        while self._detail_stack.count() > 2:
            old = self._detail_stack.widget(2)
            self._detail_stack.removeWidget(old)
            old.deleteLater()
        self._detail_stack.addWidget(widget)
        self._detail_stack.setCurrentWidget(widget)

    def _show_empty_detail(self) -> None:
        if self._detail_stack is None or self._empty_detail is None:
            return
        self._detail_stack.setCurrentWidget(self._empty_detail)

    def _select_row(self, row: int) -> None:
        index = self._model.index(row, 0)
        self._table.setCurrentIndex(index)
        self._table.scrollTo(index)

    def _currently_selected_identifier(self) -> str | None:
        """Return the identifier of the currently-selected master row, if any.

        Used by ``_on_fetch_success`` to preserve the user's selection
        across refreshes when the row still exists in the new dataset.
        Default reads ``self._records`` by row index; subclasses with a
        different master widget shape (e.g., the Topics tree panel) may
        override.
        """
        master = getattr(self, "_master_view", None)
        if master is None:
            return None
        sel_model = master.selectionModel()
        if sel_model is None:
            return None
        index = sel_model.currentIndex()
        if not index.isValid():
            return None
        row = index.row()
        if 0 <= row < len(self._records):
            ident = self._records[row].get("identifier")
            if isinstance(ident, str):
                return ident
        return None

    def _sender_is_current_refresh(self) -> bool:
        sender = self.sender()
        if sender is None:
            # Test paths can invoke the slot directly without a sender;
            # treat as current.
            return True
        token = self._refresh_tokens.get(id(sender))
        if token is None:
            return False
        return token == self._refresh_counter

    def _sender_is_current_detail(self) -> bool:
        sender = self.sender()
        if sender is None:
            return True
        token = self._detail_tokens.get(id(sender))
        if token is None:
            return False
        return token == self._detail_counter

    def _on_worker_finished(self) -> None:
        sender = self.sender()
        if sender is None:
            return
        self._refresh_tokens.pop(id(sender), None)
        self._detail_tokens.pop(id(sender), None)
        self._detail_records.pop(id(sender), None)
        try:
            self._in_flight_workers.remove(sender)
        except ValueError:
            pass
