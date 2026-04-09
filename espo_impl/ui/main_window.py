"""Main application window."""

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QStackedWidget,
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
from espo_impl.ui.confirm_delete_dialog import (
    ConfirmDeleteDialog,
    DeleteDialogResult,
)
from espo_impl.ui.deploy_panel import DeployPanel
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
    """Main application window for CRM Builder.

    :param base_dir: Base directory for data and reports.
    """

    def __init__(self, base_dir: Path) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.state = UIState()
        self.config_loader = ConfigLoader()
        self.reporter: Reporter | None = None
        self._worker: RunWorker | None = None
        self._build_ui()
        self._update_button_states()

    def _build_ui(self) -> None:
        """Build the main window layout."""
        self.setWindowTitle("CRM Builder")
        self.setMinimumSize(900, 650)

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)

        # Mode selector bar — persistent at the top
        mode_bar = QHBoxLayout()
        mode_bar.setContentsMargins(8, 4, 8, 4)

        self._mode_group = QButtonGroup(self)
        self._deploy_mode_btn = QPushButton("Deployment")
        self._deploy_mode_btn.setCheckable(True)
        self._deploy_mode_btn.setChecked(True)
        self._req_mode_btn = QPushButton("Requirements")
        self._req_mode_btn.setCheckable(True)

        _mode_btn_style = (
            "QPushButton { padding: 6px 16px; font-size: 13px; border: 1px solid #BDBDBD; "
            "border-radius: 4px; background-color: #FAFAFA; } "
            "QPushButton:checked { background-color: #1F3864; color: white; border-color: #1F3864; }"
        )
        self._deploy_mode_btn.setStyleSheet(_mode_btn_style)
        self._req_mode_btn.setStyleSheet(_mode_btn_style)

        self._mode_group.addButton(self._deploy_mode_btn, 0)
        self._mode_group.addButton(self._req_mode_btn, 1)
        self._mode_group.idToggled.connect(self._on_mode_changed)

        mode_bar.addWidget(self._deploy_mode_btn)
        mode_bar.addWidget(self._req_mode_btn)
        mode_bar.addStretch()
        outer_layout.addLayout(mode_bar)

        # Content stack — switches between Deployment and Requirements modes
        self._mode_stack = QStackedWidget()
        outer_layout.addWidget(self._mode_stack, stretch=1)

        # --- Deployment mode container (index 0) ---
        deploy_container = QWidget()
        main_layout = QVBoxLayout(deploy_container)
        main_layout.setContentsMargins(0, 0, 0, 0)

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
        self.tooltip_btn = QPushButton("Import Tooltips")
        self.validate_btn.clicked.connect(self._on_validate_clicked)
        self.run_btn.clicked.connect(self._on_run_clicked)
        self.verify_btn.clicked.connect(self._on_verify_clicked)
        self.tooltip_btn.clicked.connect(self._on_import_tooltips)
        action_layout.addWidget(self.validate_btn)
        action_layout.addWidget(self.run_btn)
        action_layout.addWidget(self.verify_btn)
        action_layout.addWidget(self.tooltip_btn)
        right_layout.addLayout(action_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        top_layout.addLayout(right_layout)
        main_layout.addLayout(top_layout)

        # Deploy panel
        self.deploy_panel = DeployPanel(
            self.base_dir / "data" / "instances"
        )
        main_layout.addWidget(self.deploy_panel, stretch=1)

        # Output panel
        self.output_panel = OutputPanel()
        main_layout.addWidget(self.output_panel, stretch=1)

        # Bottom bar
        bottom_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Output")
        self.clear_btn.clicked.connect(self._on_clear_output)
        bottom_layout.addWidget(self.clear_btn)

        self.docgen_btn = QPushButton("Generate Docs")
        self.docgen_btn.clicked.connect(self._on_generate_docs)
        bottom_layout.addWidget(self.docgen_btn)

        self.open_ref_btn = QPushButton("Open Reference Doc")
        self.open_ref_btn.clicked.connect(self._on_open_reference)
        bottom_layout.addWidget(self.open_ref_btn)

        self.preview_btn = QPushButton("Preview YAML")
        self.preview_btn.clicked.connect(self._on_preview_yaml)
        bottom_layout.addWidget(self.preview_btn)

        self.import_btn = QPushButton("Import Data")
        self.import_btn.clicked.connect(self._on_import_data)
        bottom_layout.addWidget(self.import_btn)

        self.compare_btn = QPushButton("CRM Compare")
        self.compare_btn.clicked.connect(self._on_crm_compare)
        bottom_layout.addWidget(self.compare_btn)

        bottom_layout.addStretch()
        self.report_btn = QPushButton("View Report")
        self.report_btn.clicked.connect(self._on_view_report)
        bottom_layout.addWidget(self.report_btn)
        main_layout.addLayout(bottom_layout)

        self._mode_stack.addWidget(deploy_container)  # index 0

        # --- Requirements mode container (index 1) ---
        from automation.ui.requirements_window import RequirementsWindow
        self._requirements_window = RequirementsWindow(parent=self)
        self._mode_stack.addWidget(self._requirements_window)  # index 1

        # Default to Deployment mode
        self._mode_stack.setCurrentIndex(0)

    def _on_mode_changed(self, button_id: int, checked: bool) -> None:
        """Handle mode selector toggle with instance/client auto-selection."""
        if not checked:
            return

        self._mode_stack.setCurrentIndex(button_id)

        # Pass instance profiles to RequirementsWindow for project_folder resolution
        try:
            self._requirements_window.set_instance_profiles(
                self.instance_panel._profiles
            )
        except Exception:
            pass

        # Section 14.9.3: Auto-select associated client/instance
        try:
            from automation.ui.mode_integration.instance_association import (
                find_client_for_instance,
                find_instance_for_client,
                get_client_crm_platform,
            )

            if button_id == 1:
                # Switching to Requirements mode — auto-select matching client
                if self.state.instance and self.state.instance.project_folder:
                    rw = self._requirements_window
                    clients = []
                    for i in range(1, rw._client_combo.count()):
                        c = rw._client_combo.itemData(i)
                        if c:
                            clients.append(c)
                    idx = find_client_for_instance(
                        self.state.instance.project_folder, clients
                    )
                    if idx is not None:
                        rw._client_combo.setCurrentIndex(idx + 1)  # +1 for placeholder

            elif button_id == 0:
                # Switching to Deployment mode — auto-select matching instance
                rw = self._requirements_window
                client = rw._client_context.client
                if client:
                    crm_platform = get_client_crm_platform(
                        rw._master_db_path, client.id
                    )
                    if crm_platform:
                        profiles = self.instance_panel._profiles
                        idx = find_instance_for_client(crm_platform, profiles)
                        if idx is not None:
                            self.instance_panel.list_widget.setCurrentRow(idx)
        except Exception:
            pass  # Auto-select is best-effort

    def _on_instance_selected(self, profile: InstanceProfile | None) -> None:
        """Handle instance selection change."""
        self.state.instance = profile
        self.state.validated = False
        self.state.run_complete = False

        # Update deploy panel
        self.deploy_panel.set_instance(profile)

        # Update program panel to use this instance's project folder
        if profile and profile.programs_dir:
            self.program_panel.set_programs_dir(profile.programs_dir)
        else:
            self.program_panel.set_programs_dir(
                self.base_dir / "data" / "programs"
            )

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
        if self.state.operation_in_progress:
            self.output_panel.append_line(
                "[VALIDATE] An operation is already in progress", "yellow"
            )
            return
        if not self.state.instance:
            self.output_panel.append_line(
                "[VALIDATE] Select an instance first", "yellow"
            )
            return
        if not self.state.program_path:
            self.output_panel.append_line(
                "[VALIDATE] Select a program file first", "yellow"
            )
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
        total_relationships = len(program.relationships)

        parts = []
        if program.entities:
            parts.append(f"{len(program.entities)} entities, {total_fields} fields")
        if total_relationships:
            parts.append(f"{total_relationships} relationships")
        if not parts:
            parts.append("no entities or relationships")

        self.output_panel.append_line(
            f"[VALIDATE] OK — {', '.join(parts)} found",
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
        if self.state.operation_in_progress:
            self.output_panel.append_line(
                "[RUN] An operation is already in progress", "yellow"
            )
            return
        if not self.state.instance or not self.state.program:
            self.output_panel.append_line(
                "[RUN] Validate a program file first", "yellow"
            )
            return

        skip_deletes = False

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
            dialog.exec()

            if dialog.result == DeleteDialogResult.CANCELLED:
                self.output_panel.append_line(
                    "[RUN] Cancelled by user", "yellow"
                )
                return
            elif dialog.result == DeleteDialogResult.SKIP_DELETES:
                skip_deletes = True

        self._start_worker("run", skip_deletes=skip_deletes)

    def _on_verify_clicked(self) -> None:
        """Start the verify operation in a background thread."""
        if self.state.operation_in_progress:
            self.output_panel.append_line(
                "[VERIFY] An operation is already in progress", "yellow"
            )
            return
        if not self.state.instance or not self.state.program:
            self.output_panel.append_line(
                "[VERIFY] Validate a program file first", "yellow"
            )
            return
        self._start_worker("verify")

    def _on_import_tooltips(self) -> None:
        """Start the tooltip import operation in a background thread."""
        if self.state.operation_in_progress:
            self.output_panel.append_line(
                "[TOOLTIP] An operation is already in progress", "yellow"
            )
            return
        if not self.state.instance:
            self.output_panel.append_line(
                "[TOOLTIP] Select an instance first", "yellow"
            )
            return
        if not self.state.program:
            self.output_panel.append_line(
                "[TOOLTIP] Validate a program file first", "yellow"
            )
            return

        self.state.operation_in_progress = True
        self.progress_bar.setVisible(True)

        # Use instance project folder for reports, fall back to default
        if self.state.instance.reports_dir:
            reports_dir = self.state.instance.reports_dir
        else:
            reports_dir = self.base_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        self.reporter = Reporter(reports_dir)

        self.output_panel.append_line("", "white")
        self.output_panel.append_line(
            "--- IMPORT TOOLTIPS started ---", "white"
        )

        from espo_impl.workers.tooltip_worker import TooltipWorker

        self._worker = TooltipWorker(
            self.state.instance,
            self.state.program,
            parent=self,
        )
        self._worker.output_line.connect(self._on_worker_output)
        self._worker.finished_ok.connect(self._on_worker_finished)
        self._worker.finished_error.connect(self._on_worker_error)
        self._worker.start()

    def _start_worker(
        self, operation: str, skip_deletes: bool = False
    ) -> None:
        """Launch the background worker thread.

        :param operation: "run", "preview", or "verify".
        :param skip_deletes: If True, skip entity delete operations.
        """
        self.state.operation_in_progress = True
        self.progress_bar.setVisible(True)
        self._update_button_states()

        # Use instance project folder for reports, fall back to default
        if self.state.instance and self.state.instance.reports_dir:
            reports_dir = self.state.instance.reports_dir
        else:
            reports_dir = self.base_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        self.reporter = Reporter(reports_dir)

        self.output_panel.append_line("", "white")
        self.output_panel.append_line(
            f"--- {operation.upper()} started ---", "white"
        )

        self._worker = RunWorker(
            self.state.instance,
            self.state.program,
            operation,
            skip_deletes=skip_deletes,
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

    def _on_generate_docs(self) -> None:
        """Generate reference documentation from YAML program files."""
        if self.state.operation_in_progress:
            self.output_panel.append_line(
                "[DOCGEN] An operation is already in progress", "yellow"
            )
            return
        if not self.state.instance:
            self.output_panel.append_line(
                "[DOCGEN] No instance selected.", "red"
            )
            return

        if not self.state.instance.project_folder:
            self.output_panel.append_line(
                "[DOCGEN] No project folder configured for this instance. "
                "Edit the instance to add a project folder.",
                "red",
            )
            return

        import sys

        sys.path.insert(
            0, str(self.base_dir)
        )

        programs_dir = self.state.instance.programs_dir
        output_dir = self.state.instance.docs_dir

        self.output_panel.append_line("", "white")
        self.output_panel.append_line(
            f"[DOCGEN]  Loading program files from {programs_dir} ...",
            "white",
        )

        try:
            from tools.docgen.renderers import docx_renderer, md_renderer
            from tools.generate_docs import build_document

            instance_name = self.state.instance.name
            doc = build_document(programs_dir, f"{instance_name} CRM Implementation Reference")

            self.output_panel.append_line(
                "[DOCGEN]  Building document ...", "white"
            )

            output_dir.mkdir(parents=True, exist_ok=True)

            md_path = output_dir / f"{instance_name}-CRM-Reference.md"
            md_path.write_text(
                md_renderer.render(doc), encoding="utf-8"
            )
            self.output_panel.append_line(
                f"[DOCGEN]  Generated {md_path.name}", "green"
            )

            docx_path = output_dir / f"{instance_name}-CRM-Reference.docx"
            docx_renderer.render(doc, docx_path)
            self.output_panel.append_line(
                f"[DOCGEN]  Generated {docx_path.name}", "green"
            )

            self._docx_path = docx_path

            self.output_panel.append_line(
                f"[DOCGEN]  Done. Files written to {output_dir}/",
                "green",
            )

        except Exception as exc:
            self.output_panel.append_line(
                f"[DOCGEN]  ERROR: {exc}", "red"
            )

    def _on_preview_yaml(self) -> None:
        """Open the YAML preview dialog."""
        if not self.state.instance:
            self.output_panel.append_line(
                "[PREVIEW] Select an instance first", "yellow"
            )
            return

        programs_dir = self.state.instance.programs_dir
        if not programs_dir:
            self.output_panel.append_line(
                "[PREVIEW] No project folder configured for this instance",
                "yellow",
            )
            return

        if not programs_dir.exists() or not any(programs_dir.glob("*.yaml")):
            self.output_panel.append_line(
                f"[PREVIEW] No YAML files found in {programs_dir}",
                "yellow",
            )
            return

        from espo_impl.ui.yaml_preview_dialog import YamlPreviewDialog

        dialog = YamlPreviewDialog(programs_dir, self)
        dialog.exec()

    def _on_crm_compare(self) -> None:
        """Open the CRM platform comparison window."""
        from espo_impl.ui.crm_compare_window import CrmCompareWindow

        if hasattr(self, "_compare_window") and self._compare_window is not None:
            if self._compare_window.isVisible():
                self._compare_window.raise_()
                self._compare_window.activateWindow()
                return
            self._compare_window.deleteLater()
            self._compare_window = None

        self._compare_window = CrmCompareWindow(self.base_dir, self)
        self._compare_window.show()

    def _on_import_data(self) -> None:
        """Open the import wizard dialog."""
        if self.state.operation_in_progress:
            self.output_panel.append_line(
                "[IMPORT] An operation is already in progress", "yellow"
            )
            return
        if not self.state.instance:
            self.output_panel.append_line(
                "[IMPORT] Select an instance first", "yellow"
            )
            return

        from espo_impl.core.api_client import EspoAdminClient
        from espo_impl.ui.import_dialog import ImportDialog

        client = EspoAdminClient(self.state.instance)
        dialog = ImportDialog(self.state.instance, client, self)
        dialog.exec()

    def _on_cert_expiry_updated(self, expiry_date: str) -> None:
        """Handle cert expiry update from deploy worker (runs on main thread).

        Updates the deploy config, saves it, updates the instance profile URL,
        and refreshes the deploy panel cert badge.
        """
        if not self.state.instance:
            return

        from espo_impl.core.deploy_manager import (
            load_deploy_config,
            save_deploy_config,
        )

        instances_dir = self.base_dir / "data" / "instances"
        config = load_deploy_config(instances_dir, self.state.instance.slug)
        if not config:
            return

        config.cert_expiry_date = expiry_date
        save_deploy_config(instances_dir, self.state.instance.slug, config)

        # Update instance profile URL to match the deployed domain
        new_url = f"https://{config.full_domain}"
        if self.state.instance.url != new_url:
            self.state.instance.url = new_url
            self.instance_panel._save_instance(self.state.instance)

        # Refresh dashboard cert badge
        dashboard = self.deploy_panel.get_dashboard()
        if dashboard:
            dashboard.update_cert_badge(expiry_date)

    def _on_deploy_config_saved(self, config) -> None:
        """Handle deploy config saved from wizard. Refresh deploy panel."""
        self.deploy_panel.set_instance(self.state.instance)

    def _on_open_reference(self) -> None:
        """Open the generated reference document."""
        if not hasattr(self, "_docx_path"):
            self.output_panel.append_line(
                "[DOCGEN] No reference doc generated yet "
                "\u2014 click Generate Docs first",
                "yellow",
            )
            return
        if not self._docx_path.exists():
            self.output_panel.append_line(
                f"[DOCGEN] Reference doc not found: {self._docx_path}",
                "yellow",
            )
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._docx_path))
        )

    def _on_view_report(self) -> None:
        """Open the most recent report in the system viewer."""
        if not self.state.last_report_path:
            self.output_panel.append_line(
                "[INFO] No report yet \u2014 run or verify a program first",
                "yellow",
            )
            return
        if not self.state.last_report_path.exists():
            self.output_panel.append_line(
                f"[INFO] Report file not found: {self.state.last_report_path}",
                "yellow",
            )
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.state.last_report_path))
        )

    def closeEvent(self, event) -> None:
        """Clean up resources on window close."""
        if hasattr(self, "_requirements_window"):
            self._requirements_window.cleanup()
        super().closeEvent(event)

    def _update_button_states(self) -> None:
        """Refresh any dynamic button labels. Buttons are never disabled."""
