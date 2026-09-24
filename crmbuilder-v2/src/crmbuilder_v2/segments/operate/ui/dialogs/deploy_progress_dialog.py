"""Deploy progress dialog — PI-419 (REQ-522, DEC-945); redesigned by PI-571 (REQ-650, REQ-652).

Shows one deploy run as the service executes it. The deploy worker owns the
run, so the dialog polls ``GET /deploy-runs/{id}?log_after=N`` every couple of
seconds off the UI thread and renders only what is new. Close is always
available: the run continues on the service and can be reopened from Deploy
History.

What the operator sees, top to bottom:

* the run's status in one sentence;
* a message whenever something needs a person — what was found, what to do,
  who does it and how to confirm — taken from the run's open items;
* every step as a plain sentence with its expected time and its state: done,
  working, needs action, waiting on another step, not started, or failed;
* the detailed log, for anyone who wants it.

Try again resumes the run on the same server. Change web address… tries again
with a corrected address. Handover sheet opens the page for the client once
the run has registered the instance.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from crmbuilder_v2.segments.operate.ui.dialogs.handover_dialog import (
    HandoverDialog,
    fit_to_screen,
)
from crmbuilder_v2.segments.operate.ui.handover import open_items_html
from crmbuilder_v2.segments.operate.vocab import (
    DEPLOY_RUN_PHASE_ORDER,
    DEPLOY_RUN_TERMINAL_STATUSES,
)
from crmbuilder_v2.ui.exceptions import RequestShapeError, StorageConnectionError
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import primary_button
from crmbuilder_v2.ui.workers import drain_workers, run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.deploy_progress_dialog")

_GREEN = "#1e8449"
_RED = "#c0392b"
_AMBER = "#b9770e"
_INFO = "#222222"
_GREY = "#6A7480"
_LEVEL_COLOR = {"success": _GREEN, "warning": _AMBER, "error": _RED, "info": _INFO}

#: Short step names (also the Deploy History panel's phase column).
PHASE_LABELS = {
    "validate": "Checking credentials",
    "create_droplet": "Creating server",
    "wait_droplet": "Waiting for server",
    "create_dns": "Setting DNS",
    "wait_dns": "Waiting for DNS",
    "server_prep": "Preparing server",
    "install_espocrm": "Installing CRM",
    "post_install": "Post-install checks",
    "check_dns": "Checking DNS",
    "certificate": "Certificate",
    "verify": "Verifying",
    "create_instance": "Registering instance",
}

#: Each step as a sentence with its expected time (PI-571 / REQ-652).
STEP_SENTENCES = {
    "validate": "Checking the provider accounts — a few seconds",
    "create_droplet": "Creating the server — about 1 minute",
    "wait_droplet": "Waiting for the server to start — 1 to 2 minutes",
    "create_dns": "Creating or showing the DNS record — a few seconds",
    "wait_dns": "Waiting for DNS",
    "server_prep": "Preparing the server — about 5 minutes",
    "install_espocrm": "Installing the CRM — about 6 minutes",
    "post_install": "Checking the installation — about 1 minute",
    "check_dns": "Checking DNS — up to 15 minutes if it is still spreading",
    "certificate": "Securing the site with a certificate — about 2 minutes once DNS is correct",
    "verify": "Final checks — about 1 minute",
    "create_instance": "Registering the instance in CRMBuilder — a few seconds",
}

STATUS_TEXT = {
    "queued": "Queued — waiting for the deploy worker…",
    "running": "Running",
    "succeeded": "Deployment complete. The CRM is installed and secure.",
    "succeeded_with_issues": "Deployment complete with verification gaps — see the steps and log.",
    "needs_action": "The CRM is installed, but something needs attention before it is ready.",
    "failed": "Deployment stopped — everything built was kept. See the message below.",
    "cancelled": "Deployment cancelled — everything built was kept.",
}

#: How each step state is shown: symbol, colour, words.
_STEP_STATE = {
    "done": ("✓", _GREEN, "done"),
    "running": ("▸", _INFO, "working"),
    "needs_action": ("⚑", _AMBER, "needs action"),
    "waiting": ("…", _GREY, "waiting on another step"),
    "failed": ("✗", _RED, "failed"),
    "retry": ("○", _GREY, "will run again"),
    None: ("○", _GREY, "not started"),
}


def describe_run(run: dict[str, Any]) -> str:
    """One status line for a run (shared with the history panel)."""
    status = run.get("deploy_run_status") or ""
    text = STATUS_TEXT.get(status, status)
    if status == "running":
        phase = run.get("deploy_run_phase")
        text = f"Running — {PHASE_LABELS.get(phase, phase or '…')}"
    state = run.get("deploy_run_state") or {}
    record = state.get("manual_dns_record")
    if (
        record
        and status in ("queued", "running", "failed")
        and run.get("deploy_run_phase") in ("create_dns", "wait_dns")
    ):
        # Manual DNS (PI-566 / REQ-642): the record the client must add.
        where = record.get("dns_host") or "the domain's DNS provider"
        text += (
            f" Add this DNS record at {where}: type A, name "
            f"{record.get('host_name') or record.get('name')}, value {record.get('value')}. "
            "Leave any proxy off."
        )
    if status in ("failed", "cancelled") and state.get("droplet_id"):
        text += f" Server {state['droplet_id']}"
        if state.get("droplet_ip"):
            text += f" ({state['droplet_ip']})"
        text += " still exists."
    return text


def phase_index(run: dict[str, Any]) -> int:
    """How many steps are finished — done, or waiting only on a person (drives the bar)."""
    phases = (run.get("deploy_run_state") or {}).get("phases") or {}
    return sum(
        1 for p in DEPLOY_RUN_PHASE_ORDER
        if (phases.get(p) or {}).get("status") in ("done", "needs_action", "waiting")
    )


def step_lines(run: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """``(phase, symbol, colour, text)`` for every step, in order."""
    phases = (run.get("deploy_run_state") or {}).get("phases") or {}
    lines = []
    for phase in DEPLOY_RUN_PHASE_ORDER:
        entry = phases.get(phase) or {}
        status = entry.get("status")
        symbol, colour, words = _STEP_STATE.get(status, _STEP_STATE[None])
        text = f"{STEP_SENTENCES.get(phase, phase)}   ({words})"
        if status == "failed" and entry.get("error"):
            text += f" — {entry['error']}"
        lines.append((phase, symbol, colour, text))
    return lines


def _open_items(run: dict[str, Any]) -> list[dict[str, Any]]:
    items = (run.get("deploy_run_state") or {}).get("open_items") or {}
    return list(items.values()) if isinstance(items, dict) else list(items)


class DeployProgressDialog(QDialog):
    """Poll one deploy run and render its progress until it is terminal."""

    #: Emitted with the instance identifier once the run has registered it.
    instance_created = Signal(str)
    connection_lost = Signal(str)

    def __init__(self, client, identifier: str, parent=None, *, poll_ms: int = 2000,
                 admin_password: str | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self.identifier = identifier
        self._admin_password = admin_password
        self._log_seen = 0
        self._last: dict[str, Any] = {}
        self._in_flight: list = []
        self._emitted_instance = False

        self.setWindowTitle(f"Deploy run {identifier}")
        fit_to_screen(self, 0.7, (860, 640))
        layout = QVBoxLayout(self)
        self._title = QLabel(f"Deploy run {identifier}")
        self._title.setObjectName("deploy_title")
        self._title.setStyleSheet(f"font-size: {t('font.size.heading_2')}; font-weight: 600;")
        layout.addWidget(self._title)
        self._status = QLabel("Loading…")
        self._status.setObjectName("deploy_status")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"font-size: {t('font.size.body_large')};")
        layout.addWidget(self._status)
        self._banner = QLabel("")
        self._banner.setObjectName("deploy_attention")
        self._banner.setWordWrap(True)
        self._banner.setTextFormat(Qt.TextFormat.RichText)
        self._banner.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._banner.setStyleSheet(
            f"background: {t('color.warning.subtle')}; border-radius: 6px; padding: 10px; "
            f"font-size: {t('font.size.body_large')};"
        )
        self._banner.setVisible(False)
        layout.addWidget(self._banner)
        self._progress = QProgressBar()
        self._progress.setObjectName("deploy_progress_bar")
        self._progress.setRange(0, len(DEPLOY_RUN_PHASE_ORDER))
        layout.addWidget(self._progress)
        self._steps = QListWidget()
        self._steps.setObjectName("deploy_steps")
        self._steps.setStyleSheet(f"font-size: {t('font.size.body_large')};")
        self._steps.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self._steps, 2)
        log_label = QLabel("Detailed log")
        log_label.setStyleSheet(f"color: {t('color.neutral.700')};")
        layout.addWidget(log_label)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setObjectName("deploy_progress_log")
        layout.addWidget(self._log, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel run")
        self._cancel_btn.setObjectName("deploy_cancel_button")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._address_btn = QPushButton("Change web address…")
        self._address_btn.setObjectName("deploy_change_address_button")
        self._address_btn.clicked.connect(self._on_change_address)
        self._address_btn.setVisible(False)
        self._retry_btn = primary_button("Try again")
        self._retry_btn.setObjectName("deploy_retry_button")
        self._retry_btn.clicked.connect(self._on_retry)
        self._retry_btn.setVisible(False)
        self._handover_btn = QPushButton("Handover sheet")
        self._handover_btn.setObjectName("deploy_handover_button")
        self._handover_btn.clicked.connect(self.open_handover)
        self._handover_btn.setVisible(False)
        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("deploy_close_button")
        self._close_btn.clicked.connect(self.accept)
        for b in (self._cancel_btn, self._address_btn, self._retry_btn,
                  self._handover_btn, self._close_btn):
            row.addWidget(b)
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
        domain = (run.get("deploy_run_spec") or {}).get("domain")
        if domain:
            self._title.setText(f"Deploying {domain}")
        self._progress.setValue(phase_index(run))
        self._status.setText(describe_run(run))
        self._render_steps(run)
        self._render_banner(run)
        status = run.get("deploy_run_status")
        terminal = status in DEPLOY_RUN_TERMINAL_STATUSES
        self._cancel_btn.setVisible(not terminal)
        can_retry = status in ("failed", "cancelled", "needs_action")
        self._retry_btn.setVisible(can_retry)
        self._address_btn.setVisible(can_retry)
        self._handover_btn.setVisible(bool(run.get("instance_identifier")))
        if terminal:
            self._timer.stop()
        ident = run.get("instance_identifier")
        if ident and not self._emitted_instance:
            self._emitted_instance = True
            self.instance_created.emit(ident)

    def _render_steps(self, run: dict[str, Any]) -> None:
        self._steps.clear()
        running = run.get("deploy_run_phase") if run.get("deploy_run_status") == "running" else None
        for phase, symbol, colour, text in step_lines(run):
            if phase == running and symbol == "○":
                symbol, colour = "▸", _INFO
                text = text.replace("(not started)", "(working)").replace("(will run again)", "(working)")
            item = QListWidgetItem(f"{symbol}  {text}")
            item.setForeground(_qcolor(colour))
            item.setData(Qt.ItemDataRole.UserRole, phase)
            self._steps.addItem(item)

    def _render_banner(self, run: dict[str, Any]) -> None:
        status = run.get("deploy_run_status")
        items = _open_items(run)
        if items and status not in ("queued", "running"):
            self._banner.setText(open_items_html(items))
            self._banner.setVisible(True)
        elif status == "failed" and run.get("deploy_run_error"):
            self._banner.setText(
                f"<b>The deploy stopped:</b> {html.escape(run['deploy_run_error'])}<br>"
                "Everything built was kept. Fix the cause if it is named, then press Try again; "
                "the run resumes where it stopped."
            )
            self._banner.setVisible(True)
        else:
            self._banner.setVisible(False)

    @property
    def last_run(self) -> dict[str, Any]:
        return self._last

    # -- actions ----------------------------------------------------------

    def _on_cancel(self) -> None:
        self._cancel_btn.setEnabled(False)
        self._status.setText("Cancelling — the run stops after the current step…")
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.cancel_deploy_run(self.identifier),
                on_success=lambda _r: self.poll(),
                on_error=self._on_error,
                parent=self,
            )
        )

    def _on_retry(self, corrections: dict[str, Any] | None = None) -> None:
        corrections = corrections if isinstance(corrections, dict) else None
        self._retry_btn.setVisible(False)
        self._address_btn.setVisible(False)
        self._log_line(
            "Trying again — the run resumes on the same server at the steps that did not finish.",
            "info",
        )
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.retry_deploy_run(self.identifier, corrections),
                on_success=self._retried,
                on_error=self._retry_failed,
                parent=self,
            )
        )

    def corrections_for(self, address: str) -> dict[str, Any] | str:
        """The Try again body for a corrected ``address``, or why it cannot be used."""
        spec = self._last.get("deploy_run_spec") or {}
        address = address.strip().lower().rstrip(".")
        if "." not in address:
            return "Enter the full web address, for example crm.example.org."
        if spec.get("dns_mode") == "manual":
            return {"domain": address}
        zone = spec.get("zone_name") or ""
        if not address.endswith("." + zone):
            return (
                f"This run creates its record in the Cloudflare zone {zone}, so the address "
                f"must end in .{zone}."
            )
        return {"subdomain": address[: -len(zone) - 1]}

    def _on_change_address(self) -> None:
        current = (self._last.get("deploy_run_spec") or {}).get("domain") or ""
        address, ok = QInputDialog.getText(
            self, "Change web address",
            "The corrected web address. The server is kept; the steps that depend on the "
            "address run again:", text=current,
        )
        if not ok or not address.strip() or address.strip().lower() == current:
            return
        body = self.corrections_for(address)
        if isinstance(body, str):
            self._status.setText(body)
            return
        self._on_retry(body)

    def _retried(self, _run: dict[str, Any]) -> None:
        self._cancel_btn.setEnabled(True)
        self._timer.start()
        self.poll()

    def _retry_failed(self, exc: Exception) -> None:
        if isinstance(exc, RequestShapeError):
            problems = "; ".join(e.get("message", "") for e in (exc.errors or [])) or str(exc)
            self._status.setText(f"Not tried again — {problems}")
            self._retry_btn.setVisible(True)
            self._address_btn.setVisible(True)
            return
        self._on_error(exc)

    def open_handover(self) -> HandoverDialog:
        dialog = HandoverDialog(self._last, admin_password=self._admin_password, parent=self)
        dialog.open()
        return dialog

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


def _qcolor(hex_colour: str) -> QColor:
    return QColor(hex_colour)
