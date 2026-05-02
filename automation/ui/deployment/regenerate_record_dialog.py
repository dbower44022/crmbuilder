"""Modal dialog that regenerates the Deployment Record for an instance.

Three modes, transitioned in order: Setup → Running → Done.

Setup:
    Form with the administrator-supplied inputs (registrar, DNS provider,
    Droplet ID, backups checkbox, three Proton Pass entry names). Output
    file section shows the canonical target path and offers an
    overwrite-vs-versioned-copy choice.

Running:
    Form is hidden. Log area streams the SSH inspection and generation
    progress. Cancel is disabled — paramiko's blocking I/O can't be
    interrupted gracefully in v1.0; the user closes the dialog after
    the worker finishes.

Done:
    Log remains visible. Buttons swap to Close + Reveal in file manager.

See deployment-record series Prompt C for the full specification.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.record_generator import (
    AdministratorInputs,
    increment_minor_version,
)
from automation.ui.deployment.deployment_logic import InstanceDetail

logger = logging.getLogger(__name__)


LOG_COLORS: dict[str, str] = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
}

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 8px 18px; font-size: 13px; } "
    "QPushButton:hover { background-color: #0D47A1; } "
    "QPushButton:disabled { background-color: #888; color: #ddd; }"
)


def default_proton_pass_entry(
    instance_code: str, environment: str, suffix: str,
) -> str:
    """Return the templated Proton Pass entry name for an instance.

    Mirrors the Prompt B wizard defaults so manual regeneration
    pre-fills the same way: ``{CODE}-ESPOCRM-{Env} {suffix}``.

    :param instance_code: Instance code (e.g. ``"CBMTEST"``).
    :param environment: Environment string (``"test"``,
        ``"production"``, ...). Capitalized in the output.
    :param suffix: The trailing descriptor (e.g.
        ``"Instance Admin"``, ``"DB Root"``,
        ``"DigitalOcean Account"``).
    """
    env = (environment or "").strip()
    env_label = env.capitalize() if env else ""
    code = (instance_code or "").upper()
    if env_label:
        return f"{code}-ESPOCRM-{env_label} {suffix}"
    return f"{code}-ESPOCRM {suffix}"


def resolve_output_path(
    project_folder: Path | str, instance_code: str, *, versioned: bool,
) -> Path:
    """Resolve where the generated ``.docx`` should be written.

    :param project_folder: Client project folder (absolute path).
    :param instance_code: Instance code; used as filename disambiguator.
    :param versioned: If True, append a ``-YYYY-MM-DD-HHMMSS`` suffix
        before the extension so the canonical file is preserved.
    :returns: Absolute path. Parent directory is created.
    """
    base_dir = Path(project_folder) / "PRDs" / "deployment"
    base_dir.mkdir(parents=True, exist_ok=True)
    if versioned:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
        return (
            base_dir
            / f"{instance_code}-Instance-Deployment-Record-{timestamp}.docx"
        )
    return base_dir / f"{instance_code}-Instance-Deployment-Record.docx"


class RegenerateRecordDialog(QDialog):
    """Modal dialog for manual Deployment Record regeneration.

    :param instance: The InstanceDetail row.
    :param deploy_config: The InstanceDeployConfig row (with persisted
        administrator-input columns from Prompt B).
    :param project_folder: Client project folder (absolute path).
    :param db_path: Path to the per-client SQLite database; passed to
        the worker so it can persist updated administrator inputs.
    :param client_name: Human-readable client name from the master
        ``Client`` table; passed through to the generator so the
        rendered document title shows the client's display name.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        instance: InstanceDetail,
        deploy_config: InstanceDeployConfig,
        project_folder: str,
        db_path: str,
        client_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._instance = instance
        self._deploy_config = deploy_config
        self._project_folder = project_folder
        self._db_path = db_path
        self._client_name = client_name
        self._worker = None
        self._generated_path: Path | None = None

        self.setWindowTitle(f"Regenerate Deployment Record — {instance.name}")
        self.setModal(True)
        self.resize(720, 720)

        self._build_ui()
        self._enter_setup_mode()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel(
            "<b>Regenerate Deployment Record</b><br/>"
            f"<span style='color:#555; font-size:11px;'>"
            f"Instance: {self._instance.name} "
            f"({self._instance.code}, {self._instance.environment})"
            "</span>"
        )
        header.setTextFormat(header.textFormat())
        layout.addWidget(header)

        self._form_group = self._build_form_group()
        layout.addWidget(self._form_group)

        self._output_group = self._build_output_group()
        layout.addWidget(self._output_group)

        self._log_label = QLabel("<b>Log</b>")
        layout.addWidget(self._log_label)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QFont("Monospace", 10))
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._reveal_btn = QPushButton("Reveal in File Manager")
        self._reveal_btn.clicked.connect(self._on_reveal)
        btn_row.addWidget(self._reveal_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setStyleSheet(_PRIMARY_STYLE)
        self._generate_btn.clicked.connect(self._on_generate)
        btn_row.addWidget(self._generate_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    def _build_form_group(self) -> QGroupBox:
        group = QGroupBox("Documentation Inputs")
        form = QFormLayout(group)

        cfg = self._deploy_config

        self._registrar_edit = QLineEdit(cfg.domain_registrar or "Porkbun")
        form.addRow("Domain Registrar:", self._registrar_edit)

        self._dns_provider_edit = QLineEdit(
            cfg.dns_provider or cfg.domain_registrar or "Porkbun"
        )
        form.addRow("DNS Provider:", self._dns_provider_edit)

        self._droplet_id_edit = QLineEdit(cfg.droplet_id or "")
        self._droplet_id_edit.setPlaceholderText("e.g., 123456789 (optional)")
        form.addRow("Droplet ID:", self._droplet_id_edit)

        self._backups_check = QCheckBox("Weekly backups enabled")
        if cfg.backups_enabled:
            self._backups_check.setChecked(True)
        form.addRow("Backups:", self._backups_check)

        code = self._instance.code
        env = self._instance.environment
        # Persisted values from prior regenerations win over the
        # templated defaults so the operator never re-edits the same
        # three names twice (deployment-record-I FU-1).
        self._proton_admin_edit = QLineEdit(
            cfg.proton_pass_admin_entry
            or default_proton_pass_entry(code, env, "Instance Admin")
        )
        form.addRow("Admin Proton Pass Entry:", self._proton_admin_edit)

        self._proton_db_root_edit = QLineEdit(
            cfg.proton_pass_db_root_entry
            or default_proton_pass_entry(code, env, "DB Root")
        )
        form.addRow("DB Root Proton Pass Entry:", self._proton_db_root_edit)

        self._proton_hosting_edit = QLineEdit(
            cfg.proton_pass_hosting_entry
            or default_proton_pass_entry(code, env, "DigitalOcean Account")
        )
        form.addRow(
            "Hosting Proton Pass Entry:", self._proton_hosting_edit,
        )

        for edit in (
            self._registrar_edit, self._dns_provider_edit,
            self._proton_admin_edit, self._proton_db_root_edit,
            self._proton_hosting_edit,
        ):
            edit.textChanged.connect(self._update_generate_button_state)

        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output File")
        layout = QVBoxLayout(group)

        target = resolve_output_path(
            self._project_folder, self._instance.code, versioned=False,
        )
        self._target_label = QLabel(f"<code>{target}</code>")
        self._target_label.setWordWrap(True)
        self._target_label.setTextFormat(self._target_label.textFormat())
        layout.addWidget(self._target_label)

        if target.exists():
            mtime = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC)
            existing = QLabel(
                "Existing file last modified: "
                f"{mtime.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            existing.setStyleSheet("color: #555; font-size: 11px;")
            layout.addWidget(existing)

        self._overwrite_radio = QRadioButton("Overwrite (default)")
        self._overwrite_radio.setChecked(True)
        layout.addWidget(self._overwrite_radio)

        self._versioned_radio = QRadioButton(
            "Write versioned copy with timestamp suffix"
        )
        layout.addWidget(self._versioned_radio)

        return group

    # ── Mode management ───────────────────────────────────────────

    def _enter_setup_mode(self) -> None:
        self._form_group.setVisible(True)
        self._output_group.setVisible(True)
        self._log_label.setVisible(False)
        self._log_edit.setVisible(False)
        self._cancel_btn.setVisible(True)
        self._generate_btn.setVisible(True)
        self._close_btn.setVisible(False)
        self._reveal_btn.setVisible(False)
        self._update_generate_button_state()

    def _enter_running_mode(self) -> None:
        self._form_group.setVisible(False)
        self._output_group.setVisible(False)
        self._log_label.setVisible(True)
        self._log_edit.setVisible(True)
        self._cancel_btn.setVisible(False)
        self._generate_btn.setVisible(False)
        self._close_btn.setVisible(False)
        self._reveal_btn.setVisible(False)

    def _enter_done_mode(self, *, success: bool) -> None:
        self._form_group.setVisible(False)
        self._output_group.setVisible(False)
        self._log_label.setVisible(True)
        self._log_edit.setVisible(True)
        self._cancel_btn.setVisible(False)
        self._generate_btn.setVisible(False)
        self._close_btn.setVisible(True)
        self._reveal_btn.setVisible(success and self._generated_path is not None)

    def _update_generate_button_state(self) -> None:
        ready = all(
            edit.text().strip() for edit in (
                self._registrar_edit,
                self._dns_provider_edit,
                self._proton_admin_edit,
                self._proton_db_root_edit,
                self._proton_hosting_edit,
            )
        )
        self._generate_btn.setEnabled(ready)

    # ── Generate flow ─────────────────────────────────────────────

    def _on_generate(self) -> None:
        droplet_id = self._droplet_id_edit.text().strip() or None
        if droplet_id and not droplet_id.isdigit():
            QMessageBox.warning(
                self,
                "Invalid Droplet ID",
                "Droplet ID must contain digits only (or be left blank).",
            )
            return

        primary_domain, instance_subdomain = _split_domain(
            self._deploy_config.domain
        )

        next_version = increment_minor_version(
            self._deploy_config.last_record_version
        )

        administrator_inputs = AdministratorInputs(
            domain_registrar=self._registrar_edit.text().strip(),
            dns_provider=self._dns_provider_edit.text().strip(),
            primary_domain=primary_domain,
            instance_subdomain=instance_subdomain,
            droplet_id=droplet_id,
            backups_enabled=self._backups_check.isChecked(),
            proton_pass_admin_entry=self._proton_admin_edit.text().strip(),
            proton_pass_db_root_entry=self._proton_db_root_edit.text().strip(),
            proton_pass_hosting_entry=self._proton_hosting_edit.text().strip(),
            document_version=next_version,
        )

        overwrite_canonical = not self._versioned_radio.isChecked()
        output_path = resolve_output_path(
            self._project_folder,
            self._instance.code,
            versioned=not overwrite_canonical,
        )

        from automation.ui.deployment.regenerate_record_worker import (
            RegenerateRecordWorker,
        )

        self._enter_running_mode()
        self._worker = RegenerateRecordWorker(
            instance=self._instance,
            deploy_config=self._deploy_config,
            administrator_inputs=administrator_inputs,
            output_path=output_path,
            db_path=self._db_path,
            client_name=self._client_name,
            overwrite_canonical=overwrite_canonical,
            parent=self,
        )
        self._worker.log_line.connect(self.append_log)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_completed(self, output_path: str) -> None:
        self._generated_path = Path(output_path)
        self.append_log(
            f"Deployment Record written to {output_path}", "info",
        )
        self._enter_done_mode(success=True)

    def _on_failed(self, error: str) -> None:
        self._generated_path = None
        self.append_log(f"Generation failed: {error}", "error")
        self._enter_done_mode(success=False)

    def _on_reveal(self) -> None:
        if self._generated_path is None:
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._generated_path.parent))
        )

    # ── Log ───────────────────────────────────────────────────────

    def append_log(self, message: str, level: str = "info") -> None:
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(LOG_COLORS.get(level, LOG_COLORS["info"])))
        fmt.setFont(QFont("Monospace", 10))

        if not self._log_edit.document().isEmpty():
            cursor.insertText("\n", fmt)
        cursor.insertText(message, fmt)

        self._log_edit.setTextCursor(cursor)
        self._log_edit.ensureCursorVisible()


