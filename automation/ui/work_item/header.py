"""Work item header (Section 14.3.2).

Displays work item name, phase, status badge, scoping info,
blocked reason, timestamps, and staleness indicator.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from automation.ui.common.readable_first import format_work_item_name
from automation.ui.common.staleness_indicators import StalenessIndicator
from automation.ui.common.status_badges import StatusBadge
from automation.ui.work_item.work_item_logic import WorkItemDetail


class WorkItemHeader(QWidget):
    """Persistent header for the Work Item Detail view.

    :param parent: Parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Top row: name + status badge
        top = QHBoxLayout()
        self._name_label = QLabel()
        self._name_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1F3864;"
        )
        top.addWidget(self._name_label, stretch=1)

        self._status_badge = StatusBadge()
        top.addWidget(self._status_badge)

        self._staleness = StalenessIndicator()
        top.addWidget(self._staleness)

        layout.addLayout(top)

        # Detail row: phase, type, scoping
        detail = QHBoxLayout()
        self._phase_label = QLabel()
        self._phase_label.setStyleSheet("font-size: 12px; color: #757575;")
        detail.addWidget(self._phase_label)

        self._type_label = QLabel()
        self._type_label.setStyleSheet("font-size: 12px; color: #757575;")
        detail.addWidget(self._type_label)

        self._scope_label = QLabel()
        self._scope_label.setStyleSheet("font-size: 12px; color: #757575;")
        detail.addWidget(self._scope_label)

        detail.addStretch()

        self._timestamp_label = QLabel()
        self._timestamp_label.setStyleSheet("font-size: 11px; color: #9E9E9E;")
        detail.addWidget(self._timestamp_label)

        layout.addLayout(detail)

        # Blocked reason row (hidden when not blocked)
        self._blocked_label = QLabel()
        self._blocked_label.setStyleSheet(
            "font-size: 12px; color: #C62828; padding: 4px 0px;"
        )
        self._blocked_label.setVisible(False)
        layout.addWidget(self._blocked_label)

    def update_item(self, item: WorkItemDetail) -> None:
        """Refresh the header with new work item data.

        :param item: The work item detail.
        """
        name = format_work_item_name(
            item.item_type, item.domain_name, item.entity_name, item.process_name
        )
        self._name_label.setText(name)
        self._status_badge.set_status(item.status)
        self._phase_label.setText(f"Phase {item.phase}: {item.phase_name}")
        self._type_label.setText(f"Type: {item.item_type.replace('_', ' ').title()}")

        # Scoping
        parts = []
        if item.domain_name:
            parts.append(f"Domain: {item.domain_name}")
        if item.entity_name:
            parts.append(f"Entity: {item.entity_name}")
        if item.process_name:
            parts.append(f"Process: {item.process_name}")
        self._scope_label.setText("  |  ".join(parts) if parts else "")

        # Timestamps
        if item.status == "in_progress" and item.started_at:
            self._timestamp_label.setText(f"Started: {item.started_at[:10]}")
        elif item.status == "complete" and item.completed_at:
            self._timestamp_label.setText(f"Completed: {item.completed_at[:10]}")
        else:
            self._timestamp_label.setText("")

        # Blocked reason
        if item.blocked_reason:
            self._blocked_label.setText(f"Blocked: {item.blocked_reason}")
            self._blocked_label.setVisible(True)
        else:
            self._blocked_label.setVisible(False)

        # Staleness — placeholder, real check in Step 15c
        self._staleness.set_stale(False)
