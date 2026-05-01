"""Background workers for Recovery & Reset operations.

``CredentialResetWorker`` runs the SSH SQL UPDATE that resets the
EspoCRM admin user's username and password.

``FullResetWorker`` tears down the install directory and re-runs the
EspoCRM installer + post-install + verify phases. Destructive: wipes
all data on the Droplet.

Both workers update the per-client ``Instance`` row with the new admin
credentials on success so the API path keeps working.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from PySide6.QtCore import QThread, Signal

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.recovery_ssh import (
    build_reinstall_config,
    reset_admin_credentials,
    teardown,
)
from automation.core.deployment.ssh_deploy import (
    connect_ssh,
    phase_install_espocrm,
    phase_post_install,
    phase_verify,
)


class CredentialResetWorker(QThread):
    """Reset the EspoCRM admin user via SSH-driven SQL.

    :param config: Hydrated InstanceDeployConfig.
    :param db_path: Path to the per-client SQLite database.
    :param instance_id: Instance.id to update on success.
    :param new_username: New admin username.
    :param new_password: New admin password (plaintext).
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    finished_ok = Signal(str)            # new username
    finished_error = Signal(str)         # error message

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        instance_id: int,
        new_username: str,
        new_password: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path
        self.instance_id = instance_id
        self.new_username = new_username
        self.new_password = new_password

    def _log(self, message: str, level: str = "info") -> None:
        self.log_line.emit(message, level)

    def run(self) -> None:
        try:
            self._log("Connecting via SSH...", "info")
            ssh = connect_ssh(self.config)
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.finished_error.emit(str(exc))
            return

        try:
            ok, error = reset_admin_credentials(
                ssh, self.config, self.new_username, self.new_password,
                self._log,
            )
        finally:
            ssh.close()

        if not ok:
            self.finished_error.emit(error)
            return

        self._update_instance_row()
        self.finished_ok.emit(self.new_username)

    def _update_instance_row(self) -> None:
        """Persist the new credentials into Instance.username/password."""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute(
                    "UPDATE Instance SET username = ?, password = ?, "
                    "updated_at = ? WHERE id = ?",
                    (
                        self.new_username,
                        self.new_password,
                        datetime.now(UTC).isoformat(),
                        self.instance_id,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            self._log(
                f"Could not update Instance row: {exc}", "warning"
            )


class FullResetWorker(QThread):
    """Tear down and reinstall an EspoCRM deployment from scratch.

    Destructive — wipes all data on the Droplet. Called only after the
    user has confirmed the action in the dialog.

    :param config: Hydrated InstanceDeployConfig.
    :param db_path: Path to the per-client database.
    :param instance_id: Instance.id to update on success.
    :param new_admin_username: New admin username.
    :param new_admin_password: New admin password.
    :param new_db_password: New application-level DB password.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    phase_started = Signal(int)              # 1=teardown, 2=install, 3=post, 4=verify
    phase_completed = Signal(int)
    phase_failed = Signal(int, str)
    verify_results = Signal(list)
    finished_ok = Signal()
    finished_error = Signal(str)

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        instance_id: int,
        new_admin_username: str,
        new_admin_password: str,
        new_db_password: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path
        self.instance_id = instance_id
        self.new_admin_username = new_admin_username
        self.new_admin_password = new_admin_password
        self.new_db_password = new_db_password

    def _log(self, message: str, level: str = "info") -> None:
        self.log_line.emit(message, level)

    def run(self) -> None:
        try:
            self._log("Connecting via SSH...", "info")
            ssh = connect_ssh(self.config)
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.finished_error.emit(str(exc))
            return

        try:
            self._run(ssh)
        finally:
            ssh.close()

    def _run(self, ssh) -> None:
        # Phase 1: teardown
        self.phase_started.emit(1)
        self._log("=== Phase 1: Teardown ===", "info")
        ok, error = teardown(ssh, self._log)
        if not ok:
            self.phase_failed.emit(1, error)
            self.finished_error.emit(error)
            return
        self.phase_completed.emit(1)

        # Build a SelfHostedConfig from the durable + user-supplied bits
        install_config = build_reinstall_config(
            self.config,
            admin_username=self.new_admin_username,
            admin_password=self.new_admin_password,
            db_password=self.new_db_password,
        )

        # Phase 2: install
        self.phase_started.emit(2)
        self._log("=== Phase 2: EspoCRM Installation ===", "info")
        ok, error = phase_install_espocrm(ssh, install_config, self._log)
        if not ok:
            self.phase_failed.emit(2, error)
            self.finished_error.emit(error)
            return
        self.phase_completed.emit(2)

        # Phase 3: post-install
        self.phase_started.emit(3)
        self._log("=== Phase 3: Post-Install ===", "info")
        ok, error, cert_expiry = phase_post_install(
            ssh, install_config, self._log
        )
        if not ok:
            self.phase_failed.emit(3, error)
            self.finished_error.emit(error)
            return
        self.phase_completed.emit(3)

        # Phase 4: verify
        self.phase_started.emit(4)
        self._log("=== Phase 4: Verification ===", "info")
        overall, results = phase_verify(ssh, self.config.domain, self._log)
        self.verify_results.emit(results)
        if not overall:
            failed = [r["check"] for r in results if not r["passed"]]
            error = f"Failed checks: {', '.join(failed)}"
            self.phase_failed.emit(4, error)
            self.finished_error.emit(error)
            return
        self.phase_completed.emit(4)

        self._update_records(cert_expiry)
        self.finished_ok.emit()

    def _update_records(self, cert_expiry: str | None) -> None:
        """Persist new admin credentials and cert expiry to the DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    "UPDATE Instance SET username = ?, password = ?, "
                    "updated_at = ? WHERE id = ?",
                    (
                        self.new_admin_username,
                        self.new_admin_password,
                        now,
                        self.instance_id,
                    ),
                )
                if cert_expiry:
                    conn.execute(
                        "UPDATE InstanceDeployConfig SET "
                        "cert_expiry_date = ?, updated_at = ? "
                        "WHERE instance_id = ?",
                        (cert_expiry, now, self.instance_id),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            self._log(f"Could not update DB records: {exc}", "warning")
