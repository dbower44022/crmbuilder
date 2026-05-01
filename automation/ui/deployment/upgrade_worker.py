"""Background workers for the EspoCRM upgrade flow.

``UpgradeWorker`` runs the four upgrade phases off the main thread.
``VersionCheckWorker`` polls current and latest versions for the
Deploy panel's version badge.

Both persist results back to ``InstanceDeployConfig`` via the repo so
the next time the user opens the panel the badge is already correct.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QThread, Signal

from automation.core.deployment.deploy_config_repo import (
    InstanceDeployConfig,
    update_after_upgrade,
    update_version_state,
)
from automation.core.deployment.ssh_deploy import connect_ssh
from automation.core.deployment.upgrade_ssh import (
    get_current_version,
    get_latest_version,
    phase1_pre_upgrade_checks,
    phase2_backup,
    phase3_run_upgrade,
    phase4_verify_upgrade,
)


class UpgradeWorker(QThread):
    """Run upgrade phases off the main thread.

    Persists state after each phase via the repo so a mid-flow failure
    leaves the recorded state consistent with what actually ran.

    :param config: Hydrated InstanceDeployConfig (mutated as phases run).
    :param db_path: Path to the per-client database file.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)              # (message, level)
    phase_started = Signal(int)              # phase 1-4
    phase_completed = Signal(int)
    phase_failed = Signal(int, str)
    version_detected = Signal(str, str)      # (current, latest)
    verify_results = Signal(list)
    upgrade_finished = Signal(bool)

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path

    def _log(self, message: str, level: str = "info") -> None:
        self.log_line.emit(message, level)

    def run(self) -> None:
        try:
            self._log("Connecting via SSH...", "info")
            ssh = connect_ssh(self.config)
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.upgrade_finished.emit(False)
            return

        try:
            self._run_phases(ssh)
        finally:
            ssh.close()

    def _run_phases(self, ssh) -> None:
        # Phase 1
        self.phase_started.emit(1)
        self._log("=== Phase 1: Pre-upgrade checks ===", "info")
        ok, error = phase1_pre_upgrade_checks(ssh, self.config, self._log)
        if not ok:
            self._log(f"Phase 1 failed: {error}", "error")
            self.phase_failed.emit(1, error)
            self.upgrade_finished.emit(False)
            return
        self.phase_completed.emit(1)

        latest = (
            get_latest_version() or self.config.latest_espocrm_version
        )
        if latest:
            self.config.latest_espocrm_version = latest
        self.version_detected.emit(
            self.config.current_espocrm_version or "",
            self.config.latest_espocrm_version or "",
        )
        self._persist_versions()

        # Phase 2
        self.phase_started.emit(2)
        self._log("=== Phase 2: Backup ===", "info")
        ok, error = phase2_backup(ssh, self.config, self._log)
        if not ok:
            self._log(f"Phase 2 failed: {error}", "error")
            self.phase_failed.emit(2, error)
            self.upgrade_finished.emit(False)
            return
        self.phase_completed.emit(2)

        # Phase 3
        self.phase_started.emit(3)
        self._log("=== Phase 3: Run upgrade ===", "info")
        ok, error = phase3_run_upgrade(ssh, self.config, self._log)
        if not ok:
            self._log(f"Phase 3 failed: {error}", "error")
            self.phase_failed.emit(3, error)
            self.upgrade_finished.emit(False)
            return
        self.phase_completed.emit(3)
        self._persist_after_upgrade()

        # Phase 4
        self.phase_started.emit(4)
        self._log("=== Phase 4: Verification ===", "info")
        overall, results = phase4_verify_upgrade(
            ssh, self.config, self._log
        )
        self.verify_results.emit(results)
        if overall:
            self.phase_completed.emit(4)
            self._log("Phase 4: All checks passed", "info")
        else:
            failed = [r["check"] for r in results if not r["passed"]]
            self.phase_failed.emit(
                4, f"Failed checks: {', '.join(failed)}"
            )
            self.upgrade_finished.emit(False)
            return

        self._log("", "info")
        self._log("=== Upgrade complete ===", "info")
        self.upgrade_finished.emit(True)

    def _persist_versions(self) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                update_version_state(
                    conn,
                    self.config.instance_id,
                    current_version=self.config.current_espocrm_version,
                    latest_version=self.config.latest_espocrm_version,
                )
            finally:
                conn.close()
        except Exception as exc:
            self._log(
                f"Could not persist version state: {exc}", "warning"
            )

    def _persist_after_upgrade(self) -> None:
        if not self.config.current_espocrm_version:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                update_after_upgrade(
                    conn,
                    self.config.instance_id,
                    current_version=self.config.current_espocrm_version,
                    last_upgrade_at=self.config.last_upgrade_at or "",
                    last_backup_paths=self.config.last_backup_paths or [],
                )
            finally:
                conn.close()
        except Exception as exc:
            self._log(
                f"Could not persist post-upgrade state: {exc}", "warning"
            )


class VersionCheckWorker(QThread):
    """Poll current and latest EspoCRM versions in the background.

    Runs each time the Deploy panel is shown for a self-hosted instance.
    Emits ``versions_detected(current, latest)`` and persists both into
    ``InstanceDeployConfig``.

    :param config: Hydrated InstanceDeployConfig.
    :param db_path: Path to the per-client database file.
    :param parent: Parent QObject.
    """

    versions_detected = Signal(str, str)   # (current, latest)

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path

    def run(self) -> None:
        latest = get_latest_version() or ""
        current = ""
        try:
            ssh = connect_ssh(self.config)
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
        self._persist(current, latest)

    def _persist(self, current: str, latest: str) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                update_version_state(
                    conn,
                    self.config.instance_id,
                    current_version=current or None,
                    latest_version=latest or None,
                )
            finally:
                conn.close()
        except Exception:
            pass
