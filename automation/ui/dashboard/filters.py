"""Filter controls for the Requirements Dashboard (Section 14.2.4).

Domain, phase, and status filters with removable tags.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from automation.workflow.phases import PHASE_NAMES


class FilterBar(QWidget):
    """Filter controls for the Requirements Dashboard inventory and work queue.

    :param parent: Parent widget.
    """

    filters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        layout.addWidget(QLabel("Filters:"))

        # Domain filter
        self._domain_combo = QComboBox()
        self._domain_combo.addItem("All Domains", None)
        self._domain_combo.currentIndexChanged.connect(self._on_filter_change)
        layout.addWidget(self._domain_combo)

        # Phase filter
        self._phase_combo = QComboBox()
        self._phase_combo.addItem("All Phases", None)
        for num, name in sorted(PHASE_NAMES.items()):
            self._phase_combo.addItem(f"Phase {num}: {name}", num)
        self._phase_combo.currentIndexChanged.connect(self._on_filter_change)
        layout.addWidget(self._phase_combo)

        # Status filter
        self._status_combo = QComboBox()
        self._status_combo.addItem("All Statuses", None)
        for status in ("not_started", "ready", "in_progress", "complete", "blocked"):
            self._status_combo.addItem(status.replace("_", " ").title(), status)
        self._status_combo.currentIndexChanged.connect(self._on_filter_change)
        layout.addWidget(self._status_combo)

        # Clear all
        self._clear_btn = QPushButton("Clear Filters")
        self._clear_btn.clicked.connect(self.clear_filters)
        layout.addWidget(self._clear_btn)

        layout.addStretch()

    @property
    def domain_filter(self) -> str | None:
        return self._domain_combo.currentData()

    @property
    def phase_filter(self) -> int | None:
        return self._phase_combo.currentData()

    @property
    def status_filter(self) -> str | None:
        return self._status_combo.currentData()

    def set_domains(self, domains: list[str]) -> None:
        """Update the domain filter options.

        :param domains: List of domain names.
        """
        self._domain_combo.blockSignals(True)
        current = self._domain_combo.currentData()
        self._domain_combo.clear()
        self._domain_combo.addItem("All Domains", None)
        for d in domains:
            self._domain_combo.addItem(d, d)
        # Restore selection if still valid
        if current:
            idx = self._domain_combo.findData(current)
            if idx >= 0:
                self._domain_combo.setCurrentIndex(idx)
        self._domain_combo.blockSignals(False)

    def clear_filters(self) -> None:
        """Reset all filters to 'All'."""
        self._domain_combo.setCurrentIndex(0)
        self._phase_combo.setCurrentIndex(0)
        self._status_combo.setCurrentIndex(0)

    def _on_filter_change(self) -> None:
        self.filters_changed.emit()
