"""Background worker for deployment operations.

Runs SSH-based deployment phases (self-hosted) and HTTP-based
connectivity checks (cloud/BYO) off the main thread.

Mirrors the signal pattern from ``espo_impl/workers/deploy_worker.py``.
"""

from __future__ import annotations

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
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)          # (message, level)
    step_started = Signal(str)           # step name
    step_completed = Signal(str)         # step name
    step_failed = Signal(str, str)       # (step name, error)
    deployment_finished = Signal(bool)   # overall success
    verify_results = Signal(list)        # check result dicts
    cert_expiry = Signal(str)            # ISO date

    def __init__(self, config: SelfHostedConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config

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

        self._log("")
        self._log("=== Deployment complete ===")
        self.deployment_finished.emit(overall)


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
