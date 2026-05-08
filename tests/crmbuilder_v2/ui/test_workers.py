"""Tests for the worker QThread helper.

Note on the wait pattern: ``qtbot.waitSignal`` only sees a signal if its
internal connection is made before the signal fires. With a trivial
callable like ``lambda: 42`` the worker can complete before the test
returns from ``run_in_thread``, so these tests use ``qtbot.waitUntil``
on captured state instead, which is race-free.
"""

from __future__ import annotations

from crmbuilder_v2.ui.workers import run_in_thread


def test_successful_run(qapp, qtbot):
    captured: list[object] = []
    finished: list[bool] = []

    worker = run_in_thread(
        lambda: 42,
        on_success=captured.append,
    )
    worker.finished.connect(lambda: finished.append(True))

    qtbot.waitUntil(lambda: captured == [42], timeout=2000)
    qtbot.waitUntil(lambda: bool(finished), timeout=2000)


def test_failed_run(qapp, qtbot):
    captured: list[BaseException] = []
    finished: list[bool] = []

    def boom() -> int:
        return 1 // 0

    worker = run_in_thread(
        boom,
        on_error=captured.append,
    )
    worker.finished.connect(lambda: finished.append(True))

    qtbot.waitUntil(lambda: len(captured) == 1, timeout=2000)
    assert isinstance(captured[0], ZeroDivisionError)
    qtbot.waitUntil(lambda: bool(finished), timeout=2000)


def test_finished_fires_without_callbacks(qapp, qtbot):
    finished: list[bool] = []
    worker = run_in_thread(lambda: "ok")
    worker.finished.connect(lambda: finished.append(True))
    qtbot.waitUntil(lambda: bool(finished), timeout=2000)


def test_finished_fires_on_failure_without_callbacks(qapp, qtbot):
    finished: list[bool] = []

    def boom():
        raise RuntimeError("nope")

    worker = run_in_thread(boom)
    worker.finished.connect(lambda: finished.append(True))
    qtbot.waitUntil(lambda: bool(finished), timeout=2000)
