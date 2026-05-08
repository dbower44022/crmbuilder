"""Unit tests for the file-watch RefreshService.

Each test uses a real ``QFileSystemWatcher`` (no mocks) over a
``tmp_path`` directory. Filesystem events go through the real OS
notification mechanism (inotify on Linux), so small ``qtbot.wait``
calls are sometimes needed between filesystem operations.
"""

from __future__ import annotations

import time
from pathlib import Path

from crmbuilder_v2.ui.refresh import RefreshService


def _write(path: Path, payload: str = "{}") -> None:
    """Write a file and bump its mtime by a non-trivial delta so the
    file-watch service notices.

    Some filesystems have second-resolution mtimes; ``os.utime`` with
    an explicit value avoids same-second writes producing identical
    mtimes that the service would treat as no-change.
    """
    path.write_text(payload, encoding="utf-8")
    # Force a unique-ish mtime in case the underlying FS has
    # 1-second resolution: bump forward by the loop counter.
    bumped = time.time() + (_write.counter * 0.01)
    _write.counter += 1
    import os

    os.utime(path, (bumped, bumped))


_write.counter = 0


def test_single_write_fires_data_changed_for_right_entity_type(
    qapp, qtbot, tmp_path
):
    service = RefreshService(tmp_path)
    service.start()

    with qtbot.waitSignal(service.data_changed, timeout=2000) as blocker:
        _write(tmp_path / "decisions.json", '{"data": []}')
    assert blocker.args == ["decision"]
    service.stop()


def test_change_log_is_ignored(qapp, qtbot, tmp_path):
    service = RefreshService(tmp_path)
    service.start()

    emissions: list[str] = []
    service.data_changed.connect(lambda et: emissions.append(et))
    _write(tmp_path / "change_log.json", '{"events": []}')
    qtbot.wait(int(RefreshService.DEBOUNCE_MS * 2 + 200))
    assert emissions == [], f"change_log.json should not fire, got {emissions!r}"
    service.stop()


def test_tempfile_creation_is_ignored(qapp, qtbot, tmp_path):
    service = RefreshService(tmp_path)
    service.start()

    emissions: list[str] = []
    service.data_changed.connect(lambda et: emissions.append(et))
    _write(tmp_path / "decisions.json.tmp.abc123", "raw")
    qtbot.wait(int(RefreshService.DEBOUNCE_MS * 2 + 200))
    assert emissions == [], f"tempfile should not fire, got {emissions!r}"
    service.stop()


def test_multi_write_burst_is_debounced(qapp, qtbot, tmp_path):
    service = RefreshService(tmp_path)
    service.start()

    emissions: list[str] = []
    service.data_changed.connect(lambda et: emissions.append(et))

    target = tmp_path / "decisions.json"
    for i in range(10):
        _write(target, f'{{"i": {i}}}')

    # Wait beyond the debounce window plus headroom.
    qtbot.wait(int(RefreshService.DEBOUNCE_MS * 2 + 200))
    assert emissions == ["decision"], (
        f"expected one coalesced emission, got {emissions!r}"
    )
    service.stop()


def test_multiple_entity_types_fire_separately(qapp, qtbot, tmp_path):
    service = RefreshService(tmp_path)
    service.start()

    emissions: list[str] = []
    service.data_changed.connect(lambda et: emissions.append(et))

    _write(tmp_path / "decisions.json", "{}")
    _write(tmp_path / "sessions.json", "{}")

    qtbot.wait(int(RefreshService.DEBOUNCE_MS * 2 + 200))
    assert sorted(emissions) == ["decision", "session"], (
        f"expected one of each, got {emissions!r}"
    )
    service.stop()


def test_watch_failure_on_nonexistent_directory_emits_watch_failed(
    qapp, qtbot, tmp_path
):
    missing = tmp_path / "does_not_exist"
    service = RefreshService(missing)

    with qtbot.waitSignal(service.watch_failed, timeout=1000) as blocker:
        service.start()
    assert blocker.args, "watch_failed should carry a diagnostic"
    assert str(missing) in blocker.args[0]
    service.stop()


def test_stop_prevents_further_emissions(qapp, qtbot, tmp_path):
    service = RefreshService(tmp_path)
    service.start()

    with qtbot.waitSignal(service.data_changed, timeout=2000):
        _write(tmp_path / "decisions.json", "{}")

    service.stop()

    emissions: list[str] = []
    service.data_changed.connect(lambda et: emissions.append(et))

    _write(tmp_path / "sessions.json", "{}")
    qtbot.wait(int(RefreshService.DEBOUNCE_MS * 2 + 200))
    assert emissions == [], (
        f"no signals expected after stop(), got {emissions!r}"
    )
