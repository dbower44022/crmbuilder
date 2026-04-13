"""Instances sidebar entry — list + detail pane (Section 14.12.3).

Displays all instances for the active client with inline editing,
connection testing, and instance management actions.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    create_instance,
    delete_instance,
    load_instance_detail,
    load_instances,
    set_default_instance,
    update_instance,
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

_DANGER_STYLE = (
    "QPushButton { background-color: #E53935; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #C62828; }"
)

_TOGGLE_PW_STYLE = (
    "QPushButton { border: 1px solid #555; border-radius: 3px; "
    "padding: 2px 8px; font-size: 13px; color: #9E9E9E; "
    "background: transparent; } "
    "QPushButton:hover { color: #FFFFFF; border-color: #999; }"
)

_EMPTY_MSG = (
    "No CRM instances have been created for this client yet.\n\n"
    "Click '+ New Instance' above to add the first instance."
)

# Status display constants
_STATUS_COLORS = {
    "connected": "#4CAF50",
    "auth_failed": "#E53935",
    "unreachable": "#E53935",
    "error": "#E53935",
    "no_url": "#9E9E9E",
    "not_tested": "#9E9E9E",
    "testing": "#2196F3",
}

_STATUS_LABELS = {
    "connected": "Connected",
    "auth_failed": "Auth Failed",
    "unreachable": "Unreachable",
    "error": "Error",
    "no_url": "No URL",
    "not_tested": "Not Tested",
    "testing": "Testing...",
}


class _ConnectionTestWorker(QThread):
    """Background worker for testing instance connectivity.

    Accepts pre-read connection parameters so the sqlite3 connection
    is never touched from the worker thread.

    :param instance_id: The instance ID (for result routing).
    :param url: EspoCRM instance base URL.
    :param username: API username.
    :param password: API password.
    :param name: Instance display name.
    """

    result = Signal(int, bool, str)  # instance_id, success, message

    def __init__(
        self,
        instance_id: int,
        url: str,
        username: str,
        password: str,
        name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._instance_id = instance_id
        self._url = url
        self._username = username
        self._password = password
        self._name = name

    def run(self) -> None:
        """Execute the connection test."""
        try:
            from espo_impl.core.api_client import EspoAdminClient
            from espo_impl.core.models import InstanceProfile

            profile = InstanceProfile(
                name=self._name,
                url=self._url,
                api_key=self._username,
                auth_method="basic",
                secret_key=self._password,
            )
            client = EspoAdminClient(profile, timeout=15)
            success, message = client.test_connection()
        except Exception as exc:
            success, message = False, f"Connection error: {exc}"
        self.result.emit(self._instance_id, success, message)


class InstancesEntry(QWidget):
    """Instances list + detail pane.

    :param parent: Parent widget.
    """

    instance_created = Signal()  # Emitted after creating/updating/deleting
    navigate_requested = Signal(int)  # Emitted with sidebar index to navigate to

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instances: list[InstanceRow] = []
        self._selected_id: int | None = None
        self._status_cache: dict[int, str] = {}  # instance_id → status key
        self._test_worker: _ConnectionTestWorker | None = None
        self._master_db_path: str | None = None
        self._client_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with + New Instance button
        header = QHBoxLayout()
        self._new_btn = QPushButton("+ New Instance")
        self._new_btn.setStyleSheet(_PRIMARY_STYLE)
        self._new_btn.clicked.connect(self._on_new)
        header.addWidget(self._new_btn)
        header.addStretch()
        layout.addLayout(header)

        # Empty state
        self._empty_label = QLabel(_EMPTY_MSG)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        # Splitter: table on top, detail below
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # --- Instance table ---
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Code", "Environment", "URL", "Default", "Status"]
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.currentCellChanged.connect(self._on_row_changed)
        self._splitter.addWidget(self._table)

        # --- Detail pane ---
        self._detail_group = QGroupBox("Instance Details")
        detail_layout = QFormLayout()

        self._detail_name = QLineEdit()
        detail_layout.addRow("Name:", self._detail_name)

        self._detail_code = QLineEdit()
        self._detail_code.setReadOnly(True)
        self._detail_code.setStyleSheet("background-color: #F5F5F5;")
        detail_layout.addRow("Code:", self._detail_code)

        self._detail_env = QLineEdit()
        self._detail_env.setReadOnly(True)
        self._detail_env.setStyleSheet("background-color: #F5F5F5;")
        detail_layout.addRow("Environment:", self._detail_env)

        self._detail_url = QLineEdit()
        detail_layout.addRow("URL:", self._detail_url)

        self._detail_username = QLineEdit()
        detail_layout.addRow("Username:", self._detail_username)

        detail_pw_row = QHBoxLayout()
        self._detail_password = QLineEdit()
        self._detail_password.setEchoMode(QLineEdit.EchoMode.Password)
        detail_pw_row.addWidget(self._detail_password)
        self._detail_pw_toggle = QPushButton("\U0001f441")
        self._detail_pw_toggle.setFixedWidth(36)
        self._detail_pw_toggle.setToolTip("Show / hide password")
        self._detail_pw_toggle.setStyleSheet(_TOGGLE_PW_STYLE)
        self._detail_pw_toggle.clicked.connect(self._toggle_detail_password)
        detail_pw_row.addWidget(self._detail_pw_toggle)
        detail_layout.addRow("Password:", detail_pw_row)

        self._detail_desc = QLineEdit()
        detail_layout.addRow("Description:", self._detail_desc)

        self._detail_default = QCheckBox("Default Instance")
        detail_layout.addRow("", self._detail_default)

        # Connection test result label
        self._test_result_label = QLabel("")
        self._test_result_label.setWordWrap(True)
        self._test_result_label.setVisible(False)
        self._test_result_label.setStyleSheet(
            "padding: 6px; border-radius: 3px; font-size: 12px;"
        )
        detail_layout.addRow("", self._test_result_label)

        # Primary action row — workflow actions
        primary_row = QHBoxLayout()

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setStyleSheet(_PRIMARY_STYLE)
        self._test_btn.clicked.connect(self._on_test_connection)
        primary_row.addWidget(self._test_btn)

        self._configure_btn = QPushButton("Configure Instance")
        self._configure_btn.setStyleSheet(_PRIMARY_STYLE)
        self._configure_btn.clicked.connect(self._on_configure)
        primary_row.addWidget(self._configure_btn)

        self._open_btn = QPushButton("Open in Browser")
        self._open_btn.setStyleSheet(_SECONDARY_STYLE)
        self._open_btn.clicked.connect(self._on_open_browser)
        primary_row.addWidget(self._open_btn)

        primary_row.addStretch()
        detail_layout.addRow("", primary_row)

        # Management row — save, deploy, delete
        mgmt_row = QHBoxLayout()

        self._save_btn = QPushButton("Save Changes")
        self._save_btn.setStyleSheet(_SECONDARY_STYLE)
        self._save_btn.clicked.connect(self._on_save)
        mgmt_row.addWidget(self._save_btn)

        self._wizard_btn = QPushButton("Deploy Wizard")
        self._wizard_btn.setStyleSheet(_SECONDARY_STYLE)
        self._wizard_btn.clicked.connect(self._on_start_wizard)
        mgmt_row.addWidget(self._wizard_btn)

        mgmt_row.addStretch()

        self._delete_btn = QPushButton("Delete Instance")
        self._delete_btn.setStyleSheet(_DANGER_STYLE)
        self._delete_btn.clicked.connect(self._on_delete)
        mgmt_row.addWidget(self._delete_btn)

        detail_layout.addRow("", mgmt_row)

        self._detail_group.setLayout(detail_layout)
        self._splitter.addWidget(self._detail_group)

        layout.addWidget(self._splitter, stretch=1)

        # --- New-instance form (hidden by default) ---
        self._new_form = QGroupBox("Create New Instance")
        new_layout = QFormLayout()

        self._new_name = QLineEdit()
        new_layout.addRow("Name:", self._new_name)

        self._new_code = QLineEdit()
        self._new_code.setPlaceholderText("2-10 uppercase letters/digits")
        new_layout.addRow("Code:", self._new_code)

        self._new_env = QComboBox()
        self._new_env.addItems(["production", "staging", "test"])
        new_layout.addRow("Environment:", self._new_env)

        self._new_url = QLineEdit()
        new_layout.addRow("URL:", self._new_url)

        self._new_username = QLineEdit()
        new_layout.addRow("Username:", self._new_username)

        new_pw_row = QHBoxLayout()
        self._new_password = QLineEdit()
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        new_pw_row.addWidget(self._new_password)
        self._new_pw_toggle = QPushButton("\U0001f441")
        self._new_pw_toggle.setFixedWidth(36)
        self._new_pw_toggle.setToolTip("Show / hide password")
        self._new_pw_toggle.setStyleSheet(_TOGGLE_PW_STYLE)
        self._new_pw_toggle.clicked.connect(self._toggle_new_password)
        new_pw_row.addWidget(self._new_pw_toggle)
        new_layout.addRow("Password:", new_pw_row)

        self._new_desc = QLineEdit()
        new_layout.addRow("Description:", self._new_desc)

        self._new_default = QCheckBox("Set as default instance")
        new_layout.addRow("", self._new_default)

        new_btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel_new)
        new_btn_row.addWidget(cancel_btn)
        create_btn = QPushButton("Create")
        create_btn.setStyleSheet(_PRIMARY_STYLE)
        create_btn.clicked.connect(self._on_create)
        new_btn_row.addWidget(create_btn)
        new_layout.addRow("", new_btn_row)

        self._new_form.setLayout(new_layout)
        self._new_form.setVisible(False)
        layout.addWidget(self._new_form)

    def set_client_context(
        self, master_db_path: str, client_id: int,
    ) -> None:
        """Set the client context needed for the deploy wizard.

        :param master_db_path: Path to the master database.
        :param client_id: Active client ID.
        """
        self._master_db_path = master_db_path
        self._client_id = client_id

    def refresh(self, conn: sqlite3.Connection) -> None:
        """Reload instances from the database.

        :param conn: Per-client database connection.
        """
        self._conn = conn
        self._instances = load_instances(conn)
        self._populate_table()
        has_instances = len(self._instances) > 0
        self._empty_label.setVisible(not has_instances)
        self._splitter.setVisible(has_instances)

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._instances))
        for row, inst in enumerate(self._instances):
            self._table.setItem(row, 0, QTableWidgetItem(inst.name))
            self._table.setItem(row, 1, QTableWidgetItem(inst.code))
            self._table.setItem(row, 2, QTableWidgetItem(inst.environment))
            self._table.setItem(row, 3, QTableWidgetItem(inst.url or ""))
            self._table.setItem(
                row, 4, QTableWidgetItem("Yes" if inst.is_default else "")
            )

            # Status column — color-coded from cache
            status_key = self._status_cache.get(inst.id, "not_tested")
            if not inst.url:
                status_key = "no_url"
            status_item = QTableWidgetItem(_STATUS_LABELS.get(status_key, "—"))
            color = _STATUS_COLORS.get(status_key, "#9E9E9E")
            status_item.setForeground(QColor(color))
            self._table.setItem(row, 5, status_item)

        # Restore selection
        if self._selected_id is not None:
            for row, inst in enumerate(self._instances):
                if inst.id == self._selected_id:
                    self._table.setCurrentCell(row, 0)
                    return
        if self._instances:
            self._table.setCurrentCell(0, 0)

    def _update_status_cell(self, instance_id: int, status_key: str) -> None:
        """Update the Status column for a specific instance without full refresh.

        :param instance_id: The instance ID.
        :param status_key: One of the _STATUS_LABELS keys.
        """
        self._status_cache[instance_id] = status_key
        for row, inst in enumerate(self._instances):
            if inst.id == instance_id:
                status_item = QTableWidgetItem(
                    _STATUS_LABELS.get(status_key, "—")
                )
                color = _STATUS_COLORS.get(status_key, "#9E9E9E")
                status_item.setForeground(QColor(color))
                self._table.setItem(row, 5, status_item)
                break

    # ── Row selection ──────────────────────────────────────────────

    def _on_row_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        if not self._conn or row < 0 or row >= len(self._instances):
            self._detail_group.setVisible(False)
            self._selected_id = None
            return

        inst_row = self._instances[row]
        self._selected_id = inst_row.id
        detail = load_instance_detail(self._conn, inst_row.id)
        if detail is None:
            self._detail_group.setVisible(False)
            return

        self._detail_group.setVisible(True)
        self._detail_name.setText(detail.name)
        self._detail_code.setText(detail.code)
        self._detail_env.setText(detail.environment)
        self._detail_url.setText(detail.url or "")
        self._detail_username.setText(detail.username or "")
        self._detail_password.setText(detail.password or "")
        self._detail_desc.setText(detail.description or "")
        self._detail_default.setChecked(detail.is_default)
        self._test_result_label.setVisible(False)

    # ── Password visibility toggles ──────────────────────────────

    @staticmethod
    def _toggle_password(field: QLineEdit) -> None:
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)

    def _toggle_detail_password(self) -> None:
        self._toggle_password(self._detail_password)

    def _toggle_new_password(self) -> None:
        self._toggle_password(self._new_password)

    # ── Save ───────────────────────────────────────────────────────

    def _on_save(self) -> None:
        if not self._conn or self._selected_id is None:
            return

        name = self._detail_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return

        update_instance(
            self._conn,
            self._selected_id,
            name=name,
            url=self._detail_url.text().strip() or None,
            username=self._detail_username.text().strip() or None,
            password=self._detail_password.text() or None,
            description=self._detail_desc.text().strip() or None,
        )

        # Handle default flag change
        if self._detail_default.isChecked():
            set_default_instance(self._conn, self._selected_id)

        self.refresh(self._conn)
        self.instance_created.emit()

    # ── Test Connection ────────────────────────────────────────────

    def _on_test_connection(self) -> None:
        if self._selected_id is None:
            return

        if self._test_worker is not None:
            self._test_result_label.setText("A test is already in progress.")
            self._test_result_label.setStyleSheet(
                "padding: 6px; border-radius: 3px; font-size: 12px; "
                "color: #FFA726; background-color: #3E2723;"
            )
            self._test_result_label.setVisible(True)
            return

        # Read values from the form on the main thread (not in the worker)
        url = self._detail_url.text().strip()
        username = self._detail_username.text().strip()
        password = self._detail_password.text()
        name = self._detail_name.text().strip()

        if not url:
            self._test_result_label.setText(
                "No URL configured — enter a URL and save before testing."
            )
            self._test_result_label.setStyleSheet(
                "padding: 6px; border-radius: 3px; font-size: 12px; "
                "color: #FFA726; background-color: #3E2723;"
            )
            self._test_result_label.setVisible(True)
            return

        if not username or not password:
            self._test_result_label.setText(
                "Username and password are required to test the connection."
            )
            self._test_result_label.setStyleSheet(
                "padding: 6px; border-radius: 3px; font-size: 12px; "
                "color: #FFA726; background-color: #3E2723;"
            )
            self._test_result_label.setVisible(True)
            return

        # Show testing state
        self._update_status_cell(self._selected_id, "testing")
        self._test_result_label.setText("Testing connection...")
        self._test_result_label.setStyleSheet(
            "padding: 6px; border-radius: 3px; font-size: 12px; "
            "color: #2196F3; background-color: #1A237E;"
        )
        self._test_result_label.setVisible(True)
        self._test_btn.setText("Testing...")

        self._test_worker = _ConnectionTestWorker(
            instance_id=self._selected_id,
            url=url,
            username=username,
            password=password,
            name=name,
            parent=self,
        )
        self._test_worker.result.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(
        self, instance_id: int, success: bool, message: str
    ) -> None:
        """Handle connection test result from the background worker."""
        self._test_worker = None
        self._test_btn.setText("Test Connection")

        if success:
            status_key = "connected"
            self._test_result_label.setStyleSheet(
                "padding: 6px; border-radius: 3px; font-size: 12px; "
                "color: #4CAF50; background-color: #1B5E20;"
            )
        else:
            # Classify the failure for the status column
            msg_lower = message.lower()
            if "authentication" in msg_lower or "auth" in msg_lower:
                status_key = "auth_failed"
            elif "connection failed" in msg_lower or "url" in msg_lower:
                status_key = "unreachable"
            else:
                status_key = "error"
            self._test_result_label.setStyleSheet(
                "padding: 6px; border-radius: 3px; font-size: 12px; "
                "color: #E53935; background-color: #3E1A1A;"
            )

        self._test_result_label.setText(message)
        self._test_result_label.setVisible(True)
        self._update_status_cell(instance_id, status_key)

    # ── Configure Instance ────────────────────────────────────────

    def _on_configure(self) -> None:
        if self._selected_id is None:
            return

        url = self._detail_url.text().strip()
        if not url:
            QMessageBox.information(
                self,
                "No URL",
                "This instance has no URL configured yet.\n\n"
                "Enter a URL, save, and test the connection before "
                "configuring.",
            )
            return

        # Ensure the deployment phase is marked complete so Configure
        # becomes available.  For an already-deployed instance the user
        # should not have to run the Deploy Wizard first.
        if self._conn:
            self._ensure_deployment_phase_complete()

        # Navigate sidebar to Configure (index 2)
        self.navigate_requested.emit(2)

    def _ensure_deployment_phase_complete(self) -> None:
        """Advance crm_deployment through the workflow if not yet complete.

        If the work item exists and is not_started or ready, fast-forward it
        through start → complete so that crm_configuration becomes ready.
        """
        from automation.ui.deployment.deployment_logic import (
            get_phase_work_item,
        )
        from automation.workflow.engine import WorkflowEngine

        deploy_item = get_phase_work_item(self._conn, "crm_deployment")
        if deploy_item is None:
            return  # No workflow items yet — nothing to gate

        if deploy_item.status == "complete":
            return  # Already done

        engine = WorkflowEngine(self._conn)

        if deploy_item.status in ("not_started", "ready"):
            # Fast-forward: not_started → ready → in_progress → complete
            if deploy_item.status == "not_started":
                # Force to ready so start() won't reject it
                self._conn.execute(
                    "UPDATE WorkItem SET status = 'ready' WHERE id = ?",
                    (deploy_item.id,),
                )
                self._conn.commit()
            engine.start(deploy_item.id)
            engine.complete(deploy_item.id)
        elif deploy_item.status == "in_progress":
            engine.complete(deploy_item.id)

        # Also auto-start crm_configuration so the user can work immediately
        config_item = get_phase_work_item(self._conn, "crm_configuration")
        if config_item and config_item.status == "ready":
            engine.start(config_item.id)

    # ── Open in Browser ────────────────────────────────────────────

    def _on_open_browser(self) -> None:
        if self._selected_id is None:
            return

        url = self._detail_url.text().strip()
        if not url:
            QMessageBox.information(
                self,
                "No URL",
                "No URL is configured for this instance.\n"
                "Enter a URL and save before opening in the browser.",
            )
            return

        QDesktopServices.openUrl(QUrl(url))

    # ── Delete ─────────────────────────────────────────────────────

    def _on_delete(self) -> None:
        if not self._conn or self._selected_id is None:
            return

        # Find the instance name for the confirmation message
        name = self._detail_name.text().strip() or "this instance"
        code = self._detail_code.text().strip()

        reply = QMessageBox.warning(
            self,
            "Delete Instance",
            f"Are you sure you want to delete '{name}' ({code})?\n\n"
            "This will also remove any associated deployment run history.\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        error = delete_instance(self._conn, self._selected_id)
        if error:
            QMessageBox.warning(self, "Cannot Delete", error)
            return

        # Clear status cache for deleted instance
        self._status_cache.pop(self._selected_id, None)
        self._selected_id = None
        self._detail_group.setVisible(False)
        self.refresh(self._conn)
        self.instance_created.emit()

    # ── Deploy Wizard ─────────────────────────────────────────────

    def _on_start_wizard(self) -> None:
        if not self._conn:
            QMessageBox.information(
                self,
                "No Connection",
                "No client database connection available.",
            )
            return

        if not self._master_db_path or not self._client_id:
            QMessageBox.information(
                self,
                "No Client",
                "No active client. Select a client from the Clients tab first.",
            )
            return

        from automation.core.deployment.wizard_logic import get_pre_selection
        from automation.ui.deployment.deploy_wizard.wizard_dialog import (
            DeployWizard,
        )

        pre = get_pre_selection(self._master_db_path, self._client_id)
        wizard = DeployWizard(
            conn=self._conn,
            pre_selection=pre,
            master_db_path=self._master_db_path,
            client_id=self._client_id,
            parent=self,
        )
        wizard.exec()

        # Refresh instances after wizard completes (wizard may create one)
        if self._conn:
            self.refresh(self._conn)
            self.instance_created.emit()

    # ── New instance form ──────────────────────────────────────────

    def _on_new(self) -> None:
        self._new_form.setVisible(True)
        self._new_name.clear()
        self._new_code.clear()
        self._new_env.setCurrentIndex(0)
        self._new_url.clear()
        self._new_username.clear()
        self._new_password.clear()
        self._new_desc.clear()
        self._new_default.setChecked(not self._instances)

    def _on_cancel_new(self) -> None:
        self._new_form.setVisible(False)

    def _on_create(self) -> None:
        if not self._conn:
            return

        name = self._new_name.text().strip()
        code = self._new_code.text().strip().upper()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if not code or len(code) < 2 or len(code) > 10:
            QMessageBox.warning(
                self, "Validation",
                "Code must be 2-10 uppercase letters/digits, starting with a letter.",
            )
            return

        environment = self._new_env.currentText()
        try:
            new_id = create_instance(
                self._conn,
                name=name,
                code=code,
                environment=environment,
                url=self._new_url.text().strip() or None,
                username=self._new_username.text().strip() or None,
                password=self._new_password.text() or None,
                description=self._new_desc.text().strip() or None,
                is_default=self._new_default.isChecked(),
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Error", f"Could not create instance: {exc}"
            )
            return

        self._new_form.setVisible(False)
        self._selected_id = new_id
        self.refresh(self._conn)
        self.instance_created.emit()
