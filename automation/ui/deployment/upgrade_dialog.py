"""Modal dialog that runs an EspoCRM in-place upgrade.

Opened from the Deploy entry's Upgrade EspoCRM button. Shows current
and latest versions, four phase status cards, and a streaming log.
Major-version jumps trigger a confirmation dialog before the worker
starts.

See PRDs/product/features/feat-server-management.md §6.3.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
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

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.upgrade_ssh import (
    is_major_upgrade,
    is_upgrade_available,
)

logger = logging.getLogger(__name__)


LOG_COLORS: dict[str, str] = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
}

PHASE_INFO: list[tuple[str, str]] = [
    ("Phase 1: Pre-upgrade Checks", "Verify container is up and read current version"),
    ("Phase 2: Backup", "Dump database and archive data volume"),
    ("Phase 3: Run Upgrade", "Run EspoCRM CLI upgrader inside the container"),
    ("Phase 4: Verification", "Confirm site responds and version reads back"),
]


class PhaseCard(QFrame):
    """A single upgrade phase status card."""

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

        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(desc_label)

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
        styles = {
            "not_started": ("#9E9E9E", "Not Started"),
            "in_progress": ("#2196F3", "Running..."),
            "completed": ("#4CAF50", "Completed"),
            "failed": ("#F44336", "Failed \u2014 see log"),
        }
        color, label = styles.get(status, styles["not_started"])
        self._indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._status_label.setText(label)
        self._status_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )

        if status == "failed" and error:
            self._error_detail.setText(error)
            self._error_detail.setVisible(True)
        else:
            self._error_detail.setVisible(False)


class UpgradeDialog(QDialog):
    """Modal dialog that runs an EspoCRM in-place upgrade.

    :param config: Hydrated InstanceDeployConfig (mutated as worker runs).
    :param db_path: Path to the per-client database file.
    :param instance_name: Human-readable name for the title.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        instance_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path
        self.instance_name = instance_name
        self._worker = None

        self.setWindowTitle(f"Upgrade EspoCRM — {instance_name}")
        self.setModal(True)
        self.resize(800, 720)

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QGroupBox("Versions")
        header_layout = QVBoxLayout(header)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel(
            f"<b>{self.instance_name}</b> \u2014 {self.config.domain}"
        ))
        title_row.addStretch()
        header_layout.addLayout(title_row)

        version_row = QHBoxLayout()
        self._version_label = QLabel("")
        version_row.addWidget(self._version_label)
        version_row.addStretch()
        self._upgrade_badge = QLabel("")
        version_row.addWidget(self._upgrade_badge)
        header_layout.addLayout(version_row)

        layout.addWidget(header)
        self._refresh_version_display()

        self._phase_cards: list[PhaseCard] = []
        for i, (title, desc) in enumerate(PHASE_INFO):
            card = PhaseCard(i + 1, title, desc, self)
            self._phase_cards.append(card)
            layout.addWidget(card)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Upgrade")
        self._run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

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

    # ── Version display ───────────────────────────────────────────

    def _refresh_version_display(self) -> None:
        current = self.config.current_espocrm_version or "unknown"
        latest = self.config.latest_espocrm_version or "unknown"
        self._version_label.setText(
            f"Current: <b>{current}</b> \u2014 Latest: <b>{latest}</b>"
        )

        if is_upgrade_available(
            self.config.current_espocrm_version,
            self.config.latest_espocrm_version,
        ):
            self._upgrade_badge.setText("\u25cf Upgrade Available")
            self._upgrade_badge.setStyleSheet(
                "color: #FFA726; font-weight: bold;"
            )
        elif self.config.current_espocrm_version:
            self._upgrade_badge.setText("\u25cf Up to date")
            self._upgrade_badge.setStyleSheet(
                "color: #4CAF50; font-weight: bold;"
            )
        else:
            self._upgrade_badge.setText("")

    # ── Run flow ──────────────────────────────────────────────────

    def _on_run(self) -> None:
        if self._worker is not None:
            self.append_log(
                "An upgrade is already in progress.", "warning"
            )
            return

        if (
            self.config.current_espocrm_version
            and not is_upgrade_available(
                self.config.current_espocrm_version,
                self.config.latest_espocrm_version,
            )
        ):
            reply = QMessageBox.question(
                self,
                "No Upgrade Detected",
                "EspoCRM appears to already be up to date "
                f"({self.config.current_espocrm_version}). "
                "Run the upgrade flow anyway?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if is_major_upgrade(
            self.config.current_espocrm_version,
            self.config.latest_espocrm_version,
        ):
            reply = QMessageBox.warning(
                self,
                "Major Version Upgrade",
                f"This is a major version upgrade "
                f"({self.config.current_espocrm_version} \u2192 "
                f"{self.config.latest_espocrm_version}).\n\n"
                "Major upgrades can introduce breaking changes and may "
                "require manual configuration adjustments. Review the "
                "EspoCRM release notes before proceeding.\n\nContinue?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for card in self._phase_cards:
            card.set_status("not_started")
        self._run_btn.setEnabled(False)
        self._start_worker()

    def _start_worker(self) -> None:
        from automation.ui.deployment.upgrade_worker import UpgradeWorker

        self._worker = UpgradeWorker(
            config=self.config, db_path=self.db_path, parent=self
        )
        self._worker.log_line.connect(self.append_log)
        self._worker.phase_started.connect(self.on_phase_started)
        self._worker.phase_completed.connect(self.on_phase_completed)
        self._worker.phase_failed.connect(self.on_phase_failed)
        self._worker.version_detected.connect(self.on_version_detected)
        self._worker.verify_results.connect(self.on_verify_results)
        self._worker.upgrade_finished.connect(self.on_upgrade_finished)
        self._worker.start()

    # ── Worker signal handlers ────────────────────────────────────

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

    def on_phase_started(self, phase: int) -> None:
        if 1 <= phase <= 4:
            self._phase_cards[phase - 1].set_status("in_progress")

    def on_phase_completed(self, phase: int) -> None:
        if 1 <= phase <= 4:
            self._phase_cards[phase - 1].set_status("completed")

    def on_phase_failed(self, phase: int, error: str) -> None:
        if 1 <= phase <= 4:
            self._phase_cards[phase - 1].set_status("failed", error)

    def on_version_detected(self, current: str, latest: str) -> None:
        if current:
            self.config.current_espocrm_version = current
        if latest:
            self.config.latest_espocrm_version = latest
        self._refresh_version_display()

    def on_verify_results(self, results: list[dict]) -> None:
        self.append_log("", "info")
        self.append_log("=== Verification Results ===", "info")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            level = "info" if r["passed"] else "error"
            self.append_log(f"  {status}: {r['check']}", level)

    def on_upgrade_finished(self, success: bool) -> None:
        self._worker = None
        self._run_btn.setEnabled(True)
        self._refresh_version_display()
        if success:
            self.append_log("Upgrade completed successfully.", "info")
        else:
            self.append_log("Upgrade failed.", "error")

    # ── Log helpers ───────────────────────────────────────────────

    def _on_copy_log(self) -> None:
        from PySide6.QtWidgets import QApplication

        text = self._log_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.append_log("Log copied to clipboard.", "info")

    def _on_save_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "", "Log Files (*.log);;Text Files (*.txt)"
        )
        if path:
            Path(path).write_text(
                self._log_edit.toPlainText(), encoding="utf-8"
            )
            self.append_log(f"Log saved to {path}", "info")
