"""Run History sidebar entry — configuration run audit trail.

Shows every YAML configuration run recorded in the ConfigurationRun table,
with filtering by instance and outcome.  Allows the user to see which
YAML files have been applied, their versions, and whether the file has
changed since it was last run.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    load_instances,
)

_EMPTY_NO_INSTANCES = (
    "No CRM instances available.\n\n"
    "Go to the Instances entry to create one."
)

_EMPTY_NO_RUNS = (
    "No configuration runs recorded yet.\n\n"
    "Use the Configure entry to run or verify YAML files\n"
    "against an instance."
)

_COL_HEADERS = [
    "File Name",
    "Version",
    "Operation",
    "Outcome",
    "Instance",
    "Started",
    "Completed",
    "Changed?",
]


class RunHistoryEntry(QWidget):
    """Configuration run history viewer with filters.

    :param parent: Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._project_folder: str | None = None
        self._runs: list[tuple] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter bar
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Instance:"))
        self._instance_filter = QComboBox()
        self._instance_filter.setMinimumWidth(180)
        self._instance_filter.currentIndexChanged.connect(self._on_filter)
        filter_bar.addWidget(self._instance_filter)

        filter_bar.addWidget(QLabel("Outcome:"))
        self._outcome_filter = QComboBox()
        self._outcome_filter.addItems(["All", "Success", "Error"])
        self._outcome_filter.currentIndexChanged.connect(self._on_filter)
        filter_bar.addWidget(self._outcome_filter)

        filter_bar.addWidget(QLabel("Operation:"))
        self._operation_filter = QComboBox()
        self._operation_filter.addItems(["All", "Run", "Verify"])
        self._operation_filter.currentIndexChanged.connect(self._on_filter)
        filter_bar.addWidget(self._operation_filter)

        filter_bar.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh_click)
        filter_bar.addWidget(self._refresh_btn)

        layout.addLayout(filter_bar)

        # Empty state
        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        # History table
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COL_HEADERS))
        self._table.setHorizontalHeaderLabels(_COL_HEADERS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table, stretch=1)

    def refresh(
        self,
        conn: sqlite3.Connection,
        instance: InstanceRow | None,
        project_folder: str | None,
        has_instances: bool,
    ) -> None:
        """Reload run history from the database.

        :param conn: Per-client database connection.
        :param instance: Active instance from the picker.
        :param project_folder: Client's project folder (for hash comparison).
        :param has_instances: Whether the client has any instances.
        """
        self._conn = conn
        self._instance = instance
        self._project_folder = project_folder

        if not has_instances:
            self._empty_label.setText(_EMPTY_NO_INSTANCES)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        self._refresh_instance_filter(conn)
        self._load_and_display()

    def _refresh_instance_filter(self, conn: sqlite3.Connection) -> None:
        """Populate the instance filter dropdown."""
        self._instance_filter.blockSignals(True)
        prev_text = self._instance_filter.currentText()
        self._instance_filter.clear()
        self._instance_filter.addItem("All", None)
        for inst in load_instances(conn):
            self._instance_filter.addItem(
                f"{inst.name} ({inst.environment})", inst.id
            )
        # Restore previous selection
        for i in range(self._instance_filter.count()):
            if self._instance_filter.itemText(i) == prev_text:
                self._instance_filter.setCurrentIndex(i)
                break
        self._instance_filter.blockSignals(False)

    def _load_and_display(self) -> None:
        """Query ConfigurationRun with current filters and populate the table."""
        if not self._conn:
            return

        # Check table exists
        table_exists = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='ConfigurationRun'"
        ).fetchone()
        if not table_exists:
            self._empty_label.setText(_EMPTY_NO_RUNS)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        # Build query with filters
        where_clauses = []
        params: list = []

        instance_id = self._instance_filter.currentData()
        if instance_id is not None:
            where_clauses.append("cr.instance_id = ?")
            params.append(instance_id)

        outcome_text = self._outcome_filter.currentText()
        if outcome_text == "Success":
            where_clauses.append("cr.outcome = 'success'")
        elif outcome_text == "Error":
            where_clauses.append("cr.outcome = 'error'")

        op_text = self._operation_filter.currentText()
        if op_text == "Run":
            where_clauses.append("cr.operation = 'run'")
        elif op_text == "Verify":
            where_clauses.append("cr.operation = 'verify'")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        rows = self._conn.execute(
            "SELECT cr.file_name, cr.file_version, cr.operation, "
            "cr.outcome, i.name, cr.started_at, cr.completed_at, "
            "cr.file_hash "
            "FROM ConfigurationRun cr "
            "JOIN Instance i ON i.id = cr.instance_id "
            f"{where_sql} "
            "ORDER BY cr.id DESC",
            params,
        ).fetchall()

        if not rows:
            self._empty_label.setText(_EMPTY_NO_RUNS)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._table.setVisible(True)
        self._populate_table(rows)

    def _populate_table(self, rows: list[tuple]) -> None:
        """Fill the table from query results."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))

        programs_dir = None
        if self._project_folder:
            programs_dir = Path(self._project_folder) / "programs"

        for row_idx, r in enumerate(rows):
            file_name, file_version, operation, outcome, inst_name, \
                started_at, completed_at, file_hash = r

            self._table.setItem(row_idx, 0, QTableWidgetItem(file_name))
            self._table.setItem(
                row_idx, 1, QTableWidgetItem(file_version or "—")
            )
            self._table.setItem(
                row_idx, 2, QTableWidgetItem(operation.capitalize())
            )

            outcome_item = QTableWidgetItem(outcome.capitalize())
            if outcome == "success":
                outcome_item.setForeground(QColor("#4CAF50"))
            elif outcome == "error":
                outcome_item.setForeground(QColor("#F44336"))
            self._table.setItem(row_idx, 3, outcome_item)

            self._table.setItem(row_idx, 4, QTableWidgetItem(inst_name))

            started_display = (started_at or "")[:19].replace("T", " ")
            self._table.setItem(
                row_idx, 5, QTableWidgetItem(started_display)
            )

            completed_display = (completed_at or "")[:19].replace("T", " ")
            self._table.setItem(
                row_idx, 6, QTableWidgetItem(completed_display)
            )

            # Changed? — compare stored hash with current file on disk
            changed_item = self._check_file_changed(
                programs_dir, file_name, file_hash
            )
            self._table.setItem(row_idx, 7, changed_item)

        self._table.setSortingEnabled(True)

    @staticmethod
    def _check_file_changed(
        programs_dir: Path | None,
        file_name: str,
        stored_hash: str | None,
    ) -> QTableWidgetItem:
        """Compare stored hash with the current file contents.

        :returns: A color-coded QTableWidgetItem.
        """
        if not programs_dir or not stored_hash:
            item = QTableWidgetItem("—")
            item.setForeground(QColor("#9E9E9E"))
            return item

        file_path = programs_dir / file_name
        if not file_path.is_file():
            item = QTableWidgetItem("File Missing")
            item.setForeground(QColor("#F44336"))
            return item

        try:
            current_hash = hashlib.sha256(
                file_path.read_bytes()
            ).hexdigest()
        except OSError:
            item = QTableWidgetItem("Read Error")
            item.setForeground(QColor("#F44336"))
            return item

        if current_hash == stored_hash:
            item = QTableWidgetItem("No")
            item.setForeground(QColor("#4CAF50"))
        else:
            item = QTableWidgetItem("Yes — file modified")
            item.setForeground(QColor("#FFA726"))
        return item

    # ── Filter handlers ────────────────────────────────────────────

    def _on_filter(self, _index: int = 0) -> None:
        self._load_and_display()

    def _on_refresh_click(self) -> None:
        self._load_and_display()
