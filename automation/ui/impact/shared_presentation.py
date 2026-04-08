"""Shared impact presentation format (Section 14.6.1).

Single source of truth for rendering ChangeImpact records, used in:
1. Import Review trigger stage (14.5.7)
2. Work Item Detail Impacts tab (14.3.7)
3. Data Browser pre-commit confirmation (14.8)
4. Impact Review sidebar view (14.6.5)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.toast import show_toast
from automation.ui.impact.impact_logic import (
    ImpactDisplayRow,
    ImpactSummary,
    compute_impact_summary,
    group_impacts_by_table,
)


class ImpactSummaryHeader(QWidget):
    """Summary header showing total/review/informational/reviewed counts.

    :param summary: The computed summary.
    :param show_reviewed: Whether to show the reviewed count (post-commit only).
    :param parent: Parent widget.
    """

    def __init__(
        self, summary: ImpactSummary, show_reviewed: bool = True, parent=None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        parts = [
            f"Total: {summary.total}",
            f"Requires Review: {summary.requires_review}",
            f"Informational: {summary.informational}",
        ]
        if show_reviewed:
            parts.append(f"Reviewed: {summary.reviewed}")

        label = QLabel("  |  ".join(parts))
        label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #1F3864; "
            "padding: 6px 8px; background-color: #F2F7FB; border-radius: 4px;"
        )
        layout.addWidget(label)
        layout.addStretch()


class ImpactRow(QWidget):
    """A single impact row with description, source, and optional review status.

    :param impact: The impact data.
    :param show_review_status: Whether to show review status indicator.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        impact: ImpactDisplayRow,
        show_review_status: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._impact = impact

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 8, 2)

        # Affected record link (placeholder — Data Browser navigation in Step 15c)
        link = QPushButton(f"{impact.affected_table} #{impact.affected_record_id}")
        link.setStyleSheet(
            "font-size: 11px; border: none; color: #1565C0; "
            "text-decoration: underline; padding: 0;"
        )
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(
            lambda: show_toast(self, "Data Browser navigation coming in Step 15c")
        )
        layout.addWidget(link)

        # Impact description
        desc = QLabel(impact.impact_description or "No description")
        desc.setStyleSheet("font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc, stretch=1)

        # Source summary
        source = QLabel(impact.source_summary)
        source.setStyleSheet("font-size: 10px; color: #757575;")
        layout.addWidget(source)

        # Review status indicator (post-commit contexts only)
        if show_review_status:
            if impact.reviewed:
                if impact.action_required:
                    status_text = "Flagged"
                    color = "#C62828"
                else:
                    status_text = "Reviewed"
                    color = "#2E7D32"
            else:
                status_text = "Unreviewed"
                color = "#E65100"
            status_label = QLabel(status_text)
            status_label.setStyleSheet(f"font-size: 10px; color: {color}; font-weight: bold;")
            layout.addWidget(status_label)

        # Subdued styling for informational impacts
        if not impact.requires_review:
            self.setStyleSheet("background-color: #FAFAFA;")


class ImpactTableGroup(QWidget):
    """A group of impacts for a single affected table.

    :param table_name: The affected table name.
    :param review_impacts: Requires-review impacts.
    :param info_impacts: Informational impacts.
    :param show_review_status: Whether to show review status.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        table_name: str,
        review_impacts: list[ImpactDisplayRow],
        info_impacts: list[ImpactDisplayRow],
        show_review_status: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        # Group header
        total = len(review_impacts) + len(info_impacts)
        header = QLabel(f"{table_name} ({total})")
        header.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 4px 8px; "
            "background-color: #E8EAF6; border-radius: 2px;"
        )
        layout.addWidget(header)

        # Requires-review impacts first
        for impact in review_impacts:
            layout.addWidget(ImpactRow(impact, show_review_status))

        # Informational impacts in subdued styling
        for impact in info_impacts:
            layout.addWidget(ImpactRow(impact, show_review_status))


class SharedImpactPresentation(QWidget):
    """Renders a list of ChangeImpact records in the shared format.

    :param impacts: The impact rows to display.
    :param show_review_status: Whether to show review status (True for post-commit).
    :param show_reviewed_count: Whether to include reviewed count in summary.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        impacts: list[ImpactDisplayRow],
        show_review_status: bool = True,
        show_reviewed_count: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.update_impacts(impacts, show_review_status, show_reviewed_count)

    def update_impacts(
        self,
        impacts: list[ImpactDisplayRow],
        show_review_status: bool = True,
        show_reviewed_count: bool = True,
    ) -> None:
        """Refresh the display with new impact data.

        :param impacts: The impact rows.
        :param show_review_status: Whether to show review status.
        :param show_reviewed_count: Whether to include reviewed count.
        """
        # Clear existing
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not impacts:
            empty = QLabel("No impacts recorded")
            empty.setStyleSheet("color: #757575; padding: 12px;")
            self._layout.addWidget(empty)
            return

        # Summary header
        summary = compute_impact_summary(impacts)
        self._layout.addWidget(
            ImpactSummaryHeader(summary, show_reviewed=show_reviewed_count)
        )

        # Grouped by table
        groups = group_impacts_by_table(impacts)
        for table_name in sorted(groups.keys()):
            review_list, info_list = groups[table_name]
            self._layout.addWidget(
                ImpactTableGroup(
                    table_name, review_list, info_list,
                    show_review_status=show_review_status,
                )
            )

        self._layout.addStretch()
