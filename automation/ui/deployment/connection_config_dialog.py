"""Backfill dialog for InstanceDeployConfig server-connection details.

Opened the first time a user clicks Upgrade EspoCRM or Recovery & Reset
on an instance that was deployed before the server-management layer
existed (or whose deploy config persistence failed). Captures the same
fields the deploy wizard collects on pages 1-3, writes them through
``deploy_config_repo`` (secrets routed through OS keyring), and
returns the saved config.

The form-validation and save logic is split into pure functions so it
can be unit-tested without instantiating the Qt widget.

See PRDs/product/features/feat-server-management.md §5.2.
"""

from __future__ import annotations

import dataclasses
import logging
import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from automation.core.deployment.deploy_config_repo import (
    InstanceDeployConfig,
    save_deploy_config,
)

logger = logging.getLogger(__name__)


SSH_AUTH_KEY = "key"
SSH_AUTH_PASSWORD = "password"

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


@dataclasses.dataclass
class ConnectionForm:
    """Pure-data view of the dialog's fields, populated on Save click.

    Decoupled from Qt so the validation and save helpers below can be
    unit-tested without spinning up a QApplication.
    """

    ssh_host: str
    ssh_port: int
    ssh_username: str
    ssh_auth_type: str  # 'key' | 'password'
    ssh_credential: str
    domain: str
    letsencrypt_email: str
    db_root_password: str
    admin_email: str = ""


def validate_form(form: ConnectionForm) -> list[str]:
    """Return a list of human-readable validation errors, empty if OK.

    :param form: Fields collected from the dialog.
    :returns: Error messages (one per failed check).
    """
    import re

    errors: list[str] = []

    if not form.ssh_host.strip():
        errors.append("SSH host is required.")
    if form.ssh_port < 1 or form.ssh_port > 65535:
        errors.append("SSH port must be between 1 and 65535.")
    if not form.ssh_username.strip():
        errors.append("SSH username is required.")
    if form.ssh_auth_type not in {SSH_AUTH_KEY, SSH_AUTH_PASSWORD}:
        errors.append("SSH auth type must be 'key' or 'password'.")
    if not form.ssh_credential.strip():
        if form.ssh_auth_type == SSH_AUTH_KEY:
            errors.append("SSH key file path is required.")
        else:
            errors.append("SSH password is required.")
    if form.ssh_auth_type == SSH_AUTH_KEY and form.ssh_credential.strip():
        if not Path(form.ssh_credential.strip()).expanduser().exists():
            errors.append(
                f"SSH key file not found: {form.ssh_credential.strip()}"
            )
    if not form.domain.strip():
        errors.append("Domain is required.")
    if not form.letsencrypt_email.strip():
        errors.append("Let's Encrypt email is required.")
    elif not re.match(EMAIL_PATTERN, form.letsencrypt_email.strip()):
        errors.append("Let's Encrypt email must be a valid email address.")
    if not form.db_root_password.strip():
        errors.append("MariaDB root password is required.")
    if form.admin_email.strip() and not re.match(
        EMAIL_PATTERN, form.admin_email.strip()
    ):
        errors.append("Admin email must be a valid email address.")

    return errors


def save_form(
    conn: sqlite3.Connection,
    instance_id: int,
    form: ConnectionForm,
) -> InstanceDeployConfig:
    """Persist a validated form via deploy_config_repo.

    :param conn: Per-client database connection.
    :param instance_id: ``Instance.id`` to attach the config to.
    :param form: A validated ConnectionForm.
    :returns: The saved ``InstanceDeployConfig`` with refs populated.
    :raises ValueError: If the form fails validation.
    """
    errors = validate_form(form)
    if errors:
        raise ValueError("; ".join(errors))

    config = InstanceDeployConfig(
        instance_id=instance_id,
        scenario="self_hosted",
        ssh_host=form.ssh_host.strip(),
        ssh_port=form.ssh_port,
        ssh_username=form.ssh_username.strip(),
        ssh_auth_type=form.ssh_auth_type,
        ssh_credential=form.ssh_credential.strip(),
        domain=form.domain.strip(),
        letsencrypt_email=form.letsencrypt_email.strip(),
        db_root_password=form.db_root_password.strip(),
        admin_email=form.admin_email.strip() or None,
    )
    return save_deploy_config(conn, config)


