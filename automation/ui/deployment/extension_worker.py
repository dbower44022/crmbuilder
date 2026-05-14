"""Background worker for the extension install flow.

Runs ``install_extension`` off the main thread, streaming phase events
as Qt signals and persisting the ExtensionInstall row on success.
Modeled on ``UpgradeWorker``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.extension_repo import record_install
from automation.core.deployment.extension_ssh import (
    ExtensionManifest,
    install_extension,
    parse_extension_manifest,
)
from automation.core.deployment.ssh_deploy import connect_ssh


class ExtensionInstallWorker(QThread):
    """Run the four extension-install phases off the main thread.

    Persists an ExtensionInstall row on success, using the manifest's
    ``name`` field as the canonical ``extension_name`` so downstream
    slot enforcement always groups by the EspoCRM display name.

    :param config: Hydrated InstanceDeployConfig (mutated as phases run).
    :param db_path: Path to the per-client database file.
    :param zip_path: Local path to the extension zip.
    :param license_id: License row id to attribute the install to,
        or None for unlicensed extensions.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)          # (message, level)
    phase_started = Signal(int)          # phase 1-4
    phase_completed = Signal(int)
    phase_failed = Signal(int, str)
    manifest_parsed = Signal(object)     # ExtensionManifest
    install_finished = Signal(bool)

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        zip_path: str | Path,
        license_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path
        self.zip_path = Path(zip_path)
        self.license_id = license_id
        self._manifest: ExtensionManifest | None = None

    # ── Logging callback adapter ──────────────────────────────────

    def _log(self, message: str, level: str = "info") -> None:
        # Surface phase progress to the UI by sniffing the phase markers
        # emitted by install_extension's headers.
        stripped = message.strip()
        if stripped.startswith("=== Phase 1"):
            self.phase_started.emit(1)
        elif stripped.startswith("=== Phase 2: Backup ==="):
            self.phase_started.emit(2)
        elif stripped.startswith("=== Phase 2: Backup skipped"):
            # Backup intentionally skipped — mark the card completed so
            # the UI doesn't show it stuck in 'not started'.
            self.phase_completed.emit(2)
        elif stripped.startswith("=== Phase 3"):
            self.phase_started.emit(3)
        elif stripped.startswith("=== Phase 4"):
            self.phase_started.emit(4)
        self.log_line.emit(message, level)

    # ── Run ───────────────────────────────────────────────────────

    def run(self) -> None:
        # Parse the manifest first so the UI can show the extension
        # name even if the SSH connection fails.
        try:
            self._manifest = parse_extension_manifest(self.zip_path)
            self.manifest_parsed.emit(self._manifest)
        except (FileNotFoundError, ValueError) as exc:
            self._log(f"Could not read manifest: {exc}", "error")
            self.install_finished.emit(False)
            return

        try:
            self._log("Connecting via SSH...", "info")
            ssh = connect_ssh(self.config)
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.install_finished.emit(False)
            return

        try:
            result = install_extension(
                ssh, self.config, self.zip_path, self._log,
            )
        finally:
            ssh.close()

        if not result.success:
            if result.failed_phase and result.failed_phase >= 1:
                self.phase_failed.emit(result.failed_phase, result.error)
            self.install_finished.emit(False)
            return

        # Phase 4 ran to completion — mark the card explicitly. Phase 1
        # and 3 cards are marked at the start; their completion happens
        # implicitly when the next phase header arrives, so emit them
        # here too for the success path.
        self.phase_completed.emit(1)
        if result.backup_paths:
            self.phase_completed.emit(2)
        self.phase_completed.emit(3)
        self.phase_completed.emit(4)

        manifest = result.manifest
        if manifest is None:
            # Defensive: install succeeded but no manifest came back.
            self.install_finished.emit(True)
            return

        self._record_install(manifest)
        self.install_finished.emit(True)

    # ── Persistence ───────────────────────────────────────────────

    def _record_install(self, manifest: ExtensionManifest) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                record_install(
                    conn,
                    instance_id=self.config.instance_id,
                    extension_name=manifest.name,
                    extension_version=manifest.version,
                    license_id=self.license_id,
                    source_zip_path=str(self.zip_path),
                )
            finally:
                conn.close()
        except Exception as exc:
            self._log(
                f"Could not persist install record: {exc}", "warning",
            )
