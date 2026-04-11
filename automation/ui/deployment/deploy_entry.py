"""Deploy sidebar entry — history table + stub wizard button (Section 14.12.4).

The "Start Deploy Wizard" button is wired up but launches a stub dialog.
Prompt D will replace the stub with the real wizard.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
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
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table, stretch=1)

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

    def _on_start_wizard(self) -> None:
        """Handle Start Deploy Wizard click — stub for Prompt D."""
        QMessageBox.information(
            self,
            "Deploy Wizard",
            "Deploy Wizard not yet implemented \u2014 see Prompt D.",
        )
