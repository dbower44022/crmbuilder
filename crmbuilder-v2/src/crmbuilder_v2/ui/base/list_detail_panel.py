"""Master/detail panel base.

Wired in slice C. Per PRD §4.5 every entity panel uses a master/detail
layout — list of records on the left, detail of the selected record on
the right. This module provides the abstract base class with the
toolbar, list pane, detail pane, refresh wiring, status label, and
in-flight worker tracking. Subclasses implement ``entity_title()``,
``fetch_records()``, ``list_columns()``, and ``render_detail(record)``.

Connection-loss policy (PRD §4.11): a ``StorageConnectionError`` from
``fetch_records()`` is promoted to the ``connection_lost`` signal so
the main window can surface the existing crash banner. Domain errors
(``ValidationError``, ``NotFoundError``, etc.) stay inline in the
status label.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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

    def __init__(self, columns: list[ColumnSpec], parent: QWidget | None = None):
        super().__init__(parent)
        self._columns = columns
        self._records: list[dict[str, Any]] = []

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
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        record = self._records[index.row()]
        spec = self._columns[index.column()]
        value = record.get(spec.field)
        if value is None:
            return ""
        return str(value)

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
    other thread-safe operations — no Qt widget access.

    Signals:

    * ``connection_lost(str)`` — emitted when a refresh raises
      ``StorageConnectionError``. The main window connects this to
      the existing crash banner.
    """

    connection_lost = Signal(str)

    def __init__(self, client: StorageClient, parent: QWidget | None = None):
        super().__init__(parent)
        self._client = client
        self._records: list[dict[str, Any]] = []
        self._refresh_counter = 0
        self._in_flight_workers: list[Any] = []
        # Maps id(worker) → token. Tokens identify which refresh
        # produced the result so stale (out-of-order) results are
        # ignored. Stored side-band rather than on the QObject to
        # avoid cross-thread setProperty calls.
        self._worker_tokens: dict[int, int] = {}

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

    def render_detail(self, record: dict[str, Any]) -> QWidget:
        raise NotImplementedError

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
        self._worker_tokens[id(worker)] = token
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
        self._detail_stack.setEnabled(enabled)
        if enabled:
            self.refresh()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        self._toolbar_widget = self._build_toolbar()
        outer.addWidget(self._toolbar_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)

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
        self._model = _RecordTableModel(columns, self)
        self._table.setModel(self._model)
        for col_idx, spec in enumerate(columns):
            if spec.width is not None:
                self._table.setColumnWidth(col_idx, spec.width)
        # Wire selection AFTER model is set so currentChanged fires.
        self._table.selectionModel().currentChanged.connect(
            self._on_current_changed
        )

        self._detail_stack = QStackedWidget()
        self._empty_detail = QLabel("Select a record to see its detail.")
        self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_stack.addWidget(self._empty_detail)

        splitter.addWidget(self._table)
        splitter.addWidget(self._detail_stack)
        splitter.setSizes([_INITIAL_LIST_WIDTH, _INITIAL_DETAIL_WIDTH])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        outer.addWidget(splitter, stretch=1)

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
        if not self._sender_token_is_current():
            return
        self._records = list(result) if isinstance(result, list) else []
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

    def _on_fetch_error(self, exc: Exception) -> None:
        if not self._sender_token_is_current():
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
        if not current.isValid():
            self._show_empty_detail()
            return
        record = self._model.record_at(current.row())
        if record is None:
            self._show_empty_detail()
            return
        widget = self.render_detail(record)
        # Replace the current detail widget. Remove any non-empty
        # widgets we previously added so they don't leak across selections.
        while self._detail_stack.count() > 1:
            old = self._detail_stack.widget(1)
            self._detail_stack.removeWidget(old)
            old.deleteLater()
        self._detail_stack.addWidget(widget)
        self._detail_stack.setCurrentWidget(widget)

    def _show_empty_detail(self) -> None:
        self._detail_stack.setCurrentWidget(self._empty_detail)

    def _sender_token_is_current(self) -> bool:
        sender = self.sender()
        if sender is None:
            # Test paths can invoke the slot directly without a sender;
            # treat as current.
            return True
        token = self._worker_tokens.get(id(sender))
        return token == self._refresh_counter

    def _on_worker_finished(self) -> None:
        sender = self.sender()
        if sender is None:
            return
        self._worker_tokens.pop(id(sender), None)
        try:
            self._in_flight_workers.remove(sender)
        except ValueError:
            pass
