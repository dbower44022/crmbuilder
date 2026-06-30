"""Working-copy build lock — REQ-441 / PI-380.

One builder per working copy: a second concurrent build driver against the same
checkout is refused, so one driver's rollback can't delete another's worktree.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.scheduler.repo_build_lock import (
    BuildLockHeld,
    acquire_build_lock,
)


def test_second_concurrent_build_is_refused(tmp_path):
    (tmp_path / ".git").mkdir()
    repo = str(tmp_path)
    with acquire_build_lock(repo, label="first"):
        with pytest.raises(BuildLockHeld):
            with acquire_build_lock(repo, label="second"):
                pass  # pragma: no cover — should never enter


def test_lock_released_after_exit_allows_reacquire(tmp_path):
    (tmp_path / ".git").mkdir()
    repo = str(tmp_path)
    with acquire_build_lock(repo):
        pass
    # The first holder released; a later driver may take it.
    with acquire_build_lock(repo):
        pass


def test_lock_file_lives_inside_git_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    with acquire_build_lock(str(tmp_path)) as path:
        assert path.endswith("/.git/crmbuilder-build.lock")


def test_lock_falls_back_to_repo_root_when_no_git_dir(tmp_path):
    # A bare path without .git/ still locks (on repo_root) rather than erroring.
    with acquire_build_lock(str(tmp_path)) as path:
        assert path.endswith("/crmbuilder-build.lock")
