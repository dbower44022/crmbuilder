"""Detect-then-launch lifecycle for the storage API subprocess.

Per DEC-023, on startup the UI probes ``GET /health``; if no response
arrives, the UI spawns ``crmbuilder-v2-api`` via ``QProcess`` and polls
``/health`` until either it responds or a 10-second deadline elapses.
The lifecycle tracks ownership ("external" / "owned") so it terminates
only subprocesses it spawned itself.
"""

from __future__ import annotations

import logging
import sys
import time

import httpx
from PySide6.QtCore import QObject, QProcess, QTimer, Signal, Slot

_log = logging.getLogger("crmbuilder_v2.ui.lifecycle")

_PROBE_TIMEOUT_SECONDS = 1.0
_POLL_TIMEOUT_SECONDS = 0.25
_POLL_INTERVAL_MS = 250
_READINESS_DEADLINE_SECONDS = 10.0
_TERMINATE_TIMEOUT_MS = 3000

_SPAWN_ARGS: list[str] = [
    "-c",
    "from crmbuilder_v2.cli import run_api; run_api()",
]


class ServerLifecycle(QObject):
    """Probe-then-spawn lifecycle for the v2 API subprocess.

    Signals:

    * ``ready()`` — emitted on probe success or when a spawned
      subprocess responds to ``/health``.
    * ``crashed(str)`` — emitted when an owned subprocess exits
      unexpectedly OR when ``QProcess.errorOccurred`` fires after the
      lifecycle has reached ready state. Argument carries any captured
      stdout/stderr text or the QProcess error string.
    * ``spawn_failed(str)`` — emitted when an initial spawn does not
      become ready within the deadline, or when ``QProcess.errorOccurred``
      fires before ready. Argument carries diagnostic text.
    * ``terminated()`` — emitted after a deliberate ``terminate()``
      completes.
    """

    ready = Signal()
    crashed = Signal(str)
    spawn_failed = Signal(str)
    terminated = Signal()

    def __init__(
        self,
        base_url: str,
        parent: QObject | None = None,
        remote: bool = False,
    ):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        # REQ-448 / PI-386: when the client targets a remote backend it must
        # never spawn a local API — a failed probe surfaces a reconnect banner
        # instead of starting a stale local process.
        self._remote = remote
        self._ownership = "unknown"
        self._process: QProcess | None = None
        self._poll_timer: QTimer | None = None
        self._poll_started_at: float | None = None
        self._intentional_terminate = False
        # Tracks whether the lifecycle has reached ready state. Used to
        # distinguish runtime crashes (post-ready ``errorOccurred`` →
        # ``crashed``) from startup failures (pre-ready ``errorOccurred``
        # → ``spawn_failed``). Reset on ``start()`` so a Reconnect after
        # a crash treats the new spawn as starting again.
        self._post_ready = False

    @property
    def ownership(self) -> str:
        return self._ownership

    @Slot()
    def start(self) -> None:
        """Probe; if the API responds, mark external. Otherwise spawn + poll."""
        self._reset_for_start()
        if self._probe():
            self._ownership = "external"
            _log.info(
                "API already running at %s; using external instance",
                self._base_url,
            )
            self._post_ready = True
            self.ready.emit()
            return
        if self._remote:
            # REQ-448 / PI-386: configured for a remote cloud API — do not
            # spawn a local server. Surface a clear reconnect message instead.
            msg = (
                f"Cannot reach the CRMBuilder cloud API at {self._base_url}. "
                "The desktop is configured for a remote backend and will not "
                "start a local server. Check your connection and your "
                "CRMBUILDER_V2_API_BASE_URL / CRMBUILDER_V2_API_TOKEN settings, "
                "then reconnect."
            )
            _log.error(msg)
            self._ownership = "external"
            self.spawn_failed.emit(msg)
            return
        _log.info(
            "API not reachable at %s; spawning subprocess", self._base_url
        )
        self._spawn()

    @Slot()
    def terminate(self) -> None:
        """Terminate an owned subprocess; no-op for external ownership."""
        if self._ownership != "owned":
            return
        if self._process is None:
            return
        self._intentional_terminate = True
        self._stop_polling()
        _log.info("Terminating owned subprocess")
        self._process.terminate()
        if not self._process.waitForFinished(_TERMINATE_TIMEOUT_MS):
            _log.warning("Subprocess did not terminate gracefully; killing")
            self._process.kill()
            self._process.waitForFinished(_TERMINATE_TIMEOUT_MS)
        self._ownership = "terminated"
        self.terminated.emit()

    def _reset_for_start(self) -> None:
        # A second start() (e.g., Reconnect after a crash) should drop
        # any leftover process and timer state without firing the
        # crash handler from the dead subprocess.
        self._stop_polling()
        if self._process is not None:
            self._intentional_terminate = True
            try:
                self._process.errorOccurred.disconnect(self._on_process_error)
            except (TypeError, RuntimeError):
                pass
            try:
                self._process.finished.disconnect(self._on_process_finished)
            except (TypeError, RuntimeError):
                pass
            self._process = None
        self._intentional_terminate = False
        self._poll_started_at = None
        self._post_ready = False

    def _probe(self) -> bool:
        try:
            response = httpx.get(
                f"{self._base_url}/health",
                timeout=_PROBE_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            _log.debug("Initial probe failed: %s", exc)
            return False
        return response.status_code == 200

    def _spawn(self) -> None:
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.errorOccurred.connect(self._on_process_error)
        process.finished.connect(self._on_process_finished)
        self._process = process
        self._intentional_terminate = False
        self._ownership = "owned"
        _log.info("Spawning %s -c '<run_api>'", sys.executable)
        process.start(sys.executable, _SPAWN_ARGS)
        self._begin_polling()

    def _begin_polling(self) -> None:
        self._poll_started_at = time.monotonic()
        timer = QTimer(self)
        timer.setInterval(_POLL_INTERVAL_MS)
        timer.timeout.connect(self._on_poll_tick)
        self._poll_timer = timer
        _log.debug(
            "Beginning readiness polling (interval=%dms, deadline=%.0fs)",
            _POLL_INTERVAL_MS,
            _READINESS_DEADLINE_SECONDS,
        )
        timer.start()

    def _on_poll_tick(self) -> None:
        try:
            response = httpx.get(
                f"{self._base_url}/health",
                timeout=_POLL_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                elapsed = time.monotonic() - (
                    self._poll_started_at or time.monotonic()
                )
                self._stop_polling()
                _log.info("Spawned API ready after %.2fs", elapsed)
                self._post_ready = True
                self.ready.emit()
                return
        except Exception as exc:
            _log.debug("Readiness probe failed: %s", exc)

        elapsed = time.monotonic() - (
            self._poll_started_at or time.monotonic()
        )
        if elapsed >= _READINESS_DEADLINE_SECONDS:
            self._stop_polling()
            stderr_text = self._read_subprocess_output()
            _log.error(
                "Spawned API did not become ready within %.0fs; aborting",
                _READINESS_DEADLINE_SECONDS,
            )
            self.spawn_failed.emit(stderr_text)

    def _stop_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer.deleteLater()
            self._poll_timer = None

    def _read_subprocess_output(self) -> str:
        if self._process is None:
            return ""
        try:
            data = self._process.readAllStandardOutput()
        except Exception:
            return ""
        try:
            return bytes(data).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _on_process_error(self, error) -> None:
        message = ""
        if self._process is not None and hasattr(self._process, "errorString"):
            try:
                message = self._process.errorString()
            except Exception:
                message = str(error)
        else:
            message = str(error)
        # SIGTERM from terminate() makes QProcess report Crashed via
        # errorOccurred. Suppress so the engagement-switch terminate path
        # doesn't fire spawn_failed (wired in app.py to app.exit), which
        # would tear down the QApplication mid-activation-step.
        if self._intentional_terminate:
            _log.debug(
                "QProcess error during intentional terminate (suppressed): %s",
                message,
            )
            self._stop_polling()
            return
        _log.error("QProcess error: %s", message)
        self._stop_polling()
        if self._post_ready:
            # Runtime crash: surface to the in-window banner via ``crashed``.
            self.crashed.emit(message)
        else:
            # Pre-ready: the spawn never reached readiness.
            self.spawn_failed.emit(message)

    def _on_process_finished(self, exit_code: int = 0, exit_status=None) -> None:
        if self._intentional_terminate:
            _log.debug(
                "Process finished after intentional terminate; suppressing crash"
            )
            return
        if self._ownership != "owned":
            return
        stderr_text = self._read_subprocess_output()
        _log.warning(
            "Owned subprocess exited unexpectedly (code=%s)", exit_code
        )
        self.crashed.emit(stderr_text)
