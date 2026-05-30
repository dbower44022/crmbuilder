"""Tests for the main window's bounded API auto-reconnect.

When the storage API drops (a panel reports ``connection_lost``, or an
owned subprocess ``crashed``), the window drives
``ServerLifecycle.start()`` up to ``_MAX_RECONNECT_ATTEMPTS`` times
before falling back to the manual-Reconnect banner. A *runtime* spawn
failure (routed from ``app.py`` via ``handle_reconnect_failed``) advances
the retry loop rather than killing the app — that gating is exercised
here against a fake lifecycle so no real subprocess is spawned.
"""

from __future__ import annotations

import httpx
import pytest
from crmbuilder_v2.ui.main_window import _MAX_RECONNECT_ATTEMPTS, MainWindow
from PySide6.QtCore import QObject, Signal


class FakeLifecycle(QObject):
    """Stand-in for ServerLifecycle: records start() calls, emits ready."""

    ready = Signal()
    crashed = Signal(str)
    spawn_failed = Signal(str)
    terminated = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.start_calls = 0
        self.ownership = "owned"

    def start(self) -> None:
        self.start_calls += 1

    def terminate(self) -> None:  # called from closeEvent
        pass


def _empty_client():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": [], "meta": {}, "errors": None}
            )
        return httpx.Response(
            404, json={"data": None, "meta": {}, "errors": [{"message": "x"}]}
        )

    from crmbuilder_v2.ui.client import StorageClient

    transport = httpx.MockTransport(handler)
    httpx_client = httpx.Client(base_url="http://test.invalid", transport=transport)
    return StorageClient(base_url="http://test.invalid", client=httpx_client)


@pytest.fixture
def window(qapp, tmp_path):
    for name in (
        "charter.json",
        "status.json",
        "decisions.json",
        "sessions.json",
        "risks.json",
        "planning_items.json",
        "topics.json",
        "references.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    lifecycle = FakeLifecycle()
    win = MainWindow(
        lifecycle=lifecycle, client=_empty_client(), snapshot_dir=tmp_path
    )
    return win, lifecycle


def _make_ready_once(win, lifecycle) -> None:
    """Drive the window through one successful readiness."""
    win._on_lifecycle_ready()
    assert win.had_first_ready() is True


def test_connection_loss_triggers_one_start_and_disables(window):
    win, lifecycle = window
    _make_ready_once(win, lifecycle)

    win._on_panel_connection_lost("Connection refused")

    assert lifecycle.start_calls == 1
    assert win._auto_reconnecting is True
    assert win._reconnect_attempts == 1
    assert win._lifecycle_ready is False
    # Banner message names the URL and the restart intent.
    text = win._crash_banner._label.text()
    assert win._base_url in text
    assert "restart" in text.lower()


def test_overlapping_connection_loss_does_not_stack_starts(window):
    win, lifecycle = window
    _make_ready_once(win, lifecycle)

    win._on_panel_connection_lost("a")
    win._on_panel_connection_lost("b")
    win._on_panel_connection_lost("c")

    # Still a single in-flight cycle — only the first kicked start().
    assert lifecycle.start_calls == 1
    assert win._reconnect_attempts == 1


def test_successful_reconnect_clears_state_and_banner(window):
    win, lifecycle = window
    _make_ready_once(win, lifecycle)
    win._on_panel_connection_lost("boom")

    win._on_lifecycle_ready()

    assert win._auto_reconnecting is False
    assert win._reconnect_attempts == 0
    assert win._lifecycle_ready is True
    assert win._crash_banner.isHidden()


def test_retries_are_bounded_then_actionable_banner(window):
    win, lifecycle = window
    _make_ready_once(win, lifecycle)
    win._on_panel_connection_lost("boom")  # attempt 1

    # Each runtime spawn failure advances the loop until the bound.
    for _ in range(_MAX_RECONNECT_ATTEMPTS - 1):
        win.handle_reconnect_failed("spawn err")
    assert lifecycle.start_calls == _MAX_RECONNECT_ATTEMPTS
    assert win._reconnect_attempts == _MAX_RECONNECT_ATTEMPTS

    # One more failure exhausts the budget: stop retrying, show guidance.
    win.handle_reconnect_failed("spawn err")
    assert lifecycle.start_calls == _MAX_RECONNECT_ATTEMPTS  # no further start
    assert win._auto_reconnecting is False
    text = win._crash_banner._label.text()
    assert "Reconnect" in text
    assert str(win._log_path) in text


def test_manual_reconnect_resets_exhausted_cycle(window):
    win, lifecycle = window
    _make_ready_once(win, lifecycle)
    win._on_panel_connection_lost("boom")
    for _ in range(_MAX_RECONNECT_ATTEMPTS):
        win.handle_reconnect_failed("spawn err")
    assert win._auto_reconnecting is False
    starts_after_exhaustion = lifecycle.start_calls

    # The banner's Reconnect button path starts a fresh bounded round.
    win._on_reconnect_requested()

    assert lifecycle.start_calls == starts_after_exhaustion + 1
    assert win._auto_reconnecting is True
    assert win._reconnect_attempts == 1


def test_crash_signal_also_auto_reconnects(window):
    win, lifecycle = window
    _make_ready_once(win, lifecycle)

    win.handle_crash("subprocess died")

    assert lifecycle.start_calls == 1
    assert win._auto_reconnecting is True
    assert win._lifecycle_ready is False


def test_had_first_ready_is_false_before_any_ready(window):
    win, _lifecycle = window
    # Gates app.py's fatal-vs-banner decision on a runtime spawn failure.
    assert win.had_first_ready() is False
