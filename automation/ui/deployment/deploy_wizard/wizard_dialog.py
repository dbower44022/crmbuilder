"""Deploy Wizard — three-scenario modal dialog (§14.12.5).

Step 1 is shared (scenario + platform selection). Subsequent steps
branch by scenario: self-hosted (7 total steps) or cloud/BYO (4 total).

Every wizard execution writes a DeploymentRun row.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from automation.core.deployment.connectivity import ConnectivityResult
from automation.core.deployment.deploy_config_repo import load_deploy_config
from automation.core.deployment.record_generator import AdministratorInputs
from automation.core.deployment.ssh_deploy import SelfHostedConfig
from automation.core.deployment.wizard_logic import (
    SCENARIO_LABELS,
    SCENARIOS,
    SUPPORTED_PLATFORMS,
    MatchingInstance,
    PreSelection,
    create_wizard_instance,
    finalize_deployment_run,
    find_matching_instances,
    insert_deployment_run,
    update_instance_from_wizard,
)
from automation.ui.deployment.deploy_wizard.deploy_worker import (
    ConnectivityWorker,
    SelfHostedWorker,
)
from automation.ui.deployment.deployment_logic import load_instance_detail
from automation.ui.deployment.regenerate_record_dialog import (
    launch_regeneration_dialog,
)

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)
_SECONDARY_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)


class DeployWizard(QDialog):
    """Three-scenario Deploy Wizard.

    :param conn: Per-client database connection.
    :param pre_selection: Pre-selection from Client columns.
    :param master_db_path: Path to master database.
    :param client_id: Active client ID.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        pre_selection: PreSelection,
        master_db_path: str,
        client_id: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._pre = pre_selection
        self._master_db_path = master_db_path
        self._client_id = client_id
        self._run_id: int | None = None
        self._instance_id: int | None = None
        self._creating_new: bool = True
        self._worker = None
        self._finished = False

        self.setWindowTitle("Deploy Wizard")
        self.setMinimumSize(650, 500)
        self._build_ui()
        self._apply_pre_selection()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._step_label = QLabel()
        self._step_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._step_label)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        # Page 0: Scenario selection
        self._build_scenario_page()
        # Page 1: Self-hosted — server target
        self._build_self_hosted_server_page()
        # Page 2: Self-hosted — domain + deploy (combined)
        self._build_self_hosted_domain_page()
        # Page 3: Self-hosted — admin credentials
        self._build_self_hosted_admin_page()
        # Page 4: Self-hosted — Deployment Record documentation inputs
        self._build_self_hosted_documentation_page()
        # Page 5: Self-hosted — deploy progress
        self._build_self_hosted_progress_page()
        # Page 6: Cloud/BYO — instance details
        self._build_cloud_byo_details_page()
        # Page 7: Cloud/BYO — connectivity progress
        self._build_cloud_byo_progress_page()
        # Page 8: Result page (shared)
        self._build_result_page()

        # Navigation
        nav = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._on_back)
        nav.addWidget(self._back_btn)
        nav.addStretch()
        self._next_btn = QPushButton("Next")
        self._next_btn.setStyleSheet(_PRIMARY_STYLE)
        self._next_btn.clicked.connect(self._on_next)
        nav.addWidget(self._next_btn)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        nav.addWidget(self._cancel_btn)
        layout.addLayout(nav)

        self._stack.setCurrentIndex(0)
        self._update_nav()

    # --- Page 0: Scenario ---

    def _build_scenario_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("Select the deployment scenario and CRM platform:"))

        group = QGroupBox("Scenario")
        g_layout = QVBoxLayout(group)
        self._scenario_radios: dict[str, QRadioButton] = {}
        for scenario in SCENARIOS:
            radio = QRadioButton(SCENARIO_LABELS[scenario])
            self._scenario_radios[scenario] = radio
            g_layout.addWidget(radio)
        layout.addWidget(group)

        platform_layout = QFormLayout()
        self._platform_combo = QComboBox()
        for p in SUPPORTED_PLATFORMS:
            self._platform_combo.addItem(p)
        self._platform_combo.setEnabled(len(SUPPORTED_PLATFORMS) > 1)
        platform_layout.addRow("CRM Platform:", self._platform_combo)
        layout.addLayout(platform_layout)

        layout.addStretch()
        self._stack.addWidget(w)

    # --- Pages 1-4: Self-hosted ---

    def _build_self_hosted_server_page(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self._ssh_host = QLineEdit()
        self._ssh_host.setPlaceholderText("e.g. 104.131.45.208 (Droplet IP)")
        self._ssh_host.setToolTip(
            "The IP address of the DigitalOcean Droplet you "
            "provisioned. Not the application domain (e.g. "
            "crm-test.example.org). For an existing instance being "
            "re-deployed, this value is recorded as \"Public IPv4 "
            "(SSH Host)\" in Section 3.1 of the per-instance "
            "Deployment Record. See Deployment Runbook §4.2 and "
            "§7.3."
        )
        form.addRow(
            "SSH Host:",
            _input_with_helper(
                self._ssh_host, "The Droplet's public IPv4 address."
            ),
        )

        self._ssh_port = QLineEdit()
        self._ssh_port.setText("22")
        self._ssh_port.setPlaceholderText("22")
        self._ssh_port.setToolTip(
            "Default 22. Change only if the Droplet has been "
            "configured to use a non-standard SSH port (uncommon). "
            "See Deployment Runbook §7.3."
        )
        form.addRow(
            "SSH Port:",
            _input_with_helper(self._ssh_port, "The SSH port on the Droplet."),
        )

        self._ssh_user = QLineEdit()
        self._ssh_user.setText("root")
        self._ssh_user.setPlaceholderText("root")
        self._ssh_user.setToolTip(
            "Must be root. The EspoCRM installer requires root "
            "privileges to install Docker and configure the firewall; "
            "non-root users with sudo are not supported in v1.0. See "
            "Deployment Runbook §7.3."
        )
        form.addRow(
            "SSH Username:",
            _input_with_helper(
                self._ssh_user, "The SSH user that will run the install."
            ),
        )

        self._ssh_auth_combo = QComboBox()
        self._ssh_auth_combo.addItems(["SSH Key", "Password"])
        self._ssh_auth_combo.setToolTip(
            "Select SSH Key for key-based authentication "
            "(recommended) or Password for password authentication."
        )
        self._ssh_auth_combo.currentIndexChanged.connect(self._on_ssh_auth_changed)
        form.addRow("Authentication:", self._ssh_auth_combo)

        key_widget = QWidget()
        key_layout = QHBoxLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self._ssh_credential = QLineEdit()
        self._ssh_credential.setPlaceholderText("e.g. ~/.ssh/id_ed25519")
        self._ssh_credential.setToolTip(
            "Click Browse to select the private key file. The "
            "corresponding public key must be installed in "
            "/root/.ssh/authorized_keys on the Droplet. See "
            "Deployment Runbook §5."
        )
        self._ssh_browse_btn = QPushButton("Browse...")
        self._ssh_browse_btn.clicked.connect(self._on_browse_ssh_key)
        key_layout.addWidget(self._ssh_credential)
        key_layout.addWidget(self._ssh_browse_btn)
        form.addRow(
            "Credential:",
            _input_with_helper(
                key_widget, "Path to the SSH private key file."
            ),
        )

        self._stack.addWidget(w)

    def _build_self_hosted_domain_page(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self._sh_domain = QLineEdit()
        self._sh_domain.setPlaceholderText("e.g. crm-test.example.org")
        self._sh_domain.setToolTip(
            "The full subdomain.domain.tld where EspoCRM will be "
            "reachable. Must already have an A record pointing to "
            "the SSH Host IP; the wizard verifies DNS resolution "
            "before proceeding. See Deployment Runbook §6."
        )
        form.addRow(
            "Domain:",
            _input_with_helper(
                self._sh_domain,
                "Fully-qualified domain for this instance.",
            ),
        )

        self._sh_le_email = QLineEdit()
        self._sh_le_email.setPlaceholderText("e.g. admin@example.org")
        self._sh_le_email.setToolTip(
            "A monitored mailbox at your organization. Let's Encrypt "
            "sends warnings here if certificate renewal fails. Use a "
            "real, monitored address."
        )
        form.addRow(
            "Let's Encrypt Email:",
            _input_with_helper(
                self._sh_le_email,
                "Email for certificate expiry notifications.",
            ),
        )

        self._sh_db_password = QLineEdit()
        self._sh_db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._sh_db_password.setToolTip(
            "The password for the EspoCRM application's database "
            "user. Generate a strong password and record it in your "
            "password manager (Proton Pass for CBM). Never reuse a "
            "password from another system."
        )
        form.addRow(
            "DB Password:",
            _input_with_helper(
                self._sh_db_password,
                "The application database user's password.",
            ),
        )

        self._sh_db_root_password = QLineEdit()
        self._sh_db_root_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._sh_db_root_password.setPlaceholderText(
            "Leave blank to auto-generate"
        )
        self._sh_db_root_password.setToolTip(
            "Leave blank for the wizard to auto-generate a strong "
            "random password (recommended). If supplied, must be a "
            "strong password. Either way, this value must be "
            "captured in your password manager during post-deploy "
            "because it is otherwise inaccessible after the deploy "
            "completes. See Deployment Runbook §10.2."
        )
        form.addRow(
            "DB Root Password:",
            _input_with_helper(
                self._sh_db_root_password,
                "MariaDB root password.",
            ),
        )

        self._stack.addWidget(w)

    def _build_self_hosted_admin_page(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self._sh_admin_user = QLineEdit()
        self._sh_admin_user.setText("admin")
        self._sh_admin_user.setPlaceholderText("admin")
        self._sh_admin_user.setToolTip(
            "Convention is \"admin\". Used for first login; can be "
            "changed in EspoCRM after deploy."
        )
        form.addRow(
            "Admin Username:",
            _input_with_helper(
                self._sh_admin_user,
                "The EspoCRM administrator username.",
            ),
        )

        self._sh_admin_pass = QLineEdit()
        self._sh_admin_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._sh_admin_pass.setToolTip(
            "Generate a strong password and record it in your "
            "password manager. Required for first login and all "
            "subsequent admin operations. See Deployment Runbook §10.1."
        )
        form.addRow(
            "Admin Password:",
            _input_with_helper(
                self._sh_admin_pass,
                "The EspoCRM administrator password.",
            ),
        )

        self._sh_admin_email = QLineEdit()
        self._sh_admin_email.setPlaceholderText("e.g. admin@example.org")
        self._sh_admin_email.setToolTip(
            "Becomes the admin user's email in EspoCRM. Used for "
            "password reset and notifications."
        )
        form.addRow(
            "Admin Email:",
            _input_with_helper(
                self._sh_admin_email,
                "Email address for the admin user record.",
            ),
        )

        hint = QLabel(
            "These credentials will be used to create the initial EspoCRM "
            "administrator account and saved to the Instance record."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #757575; font-size: 11px; padding-top: 12px;")
        form.addRow("", hint)

        self._stack.addWidget(w)

    def _build_self_hosted_documentation_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)

        header = QLabel(
            "These values are needed to generate the Deployment Record "
            "document. They are not used by the application itself; "
            "they document where each item is stored or who manages it."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #424242; padding-bottom: 8px;")
        layout.addWidget(header)

        form = QFormLayout()

        self._doc_registrar = QLineEdit()
        self._doc_registrar.setText("Porkbun")
        self._doc_registrar.setPlaceholderText("e.g. Porkbun")
        self._doc_registrar.setToolTip(
            "The DNS registrar / domain provider for the "
            "application's domain. Recorded in the Deployment "
            "Record's Section 4.1 for future reference."
        )
        form.addRow(
            "Domain Registrar:",
            _input_with_helper(
                self._doc_registrar,
                "The registrar where the domain is registered.",
            ),
        )

        self._doc_dns_provider = QLineEdit()
        self._doc_dns_provider.setText("Porkbun")
        self._doc_dns_provider.setPlaceholderText(
            "e.g. Porkbun (defaults to registrar if same)"
        )
        self._doc_dns_provider.setToolTip(
            "Often equals the registrar but may differ if DNS has "
            "been delegated to a third party (e.g. Cloudflare). "
            "Recorded in the Deployment Record's Section 4.1."
        )
        self._doc_registrar.textChanged.connect(self._on_registrar_changed)
        form.addRow(
            "DNS Provider:",
            _input_with_helper(
                self._doc_dns_provider, "Where DNS records are managed."
            ),
        )

        self._doc_droplet_id = QLineEdit()
        self._doc_droplet_id.setPlaceholderText("e.g. 561480073")
        self._doc_droplet_id.setToolTip(
            "Find in the URL when viewing the Droplet in the "
            "DigitalOcean dashboard: "
            "cloud.digitalocean.com/droplets/<DROPLET_ID>. Used to "
            "populate the Deployment Record's Section 3.1 with "
            "direct links to the Droplet detail page and "
            "in-browser Console."
        )
        form.addRow(
            "Droplet ID:",
            _input_with_helper(
                self._doc_droplet_id,
                "The DigitalOcean Droplet's numeric ID.",
            ),
        )

        self._doc_backups_enabled = QCheckBox(
            "DigitalOcean weekly backups are enabled for this Droplet"
        )
        self._doc_backups_enabled.setToolTip(
            "Whether DigitalOcean automated weekly backups are "
            "enabled for this Droplet. Recorded in the Deployment "
            "Record's Section 3.4."
        )
        form.addRow("Backups:", self._doc_backups_enabled)

        self._doc_proton_admin = QLineEdit()
        self._doc_proton_admin.setPlaceholderText(
            "e.g. CBM-ESPOCRM-Test Instance Admin"
        )
        self._doc_proton_admin.setToolTip(
            "The exact name of the password manager entry where the "
            "admin password is stored. The Deployment Record "
            "references credentials by entry name only, never by value."
        )
        form.addRow(
            "Admin Password Proton Pass Entry:",
            _input_with_helper(
                self._doc_proton_admin,
                "Password manager entry name for the admin password.",
            ),
        )

        self._doc_proton_db_root = QLineEdit()
        self._doc_proton_db_root.setPlaceholderText(
            "e.g. ESPOCRM Root DB Password - Test Instance"
        )
        self._doc_proton_db_root.setToolTip(
            "Same convention as the admin password entry."
        )
        form.addRow(
            "DB Root Password Proton Pass Entry:",
            _input_with_helper(
                self._doc_proton_db_root,
                "Password manager entry name for the DB root password.",
            ),
        )

        self._doc_proton_hosting = QLineEdit()
        self._doc_proton_hosting.setPlaceholderText(
            "e.g. DigitalOcean-CRM Hosting - Test Instance"
        )
        self._doc_proton_hosting.setToolTip(
            "The exact name of the password manager entry for the "
            "DigitalOcean (or other hosting provider) account login."
        )
        form.addRow(
            "DigitalOcean Account Proton Pass Entry:",
            _input_with_helper(
                self._doc_proton_hosting,
                "Password manager entry name for the hosting account.",
            ),
        )

        layout.addLayout(form)
        layout.addStretch()
        self._stack.addWidget(w)

    def _build_self_hosted_progress_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._sh_progress_label = QLabel("Deployment in progress...")
        self._sh_progress_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._sh_progress_label)
        self._sh_log = QPlainTextEdit()
        self._sh_log.setReadOnly(True)
        self._sh_log.setStyleSheet(
            "QPlainTextEdit { background-color: #1E1E1E; color: #D4D4D4; "
            "font-family: Monospace; font-size: 10pt; }"
        )
        layout.addWidget(self._sh_log, stretch=1)
        self._stack.addWidget(w)

    # --- Pages 5-6: Cloud/BYO ---

    def _build_cloud_byo_details_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._cloud_help = QLabel()
        self._cloud_help.setWordWrap(True)
        self._cloud_help.setStyleSheet("color: #757575; padding-bottom: 8px;")
        layout.addWidget(self._cloud_help)

        form = QFormLayout()
        self._cloud_url = QLineEdit()
        self._cloud_url.setPlaceholderText("https://mycrm.espocloud.com")
        form.addRow("Instance URL:", self._cloud_url)

        self._cloud_user = QLineEdit()
        self._cloud_user.setText("admin")
        form.addRow("Admin Username:", self._cloud_user)

        self._cloud_pass = QLineEdit()
        self._cloud_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Admin Password:", self._cloud_pass)

        layout.addLayout(form)
        layout.addStretch()
        self._stack.addWidget(w)

    def _build_cloud_byo_progress_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._cloud_progress_label = QLabel("Checking connectivity...")
        self._cloud_progress_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._cloud_progress_label)
        self._cloud_log = QPlainTextEdit()
        self._cloud_log.setReadOnly(True)
        self._cloud_log.setStyleSheet(
            "QPlainTextEdit { background-color: #1E1E1E; color: #D4D4D4; "
            "font-family: Monospace; font-size: 10pt; }"
        )
        layout.addWidget(self._cloud_log, stretch=1)
        self._stack.addWidget(w)

    # --- Page 7: Result ---

    def _build_result_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._result_icon = QLabel()
        self._result_icon.setStyleSheet("font-size: 48px;")
        self._result_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._result_icon)
        self._result_msg = QLabel()
        self._result_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_msg.setWordWrap(True)
        self._result_msg.setStyleSheet("font-size: 14px; padding: 16px;")
        layout.addWidget(self._result_msg)

        self._record_panel = QWidget()
        record_layout = QVBoxLayout(self._record_panel)
        record_layout.setContentsMargins(20, 8, 20, 8)
        self._record_heading = QLabel("Deployment Record")
        self._record_heading.setStyleSheet(
            "font-weight: bold; font-size: 13px;"
        )
        record_layout.addWidget(self._record_heading)
        self._record_status = QLabel()
        self._record_status.setWordWrap(True)
        self._record_status.setStyleSheet(
            "font-size: 12px; padding: 4px 0;"
        )
        record_layout.addWidget(self._record_status)
        record_btn_row = QHBoxLayout()
        self._record_reveal_btn = QPushButton("Reveal in file manager")
        self._record_reveal_btn.setStyleSheet(_SECONDARY_STYLE)
        self._record_reveal_btn.clicked.connect(self._on_reveal_record)
        record_btn_row.addWidget(self._record_reveal_btn)
        self._record_manual_btn = QPushButton("Generate manually")
        self._record_manual_btn.setStyleSheet(_SECONDARY_STYLE)
        self._record_manual_btn.clicked.connect(self._on_generate_record_manually)
        record_btn_row.addWidget(self._record_manual_btn)
        record_btn_row.addStretch()
        record_layout.addLayout(record_btn_row)
        self._record_panel.setVisible(False)
        layout.addWidget(self._record_panel)

        layout.addStretch()
        self._stack.addWidget(w)

    # ------------------------------------------------------------------
    # Pre-selection
    # ------------------------------------------------------------------

    def _apply_pre_selection(self) -> None:
        if self._pre.platform:
            idx = self._platform_combo.findText(self._pre.platform)
            if idx >= 0:
                self._platform_combo.setCurrentIndex(idx)
        if self._pre.scenario and self._pre.scenario in self._scenario_radios:
            self._scenario_radios[self._pre.scenario].setChecked(True)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    _PAGE_SCENARIO = 0
    _PAGE_SH_SERVER = 1
    _PAGE_SH_DOMAIN = 2
    _PAGE_SH_ADMIN = 3
    _PAGE_SH_DOCUMENTATION = 4
    _PAGE_SH_PROGRESS = 5
    _PAGE_CLOUD_DETAILS = 6
    _PAGE_CLOUD_PROGRESS = 7
    _PAGE_RESULT = 8

    def _selected_scenario(self) -> str | None:
        for scenario, radio in self._scenario_radios.items():
            if radio.isChecked():
                return scenario
        return None

    def _update_nav(self) -> None:
        page = self._stack.currentIndex()
        is_progress = page in (self._PAGE_SH_PROGRESS, self._PAGE_CLOUD_PROGRESS)
        is_result = page == self._PAGE_RESULT

        self._back_btn.setVisible(
            page > 0 and not is_progress and not is_result
        )
        self._next_btn.setVisible(not is_progress and not is_result)
        self._cancel_btn.setText("Close" if is_result else "Cancel")

        # Step labels
        scenario = self._selected_scenario()
        if page == self._PAGE_SCENARIO:
            self._step_label.setText("Step 1 \u2014 Scenario & Platform")
        elif scenario == "self_hosted":
            labels = {
                self._PAGE_SH_SERVER: "Step 2 \u2014 Server Target",
                self._PAGE_SH_DOMAIN: "Step 3 \u2014 Domain & Database",
                self._PAGE_SH_ADMIN: "Step 4 \u2014 Admin Account",
                self._PAGE_SH_DOCUMENTATION:
                    "Step 5 \u2014 Documentation Inputs",
                self._PAGE_SH_PROGRESS: "Deploying...",
            }
            self._step_label.setText(labels.get(page, ""))
        elif scenario in ("cloud_hosted", "bring_your_own"):
            labels = {
                self._PAGE_CLOUD_DETAILS: "Step 2 \u2014 Instance Details",
                self._PAGE_CLOUD_PROGRESS: "Verifying...",
            }
            self._step_label.setText(labels.get(page, ""))
        if is_result:
            self._step_label.setText("Complete")

    def _on_back(self) -> None:
        page = self._stack.currentIndex()
        if page == self._PAGE_SH_SERVER:
            self._stack.setCurrentIndex(self._PAGE_SCENARIO)
        elif page == self._PAGE_CLOUD_DETAILS:
            self._stack.setCurrentIndex(self._PAGE_SCENARIO)
        elif page > 0:
            self._stack.setCurrentIndex(page - 1)
        self._update_nav()

    def _on_next(self) -> None:
        page = self._stack.currentIndex()

        if page == self._PAGE_SCENARIO:
            if not self._validate_scenario():
                return
            self._handle_instance_matching()
            return

        if page == self._PAGE_SH_SERVER:
            if not self._validate_sh_server():
                return
            self._stack.setCurrentIndex(self._PAGE_SH_DOMAIN)

        elif page == self._PAGE_SH_DOMAIN:
            if not self._validate_sh_domain():
                return
            self._stack.setCurrentIndex(self._PAGE_SH_ADMIN)

        elif page == self._PAGE_SH_ADMIN:
            if not self._validate_sh_admin():
                return
            self._populate_documentation_defaults()
            self._stack.setCurrentIndex(self._PAGE_SH_DOCUMENTATION)

        elif page == self._PAGE_SH_DOCUMENTATION:
            if not self._validate_sh_documentation():
                return
            self._start_self_hosted_deploy()
            return

        elif page == self._PAGE_CLOUD_DETAILS:
            if not self._validate_cloud_details():
                return
            self._start_cloud_byo_check()
            return

        self._update_nav()

    def _on_cancel(self) -> None:
        if self._finished:
            self.accept()
            return
        if self._run_id is not None and not self._finished:
            finalize_deployment_run(
                self._conn, self._run_id,
                outcome="cancelled",
            )
        self.reject()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_scenario(self) -> bool:
        if not self._selected_scenario():
            QMessageBox.warning(self, "Validation", "Please select a deployment scenario.")
            return False
        return True

    def _validate_sh_server(self) -> bool:
        if not self._ssh_host.text().strip():
            QMessageBox.warning(self, "Validation", "SSH Host is required.")
            return False
        if not self._ssh_credential.text().strip():
            QMessageBox.warning(self, "Validation", "SSH credential is required.")
            return False
        return True

    def _validate_sh_domain(self) -> bool:
        if not self._sh_domain.text().strip():
            QMessageBox.warning(self, "Validation", "Domain is required.")
            return False
        if not self._sh_db_password.text().strip():
            QMessageBox.warning(self, "Validation", "DB Password is required.")
            return False
        if not self._sh_le_email.text().strip():
            QMessageBox.warning(self, "Validation", "Let's Encrypt Email is required.")
            return False
        return True

    def _validate_sh_admin(self) -> bool:
        if not self._sh_admin_pass.text().strip():
            QMessageBox.warning(self, "Validation", "Admin Password is required.")
            return False
        if not self._sh_admin_email.text().strip():
            QMessageBox.warning(self, "Validation", "Admin Email is required.")
            return False
        return True

    def _validate_sh_documentation(self) -> bool:
        if not self._doc_registrar.text().strip():
            QMessageBox.warning(self, "Validation", "Domain Registrar is required.")
            return False
        if not self._doc_dns_provider.text().strip():
            QMessageBox.warning(self, "Validation", "DNS Provider is required.")
            return False
        droplet_id = self._doc_droplet_id.text().strip()
        if droplet_id and not droplet_id.isdigit():
            QMessageBox.warning(
                self, "Validation",
                "Droplet ID must be numeric (or left blank).",
            )
            return False
        if not self._doc_proton_admin.text().strip():
            QMessageBox.warning(
                self, "Validation",
                "Admin Password Proton Pass entry name is required.",
            )
            return False
        if not self._doc_proton_db_root.text().strip():
            QMessageBox.warning(
                self, "Validation",
                "DB Root Password Proton Pass entry name is required.",
            )
            return False
        if not self._doc_proton_hosting.text().strip():
            QMessageBox.warning(
                self, "Validation",
                "DigitalOcean Account Proton Pass entry name is required.",
            )
            return False
        return True

    def _validate_cloud_details(self) -> bool:
        if not self._cloud_url.text().strip():
            QMessageBox.warning(self, "Validation", "Instance URL is required.")
            return False
        if not self._cloud_pass.text().strip():
            QMessageBox.warning(self, "Validation", "Admin Password is required.")
            return False
        return True

    # ------------------------------------------------------------------
    # Existing-instance matching (§14.12.5)
    # ------------------------------------------------------------------

    def _handle_instance_matching(self) -> None:
        scenario = self._selected_scenario()
        platform = self._platform_combo.currentText()
        matches = find_matching_instances(self._conn)

        if matches:
            result = self._show_instance_match_dialog(matches)
            if result == "cancel":
                return
            if result == "new":
                self._creating_new = True
                self._instance_id = None
            else:
                # result is an instance ID
                self._creating_new = False
                self._instance_id = int(result)
        else:
            self._creating_new = True
            self._instance_id = None

        # Create a placeholder instance if needed (DeploymentRun requires instance_id)
        if self._creating_new:
            code = platform[:2].upper() + scenario[:2].upper() + "01"
            # Ensure code uniqueness
            existing = {m.code for m in matches}
            suffix = 1
            while code in existing:
                suffix += 1
                code = platform[:2].upper() + scenario[:2].upper() + f"{suffix:02d}"
            self._instance_id = create_wizard_instance(
                self._conn,
                name=f"{platform} ({SCENARIO_LABELS.get(scenario, scenario)})",
                code=code,
                environment="production",
            )

        # Insert DeploymentRun
        self._run_id = insert_deployment_run(
            self._conn,
            instance_id=self._instance_id,
            scenario=scenario,
            crm_platform=platform,
        )

        # Branch to scenario-specific pages
        if scenario == "self_hosted":
            self._stack.setCurrentIndex(self._PAGE_SH_SERVER)
        else:
            # Set help text for cloud vs BYO
            if scenario == "cloud_hosted":
                self._cloud_help.setText(
                    "Enter the URL and admin credentials for your cloud-hosted "
                    "EspoCRM instance. You can find these in your EspoCRM Cloud "
                    "portal or hosting provider's dashboard."
                )
            else:
                self._cloud_help.setText(
                    "Enter the URL and admin credentials for your existing "
                    "EspoCRM instance. Use the credentials you configured "
                    "when setting up the instance."
                )
            self._stack.setCurrentIndex(self._PAGE_CLOUD_DETAILS)
        self._update_nav()

    def _show_instance_match_dialog(
        self, matches: list[MatchingInstance]
    ) -> str:
        """Show dialog for existing-instance matching.

        :returns: 'cancel', 'new', or an instance ID string.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Existing Instances Found")
        msg.setText(
            f"Found {len(matches)} existing instance(s) for this client.\n\n"
            "Would you like to update an existing instance or create a new one?"
        )
        msg.addButton("Update Existing", QMessageBox.ButtonRole.AcceptRole)
        new_btn = msg.addButton("Create New", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == cancel_btn:
            return "cancel"
        if clicked == new_btn:
            return "new"

        # If multiple matches, let user pick
        if len(matches) == 1:
            return str(matches[0].id)

        items = [f"{m.name} ({m.environment}) — {m.url or 'no URL'}" for m in matches]
        from PySide6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(
            self, "Select Instance", "Update which instance?", items, 0, False,
        )
        if not ok:
            return "cancel"
        idx = items.index(choice)
        return str(matches[idx].id)

    # ------------------------------------------------------------------
    # Self-hosted deploy
    # ------------------------------------------------------------------

    def _populate_documentation_defaults(self) -> None:
        """Pre-populate Proton Pass entry defaults from instance/code/env.

        Called as the user transitions from the Admin step into the
        Documentation Inputs step. Only writes values if the field is
        empty so a Back/Next round trip doesn't clobber edits.
        """
        code = ""
        env_label = ""
        try:
            row = self._conn.execute(
                "SELECT code, environment FROM Instance WHERE id = ?",
                (self._instance_id,),
            ).fetchone()
            if row:
                code = (row[0] or "").upper()
                env_label = (row[1] or "").title()
        except Exception:
            pass

        admin_default = (
            f"{code}-ESPOCRM-{env_label} Instance Admin"
            if code and env_label else ""
        )
        db_root_default = (
            f"{code}-ESPOCRM-{env_label} DB Root"
            if code and env_label else ""
        )
        hosting_default = (
            f"{code} DigitalOcean Account" if code else ""
        )

        if not self._doc_proton_admin.text().strip():
            self._doc_proton_admin.setText(admin_default)
        if not self._doc_proton_db_root.text().strip():
            self._doc_proton_db_root.setText(db_root_default)
        if not self._doc_proton_hosting.text().strip():
            self._doc_proton_hosting.setText(hosting_default)

    def _on_registrar_changed(self, text: str) -> None:
        """Mirror registrar into DNS provider when the two were in sync."""
        current = self._doc_dns_provider.text().strip()
        if current == "" or current == "Porkbun":
            self._doc_dns_provider.setText(text)

    def _build_administrator_inputs(
        self, config: SelfHostedConfig
    ) -> AdministratorInputs:
        """Bridge wizard form fields to the Prompt-A AdministratorInputs."""
        subdomain, primary = _split_domain(config.domain)
        droplet_id = self._doc_droplet_id.text().strip() or None
        return AdministratorInputs(
            domain_registrar=self._doc_registrar.text().strip(),
            dns_provider=self._doc_dns_provider.text().strip(),
            primary_domain=primary,
            instance_subdomain=subdomain,
            droplet_id=droplet_id,
            backups_enabled=self._doc_backups_enabled.isChecked(),
            proton_pass_admin_entry=self._doc_proton_admin.text().strip(),
            proton_pass_db_root_entry=self._doc_proton_db_root.text().strip(),
            proton_pass_hosting_entry=self._doc_proton_hosting.text().strip(),
        )

    def _start_self_hosted_deploy(self) -> None:
        import secrets

        db_root = self._sh_db_root_password.text().strip()
        if not db_root:
            db_root = secrets.token_urlsafe(16)

        config = SelfHostedConfig(
            ssh_host=self._ssh_host.text().strip(),
            ssh_port=int(self._ssh_port.text().strip() or "22"),
            ssh_username=self._ssh_user.text().strip(),
            ssh_credential=self._ssh_credential.text().strip(),
            ssh_auth_type="key" if self._ssh_auth_combo.currentIndex() == 0 else "password",
            domain=self._sh_domain.text().strip(),
            letsencrypt_email=self._sh_le_email.text().strip(),
            db_password=self._sh_db_password.text().strip(),
            db_root_password=db_root,
            admin_username=self._sh_admin_user.text().strip(),
            admin_password=self._sh_admin_pass.text().strip(),
            admin_email=self._sh_admin_email.text().strip(),
        )
        self._self_hosted_config = config
        self._administrator_inputs = self._build_administrator_inputs(config)
        self._record_generated_path = None
        self._record_generation_error = None

        self._sh_log.clear()
        self._stack.setCurrentIndex(self._PAGE_SH_PROGRESS)
        self._update_nav()

        db_path = self._conn.execute(
            "PRAGMA database_list"
        ).fetchone()[2]
        project_folder = self._read_project_folder()
        client_name = self._read_client_name()

        self._worker = SelfHostedWorker(
            config,
            administrator_inputs=self._administrator_inputs,
            instance_id=self._instance_id,
            db_path=db_path,
            project_folder=project_folder,
            client_name=client_name,
            parent=self,
        )
        self._worker.log_line.connect(self._on_sh_log)
        self._worker.record_generated.connect(self._on_record_generated)
        self._worker.record_generation_failed.connect(
            self._on_record_generation_failed
        )
        self._worker.deployment_finished.connect(
            lambda ok: self._on_deploy_finished(ok, config)
        )
        self._worker.start()

    def _read_project_folder(self) -> str | None:
        """Look up the active client's project_folder from the master DB."""
        if not self._master_db_path or not self._client_id:
            return None
        try:
            conn = sqlite3.connect(self._master_db_path)
            try:
                row = conn.execute(
                    "SELECT project_folder FROM Client WHERE id = ?",
                    (self._client_id,),
                ).fetchone()
            finally:
                conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        return None

    def _read_client_name(self) -> str | None:
        """Look up the active client's display name from the master DB."""
        if not self._master_db_path or not self._client_id:
            return None
        try:
            conn = sqlite3.connect(self._master_db_path)
            try:
                row = conn.execute(
                    "SELECT name FROM Client WHERE id = ?",
                    (self._client_id,),
                ).fetchone()
            finally:
                conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        return None

    def _on_record_generated(self, path: str) -> None:
        """Worker emitted a generated Deployment Record path."""
        self._record_generated_path = path
        self._record_generation_error = None

    def _on_record_generation_failed(self, message: str) -> None:
        """Worker emitted a Record-generation failure (deploy still ok)."""
        self._record_generated_path = None
        self._record_generation_error = message

    def _on_sh_log(self, message: str, level: str) -> None:
        color = {"error": "#F44336", "warning": "#FFC107"}.get(level, "#D4D4D4")
        self._sh_log.appendHtml(f'<span style="color: {color};">{_escape(message)}</span>')

    def _on_deploy_finished(self, success: bool, config: SelfHostedConfig) -> None:
        if success:
            finalize_deployment_run(
                self._conn, self._run_id, outcome="success",
            )
            self._show_result(True, "Deployment completed successfully!")
        else:
            finalize_deployment_run(
                self._conn, self._run_id, outcome="failure",
                failure_reason="One or more deployment steps failed.",
            )
            self._show_result(False, "Deployment failed. Check the log for details.")

    # ------------------------------------------------------------------
    # Cloud / BYO
    # ------------------------------------------------------------------

    def _start_cloud_byo_check(self) -> None:
        self._cloud_log.clear()
        self._stack.setCurrentIndex(self._PAGE_CLOUD_PROGRESS)
        self._update_nav()

        self._worker = ConnectivityWorker(
            self._cloud_url.text().strip(),
            self._cloud_user.text().strip(),
            self._cloud_pass.text().strip(),
            parent=self,
        )
        self._worker.log_line.connect(self._on_cloud_log)
        self._worker.result_ready.connect(self._on_cloud_result)
        self._worker.start()

    def _on_cloud_log(self, message: str, level: str) -> None:
        color = {"error": "#F44336", "warning": "#FFC107"}.get(level, "#D4D4D4")
        self._cloud_log.appendHtml(f'<span style="color: {color};">{_escape(message)}</span>')

    def _on_cloud_result(self, result: ConnectivityResult) -> None:
        if result.error:
            finalize_deployment_run(
                self._conn, self._run_id, outcome="failure",
                failure_reason=result.error,
            )
            self._show_result(False, f"Connection failed:\n{result.error}")
            return

        if not result.version_supported and result.version:
            finalize_deployment_run(
                self._conn, self._run_id, outcome="failure",
                failure_reason=f"Unsupported version: {result.version}",
            )
            self._show_result(
                False,
                f"EspoCRM version {result.version} is not supported.\n"
                "Please upgrade your instance to a supported version.",
            )
            return

        # Success — update instance
        url = self._cloud_url.text().strip()
        update_instance_from_wizard(
            self._conn, self._instance_id,
            url=url,
            username=self._cloud_user.text().strip(),
            password=self._cloud_pass.text().strip(),
        )
        finalize_deployment_run(
            self._conn, self._run_id, outcome="success",
        )
        version_info = f" (version {result.version})" if result.version else ""
        self._show_result(
            True,
            f"Successfully connected to EspoCRM{version_info} at {url}",
        )

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def _show_result(self, success: bool, message: str) -> None:
        self._finished = True
        self._result_icon.setText("\u2705" if success else "\u274c")
        self._result_msg.setText(message)
        self._populate_record_panel(success)
        self._stack.setCurrentIndex(self._PAGE_RESULT)
        self._update_nav()

    def _populate_record_panel(self, deploy_success: bool) -> None:
        """Show the Deployment Record panel based on the worker's signals.

        Hidden entirely when a Record was not attempted (failed deploy,
        cloud/BYO scenario, or no project_folder available).
        """
        path = getattr(self, "_record_generated_path", None)
        error = getattr(self, "_record_generation_error", None)

        if not deploy_success or (path is None and error is None):
            self._record_panel.setVisible(False)
            return

        if path:
            self._record_status.setText(
                f"A Deployment Record was generated at:\n{path}"
            )
            self._record_status.setStyleSheet(
                "font-size: 12px; padding: 4px 0; color: #2E7D32;"
            )
            self._record_reveal_btn.setVisible(True)
            self._record_manual_btn.setVisible(False)
        else:
            self._record_status.setText(
                "Deployment succeeded, but the Deployment Record could "
                f"not be generated:\n{error}\n\n"
                "You can generate it manually from the Deployment tab."
            )
            self._record_status.setStyleSheet(
                "font-size: 12px; padding: 4px 0; color: #B71C1C; "
                "background-color: #FFF8E1; padding: 8px; "
                "border-left: 4px solid #FFC107;"
            )
            self._record_reveal_btn.setVisible(False)
            self._record_manual_btn.setVisible(True)
        self._record_panel.setVisible(True)

    def _on_reveal_record(self) -> None:
        """Open the Deployment Record's parent folder in the OS file manager."""
        path = getattr(self, "_record_generated_path", None)
        if not path:
            return
        parent = str(Path(path).parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(parent))

    def _on_generate_record_manually(self) -> None:
        """Launch the manual Deployment Record regeneration dialog.

        Resolves the active instance, its persisted ``InstanceDeployConfig``,
        and the per-client database path from existing wizard state, then
        defers to ``launch_regeneration_dialog`` from
        :mod:`automation.ui.deployment.regenerate_record_dialog` — the
        same entry point used by the Deployment tab's Generate Deployment
        Record button. Shown only when automatic generation failed
        during a successful deploy; if any prerequisite is missing,
        surfaces a clear warning and directs the operator to the
        Deployment tab instead of crashing.
        """
        if self._instance_id is None:
            QMessageBox.warning(
                self,
                "Generate Deployment Record",
                "Cannot regenerate the Deployment Record from this "
                "wizard because no instance was created. Open the "
                "Deployment tab and use the 'Generate Deployment "
                "Record' action there instead.",
            )
            return

        instance = load_instance_detail(self._conn, self._instance_id)
        if instance is None:
            QMessageBox.warning(
                self,
                "Generate Deployment Record",
                "The instance row could not be loaded. Open the "
                "Deployment tab and use the 'Generate Deployment "
                "Record' action there instead.",
            )
            return

        deploy_config = load_deploy_config(self._conn, self._instance_id)
        if deploy_config is None:
            QMessageBox.warning(
                self,
                "Generate Deployment Record",
                "No InstanceDeployConfig is recorded for this "
                "instance, so the regeneration dialog cannot reach "
                "the server. Open the Deployment tab and use the "
                "'Generate Deployment Record' action there once the "
                "connection details are populated.",
            )
            return

        project_folder = self._read_project_folder()
        if not project_folder or not Path(project_folder).is_dir():
            QMessageBox.warning(
                self,
                "Generate Deployment Record",
                "The client's project folder is not configured or "
                "does not exist on disk. Set it on the Client and "
                "use the 'Generate Deployment Record' action on the "
                "Deployment tab.",
            )
            return

        db_path = self._conn.execute(
            "PRAGMA database_list"
        ).fetchone()[2]
        client_name = self._read_client_name() or instance.name

        launch_regeneration_dialog(
            parent=self,
            instance=instance,
            deploy_config=deploy_config,
            project_folder=project_folder,
            db_path=db_path,
            client_name=client_name,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_ssh_auth_changed(self, index: int) -> None:
        if index == 0:
            self._ssh_credential.setPlaceholderText("e.g. ~/.ssh/id_ed25519")
            self._ssh_credential.setEchoMode(QLineEdit.EchoMode.Normal)
            self._ssh_credential.setToolTip(
                "Click Browse to select the private key file. The "
                "corresponding public key must be installed in "
                "/root/.ssh/authorized_keys on the Droplet. See "
                "Deployment Runbook §5."
            )
            self._ssh_browse_btn.setVisible(True)
        else:
            # Password mode: omit placeholder for security; keep tooltip.
            self._ssh_credential.setPlaceholderText("")
            self._ssh_credential.setEchoMode(QLineEdit.EchoMode.Password)
            self._ssh_credential.setToolTip(
                "The password for the SSH user. Avoid password "
                "authentication where possible; key-based "
                "authentication is recommended."
            )
            self._ssh_browse_btn.setVisible(False)

    def _on_browse_ssh_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Private Key", str(Path.home() / ".ssh"),
        )
        if path:
            self._ssh_credential.setText(path)

    def closeEvent(self, event) -> None:
        """Ensure DeploymentRun is finalized on close."""
        if self._run_id and not self._finished:
            finalize_deployment_run(
                self._conn, self._run_id, outcome="cancelled",
            )
        super().closeEvent(event)


def _escape(text: str) -> str:
    """HTML-escape text for log display."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _hint(text: str) -> QLabel:
    """Build a one-line hint label for the Documentation Inputs form."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #757575; font-size: 11px;")
    return label


