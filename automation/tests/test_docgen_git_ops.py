"""Tests for automation.docgen.git_ops — git commit and push."""

import subprocess

import pytest

from automation.docgen.git_ops import commit, push


@pytest.fixture()
def git_repo(tmp_path):
    """Initialize a temporary git repo."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True,
    )
    # Initial commit
    readme = tmp_path / "README.md"
    readme.write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(tmp_path), capture_output=True,
    )
    return tmp_path


class TestCommit:

    def test_commit_returns_hash(self, git_repo):
        test_file = git_repo / "output.docx"
        test_file.write_text("test content")

        result = commit(git_repo, [str(test_file)], "Test commit")
        assert result is not None
        assert len(result) == 40  # SHA-1 hash

    def test_commit_nothing_returns_none(self, git_repo):
        result = commit(git_repo, [], "Empty commit")
        assert result is None

    def test_commit_nonexistent_file_returns_none(self, git_repo):
        result = commit(git_repo, ["/nonexistent/file.txt"], "Bad commit")
        assert result is None


class TestPush:

    def test_push_no_remote_returns_false(self, git_repo):
        result = push(git_repo)
        assert result is False
