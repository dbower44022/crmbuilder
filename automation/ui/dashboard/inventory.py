"""Full project inventory (Section 14.2.3).

Collapsible section grouped by phase, with completion indicators.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.readable_first import format_work_item_name
from automation.ui.common.status_badges import StatusBadge
from automation.ui.common.status_row_styling import apply_work_item_row_style
from automation.ui.dashboard.dashboard_logic import PhaseGroup, WorkItemRow


class InventoryItemRow(QWidget):
    """A single work item row in the inventory.

    :param item: The work item data.
    :param parent: Parent widget.
    """

    clicked = Signal(int)

    def __init__(self, item: WorkItemRow, parent=None) -> None:
        super().__init__(parent)
        self._item_id = item.id
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 2, 8, 2)

        name = format_work_item_name(
            item.item_type, item.domain_name, item.entity_name, item.process_name
        )
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(name_label, stretch=2)

        badge = StatusBadge(item.status)
        layout.addWidget(badge)

        if item.blocked_reason:
            reason = QLabel(f"Blocked: {item.blocked_reason}")
            reason.setStyleSheet("font-size: 11px; color: #C62828;")
            layout.addWidget(reason)

        apply_work_item_row_style(self, item.status)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._item_id)
        super().mousePressEvent(event)


class PhaseSection(QWidget):
    """A collapsible phase group in the inventory.

    :param group: The phase group data.
    :param parent: Parent widget.
    """

    item_clicked = Signal(int)

    def __init__(self, group: PhaseGroup, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 4, 8, 4)

        self._toggle_btn = QPushButton(f"Phase {group.phase}: {group.phase_name}")
        self._toggle_btn.setStyleSheet(
            "font-size: 13px; font-weight: bold; text-align: left; "
            "border: none; padding: 4px;"
        )
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self._toggle_btn, stretch=1)

        completion = QLabel(f"{group.complete_count}/{group.total_count}")
        completion.setStyleSheet("font-size: 12px; color: #757575;")
        header_layout.addWidget(completion)

        if group.complete_count == group.total_count and group.total_count > 0:
            done_label = QLabel(" Done ")
            done_label.setStyleSheet(
                "background-color: #E8F5E9; color: #2E7D32; "
                "border-radius: 4px; padding: 2px 6px; font-size: 11px;"
            )
            header_layout.addWidget(done_label)

        layout.addLayout(header_layout)

        # Item container
        self._items_container = QWidget()
        items_layout = QVBoxLayout(self._items_container)
        items_layout.setContentsMargins(0, 0, 0, 0)
        items_layout.setSpacing(0)

        for item in group.items:
            row = InventoryItemRow(item)
            row.clicked.connect(self.item_clicked.emit)
            items_layout.addWidget(row)

        layout.addWidget(self._items_container)
        self._expanded = True

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._items_container.setVisible(self._expanded)


class ProjectInventory(QWidget):
    """Collapsible full project inventory grouped by phase.

    :param parent: Parent widget.
    """

    item_clicked = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Collapse/expand all header
        header = QHBoxLayout()
        title = QLabel("Full Project Inventory")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 8px;")
        header.addWidget(title)
        header.addStretch()
        self._toggle_all_btn = QPushButton("Collapse All")
        self._toggle_all_btn.clicked.connect(self._toggle_all)
        header.addWidget(self._toggle_all_btn)
        self._layout.addLayout(header)

        self._phases_container = QWidget()
        self._phases_layout = QVBoxLayout(self._phases_container)
        self._phases_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._phases_container)
        self._phase_sections: list[PhaseSection] = []

    def update_groups(self, groups: list[PhaseGroup]) -> None:
        """Replace the inventory with new phase groups.

        :param groups: Phase groups sorted by phase number.
        """
        # Clear existing
        for section in self._phase_sections:
            section.deleteLater()
        self._phase_sections.clear()
        while self._phases_layout.count():
            self._phases_layout.takeAt(0)

        for group in groups:
            section = PhaseSection(group)
            section.item_clicked.connect(self.item_clicked.emit)
            self._phases_layout.addWidget(section)
            self._phase_sections.append(section)

        self._phases_layout.addStretch()

    def _toggle_all(self) -> None:
        """Toggle all phase sections."""
        if self._toggle_all_btn.text() == "Collapse All":
            for section in self._phase_sections:
                section._expanded = False
                section._items_container.setVisible(False)
            self._toggle_all_btn.setText("Expand All")
        else:
            for section in self._phase_sections:
                section._expanded = True
                section._items_container.setVisible(True)
            self._toggle_all_btn.setText("Collapse All")