def _input_with_helper(widget: QWidget, helper_text: str) -> QWidget:
    """Wrap an input widget with a small helper label below it.

    Helper labels render in 9pt italic gray text directly under the
    field they describe, providing just-in-time guidance without
    competing visually with the field's own label or input text.
    Widgets without a helper string are returned wrapped without a
    label so the form layout still aligns.

    :param widget: The input control (typically a ``QLineEdit`` or a
        composite ``QWidget`` such as the SSH credential row).
    :param helper_text: One-line guidance text. Empty string skips
        the helper label entirely.
    :returns: A container ``QWidget`` suitable for ``QFormLayout.addRow``.
    """
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.addWidget(widget)

    if helper_text:
        helper = QLabel(helper_text)
        font = helper.font()
        font.setPointSize(9)
        font.setItalic(True)
        helper.setFont(font)
        helper.setStyleSheet("color: #666666;")
        layout.addWidget(helper)

    return container


def _split_domain(domain: str) -> tuple[str, str]:
    """Split a fully qualified domain into (subdomain, primary_domain).

    "crm-mr-test.cbm-charity.org" → ("crm-mr-test", "cbm-charity.org").
    "example.com" → ("", "example.com") — a two-label domain has no
    subdomain. Caller-tolerant: empty input returns ("", "").
    """
    text = (domain or "").strip().rstrip(".")
    if not text:
        return ("", "")
    parts = text.split(".")
    if len(parts) <= 2:
        return ("", text)
    return (parts[0], ".".join(parts[1:]))
