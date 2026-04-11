"""Configure sidebar entry — YAML file list + actions (Section 14.12.7).

Thin wrapper over existing ``espo_impl`` check-then-act configuration,
scoped to the active client's ``{project_folder}/programs/`` and the
active instance from the picker.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
    YamlFileInfo,
    load_yaml_files,
)

_SECONDARY_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)

_EMPTY_NO_INSTANCES = (
    "No CRM instances available.\n\n"
    "Go to the Instances entry to create one, or run the Deploy Wizard."
)

_EMPTY_NO_YAML = (
    "No YAML program files found in this client's programs directory.\n\n"
    "Generate YAML files from the Requirements tab (Phase 8 — YAML Generation)\n"
    "to populate this list."
)


class ConfigureEntry(QWidget):
    """YAML file list with configuration actions.

    :param parent: Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._project_folder: str | None = None
        self._files: list[YamlFileInfo] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with action buttons
        header = QHBoxLayout()
        self._check_btn = QPushButton("Check All")
        self._check_btn.setStyleSheet(_SECONDARY_STYLE)
        self._check_btn.clicked.connect(self._on_check_all)
        header.addWidget(self._check_btn)

        self._run_btn = QPushButton("Run All")
        self._run_btn.setStyleSheet(_SECONDARY_STYLE)
        self._run_btn.clicked.connect(self._on_run_all)
        header.addWidget(self._run_btn)
        header.addStretch()
        layout.addLayout(header)

        # Empty state
        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        # File table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(
            ["File Name", "Last Modified", "Last Run"]
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
        project_folder: str | None,
        has_instances: bool,
    ) -> None:
        """Reload YAML files.

        :param conn: Per-client database connection.
        :param instance: Active instance from the picker.
        :param project_folder: Client's project folder.
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

        self._files = load_yaml_files(project_folder)
        if not self._files:
            self._empty_label.setText(_EMPTY_NO_YAML)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._table.setVisible(True)
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._files))
        for row, f in enumerate(self._files):
            self._table.setItem(row, 0, QTableWidgetItem(f.name))
            self._table.setItem(row, 1, QTableWidgetItem(f.last_modified))
            self._table.setItem(
                row, 2, QTableWidgetItem(f.last_run_outcome or "—")
            )

    def _on_check_all(self) -> None:
        """Handle Check All button — placeholder for espo_impl integration."""
        # The existing espo_impl check-then-act flow will be wired here.
        # For now this is a thin wrapper; the underlying RunWorker logic
        # remains in espo_impl and will be connected in a follow-up.
        pass

    def _on_run_all(self) -> None:
        """Handle Run All button — placeholder for espo_impl integration."""
        pass
