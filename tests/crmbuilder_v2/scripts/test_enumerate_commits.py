"""Tests for enumerate_commits.py — the close-out commit enumerator."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


# Load the script as a module (it isn't on the package import path).
_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "crmbuilder-v2"
    / "scripts"
    / "enumerate_commits.py"
)
_spec = importlib.util.spec_from_file_location(
    "enumerate_commits", _SCRIPT_PATH
)
enumerate_commits = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enumerate_commits)


def _init_git_repo(repo_path: Path, *commits) -> list[str]:
    """Initialize a git repo at ``repo_path`` and create commits with
    the given (subject, body) tuples. Returns the SHA list in
    chronological order."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    shas = []
    for i, (subject, body) in enumerate(commits):
        f = repo_path / f"file_{i}.txt"
        f.write_text(f"content {i}\n")
        subprocess.run(["git", "add", str(f)], cwd=repo_path, check=True)
        full_msg = subject if not body else f"{subject}\n\n{body}"
        subprocess.run(
            ["git", "commit", "-q", "-m", full_msg], cwd=repo_path, check=True
        )
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, check=True,
        )
        shas.append(result.stdout.strip())
    return shas


def test_files_changed_count_single_file(tmp_path):
    """Single-file commit returns 1."""
    repo = tmp_path / "repo"
    shas = _init_git_repo(repo, ("first commit", ""))
    count = enumerate_commits._files_changed_count(shas[0], repo)
    assert count == 1


def test_enumerate_from_empty_snapshot_returns_all_commits(tmp_path):
    """When db-export/commits.json doesn't exist, the helper enumerates
    all of history (first-ingestion bootstrap case)."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    shas = _init_git_repo(repo,
        ("first commit", ""),
        ("second commit", "with a body"),
        ("third commit", ""),
    )
    records = enumerate_commits._enumerate_repo(
        repo_name="testrepo",
        repo_root=repo,
        branch="main",
        db_export_dir=db_export,
        skip_pull=True,
    )
    assert len(records) == 3
    # Records are sorted by committed_at ascending
    assert [r["commit_sha"] for r in records] == shas


def test_enumerate_since_snapshot_filters_correctly(tmp_path):
    """When db-export/commits.json names a SHA, the helper enumerates
    only commits after that SHA."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    shas = _init_git_repo(repo,
        ("first commit", ""),
        ("second commit", ""),
        ("third commit", ""),
    )
    # Snapshot claims the second commit was the last ingested
    snapshot = [{
        "commit_sha": shas[1],
        "commit_repository": "testrepo",
        "commit_committed_at": "2026-05-23T10:00:00-04:00",
    }]
    (db_export / "commits.json").write_text(json.dumps(snapshot))
    records = enumerate_commits._enumerate_repo(
        repo_name="testrepo",
        repo_root=repo,
        branch="main",
        db_export_dir=db_export,
        skip_pull=True,
    )
    assert len(records) == 1
    assert records[0]["commit_sha"] == shas[2]


def test_multi_line_commit_message_parsed_correctly(tmp_path):
    """A commit message with embedded newlines must be preserved
    correctly (the ASCII separator pattern is the key claim)."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    body = (
        "This commit has a multi-line body.\n"
        "\n"
        "It contains a list:\n"
        "- item one\n"
        "- item two\n"
    )
    shas = _init_git_repo(repo, ("subject with no body", ""), ("multi-line subject", body))
    records = enumerate_commits._enumerate_repo(
        repo_name="testrepo",
        repo_root=repo,
        branch="main",
        db_export_dir=db_export,
        skip_pull=True,
    )
    assert len(records) == 2
    # Look up the multi-line record by subject; same-second commits
    # don't have a strict order guarantee in tests.
    multi = next(r for r in records if r["commit_message_first_line"] == "multi-line subject")
    assert "item one" in multi["commit_message_full"]
    assert "item two" in multi["commit_message_full"]


def test_parent_shas_extracted_for_merge_commit(tmp_path):
    """A merge commit (2 parents) emits a 2-element commit_parent_shas list."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    _init_git_repo(repo, ("base", ""))
    # Create a feature branch with a commit, then merge it
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=repo, check=True)
    (repo / "feature_file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "feature commit"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge feature", "feature"],
        cwd=repo, check=True,
    )
    records = enumerate_commits._enumerate_repo(
        repo_name="testrepo", repo_root=repo, branch="main",
        db_export_dir=db_export, skip_pull=True,
    )
    merge_record = next(r for r in records if r["commit_message_first_line"].startswith("merge"))
    assert len(merge_record["commit_parent_shas"]) == 2


def test_lowercase_sha_normalization(tmp_path):
    """SHAs are emitted in lowercase per commit.md §3.2.1 spec."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    _init_git_repo(repo, ("test commit", ""))
    records = enumerate_commits._enumerate_repo(
        repo_name="testrepo", repo_root=repo, branch="main",
        db_export_dir=db_export, skip_pull=True,
    )
    for r in records:
        assert r["commit_sha"] == r["commit_sha"].lower()
        assert len(r["commit_sha"]) == 40


def test_repo_root_not_git_repo_raises(tmp_path):
    """A non-git repo_root produces a clear error."""
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    with pytest.raises(RuntimeError, match="not a git repository"):
        enumerate_commits._enumerate_repo(
            repo_name="x", repo_root=not_a_repo, branch="main",
            db_export_dir=db_export, skip_pull=True,
        )


def test_main_cli_writes_json_to_stdout(tmp_path, capsys):
    """End-to-end: the CLI writes the JSON array to stdout."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    _init_git_repo(repo, ("test commit", ""))
    rc = enumerate_commits.main([
        "--repos", "testrepo",
        "--engagement-db-export", str(db_export),
        "--repo-root", str(repo),
        "--skip-pull",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["commit_repository"] == "testrepo"
