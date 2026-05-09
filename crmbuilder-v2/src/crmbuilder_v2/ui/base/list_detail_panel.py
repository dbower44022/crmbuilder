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
from dataclasses import dataclass
from typing import Any, ClassVar

from collections.abc import Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.list_detail_panel")

_STATUS_ERROR_MAX = 80
_INITIAL_LIST_WIDTH = 480
_INITIAL_DETAIL_WIDTH = 720


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

    def __init__(self, client: StorageClient, parent: QWidget | None = None):
        super().__init__(parent)
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
        """
        for row, record in enumerate(self._records):
            if record.get("identifier") == identifier:
                self._select_row(row)
                return True
        self._pending_select_identifier = identifier
        self.refresh()
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
    # Internal
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        self._toolbar_widget = self._build_toolbar()
        outer.addWidget(self._toolbar_widget)

        # Optional filter strip between the toolbar and the table; used
        # by list-only panels (e.g. ReferencesPanel).
        filter_strip = self._filter_strip_widget()
        if filter_strip is not None:
            outer.addWidget(filter_strip)

        self._table = QTableView()
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)

        columns = self.list_columns()
        self._model = _RecordTableModel(
            columns,
            self,
            strikethrough_predicate=self._strikethrough_for_record,
        )
        self._table.setModel(self._model)
        for col_idx, spec in enumerate(columns):
            if spec.width is not None:
                self._table.setColumnWidth(col_idx, spec.width)
        # Wire selection AFTER model is set so currentChanged fires.
        self._table.selectionModel().currentChanged.connect(
            self._on_current_changed
        )

        if self._has_detail_pane:
            self._detail_stack = QStackedWidget()
            self._empty_detail = QLabel("Select a record to see its detail.")
            self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._detail_stack.addWidget(self._empty_detail)

            self._loading_detail = QLabel("Loading detail…")
            self._loading_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._detail_stack.addWidget(self._loading_detail)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.addWidget(self._table)
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
            outer.addWidget(self._table, stretch=1)

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
        # Reset the detail pane to the empty placeholder until the user
        # selects a row.
        self._show_empty_detail()
        # If a navigation request asked us to select a specific row,
        # apply it now.
        pending = self._pending_select_identifier
        if pending is not None:
            self._pending_select_identifier = None
            for row, record in enumerate(self._records):
                if record.get("identifier") == pending:
                    self._select_row(row)
                    break

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
