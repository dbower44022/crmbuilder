"""Work item header action buttons (Section 14.3.3).

All 9 action buttons. Buttons are never disabled — clicking an
inapplicable action shows an explanatory message.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QTabWidget,
    QWidget,
)

from automation.ui.common.confirmation import confirm_action
from automation.ui.common.error_display import show_info
from automation.ui.work_item.work_item_logic import (
    WorkItemDetail,
    get_available_actions,
)
from automation.workflow.engine import WorkflowEngine

ACTION_LABELS: dict[str, str] = {
    "start_work": "Start Work",
    "mark_complete": "Mark Complete",
    "reopen_for_revision": "Reopen for Revision",
    "block": "Block",
    "unblock": "Unblock",
    "generate_prompt": "Generate Prompt",
    "run_import": "Run Import",
    "generate_document": "Generate Document",
    "view_impact_analysis": "View Impacts",
}

# Warm orange for secondary buttons per feedback_button_styling.md
_SECONDARY_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)
_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)


class HeaderActions(QWidget):
    """Action button bar for the work item detail header.

    :param parent: Parent widget.
    """

    action_completed = Signal()  # Emitted after any state-changing action
    navigate_to_session = Signal(int)  # work_item_id — drill-down to session view
    navigate_to_import = Signal(int)  # work_item_id — drill-down to import view
    navigate_to_documents = Signal(int)  # work_item_id — navigate to Documents view

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._item: WorkItemDetail | None = None
        self._conn: sqlite3.Connection | None = None
        self._buttons: dict[str, QPushButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Workflow actions (primary style)
        for action in ("start_work", "mark_complete", "reopen_for_revision", "block", "unblock"):
            btn = QPushButton(ACTION_LABELS[action])
            btn.setStyleSheet(_PRIMARY_STYLE)
            btn.clicked.connect(lambda checked, a=action: self._on_action(a))
            layout.addWidget(btn)
            self._buttons[action] = btn

        layout.addStretch()

        # Tool actions (secondary/orange style)
        for action in ("generate_prompt", "run_import", "generate_document", "view_impact_analysis"):
            btn = QPushButton(ACTION_LABELS[action])
            btn.setStyleSheet(_SECONDARY_STYLE)
            btn.clicked.connect(lambda checked, a=action: self._on_action(a))
            layout.addWidget(btn)
            self._buttons[action] = btn

    def set_context(self, item: WorkItemDetail, conn: sqlite3.Connection) -> None:
        """Set the work item and database connection.

        :param item: The current work item.
        :param conn: Client database connection.
        """
        self._item = item
        self._conn = conn

    def _on_action(self, action: str) -> None:
        """Handle an action button click.

        If the action is not available, shows an explanatory message.
        Otherwise, performs the action via the WorkflowEngine.
        """
        if not self._item or not self._conn:
            return

        actions = get_available_actions(self._item.status)
        reason = actions.get(action)

        if reason is not None:
            # Action not available — show explanatory message (never disable buttons)
            show_info(self, "Action Not Available", reason)
            return

        # Dispatch the action
        if action == "start_work":
            self._do_start()
        elif action == "mark_complete":
            self._do_complete()
        elif action == "reopen_for_revision":
            self._do_revise()
        elif action == "block":
            self._do_block()
        elif action == "unblock":
            self._do_unblock()
        elif action == "generate_prompt":
            self.navigate_to_session.emit(self._item.id)
        elif action == "run_import":
            self.navigate_to_import.emit(self._item.id)
        elif action == "generate_document":
            self.navigate_to_documents.emit(self._item.id)
        elif action == "view_impact_analysis":
            # Per Section 14.3.3, the Impacts tab is the entry point.
            # Find the parent QTabWidget and switch to the Impacts tab (index 3).
            parent = self.parent()
            while parent is not None:
                tabs = parent.findChild(QTabWidget)
                if tabs is not None:
                    tabs.setCurrentIndex(3)
                    break
                parent = parent.parent()

    def _do_start(self) -> None:
        if confirm_action(self, "Start Work", "Start working on this item?"):
            engine = WorkflowEngine(self._conn)
            engine.start(self._item.id)
            self.action_completed.emit()

    def _do_complete(self) -> None:
        if confirm_action(self, "Mark Complete", "Mark this item as complete?"):
            engine = WorkflowEngine(self._conn)
            engine.complete(self._item.id)
            self.action_completed.emit()

    def _do_revise(self) -> None:
        if confirm_action(
            self, "Reopen for Revision",
            "Reopen this item for revision? This will cascade to downstream items."
        ):
            engine = WorkflowEngine(self._conn)
            engine.revise(self._item.id)
            self.action_completed.emit()

    def _do_block(self) -> None:
        reason, ok = QInputDialog.getText(
            self, "Block Work Item", "Enter the reason for blocking:"
        )
        if ok and reason.strip():
            engine = WorkflowEngine(self._conn)
            engine.block(self._item.id, reason.strip())
            self.action_completed.emit()

    def _do_unblock(self) -> None:
        if confirm_action(self, "Unblock", "Unblock this work item?"):
            engine = WorkflowEngine(self._conn)
            engine.unblock(self._item.id)
            self.action_completed.emit()
