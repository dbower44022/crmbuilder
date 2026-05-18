"""Master/detail panel base.

Wired in slice C; extended in slice D with a ``fetch_detail_extras``
hook (for off-thread fetching of records needed by the detail pane,
e.g. inbound references), a ``navigate_requested`` signal (for
cross-panel link clicks), and ``select_record_by_identifier`` (for
the navigation router to jump to a row). Slice E adds the
``_has_detail_pane`` class flag (for list-only panels like References),
the ``_filter_strip_widget`` hook (for filter dropdowns above the
table), and the ``_post_process_records`` hook (for synthetic columns).

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
from typing import Any, ClassVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from crmbuilder_v2.ui.widgets.master_pane_delegate import MasterPaneDelegate
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
    """

    connection_lost = Signal(str)
    navigate_requested = Signal(str, str)

    # Subclasses can set ``False`` to render list-only with no detail
    # pane (no splitter, no detail-extras flow). The toolbar and master
    # list still appear; subclasses may also insert a filter strip
    # between the toolbar and the table by overriding
    # ``_filter_strip_widget``. Used by the slice-E ReferencesPanel.
    _has_detail_pane: ClassVar[bool] = True

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
        """Return an optional widget shown between the toolbar and the table.

        Default ``None`` (no filter strip). Subclasses with a list-only
        layout (``_has_detail_pane = False``) can override this to add
        filter dropdowns above the table. The hook is also available for
        master/detail layouts but the typical usage is list-only panels.
        """
        return None

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

    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        """Wait for in-flight workers so subprocess threads don't outlive the widget."""
        for worker in list(self._in_flight_workers):
            try:
                worker.wait(2000)
            except Exception:
                _log.exception("Worker.wait failed during panel teardown")
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

        self._toolbar_widget = self._build_toolbar()
        outer.addWidget(self._toolbar_widget)

        # Optional filter strip between the toolbar and the table; used
        # by list-only panels (e.g. ReferencesPanel).
        filter_strip = self._filter_strip_widget()
        if filter_strip is not None:
            outer.addWidget(filter_strip)

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
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel(self.entity_title())
        title_font = QFont(title_label.font())
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_button)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        layout.addStretch(1)

        # Slot for subclass action buttons (e.g., "New Decision" in slice G).
        self._action_layout = QHBoxLayout()
        self._action_layout.setContentsMargins(0, 0, 0, 0)
        self._action_layout.setSpacing(4)
        action_container = QWidget()
        action_container.setLayout(self._action_layout)
        layout.addWidget(action_container)

        return toolbar

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
        self._records = self._post_process_records(raw)
        self._model.set_records(self._records)
        # Header sizing: stretch the last column; the rest use the spec width
        # or resize to contents.
        header = self._table.horizontalHeader()
        for col_idx, spec in enumerate(self.list_columns()):
            if spec.width is None:
                header.setSectionResizeMode(
                    col_idx, QHeaderView.ResizeMode.Stretch
                )
        self._status_label.setText(f"{len(self._records)} records")
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
