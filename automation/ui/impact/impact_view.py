"""Impact Review sidebar view (Section 14.6.5).

The administrator's dedicated workspace for reviewing impacts.
Two sections: Unresolved Changes at top, Flagged Work Items below.

Design decision: resolved change sets are removed from the list
(not moved to a "Resolved Changes" area) to keep the view clean.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.confirmation import confirm_action
from automation.ui.common.error_display import show_error
from automation.ui.common.readable_first import format_work_item_name
from automation.ui.common.toast import show_toast
from automation.ui.impact.bulk_review import BulkReviewBar
from automation.ui.impact.impact_logic import (
    ChangeSetEntry,
    FlaggedWorkItemEntry,
    group_impacts_by_table,
    load_change_sets,
    load_flagged_work_items,
    load_impacts_for_change_set,
    store_revision_reason,
)
from automation.ui.impact.review_actions import ReviewActions
from automation.ui.impact.shared_presentation import (
    ImpactRow,
    ImpactSummaryHeader,
    compute_impact_summary,
)


class ChangeSetCard(QWidget):
    """An expandable card for a single change set.

    :param entry: The change set data.
    :param conn: Client database connection.
    :param parent: Parent widget.
    """

    change_reviewed = Signal()  # Emitted when any impact in this set is reviewed

    def __init__(
        self, entry: ChangeSetEntry, conn: sqlite3.Connection, parent=None
    ) -> None:
        super().__init__(parent)
        self._entry = entry
        self._conn = conn
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Summary row
        summary = QHBoxLayout()

        source_label = QLabel(entry.source_label)
        source_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        summary.addWidget(source_label)

        time_label = QLabel(entry.timestamp[:16] if entry.timestamp else "")
        time_label.setStyleSheet("font-size: 11px; color: #757575;")
        summary.addWidget(time_label)

        change_label = QLabel(entry.change_summary)
        change_label.setStyleSheet("font-size: 11px; color: #424242;")
        summary.addWidget(change_label, stretch=1)

        count_label = QLabel(f"{entry.unreviewed_count}/{entry.total_count} unreviewed")
        count_label.setStyleSheet("font-size: 11px; color: #E65100; font-weight: bold;")
        summary.addWidget(count_label)

        self._toggle_btn = QPushButton("Expand")
        self._toggle_btn.setStyleSheet("font-size: 11px;")
        self._toggle_btn.clicked.connect(self._toggle)
        summary.addWidget(self._toggle_btn)

        layout.addLayout(summary)

        # Detail area (hidden by default)
        self._detail = QWidget()
        self._detail_layout = QVBoxLayout(self._detail)
        self._detail_layout.setContentsMargins(16, 4, 0, 4)
        self._detail.setVisible(False)
        layout.addWidget(self._detail)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._detail.setVisible(self._expanded)
        self._toggle_btn.setText("Collapse" if self._expanded else "Expand")

        if self._expanded:
            self._load_detail()

    def _load_detail(self) -> None:
        """Load and display the full impact set with review actions."""
        # Clear existing
        while self._detail_layout.count():
            child = self._detail_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        impacts = load_impacts_for_change_set(self._conn, self._entry.impact_ids)
        if not impacts:
            empty = QLabel("No impacts in this change set")
            empty.setStyleSheet("color: #757575; font-size: 11px;")
            self._detail_layout.addWidget(empty)
            return

        # Summary
        summary = compute_impact_summary(impacts)
        self._detail_layout.addWidget(ImpactSummaryHeader(summary))

        # Group by table with review actions
        groups = group_impacts_by_table(impacts)
        for table_name in sorted(groups.keys()):
            review_list, info_list = groups[table_name]
            all_in_group = review_list + info_list

            # Bulk review bar
            bulk_bar = BulkReviewBar(all_in_group, self._conn)
            bulk_bar.bulk_reviewed.connect(self._on_reviewed)
            self._detail_layout.addWidget(bulk_bar)

            # Individual impact rows with review actions
            for impact in review_list + info_list:
                row_widget = QWidget()
                row_layout = QVBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(2)

                row_layout.addWidget(ImpactRow(impact))

                if not impact.reviewed:
                    actions = ReviewActions(impact, self._conn)
                    actions.reviewed.connect(lambda *_: self._on_reviewed())
                    row_layout.addWidget(actions)

                self._detail_layout.addWidget(row_widget)

        self._detail_layout.addStretch()

    def _on_reviewed(self) -> None:
        """Refresh after a review action."""
        self._load_detail()
        self.change_reviewed.emit()


class FlaggedWorkItemCard(QWidget):
    """A card for a flagged work item in the revision queue.

    :param entry: The flagged work item data.
    :param conn: Client database connection.
    :param parent: Parent widget.
    """

    revision_triggered = Signal()  # Emitted after successful revision

    def __init__(
        self, entry: FlaggedWorkItemEntry, conn: sqlite3.Connection, parent=None
    ) -> None:
        super().__init__(parent)
        self._entry = entry
        self._conn = conn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Name and count
        name = format_work_item_name(
            entry.item_type, entry.domain_name, entry.entity_name, entry.process_name
        )
        top = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        top.addWidget(name_label, stretch=1)

        count_label = QLabel(f"{entry.flagged_count} flagged")
        count_label.setStyleSheet("font-size: 11px; color: #C62828; font-weight: bold;")
        top.addWidget(count_label)
        layout.addLayout(top)

        # Impact summaries
        for desc in entry.impact_summaries[:3]:
            desc_label = QLabel(f"  - {desc}")
            desc_label.setStyleSheet("font-size: 11px; color: #424242;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        if entry.flagged_count > 3:
            more = QLabel(f"  ... and {entry.flagged_count - 3} more")
            more.setStyleSheet("font-size: 11px; color: #757575;")
            layout.addWidget(more)

        # Eligibility and action
        if entry.eligible:
            btn = QPushButton("Reopen for Revision")
            btn.setStyleSheet(
                "QPushButton { background-color: #FFA726; color: white; "
                "border-radius: 4px; padding: 4px 12px; font-size: 11px; } "
                "QPushButton:hover { background-color: #FB8C00; }"
            )
            btn.clicked.connect(self._do_revise)
            layout.addWidget(btn)
        else:
            reason_label = QLabel(entry.eligibility_reason)
            reason_label.setStyleSheet("font-size: 11px; color: #757575; font-style: italic;")
            reason_label.setWordWrap(True)
            layout.addWidget(reason_label)

    def _do_revise(self) -> None:
        """Prompt for revision reason and trigger the revision."""
        # Pre-populate with impact summaries
        default_reason = "; ".join(self._entry.impact_summaries[:3])

        reason, ok = QInputDialog.getMultiLineText(
            self, "Revision Reason",
            "Enter the reason for reopening this work item.\n"
            "This will be included in the next prompt generation.",
            default_reason,
        )
        if not ok or not reason.strip():
            return

        if not confirm_action(
            self, "Reopen for Revision",
            "Reopen this item for revision? This will cascade to downstream items."
        ):
            return

        try:
            from automation.workflow.engine import WorkflowEngine
            engine = WorkflowEngine(self._conn)
            engine.revise(self._entry.work_item_id)

            # Store reason for next PromptGenerator call (ISS-013)
            store_revision_reason(self._entry.work_item_id, reason.strip())

            show_toast(self, "Work item reopened for revision")
            self.revision_triggered.emit()
        except Exception as e:
            show_error(self, "Revision Failed", str(e))


class ImpactView(QWidget):
    """Impact Review sidebar view (Section 14.6.5).

    Two vertical sections: Unresolved Changes, Flagged Work Items.

    :param parent: Parent widget.
    """

    item_changed = Signal()  # Emitted after any state-changing action

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("Impact Review")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1F3864; padding: 8px;"
        )
        main_layout.addWidget(title)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 8, 4)
        scroll.setWidget(self._content)
        main_layout.addWidget(scroll, stretch=1)

    def refresh(self, conn: sqlite3.Connection) -> None:
        """Reload all data.

        :param conn: Client database connection.
        """
        self._conn = conn

        # Clear existing
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # --- Unresolved Changes ---
        section_header = QLabel("Unresolved Changes")
        section_header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1F3864; "
            "padding: 8px 0 4px 0;"
        )
        self._content_layout.addWidget(section_header)

        change_sets = load_change_sets(conn)
        if change_sets:
            for cs in change_sets:
                card = ChangeSetCard(cs, conn)
                card.change_reviewed.connect(lambda: self.refresh(conn))
                self._content_layout.addWidget(card)
        else:
            empty = QLabel("All changes have been reviewed.")
            empty.setStyleSheet("color: #757575; padding: 8px; font-size: 12px;")
            self._content_layout.addWidget(empty)

        # Separator
        sep = QLabel("")
        sep.setStyleSheet("border-top: 1px solid #E0E0E0; margin: 8px 0;")
        sep.setFixedHeight(1)
        self._content_layout.addWidget(sep)

        # --- Flagged Work Items ---
        flagged_header = QLabel("Flagged Work Items")
        flagged_header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1F3864; "
            "padding: 8px 0 4px 0;"
        )
        self._content_layout.addWidget(flagged_header)

        flagged = load_flagged_work_items(conn)
        if flagged:
            for entry in flagged:
                card = FlaggedWorkItemCard(entry, conn)
                card.revision_triggered.connect(self._on_revision_triggered)
                self._content_layout.addWidget(card)
        else:
            empty = QLabel("No work items are flagged for revision.")
            empty.setStyleSheet("color: #757575; padding: 8px; font-size: 12px;")
            self._content_layout.addWidget(empty)

        self._content_layout.addStretch()

    def _on_revision_triggered(self) -> None:
        """Refresh after a revision."""
        if self._conn:
            self.refresh(self._conn)
        self.item_changed.emit()
