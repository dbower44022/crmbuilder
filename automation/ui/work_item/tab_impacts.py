"""Impacts tab (Section 14.3.7).

Shows change impact records where this work item is affected.
Uses shared_presentation and review_actions from the impact module.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from automation.ui.common.toast import show_toast
from automation.ui.impact.bulk_review import BulkReviewBar
from automation.ui.impact.impact_logic import (
    ImpactDisplayRow,
    compute_impact_summary,
    group_impacts_by_table,
)
from automation.ui.impact.review_actions import ReviewActions
from automation.ui.impact.shared_presentation import (
    ImpactRow as ImpactRowWidget,
)
from automation.ui.impact.shared_presentation import (
    ImpactSummaryHeader,
)
from automation.ui.work_item.work_item_logic import ImpactRow


class ImpactsTab(QWidget):
    """Tab showing change impacts affecting this work item.

    Uses the shared impact presentation format (Section 14.6.1)
    with review actions (Section 14.6.2).

    :param parent: Parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._conn: sqlite3.Connection | None = None

    def set_connection(self, conn: sqlite3.Connection) -> None:
        """Set the database connection for review actions.

        :param conn: Client database connection.
        """
        self._conn = conn

    def update_impacts(self, impacts: list[ImpactRow]) -> None:
        """Refresh the tab with new impact data.

        :param impacts: Impact rows, unreviewed first.
        """
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not impacts:
            empty = QLabel("No impacts recorded")
            empty.setStyleSheet("color: #757575; padding: 12px;")
            self._layout.addWidget(empty)
            self._layout.addStretch()
            return

        # Convert ImpactRow to ImpactDisplayRow for shared presentation
        display_rows = [
            ImpactDisplayRow(
                id=i.id,
                change_log_id=i.change_log_id,
                affected_table=i.affected_table,
                affected_record_id=i.affected_record_id,
                impact_description=i.impact_description,
                requires_review=i.requires_review,
                reviewed=i.reviewed,
                reviewed_at=i.reviewed_at,
                action_required=i.action_required,
                source_summary="",
            )
            for i in impacts
        ]

        # Summary header
        summary = compute_impact_summary(display_rows)
        self._layout.addWidget(ImpactSummaryHeader(summary))

        # Grouped by table with review actions
        groups = group_impacts_by_table(display_rows)
        for table_name in sorted(groups.keys()):
            review_list, info_list = groups[table_name]
            all_in_group = review_list + info_list

            # Table header
            total = len(all_in_group)
            header = QLabel(f"{table_name} ({total})")
            header.setStyleSheet(
                "font-size: 12px; font-weight: bold; padding: 4px 8px; "
                "background-color: #E8EAF6; border-radius: 2px;"
            )
            self._layout.addWidget(header)

            # Bulk review bar
            if self._conn:
                bulk_bar = BulkReviewBar(all_in_group, self._conn)
                bulk_bar.bulk_reviewed.connect(self._on_bulk_reviewed)
                self._layout.addWidget(bulk_bar)

            # Individual impact rows with review actions
            for impact in review_list + info_list:
                row_widget = QWidget()
                row_layout = QVBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(2)

                row_layout.addWidget(ImpactRowWidget(impact))

                if not impact.reviewed and self._conn:
                    actions = ReviewActions(impact, self._conn)
                    actions.reviewed.connect(self._on_impact_reviewed)
                    row_layout.addWidget(actions)

                self._layout.addWidget(row_widget)

        self._layout.addStretch()

    def _on_impact_reviewed(self, impact_id: int, action_required: bool) -> None:
        """Handle individual impact review — toast confirmation."""
        if action_required:
            show_toast(self, "Impact flagged for revision")
        else:
            show_toast(self, "Impact reviewed — no action needed")

    def _on_bulk_reviewed(self) -> None:
        """Handle bulk review — toast confirmation."""
        show_toast(self, "Bulk review completed")
