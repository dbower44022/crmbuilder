"""Deploy Wizard — three-scenario modal dialog (§14.12.5).

Step 1 is shared (scenario + platform selection). Subsequent steps
branch by scenario: self-hosted (7 total steps) or cloud/BYO (4 total).

Every wizard execution writes a DeploymentRun row.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
        # Page 4: Self-hosted — deploy progress
        self._build_self_hosted_progress_page()
        # Page 5: Cloud/BYO — instance details
        self._build_cloud_byo_details_page()
        # Page 6: Cloud/BYO — connectivity progress
        self._build_cloud_byo_progress_page()
        # Page 7: Result page (shared)
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
        self._ssh_host.setPlaceholderText("e.g., 165.232.150.42")
        form.addRow("SSH Host:", self._ssh_host)

        self._ssh_port = QLineEdit()
        self._ssh_port.setText("22")
        form.addRow("SSH Port:", self._ssh_port)

        self._ssh_user = QLineEdit()
        self._ssh_user.setText("root")
        form.addRow("SSH Username:", self._ssh_user)

        self._ssh_auth_combo = QComboBox()
        self._ssh_auth_combo.addItems(["SSH Key", "Password"])
        self._ssh_auth_combo.currentIndexChanged.connect(self._on_ssh_auth_changed)
        form.addRow("Authentication:", self._ssh_auth_combo)

        key_layout = QHBoxLayout()
        self._ssh_credential = QLineEdit()
        self._ssh_credential.setPlaceholderText("~/.ssh/id_ed25519")
        self._ssh_browse_btn = QPushButton("Browse...")
        self._ssh_browse_btn.clicked.connect(self._on_browse_ssh_key)
        key_layout.addWidget(self._ssh_credential)
        key_layout.addWidget(self._ssh_browse_btn)
        form.addRow("Credential:", key_layout)

        self._stack.addWidget(w)

    def _build_self_hosted_domain_page(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self._sh_domain = QLineEdit()
        self._sh_domain.setPlaceholderText("crm.mycompany.com")
        form.addRow("Domain:", self._sh_domain)

        self._sh_le_email = QLineEdit()
        self._sh_le_email.setPlaceholderText("admin@mycompany.com")
        form.addRow("Let's Encrypt Email:", self._sh_le_email)

        self._sh_db_password = QLineEdit()
        self._sh_db_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("DB Password:", self._sh_db_password)

        self._sh_db_root_password = QLineEdit()
        self._sh_db_root_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._sh_db_root_password.setPlaceholderText("Leave blank to auto-generate")
        form.addRow("DB Root Password:", self._sh_db_root_password)

        self._stack.addWidget(w)

    def _build_self_hosted_admin_page(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self._sh_admin_user = QLineEdit()
        self._sh_admin_user.setText("admin")
        form.addRow("Admin Username:", self._sh_admin_user)

        self._sh_admin_pass = QLineEdit()
        self._sh_admin_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Admin Password:", self._sh_admin_pass)

        self._sh_admin_email = QLineEdit()
        form.addRow("Admin Email:", self._sh_admin_email)

        hint = QLabel(
            "These credentials will be used to create the initial EspoCRM "
            "administrator account and saved to the Instance record."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #757575; font-size: 11px; padding-top: 12px;")
        form.addRow("", hint)

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
    _PAGE_SH_PROGRESS = 4
    _PAGE_CLOUD_DETAILS = 5
    _PAGE_CLOUD_PROGRESS = 6
    _PAGE_RESULT = 7

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

        self._sh_log.clear()
        self._stack.setCurrentIndex(self._PAGE_SH_PROGRESS)
        self._update_nav()

        self._worker = SelfHostedWorker(config, parent=self)
        self._worker.log_line.connect(self._on_sh_log)
        self._worker.deployment_finished.connect(
            lambda ok: self._on_deploy_finished(ok, config)
        )
        self._worker.start()

    def _on_sh_log(self, message: str, level: str) -> None:
        color = {"error": "#F44336", "warning": "#FFC107"}.get(level, "#D4D4D4")
        self._sh_log.appendHtml(f'<span style="color: {color};">{_escape(message)}</span>')

    def _on_deploy_finished(self, success: bool, config: SelfHostedConfig) -> None:
        if success:
            # Update instance row
            url = f"https://{config.domain}"
            update_instance_from_wizard(
                self._conn, self._instance_id,
                url=url,
                username=config.admin_username,
                password=config.admin_password,
            )
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
        self._stack.setCurrentIndex(self._PAGE_RESULT)
        self._update_nav()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_ssh_auth_changed(self, index: int) -> None:
        if index == 0:
            self._ssh_credential.setPlaceholderText("~/.ssh/id_ed25519")
            self._ssh_credential.setEchoMode(QLineEdit.EchoMode.Normal)
            self._ssh_browse_btn.setVisible(True)
        else:
            self._ssh_credential.setPlaceholderText("SSH password")
            self._ssh_credential.setEchoMode(QLineEdit.EchoMode.Password)
            self._ssh_browse_btn.setVisible(False)

    def _on_browse_ssh_key(self) -> None:
        from pathlib import Path
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
