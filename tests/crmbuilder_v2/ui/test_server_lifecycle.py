"""Tests for ``ServerLifecycle``.

Mocks ``httpx.get`` and ``QProcess`` at the module level. Direct
invocation of private slots (e.g., ``_on_process_finished``) stands in
for emitting the corresponding ``QProcess`` signals from the mock — the
QProcess instance is a Mock, so emitting real Qt signals from it is not
possible.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import httpx
from crmbuilder_v2.ui import server_lifecycle
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle

_BASE_URL = "http://127.0.0.1:8765"


def _make_get(responses):
    """Build an ``httpx.get`` replacement that yields each response in turn.

    Each entry is either an ``Exception`` (raised) or an object with a
    ``status_code`` attribute (returned). Once the list is exhausted the
    final entry is repeated, which lets tests express "first n calls
    fail, then succeed forever" patterns concisely.
    """
    state = {"index": 0}

    def get(*_args, **_kwargs):
        i = min(state["index"], len(responses) - 1)
        state["index"] += 1
        value = responses[i]
        if isinstance(value, Exception):
            raise value
        return value

    return get


def _patch_qprocess(monkeypatch, fake_process: MagicMock | None = None) -> MagicMock:
    """Replace the module-local ``QProcess`` symbol with a factory mock.

    Returns the ``fake_process`` instance the lifecycle will receive
    when it instantiates ``QProcess`` in ``_spawn``.
    """
    if fake_process is None:
        fake_process = MagicMock()
    qprocess_factory = MagicMock(return_value=fake_process)
    # ProcessChannelMode.MergedChannels access on the mocked class still
    # has to resolve to *something*; MagicMock attribute access returns
    # MagicMock by default which is acceptable.
    monkeypatch.setattr(server_lifecycle, "QProcess", qprocess_factory)
    return fake_process


def test_probe_success_marks_external_and_emits_ready(
    qapp, qtbot, monkeypatch
):
    """A successful initial probe sets external ownership; no spawn happens."""
    monkeypatch.setattr(
        server_lifecycle.httpx, "get",
        _make_get([Mock(status_code=200)]),
    )
    qprocess_factory = MagicMock()
    monkeypatch.setattr(server_lifecycle, "QProcess", qprocess_factory)

    lifecycle = ServerLifecycle(_BASE_URL)

    with qtbot.waitSignal(lifecycle.ready, timeout=1000):
        lifecycle.start()

    assert lifecycle.ownership == "external"
    qprocess_factory.assert_not_called()


def test_probe_failure_then_spawn_then_ready(qapp, qtbot, monkeypatch):
    """Probe fails, spawn occurs, polling sees a 200 and emits ready."""
    monkeypatch.setattr(
        server_lifecycle.httpx, "get",
        _make_get([
            httpx.ConnectError("nope"),
            Mock(status_code=200),
        ]),
    )
    fake_process = _patch_qprocess(monkeypatch)

    lifecycle = ServerLifecycle(_BASE_URL)

    with qtbot.waitSignal(lifecycle.ready, timeout=2000):
        lifecycle.start()

    assert lifecycle.ownership == "owned"
    assert fake_process.start.called


def test_spawn_failure_when_polling_deadline_expires(
    qapp, qtbot, monkeypatch
):
    """If the spawned subprocess never responds, spawn_failed fires."""
    # Production deadline is 10s; shrink it so the test finishes quickly.
    # The behavior under test is "deadline expiry → spawn_failed", not the
    # specific magnitude of the production deadline.
    monkeypatch.setattr(server_lifecycle, "_READINESS_DEADLINE_SECONDS", 0.5)
    monkeypatch.setattr(
        server_lifecycle.httpx, "get",
        _make_get([httpx.ConnectError("never")]),
    )
    fake_process = _patch_qprocess(monkeypatch)
    fake_process.readAllStandardOutput.return_value = b"boot output"

    lifecycle = ServerLifecycle(_BASE_URL)

    with qtbot.waitSignal(lifecycle.spawn_failed, timeout=3000) as blocker:
        lifecycle.start()

    assert "boot output" in blocker.args[0]


def test_terminate_is_noop_for_external_ownership(
    qapp, qtbot, monkeypatch
):
    """An externally-launched API is left untouched on terminate."""
    monkeypatch.setattr(
        server_lifecycle.httpx, "get",
        _make_get([Mock(status_code=200)]),
    )
    qprocess_factory = MagicMock()
    monkeypatch.setattr(server_lifecycle, "QProcess", qprocess_factory)

    lifecycle = ServerLifecycle(_BASE_URL)
    with qtbot.waitSignal(lifecycle.ready, timeout=1000):
        lifecycle.start()

    terminated_seen = Mock()
    lifecycle.terminated.connect(terminated_seen)
    lifecycle.terminate()

    assert lifecycle.ownership == "external"
    qprocess_factory.assert_not_called()
    terminated_seen.assert_not_called()


def test_unexpected_finished_emits_crashed(qapp, qtbot, monkeypatch):
    """When ownership is 'owned' and finished fires, crashed emits."""
    monkeypatch.setattr(
        server_lifecycle.httpx, "get",
        _make_get([
            httpx.ConnectError("nope"),
            Mock(status_code=200),
        ]),
    )
    fake_process = _patch_qprocess(monkeypatch)
    fake_process.readAllStandardOutput.return_value = b"died at line 17"

    lifecycle = ServerLifecycle(_BASE_URL)
    with qtbot.waitSignal(lifecycle.ready, timeout=2000):
        lifecycle.start()

    assert lifecycle.ownership == "owned"

    with qtbot.waitSignal(lifecycle.crashed, timeout=1000) as blocker:
        lifecycle._on_process_finished(1, 0)

    assert "died at line 17" in blocker.args[0]


def test_finished_after_intentional_terminate_does_not_emit_crashed(
    qapp, qtbot, monkeypatch
):
    """A finished signal after our own terminate() must not surface as crashed."""
    monkeypatch.setattr(
        server_lifecycle.httpx, "get",
        _make_get([
            httpx.ConnectError("nope"),
            Mock(status_code=200),
        ]),
    )
    fake_process = _patch_qprocess(monkeypatch)
    # waitForFinished() returning truthy keeps terminate() out of the kill branch.
    fake_process.waitForFinished.return_value = True

    lifecycle = ServerLifecycle(_BASE_URL)
    with qtbot.waitSignal(lifecycle.ready, timeout=2000):
        lifecycle.start()

    crashed_seen = Mock()
    lifecycle.crashed.connect(crashed_seen)

    with qtbot.waitSignal(lifecycle.terminated, timeout=1000):
        lifecycle.terminate()

    assert lifecycle.ownership == "terminated"
    assert fake_process.terminate.called

    # Now simulate the dead subprocess's finished signal arriving late.
    lifecycle._on_process_finished(0, 0)
    qapp.processEvents()

    crashed_seen.assert_not_called()
