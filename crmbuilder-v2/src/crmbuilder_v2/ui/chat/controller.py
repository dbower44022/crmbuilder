"""Main-thread bridge between the chat panel and the worker (PI-052 Slice B).

``ChatController`` owns the in-memory :class:`ChatSession` and the
:class:`ChatWorker`. The panel talks only to the controller: it calls
:meth:`send` / :meth:`stop` and connects to the controller's panel-facing
signals. The controller connects the worker's signals to slots that keep
the session in sync and re-emit to the panel, so the panel never sees the
worker thread or the asyncio loop directly.

Slice B holds exactly one implicit session. Persistence, multiple
sessions, and usage tracking are Slice C.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from crmbuilder_v2.ui.chat.session import ChatSession
from crmbuilder_v2.ui.chat.worker import ChatWorker

_log = logging.getLogger("crmbuilder_v2.ui.chat.controller")


class ChatController(QObject):
    """Owns the session + worker; bridges signals to the panel.

    Panel-facing signals:

    * ``assistant_delta(str)`` — streamed text for the live bubble.
    * ``tool_started(str, str)`` — ``(name, args_json)``.
    * ``tool_completed(str, str, str)`` — ``(name, summary, result_json)``.
    * ``tool_failed(str, str)`` — ``(name, error)``.
    * ``turn_state_changed(bool)`` — True when a turn starts, False when
      it settles. Drives Send-disabled / Stop-visible in the panel.
    * ``turn_finished(str)`` — ``stop_reason`` ("end_turn"/"cancelled"/…).
    * ``turn_failed(str)`` — error string, shown inline.
    * ``auth_failed(str)`` — 401; the panel re-prompts for the key.
    """

    assistant_delta = Signal(str)
    tool_started = Signal(str, str)
    tool_completed = Signal(str, str, str)
    tool_failed = Signal(str, str)
    turn_state_changed = Signal(bool)
    turn_finished = Signal(str)
    turn_failed = Signal(str)
    auth_failed = Signal(str)

    def __init__(self, base_url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._session = ChatSession()
        self._worker: ChatWorker | None = None
        self._in_turn = False

    @property
    def in_turn(self) -> bool:
        return self._in_turn

    def set_api_key(self, api_key: str) -> None:
        """Create and start the worker for ``api_key``. Idempotent-ish:
        a prior worker is shut down first (used by the 401 re-prompt)."""
        self._teardown_worker()
        worker = ChatWorker(api_key=api_key, base_url=self._base_url)
        worker.assistant_delta.connect(self.assistant_delta)
        worker.tool_started.connect(self.tool_started)
        worker.tool_completed.connect(self.tool_completed)
        worker.tool_failed.connect(self.tool_failed)
        worker.turn_finished.connect(self._on_worker_turn_finished)
        worker.turn_failed.connect(self._on_worker_turn_failed)
        worker.auth_failed.connect(self.auth_failed)
        worker.start()
        self._worker = worker

    def send(self, text: str) -> None:
        """Append a user turn and dispatch it to the worker."""
        if self._worker is None:
            _log.warning("send() before API key configured; ignoring")
            return
        if self._in_turn:
            _log.debug("send() while a turn is in flight; ignoring")
            return
        self._session.append_user(text)
        self._set_in_turn(True)
        self._worker.start_turn(
            list(self._session.messages_for_api()), self._session.model
        )

    def stop(self) -> None:
        """Request cancellation of the in-flight turn."""
        if self._worker is not None:
            self._worker.stop()

    def shutdown(self) -> None:
        """Tear down the worker thread cleanly (called at panel/app close)."""
        self._teardown_worker()

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_worker_turn_finished(self, stop_reason: str, messages) -> None:
        self._session.replace_messages(messages)
        self._set_in_turn(False)
        self.turn_finished.emit(stop_reason)

    def _on_worker_turn_failed(self, error: str, messages) -> None:
        self._session.replace_messages(messages)
        self._set_in_turn(False)
        self.turn_failed.emit(error)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_in_turn(self, value: bool) -> None:
        self._in_turn = value
        self.turn_state_changed.emit(value)

    def _teardown_worker(self) -> None:
        if self._worker is None:
            return
        worker = self._worker
        self._worker = None
        try:
            worker.shutdown()
            if not worker.wait(5000):
                _log.warning("ChatWorker did not stop within 5s; terminating")
                worker.terminate()
                worker.wait(2000)
        except Exception:  # noqa: BLE001 — best-effort teardown
            _log.exception("Error tearing down ChatWorker")
