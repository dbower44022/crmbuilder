"""File-watch refresh service.

Per DEC-022, the storage system rewrites JSON snapshot files on every
successful write. This module wraps ``QFileSystemWatcher`` over the
snapshot directory and emits a per-entity-type ``data_changed`` signal
when an entity-type snapshot file is modified. Manual Refresh buttons
on every panel act as a fallback.

Multi-write bursts within ``DEBOUNCE_MS`` coalesce to a single emission
per entity type. ``change_log.json`` and tempfile names are filtered
out — only the eight known entity-snapshot filenames produce signals.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

_log = logging.getLogger("crmbuilder_v2.ui.refresh")

# Maps a snapshot filename to the entity_type it represents. Filenames
# not in this map (notably ``change_log.json`` and tempfiles produced
# by atomic-rename writes) are ignored.
_FILENAME_TO_ENTITY_TYPE: dict[str, str] = {
    "charter.json": "charter",
    "status.json": "status",
    "decisions.json": "decision",
    "sessions.json": "session",
    "risks.json": "risk",
    "planning_items.json": "planning_item",
    "topics.json": "topic",
    "references.json": "reference",
}


class RefreshService(QObject):
    """File-watch refresh service.

    Watches the configured snapshot directory and emits ``data_changed``
    signals when an entity-type snapshot file is modified. Multi-write
    bursts within the debounce window coalesce to a single emission
    per entity type.

    Signals:

    * ``data_changed(str)`` — entity_type whose snapshot was rewritten.
                              One of: charter, status, decision, session,
                              risk, planning_item, topic, reference.
    * ``watch_failed(str)``  — emitted if ``QFileSystemWatcher`` cannot
                               watch the directory. Argument carries a
                               diagnostic message.
    """

    data_changed = Signal(str)
    watch_failed = Signal(str)

    DEBOUNCE_MS: ClassVar[int] = 500

    def __init__(
        self, snapshot_dir: Path, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._snapshot_dir = Path(snapshot_dir)
        self._watcher: QFileSystemWatcher | None = None
        self._mtimes: dict[str, float] = {}
        self._pending_emits: set[str] = set()
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self.DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._flush_pending)

    def start(self) -> None:
        """Begin watching the snapshot directory.

        If the directory cannot be watched (e.g., it does not exist),
        emits ``watch_failed`` with a diagnostic and returns. The
        manual Refresh button on each panel remains the user's
        fallback. Calling ``start()`` again after a previous call is
        a no-op.
        """
        if self._watcher is not None:
            return

        path_str = str(self._snapshot_dir)
        watcher = QFileSystemWatcher(self)
        watcher.addPath(path_str)
        if path_str not in watcher.directories():
            _log.warning(
                "QFileSystemWatcher could not watch %s", path_str
            )
            watcher.deleteLater()
            self.watch_failed.emit(
                f"Could not watch directory: {path_str}"
            )
            return

        watcher.directoryChanged.connect(self._on_directory_changed)
        self._watcher = watcher
        self._mtimes = self._snapshot_mtimes()
        _log.debug("RefreshService watching %s", path_str)

    def stop(self) -> None:
        """Stop watching and tear down the timer.

        Idempotent. After ``stop()``, no further signals will be
        emitted from this instance unless ``start()`` is called again.
        """
        self._debounce_timer.stop()
        self._pending_emits.clear()
        if self._watcher is not None:
            try:
                self._watcher.directoryChanged.disconnect(
                    self._on_directory_changed
                )
            except (RuntimeError, TypeError):
                pass
            for d in list(self._watcher.directories()):
                self._watcher.removePath(d)
            self._watcher.deleteLater()
            self._watcher = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_directory_changed(self, path: str) -> None:
        _log.debug("directoryChanged fired for %s", path)
        new_mtimes = self._snapshot_mtimes()
        for filename, mtime in new_mtimes.items():
            previous = self._mtimes.get(filename)
            if previous is None or mtime != previous:
                entity_type = _FILENAME_TO_ENTITY_TYPE.get(filename)
                if entity_type is not None:
                    self._pending_emits.add(entity_type)
        self._mtimes = new_mtimes
        if self._pending_emits:
            self._debounce_timer.start()

    def _flush_pending(self) -> None:
        pending = list(self._pending_emits)
        self._pending_emits.clear()
        for entity_type in pending:
            _log.debug("data_changed emitting for %s", entity_type)
            self.data_changed.emit(entity_type)

    def _snapshot_mtimes(self) -> dict[str, float]:
        """Return current mtimes for known entity-snapshot filenames.

        Files that don't exist are simply absent from the map. Files
        we don't recognize (tempfiles, ``change_log.json``) are ignored.
        """
        result: dict[str, float] = {}
        try:
            entries = list(self._snapshot_dir.iterdir())
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            return result
        for entry in entries:
            name = entry.name
            if name not in _FILENAME_TO_ENTITY_TYPE:
                continue
            try:
                result[name] = entry.stat().st_mtime
            except OSError:
                continue
        return result
