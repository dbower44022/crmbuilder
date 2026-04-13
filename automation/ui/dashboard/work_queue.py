"""Actionable work queue (Section 14.2.2).

Two groups: Continue Work (in_progress) and Ready to Start (ready).
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.readable_first import format_work_item_name
from automation.ui.common.staleness_indicators import StalenessIndicator
from automation.ui.common.status_badges import StatusBadge
from automation.ui.common.status_row_styling import apply_work_item_row_style
from automation.ui.dashboard.dashboard_logic import WorkItemRow


class WorkQueueRow(QWidget):
    """A single row in the work queue.

    :param item: The work item data.
    :param parent: Parent widget.
    """

    clicked = Signal(int)

    def __init__(self, item: WorkItemRow, parent=None) -> None:
        super().__init__(parent)
        self._item_id = item.id
        self.setCursor(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CursorShape.PointingHandCursor
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Name
        name = format_work_item_name(
            item.item_type, item.domain_name, item.entity_name, item.process_name
        )
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 13px; font-weight: 500;")
        layout.addWidget(name_label, stretch=2)

        # Phase
        phase_label = QLabel(f"Phase {item.phase}")
        phase_label.setStyleSheet("font-size: 11px; color: #757575;")
        layout.addWidget(phase_label)

        # Type
        type_label = QLabel(item.item_type.replace("_", " ").title())
        type_label.setStyleSheet("font-size: 11px; color: #757575;")
        layout.addWidget(type_label)

        # Status badge
        badge = StatusBadge(item.status)
        layout.addWidget(badge)

        # Context info (started_at for in_progress)
        if item.status == "in_progress" and item.started_at:
            ctx_label = QLabel(f"Started: {item.started_at[:10]}")
            ctx_label.setStyleSheet("font-size: 11px; color: #757575;")
            layout.addWidget(ctx_label)

        # Staleness indicator (for display only — data calculated elsewhere)
        self._staleness = StalenessIndicator(False)
        layout.addWidget(self._staleness)

        apply_work_item_row_style(self, item.status)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._item_id)
        super().mousePressEvent(event)


class WorkQueue(QWidget):
    """The actionable work queue with Continue Work and Ready sections.

    :param parent: Parent widget.
    """

    item_clicked = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def update_items(self, items: list[WorkItemRow]) -> None:
        """Replace the queue contents with new items.

        :param items: Work items, already sorted (in_progress first, then ready).
        """
        # Clear existing
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        in_progress = [i for i in items if i.status == "in_progress"]
        ready = [i for i in items if i.status == "ready"]

        if in_progress:
            header = QLabel("Continue Work")
            header.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #E65100; "
                "padding: 4px 8px; margin-top: 4px;"
            )
            self._layout.addWidget(header)
            for item in in_progress:
                row = WorkQueueRow(item)
                row.clicked.connect(self.item_clicked.emit)
                self._layout.addWidget(row)

        if ready:
            header = QLabel("Ready to Start")
            header.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #1565C0; "
                "padding: 4px 8px; margin-top: 4px;"
            )
            self._layout.addWidget(header)
            for item in ready:
                row = WorkQueueRow(item)
                row.clicked.connect(self.item_clicked.emit)
                self._layout.addWidget(row)

        if not items:
            empty = QLabel("No actionable work items")
            empty.setStyleSheet("color: #757575; padding: 12px;")
            self._layout.addWidget(empty)

        self._layout.addStretch()
