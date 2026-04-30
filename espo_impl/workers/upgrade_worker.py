"""Background worker threads for EspoCRM upgrade operations."""

from PySide6.QtCore import QThread, Signal

from espo_impl.core.deploy_manager import connect_ssh, save_deploy_config
from espo_impl.core.models import DeployConfig, InstanceProfile
from espo_impl.core.upgrade_manager import (
    get_current_version,
    get_latest_version,
    phase1_pre_upgrade_checks,
    phase2_backup,
    phase3_run_upgrade,
    phase4_verify_upgrade,
)


class UpgradeWorker(QThread):
    """Background worker that runs upgrade phases off the main thread.

    :param config: Deployment configuration (mutated in place as phases run).
    :param profile: Instance connection profile.
    :param instances_dir: Path to instances directory for config saving.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    phase_started = Signal(int)
    phase_completed = Signal(int)
    phase_failed = Signal(int, str)
    version_detected = Signal(str, str)  # current, latest
    verify_results = Signal(list)
    upgrade_finished = Signal(bool)

    def __init__(
        self,
        config: DeployConfig,
        profile: InstanceProfile,
        instances_dir,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.profile = profile
        self.instances_dir = instances_dir

    def _log(self, message: str, level: str = "info") -> None:
        """Emit a log line signal."""
        self.log_line.emit(message, level)

    def run(self) -> None:
        """Execute upgrade phases sequentially."""
        try:
            self._log("Connecting via SSH...")
            ssh = connect_ssh(
                self.config.droplet_ip,
                self.config.ssh_user,
                self.config.ssh_key_path,
            )
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.upgrade_finished.emit(False)
            return

        try:
            self._run_phases(ssh)
        finally:
            ssh.close()

    def _run_phases(self, ssh) -> None:
        """Run all four upgrade phases."""
        self.phase_started.emit(1)
        self._log("=== Phase 1: Pre-upgrade checks ===")
        success, error = phase1_pre_upgrade_checks(
            ssh, self.config, self._log
        )
        if not success:
            self._log(f"Phase 1 failed: {error}", "error")
            self.phase_failed.emit(1, error)
            self.upgrade_finished.emit(False)
            return
        self.phase_completed.emit(1)

        latest = get_latest_version() or self.config.latest_espocrm_version
        if latest:
            self.config.latest_espocrm_version = latest
        self.version_detected.emit(
            self.config.current_espocrm_version or "",
            self.config.latest_espocrm_version or "",
        )
        save_deploy_config(
            self.instances_dir, self.profile.slug, self.config
        )

        self.phase_started.emit(2)
        self._log("=== Phase 2: Backup ===")
        success, error = phase2_backup(ssh, self.config, self._log)
        if not success:
            self._log(f"Phase 2 failed: {error}", "error")
            self.phase_failed.emit(2, error)
            self.upgrade_finished.emit(False)
            return
        self.phase_completed.emit(2)
        save_deploy_config(
            self.instances_dir, self.profile.slug, self.config
        )

        self.phase_started.emit(3)
        self._log("=== Phase 3: Run upgrade ===")
        success, error = phase3_run_upgrade(ssh, self.config, self._log)
        if not success:
            self._log(f"Phase 3 failed: {error}", "error")
            self.phase_failed.emit(3, error)
            self.upgrade_finished.emit(False)
            return
        self.phase_completed.emit(3)
        save_deploy_config(
            self.instances_dir, self.profile.slug, self.config
        )

        self.phase_started.emit(4)
        self._log("=== Phase 4: Verification ===")
        overall, results = phase4_verify_upgrade(
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
            self.upgrade_finished.emit(False)
            return

        self._log("")
        self._log("=== Upgrade complete ===")
        self.upgrade_finished.emit(True)


class VersionCheckWorker(QThread):
    """Background worker that detects current + latest EspoCRM versions.

    Runs each time the Deploy panel is shown for a deployed instance.
    Emits both versions so the UI can render an "upgrade available" badge.

    :param config: Deployment configuration.
    :param parent: Parent QObject.
    """

    versions_detected = Signal(str, str)  # current, latest

    def __init__(self, config: DeployConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config

    def run(self) -> None:
        """Look up current (via SSH) and latest (via release feed) versions."""
        latest = get_latest_version() or ""

        current = ""
        try:
            ssh = connect_ssh(
                self.config.droplet_ip,
                self.config.ssh_user,
                self.config.ssh_key_path,
            )
        except Exception:
            self.versions_detected.emit(
                self.config.current_espocrm_version or "", latest
            )
            return

        try:
            detected = get_current_version(ssh)
            current = detected or self.config.current_espocrm_version or ""
        finally:
            ssh.close()

        self.versions_detected.emit(current, latest)
