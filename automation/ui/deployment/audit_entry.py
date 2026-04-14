"""Audit sidebar entry — reverse-engineer a source CRM into YAML files.

Reads the current configuration of a source CRM instance and produces
YAML program files + database records as a starting point for CRM
Builder management.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    load_instance_detail,
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

_EMPTY_NO_FOLDER = (
    "No project folder is configured for this client.\n\n"
    "Set a project folder in the Clients tab so the system knows\n"
    "where to write audit output."
)

_EMPTY_NO_INSTANCE = (
    "Select an instance from the picker above to audit.\n\n"
    "The audit reads the current configuration of a live CRM\n"
    "and produces YAML program files as a starting point."
)


class AuditEntry(QWidget):
    """Audit sidebar entry for reverse-engineering a CRM instance.

    :param parent: Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._project_folder: str | None = None
        self._output_entry = None
        self._worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with action button
        header = QHBoxLayout()

        self._start_btn = QPushButton("Start Audit")
        self._start_btn.setStyleSheet(_PRIMARY_STYLE)
        self._start_btn.clicked.connect(self._on_start_audit)
        header.addWidget(self._start_btn)

        self._open_folder_btn = QPushButton("Open Output Folder")
        self._open_folder_btn.setStyleSheet(_SECONDARY_STYLE)
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        header.addWidget(self._open_folder_btn)

        header.addStretch()
        layout.addLayout(header)

        # Empty state label
        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        # Content area (hidden until ready)
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 8, 0, 0)

        # Instance info
        info_group = QGroupBox("Source Instance")
        info_layout = QVBoxLayout(info_group)
        self._instance_label = QLabel()
        self._instance_label.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(self._instance_label)
        content_layout.addWidget(info_group)

        # Scope options
        scope_group = QGroupBox("Audit Scope")
        scope_layout = QVBoxLayout(scope_group)

        self._cb_custom_fields = QCheckBox("Custom entity fields")
        self._cb_custom_fields.setChecked(True)
        scope_layout.addWidget(self._cb_custom_fields)

        self._cb_native_fields = QCheckBox("Native entity custom fields")
        self._cb_native_fields.setChecked(True)
        scope_layout.addWidget(self._cb_native_fields)

        self._cb_detail_layouts = QCheckBox("Detail layouts")
        self._cb_detail_layouts.setChecked(True)
        scope_layout.addWidget(self._cb_detail_layouts)

        self._cb_list_layouts = QCheckBox("List layouts")
        self._cb_list_layouts.setChecked(True)
        scope_layout.addWidget(self._cb_list_layouts)

        self._cb_relationships = QCheckBox("Relationships")
        self._cb_relationships.setChecked(True)
        scope_layout.addWidget(self._cb_relationships)

        self._cb_include_native = QCheckBox(
            "Include native fields (normally excluded)"
        )
        self._cb_include_native.setChecked(False)
        scope_layout.addWidget(self._cb_include_native)

        content_layout.addWidget(scope_group)

        # Last audit info
        self._last_audit_label = QLabel()
        self._last_audit_label.setStyleSheet(
            "font-size: 12px; color: #757575; padding: 4px;"
        )
        content_layout.addWidget(self._last_audit_label)

        content_layout.addStretch()
        layout.addWidget(self._content, stretch=1)

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
        """Reload the entry with current context.

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
            self._content.setVisible(False)
            return

        if not instance:
            self._empty_label.setText(_EMPTY_NO_INSTANCE)
            self._empty_label.setVisible(True)
            self._content.setVisible(False)
            return

        if not project_folder:
            self._empty_label.setText(_EMPTY_NO_FOLDER)
            self._empty_label.setVisible(True)
            self._content.setVisible(False)
            return

        # Show content
        self._empty_label.setVisible(False)
        self._content.setVisible(True)

        # Update instance info
        self._instance_label.setText(
            f"{instance.name}  ({instance.code})\n"
            f"URL: {instance.url or 'Not configured'}\n"
            f"Environment: {instance.environment}"
        )

        # Update last audit info
        self._update_last_audit_info()

    def _update_last_audit_info(self) -> None:
        """Query and display the most recent audit for this instance."""
        if not self._conn or not self._instance:
            self._last_audit_label.setText("")
            return

        try:
            row = self._conn.execute(
                "SELECT file_name, outcome, completed_at "
                "FROM ConfigurationRun "
                "WHERE instance_id = ? AND operation = 'audit' "
                "ORDER BY completed_at DESC LIMIT 1",
                (self._instance.id,),
            ).fetchone()
        except sqlite3.OperationalError:
            # Table may not exist yet (pre-v5/v7 migration)
            self._last_audit_label.setText("")
            return

        if row:
            name, outcome, completed = row
            ts = completed[:16].replace("T", " ") if completed else "—"
            status = "Success" if outcome == "success" else "Error"
            self._last_audit_label.setText(
                f"Last audit: {status} — {ts}\nOutput: {name}"
            )
        else:
            self._last_audit_label.setText("No previous audits for this instance.")

    # ── Actions ─────────────────────────────────────────────────────

    def _on_start_audit(self) -> None:
        """Start the audit process."""
        if not self._instance:
            QMessageBox.information(
                self, "No Instance",
                "Select an instance from the picker above first.",
            )
            return

        if not self._conn:
            QMessageBox.warning(self, "Error", "No database connection.")
            return

        if not self._project_folder:
            QMessageBox.information(
                self, "No Project Folder",
                "Configure a project folder in the Clients tab first.",
            )
            return

        detail = load_instance_detail(self._conn, self._instance.id)
        if detail is None:
            QMessageBox.warning(
                self, "Error", "Could not load instance details."
            )
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

        # Build output directory with timestamp
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_dir = Path(self._project_folder) / "programs" / f"audit-{timestamp}"

        # Build audit options from checkboxes
        from espo_impl.core.audit_manager import AuditOptions

        options = AuditOptions(
            include_custom_fields=self._cb_custom_fields.isChecked(),
            include_native_custom_fields=self._cb_native_fields.isChecked(),
            include_detail_layouts=self._cb_detail_layouts.isChecked(),
            include_list_layouts=self._cb_list_layouts.isChecked(),
            include_relationships=self._cb_relationships.isChecked(),
            include_native_fields=self._cb_include_native.isChecked(),
        )

        # Build InstanceProfile from database detail
        from espo_impl.core.models import InstanceProfile

        profile = InstanceProfile(
            name=detail.name,
            url=detail.url,
            api_key=detail.username,
            auth_method="basic",
            secret_key=detail.password,
        )

        # Get client DB path for record insertion
        db_path = None
        if self._conn:
            try:
                # Get the file path from the connection
                db_info = self._conn.execute("PRAGMA database_list").fetchall()
                for _, _, path in db_info:
                    if path:
                        db_path = path
                        break
            except sqlite3.Error:
                pass

        # Launch progress dialog
        dialog = AuditProgressDialog(
            profile=profile,
            output_dir=output_dir,
            options=options,
            db_path=db_path,
            instance_id=self._instance.id,
            output_entry=self._output_entry,
            parent=self,
        )
        dialog.exec()

        # Refresh to show updated last audit info
        self._update_last_audit_info()

    def _on_open_folder(self) -> None:
        """Open the most recent audit output folder."""
        if not self._project_folder:
            QMessageBox.information(
                self, "No Project Folder",
                "No project folder is configured.",
            )
            return

        programs_dir = Path(self._project_folder) / "programs"
        # Find the most recent audit-* folder
        audit_dirs = sorted(
            programs_dir.glob("audit-*"),
            key=lambda p: p.name,
            reverse=True,
        )
        if not audit_dirs:
            QMessageBox.information(
                self, "No Audit Output",
                "No audit output folders found.\n"
                "Run an audit first.",
            )
            return

        import subprocess
        subprocess.Popen(["xdg-open", str(audit_dirs[0])])


# ── Progress Dialog ─────────────────────────────────────────────


class AuditProgressDialog(QDialog):
    """Modal progress dialog for audit execution.

    :param profile: Source instance profile.
    :param output_dir: Output directory for YAML files.
    :param options: Audit options.
    :param db_path: Client DB path for record insertion.
    :param instance_id: Instance table row ID.
    :param output_entry: Optional OutputEntry for mirrored logging.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        profile,
        output_dir: Path,
        options=None,
        db_path: str | None = None,
        instance_id: int | None = None,
        output_entry=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._output_dir = output_dir
        self._options = options
        self._db_path = db_path
        self._instance_id = instance_id
        self._output_entry = output_entry
        self._worker = None

        self.setWindowTitle("CRM Audit")
        self.setMinimumSize(700, 500)
        self.setModal(True)

        self._build_ui()
        self._start_worker()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # Indeterminate initially
        layout.addWidget(self._progress_bar)

        # Log output
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "QTextEdit { background-color: #1E1E1E; color: #D4D4D4; "
            "font-family: monospace; font-size: 11px; }"
        )
        layout.addWidget(self._log, stretch=1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setVisible(False)
        btn_layout.addWidget(self._close_btn)

        layout.addLayout(btn_layout)

    def _start_worker(self) -> None:
        """Launch the audit worker thread."""
        from espo_impl.workers.audit_worker import AuditWorker

        self._worker = AuditWorker(
            profile=self._profile,
            output_dir=self._output_dir,
            options=self._options,
            db_path=self._db_path,
            instance_id=self._instance_id,
            parent=self,
        )
        self._worker.output_line.connect(self._on_output_line)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)
        self._worker.start()

    def _on_output_line(self, text: str, color: str) -> None:
        """Append a line to the log display."""
        color_map = {
            "red": "#F44336",
            "green": "#4CAF50",
            "yellow": "#FFC107",
            "cyan": "#00BCD4",
            "white": "#D4D4D4",
            "gray": "#9E9E9E",
        }
        hex_color = color_map.get(color, "#D4D4D4")
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log.append(
            f'<span style="color: {hex_color};">{escaped}</span>'
        )

        # Mirror to output entry
        if self._output_entry:
            level_map = {
                "red": "error",
                "yellow": "warning",
                "green": "success",
            }
            level = level_map.get(color, "info")
            self._output_entry.append_line(text, level)

    def _on_finished_ok(self, report) -> None:
        """Handle successful audit completion."""
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)

    def _on_finished_error(self, error: str) -> None:
        """Handle audit failure."""
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._on_output_line(f"\nAUDIT FAILED: {error}", "red")
        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)

    def _on_cancel(self) -> None:
        """Cancel the running audit."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
            self._on_output_line("Audit cancelled by user.", "yellow")
        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)

    def reject(self) -> None:
        """Handle Escape key — same as cancel."""
        if self._worker and self._worker.isRunning():
            self._on_cancel()
        else:
            super().reject()
