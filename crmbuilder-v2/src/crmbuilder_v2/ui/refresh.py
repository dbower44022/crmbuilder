"""File-watch refresh service.

Per DEC-022, the storage system rewrites JSON snapshot files on every
successful write. This module wraps ``QFileSystemWatcher`` over the
snapshot directory and emits a per-entity-type ``data_changed`` signal
when an entity-type snapshot file is modified. Manual Refresh buttons
on every panel act as a fallback.

Multi-write bursts within ``DEBOUNCE_MS`` coalesce to a single emission
per entity type. ``change_log.json`` and tempfile names are filtered
out — only the known entity-snapshot filenames produce signals.

UI v0.4 slice A extends the filename map with the four methodology
entity types (``domain``, ``entity``, ``process``, ``crm_candidate``);
their panels land in slices B–E and connect to ``data_changed`` for
the matching entity-type string.

UI v0.5 slice A adds ``meta/engagements.json`` to the watch list. The
file lives one level deeper than the per-engagement snapshots; the
engagement panel (v0.5 slice C) subscribes to ``data_changed`` for the
``engagement`` entity-type string.
"""

from __future__ import annotations

import hashlib
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
    # Methodology entity types (UI v0.4 slice A). Panels land in
    # slices B–E and connect to ``data_changed`` for these strings.
    "domains.json": "domain",
    "entities.json": "entity",
    "processes.json": "process",
    "crm_candidates.json": "crm_candidate",
}

# v0.5 slice A: file-watch entries that live one level below the
# top-level export_dir (e.g., ``db-export/meta/engagements.json``).
# The engagement panel (v0.5 slice C) subscribes to ``data_changed``
# for the ``engagement`` entity-type string.
_SUBDIR_FILENAME_TO_ENTITY_TYPE: dict[tuple[str, str], str] = {
    ("meta", "engagements.json"): "engagement",
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
                              risk, planning_item, topic, reference,
                              domain, entity, process, crm_candidate.
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
        self._content_hashes: dict[str, str] = {}
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
        self._content_hashes = self._snapshot_hashes()
        _log.debug("RefreshService watching %s", path_str)

    def stop(self) -> None:
        """Stop watching and tear down the timer.

        Idempotent. After ``stop()``, no further signals will be
        emitted from this instance unless ``start()`` is called again.
        """
        self._debounce_timer.stop()
        self._pending_emits.clear()
        self._content_hashes.clear()
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
            if previous is not None and mtime == previous:
                # Mtime unchanged — skip; storage system always rewrites.
                continue
            entity_type = _FILENAME_TO_ENTITY_TYPE.get(filename)
            if entity_type is None:
                continue
            # Mtime advanced; check whether content actually changed.
            # The storage system rewrites all eight snapshots on every
            # commit, so seven of every eight events are no-op rewrites
            # with byte-identical content. Hash-gate to suppress them.
            new_hash = self._hash_file(self._snapshot_dir / filename)
            old_hash = self._content_hashes.get(filename)
            if new_hash and new_hash == old_hash:
                continue
            if new_hash:
                self._content_hashes[filename] = new_hash
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

    def _snapshot_hashes(self) -> dict[str, str]:
        """Return the content hash for each known entity-snapshot file."""
        result: dict[str, str] = {}
        for filename in _FILENAME_TO_ENTITY_TYPE:
            path = self._snapshot_dir / filename
            if not path.exists():
                continue
            digest = self._hash_file(path)
            if digest:
                result[filename] = digest
        return result

    @staticmethod
    def _hash_file(path: Path) -> str:
        """SHA-256 hex digest of the file's bytes; '' on error.

        No security context — this is a cheap content-equality check
        used to suppress no-op rewrites from the snapshot exporter.
        """
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return ""
