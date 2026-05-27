"""Tests for enumerate_commits.py — the close-out commit enumerator."""
from __future__ import annotations

import importlib.util
import json
import os
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


# ---------------------------------------------------------------------------
# PI-050: --commits explicit-list mode tests
# ---------------------------------------------------------------------------


def test_explicit_commits_single_sha(tmp_path):
    """--commits with one SHA returns exactly one commit record for it."""
    repo = tmp_path / "repo"
    shas = _init_git_repo(repo,
        ("first commit", ""),
        ("second commit", ""),
        ("third commit", ""),
    )
    records = enumerate_commits._enumerate_explicit_commits(
        repo_name="testrepo",
        repo_root=repo,
        branch="main",
        commit_shas=[shas[1]],
    )
    assert len(records) == 1
    assert records[0]["commit_sha"] == shas[1]
    assert records[0]["commit_message_first_line"] == "second commit"
    assert records[0]["commit_repository"] == "testrepo"
    assert records[0]["commit_branch"] == "main"


def test_explicit_commits_multiple_shas_chronological_order(tmp_path):
    """--commits with multiple SHAs returns them in chronological order
    (oldest first), regardless of the order they appear in the
    --commits argument."""
    repo = tmp_path / "repo"
    # Use commits with distinct timestamps so chronological order is
    # deterministic. GIT_AUTHOR_DATE / GIT_COMMITTER_DATE override the
    # natural clock.
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)

    shas: list[str] = []
    for i, ts in enumerate([
        "2026-05-01T10:00:00 -0400",
        "2026-05-02T10:00:00 -0400",
        "2026-05-03T10:00:00 -0400",
        "2026-05-04T10:00:00 -0400",
    ]):
        f = repo / f"file_{i}.txt"
        f.write_text(f"content {i}\n")
        subprocess.run(["git", "add", str(f)], cwd=repo, check=True)
        env_extra = {
            "GIT_AUTHOR_DATE": ts,
            "GIT_COMMITTER_DATE": ts,
        }
        env = {**os.environ, **env_extra}
        subprocess.run(
            ["git", "commit", "-q", "-m", f"commit {i}"],
            cwd=repo, check=True, env=env,
        )
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo, capture_output=True, text=True, check=True,
        )
        shas.append(result.stdout.strip())

    # Pass commits in REVERSE order to confirm the script sorts them.
    records = enumerate_commits._enumerate_explicit_commits(
        repo_name="testrepo",
        repo_root=repo,
        branch="main",
        commit_shas=[shas[3], shas[1], shas[2]],
    )
    assert len(records) == 3
    # Chronological order: shas[1], shas[2], shas[3]
    assert [r["commit_sha"] for r in records] == [shas[1], shas[2], shas[3]]


def test_explicit_commits_invalid_sha_raises_clear_error(tmp_path):
    """An unknown SHA raises RuntimeError naming the offender."""
    repo = tmp_path / "repo"
    _init_git_repo(repo, ("first commit", ""))
    bogus = "0" * 40
    with pytest.raises(RuntimeError, match=f"unknown commit SHA.*{bogus}"):
        enumerate_commits._enumerate_explicit_commits(
            repo_name="testrepo",
            repo_root=repo,
            branch="main",
            commit_shas=[bogus],
        )


def test_explicit_commits_main_cli(tmp_path, capsys):
    """End-to-end via main(): --commits emits two records in
    chronological order without --engagement-db-export."""
    repo = tmp_path / "repo"
    shas = _init_git_repo(repo,
        ("first commit", ""),
        ("second commit", ""),
        ("third commit", ""),
    )
    # Pick first and third, in reverse argument order
    rc = enumerate_commits.main([
        "--repos", "testrepo",
        "--repo-root", str(repo),
        "--commits", f"{shas[2]},{shas[0]}",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed) == 2
    # Chronological order: first then third
    assert parsed[0]["commit_sha"] == shas[0]
    assert parsed[1]["commit_sha"] == shas[2]


def test_explicit_commits_main_cli_unknown_sha_exits_nonzero(tmp_path, capsys):
    """main() returns exit code 1 with a clear error on an unknown SHA."""
    repo = tmp_path / "repo"
    _init_git_repo(repo, ("first commit", ""))
    bogus = "deadbeef" * 5  # 40-char hex but invalid
    rc = enumerate_commits.main([
        "--repos", "testrepo",
        "--repo-root", str(repo),
        "--commits", bogus,
    ])
    assert rc == 1
    captured = capsys.readouterr()
    assert "unknown commit SHA" in captured.err
    assert bogus in captured.err


def test_explicit_commits_warns_when_engagement_db_export_supplied(
    tmp_path, capsys
):
    """When both --commits and --engagement-db-export are supplied,
    --engagement-db-export is ignored and a warning is printed."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    shas = _init_git_repo(repo, ("only commit", ""))
    rc = enumerate_commits.main([
        "--repos", "testrepo",
        "--engagement-db-export", str(db_export),
        "--repo-root", str(repo),
        "--commits", shas[0],
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "ignored" in captured.err.lower()
    parsed = json.loads(captured.out)
    assert len(parsed) == 1
    assert parsed[0]["commit_sha"] == shas[0]


def test_default_range_mode_behavior_unchanged(tmp_path, capsys):
    """Default behavior (no --commits) preserves the existing
    since..HEAD range-mode contract."""
    repo = tmp_path / "repo"
    db_export = tmp_path / "db-export"
    db_export.mkdir()
    shas = _init_git_repo(repo,
        ("first commit", ""),
        ("second commit", ""),
        ("third commit", ""),
    )
    rc = enumerate_commits.main([
        "--repos", "testrepo",
        "--engagement-db-export", str(db_export),
        "--repo-root", str(repo),
        "--skip-pull",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed) == 3
    assert [r["commit_sha"] for r in parsed] == shas
    # No warning printed in pure range mode
    assert "warning" not in captured.err.lower()


def test_range_mode_requires_engagement_db_export(tmp_path, capsys):
    """Omitting --engagement-db-export in range mode is an arg error."""
    repo = tmp_path / "repo"
    _init_git_repo(repo, ("first commit", ""))
    rc = enumerate_commits.main([
        "--repos", "testrepo",
        "--repo-root", str(repo),
        "--skip-pull",
    ])
    assert rc == 2
    captured = capsys.readouterr()
    assert "--engagement-db-export" in captured.err


def test_explicit_commits_repo_root_not_git_raises(tmp_path):
    """A non-git repo_root in explicit-list mode also raises clearly."""
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    with pytest.raises(RuntimeError, match="not a git repository"):
        enumerate_commits._enumerate_explicit_commits(
            repo_name="x", repo_root=not_a_repo, branch="main",
            commit_shas=["0" * 40],
        )
