"""QThread worker pattern for off-thread blocking calls.

Wired in slice C. Generic ``Worker`` QThread subclass + ``run_in_thread``
helper. Every blocking call (HTTP, file I/O) goes through a worker so
the UI thread never blocks.

Usage::

    worker = run_in_thread(
        lambda: client.list_decisions(),
        on_success=self._handle_records,
        on_error=self._handle_error,
        parent=self,
    )
    self._in_flight_workers.append(worker)

The caller MUST keep the returned worker alive until it emits
``finished``; otherwise garbage collection can destroy the worker
before its slots fire.

We use the QThread-subclass pattern (override ``run``) rather than the
QObject-on-QThread pattern. The subclass approach is more
straightforward when the worker performs a single one-shot job: the
QThread itself is the QObject that owns the work and emits its
results, so signal/slot routing across the worker/main thread
boundary is unambiguous.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

_log = logging.getLogger("crmbuilder_v2.ui.workers")


class Worker(QThread):
    """One-shot worker: runs a callable on a thread; emits result + error.

    Signals:

    * ``succeeded(object)`` — emitted with the callable's return value
      on success. Delivered to slots on their owning thread (queued
      across thread boundaries).
    * ``failed(object)`` — emitted with the raised ``Exception`` on
      failure.
    * The inherited ``finished()`` signal fires after run() returns,
      regardless of success or failure.

    ``KeyboardInterrupt`` and ``SystemExit`` propagate normally.
    """

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        fn: Callable[[], Any],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D401 — Qt method
        try:
            result = self._fn()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:  # noqa: BLE001 — convert to signal
            _log.debug("Worker callable raised %r", exc)
            self.failed.emit(exc)
            return
        self.succeeded.emit(result)


def run_in_thread(
    fn: Callable[[], Any],
    *,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    parent: QObject | None = None,
) -> Worker:
    """Run ``fn`` on a new ``Worker`` thread; deliver the result via callbacks.

    ``on_success`` and ``on_error`` should be bound methods of QObjects
    so Qt can resolve AutoConnection to QueuedConnection across thread
    boundaries.

    Returns the ``Worker`` instance. The caller must keep it alive
    until ``finished`` fires; on ``finished`` it is scheduled for
    deletion via ``deleteLater``.
    """
    worker = Worker(fn, parent)
    if on_success is not None:
        worker.succeeded.connect(on_success)
    if on_error is not None:
        worker.failed.connect(on_error)
    worker.finished.connect(worker.deleteLater)
    worker.start()
    return worker
