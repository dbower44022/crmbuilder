"""Background worker for deployment operations.

Runs SSH-based deployment phases (self-hosted) and HTTP-based
connectivity checks (cloud/BYO) off the main thread.

Mirrors the signal pattern from ``espo_impl/workers/deploy_worker.py``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from automation.core.deployment.connectivity import (
    check_espocrm_connectivity,
)
from automation.core.deployment.ssh_deploy import (
    SelfHostedConfig,
    cleanup_phase1,
    cleanup_phase2,
    connect_ssh,
    phase_install_espocrm,
    phase_post_install,
    phase_server_prep,
    phase_verify,
    wait_for_dns,
)


class SelfHostedWorker(QThread):
    """Background worker for the self-hosted deployment path.

    :param config: Self-hosted configuration from the wizard.
    :param administrator_inputs: Optional ``AdministratorInputs`` bag
        from the Documentation Inputs wizard step. When supplied along
        with ``instance_id``, ``db_path``, and ``project_folder``, the
        worker persists the wizard's deploy state and generates a
        Deployment Record ``.docx`` before closing the SSH connection.
    :param instance_id: The ``Instance.id`` row this deploy targets.
    :param db_path: Filesystem path to the per-client SQLite database;
        the worker opens its own connection on the worker thread.
    :param project_folder: Absolute path to the client's project folder
        (where ``PRDs/deployment/`` lives).
    :param client_name: The human-readable client name from the master
        ``Client`` table (e.g., "Cleveland Business Mentors"). Passed
        verbatim into the Deployment Record so the document title and
        metadata block render the client's display name rather than
        the technical instance code.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)              # (message, level)
    step_started = Signal(str)               # step name
    step_completed = Signal(str)             # step name
    step_failed = Signal(str, str)           # (step name, error)
    deployment_finished = Signal(bool)       # overall success
    verify_results = Signal(list)            # check result dicts
    cert_expiry = Signal(str)                # ISO date
    record_generated = Signal(str)           # absolute path of .docx
    record_generation_failed = Signal(str)   # exception message

    def __init__(
        self,
        config: SelfHostedConfig,
        *,
        administrator_inputs=None,
        instance_id: int | None = None,
        db_path: str | None = None,
        project_folder: str | None = None,
        client_name: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self._administrator_inputs = administrator_inputs
        self._instance_id = instance_id
        self._db_path = db_path
        self._project_folder = project_folder
        self._client_name = client_name

    def _log(self, message: str, level: str = "info") -> None:
        self.log_line.emit(message, level)

    def run(self) -> None:
        """Execute self-hosted deployment phases sequentially."""
        cfg = self.config
        try:
            self._log("Connecting via SSH...")
            ssh = connect_ssh(cfg)
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.step_failed.emit("ssh_connect", str(exc))
            self.deployment_finished.emit(False)
            return

        try:
            self._run_phases(ssh)
        finally:
            ssh.close()

    def _run_phases(self, ssh) -> None:
        cfg = self.config

        # DNS verification
        self.step_started.emit("dns_verify")
        self._log("=== DNS Verification ===")
        if not wait_for_dns(cfg.domain, cfg.ssh_host, self._log):
            self.step_failed.emit("dns_verify", "DNS validation timed out")
            self.deployment_finished.emit(False)
            return
        self.step_completed.emit("dns_verify")

        # Server preparation
        self.step_started.emit("server_prep")
        self._log("=== Server Preparation ===")
        ok, err = phase_server_prep(ssh, self._log)
        if not ok:
            self._log(f"Server prep failed: {err}", "error")
            cleanup_phase1(ssh, self._log)
            self.step_failed.emit("server_prep", err)
            self.deployment_finished.emit(False)
            return
        self.step_completed.emit("server_prep")

        # DNS re-verify before SSL
        self._log("Re-validating DNS before installation...")
        if not wait_for_dns(cfg.domain, cfg.ssh_host, self._log):
            self.step_failed.emit("dns_reverify", "DNS validation timed out")
            self.deployment_finished.emit(False)
            return

        # EspoCRM installation + TLS
        self.step_started.emit("install")
        self._log("=== EspoCRM Installation ===")
        ok, err = phase_install_espocrm(ssh, cfg, self._log)
        if not ok:
            self._log(f"Installation failed: {err}", "error")
            cleanup_phase2(ssh, self._log)
            self.step_failed.emit("install", err)
            self.deployment_finished.emit(False)
            return
        self.step_completed.emit("install")

        # Post-install checks
        self.step_started.emit("post_install")
        self._log("=== Post-Install Verification ===")
        ok, err, cert_date = phase_post_install(ssh, cfg, self._log)
        if not ok:
            self.step_failed.emit("post_install", err)
            self.deployment_finished.emit(False)
            return
        if cert_date:
            self.cert_expiry.emit(cert_date)
        self.step_completed.emit("post_install")

        # Verification
        self.step_started.emit("verify")
        self._log("=== Connectivity Verification ===")
        overall, results = phase_verify(ssh, cfg.domain, self._log)
        self.verify_results.emit(results)
        if overall:
            self.step_completed.emit("verify")
        else:
            failed = [r["check"] for r in results if not r["passed"]]
            self.step_failed.emit("verify", f"Failed: {', '.join(failed)}")

        # Deployment Record generation (deployment-record series Prompt B).
        # Runs on the success path only; failures are non-fatal so the
        # deploy as a whole is still considered successful.
        if overall and self._can_generate_record():
            self._persist_and_generate_record(ssh)

        self._log("")
        self._log("=== Deployment complete ===")
        self.deployment_finished.emit(overall)

    def _can_generate_record(self) -> bool:
        """True if the worker has every input required to generate a Record."""
        return all(
            value is not None for value in (
                self._administrator_inputs,
                self._instance_id,
                self._db_path,
                self._project_folder,
            )
        )

    def _persist_and_generate_record(self, ssh) -> None:
        """Persist deploy state and generate the Deployment Record .docx.

        Opens its own sqlite connection on the worker thread, persists
        the InstanceDeployConfig row (including the four
        administrator-supplied columns), then runs SSH inspection and
        the .docx generator. Any failure here is logged as a warning
        and surfaced via ``record_generation_failed``; the deploy is
        still considered successful.
        """
        # Lazy imports keep this module's startup cost down and avoid
        # importing python-docx when only the cloud/BYO worker is used.
        import sqlite3

        from automation.core.deployment.deploy_config_repo import (
            load_deploy_config,
        )
        from automation.core.deployment.record_generator import (
            generate_deployment_record,
            inspect_server_for_record_values,
        )
        from automation.core.deployment.wizard_logic import (
            persist_deploy_config_from_wizard,
            update_instance_from_wizard,
        )
        from automation.ui.deployment.deployment_logic import (
            load_instance_detail,
        )

        self.step_started.emit("generate_record")
        self._log("=== Generating Deployment Record ===")

        cfg = self.config

        try:
            project_folder = Path(self._project_folder)
            if not project_folder.is_dir():
                msg = (
                    f"Project folder does not exist: {self._project_folder}"
                )
                self._log(msg, "warning")
                self.record_generation_failed.emit(msg)
                return

            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                update_instance_from_wizard(
                    conn, self._instance_id,
                    url=f"https://{cfg.domain}",
                    username=cfg.admin_username,
                    password=cfg.admin_password,
                )
                persist_deploy_config_from_wizard(
                    conn, self._instance_id, cfg,
                    administrator_inputs=self._administrator_inputs,
                )
                instance = load_instance_detail(conn, self._instance_id)
                deploy_config = load_deploy_config(conn, self._instance_id)
            finally:
                conn.close()

            if instance is None or deploy_config is None:
                msg = (
                    "Could not reload Instance or InstanceDeployConfig "
                    "after persistence; skipping Record generation."
                )
                self._log(msg, "warning")
                self.record_generation_failed.emit(msg)
                return

            values = inspect_server_for_record_values(
                ssh,
                instance,
                deploy_config,
                self._administrator_inputs,
                client_name=self._client_name or instance.name or "",
            )

            output_path = (
                project_folder
                / "PRDs"
                / "deployment"
                / f"{instance.code}-Instance-Deployment-Record.docx"
            )
            generate_deployment_record(values, output_path)
            self._log(f"Deployment Record written to {output_path}")
            self.record_generated.emit(str(output_path))
            self.step_completed.emit("generate_record")
        except Exception as exc:
            self._log(f"Deployment Record generation failed: {exc}", "warning")
            self.record_generation_failed.emit(str(exc))


class ConnectivityWorker(QThread):
    """Background worker for cloud-hosted / bring-your-own connectivity.

    :param url: Instance URL.
    :param username: Admin username.
    :param password: Admin password.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    result_ready = Signal(object)  # ConnectivityResult

    def __init__(
        self, url: str, username: str, password: str, parent=None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._username = username
        self._password = password

    def run(self) -> None:
        """Run connectivity check."""
        self.log_line.emit("Checking connectivity...", "info")
        result = check_espocrm_connectivity(
            self._url, self._username, self._password,
        )
        if result.error:
            self.log_line.emit(f"Error: {result.error}", "error")
        elif result.authenticated:
            self.log_line.emit("Connected and authenticated successfully", "info")
            if result.version:
                self.log_line.emit(f"EspoCRM version: {result.version}", "info")
        self.result_ready.emit(result)
