"""Deploy progress dialog — PI-419 (REQ-522, DEC-945).

Shows one deploy run as the service executes it: a phase progress bar, the
run's colour-coded log, and Cancel / Retry / Close. Unlike the audit dialog it
drives nothing — the deploy worker owns the run — so it polls
``GET /deploy-runs/{id}?log_after=N`` every couple of seconds off the UI thread
and renders only what is new. Close is always available: the run continues on
the service and can be reopened from Deploy History. A failed run shows what
was kept (server id / IP) and offers Retry, which resumes at the failed phase.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from crmbuilder_v2.access.vocab import (
    DEPLOY_RUN_PHASE_ORDER,
    DEPLOY_RUN_TERMINAL_STATUSES,
)
from crmbuilder_v2.ui.exceptions import StorageConnectionError
from crmbuilder_v2.ui.widgets.form_helpers import primary_button
from crmbuilder_v2.ui.workers import drain_workers, run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.deploy_progress_dialog")

_GREEN = "#1e8449"
_RED = "#c0392b"
_AMBER = "#b9770e"
_INFO = "#222222"
_LEVEL_COLOR = {"success": _GREEN, "warning": _AMBER, "error": _RED, "info": _INFO}
PHASE_LABELS = {
    "validate": "Checking credentials",
    "create_droplet": "Creating server",
    "wait_droplet": "Waiting for server",
    "create_dns": "Setting DNS",
    "wait_dns": "Waiting for DNS",
    "server_prep": "Preparing server",
    "install_espocrm": "Installing CRM",
    "post_install": "Post-install checks",
    "verify": "Verifying",
    "create_instance": "Registering instance",
}
STATUS_TEXT = {
    "queued": "Queued — waiting for the deploy worker…",
    "running": "Running",
    "succeeded": "Deployment complete.",
    "succeeded_with_issues": "Deployment complete with verification gaps — see the log.",
    "failed": "Deployment failed — everything built was kept. See the log.",
    "cancelled": "Deployment cancelled — everything built was kept.",
}


def describe_run(run: dict[str, Any]) -> str:
    """One status line for a run (shared with the history panel)."""
    status = run.get("deploy_run_status") or ""
    text = STATUS_TEXT.get(status, status)
    if status == "running":
        phase = run.get("deploy_run_phase")
        text = f"Running — {PHASE_LABELS.get(phase, phase or '…')}"
    state = run.get("deploy_run_state") or {}
    if status in ("failed", "cancelled") and state.get("droplet_id"):
        text += f" Server {state['droplet_id']}"
        if state.get("droplet_ip"):
            text += f" ({state['droplet_ip']})"
        text += " still exists."
    return text


def phase_index(run: dict[str, Any]) -> int:
    """How many phases are done (drives the progress bar)."""
    phases = (run.get("deploy_run_state") or {}).get("phases") or {}
    done = sum(1 for p in DEPLOY_RUN_PHASE_ORDER if (phases.get(p) or {}).get("status") == "done")
    return done


class DeployProgressDialog(QDialog):
    """Poll one deploy run and render its progress until it is terminal."""

    #: Emitted with the instance identifier once the run has registered it.
    instance_created = Signal(str)
    connection_lost = Signal(str)

    def __init__(self, client, identifier: str, parent=None, *, poll_ms: int = 2000) -> None:
        super().__init__(parent)
        self._client = client
        self.identifier = identifier
        self._log_seen = 0
        self._last: dict[str, Any] = {}
        self._in_flight: list = []
        self._emitted_instance = False

        self.setWindowTitle(f"Deploy run {identifier}")
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        self._status = QLabel("Loading…")
        self._status.setObjectName("deploy_status")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._progress = QProgressBar()
        self._progress.setObjectName("deploy_progress_bar")
        self._progress.setRange(0, len(DEPLOY_RUN_PHASE_ORDER))
        layout.addWidget(self._progress)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setObjectName("deploy_progress_log")
        layout.addWidget(self._log, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel run")
        self._cancel_btn.setObjectName("deploy_cancel_button")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._retry_btn = primary_button("Retry")
        self._retry_btn.setObjectName("deploy_retry_button")
        self._retry_btn.clicked.connect(self._on_retry)
        self._retry_btn.setVisible(False)
        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("deploy_close_button")
        self._close_btn.clicked.connect(self.accept)
        row.addWidget(self._cancel_btn)
        row.addWidget(self._retry_btn)
        row.addWidget(self._close_btn)
        layout.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setInterval(poll_ms)
        self._timer.timeout.connect(self.poll)
        self._timer.start()
        self.poll()

    # -- polling ----------------------------------------------------------

    def poll(self) -> None:
        """Fetch the run (only new log lines) off the UI thread."""
        after = self._log_seen
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.get_deploy_run(self.identifier, log_after=after),
                on_success=self.apply,
                on_error=self._on_error,
                parent=self,
            )
        )

    def apply(self, run: dict[str, Any]) -> None:
        """Render a run snapshot (public so tests can feed one directly)."""
        self._last = run
        for entry in run.get("deploy_run_log") or []:
            level, text = (entry[1], entry[2]) if len(entry) >= 3 else ("info", str(entry))
            self._log_line(text, level)
        self._log_seen = int(run.get("log_length") or self._log_seen)
        self._progress.setValue(phase_index(run))
        self._status.setText(describe_run(run))
        status = run.get("deploy_run_status")
        terminal = status in DEPLOY_RUN_TERMINAL_STATUSES
        self._cancel_btn.setVisible(not terminal)
        self._retry_btn.setVisible(status in ("failed", "cancelled"))
        if terminal:
            self._timer.stop()
        ident = run.get("instance_identifier")
        if ident and not self._emitted_instance:
            self._emitted_instance = True
            self.instance_created.emit(ident)

    @property
    def last_run(self) -> dict[str, Any]:
        return self._last

    # -- actions ----------------------------------------------------------

    def _on_cancel(self) -> None:
        self._cancel_btn.setEnabled(False)
        self._status.setText("Cancelling — the run stops after the current phase…")
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.cancel_deploy_run(self.identifier),
                on_success=lambda _r: self.poll(),
                on_error=self._on_error,
                parent=self,
            )
        )

    def _on_retry(self) -> None:
        self._retry_btn.setVisible(False)
        self._log_line("Retrying — the run resumes at the phase that did not finish.", "info")
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.retry_deploy_run(self.identifier),
                on_success=self._retried,
                on_error=self._on_error,
                parent=self,
            )
        )

    def _retried(self, _run: dict[str, Any]) -> None:
        self._cancel_btn.setEnabled(True)
        self._timer.start()
        self.poll()

    def _on_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self._timer.stop()
            self._log_line(f"Connection lost: {exc}", "error")
            self.connection_lost.emit(str(exc))
            return
        _log.warning("deploy progress: %s", exc)
        self._log_line(f"✗ {exc}", "error")

    def done(self, result: int) -> None:  # noqa: D401 - Qt override
        """Stop polling and finish the in-flight workers before teardown."""
        self._timer.stop()
        drain_workers(self._in_flight)
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._timer.stop()
        super().closeEvent(event)

    def _log_line(self, text: str, level: str) -> None:
        color = _LEVEL_COLOR.get(level, _INFO)
        self._log.append(f"<span style='color:{color}'>{html.escape(text)}</span>")
