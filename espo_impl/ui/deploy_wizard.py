"""Six-step Setup Wizard for deployment configuration."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.deploy_manager import save_deploy_config
from espo_impl.core.models import DeployConfig, InstanceProfile


class DeployWizard(QDialog):
    """Six-step modal wizard for deployment configuration.

    :param profile: Instance profile (for slug and instances_dir).
    :param instances_dir: Path to instances directory.
    :param existing_config: Existing config to pre-populate (edit mode).
    :param parent: Parent widget.
    """

    config_saved = Signal(object)

    def __init__(
        self,
        profile: InstanceProfile,
        instances_dir: Path,
        existing_config: DeployConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._instances_dir = instances_dir
        self._existing = existing_config
        self._build_ui()
        if existing_config:
            self._populate_from_config(existing_config)

    def _build_ui(self) -> None:
        """Build the wizard UI."""
        self.setWindowTitle("Set Up Deployment")
        self.setMinimumSize(550, 400)

        layout = QVBoxLayout(self)

        # Step indicator
        self._step_label = QLabel()
        self._step_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._step_label)

        # Stacked widget
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        # Build steps
        self._build_step1()
        self._build_step2()
        self._build_step3()
        self._build_step4()
        self._build_step5()
        self._build_step6()

        # Navigation
        nav = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._on_back)
        nav.addWidget(self._back_btn)

        nav.addStretch()

        self._next_btn = QPushButton("Next")
        self._next_btn.clicked.connect(self._on_next)
        nav.addWidget(self._next_btn)

        self._save_btn = QPushButton("Save && Deploy")
        self._save_btn.clicked.connect(self._on_save)
        nav.addWidget(self._save_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        nav.addWidget(self._cancel_btn)

        layout.addLayout(nav)

        self._update_nav()

    # ── Step builders ──────────────────────────────────────────────

    def _build_step1(self) -> None:
        """Step 1 — Server Connection."""
        w = QWidget()
        form = QFormLayout(w)

        self._ip_input = QLineEdit()
        self._ip_input.setPlaceholderText("e.g., 165.232.150.42")
        form.addRow("Droplet IP:", self._ip_input)

        key_layout = QHBoxLayout()
        self._ssh_key_input = QLineEdit()
        self._ssh_key_input.setPlaceholderText("~/.ssh/id_ed25519")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse_ssh_key)
        key_layout.addWidget(self._ssh_key_input)
        key_layout.addWidget(browse_btn)
        form.addRow("SSH Key File:", key_layout)

        self._ssh_user_input = QLineEdit()
        self._ssh_user_input.setText("root")
        form.addRow("SSH Username:", self._ssh_user_input)

        self._stack.addWidget(w)

    def _build_step2(self) -> None:
        """Step 2 — Domain."""
        w = QWidget()
        form = QFormLayout(w)

        self._base_domain_input = QLineEdit()
        self._base_domain_input.setPlaceholderText("mycompany.com")
        self._base_domain_input.textChanged.connect(self._update_domain_preview)
        form.addRow("Base Domain:", self._base_domain_input)

        self._subdomain_input = QLineEdit()
        self._subdomain_input.setText("crm")
        self._subdomain_input.textChanged.connect(self._update_domain_preview)
        form.addRow("Subdomain:", self._subdomain_input)

        self._domain_preview = QLabel("")
        self._domain_preview.setStyleSheet(
            "font-weight: bold; color: #4CAF50; padding: 4px;"
        )
        form.addRow("Full Domain:", self._domain_preview)

        self._stack.addWidget(w)

    def _build_step3(self) -> None:
        """Step 3 — Database."""
        w = QWidget()
        form = QFormLayout(w)

        self._db_password_input = QLineEdit()
        self._db_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("EspoCRM DB Password:", self._db_password_input)

        self._db_root_password_input = QLineEdit()
        self._db_root_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._db_root_password_input.setPlaceholderText(
            "Leave blank to auto-generate"
        )
        form.addRow("MariaDB Root Password:", self._db_root_password_input)

        self._stack.addWidget(w)

    def _build_step4(self) -> None:
        """Step 4 — EspoCRM Admin."""
        w = QWidget()
        form = QFormLayout(w)

        self._admin_username_input = QLineEdit()
        self._admin_username_input.setText("admin")
        form.addRow("Admin Username:", self._admin_username_input)

        self._admin_password_input = QLineEdit()
        self._admin_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Admin Password:", self._admin_password_input)

        self._admin_email_input = QLineEdit()
        form.addRow("Admin Email:", self._admin_email_input)

        self._stack.addWidget(w)

    def _build_step5(self) -> None:
        """Step 5 — SSL / Let's Encrypt."""
        w = QWidget()
        form = QFormLayout(w)

        self._le_email_input = QLineEdit()
        form.addRow("Let's Encrypt Email:", self._le_email_input)

        hint = QLabel("Used for certificate expiry notifications from Let's Encrypt.")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow("", hint)

        self._stack.addWidget(w)

    def _build_step6(self) -> None:
        """Step 6 — Review & Confirm."""
        w = QWidget()
        layout = QVBoxLayout(w)

        self._review_text = QTextEdit()
        self._review_text.setReadOnly(True)
        layout.addWidget(self._review_text)

        self._show_passwords_btn = QPushButton("Show Passwords")
        self._show_passwords_btn.setCheckable(True)
        self._show_passwords_btn.toggled.connect(self._refresh_review)
        layout.addWidget(self._show_passwords_btn)

        self._stack.addWidget(w)

    # ── Helpers ────────────────────────────────────────────────────

    def _on_browse_ssh_key(self) -> None:
        """Open file picker for SSH key."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Private Key",
            str(Path.home() / ".ssh"),
        )
        if path:
            self._ssh_key_input.setText(path)

    def _update_domain_preview(self) -> None:
        """Update the full domain preview label."""
        sub = self._subdomain_input.text().strip()
        base = self._base_domain_input.text().strip()
        if sub and base:
            self._domain_preview.setText(f"{sub}.{base}")
        else:
            self._domain_preview.setText("")

    def _populate_from_config(self, config: DeployConfig) -> None:
        """Pre-populate all fields from an existing config."""
        self._ip_input.setText(config.droplet_ip)
        self._ssh_key_input.setText(config.ssh_key_path)
        self._ssh_user_input.setText(config.ssh_user)
        self._base_domain_input.setText(config.base_domain)
        self._subdomain_input.setText(config.subdomain)
        self._db_password_input.setText(config.db_password)
        self._db_root_password_input.setText(config.db_root_password)
        self._admin_username_input.setText(config.admin_username)
        self._admin_password_input.setText(config.admin_password)
        self._admin_email_input.setText(config.admin_email)
        self._le_email_input.setText(config.letsencrypt_email)

    def _refresh_review(self) -> None:
        """Refresh the review summary text."""
        show = self._show_passwords_btn.isChecked()

        def mask(v: str) -> str:
            return v if show else "\u2022" * 8

        lines = [
            f"Server:      {self._ip_input.text().strip()}",
            f"SSH Key:     {self._ssh_key_input.text().strip()}",
            f"SSH User:    {self._ssh_user_input.text().strip()}",
            "",
            f"Domain:      {self._subdomain_input.text().strip()}"
            f".{self._base_domain_input.text().strip()}",
            "",
            f"DB Password:      {mask(self._db_password_input.text())}",
            f"DB Root Password: {mask(self._db_root_password_input.text())}",
            "",
            f"Admin Username:   {self._admin_username_input.text().strip()}",
            f"Admin Password:   {mask(self._admin_password_input.text())}",
            f"Admin Email:      {self._admin_email_input.text().strip()}",
            "",
            f"Let's Encrypt:    {self._le_email_input.text().strip()}",
        ]
        self._review_text.setPlainText("\n".join(lines))

    def _build_config(self) -> DeployConfig:
        """Build a DeployConfig from the wizard inputs."""
        import secrets

        db_root = self._db_root_password_input.text().strip()
        if not db_root:
            db_root = secrets.token_urlsafe(16)

        return DeployConfig(
            droplet_ip=self._ip_input.text().strip(),
            ssh_key_path=self._ssh_key_input.text().strip(),
            ssh_user=self._ssh_user_input.text().strip(),
            base_domain=self._base_domain_input.text().strip(),
            subdomain=self._subdomain_input.text().strip(),
            letsencrypt_email=self._le_email_input.text().strip(),
            db_password=self._db_password_input.text().strip(),
            db_root_password=db_root,
            admin_username=self._admin_username_input.text().strip(),
            admin_password=self._admin_password_input.text().strip(),
            admin_email=self._admin_email_input.text().strip(),
            cert_expiry_date=(
                self._existing.cert_expiry_date if self._existing else None
            ),
            deployed_at=(
                self._existing.deployed_at if self._existing else None
            ),
        )

    # ── Navigation ─────────────────────────────────────────────────

    _STEP_TITLES = [
        "Step 1 of 6 \u2014 Server Connection",
        "Step 2 of 6 \u2014 Domain",
        "Step 3 of 6 \u2014 Database",
        "Step 4 of 6 \u2014 EspoCRM Admin",
        "Step 5 of 6 \u2014 SSL / Let\u2019s Encrypt",
        "Step 6 of 6 \u2014 Review & Confirm",
    ]

    def _update_nav(self) -> None:
        """Update navigation buttons and step label."""
        step = self._stack.currentIndex()
        self._step_label.setText(self._STEP_TITLES[step])
        self._back_btn.setVisible(step > 0)
        self._next_btn.setVisible(step < 5)
        self._save_btn.setVisible(step == 5)

    def _on_back(self) -> None:
        """Go to previous step."""
        step = self._stack.currentIndex()
        if step > 0:
            self._stack.setCurrentIndex(step - 1)
            self._update_nav()

    def _on_next(self) -> None:
        """Go to next step."""
        step = self._stack.currentIndex()
        if step < 5:
            self._stack.setCurrentIndex(step + 1)
            if step + 1 == 5:
                self._refresh_review()
            self._update_nav()

    def _on_save(self) -> None:
        """Validate, save config, emit signal, and close."""
        # Validate required fields
        missing = []
        if not self._ip_input.text().strip():
            missing.append("Droplet IP")
        if not self._ssh_key_input.text().strip():
            missing.append("SSH Key File")
        if not self._base_domain_input.text().strip():
            missing.append("Base Domain")
        if not self._subdomain_input.text().strip():
            missing.append("Subdomain")
        if not self._db_password_input.text().strip():
            missing.append("DB Password")
        if not self._admin_password_input.text().strip():
            missing.append("Admin Password")
        if not self._admin_email_input.text().strip():
            missing.append("Admin Email")
        if not self._le_email_input.text().strip():
            missing.append("Let's Encrypt Email")

        if missing:
            QMessageBox.warning(
                self,
                "Missing Fields",
                "Please fill in:\n\u2022 " + "\n\u2022 ".join(missing),
            )
            return

        config = self._build_config()
        save_deploy_config(
            self._instances_dir, self._profile.slug, config
        )
        self.config_saved.emit(config)
        self.accept()
