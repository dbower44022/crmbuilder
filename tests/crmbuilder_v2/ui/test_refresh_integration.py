"""Integration tests for the file-watch refresh path.

Exercises the wire from "snapshot file modified" through MainWindow's
``_on_data_changed`` slot to a panel's ``refresh()`` call. The
StorageClient is backed by a counting httpx mock so we can assert
extra GET hits beyond the initial-load baseline.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import httpx
import pytest
from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle


def _bump_mtime(path: Path, delta: float) -> None:
    """Force a unique mtime so the file-watch service registers the change."""
    import os

    bumped = time.time() + delta
    os.utime(path, (bumped, bumped))


def _write_snapshot(path: Path, payload: str = "{}", delta: float = 0.0) -> None:
    path.write_text(payload, encoding="utf-8")
    if delta:
        _bump_mtime(path, delta)


def _seed_snapshots(tmp_path: Path) -> None:
    """Pre-create the eight entity-snapshot files so the watcher's
    baseline mtime map is well-defined before the test mutates one."""
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
        # Stagger initial mtimes slightly to make later writes detectable
        # on filesystems with second-resolution mtime.
        _bump_mtime(tmp_path / name, -10.0)


@pytest.fixture
def counted_client(qapp):
    """Returns (client, counter dict) where counter[path] increments per GET."""
    counter: Counter[str] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        counter[request.url.path] += 1
        path = request.url.path
        if request.method == "GET" and path in (
            "/decisions",
            "/sessions",
            "/risks",
            "/topics",
            "/planning-items",
            "/references",
            "/charter/versions",
            "/status/versions",
        ):
            return httpx.Response(
                200, json={"data": [], "meta": {}, "errors": None}
            )
        if request.method == "GET" and path.startswith("/references/touching/"):
            return httpx.Response(
                200,
                json={
                    "data": {"as_source": [], "as_target": []},
                    "meta": {},
                    "errors": None,
                },
            )
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "no route"}],
            },
        )

    from crmbuilder_v2.ui.client import StorageClient

    transport = httpx.MockTransport(handler)
    httpx_client = httpx.Client(
        base_url="http://test.invalid", transport=transport
    )
    client = StorageClient(base_url="http://test.invalid", client=httpx_client)
    return client, counter


@pytest.fixture
def lifecycle_unreachable():
    return ServerLifecycle(base_url="http://127.0.0.1:1")


def _wait_until(qtbot, predicate, timeout_ms: int = 3000) -> bool:
    """Poll the predicate until it's true, returning False on timeout."""
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if predicate():
            return True
        qtbot.wait(50)
    return False


def test_visible_panel_refreshes_on_data_changed_for_its_entity(
    qapp, qtbot, lifecycle_unreachable, counted_client, tmp_path
):
    _seed_snapshots(tmp_path)
    client, counter = counted_client
    window = MainWindow(
        lifecycle=lifecycle_unreachable, client=client, snapshot_dir=tmp_path
    )
    qtbot.addWidget(window)
    # Default selected entry is Decisions; the panel's refresh runs on
    # construction so let it settle.
    qtbot.wait(100)
    initial_decisions = counter["/decisions"]

    # Bump the mtime ahead so the watcher detects the change even if FS
    # resolution is coarse.
    _write_snapshot(tmp_path / "decisions.json", '{"x": 1}', delta=2.0)

    assert _wait_until(
        qtbot,
        lambda: counter["/decisions"] > initial_decisions,
        timeout_ms=3000,
    ), (
        f"expected /decisions GET count to increase past "
        f"{initial_decisions}; got {counter['/decisions']}"
    )


def test_non_visible_panel_marks_sidebar_stale(
    qapp, qtbot, lifecycle_unreachable, counted_client, tmp_path
):
    _seed_snapshots(tmp_path)
    client, counter = counted_client
    window = MainWindow(
        lifecycle=lifecycle_unreachable, client=client, snapshot_dir=tmp_path
    )
    qtbot.addWidget(window)
    qtbot.wait(100)
    initial_sessions = counter["/sessions"]

    # Default visible panel is Decisions; write to sessions.json.
    _write_snapshot(tmp_path / "sessions.json", '{"x": 1}', delta=2.0)

    assert _wait_until(
        qtbot,
        lambda: window._sidebar.is_stale("Sessions"),
        timeout_ms=3000,
    ), "Sessions sidebar entry should be marked stale"
    assert counter["/sessions"] == initial_sessions, (
        f"non-visible panel should NOT have refetched; "
        f"/sessions count went from {initial_sessions} to "
        f"{counter['/sessions']}"
    )


def test_navigating_to_stale_entry_clears_indicator_and_refreshes(
    qapp, qtbot, lifecycle_unreachable, counted_client, tmp_path
):
    _seed_snapshots(tmp_path)
    client, counter = counted_client
    window = MainWindow(
        lifecycle=lifecycle_unreachable, client=client, snapshot_dir=tmp_path
    )
    qtbot.addWidget(window)
    qtbot.wait(100)

    # Mark Sessions as stale by writing the snapshot.
    _write_snapshot(tmp_path / "sessions.json", '{"x": 1}', delta=2.0)
    assert _wait_until(
        qtbot,
        lambda: window._sidebar.is_stale("Sessions"),
        timeout_ms=3000,
    )
    sessions_before_navigate = counter["/sessions"]

    # Navigate to Sessions; the staleness indicator should clear and a
    # refresh should fire.
    sessions_idx = None
    for r in range(window._sidebar.count()):
        if window._sidebar.item(r).text() == "Sessions":
            sessions_idx = r
            break
    assert sessions_idx is not None
    window._sidebar.setCurrentRow(sessions_idx)

    assert window._sidebar.is_stale("Sessions") is False
    assert _wait_until(
        qtbot,
        lambda: counter["/sessions"] > sessions_before_navigate,
        timeout_ms=2000,
    )


def test_main_window_with_nonexistent_snapshot_dir_does_not_crash(
    qapp, qtbot, lifecycle_unreachable, counted_client, tmp_path
):
    client, _counter = counted_client
    missing = tmp_path / "does_not_exist"

    # Construction must succeed even when the watcher cannot install.
    # Connect to watch_failed BEFORE we kick the (already-fired) signal —
    # since RefreshService.start() is called inside __init__, the signal
    # may have already emitted. Use a Qt-level introspection: assert
    # that the service has no watcher and the missing dir didn't crash.
    window = MainWindow(
        lifecycle=lifecycle_unreachable, client=client, snapshot_dir=missing
    )
    qtbot.addWidget(window)

    assert window.isVisible() is False  # constructed but not shown is fine
    # The internal watcher is None when start() failed.
    assert window._refresh_service._watcher is None
