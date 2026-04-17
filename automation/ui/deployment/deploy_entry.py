"""Deploy sidebar entry — history table + wizard button (Section 14.12.4)."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import (
    DeploymentRunRow,
    InstanceRow,
    load_deployment_runs,
)
from espo_impl.ui.grid_helpers import enhance_table

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 8px 18px; font-size: 13px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)

_EMPTY_NO_INSTANCES = (
    "No CRM instances have been created for this client yet.\n\n"
    "Go to the Instances entry to create one, or start the\n"
    "Deploy Wizard which will create an instance for you."
)

_EMPTY_NO_RUNS = (
    "No deployment runs recorded yet.\n\n"
    "Click 'Start Deploy Wizard' above to begin a deployment."
)


class DeployEntry(QWidget):
    """Deploy history table and wizard launch button.

    :param parent: Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._runs: list[DeploymentRunRow] = []
        self._master_db_path: str | None = None
        self._client_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Wizard button header
        header = QHBoxLayout()
        self._wizard_btn = QPushButton("Start Deploy Wizard")
        self._wizard_btn.setStyleSheet(_PRIMARY_STYLE)
        self._wizard_btn.clicked.connect(self._on_start_wizard)
        header.addWidget(self._wizard_btn)
        header.addStretch()
        layout.addLayout(header)

        # Empty state
        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        # History table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Instance", "Scenario", "Started", "Completed", "Outcome", "Log"]
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        enhance_table(
            self._table,
            context_menu_builder=self._context_menu_actions,
        )
        layout.addWidget(self._table, stretch=1)

    def set_client_context(
        self, master_db_path: str, client_id: int,
    ) -> None:
        """Set the client context needed for the wizard.

        :param master_db_path: Path to the master database.
        :param client_id: Active client ID.
        """
        self._master_db_path = master_db_path
        self._client_id = client_id

    def refresh(
        self,
        conn: sqlite3.Connection,
        instance: InstanceRow | None,
        has_instances: bool,
    ) -> None:
        """Reload deployment history.

        :param conn: Per-client database connection.
        :param instance: The active instance (may be None).
        :param has_instances: Whether the client has any instances at all.
        """
        self._conn = conn
        self._instance = instance

        if not has_instances:
            self._empty_label.setText(_EMPTY_NO_INSTANCES)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        self._runs = load_deployment_runs(conn)
        if not self._runs:
            self._empty_label.setText(_EMPTY_NO_RUNS)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._table.setVisible(True)
        self._populate_table()

    def _context_menu_actions(self) -> list:
        """Build context menu items based on current selection."""
        return [("Start Deploy Wizard", self._on_start_wizard)]

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._runs))
        for row, run in enumerate(self._runs):
            self._table.setItem(row, 0, QTableWidgetItem(run.instance_name))
            self._table.setItem(row, 1, QTableWidgetItem(run.scenario))
            self._table.setItem(row, 2, QTableWidgetItem(run.started_at or ""))
            self._table.setItem(
                row, 3, QTableWidgetItem(run.completed_at or "—")
            )
            outcome_item = QTableWidgetItem(run.outcome or "—")
            if run.outcome == "success":
                outcome_item.setForeground(Qt.GlobalColor.darkGreen)
            elif run.outcome == "failure":
                outcome_item.setForeground(Qt.GlobalColor.red)
            self._table.setItem(row, 4, outcome_item)
            self._table.setItem(
                row, 5, QTableWidgetItem("View" if run.log_path else "—")
            )
        self._table.resizeColumnsToContents()

    def _on_start_wizard(self) -> None:
        """Handle Start Deploy Wizard click — launch the real wizard."""
        if not self._conn:
            QMessageBox.warning(
                self, "No Connection",
                "No client database connection available.",
            )
            return

        if not self._master_db_path or not self._client_id:
            QMessageBox.warning(
                self, "No Client",
                "No active client. Select a client from the Clients tab first.",
            )
            return

        from automation.core.deployment.wizard_logic import get_pre_selection
        from automation.ui.deployment.deploy_wizard.wizard_dialog import DeployWizard

        pre = get_pre_selection(self._master_db_path, self._client_id)
        wizard = DeployWizard(
            conn=self._conn,
            pre_selection=pre,
            master_db_path=self._master_db_path,
            client_id=self._client_id,
            parent=self,
        )
        wizard.exec()

        # Refresh history table after wizard completes
        if self._conn:
            self._runs = load_deployment_runs(self._conn)
            if self._runs:
                self._empty_label.setVisible(False)
                self._table.setVisible(True)
                self._populate_table()
            else:
                self._empty_label.setText(_EMPTY_NO_RUNS)
                self._empty_label.setVisible(True)
                self._table.setVisible(False)