def launch_regeneration_dialog(
    parent: QWidget | None,
    instance: InstanceDetail,
    deploy_config: InstanceDeployConfig,
    project_folder: str,
    db_path: str,
    client_name: str,
) -> None:
    """Open the regeneration dialog modal.

    Provided as a programmatic entry point so that, for example, the
    Prompt B Result page's "Generate manually" button can launch the
    same flow without going through the Deployment tab UI.

    :param parent: Parent widget (may be None).
    :param instance: The InstanceDetail row.
    :param deploy_config: The InstanceDeployConfig row.
    :param project_folder: Client project folder (absolute path).
    :param db_path: Path to the per-client SQLite database.
    :param client_name: Human-readable client name from the master
        ``Client`` table.
    """
    dialog = RegenerateRecordDialog(
        instance=instance,
        deploy_config=deploy_config,
        project_folder=project_folder,
        db_path=db_path,
        client_name=client_name,
        parent=parent,
    )
    dialog.exec()


def _split_domain(domain: str) -> tuple[str, str]:
    """Split a fully-qualified hostname into (primary_domain, subdomain).

    Examples:

    * ``crm.example.com`` → ``("example.com", "crm")``
    * ``foo.bar.example.co.uk`` → ``("bar.example.co.uk", "foo")`` —
      the first label is treated as the subdomain. This is heuristic
      but is what the Deployment Record uses; the administrator can
      edit the resulting fields manually if the split is wrong.
    * ``example.com`` → ``("example.com", "")``
    """
    parts = (domain or "").strip().split(".")
    if len(parts) <= 2:
        return (domain or "", "")
    return (".".join(parts[1:]), parts[0])
