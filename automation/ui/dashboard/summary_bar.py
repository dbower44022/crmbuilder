"""Project summary bar (Section 14.2.1).

Displays client name, total work item count, and counts by status.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from automation.ui.common.status_badges import StatusBadge
from automation.ui.dashboard.dashboard_logic import ProjectSummary


class SummaryBar(QWidget):
    """Horizontal bar showing project-level summary statistics.

    :param parent: Parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._client_label = QLabel()
        self._client_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1F3864;"
        )
        layout.addWidget(self._client_label)

        self._total_label = QLabel()
        self._total_label.setStyleSheet("font-size: 13px; color: #424242;")
        layout.addWidget(self._total_label)

        layout.addStretch()

        # Status count badges
        self._badges: dict[str, tuple[StatusBadge, QLabel]] = {}
        for status in ("not_started", "ready", "in_progress", "complete", "blocked"):
            badge = StatusBadge(status)
            count_label = QLabel("0")
            count_label.setStyleSheet("font-size: 12px; margin-left: 2px; margin-right: 8px;")
            layout.addWidget(badge)
            layout.addWidget(count_label)
            self._badges[status] = (badge, count_label)

    def update_summary(self, summary: ProjectSummary) -> None:
        """Refresh the bar with new summary data.

        :param summary: The computed project summary.
        """
        self._client_label.setText(summary.client_name)
        self._total_label.setText(f"{summary.total} work items")
        counts = {
            "not_started": summary.not_started,
            "ready": summary.ready,
            "in_progress": summary.in_progress,
            "complete": summary.complete,
            "blocked": summary.blocked,
        }
        for status, (_badge, label) in self._badges.items():
            label.setText(str(counts[status]))
