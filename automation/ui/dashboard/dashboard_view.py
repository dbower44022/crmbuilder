"""Requirements Dashboard container view (Section 14.2).

Assembles the summary bar, staleness banner, work queue,
filter controls, and full project inventory.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from automation.ui.client_context import ClientContext
from automation.ui.dashboard.dashboard_logic import (
    build_phase_groups,
    build_work_queue,
    compute_summary,
    filter_items,
    get_stale_count,
    get_unique_domains,
    load_all_work_items,
)
from automation.ui.dashboard.filters import FilterBar
from automation.ui.dashboard.inventory import ProjectInventory
from automation.ui.dashboard.staleness_summary import StalenessSummaryBanner
from automation.ui.dashboard.summary_bar import SummaryBar
from automation.ui.dashboard.work_queue import WorkQueue


class DashboardView(QWidget):
    """The Requirements Dashboard — Section 14.2.

    :param client_context: The shared client context.
    :param parent: Parent widget.
    """

    work_item_selected = Signal(int)

    def __init__(self, client_context: ClientContext, parent=None) -> None:
        super().__init__(parent)
        self._client_context = client_context
        self._all_items = []
        self._conn: sqlite3.Connection | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Summary bar
        self._summary_bar = SummaryBar()
        layout.addWidget(self._summary_bar)

        # Staleness banner
        self._staleness_banner = StalenessSummaryBanner()
        self._staleness_banner.view_stale_clicked.connect(self._on_view_stale)
        layout.addWidget(self._staleness_banner)

        # Filter bar
        self._filter_bar = FilterBar()
        self._filter_bar.filters_changed.connect(self._apply_filters)
        layout.addWidget(self._filter_bar)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Work queue
        self._work_queue = WorkQueue()
        self._work_queue.item_clicked.connect(self.work_item_selected.emit)
        content_layout.addWidget(self._work_queue)

        # Inventory
        self._inventory = ProjectInventory()
        self._inventory.item_clicked.connect(self.work_item_selected.emit)
        content_layout.addWidget(self._inventory)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

    def refresh(self, conn: sqlite3.Connection) -> None:
        """Reload all dashboard data from the database.

        :param conn: Client database connection.
        """
        self._conn = conn
        self._all_items = load_all_work_items(conn)

        # Summary bar
        client_name = self._client_context.client_name
        summary = compute_summary(client_name, self._all_items)
        self._summary_bar.update_summary(summary)

        # Staleness
        stale_count = get_stale_count(conn)
        self._staleness_banner.update_count(stale_count)

        # Filter options
        domains = get_unique_domains(self._all_items)
        self._filter_bar.set_domains(domains)

        # Apply current filters
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Re-filter and update the work queue and inventory."""
        filtered = filter_items(
            self._all_items,
            domain_filter=self._filter_bar.domain_filter,
            phase_filter=self._filter_bar.phase_filter,
            status_filter=self._filter_bar.status_filter,
        )
        queue = build_work_queue(filtered)
        self._work_queue.update_items(queue)

        groups = build_phase_groups(filtered)
        self._inventory.update_groups(groups)

    def _on_view_stale(self) -> None:
        """Handle View Stale Documents click — emits signal to RequirementsWindow."""
        # The signal is wired in RequirementsWindow._wire_header_actions
        # to navigate to the Documents view filtered to stale documents.
        self._staleness_banner.view_stale_clicked.emit()