class ConnectionConfigDialog(QDialog):
    """Modal dialog that collects server-connection details and saves them.

    :param conn: Per-client database connection.
    :param instance_id: ``Instance.id`` to attach the config to.
    :param instance_name: Human-readable instance name for the title.
    :param prefill: Optional existing config to pre-populate fields with.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        instance_id: int,
        instance_name: str,
        prefill: InstanceDeployConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._instance_id = instance_id
        self._saved_config: InstanceDeployConfig | None = None

        self.setWindowTitle(f"Server Connection — {instance_name}")
        self.setModal(True)
        self.resize(560, 480)

        self._build_ui()
        if prefill is not None:
            self._populate_from(prefill)

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Enter the SSH and server credentials needed to manage this "
            "EspoCRM instance (Upgrade, Recovery, future maintenance "
            "operations). Secrets are stored in your OS keyring."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(intro)

        form = QFormLayout()

        self._ssh_host = QLineEdit()
        self._ssh_host.setPlaceholderText("e.g., 165.232.150.42")
        form.addRow("SSH Host:", self._ssh_host)

        self._ssh_port = QSpinBox()
        self._ssh_port.setRange(1, 65535)
        self._ssh_port.setValue(22)
        form.addRow("SSH Port:", self._ssh_port)

        self._ssh_user = QLineEdit("root")
        form.addRow("SSH Username:", self._ssh_user)

        self._ssh_auth_combo = QComboBox()
        self._ssh_auth_combo.addItems(["SSH key file", "Password"])
        self._ssh_auth_combo.currentIndexChanged.connect(
            self._on_auth_type_changed
        )
        form.addRow("Auth Type:", self._ssh_auth_combo)

        cred_row = QHBoxLayout()
        self._ssh_credential = QLineEdit()
        self._ssh_credential.setPlaceholderText("/home/user/.ssh/id_ed25519")
        cred_row.addWidget(self._ssh_credential)
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.clicked.connect(self._on_browse_key)
        cred_row.addWidget(self._browse_btn)
        cred_widget = QWidget()
        cred_widget.setLayout(cred_row)
        cred_row.setContentsMargins(0, 0, 0, 0)
        form.addRow("SSH Credential:", cred_widget)

        self._domain = QLineEdit()
        self._domain.setPlaceholderText("crm.example.com")
        form.addRow("Domain:", self._domain)

        self._le_email = QLineEdit()
        self._le_email.setPlaceholderText("ops@example.com")
        form.addRow("Let's Encrypt Email:", self._le_email)

        self._db_root = QLineEdit()
        self._db_root.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("MariaDB Root Password:", self._db_root)

        self._admin_email = QLineEdit()
        self._admin_email.setPlaceholderText("admin@example.com (optional)")
        form.addRow("Admin Email:", self._admin_email)

        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_auth_type_changed(self, index: int) -> None:
        is_key = index == 0
        self._browse_btn.setVisible(is_key)
        self._ssh_credential.setEchoMode(
            QLineEdit.EchoMode.Normal
            if is_key
            else QLineEdit.EchoMode.Password
        )
        self._ssh_credential.setPlaceholderText(
            "/home/user/.ssh/id_ed25519" if is_key else ""
        )

    def _on_browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Key File", "", "All Files (*)"
        )
        if path:
            self._ssh_credential.setText(path)

    # ── Form round-trip ───────────────────────────────────────────

    def _populate_from(self, config: InstanceDeployConfig) -> None:
        self._ssh_host.setText(config.ssh_host)
        self._ssh_port.setValue(config.ssh_port)
        self._ssh_user.setText(config.ssh_username)
        self._ssh_auth_combo.setCurrentIndex(
            0 if config.ssh_auth_type == SSH_AUTH_KEY else 1
        )
        self._ssh_credential.setText(config.ssh_credential)
        self._domain.setText(config.domain)
        self._le_email.setText(config.letsencrypt_email)
        self._db_root.setText(config.db_root_password)
        if config.admin_email:
            self._admin_email.setText(config.admin_email)

    def _read_form(self) -> ConnectionForm:
        return ConnectionForm(
            ssh_host=self._ssh_host.text(),
            ssh_port=self._ssh_port.value(),
            ssh_username=self._ssh_user.text(),
            ssh_auth_type=(
                SSH_AUTH_KEY
                if self._ssh_auth_combo.currentIndex() == 0
                else SSH_AUTH_PASSWORD
            ),
            ssh_credential=self._ssh_credential.text(),
            domain=self._domain.text(),
            letsencrypt_email=self._le_email.text(),
            db_root_password=self._db_root.text(),
            admin_email=self._admin_email.text(),
        )

    # ── Save ──────────────────────────────────────────────────────

    def _on_save(self) -> None:
        form = self._read_form()
        errors = validate_form(form)
        if errors:
            QMessageBox.warning(
                self,
                "Invalid Connection Details",
                "\n".join(f"• {e}" for e in errors),
            )
            return

        try:
            self._saved_config = save_form(
                self._conn, self._instance_id, form
            )
        except RuntimeError as exc:
            QMessageBox.critical(
                self,
                "Could Not Save",
                f"Could not save server connection details:\n\n{exc}",
            )
            return
        self.accept()

    @property
    def saved_config(self) -> InstanceDeployConfig | None:
        """The saved config after a successful Save, else None."""
        return self._saved_config
