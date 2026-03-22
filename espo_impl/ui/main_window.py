"""Main application window."""

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import (
    EntityAction,
    InstanceProfile,
    ProgramFile,
    RunReport,
)
from espo_impl.core.reporter import Reporter
from espo_impl.ui.confirm_delete_dialog import ConfirmDeleteDialog
from espo_impl.ui.instance_panel import InstancePanel
from espo_impl.ui.output_panel import OutputPanel
from espo_impl.ui.program_panel import ProgramPanel
from espo_impl.workers.run_worker import RunWorker

logger = logging.getLogger(__name__)


@dataclass
class UIState:
    """Tracks the current state of the UI for button enable/disable logic."""

    instance: InstanceProfile | None = None
    program_path: Path | None = None
    program: ProgramFile | None = None
    validated: bool = False
    run_complete: bool = False
    operation_in_progress: bool = False
    last_report_path: Path | None = None


class MainWindow(QMainWindow):
    """Main application window for the EspoCRM Implementation Tool.

    :param base_dir: Base directory for data and reports.
    """

    def __init__(self, base_dir: Path) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.state = UIState()
        self.config_loader = ConfigLoader()
        self.reporter = Reporter(base_dir / "reports")
        self._worker: RunWorker | None = None
        self._build_ui()
        self._update_button_states()

    def _build_ui(self) -> None:
        """Build the main window layout."""
        self.setWindowTitle("EspoCRM Implementation Tool")
        self.setMinimumSize(900, 650)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Top section: instance panel + program panel + action buttons
        top_layout = QHBoxLayout()

        # Left: Instance panel
        self.instance_panel = InstancePanel(
            self.base_dir / "data" / "instances"
        )
        self.instance_panel.instance_selected.connect(self._on_instance_selected)
        self.instance_panel.setMaximumWidth(350)
        top_layout.addWidget(self.instance_panel)

        # Right: Program panel + action buttons
        right_layout = QVBoxLayout()

        self.program_panel = ProgramPanel(
            self.base_dir / "data" / "programs"
        )
        self.program_panel.program_selected.connect(self._on_program_selected)
        right_layout.addWidget(self.program_panel)

        # Action buttons
        action_layout = QHBoxLayout()
        self.validate_btn = QPushButton("Validate")
        self.run_btn = QPushButton("Run")
        self.verify_btn = QPushButton("Verify")
        self.validate_btn.clicked.connect(self._on_validate_clicked)
        self.run_btn.clicked.connect(self._on_run_clicked)
        self.verify_btn.clicked.connect(self._on_verify_clicked)
        action_layout.addWidget(self.validate_btn)
        action_layout.addWidget(self.run_btn)
        action_layout.addWidget(self.verify_btn)
        right_layout.addLayout(action_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        top_layout.addLayout(right_layout)
        main_layout.addLayout(top_layout)

        # Output panel
        self.output_panel = OutputPanel()
        main_layout.addWidget(self.output_panel, stretch=1)

        # Bottom bar: Clear Output + View Report
        bottom_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Output")
        self.clear_btn.clicked.connect(self._on_clear_output)
        bottom_layout.addWidget(self.clear_btn)
        bottom_layout.addStretch()
        self.report_btn = QPushButton("View Report")
        self.report_btn.clicked.connect(self._on_view_report)
        bottom_layout.addWidget(self.report_btn)
        main_layout.addLayout(bottom_layout)

    def _on_instance_selected(self, profile: InstanceProfile | None) -> None:
        """Handle instance selection change."""
        self.state.instance = profile
        self.state.validated = False
        self.state.run_complete = False
        self._update_button_states()

    def _on_program_selected(self, path: Path | None) -> None:
        """Handle program file selection change."""
        self.state.program_path = path
        self.state.program = None
        self.state.validated = False
        self.state.run_complete = False
        self._update_button_states()

    def _on_validate_clicked(self) -> None:
        """Parse and validate the YAML, then preview planned changes."""
        if not self.state.program_path or not self.state.instance:
            return

        self.output_panel.append_line(
            f"[VALIDATE] Parsing {self.state.program_path.name} ...", "white"
        )

        try:
            program = self.config_loader.load_program(self.state.program_path)
        except ValueError as exc:
            self.output_panel.append_line(
                f"[VALIDATE] FAILED — {exc}", "red"
            )
            self.state.validated = False
            self._update_button_states()
            return

        errors = self.config_loader.validate_program(program)
        if errors:
            for err in errors:
                self.output_panel.append_line(f"[VALIDATE] ERROR: {err}", "red")
            self.output_panel.append_line("[VALIDATE] FAILED", "red")
            self.state.validated = False
            self._update_button_states()
            return

        total_fields = sum(len(e.fields) for e in program.entities)
        self.output_panel.append_line(
            f"[VALIDATE] OK — {len(program.entities)} entities, "
            f"{total_fields} fields found",
            "green",
        )
        self.state.program = program

        # Launch preview to show planned changes
        self.output_panel.append_line(
            "[VALIDATE] Checking instance for planned changes ...", "white"
        )
        self._start_worker("preview")

    def _on_run_clicked(self) -> None:
        """Start the run operation, with confirmation if deletes are present."""
        if not self.state.instance or not self.state.program:
            return

        # Check for destructive operations
        if self.state.program.has_delete_operations:
            delete_actions = {
                EntityAction.DELETE, EntityAction.DELETE_AND_CREATE
            }
            delete_entities = [
                e for e in self.state.program.entities
                if e.action in delete_actions
            ]
            program_name = (
                self.state.program.source_path.name
                if self.state.program.source_path
                else "unknown"
            )
            dialog = ConfirmDeleteDialog(
                delete_entities, program_name, self
            )
            if dialog.exec() != ConfirmDeleteDialog.DialogCode.Accepted:
                self.output_panel.append_line(
                    "[RUN] Cancelled by user", "yellow"
                )
                return

        self._start_worker("run")

    def _on_verify_clicked(self) -> None:
        """Start the verify operation in a background thread."""
        if not self.state.instance or not self.state.program:
            return
        self._start_worker("verify")

    def _start_worker(self, operation: str) -> None:
        """Launch the background worker thread.

        :param operation: "run" or "verify".
        """
        self.state.operation_in_progress = True
        self.progress_bar.setVisible(True)
        self._update_button_states()

        self.output_panel.append_line("", "white")
        self.output_panel.append_line(
            f"--- {operation.upper()} started ---", "white"
        )

        self._worker = RunWorker(
            self.state.instance,
            self.state.program,
            operation,
            parent=self,
        )
        self._worker.output_line.connect(self._on_worker_output)
        self._worker.finished_ok.connect(self._on_worker_finished)
        self._worker.finished_error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_output(self, message: str, color: str) -> None:
        """Forward worker output to the output panel."""
        self.output_panel.append_line(message, color)

    def _on_worker_finished(self, report: RunReport) -> None:
        """Handle successful worker completion."""
        self.state.operation_in_progress = False
        self.progress_bar.setVisible(False)

        if report.operation == "preview":
            self.state.validated = True
            self._update_button_states()
            self._worker = None
            return

        if report.operation == "run":
            self.state.run_complete = True

        # Write reports
        try:
            log_path, json_path = self.reporter.write_report(report)
            self.state.last_report_path = log_path
            self.output_panel.append_line(
                "Reports written to:", "white"
            )
            self.output_panel.append_line(f"  {log_path}", "white")
            self.output_panel.append_line(f"  {json_path}", "white")
        except Exception as exc:
            self.output_panel.append_line(
                f"[ERROR] Failed to write reports: {exc}", "red"
            )

        self._update_button_states()
        self._worker = None

    def _on_worker_error(self, error_msg: str) -> None:
        """Handle worker failure."""
        self.state.operation_in_progress = False
        self.progress_bar.setVisible(False)
        self.output_panel.append_line(
            f"[ERROR] Operation failed: {error_msg}", "red"
        )
        self._update_button_states()
        self._worker = None

    def _on_clear_output(self) -> None:
        """Clear the output panel."""
        self.output_panel.clear()

    def _on_view_report(self) -> None:
        """Open the most recent report in the system viewer."""
        if self.state.last_report_path and self.state.last_report_path.exists():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.state.last_report_path))
            )

    def _update_button_states(self) -> None:
        """Enable/disable buttons based on current state."""
        in_progress = self.state.operation_in_progress
        has_selection = (
            self.state.instance is not None
            and self.state.program_path is not None
        )

        self.validate_btn.setEnabled(has_selection and not in_progress)
        self.run_btn.setEnabled(self.state.validated and not in_progress)
        self.verify_btn.setEnabled(self.state.run_complete and not in_progress)
        self.report_btn.setEnabled(self.state.last_report_path is not None)
