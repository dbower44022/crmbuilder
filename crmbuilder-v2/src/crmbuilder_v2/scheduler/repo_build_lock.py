"""Working-copy build lock — REQ-441 / PI-380.

Two ADO build drivers run at once against the **same working copy** corrupt each
other: one driver's rollback (``git reset --hard`` + ``git worktree prune``)
deletes the other's live worktree mid-run, producing a false ``tests_failed``
(observed in the REL-038 build). The in-pool ``_repo_lock`` only serializes git
ops *within one pool*; two separate driver processes each hold their own lock, so
they do not serialize against each other.

This is a **process-level, advisory file lock** on the working copy: every build
driver (single-PI, PM, the dev-lane pools) takes it at start and a second driver
**refuses** while it is held — one builder per working copy. It is *not* the
PI-364 run-lock (that is per-Project and DB-backed); this guards the **git
working copy** itself, across processes, regardless of which project each drives.

Lock file: ``<repo_root>/.git/crmbuilder-build.lock`` (inside ``.git`` so it never
shows up as a working-tree change and is naturally per-clone). Uses ``fcntl.flock``
with ``LB_EX | LB_NB`` so the OS releases it automatically if the holder dies — no
stale-lock cleanup needed.
"""

from __future__ import annotations

import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager

LOCK_FILENAME = "crmbuilder-build.lock"


class BuildLockHeld(RuntimeError):
    """Raised when another build driver already holds the working-copy lock."""


def _lock_path(repo_root: str) -> str:
    git_dir = os.path.join(repo_root, ".git")
    # A linked worktree's ``.git`` is a file, not a dir; fall back to repo_root so
    # the lock still lands on a stable per-clone path.
    base = git_dir if os.path.isdir(git_dir) else repo_root
    return os.path.join(base, LOCK_FILENAME)


@contextmanager
def acquire_build_lock(repo_root: str, *, label: str = "") -> Iterator[str]:
    """Hold the working-copy build lock for the duration of the ``with`` block.

    Non-blocking: if another driver holds it, raise :class:`BuildLockHeld`
    immediately rather than queue (a second concurrent build is a mistake to
    surface, not to silently serialize). The lock is released — and the OS drops
    it even on a hard crash — when the block exits.

    On platforms without ``fcntl`` (e.g. Windows), this is a best-effort no-op so
    the scheduler still runs; the guard is a POSIX-dev-host protection.
    """
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX fallback
        yield _lock_path(repo_root)
        return

    path = _lock_path(repo_root)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                raise BuildLockHeld(
                    "another build driver already holds the working-copy lock at "
                    f"{path!r}; refusing to run a second concurrent build against "
                    "the same checkout (REQ-441) — run builds serially or via the "
                    "PM (ado-pm), or use a separate clone/worktree."
                ) from exc
            raise
        # Record who holds it for diagnostics (best-effort).
        try:
            os.ftruncate(fd, 0)
            os.write(fd, f"pid={os.getpid()} {label}".encode())
        except OSError:
            pass
        yield path
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
