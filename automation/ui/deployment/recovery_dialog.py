"""Recovery & Reset modal dialog.

Two operations behind separate buttons:

1. **Reset Admin Credentials** — runs a SQL UPDATE in the EspoCRM
   database container to set a new admin username and password. Used
   when admin access has been lost but the deployment is healthy.

2. **Full Database Reset** — destructive teardown of the entire
   deployment, then reinstall from scratch. Behind a typed-confirmation
   gate. Wipes all data.

See PRDs/product/features/feat-server-management.md §6.4.
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig

logger = logging.getLogger(__name__)


LOG_COLORS: dict[str, str] = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
}

FULL_RESET_CONFIRM_PHRASE = "DELETE ALL DATA"


class RecoveryDialog(QDialog):
    """Modal dialog for the two recovery operations.

    :param config: Hydrated InstanceDeployConfig.
    :param db_path: Path to the per-client database.
    :param instance_id: Instance.id this dialog operates on.
    :param instance_name: Human-readable instance name for the title.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        instance_id: int,
        instance_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path
        self.instance_id = instance_id
        self.instance_name = instance_name
        self._worker = None

        self.setWindowTitle(f"Recovery & Reset — {instance_name}")
        self.setModal(True)
        self.resize(720, 700)

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        intro = QLabel(
            f"<b>{self.instance_name}</b> \u2014 {self.config.domain}"
        )
        layout.addWidget(intro)

        layout.addWidget(self._build_credential_reset_group())
        layout.addWidget(self._build_full_reset_group())

        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Log</b>"))
        log_header.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        log_header.addWidget(close_btn)
        layout.addLayout(log_header)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QFont("Monospace", 10))
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

    def _build_credential_reset_group(self) -> QGroupBox:
        group = QGroupBox("Reset Admin Credentials")
        group_layout = QVBoxLayout(group)

        explanation = QLabel(
            "Updates the EspoCRM admin user's username and password "
            "directly in the database. Use this only when you have "
            "lost access; do not use to rotate credentials in normal "
            "operation."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #555; font-size: 11px;")
        group_layout.addWidget(explanation)

        form = QFormLayout()
        self._cred_username = QLineEdit("admin")
        form.addRow("New Username:", self._cred_username)
        self._cred_password = QLineEdit()
        self._cred_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("New Password:", self._cred_password)
        group_layout.addLayout(form)

        self._cred_run_btn = QPushButton("Reset Admin Credentials")
        self._cred_run_btn.clicked.connect(self._on_reset_credentials)
        group_layout.addWidget(self._cred_run_btn)

        return group

    def _build_full_reset_group(self) -> QGroupBox:
        group = QGroupBox("Full Database Reset")
        group_layout = QVBoxLayout(group)

        warning = QLabel(
            "<b>DESTRUCTIVE.</b> This tears down all containers and "
            "volumes, removes the EspoCRM install directory, and "
            "re-runs the installer from scratch. <b>All data will be "
            "permanently lost.</b> Take a backup first if you are not "
            "certain."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "color: #F44336; background: #2a1a1a; padding: 6px; "
            "border-radius: 3px; font-size: 11px;"
        )
        group_layout.addWidget(warning)

        form = QFormLayout()
        self._reset_admin_user = QLineEdit("admin")
        form.addRow("New Admin Username:", self._reset_admin_user)
        self._reset_admin_pass = QLineEdit()
        self._reset_admin_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("New Admin Password:", self._reset_admin_pass)

        self._reset_confirm = QLineEdit()
        self._reset_confirm.setPlaceholderText(FULL_RESET_CONFIRM_PHRASE)
        form.addRow("Type to confirm:", self._reset_confirm)
        group_layout.addLayout(form)

        confirm_hint = QLabel(
            f"Type <code>{FULL_RESET_CONFIRM_PHRASE}</code> exactly to "
            "enable the button below."
        )
        confirm_hint.setStyleSheet("color: #555; font-size: 11px;")
        group_layout.addWidget(confirm_hint)

        self._reset_run_btn = QPushButton("Run Full Reset")
        self._reset_run_btn.setStyleSheet(
            "QPushButton { background-color: #F44336; color: white; "
            "border-radius: 4px; padding: 8px 18px; font-size: 13px; }"
            "QPushButton:hover { background-color: #C62828; }"
            "QPushButton:disabled { background-color: #666; color: #aaa; }"
        )
        self._reset_run_btn.setEnabled(False)
        self._reset_run_btn.clicked.connect(self._on_full_reset)
        self._reset_confirm.textChanged.connect(
            self._update_reset_btn_state
        )
        group_layout.addWidget(self._reset_run_btn)

        return group

    def _update_reset_btn_state(self) -> None:
        ready = self._reset_confirm.text() == FULL_RESET_CONFIRM_PHRASE
        self._reset_run_btn.setEnabled(ready)

    # ── Credential reset ──────────────────────────────────────────

    def _on_reset_credentials(self) -> None:
        if self._worker is not None:
            self.append_log("An operation is already in progress.", "warning")
            return

        username = self._cred_username.text().strip()
        password = self._cred_password.text()
        if not username or not password:
            QMessageBox.warning(
                self, "Missing Fields",
                "Both username and password are required.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Credential Reset",
            f"Reset the EspoCRM admin to:\n\nUsername: {username}\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from automation.ui.deployment.recovery_worker import (
            CredentialResetWorker,
        )

        self._cred_run_btn.setEnabled(False)
        self._worker = CredentialResetWorker(
            self.config, self.db_path, self.instance_id,
            username, password, parent=self,
        )
        self._worker.log_line.connect(self.append_log)
        self._worker.finished_ok.connect(self._on_credential_reset_ok)
        self._worker.finished_error.connect(self._on_credential_reset_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_credential_reset_ok(self, username: str) -> None:
        self.append_log(
            f"Admin credentials reset; new username: {username}", "info"
        )
        QMessageBox.information(
            self, "Credentials Reset",
            f"Admin credentials updated. New username: {username}",
        )

    def _on_credential_reset_error(self, error: str) -> None:
        self.append_log(error, "error")
        QMessageBox.critical(self, "Credential Reset Failed", error)

    # ── Full reset ────────────────────────────────────────────────

    def _on_full_reset(self) -> None:
        if self._worker is not None:
            self.append_log("An operation is already in progress.", "warning")
            return

        username = self._reset_admin_user.text().strip()
        password = self._reset_admin_pass.text()
        if not username or not password:
            QMessageBox.warning(
                self, "Missing Fields",
                "Both admin username and password are required.",
            )
            return

        if self._reset_confirm.text() != FULL_RESET_CONFIRM_PHRASE:
            return  # button should already be disabled, defensive

        reply = QMessageBox.warning(
            self,
            "Confirm Full Reset",
            "This will permanently delete <b>all data</b> on the "
            "Droplet and reinstall EspoCRM from scratch.\n\n"
            "This operation cannot be undone.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        import secrets

        new_db_password = secrets.token_urlsafe(16)

        from automation.ui.deployment.recovery_worker import FullResetWorker

        self._reset_run_btn.setEnabled(False)
        self._worker = FullResetWorker(
            self.config, self.db_path, self.instance_id,
            username, password, new_db_password, parent=self,
        )
        self._worker.log_line.connect(self.append_log)
        self._worker.phase_started.connect(self._on_phase)
        self._worker.phase_failed.connect(self._on_phase_failed)
        self._worker.verify_results.connect(self._on_verify_results)
        self._worker.finished_ok.connect(self._on_full_reset_ok)
        self._worker.finished_error.connect(self._on_full_reset_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_phase(self, phase: int) -> None:
        names = {1: "Teardown", 2: "Install", 3: "Post-Install", 4: "Verification"}
        self.append_log(
            f"Phase {phase} started: {names.get(phase, '')}", "info"
        )

    def _on_phase_failed(self, phase: int, error: str) -> None:
        self.append_log(f"Phase {phase} failed: {error}", "error")

    def _on_verify_results(self, results: list[dict]) -> None:
        self.append_log("=== Verification Results ===", "info")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            level = "info" if r["passed"] else "error"
            self.append_log(f"  {status}: {r['check']}", level)

    def _on_full_reset_ok(self) -> None:
        self.append_log("Full reset completed successfully.", "info")
        QMessageBox.information(
            self, "Reset Complete",
            "EspoCRM has been reinstalled from scratch. Old data is "
            "gone. Use the new admin credentials to log in.",
        )

    def _on_full_reset_error(self, error: str) -> None:
        QMessageBox.critical(self, "Full Reset Failed", error)

    # ── Worker lifecycle / log ────────────────────────────────────

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._cred_run_btn.setEnabled(True)
        self._update_reset_btn_state()

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
