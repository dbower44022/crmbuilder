"""Progress dialog for YAML configuration operations.

Shows a scrolling log of commands being processed, a progress bar with
completion percentage, and a cancel button.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    YamlFileInfo,
    load_instance_detail,
)

# Color map for log output levels
_LOG_COLORS = {
    "info": "#D4D4D4",
    "warning": "#FFC107",
    "error": "#F44336",
    "success": "#4CAF50",
}

# RunWorker color names → log levels
_COLOR_TO_LEVEL = {
    "green": "success",
    "red": "error",
    "yellow": "warning",
    "gray": "info",
    "white": "info",
}


def _count_operations(program) -> int:
    """Count the total expected operations in a ProgramFile.

    Counts fields, layouts, relationships, and entity actions to
    give a rough total for progress tracking.
    """
    from espo_impl.core.models import EntityAction

    total = 0
    for entity in program.entities:
        if entity.action in (
            EntityAction.DELETE, EntityAction.CREATE,
            EntityAction.DELETE_AND_CREATE,
        ):
            total += 1
        if entity.action != EntityAction.DELETE:
            total += len(entity.fields)
            total += len(entity.layouts)
    total += len(program.relationships)
    return max(total, 1)  # Avoid division by zero


class ConfigureProgressDialog(QDialog):
    """Modal progress dialog for YAML configuration operations.

    :param files: YAML files to process.
    :param operation: "run" or "verify".
    :param instance: The active instance row.
    :param conn: Database connection (for loading instance credentials).
    :param output_entry: Optional OutputEntry for mirrored logging.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        files: list[YamlFileInfo],
        operation: str,
        instance: InstanceRow,
        conn,
        output_entry=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._files = files
        self._operation = operation
        self._instance = instance
        self._conn = conn
        self._output_entry = output_entry
        self._worker = None
        self._cancelled = False
        self._pending: list[tuple[YamlFileInfo, object]] = []
        self._total_ops = 0
        self._completed_ops = 0
        self._current_file_idx = 0
        self._total_files = len(files)
        self._current_file_info: YamlFileInfo | None = None
        # Per-file results: maps file path → (outcome, timestamp)
        self._file_results: dict[str, tuple[str, str]] = {}

        op_label = "Running" if operation == "run" else "Checking"
        self.setWindowTitle(f"{op_label} Configuration")
        self.setMinimumSize(700, 500)
        self.setModal(True)

        self._build_ui()
        self._load_and_start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Status header
        self._status_label = QLabel("Preparing...")
        self._status_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 4px;"
        )
        layout.addWidget(self._status_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        self._progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #555; border-radius: 3px; "
            "text-align: center; background: #2a2a2a; color: #D4D4D4; "
            "height: 22px; } "
            "QProgressBar::chunk { background-color: #1565C0; }"
        )
        layout.addWidget(self._progress_bar)

        # File progress label
        self._file_label = QLabel("")
        self._file_label.setStyleSheet("font-size: 11px; color: #9E9E9E;")
        layout.addWidget(self._file_label)

        # Log area
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Monospace", 10))
        self._log.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self._log, stretch=1)

        # Bottom row: cancel + close
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #E53935; color: white; "
            "border-radius: 4px; padding: 6px 18px; font-size: 12px; } "
            "QPushButton:hover { background-color: #C62828; }"
        )
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "border-radius: 4px; padding: 6px 18px; font-size: 12px; } "
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setVisible(False)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    # ── Startup ────────────────────────────────────────────────────

    def _load_and_start(self) -> None:
        """Load all YAML files and begin processing."""
        detail = load_instance_detail(self._conn, self._instance.id)
        if detail is None or not detail.url or not detail.username or not detail.password:
            self._append_log("Instance is missing URL or credentials.", "error")
            self._finish()
            return

        from espo_impl.core.config_loader import ConfigLoader
        from espo_impl.core.models import InstanceProfile

        self._profile = InstanceProfile(
            name=detail.name,
            url=detail.url,
            api_key=detail.username,
            auth_method="basic",
            secret_key=detail.password,
        )

        loader = ConfigLoader()
        for f in self._files:
            try:
                program = loader.load_program(Path(f.path))
                self._pending.append((f, program))
                self._total_ops += _count_operations(program)
            except Exception as exc:
                self._append_log(f"Failed to load {f.name}: {exc}", "error")

        if not self._pending:
            self._append_log("No valid YAML files to process.", "warning")
            self._finish()
            return

        self._run_next()

    # ── File processing ────────────────────────────────────────────

    def _run_next(self) -> None:
        """Start the RunWorker for the next pending file."""
        if self._cancelled or not self._pending:
            self._finish()
            return

        file_info, program = self._pending.pop(0)
        self._current_file_info = file_info
        self._current_program = program
        self._current_file_idx += 1
        self._current_started_at = datetime.now().isoformat(timespec="seconds")

        # Compute file hash for change detection
        try:
            raw = Path(file_info.path).read_bytes()
            self._current_file_hash = hashlib.sha256(raw).hexdigest()
        except OSError:
            self._current_file_hash = None

        op_label = "Running" if self._operation == "run" else "Checking"
        self._status_label.setText(
            f"{op_label}: {file_info.name}"
        )
        self._file_label.setText(
            f"File {self._current_file_idx} of {self._total_files}"
        )
        self._append_log("")
        self._append_log(
            f"=== {op_label}: {file_info.name} "
            f"({self._current_file_idx}/{self._total_files}) ===",
            "info",
        )

        from espo_impl.workers.run_worker import RunWorker

        self._worker = RunWorker(
            profile=self._profile,
            program=program,
            operation=self._operation,
            parent=self,
        )
        self._worker.output_line.connect(self._on_output_line)
        self._worker.finished_ok.connect(self._on_worker_ok)
        self._worker.finished_error.connect(self._on_worker_error)
        self._worker.start()

    def _on_output_line(self, text: str, color: str) -> None:
        """Handle a line of output from the RunWorker."""
        level = _COLOR_TO_LEVEL.get(color, "info")
        self._append_log(text, level)

        # Heuristic: lines starting with known result markers count as
        # completed operations for progress tracking.
        stripped = text.strip()
        if stripped and any(
            stripped.startswith(m)
            for m in ("[CREATE]", "[UPDATE]", "[SKIP", "[VERIFY", "[ERROR]")
        ):
            self._completed_ops += 1
            self._update_progress()

    def _on_worker_ok(self, _report) -> None:
        """Handle successful completion of one file."""
        self._worker = None
        self._append_log("Completed successfully.", "success")
        self._record_run("success")
        self._run_next()

    def _on_worker_error(self, error: str) -> None:
        """Handle failure of one file."""
        self._worker = None
        self._append_log(f"Error: {error}", "error")
        self._record_run("error", error)
        self._run_next()

    def _record_run(self, outcome: str, error_message: str | None = None) -> None:
        """Record the run result in memory and in the database."""
        if not self._current_file_info:
            return

        now = datetime.now()
        now_display = now.strftime("%Y-%m-%d %H:%M")
        now_iso = now.isoformat(timespec="seconds")
        self._file_results[self._current_file_info.path] = (outcome, now_display)

        # Persist to ConfigurationRun table
        if self._conn and self._instance:
            try:
                from automation.ui.deployment.deployment_logic import (
                    record_configuration_run,
                )

                file_version = None
                if self._current_program:
                    file_version = self._current_program.content_version

                record_configuration_run(
                    self._conn,
                    instance_id=self._instance.id,
                    file_name=self._current_file_info.name,
                    file_version=file_version,
                    file_hash=self._current_file_hash,
                    operation=self._operation,
                    outcome=outcome,
                    error_message=error_message,
                    started_at=self._current_started_at,
                    completed_at=now_iso,
                )
            except Exception as exc:
                self._append_log(
                    f"Warning: could not save run record: {exc}", "warning"
                )

    # ── Cancel ─────────────────────────────────────────────────────

    def _on_cancel(self) -> None:
        """Cancel the operation after the current file finishes."""
        self._cancelled = True
        self._pending.clear()
        self._append_log("")
        self._append_log("Cancellation requested — finishing current file...", "warning")
        self._cancel_btn.setText("Cancelling...")
        self._cancel_btn.setEnabled(False)

    # ── Finish ─────────────────────────────────────────────────────

    def _finish(self) -> None:
        """Mark the dialog as finished."""
        self._worker = None
        if self._cancelled:
            self._status_label.setText("Cancelled")
            self._append_log("Operation cancelled.", "warning")
        else:
            self._status_label.setText("Complete")
            self._progress_bar.setValue(100)
            self._append_log("")
            self._append_log("=== All files processed ===", "success")

        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)

    # ── Progress ───────────────────────────────────────────────────

    def _update_progress(self) -> None:
        """Update the progress bar based on completed operations."""
        if self._total_ops > 0:
            pct = min(int(self._completed_ops / self._total_ops * 100), 99)
            self._progress_bar.setValue(pct)

    # ── Logging ────────────────────────────────────────────────────

    def _append_log(self, text: str, level: str = "info") -> None:
        """Append a color-coded line to the log area and the output entry."""
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        hex_color = _LOG_COLORS.get(level, _LOG_COLORS["info"])
        fmt.setForeground(QColor(hex_color))
        fmt.setFont(QFont("Monospace", 10))

        if not self._log.document().isEmpty():
            cursor.insertText("\n", fmt)
        cursor.insertText(text, fmt)

        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

        # Mirror to the Output sidebar entry
        if self._output_entry:
            self._output_entry.append_line(text, level)

    @property
    def file_results(self) -> dict[str, tuple[str, str]]:
        """Per-file results: maps file path to (outcome, timestamp).

        Outcome is "success" or "error". Timestamp is "YYYY-MM-DD HH:MM".
        """
        return self._file_results

    def reject(self) -> None:
        """Override reject (Escape key) — cancel if running, close if done."""
        if self._worker is not None:
            self._on_cancel()
        else:
            super().reject()
