"""Recovery Tools dialog — admin credential reset and full database reset."""

import json
import logging
import secrets
from datetime import datetime
from pathlib import Path

import paramiko
import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.deploy_manager import (
    connect_ssh,
    mask_credentials,
    run_remote,
    save_deploy_config,
)
from espo_impl.core.models import DeployConfig, InstanceProfile

logger = logging.getLogger(__name__)

LOG_COLORS: dict[str, str] = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
    "success": "#4CAF50",
}

# Verified against deployed EspoCRM instance:
# - Database engine is MariaDB; CLI command is 'mariadb', not 'mysql'
# - User table is 'user' (singular)
# - Admin users have type='admin' (no is_admin column)
# - Docker compose file is at /var/www/espocrm/docker-compose.yml
DOCKER_COMPOSE = "/var/www/espocrm/docker-compose.yml"
DB_CLI = "mariadb"
USER_TABLE = "user"


# ── Recovery log file writer ──────────────────────────────────────────


class RecoveryLog:
    """Writes a structured recovery log file alongside the UI log.

    :param log_dir: Directory for recovery log files.
    :param instance_name: Human-readable instance name.
    :param operation: Operation name for the log header.
    :param config: Deploy config for header metadata.
    """

    def __init__(
        self,
        log_dir: Path,
        instance_name: str,
        operation: str,
        config: DeployConfig,
    ) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self._path = log_dir / f"recovery-{ts}.log"
        self._config = config

        header = (
            "CRM Builder — Recovery Log\n"
            "===========================\n"
            f"Timestamp:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Instance:    {instance_name}\n"
            f"Operation:   {operation}\n"
            f"Server IP:   {config.droplet_ip}\n"
            f"Domain:      {config.full_domain}\n"
            "\n--- Operation Steps ---\n"
        )
        self._path.write_text(header, encoding="utf-8")

    @property
    def path(self) -> Path:
        """Return the log file path."""
        return self._path

    def step(self, status: str, description: str, **kwargs: str) -> None:
        """Append a step entry to the log file.

        :param status: STARTED, OK, or FAILED.
        :param description: Step description.
        :param kwargs: Optional 'error' and 'command' for failures.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {status:<8} {description}\n"
        error = kwargs.get("error")
        command = kwargs.get("command")
        if error:
            safe_error = mask_credentials(error, self._config)
            line += f"            Error:   {safe_error}\n"
        if command:
            safe_cmd = mask_credentials(command, self._config)
            line += f"            Command: {safe_cmd}\n"
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)

    def result(self, text: str) -> None:
        """Append a result block to the log file.

        :param text: Result text.
        """
        safe = mask_credentials(text, self._config)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(f"\n--- Result ---\n{safe}\n")


# ── Credential reset worker ──────────────────────────────────────────


class CredentialResetWorker(QThread):
    """Background worker for resetting admin credentials via SSH.

    :param config: Deploy config with SSH and DB credentials.
    :param new_username: New admin username.
    :param new_password: New admin password.
    :param recovery_log: RecoveryLog instance for file logging.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    finished_ok = Signal(str, str)
    finished_error = Signal(str)

    def __init__(
        self,
        config: DeployConfig,
        new_username: str,
        new_password: str,
        recovery_log: RecoveryLog,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.new_username = new_username
        self.new_password = new_password
        self._rlog = recovery_log

    def _log(self, msg: str, level: str = "info") -> None:
        self.log_line.emit(msg, level)

    def run(self) -> None:
        """Execute the credential reset."""
        # Step 1: SSH connect
        self._rlog.step("STARTED", "Connect via SSH")
        self._log("Connecting via SSH...")
        try:
            ssh = connect_ssh(
                self.config.droplet_ip,
                self.config.ssh_user,
                self.config.ssh_key_path,
            )
        except Exception as exc:
            self._rlog.step("FAILED", "Connect via SSH", error=str(exc))
            self._rlog.result("FAILED")
            self._log(f"SSH connection failed: {exc}", "error")
            self.finished_error.emit(str(exc))
            return
        self._rlog.step("OK", "Connect via SSH")

        try:
            self._reset_credentials(ssh)
        finally:
            ssh.close()

    def _reset_credentials(self, ssh: paramiko.SSHClient) -> None:
        """Run the SQL credential reset."""
        # Step 2: Execute UPDATE
        sql = (
            f"UPDATE {USER_TABLE} "
            f"SET user_name = '{self.new_username}', "
            f"password = MD5('{self.new_password}') "
            f"WHERE type = 'admin' AND deleted = 0 LIMIT 1;"
        )
        cmd = (
            f"docker compose -f {DOCKER_COMPOSE} exec -T espocrm-db "
            f"{DB_CLI} -u root -p'{self.config.db_root_password}' "
            f"espocrm -e \"{sql}\""
        )
        safe_cmd = mask_credentials(cmd, self.config)
        # Also mask the new password in logs
        safe_cmd = safe_cmd.replace(self.new_password, "[new_password]")

        self._rlog.step("STARTED", "Reset admin credentials in database")
        self._log(f"$ {safe_cmd}")

        exit_code, output = run_remote(ssh, cmd)
        if exit_code != 0:
            safe_output = mask_credentials(output, self.config)
            self._rlog.step(
                "FAILED", "Reset admin credentials in database",
                error=safe_output, command=safe_cmd,
            )
            self._rlog.result("FAILED")
            self._log(f"Credential reset failed: {safe_output}", "error")
            self.finished_error.emit(safe_output)
            return

        self._rlog.step("OK", "Reset admin credentials in database")
        self._rlog.result(
            f"COMPLETED\n\n"
            f"New admin username: {self.new_username}\n"
            f"Note: Password not logged for security."
        )
        self._log("Admin credentials reset successfully.", "success")
        self.finished_ok.emit(self.new_username, self.new_password)


# ── Full reset worker ─────────────────────────────────────────────────


class FullResetWorker(QThread):
    """Background worker for full database reset (teardown + reinstall).

    Tears down Docker containers/volumes, removes the install directory,
    then delegates to DeployWorker for Phases 2-4. After Phase 4, it
    automatically provisions an API user on the fresh instance.

    :param config: Deploy config.
    :param profile: Instance profile.
    :param instances_dir: Path to instances directory.
    :param recovery_log: RecoveryLog instance.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    phase_started = Signal(int)
    phase_completed = Signal(int)
    phase_failed = Signal(int, str)
    finished_ok = Signal()
    finished_error = Signal(str)
    profile_updated = Signal(object)

    def __init__(
        self,
        config: DeployConfig,
        profile: InstanceProfile,
        instances_dir: Path,
        recovery_log: RecoveryLog,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.profile = profile
        self.instances_dir = instances_dir
        self._rlog = recovery_log

    def _log(self, msg: str, level: str = "info") -> None:
        self.log_line.emit(msg, level)

    def run(self) -> None:
        """Execute the full reset sequence."""
        # Step 1: SSH connect
        self._rlog.step("STARTED", "Connect via SSH")
        self._log("Connecting via SSH...")
        try:
            ssh = connect_ssh(
                self.config.droplet_ip,
                self.config.ssh_user,
                self.config.ssh_key_path,
            )
        except Exception as exc:
            self._rlog.step("FAILED", "Connect via SSH", error=str(exc))
            self._rlog.result("FAILED")
            self._log(f"SSH connection failed: {exc}", "error")
            self.finished_error.emit(str(exc))
            return
        self._rlog.step("OK", "Connect via SSH")

        try:
            self._run_reset(ssh)
        finally:
            ssh.close()

    def _run_reset(self, ssh: paramiko.SSHClient) -> None:
        """Teardown containers, reinstall, and provision API user."""
        # Step 2: Stop and remove Docker containers and volumes
        teardown_cmd = (
            f"docker compose -f {DOCKER_COMPOSE} down --volumes"
        )
        self._rlog.step("STARTED", "Stop and remove Docker containers/volumes")
        self._log(f"$ {teardown_cmd}")
        exit_code, output = run_remote(ssh, teardown_cmd, self._log)
        if exit_code != 0:
            self._rlog.step(
                "FAILED", "Stop and remove Docker containers/volumes",
                error=output, command=teardown_cmd,
            )
            self._rlog.result("FAILED")
            self._log("Teardown failed.", "error")
            self.finished_error.emit(output)
            return
        self._rlog.step("OK", "Stop and remove Docker containers/volumes")

        # Step 3: Remove installation directory
        rm_cmd = "rm -rf /var/www/espocrm"
        self._rlog.step("STARTED", "Remove installation directory")
        self._log(f"$ {rm_cmd}")
        exit_code, output = run_remote(ssh, rm_cmd, self._log)
        if exit_code != 0:
            self._rlog.step(
                "FAILED", "Remove installation directory",
                error=output, command=rm_cmd,
            )
            self._rlog.result("FAILED")
            self._log("Failed to remove installation directory.", "error")
            self.finished_error.emit(output)
            return
        self._rlog.step("OK", "Remove installation directory")

        # Step 4: Re-run Phase 2 (EspoCRM Installation)
        from espo_impl.core.deploy_manager import phase2_install_espocrm

        self._rlog.step("STARTED", "Phase 2: EspoCRM Installation")
        self.phase_started.emit(2)
        self._log("=== Phase 2: EspoCRM Installation ===")
        success, error = phase2_install_espocrm(ssh, self.config, self._log)
        if not success:
            self._rlog.step(
                "FAILED", "Phase 2: EspoCRM Installation", error=error,
            )
            self._rlog.result(f"FAILED\n\nFailed at step: Phase 2\nError detail: {error}")
            self._log(f"Phase 2 failed: {error}", "error")
            self.phase_failed.emit(2, error)
            self.finished_error.emit(error)
            return
        self._rlog.step("OK", "Phase 2: EspoCRM Installation")
        self.phase_completed.emit(2)
        self._log("Phase 2 completed successfully")

        # Step 5: Re-run Phase 3 (Post-Install Configuration)
        from espo_impl.core.deploy_manager import phase3_post_install

        self._rlog.step("STARTED", "Phase 3: Post-Install Configuration")
        self.phase_started.emit(3)
        self._log("=== Phase 3: Post-Install Configuration ===")
        success, error = phase3_post_install(ssh, self.config, self._log)
        if not success:
            self._rlog.step(
                "FAILED", "Phase 3: Post-Install Configuration", error=error,
            )
            self._rlog.result(
                f"FAILED\n\nPhase 2 reinstallation: COMPLETED\n"
                f"Failed at step: Phase 3\nError detail: {error}"
            )
            self._log(f"Phase 3 failed: {error}", "error")
            self.phase_failed.emit(3, error)
            self.finished_error.emit(error)
            return
        self._rlog.step("OK", "Phase 3: Post-Install Configuration")
        self.phase_completed.emit(3)
        self._log("Phase 3 completed successfully")

        # Save updated config (cert_expiry_date, deployed_at)
        save_deploy_config(
            self.instances_dir, self.profile.slug, self.config
        )

        # Step 6: Re-run Phase 4 (Verification)
        from espo_impl.core.deploy_manager import phase4_verify

        self._rlog.step("STARTED", "Phase 4: Verification")
        self.phase_started.emit(4)
        self._log("=== Phase 4: Verification ===")
        overall, results = phase4_verify(ssh, self.config, self._log)

        # Log verification results
        self._log("")
        self._log("=== Verification Results ===")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            level = "info" if r["passed"] else "error"
            self._log(f"  {status}: {r['check']}", level)

        if not overall:
            failed = [r["check"] for r in results if not r["passed"]]
            error_msg = f"Failed checks: {', '.join(failed)}"
            self._rlog.step("FAILED", "Phase 4: Verification", error=error_msg)
            result_lines = [
                "FAILED",
                "",
                "Phase 2 reinstallation: COMPLETED",
                "Phase 3 post-install:   COMPLETED",
                "Phase 4 verification:   FAILED",
            ]
            for r in results:
                s = "PASS" if r["passed"] else "FAIL"
                result_lines.append(f"  {s}: {r['check']}")
            self._rlog.result("\n".join(result_lines))
            self.phase_failed.emit(4, error_msg)
            self.finished_error.emit(error_msg)
            return

        self._rlog.step("OK", "Phase 4: Verification")
        self.phase_completed.emit(4)

        # Step 7: Provision API user on the fresh instance
        self._provision_api_user()

        # Write success result to log
        result_lines = [
            "COMPLETED",
            "",
            "Phase 2 reinstallation: COMPLETED",
            "Phase 3 post-install:   COMPLETED",
            "Phase 4 verification:   COMPLETED",
        ]
        for r in results:
            s = "PASS" if r["passed"] else "FAIL"
            result_lines.append(f"  {s}: {r['check']}")
        self._rlog.result("\n".join(result_lines))

        self._log("")
        self._log("=== Full Database Reset complete ===", "success")
        self.finished_ok.emit()

    def _provision_api_user(self) -> None:
        """Create an API user on the fresh EspoCRM instance via REST API."""
        self._rlog.step("STARTED", "Provision API user")
        self._log("Creating API user on fresh instance...")

        api_key = secrets.token_urlsafe(32)
        url = f"https://{self.config.full_domain}/api/v1/User"
        payload = {
            "userName": "crmbuilder-api",
            "type": "api",
            "authMethod": "ApiKey",
            "apiKey": api_key,
            "isActive": True,
        }

        try:
            session = requests.Session()
            # Use Basic auth with admin credentials from DeployConfig
            import base64
            creds = (
                f"{self.config.admin_username}:{self.config.admin_password}"
            )
            encoded = base64.b64encode(
                creds.encode("utf-8")
            ).decode("utf-8")
            session.headers.update({
                "Content-Type": "application/json",
                "Authorization": f"Basic {encoded}",
                "Espo-Authorization": encoded,
            })

            resp = session.post(url, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                self._rlog.step("OK", "Provision API user")
                self._log(
                    "API user 'crmbuilder-api' created successfully.",
                    "success",
                )
                # Update the instance profile with the new API key
                self.profile.api_key = api_key
                self.profile.auth_method = "api_key"
                self.profile.secret_key = None
                self._save_profile()
                self.profile_updated.emit(self.profile)
                self._log(
                    "Instance profile updated with new API key.", "success"
                )
                self._log("Ready to run program files.", "success")
            else:
                raise requests.RequestException(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except Exception as exc:
            self._rlog.step(
                "FAILED", "Provision API user", error=str(exc),
            )
            self._log(
                f"Could not create API user automatically: {exc}",
                "warning",
            )
            self._log(
                "Falling back to Basic auth with admin credentials.",
                "warning",
            )
            # Fallback: switch profile to Basic auth
            self.profile.auth_method = "basic"
            self.profile.api_key = self.config.admin_username
            self.profile.secret_key = self.config.admin_password
            self._save_profile()
            self.profile_updated.emit(self.profile)
            self._log(
                "Instance profile switched to Basic auth. You can create "
                "an API user manually later through the EspoCRM "
                "administration panel.",
                "warning",
            )

    def _save_profile(self) -> None:
        """Save the updated instance profile to disk."""
        path = self.instances_dir / f"{self.profile.slug}.json"
        data = {
            "name": self.profile.name,
            "url": self.profile.url,
            "api_key": self.profile.api_key,
            "auth_method": self.profile.auth_method,
        }
        if self.profile.secret_key:
            data["secret_key"] = self.profile.secret_key
        if self.profile.project_folder:
            data["project_folder"] = self.profile.project_folder
        path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )


# ── Recovery Tools dialog ─────────────────────────────────────────────


class RecoveryDialog(QDialog):
    """Recovery Tools dialog with credential reset and full database reset.

    :param profile: Instance profile.
    :param config: Deployment configuration.
    :param instances_dir: Path to instances directory.
    :param parent: Parent widget.
    """

    config_updated = Signal(object)
    profile_updated = Signal(object)

    def __init__(
        self,
        profile: InstanceProfile,
        config: DeployConfig,
        instances_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.config = config
        self.instances_dir = instances_dir
        self._worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dialog layout."""
        self.setWindowTitle("Recovery Tools")
        self.setMinimumSize(650, 550)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            f"<b>Recovery Tools</b> — {self.profile.name} "
            f"({self.config.full_domain})"
        )
        header.setStyleSheet("font-size: 14px; padding: 4px;")
        layout.addWidget(header)

        # Operation 1: Reset Admin Credentials
        cred_group = QGroupBox("Reset Admin Credentials")
        cred_layout = QVBoxLayout(cred_group)

        cred_desc = QLabel(
            "Reset the EspoCRM admin login credentials. "
            "All data and configuration are preserved."
        )
        cred_desc.setWordWrap(True)
        cred_desc.setStyleSheet("color: gray; font-size: 11px;")
        cred_layout.addWidget(cred_desc)

        form = QVBoxLayout()

        username_row = QHBoxLayout()
        username_row.addWidget(QLabel("New Username:"))
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("admin")
        username_row.addWidget(self._username_input)
        form.addLayout(username_row)

        pw_row = QHBoxLayout()
        pw_row.addWidget(QLabel("New Password:"))
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        pw_show_btn = QPushButton("Show")
        pw_show_btn.setCheckable(True)
        pw_show_btn.setFixedWidth(60)
        pw_show_btn.toggled.connect(
            lambda checked: (
                self._password_input.setEchoMode(
                    QLineEdit.EchoMode.Normal if checked
                    else QLineEdit.EchoMode.Password
                ),
                pw_show_btn.setText("Hide" if checked else "Show"),
            )
        )
        pw_row.addWidget(self._password_input)
        pw_row.addWidget(pw_show_btn)
        form.addLayout(pw_row)

        confirm_row = QHBoxLayout()
        confirm_row.addWidget(QLabel("Confirm Password:"))
        self._confirm_input = QLineEdit()
        self._confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_show_btn = QPushButton("Show")
        confirm_show_btn.setCheckable(True)
        confirm_show_btn.setFixedWidth(60)
        confirm_show_btn.toggled.connect(
            lambda checked: (
                self._confirm_input.setEchoMode(
                    QLineEdit.EchoMode.Normal if checked
                    else QLineEdit.EchoMode.Password
                ),
                confirm_show_btn.setText("Hide" if checked else "Show"),
            )
        )
        confirm_row.addWidget(self._confirm_input)
        confirm_row.addWidget(confirm_show_btn)
        form.addLayout(confirm_row)

        cred_layout.addLayout(form)

        self._reset_cred_btn = QPushButton("Reset Credentials")
        self._reset_cred_btn.clicked.connect(self._on_reset_credentials)
        cred_layout.addWidget(self._reset_cred_btn)

        layout.addWidget(cred_group)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Operation 2: Full Database Reset
        reset_group = QGroupBox("Full Database Reset")
        reset_layout = QVBoxLayout(reset_group)

        # Red warning panel
        warning = QLabel(
            "WARNING: This will permanently delete ALL data in the CRM "
            "including all entities, records, custom fields, and "
            "configuration. This cannot be undone."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background-color: #B71C1C; color: white; "
            "padding: 10px; border-radius: 4px; font-weight: bold;"
        )
        reset_layout.addWidget(warning)

        confirm_field_row = QHBoxLayout()
        confirm_field_row.addWidget(
            QLabel("Type RESET to confirm:")
        )
        self._reset_confirm_input = QLineEdit()
        self._reset_confirm_input.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 4px;"
        )
        self._reset_confirm_input.setPlaceholderText("RESET")
        confirm_field_row.addWidget(self._reset_confirm_input)
        reset_layout.addLayout(confirm_field_row)

        self._full_reset_btn = QPushButton("Proceed with Full Reset")
        self._full_reset_btn.setStyleSheet(
            "QPushButton { background-color: #C62828; color: white; "
            "font-weight: bold; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #E53935; }"
        )
        self._full_reset_btn.clicked.connect(self._on_full_reset)
        reset_layout.addWidget(self._full_reset_btn)

        layout.addWidget(reset_group)

        # Log window
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Log</b>"))
        log_header.addStretch()
        layout.addLayout(log_header)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QFont("Monospace", 10))
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

        # Close button
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    # ── Log helpers ───────────────────────────────────────────────

    def _append_log(self, message: str, level: str = "info") -> None:
        """Append a line to the log window.

        :param message: Log message.
        :param level: 'info', 'warning', 'error', or 'success'.
        """
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        hex_color = LOG_COLORS.get(level, LOG_COLORS["info"])
        fmt.setForeground(QColor(hex_color))
        fmt.setFont(QFont("Monospace", 10))

        if not self._log_edit.document().isEmpty():
            cursor.insertText("\n", fmt)
        cursor.insertText(message, fmt)

        self._log_edit.setTextCursor(cursor)
        self._log_edit.ensureCursorVisible()

    def _log_dir(self) -> Path:
        """Return the recovery logs directory path."""
        return Path(__file__).resolve().parents[2] / "data" / "recovery_logs"

    # ── Operation 1: Reset Admin Credentials ──────────────────────

    def _on_reset_credentials(self) -> None:
        """Handle Reset Credentials button click."""
        if self._worker is not None:
            self._append_log(
                "An operation is already in progress.", "warning"
            )
            return

        username = self._username_input.text().strip()
        password = self._password_input.text()
        confirm = self._confirm_input.text()

        if not username:
            QMessageBox.warning(
                self, "Missing Field", "Please enter a new admin username."
            )
            return
        if not password:
            QMessageBox.warning(
                self, "Missing Field", "Please enter a new admin password."
            )
            return
        if password != confirm:
            QMessageBox.warning(
                self, "Password Mismatch",
                "Password and confirmation do not match."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Credential Reset",
            "This will reset the EspoCRM admin credentials. Are you sure?",
            QMessageBox.StandardButton.Cancel
            | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        rlog = RecoveryLog(
            self._log_dir(),
            self.profile.name,
            "Reset Admin Credentials",
            self.config,
        )

        self._worker = CredentialResetWorker(
            self.config, username, password, rlog, self
        )
        self._worker.log_line.connect(self._append_log)
        self._worker.finished_ok.connect(
            lambda u, p: self._on_cred_reset_ok(u, p, rlog)
        )
        self._worker.finished_error.connect(
            lambda e: self._on_operation_error(e, rlog)
        )
        self._worker.start()

    def _on_cred_reset_ok(
        self, username: str, password: str, rlog: RecoveryLog
    ) -> None:
        """Handle successful credential reset."""
        self._worker = None

        # Update DeployConfig and save
        self.config.admin_username = username
        self.config.admin_password = password
        save_deploy_config(
            self.instances_dir, self.profile.slug, self.config
        )
        self.config_updated.emit(self.config)

        self._append_log("")
        self._append_log(
            f"New admin username: {username}", "success"
        )
        self._append_log(
            "Please log in to the CRM to verify access.", "info"
        )
        self._append_log(f"Log file: {rlog.path}", "info")

    # ── Operation 2: Full Database Reset ──────────────────────────

    def _on_full_reset(self) -> None:
        """Handle Proceed with Full Reset button click."""
        if self._worker is not None:
            self._append_log(
                "An operation is already in progress.", "warning"
            )
            return

        if self._reset_confirm_input.text() != "RESET":
            QMessageBox.warning(
                self,
                "Confirmation Required",
                "You must type RESET in the confirmation field to proceed.",
            )
            return

        reply = QMessageBox.warning(
            self,
            "Final Confirmation",
            "Are you absolutely sure? All CRM data will be "
            "permanently deleted.",
            QMessageBox.StandardButton.Cancel
            | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        # Rename OK button text via a custom dialog would be ideal,
        # but QMessageBox.warning with Ok/Cancel is consistent with the
        # project patterns. The warning text is explicit enough.

        rlog = RecoveryLog(
            self._log_dir(),
            self.profile.name,
            "Full Database Reset",
            self.config,
        )

        self._worker = FullResetWorker(
            self.config, self.profile, self.instances_dir, rlog, self
        )
        self._worker.log_line.connect(self._append_log)
        self._worker.phase_started.connect(
            lambda p: self._append_log(f"Phase {p} started...")
        )
        self._worker.phase_completed.connect(
            lambda p: self._append_log(f"Phase {p} completed.")
        )
        self._worker.phase_failed.connect(
            lambda p, e: self._append_log(
                f"Phase {p} failed: {e}", "error"
            )
        )
        self._worker.profile_updated.connect(
            lambda prof: self.profile_updated.emit(prof)
        )
        self._worker.finished_ok.connect(
            lambda: self._on_full_reset_ok(rlog)
        )
        self._worker.finished_error.connect(
            lambda e: self._on_operation_error(e, rlog)
        )
        self._worker.start()

    def _on_full_reset_ok(self, rlog: RecoveryLog) -> None:
        """Handle successful full reset."""
        self._worker = None
        self._append_log(f"Log file: {rlog.path}", "info")

    # ── Shared handlers ───────────────────────────────────────────

    def _on_operation_error(self, error: str, rlog: RecoveryLog) -> None:
        """Handle operation failure."""
        self._worker = None
        self._append_log(f"Log file: {rlog.path}", "info")
