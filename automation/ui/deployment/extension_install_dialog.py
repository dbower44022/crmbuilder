"""Modal dialog that runs an EspoCRM extension install or re-install.

Opened from the Extensions entry. Shows the parsed manifest, the slot
check against any matching license, four phase status cards, and a
streaming log. Mirrors ``UpgradeDialog`` end-to-end.

See PRDs/product/features/feat-server-management.md (extensions add-on).
"""

from __future__ import annotations

import logging
import sqlite3
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
from automation.core.deployment.extension_repo import (
    SlotCheckResult,
    check_slot_availability,
    find_license,
    load_install,
)
from automation.core.deployment.extension_ssh import (
    ExtensionManifest,
    parse_extension_manifest,
)

logger = logging.getLogger(__name__)


LOG_COLORS: dict[str, str] = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
}

PHASE_INFO: list[tuple[str, str]] = [
    ("Phase 1: Pre-check", "Verify container is up"),
    ("Phase 2: Backup", "Dump database and archive data volume"),
    ("Phase 3: Install", "Upload zip and run EspoCRM CLI extension install"),
    ("Phase 4: Verification", "Confirm site responds after install"),
]


class PhaseCard(QFrame):
    """A single install phase status card. Identical to UpgradeDialog's."""

    def __init__(
        self, phase_num: int, title: str, description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.phase_num = phase_num
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        header = QHBoxLayout()
        self._indicator = QLabel("●")
        self._indicator.setFixedWidth(16)
        header.addWidget(self._indicator)
        header.addWidget(QLabel(f"<b>{title}</b>"))
        header.addStretch()
        self._status_label = QLabel("Not Started")
        header.addWidget(self._status_label)
        layout.addLayout(header)

        desc = QLabel(description)
        desc.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(desc)

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
            "failed": ("#F44336", "Failed — see log"),
            "skipped": ("#9E9E9E", "Skipped"),
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


class ExtensionInstallDialog(QDialog):
    """Modal dialog that installs (or re-installs) an EspoCRM extension.

    :param config: Hydrated InstanceDeployConfig for the target instance.
    :param db_path: Path to the per-client database file.
    :param instance_name: Human-readable instance name for the title.
    :param zip_path: Local path to the extension zip.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        config: InstanceDeployConfig,
        db_path: str,
        instance_name: str,
        zip_path: str | Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = db_path
        self.instance_name = instance_name
        self.zip_path = Path(zip_path)
        self._worker = None
        self._manifest: ExtensionManifest | None = None
        self._slot_check: SlotCheckResult | None = None
        self._license_id: int | None = None
        self._existing_version: str | None = None

        self.setWindowTitle(f"Install Extension — {instance_name}")
        self.setModal(True)
        self.resize(800, 760)

        self._build_ui()
        self._inspect_zip_and_state()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info_group = QGroupBox("Extension")
        info_layout = QVBoxLayout(info_group)
        self._title_label = QLabel("")
        self._title_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(self._title_label)
        self._zip_label = QLabel("")
        self._zip_label.setStyleSheet("color: gray; font-size: 11px;")
        info_layout.addWidget(self._zip_label)
        layout.addWidget(info_group)

        self._slot_group = QGroupBox("License + slot usage")
        slot_layout = QVBoxLayout(self._slot_group)
        self._slot_label = QLabel("")
        self._slot_label.setWordWrap(True)
        slot_layout.addWidget(self._slot_label)
        layout.addWidget(self._slot_group)

        self._phase_cards: list[PhaseCard] = []
        for i, (title, desc) in enumerate(PHASE_INFO):
            card = PhaseCard(i + 1, title, desc, self)
            self._phase_cards.append(card)
            layout.addWidget(card)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Install")
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

    # ── Pre-flight inspection ─────────────────────────────────────

    def _inspect_zip_and_state(self) -> None:
        """Parse manifest, look up license + prior install, refresh UI."""
        try:
            self._manifest = parse_extension_manifest(self.zip_path)
        except (FileNotFoundError, ValueError) as exc:
            self._title_label.setText(
                f"<b>Could not read manifest:</b> {exc}"
            )
            self._zip_label.setText(str(self.zip_path))
            self._run_btn.setEnabled(False)
            return

        self._title_label.setText(
            f"<b>{self._manifest.name}</b> "
            f"v{self._manifest.version}"
            + (f" — by {self._manifest.author}"
               if self._manifest.author else "")
        )
        self._zip_label.setText(str(self.zip_path))

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                license_obj = find_license(conn, self._manifest.name)
                existing = load_install(
                    conn, self.config.instance_id, self._manifest.name,
                )
                self._existing_version = (
                    existing.extension_version if existing else None
                )
                if license_obj is not None:
                    self._license_id = license_obj.id
                    self._slot_check = check_slot_availability(
                        conn, license_obj.id, self.config.instance_id,
                    )
            finally:
                conn.close()
        except Exception as exc:
            logger.exception("Slot inspection failed")
            self._slot_label.setText(
                f"Could not read license state: {exc}"
            )
            return

        self._refresh_slot_panel()
        self._refresh_run_button()

    def _refresh_slot_panel(self) -> None:
        if self._slot_check is None:
            self._slot_label.setText(
                "<i>No license registered for this extension. Install will "
                "proceed unlicensed.</i>"
            )
            return

        u = self._slot_check.usage
        lines = [
            f"<b>License:</b> {u.extension_name}",
            (
                f"<b>Production:</b> "
                f"{len(u.production_installs)}/{u.max_production}"
                + (
                    " — " + ", ".join(s.instance_code
                                      for s in u.production_installs)
                    if u.production_installs else ""
                )
            ),
            (
                f"<b>Non-production:</b> "
                f"{len(u.nonproduction_installs)}/{u.max_nonproduction}"
                + (
                    " — " + ", ".join(s.instance_code
                                      for s in u.nonproduction_installs)
                    if u.nonproduction_installs else ""
                )
            ),
        ]
        if self._slot_check.is_reinstall:
            lines.append(
                "<i>This is a re-install on an existing slot — no new "
                "slot will be consumed.</i>"
            )
        elif self._slot_check.allowed:
            lines.append(
                "<i>This install will consume one new slot.</i>"
            )
        else:
            lines.append(
                f"<b style='color:#F44336;'>Blocked:</b> "
                f"{self._slot_check.reason}"
            )
        self._slot_label.setText("<br>".join(lines))

    def _refresh_run_button(self) -> None:
        if self._manifest is None:
            self._run_btn.setEnabled(False)
            return
        if self._slot_check is not None and not self._slot_check.allowed:
            self._run_btn.setEnabled(False)
            self._run_btn.setText("Install (blocked by license)")
            return

        if self._existing_version is None:
            self._run_btn.setText("Install")
        elif self._existing_version == self._manifest.version:
            self._run_btn.setText(
                f"Re-install (same version {self._manifest.version})"
            )
        else:
            self._run_btn.setText(
                f"Replace v{self._existing_version} → "
                f"v{self._manifest.version}"
            )
        self._run_btn.setEnabled(True)

    # ── Run flow ──────────────────────────────────────────────────

    def _on_run(self) -> None:
        if self._worker is not None:
            self.append_log("An install is already in progress.", "warning")
            return
        if self._manifest is None:
            return

        if (
            self._existing_version
            and self._existing_version == self._manifest.version
        ):
            reply = QMessageBox.question(
                self, "Re-install same version",
                f"{self._manifest.name} v{self._manifest.version} is "
                "already installed. Re-install it anyway?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for card in self._phase_cards:
            card.set_status("not_started")
        self._run_btn.setEnabled(False)
        self._start_worker()

    def _start_worker(self) -> None:
        from automation.ui.deployment.extension_worker import (
            ExtensionInstallWorker,
        )

        self._worker = ExtensionInstallWorker(
            config=self.config,
            db_path=self.db_path,
            zip_path=self.zip_path,
            license_id=self._license_id,
            parent=self,
        )
        self._worker.log_line.connect(self.append_log)
        self._worker.phase_started.connect(self.on_phase_started)
        self._worker.phase_completed.connect(self.on_phase_completed)
        self._worker.phase_failed.connect(self.on_phase_failed)
        self._worker.install_finished.connect(self.on_install_finished)
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

    def on_install_finished(self, success: bool) -> None:
        self._worker = None
        self._run_btn.setEnabled(True)
        if success:
            self.append_log("Extension install complete.", "info")
        else:
            self.append_log("Extension install failed.", "error")

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
