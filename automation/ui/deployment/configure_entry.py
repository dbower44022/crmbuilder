"""Configure sidebar entry — YAML file list + actions (Section 14.12.7).

Thin wrapper over existing ``espo_impl`` check-then-act configuration,
scoped to the active client's ``{project_folder}/programs/`` and the
active instance from the picker.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    YamlFileInfo,
    load_instance_detail,
    load_last_runs,
    load_yaml_files,
)

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
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
    "No YAML program files found.\n\n"
    "Expected location:\n{path}\n\n"
    "Generate YAML files from the Requirements tab (Phase 9 — YAML Generation)\n"
    "to populate this list."
)

_EMPTY_NO_FOLDER = (
    "No project folder is configured for this client.\n\n"
    "Set a project folder in the Clients tab so the system knows\n"
    "where to find YAML program files."
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
        self._output_entry = None  # set via set_output_entry()
        # Persists across refresh() calls: file path → "Success — timestamp"
        self._run_results_cache: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with action buttons
        header = QHBoxLayout()

        self._run_selected_btn = QPushButton("Run Selected")
        self._run_selected_btn.setStyleSheet(_PRIMARY_STYLE)
        self._run_selected_btn.clicked.connect(self._on_run_selected)
        header.addWidget(self._run_selected_btn)

        self._verify_selected_btn = QPushButton("Verify Selected")
        self._verify_selected_btn.setStyleSheet(_PRIMARY_STYLE)
        self._verify_selected_btn.clicked.connect(self._on_verify_selected)
        header.addWidget(self._verify_selected_btn)

        self._view_yaml_btn = QPushButton("View YAML")
        self._view_yaml_btn.setStyleSheet(_SECONDARY_STYLE)
        self._view_yaml_btn.clicked.connect(self._on_view_yaml)
        header.addWidget(self._view_yaml_btn)

        header.addStretch()

        self._verify_all_btn = QPushButton("Verify All")
        self._verify_all_btn.setStyleSheet(_SECONDARY_STYLE)
        self._verify_all_btn.clicked.connect(self._on_verify_all)
        header.addWidget(self._verify_all_btn)

        self._run_all_btn = QPushButton("Run All")
        self._run_all_btn.setStyleSheet(_SECONDARY_STYLE)
        self._run_all_btn.clicked.connect(self._on_run_all)
        header.addWidget(self._run_all_btn)

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
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["File Name", "Version", "Last Modified", "Last Run"]
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table, stretch=1)

    # ── Public API ─────────────────────────────────────────────────

    def set_output_entry(self, output_entry) -> None:
        """Set the OutputEntry widget for streaming log output.

        :param output_entry: The OutputEntry instance.
        """
        self._output_entry = output_entry

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

        if not project_folder:
            self._empty_label.setText(_EMPTY_NO_FOLDER)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        programs_path = Path(project_folder) / "programs"

        self._files = load_yaml_files(project_folder)
        if not self._files:
            self._empty_label.setText(
                _EMPTY_NO_YAML.format(path=programs_path)
            )
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        # Hydrate last_run_outcome from the database
        if conn and instance:
            last_runs = load_last_runs(conn, instance.id)
            for f in self._files:
                rec = last_runs.get(f.name)
                if rec and rec.completed_at:
                    label = "Success" if rec.outcome == "success" else "Error"
                    # Show version if available
                    ver = f" (v{rec.file_version})" if rec.file_version else ""
                    ts = rec.completed_at[:16].replace("T", " ")
                    f.last_run_outcome = f"{label}{ver} — {ts}"

        # Apply any in-session cache on top (for runs just completed)
        for f in self._files:
            cached = self._run_results_cache.get(f.path)
            if cached:
                f.last_run_outcome = cached

        self._empty_label.setVisible(False)
        self._table.setVisible(True)
        self._populate_table()

    # ── Table ──────────────────────────────────────────────────────

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._files))
        for row, f in enumerate(self._files):
            self._table.setItem(row, 0, QTableWidgetItem(f.name))
            self._table.setItem(row, 1, QTableWidgetItem(f.version or "—"))
            self._table.setItem(row, 2, QTableWidgetItem(f.last_modified))

            outcome_text = f.last_run_outcome or "—"
            outcome_item = QTableWidgetItem(outcome_text)
            if outcome_text.startswith("Success"):
                outcome_item.setForeground(QColor("#4CAF50"))
            elif outcome_text.startswith("Error"):
                outcome_item.setForeground(QColor("#F44336"))
            self._table.setItem(row, 3, outcome_item)

    def _selected_files(self) -> list[YamlFileInfo]:
        """Return the YamlFileInfo objects for the currently selected rows."""
        selected_rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        return [
            self._files[row]
            for row in selected_rows
            if 0 <= row < len(self._files)
        ]

    # ── Run / Check logic ──────────────────────────────────────────

    def _launch_operation(
        self, files: list[YamlFileInfo], operation: str
    ) -> None:
        """Open the progress dialog and run the operation.

        :param files: YAML files to process.
        :param operation: "run" or "verify" (check).
        """
        if not self._instance or not self._conn:
            QMessageBox.information(
                self, "No Instance",
                "Select an active instance from the picker first.",
            )
            return

        detail = load_instance_detail(self._conn, self._instance.id)
        if detail is None:
            QMessageBox.warning(self, "Error", "Could not load instance details.")
            return
        if not detail.url:
            QMessageBox.information(
                self, "No URL",
                "The active instance has no URL configured.\n"
                "Edit the instance in the Instances entry first.",
            )
            return
        if not detail.username or not detail.password:
            QMessageBox.information(
                self, "Missing Credentials",
                "The active instance needs a username and password.\n"
                "Edit the instance in the Instances entry first.",
            )
            return

        from automation.ui.deployment.configure_progress import (
            ConfigureProgressDialog,
        )

        dialog = ConfigureProgressDialog(
            files=files,
            operation=operation,
            instance=self._instance,
            conn=self._conn,
            output_entry=self._output_entry,
            parent=self,
        )
        dialog.exec()

        # Update the table with per-file results from the dialog
        self._apply_run_results(dialog.file_results)

    def _apply_run_results(
        self, results: dict[str, tuple[str, str]]
    ) -> None:
        """Update the Last Run column, cache, and YamlFileInfo for completed files.

        :param results: Maps file path → (outcome, timestamp).
        """
        for file_path, (outcome, timestamp) in results.items():
            label = "Success" if outcome == "success" else "Error"
            display = f"{label} — {timestamp}"
            self._run_results_cache[file_path] = display

        # Update the visible table cells
        for row, f in enumerate(self._files):
            cached = self._run_results_cache.get(f.path)
            if cached:
                f.last_run_outcome = cached
                item = QTableWidgetItem(cached)
                if cached.startswith("Success"):
                    item.setForeground(QColor("#4CAF50"))
                else:
                    item.setForeground(QColor("#F44336"))
                self._table.setItem(row, 3, item)

    # ── Button handlers ────────────────────────────────────────────

    def _on_run_selected(self) -> None:
        """Run configuration for selected YAML files only."""
        files = self._selected_files()
        if not files:
            QMessageBox.information(
                self, "No Selection",
                "Select one or more YAML files in the table first.",
            )
            return
        self._launch_operation(files, "run")

    def _on_verify_selected(self) -> None:
        """Verify configuration for selected YAML files only."""
        files = self._selected_files()
        if not files:
            QMessageBox.information(
                self, "No Selection",
                "Select one or more YAML files in the table first.",
            )
            return
        self._launch_operation(files, "verify")

    def _on_view_yaml(self) -> None:
        """Open a read-only viewer for the selected YAML file."""
        files = self._selected_files()
        if not files:
            QMessageBox.information(
                self, "No Selection",
                "Select a YAML file in the table first.",
            )
            return
        if len(files) > 1:
            QMessageBox.information(
                self, "Multiple Selected",
                "Select a single YAML file to view.",
            )
            return

        file_info = files[0]
        try:
            content = Path(file_info.path).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(
                self, "Read Error", f"Could not read file:\n{exc}"
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"YAML — {file_info.name}")
        dialog.setMinimumSize(700, 500)

        layout = QVBoxLayout(dialog)

        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(content)
        viewer.setFont(QFont("Monospace", 10))
        viewer.setStyleSheet(
            "QPlainTextEdit { background-color: #1E1E1E; color: #D4D4D4; }"
        )
        layout.addWidget(viewer)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _on_verify_all(self) -> None:
        """Verify configuration for all YAML files."""
        if not self._files:
            return
        self._launch_operation(list(self._files), "verify")

    def _on_run_all(self) -> None:
        """Run configuration for all YAML files."""
        if not self._files:
            return
        self._launch_operation(list(self._files), "run")
