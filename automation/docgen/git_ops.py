"""Git operations for the Document Generator.

Implements L2 PRD Section 13.7.3 — local git commit and optional push for
generated documents. Uses subprocess.run() for git invocation.

Commit includes only the generated file(s). Push failures do not block —
the generation is complete once the local commit succeeds.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def commit(
    project_folder: str | Path,
    file_paths: list[str | Path],
    message: str,
) -> str | None:
    """Stage and commit generated files in the project folder.

    :param project_folder: Root of the client's project repository.
    :param file_paths: Paths to the generated files (absolute or relative to project_folder).
    :param message: Commit message.
    :returns: The git commit hash on success, or None if the commit fails.
    """
    cwd = str(project_folder)

    # Stage only the specified files
    for fp in file_paths:
        result = subprocess.run(
            ["git", "add", str(fp)],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("git add failed for %s: %s", fp, result.stderr.strip())
            return None

    # Commit
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        # "nothing to commit" is not an error condition
        if "nothing to commit" in stdout or "nothing to commit" in stderr:
            logger.info("Nothing to commit in %s", project_folder)
            return None
        logger.warning("git commit failed: %s", stderr)
        return None

    # Get the commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("Could not read commit hash: %s", result.stderr.strip())
        return None

    commit_hash = result.stdout.strip()
    logger.info("Committed %s: %s", message, commit_hash)
    return commit_hash


def push(project_folder: str | Path) -> bool:
    """Push the current branch to the remote.

    :param project_folder: Root of the client's project repository.
    :returns: True on success, False on failure.
    """
    result = subprocess.run(
        ["git", "push"],
        cwd=str(project_folder),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("git push failed: %s", result.stderr.strip())
        return False

    logger.info("Pushed successfully from %s", project_folder)
    return True
