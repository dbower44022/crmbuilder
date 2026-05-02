"""Background worker for manual Deployment Record regeneration.

Opens a fresh SSH connection using the persisted ``InstanceDeployConfig``,
runs :func:`inspect_server_for_record_values` to gather live on-server
values, then writes a Deployment Record ``.docx`` at the requested path.

Used by :class:`RegenerateRecordDialog` and by the programmatic
``launch_regeneration_dialog`` entry point. See deployment-record series
Prompt C for the full specification.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from automation.core.deployment.deploy_config_repo import (
    InstanceDeployConfig,
    save_deploy_config,
)
from automation.core.deployment.record_generator import (
    AdministratorInputs,
    generate_deployment_record,
    inspect_server_for_record_values,
)
from automation.core.deployment.ssh_deploy import SelfHostedConfig, connect_ssh
from automation.ui.deployment.deployment_logic import InstanceDetail

logger = logging.getLogger(__name__)


class RegenerateRecordWorker(QThread):
    """Run SSH inspection + Deployment Record generation off the UI thread.

    :param instance: The InstanceDetail row.
    :param deploy_config: The InstanceDeployConfig row (with persisted
        administrator-input columns from Prompt B).
    :param administrator_inputs: Updated administrator inputs from the
        dialog (may differ from the persisted values if the
        administrator edited them).
    :param output_path: Absolute path where the ``.docx`` should be
        written. Parent directory will be created if it does not exist.
    :param db_path: Path to the per-client SQLite database; used to
        write back any changed administrator-input columns.
    :param client_name: The human-readable client name (e.g.,
        "Cleveland Business Mentors") looked up by the caller from
        the master ``Client`` table. Distinct from
        ``instance.name``, which is the technical instance label
        (e.g., "CBMTEST"); the rendered Deployment Record's title
        and metadata block use this value.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        instance: InstanceDetail,
        deploy_config: InstanceDeployConfig,
        administrator_inputs: AdministratorInputs,
        output_path: Path,
        db_path: str,
        client_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._instance = instance
        self._deploy_config = deploy_config
        self._administrator_inputs = administrator_inputs
        self._output_path = Path(output_path)
        self._db_path = db_path
        self._client_name = client_name

    def _log(self, message: str, level: str = "info") -> None:
        self.log_line.emit(message, level)

    def run(self) -> None:
        try:
            self._persist_administrator_inputs_if_changed()
        except Exception as exc:
            self._log(
                f"Could not persist administrator inputs: {exc}", "warning"
            )

        try:
            self._log("Connecting via SSH...", "info")
            ssh = self._open_ssh()
        except Exception as exc:
            self._log(f"SSH connection failed: {exc}", "error")
            self.failed.emit(str(exc))
            return

        try:
            self._log("Inspecting server...", "info")
            try:
                values = inspect_server_for_record_values(
                    ssh,
                    self._instance,
                    self._deploy_config,
                    self._administrator_inputs,
                    client_name=self._client_name,
                )
            except Exception as exc:
                self._log(f"Server inspection failed: {exc}", "error")
                self.failed.emit(str(exc))
                return

            self._log(
                f"Generating Deployment Record at {self._output_path}...",
                "info",
            )
            try:
                generate_deployment_record(values, self._output_path)
            except Exception as exc:
                self._log(f"Generation failed: {exc}", "error")
                self.failed.emit(str(exc))
                return

            self._log("Done.", "info")
            self.completed.emit(str(self._output_path))
        finally:
            try:
                ssh.close()
            except Exception:
                pass

    # ── Helpers ───────────────────────────────────────────────────

    def _open_ssh(self):
        """Build a SelfHostedConfig and open an SSH connection."""
        ssh_config = SelfHostedConfig(
            ssh_host=self._deploy_config.ssh_host,
            ssh_port=self._deploy_config.ssh_port,
            ssh_username=self._deploy_config.ssh_username,
            ssh_credential=self._deploy_config.ssh_credential,
            ssh_auth_type=self._deploy_config.ssh_auth_type,
            domain=self._deploy_config.domain,
            letsencrypt_email=self._deploy_config.letsencrypt_email,
            db_password="",
            db_root_password=self._deploy_config.db_root_password,
            admin_username=self._instance.username or "admin",
            admin_password=self._instance.password or "",
            admin_email=self._deploy_config.admin_email or "",
        )
        return connect_ssh(ssh_config)

    def _persist_administrator_inputs_if_changed(self) -> None:
        """Write back administrator-input columns when they differ.

        Only the four persistable columns (``domain_registrar``,
        ``dns_provider``, ``droplet_id``, ``backups_enabled``) are
        compared and written; the Proton Pass entry names are
        intentionally not persisted.
        """
        cfg = self._deploy_config
        ai = self._administrator_inputs

        backups_enabled = bool(ai.backups_enabled)
        droplet_id = ai.droplet_id or None
        registrar = ai.domain_registrar or None
        dns_provider = ai.dns_provider or None

        unchanged = (
            cfg.domain_registrar == registrar
            and cfg.dns_provider == dns_provider
            and cfg.droplet_id == droplet_id
            and cfg.backups_enabled == backups_enabled
        )
        if unchanged:
            return

        cfg.domain_registrar = registrar
        cfg.dns_provider = dns_provider
        cfg.droplet_id = droplet_id
        cfg.backups_enabled = backups_enabled

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            save_deploy_config(conn, cfg)
        finally:
            conn.close()
