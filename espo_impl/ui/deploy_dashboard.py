"""Deployment Dashboard widget — phase status, log, and cert status."""

import logging
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.deploy_manager import cert_days_remaining
from espo_impl.core.models import DeployConfig, InstanceProfile

logger = logging.getLogger(__name__)

LOG_COLORS: dict[str, str] = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
}

PHASE_INFO: list[tuple[str, str]] = [
    ("Phase 1: Server Preparation", "Update packages, install Docker, configure swap and firewall"),
    ("Phase 2: EspoCRM Installation", "Download and run the official EspoCRM installer script"),
    ("Phase 3: Post-Install Configuration", "Verify containers, cron, and read SSL certificate"),
    ("Phase 4: Verification", "Run all deployment verification checks"),
]


class PhaseCard(QFrame):
    """A single phase status card.

    :param phase_num: Phase number (1-4).
    :param title: Phase title.
    :param description: One-line description.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        phase_num: int,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.phase_num = phase_num
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        # Header row: indicator + title + status
        header = QHBoxLayout()
        self._indicator = QLabel("\u25cf")
        self._indicator.setFixedWidth(16)
        header.addWidget(self._indicator)

        title_label = QLabel(f"<b>{title}</b>")
        header.addWidget(title_label)
        header.addStretch()

        self._status_label = QLabel("Not Started")
        header.addWidget(self._status_label)
        layout.addLayout(header)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(desc_label)

        # Error detail (hidden by default)
        self._error_detail = QLabel("")
        self._error_detail.setWordWrap(True)
        self._error_detail.setStyleSheet(
            "color: #F44336; background: #2a1a1a; padding: 4px; "
            "border-radius: 3px; font-size: 11px;"
        )
        self._error_detail.setVisible(False)
        layout.addWidget(self._error_detail)

        self.set_status("not_started")

    def set_status(self, status: str, error: str = "") -> None:
        """Update the phase status display.

        :param status: One of 'not_started', 'in_progress', 'completed', 'failed'.
        :param error: Error message (for failed status).
        """
        styles = {
            "not_started": ("#9E9E9E", "Not Started"),
            "in_progress": ("#2196F3", "Running..."),
            "completed": ("#4CAF50", "Completed"),
            "failed": ("#F44336", "Failed \u2014 see log"),
        }
        color, label = styles.get(status, styles["not_started"])
        self._indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._status_label.setText(label)
        self._status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        if status == "failed" and error:
            self._error_detail.setText(error)
            self._error_detail.setVisible(True)
        else:
            self._error_detail.setVisible(False)


class DeployDashboard(QWidget):
    """Deployment Dashboard with phase cards, action buttons, and log.

    :param profile: Instance profile.
    :param config: Deployment configuration.
    :param instances_dir: Path to instances directory.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        profile: InstanceProfile,
        config: DeployConfig,
        instances_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.config = config
        self.instances_dir = instances_dir
        self._worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dashboard layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Environment header
        header = QGroupBox("Environment")
        header_layout = QVBoxLayout(header)

        info_row = QHBoxLayout()
        info_row.addWidget(QLabel(
            f"<b>{self.profile.name}</b> \u2014 "
            f"{self.config.full_domain}"
        ))
        info_row.addWidget(QLabel(f"IP: {self.config.droplet_ip}"))
        info_row.addStretch()

        self._cert_badge = QLabel("")
        info_row.addWidget(self._cert_badge)
        header_layout.addLayout(info_row)

        self._edit_btn = QPushButton("Edit Configuration")
        self._edit_btn.clicked.connect(self._on_edit_config)
        header_layout.addWidget(self._edit_btn)

        layout.addWidget(header)

        self.update_cert_badge(self.config.cert_expiry_date)

        # Phase cards
        self._phase_cards: list[PhaseCard] = []
        for i, (title, desc) in enumerate(PHASE_INFO):
            card = PhaseCard(i + 1, title, desc, self)
            self._phase_cards.append(card)
            layout.addWidget(card)

        # Action buttons
        btn_row = QHBoxLayout()
        self._deploy_all_btn = QPushButton("Deploy All")
        self._deploy_all_btn.clicked.connect(self._on_deploy_all)
        btn_row.addWidget(self._deploy_all_btn)

        self._verify_btn = QPushButton("Run Verification Only")
        self._verify_btn.clicked.connect(self._on_verify_only)
        btn_row.addWidget(self._verify_btn)

        self._retry_btn = QPushButton("Retry Failed Phase")
        self._retry_btn.clicked.connect(self._on_retry_failed)
        btn_row.addWidget(self._retry_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Log window
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Log</b>"))
        log_header.addStretch()

        copy_btn = QPushButton("Copy Log")
        copy_btn.clicked.connect(self._on_copy_log)
        log_header.addWidget(copy_btn)

        save_btn = QPushButton("Save Log to File")
        save_btn.clicked.connect(self._on_save_log)
        log_header.addWidget(save_btn)

        layout.addLayout(log_header)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QFont("Monospace", 10))
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self._log_edit, stretch=1)

        self._failed_phase: int | None = None

    # ── Public API ─────────────────────────────────────────────────

    def update_cert_badge(self, expiry_date: str | None) -> None:
        """Update the SSL certificate status badge.

        :param expiry_date: ISO date string or None.
        """
        days = cert_days_remaining(expiry_date)
        if days is None:
            self._cert_badge.setText("\u25cf Unknown")
            self._cert_badge.setStyleSheet("color: #9E9E9E; font-weight: bold;")
        elif days > 30:
            self._cert_badge.setText(f"\u25cf Valid ({days} days)")
            self._cert_badge.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif days >= 14:
            self._cert_badge.setText(f"\u25cf Expiring Soon ({days} days)")
            self._cert_badge.setStyleSheet("color: #FFC107; font-weight: bold;")
        else:
            self._cert_badge.setText(f"\u25cf Critical \u2014 Renew Now ({days} days)")
            self._cert_badge.setStyleSheet("color: #F44336; font-weight: bold;")

    def append_log(self, message: str, level: str = "info") -> None:
        """Append a line to the log window.

        :param message: Log message.
        :param level: 'info', 'warning', or 'error'.
        """
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        hex_color = LOG_COLORS.get(level, LOG_COLORS["info"])
        fmt.setForeground(QColor(hex_color))
        fmt.setFont(QFont("Monospace", 10))

        if not self._log_edit.document().isEmpty():
            cursor.insertText("\n", fmt)
        cursor.insertText(message, fmt)

        self._log_edit.setTextCursor(cursor)
        self._log_edit.ensureCursorVisible()

    def on_phase_started(self, phase: int) -> None:
        """Handle phase started signal."""
        if 1 <= phase <= 4:
            self._phase_cards[phase - 1].set_status("in_progress")

    def on_phase_completed(self, phase: int) -> None:
        """Handle phase completed signal."""
        if 1 <= phase <= 4:
            self._phase_cards[phase - 1].set_status("completed")

    def on_phase_failed(self, phase: int, error: str) -> None:
        """Handle phase failed signal."""
        if 1 <= phase <= 4:
            self._phase_cards[phase - 1].set_status("failed", error)
            self._failed_phase = phase

    def on_deployment_finished(self, success: bool) -> None:
        """Handle deployment completion."""
        self._worker = None
        if success:
            self.append_log("Deployment completed successfully.", "info")
        else:
            self.append_log("Deployment failed.", "error")

    def on_verify_results(self, results: list[dict]) -> None:
        """Handle verification results."""
        self.append_log("")
        self.append_log("=== Verification Results ===")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            level = "info" if r["passed"] else "error"
            self.append_log(f"  {status}: {r['check']}", level)

    # ── Action handlers ────────────────────────────────────────────

    def _on_deploy_all(self) -> None:
        """Start full deployment from Phase 1."""
        if self._worker is not None:
            self.append_log("A deployment is already in progress.", "warning")
            return
        self._reset_phase_cards()
        self._start_deploy(start_phase=1)

    def _on_verify_only(self) -> None:
        """Run Phase 4 verification only."""
        if self._worker is not None:
            self.append_log("A deployment is already in progress.", "warning")
            return
        if self.config.deployed_at is None:
            QMessageBox.warning(
                self,
                "No Deployment Found",
                "No completed deployment found for this instance. "
                "Please run Deploy All first to install EspoCRM on "
                "the server before running verification.",
            )
            return
        self._start_deploy(start_phase=4)

    def _on_retry_failed(self) -> None:
        """Retry from the failed phase."""
        if self._worker is not None:
            self.append_log("A deployment is already in progress.", "warning")
            return
        if self._failed_phase is None:
            self.append_log("No failed phase to retry.", "warning")
            return
        phase = self._failed_phase
        self._failed_phase = None
        # Reset failed and subsequent cards
        for i in range(phase - 1, 4):
            self._phase_cards[i].set_status("not_started")
        self._start_deploy(start_phase=phase)

    def _start_deploy(self, start_phase: int) -> None:
        """Launch the deploy worker."""
        from espo_impl.workers.deploy_worker import DeployWorker

        self._worker = DeployWorker(
            config=self.config,
            profile=self.profile,
            instances_dir=self.instances_dir,
            start_phase=start_phase,
            parent=self,
        )
        self._worker.log_line.connect(self.append_log)
        self._worker.phase_started.connect(self.on_phase_started)
        self._worker.phase_completed.connect(self.on_phase_completed)
        self._worker.phase_failed.connect(self.on_phase_failed)
        self._worker.deployment_finished.connect(self.on_deployment_finished)
        self._worker.verify_results.connect(self.on_verify_results)
        # cert_expiry_updated is connected by the parent (MainWindow)
        self._worker.start()

    def _reset_phase_cards(self) -> None:
        """Reset all phase cards to not_started."""
        for card in self._phase_cards:
            card.set_status("not_started")
        self._failed_phase = None

    def _on_edit_config(self) -> None:
        """Open the deploy wizard in edit mode."""
        from espo_impl.ui.deploy_wizard import DeployWizard

        wizard = DeployWizard(
            self.profile, self.instances_dir, self.config, self
        )
        if wizard.exec():
            # Wizard saved — refresh config
            from espo_impl.core.deploy_manager import load_deploy_config

            updated = load_deploy_config(
                self.instances_dir, self.profile.slug
            )
            if updated:
                self.config = updated

    def _on_copy_log(self) -> None:
        """Copy log content to clipboard."""
        from PySide6.QtWidgets import QApplication

        text = self._log_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.append_log("Log copied to clipboard.", "info")
        else:
            self.append_log("Log is empty.", "warning")

    def _on_save_log(self) -> None:
        """Save log content to a file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "", "Log Files (*.log);;Text Files (*.txt)"
        )
        if path:
            Path(path).write_text(
                self._log_edit.toPlainText(), encoding="utf-8"
            )
            self.append_log(f"Log saved to {path}", "info")
