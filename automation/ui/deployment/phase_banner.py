"""Phase status banner for deployment entries (Section 14.12.2).

Shown above Deploy, Configure, and Verify entries.  Displays the
corresponding Phase 10/11/12 work item's status badge and a
"Mark Complete" button that updates the status without leaving
the Deployment tab.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from automation.ui.common.confirmation import confirm_action
from automation.ui.common.error_display import show_info
from automation.ui.common.status_badges import StatusBadge
from automation.ui.deployment.deployment_logic import (
    ENTRY_TO_WORK_ITEM_TYPE,
    PhaseWorkItem,
    get_phase_work_item,
)
from automation.workflow.engine import WorkflowEngine

# Phase display names
_PHASE_LABELS: dict[str, str] = {
    "crm_deployment": "Phase 10 — CRM Deployment",
    "crm_configuration": "Phase 11 — CRM Configuration",
    "verification": "Phase 12 — Verification",
}

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 4px 10px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)

# Warm orange for secondary actions per feedback_button_styling.md
_START_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 4px 10px; font-size: 12px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)


class PhaseBanner(QWidget):
    """Phase status banner with badge and Mark Complete action.

    :param parent: Parent widget.
    """

    status_changed = Signal()  # Emitted after a workflow transition

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._work_item: PhaseWorkItem | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._phase_label = QLabel()
        self._phase_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self._phase_label)

        self._badge = StatusBadge()
        layout.addWidget(self._badge)

        layout.addStretch()

        self._start_btn = QPushButton("Start Work")
        self._start_btn.setStyleSheet(_START_STYLE)
        self._start_btn.clicked.connect(self._on_start)
        layout.addWidget(self._start_btn)

        self._complete_btn = QPushButton("Mark Complete")
        self._complete_btn.setStyleSheet(_PRIMARY_STYLE)
        self._complete_btn.clicked.connect(self._on_complete)
        layout.addWidget(self._complete_btn)

    def set_entry(
        self, entry_name: str, conn: sqlite3.Connection | None
    ) -> None:
        """Update the banner for the given sidebar entry.

        :param entry_name: The sidebar entry name (Deploy, Configure, Verify).
        :param conn: Per-client database connection.
        """
        self._conn = conn
        item_type = ENTRY_TO_WORK_ITEM_TYPE.get(entry_name)
        if not item_type or not conn:
            self.setVisible(False)
            self._work_item = None
            return

        self._work_item = get_phase_work_item(conn, item_type)
        if self._work_item is None:
            self.setVisible(False)
            return

        self.setVisible(True)
        label = _PHASE_LABELS.get(item_type, item_type)
        self._phase_label.setText(label)
        self._badge.set_status(self._work_item.status)

    def _on_start(self) -> None:
        """Handle Start Work button click."""
        if not self._work_item or not self._conn:
            return

        if self._work_item.status != "ready":
            show_info(
                self,
                "Action Not Available",
                f"Cannot start work: status is '{self._work_item.status}'. "
                f"Item must be in 'ready' status to start.",
            )
            return

        if confirm_action(self, "Start Work", "Start working on this phase?"):
            engine = WorkflowEngine(self._conn)
            engine.start(self._work_item.id)
            # Refresh
            self._work_item = get_phase_work_item(
                self._conn, self._work_item.item_type
            )
            if self._work_item:
                self._badge.set_status(self._work_item.status)
            self.status_changed.emit()

    def _on_complete(self) -> None:
        """Handle Mark Complete button click."""
        if not self._work_item or not self._conn:
            return

        if self._work_item.status != "in_progress":
            show_info(
                self,
                "Action Not Available",
                f"Cannot mark complete: status is '{self._work_item.status}'. "
                f"Item must be 'in_progress' to mark complete.",
            )
            return

        if confirm_action(
            self, "Mark Complete", "Mark this phase as complete?"
        ):
            engine = WorkflowEngine(self._conn)
            engine.complete(self._work_item.id)
            # Refresh
            self._work_item = get_phase_work_item(
                self._conn, self._work_item.item_type
            )
            if self._work_item:
                self._badge.set_status(self._work_item.status)
            self.status_changed.emit()
