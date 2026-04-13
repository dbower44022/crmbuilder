"""Background worker threads for deployment operations."""

import time

from PySide6.QtCore import QThread, Signal

from espo_impl.core.deploy_manager import (
    check_dns,
    check_server_os,
    cleanup_phase1,
    cleanup_phase2,
    connect_ssh,
    get_cert_expiry,
    phase1_server_prep,
    phase2_install_espocrm,
    phase3_post_install,
    phase4_verify,
    save_deploy_config,
)
from espo_impl.core.models import DeployConfig, InstanceProfile


class DeployWorker(QThread):
    """Background worker that runs deployment phases off the main thread.

    :param config: Deployment configuration.
    :param profile: Instance connection profile.
    :param instances_dir: Path to instances directory for config saving.
    :param start_phase: Phase to start from (1-4). Default 1.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    phase_started = Signal(int)
    phase_completed = Signal(int)
    phase_failed = Signal(int, str)
    dns_retry = Signal(int)
    deployment_finished = Signal(bool)
    verify_results = Signal(list)
    cert_expiry_updated = Signal(str)

    def __init__(
        self,
        config: DeployConfig,
        profile: InstanceProfile,
        instances_dir,
        start_phase: int = 1,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.profile = profile
        self.instances_dir = instances_dir
        self.start_phase = start_phase

    def _log(self, message: str, level: str = "info") -> None:
        """Emit a log line signal."""
        self.log_line.emit(message, level)

    def run(self) -> None:
        """Execute deployment phases sequentially."""
        try:
            self._log("Connecting via SSH...")
            ssh = connect_ssh(
                self.config.droplet_ip,
                self.config.ssh_user,
                self.config.ssh_key_path,
            )
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.deployment_finished.emit(False)
            return

        try:
            self._run_phases(ssh)
        finally:
            ssh.close()

    def _run_phases(self, ssh) -> None:
        """Run phases starting from start_phase."""
        # Pre-flight OS check (only when starting from Phase 1 or 2)
        if self.start_phase <= 2:
            self._log("Checking server OS compatibility...")
            supported, error = check_server_os(ssh, self._log)
            if not supported:
                self._log(error, "error")
                self.phase_started.emit(max(self.start_phase, 1))
                self.phase_failed.emit(
                    max(self.start_phase, 1),
                    "Server OS is not supported — see log for details",
                )
                self.deployment_finished.emit(False)
                return

        # Phase 1
        if self.start_phase <= 1:
            # DNS check before Phase 1
            self._log("Validating DNS before Phase 1...")
            ok = self._wait_for_dns()
            if not ok:
                self._log("DNS validation failed — aborting", "error")
                self.deployment_finished.emit(False)
                return

            self.phase_started.emit(1)
            self._log("=== Phase 1: Server Preparation ===")
            success, error = phase1_server_prep(
                ssh, self.config, self._log
            )
            if not success:
                self._log(f"Phase 1 failed: {error}", "error")
                cleanup_phase1(ssh, self._log)
                self.phase_failed.emit(1, error)
                self.deployment_finished.emit(False)
                return
            self.phase_completed.emit(1)
            self._log("Phase 1 completed successfully")

        # Phase 2
        if self.start_phase <= 2:
            # DNS re-check before Phase 2 (SSL needs it)
            self._log("Re-validating DNS before Phase 2 (SSL)...")
            ok = self._wait_for_dns()
            if not ok:
                self._log("DNS validation failed — aborting", "error")
                self.deployment_finished.emit(False)
                return

            self.phase_started.emit(2)
            self._log("=== Phase 2: EspoCRM Installation ===")
            success, error = phase2_install_espocrm(
                ssh, self.config, self._log
            )
            if not success:
                self._log(f"Phase 2 failed: {error}", "error")
                cleanup_phase2(ssh, self._log)
                self.phase_failed.emit(2, error)
                self.deployment_finished.emit(False)
                return
            self.phase_completed.emit(2)
            self._log("Phase 2 completed successfully")

        # Phase 3
        if self.start_phase <= 3:
            self.phase_started.emit(3)
            self._log("=== Phase 3: Post-Install Configuration ===")
            success, error = phase3_post_install(
                ssh, self.config, self._log
            )
            if not success:
                self._log(f"Phase 3 failed: {error}", "error")
                self.phase_failed.emit(3, error)
                self.deployment_finished.emit(False)
                return
            self.phase_completed.emit(3)
            self._log("Phase 3 completed successfully")

            # Save updated config (cert_expiry_date, deployed_at)
            save_deploy_config(
                self.instances_dir, self.profile.slug, self.config
            )

            # Emit cert expiry for UI to update instance profile URL
            if self.config.cert_expiry_date:
                self.cert_expiry_updated.emit(self.config.cert_expiry_date)

        # Phase 4
        if self.start_phase <= 4:
            self.phase_started.emit(4)
            self._log("=== Phase 4: Verification ===")
            overall, results = phase4_verify(
                ssh, self.config, self._log
            )
            self.verify_results.emit(results)
            if overall:
                self.phase_completed.emit(4)
                self._log("Phase 4: All checks passed")
            else:
                failed = [r["check"] for r in results if not r["passed"]]
                self.phase_failed.emit(
                    4, f"Failed checks: {', '.join(failed)}"
                )

        self._log("")
        self._log("=== Deployment complete ===")
        self.deployment_finished.emit(True)

    def _wait_for_dns(self) -> bool:
        """Wait for DNS to resolve, retrying every 30s up to 10 minutes."""
        timeout = 600
        interval = 30
        elapsed = 0

        while elapsed < timeout:
            ok, msg = check_dns(
                self.config.full_domain, self.config.droplet_ip
            )
            if ok:
                self._log("DNS validated successfully")
                return True

            remaining = timeout - elapsed
            self._log(
                f"DNS not ready: {msg}. Retrying in {interval}s "
                f"({remaining}s remaining)...",
                "warning",
            )
            self.dns_retry.emit(remaining)
            time.sleep(interval)
            elapsed += interval

        self._log("DNS validation timed out after 10 minutes", "error")
        return False


class CertCheckWorker(QThread):
    """Background worker to check SSL certificate expiry.

    :param domain: Fully qualified domain name.
    :param parent: Parent QObject.
    """

    cert_expiry_result = Signal(str)

    def __init__(self, domain: str, parent=None) -> None:
        super().__init__(parent)
        self.domain = domain

    def run(self) -> None:
        """Check certificate expiry in background."""
        result = get_cert_expiry(self.domain)
        if result:
            self.cert_expiry_result.emit(result)
