"""Audit progress dialog — live per-area audit feedback (PI-274, PRJ-044).

Restores the V1 audit progress experience to the V2 desktop (REQ-308..311):
instead of one blocking request that freezes the panel until the final summary,
this dialog drives the audit's reconcile areas **one at a time** (the per-area
``POST /instances/{id}/audit/{area}`` endpoint) and shows live progress — a
progress bar that advances per area, a color-coded running log that streams
each area's outcome and any warnings, and a Cancel control that stops the audit
between areas. Each per-area call runs off the UI thread via
:func:`run_in_thread`, so the window stays responsive throughout.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from crmbuilder_v2.ui.exceptions import StorageConnectionError
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.audit_progress_dialog")

_GREEN = "#1e8449"
_RED = "#c0392b"
_AMBER = "#b9770e"
_INFO = "#222222"
_LEVEL_COLOR = {"success": _GREEN, "warning": _AMBER, "error": _RED, "info": _INFO}


def _summary_line(label: str, summary: dict) -> str:
    s = summary or {}
    return (
        f"✓ {label}: {s.get('seen', 0)} seen, "
        f"{s.get('created', 0)} created, {s.get('present', 0)} present, "
        f"{s.get('drifted', 0)} drifted, {s.get('absent', 0)} absent"
    )


class AuditProgressDialog(QDialog):
    """Drives a per-area audit and renders its live progress.

    The audit is a sequence of reconcile areas (entities → fields → … →
    filtered tabs). The dialog fetches the area list, then runs each area's
    endpoint in turn, advancing the bar and appending to the log. A reconcile
    failure stops the run (a hard error is fatal, as in V1); a warning (e.g. an
    entity whose fields could not be read) is logged but does not stop the
    audit. Cancel takes effect after the in-flight area finishes, so the audit
    always stops in a consistent state.
    """

    #: Relayed to the panel so a dropped API mid-audit drives reconnect (PI-110).
    connection_lost = Signal(str)

    def __init__(self, client, instance_record: dict, parent=None) -> None:
        super().__init__(parent)
        self._client = client
        self._identifier = instance_record.get("instance_identifier")
        self._target = (
            instance_record.get("instance_name") or self._identifier
        )
        self._areas: list[dict[str, Any]] = []
        self._index = 0
        self._cancelled = False
        self._failed = False
        self._finished = False
        self._worker = None

        self.setWindowTitle(f"Audit progress — {self._target}")
        self.resize(640, 460)

        layout = QVBoxLayout(self)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setObjectName("audit_progress_bar")
        self._progress.setRange(0, 0)  # indeterminate until the area list loads
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setObjectName("audit_progress_log")
        layout.addWidget(self._log, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("audit_cancel_button")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("audit_close_button")
        self._close_btn.clicked.connect(self.accept)
        row.addWidget(self._cancel_btn)
        row.addWidget(self._close_btn)
        layout.addLayout(row)

        self._start()

    # -- lifecycle -------------------------------------------------------

    def _start(self) -> None:
        self._status.setText(f"Auditing {self._target}…")
        self._set_running(True)
        self._worker = run_in_thread(
            self._client.list_audit_areas,
            on_success=self._areas_loaded,
            on_error=self._on_start_error,
            parent=self,
        )

    def _areas_loaded(self, areas: list[dict[str, Any]]) -> None:
        self._areas = areas or []
        self._progress.setRange(0, len(self._areas) or 1)
        self._progress.setValue(0)
        self._run_next()

    def _run_next(self) -> None:
        if self._cancelled:
            self._finish(cancelled=True)
            return
        if self._index >= len(self._areas):
            self._finish()
            return
        area = self._areas[self._index]
        self._log_line(f"▸ Auditing {area.get('label', area['area'])}…", "info")
        self._worker = run_in_thread(
            lambda a=area: self._client.audit_instance_area(
                self._identifier, a["area"]
            ),
            on_success=self._area_done,
            on_error=self._area_error,
            parent=self,
        )

    def _area_done(self, result: dict[str, Any]) -> None:
        summary = result.get("summary") or {}
        label = result.get("label") or result.get("area", "")
        self._log_line(_summary_line(label, summary), "success")
        for line in result.get("log") or []:
            msg, level = (line[0], line[1]) if len(line) >= 2 else (line, "info")
            self._log_line(f"   {msg}", level)
        self._index += 1
        self._progress.setValue(self._index)
        self._run_next()

    def _area_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self._log_line(f"✗ Connection lost: {exc}", "error")
            self.connection_lost.emit(str(exc))
        else:
            label = (
                self._areas[self._index].get("label", "audit")
                if self._index < len(self._areas)
                else "audit"
            )
            self._log_line(f"✗ {label} failed: {exc}", "error")
        self._finish(failed=True)

    def _on_start_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self.connection_lost.emit(str(exc))
        _log.warning("Audit could not start: %s", exc)
        self._log_line(f"✗ Could not start the audit: {exc}", "error")
        self._finish(failed=True)

    def _finish(
        self, *, cancelled: bool = False, failed: bool = False
    ) -> None:
        self._failed = failed
        self._finished = True
        self._set_running(False)
        if cancelled:
            self._status.setText("Audit cancelled.")
            self._log_line(
                "Audit cancelled — areas completed so far are recorded.",
                "warning",
            )
        elif failed:
            self._status.setText("Audit stopped — see the log.")
        else:
            self._progress.setRange(0, len(self._areas) or 1)
            self._progress.setValue(len(self._areas))
            self._status.setText("Audit complete.")
            self._log_line("✓ Audit complete.", "success")

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._cancel_btn.setEnabled(False)
        self._status.setText("Cancelling — finishing the current area…")

    # -- helpers ---------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        self._cancel_btn.setVisible(running)
        self._cancel_btn.setEnabled(running)
        self._close_btn.setVisible(not running)

    def _log_line(self, text: str, level: str) -> None:
        color = _LEVEL_COLOR.get(level, _INFO)
        self._log.append(
            f"<span style='color:{color}'>{html.escape(text)}</span>"
        )
