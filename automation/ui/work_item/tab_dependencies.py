"""Dependencies tab (Section 14.3.4).

Shows upstream and downstream dependencies, clickable to navigate.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from automation.ui.common.readable_first import format_work_item_name
from automation.ui.common.status_badges import StatusBadge
from automation.ui.work_item.work_item_logic import DependencyRow


class DependencyItemRow(QWidget):
    """A clickable dependency row.

    :param dep: The dependency data.
    :param highlight: Whether to highlight (incomplete upstream / reopened).
    :param parent: Parent widget.
    """

    clicked = Signal(int)

    def __init__(self, dep: DependencyRow, highlight: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._work_item_id = dep.work_item_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 2, 8, 2)

        name = format_work_item_name(
            dep.item_type, dep.domain_name, dep.entity_name, dep.process_name
        )
        name_label = QLabel(name)
        if highlight:
            name_label.setStyleSheet("font-size: 12px; color: #C62828; font-weight: bold;")
        else:
            name_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(name_label, stretch=1)

        badge = StatusBadge(dep.status)
        layout.addWidget(badge)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._work_item_id)
        super().mousePressEvent(event)


class DependenciesTab(QWidget):
    """Tab showing upstream and downstream dependencies.

    :param parent: Parent widget.
    """

    navigate_to_item = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def update_dependencies(
        self,
        deps: list[DependencyRow],
        current_status: str,
    ) -> None:
        """Refresh the tab with new dependency data.

        :param deps: All dependencies (upstream and downstream).
        :param current_status: The current work item's status.
        """
        # Clear
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        upstream = [d for d in deps if d.direction == "upstream"]
        downstream = [d for d in deps if d.direction == "downstream"]

        if upstream:
            header = QLabel("Upstream Dependencies")
            header.setStyleSheet(
                "font-size: 13px; font-weight: bold; padding: 4px 8px;"
            )
            self._layout.addWidget(header)
            for dep in upstream:
                # Highlight incomplete upstream for not_started items
                highlight = (
                    current_status == "not_started" and dep.status != "complete"
                )
                row = DependencyItemRow(dep, highlight=highlight)
                row.clicked.connect(self.navigate_to_item.emit)
                self._layout.addWidget(row)

        if downstream:
            header = QLabel("Downstream Dependents")
            header.setStyleSheet(
                "font-size: 13px; font-weight: bold; padding: 4px 8px; margin-top: 8px;"
            )
            self._layout.addWidget(header)
            for dep in downstream:
                row = DependencyItemRow(dep)
                row.clicked.connect(self.navigate_to_item.emit)
                self._layout.addWidget(row)

        if not deps:
            empty = QLabel("No dependencies")
            empty.setStyleSheet("color: #757575; padding: 12px;")
            self._layout.addWidget(empty)

        self._layout.addStretch()
