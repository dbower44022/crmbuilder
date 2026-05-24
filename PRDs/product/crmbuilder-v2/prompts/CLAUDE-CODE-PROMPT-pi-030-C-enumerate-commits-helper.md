# CLAUDE-CODE-PROMPT — PI-030 Slice C: `enumerate_commits.py` helper script

**Last Updated:** 05-24-26 17:00
**Workstream:** Code Change Lifecycle (PI-030)
**Operating mode:** DETAIL
**Predecessors:** None at the code level (independent of slices A and B). Conceptually depends on the methodology document and the commit schema spec (both already shipped via PI-027/PI-028).
**Successor:** None — this helper is the sandbox-side tool used at close-out authoring time. No downstream Claude Code prompts depend on it.
**Spec authority:**
- `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0+amendment — §5.5 (when a commit gets ingested; the range-based enumeration rule)
- `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` v1.0 — §3.2 (field validation: SHA shape, author email shape, committed_at ISO 8601 with offset, files_changed_count non-negative integer)
- `PRDs/product/crmbuilder-v2/close-out-payloads/ses_070.json` — DEC-222 (emit-time helper, full records in payload)

---

## Purpose

Author a standalone Python script at `crmbuilder-v2/scripts/enumerate_commits.py` that produces the JSON array suitable to paste into a close-out payload's `commits` section. The helper:

1. Reads the db-export commits snapshot to find the last-ingested SHA per repository (`commit_sha` of the highest-`commit_committed_at` row).
2. Runs `git pull --ff-only` per repo so the local clone reflects origin.
3. Enumerates commits via `git log <last-ingested-sha>..HEAD --format=...` per repo using ASCII control-character separators to safely parse multi-line commit messages.
4. Counts files-changed per SHA via `git diff-tree --no-commit-id --name-only -r <sha> | wc -l`.
5. Emits a JSON array (one object per commit) carrying every field the apply script needs: `commit_sha`, `commit_message_first_line`, `commit_message_full`, `commit_author_name`, `commit_author_email`, `commit_committed_at`, `commit_repository`, `commit_branch`, `commit_parent_shas`, `commit_files_changed_count`.

The helper does NOT POST to the API. It does NOT modify any state. It writes JSON to stdout (or to `--output <path>` if provided). The downstream consumer pastes the array into the close-out payload's `commits` section at close-out authoring time.

---

## Net effect

After this slice lands:

- `crmbuilder-v2/scripts/enumerate_commits.py` exists and is invokable via `uv run python scripts/enumerate_commits.py --help`.
- The helper reads from disk only (no network access except `git pull --ff-only`); no API dependency.
- The output JSON conforms to the schema commit.md specifies and is directly consumable by the apply script's commits section handling (slice B).
- Tests cover happy path, no-prior-commits bootstrap, ASCII-separator parsing of multi-line messages, files-changed-count extraction, and multi-repo handling.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder
git status                                    # expect clean
git pull --rebase origin main                 # ensure latest
ls crmbuilder-v2/scripts/apply_close_out.py   # exists (reference for style)
ls PRDs/product/crmbuilder-v2/db-export/      # exists; check whether commits.json
                                              # exists yet (may not — bootstrap case)

cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/scripts/ -q 2>&1 | tail -5
# Capture baseline test count for scripts/. This slice adds ~8 tests there.
```

---

## Changes

### 1. Create `crmbuilder-v2/scripts/enumerate_commits.py`

File: `crmbuilder-v2/scripts/enumerate_commits.py` (new)

```python
#!/usr/bin/env python3
"""Enumerate commits for a close-out payload's `commits` section.

Per methodology §5.5: at close-out authoring time, the helper walks
`<last-ingested-sha-per-repo>..<current-HEAD-per-repo>` for each repo
the conversation touched. The "last-ingested SHA" is the
highest-`commit_committed_at` row in the engagement's db-export
`commits.json` snapshot for that repository.

Output is a JSON array suitable to paste into the close-out payload's
`commits` section. Each entry conforms to the schema in
`governance-schema-specs/commit.md` §3.2.

Invocation (from the sandbox, at close-out authoring time):

    uv run python scripts/enumerate_commits.py \\
        --repos crmbuilder \\
        --engagement-db-export PRDs/product/crmbuilder-v2/db-export \\
        --repo-root . \\
        --branch main

Or for a multi-repo conversation:

    uv run python scripts/enumerate_commits.py \\
        --repos crmbuilder,ClevelandBusinessMentoring \\
        --engagement-db-export PRDs/product/crmbuilder-v2/db-export \\
        --repo-root . \\
        --repo-root-ClevelandBusinessMentoring ~/Dropbox/Projects/ClevelandBusinessMentors \\
        --branch main

The helper writes JSON to stdout by default; use ``--output <path>`` to
write to a file. Exit code 0 on success; 1 on any git failure or
parse error; 2 on argument validation failure.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# ASCII control-character separators. US (\x1f) separates fields; RS
# (\x1e) separates records. These bytes cannot legitimately appear in
# commit message text, so they make safe delimiters even when messages
# contain embedded newlines, quotes, or other special characters.
_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"

# git log format string built from the separators. Order corresponds to
# the per-record tuple unpacked below.
_GIT_LOG_FORMAT = _FIELD_SEP.join([
    "%H",   # full SHA
    "%P",   # parent SHAs (space-separated, 0/1/2 entries)
    "%an",  # author name
    "%ae",  # author email
    "%aI",  # author date, strict ISO 8601 with offset
    "%s",   # subject (first line)
    "%B",   # full body including subject
]) + _RECORD_SEP


def _run(cmd: list[str], cwd: Path) -> str:
    """Run a subprocess and return stdout as text. Raise on failure."""
    result = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command {' '.join(cmd)!r} in {cwd} failed "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def _last_ingested_sha(
    db_export_dir: Path, repository: str
) -> str | None:
    """Return the SHA of the highest-`commit_committed_at` row for
    ``repository`` in ``db_export_dir/commits.json``. Returns ``None`` if
    the snapshot doesn't exist yet (first-ever ingestion case) or has
    no rows for the named repository."""
    snapshot = db_export_dir / "commits.json"
    if not snapshot.exists():
        return None
    try:
        rows = json.loads(snapshot.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"could not parse commits snapshot at {snapshot}: {exc}"
        ) from exc
    if not isinstance(rows, list):
        raise RuntimeError(
            f"expected commits snapshot at {snapshot} to be a JSON array; "
            f"got {type(rows).__name__}"
        )
    repo_rows = [r for r in rows if r.get("commit_repository") == repository]
    if not repo_rows:
        return None
    # Sort by commit_committed_at desc. ISO 8601 strings sort
    # lexicographically in chronological order when the offset is
    # consistent. Mixed-offset values may sort imperfectly but the
    # range query is forgiving — over-inclusion produces 409s at apply
    # time, not data corruption.
    repo_rows.sort(
        key=lambda r: r.get("commit_committed_at", ""), reverse=True
    )
    return repo_rows[0].get("commit_sha")


def _enumerate_repo(
    repo_name: str,
    repo_root: Path,
    branch: str,
    db_export_dir: Path,
    skip_pull: bool,
) -> list[dict]:
    """Enumerate commits for one repository. Returns a list of commit
    record dicts in the methodology §4.1 shape."""
    if not (repo_root / ".git").exists():
        raise RuntimeError(
            f"repo_root {repo_root} is not a git repository "
            f"(no .git directory)"
        )

    if not skip_pull:
        # Fast-forward only. If origin has diverged from the local
        # clone, this fails — surface the issue rather than auto-
        # merge.
        _run(["git", "fetch", "origin"], repo_root)
        _run(["git", "pull", "--ff-only", "origin", branch], repo_root)

    since = _last_ingested_sha(db_export_dir, repo_name)
    if since is None:
        log_range = "HEAD"  # All of history (first ingestion)
    else:
        log_range = f"{since}..HEAD"

    log_output = _run(
        ["git", "log", log_range, f"--format={_GIT_LOG_FORMAT}"],
        repo_root,
    )

    records: list[dict] = []
    for raw_record in log_output.split(_RECORD_SEP):
        raw = raw_record.strip()
        if not raw:
            continue
        # Six field separators yield seven fields. The last field
        # (full body) may contain newlines and embedded text.
        parts = raw.split(_FIELD_SEP, 6)
        if len(parts) != 7:
            raise RuntimeError(
                f"unexpected git log record in {repo_name} (got "
                f"{len(parts)} fields, expected 7): {raw[:200]!r}"
            )
        sha, parent_str, author_name, author_email, committed_at, subject, body = parts
        parent_shas = parent_str.split() if parent_str else []
        files_changed_count = _files_changed_count(sha, repo_root)
        records.append({
            "commit_sha": sha.lower(),
            "commit_message_first_line": subject,
            "commit_message_full": body.rstrip("\n"),
            "commit_author_name": author_name,
            "commit_author_email": author_email,
            "commit_committed_at": committed_at,
            "commit_repository": repo_name,
            "commit_branch": branch,
            "commit_parent_shas": parent_shas,
            "commit_files_changed_count": files_changed_count,
        })

    # Sort chronologically ascending so apply-time identifier assignment
    # follows commit order naturally (CM-NNNN increments in committed_at
    # order).
    records.sort(key=lambda r: r["commit_committed_at"])
    return records


def _files_changed_count(sha: str, repo_root: Path) -> int:
    """Count files changed in commit ``sha``. Empty commits (allowed via
    ``git commit --allow-empty``) return 0."""
    output = _run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
        repo_root,
    )
    return len([line for line in output.splitlines() if line.strip()])


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate commits since last-ingested SHA per repository, "
            "producing JSON suitable for a close-out payload's `commits` "
            "section."
        ),
    )
    parser.add_argument(
        "--repos",
        required=True,
        help=(
            "Comma-separated repository names (matching `commit_repository` "
            "values in the snapshot). Example: 'crmbuilder' or "
            "'crmbuilder,ClevelandBusinessMentoring'."
        ),
    )
    parser.add_argument(
        "--engagement-db-export",
        type=Path,
        required=True,
        help=(
            "Path to the engagement's db-export directory containing "
            "`commits.json`. For the CRMBUILDER dogfood engagement: "
            "PRDs/product/crmbuilder-v2/db-export/."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help=(
            "Default repo root used when a per-repo override isn't given. "
            "Defaults to the current working directory."
        ),
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch to enumerate commits on (default: main).",
    )
    parser.add_argument(
        "--skip-pull",
        action="store_true",
        help=(
            "Skip the `git pull --ff-only` step. Useful for tests or when "
            "the caller has already synced."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON to this path instead of stdout.",
    )
    # Per-repo root overrides (e.g., --repo-root-ClevelandBusinessMentoring).
    # argparse doesn't natively support dynamic flag names; accept these
    # as a single repeatable flag instead.
    parser.add_argument(
        "--repo-root-override",
        action="append",
        default=[],
        metavar="REPO=PATH",
        help=(
            "Override the repo root for a specific repository. May be "
            "given multiple times. Example: "
            "--repo-root-override ClevelandBusinessMentoring=~/Dropbox/Projects/ClevelandBusinessMentors"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    if not repos:
        print("error: --repos must name at least one repository", file=sys.stderr)
        return 2

    overrides: dict[str, Path] = {}
    for spec in args.repo_root_override:
        if "=" not in spec:
            print(
                f"error: --repo-root-override must be REPO=PATH, got {spec!r}",
                file=sys.stderr,
            )
            return 2
        key, val = spec.split("=", 1)
        overrides[key.strip()] = Path(val.strip()).expanduser()

    all_records: list[dict] = []
    for repo in repos:
        repo_root = overrides.get(repo, args.repo_root).expanduser()
        try:
            records = _enumerate_repo(
                repo_name=repo,
                repo_root=repo_root,
                branch=args.branch,
                db_export_dir=args.engagement_db_export,
                skip_pull=args.skip_pull,
            )
        except RuntimeError as exc:
            print(f"error enumerating {repo!r}: {exc}", file=sys.stderr)
            return 1
        all_records.extend(records)

    output = json.dumps(all_records, indent=2)
    if args.output:
        args.output.write_text(output + "\n")
        print(
            f"Wrote {len(all_records)} commit record(s) to {args.output}",
            file=sys.stderr,
        )
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 2. Add tests for the helper

File: `tests/crmbuilder_v2/scripts/test_enumerate_commits.py` (new)

```python
"""Tests for enumerate_commits.py — the close-out commit enumerator."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    # The second commit's full body contains the multi-line content
    assert "item one" in records[1]["commit_message_full"]
    assert "item two" in records[1]["commit_message_full"]
    # First line is the subject only
    assert records[1]["commit_message_first_line"] == "multi-line subject"


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
```

### 3. Verify the script is executable

The shebang at line 1 (`#!/usr/bin/env python3`) plus the standard `uv run python scripts/enumerate_commits.py` invocation pattern is enough — no chmod required. Smoke-test:

```bash
cd crmbuilder-v2
uv run python scripts/enumerate_commits.py --help
```

Expect the argparse help output.

---

## Verification

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/scripts/test_enumerate_commits.py -v 2>&1 | tail -20
# Expect: 8 passed, 0 failed

uv run pytest tests/crmbuilder_v2/ -x -q 2>&1 | tail -5
# Full v2 suite — confirm no regression elsewhere
```

Sanity check with the actual crmbuilder repo (this slice's script is being authored IN the crmbuilder repo, so running it against the repo itself is the natural smoke test):

```bash
cd ~/Dropbox/Projects/crmbuilder
uv run python crmbuilder-v2/scripts/enumerate_commits.py \
  --repos crmbuilder \
  --engagement-db-export PRDs/product/crmbuilder-v2/db-export \
  --repo-root . \
  --skip-pull \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Found {len(d)} commits since last ingested')"
```

Expect: a count corresponding to commits-since-last-snapshot (likely small if commits.json doesn't exist yet — the helper enumerates all of history in that case).

---

## Commit

```bash
cd ~/Dropbox/Projects/crmbuilder
git add crmbuilder-v2/scripts/enumerate_commits.py
git add tests/crmbuilder_v2/scripts/test_enumerate_commits.py
git commit -m "v2: PI-030 slice C — enumerate_commits.py helper for close-out commit ingestion

New standalone script that produces the JSON array suitable to paste
into a close-out payload's commits section. Sandbox-side use, invoked
at close-out authoring time per methodology §5.5.

Mechanics:
- Reads db-export/commits.json to find the per-repo last-ingested SHA
  (highest commit_committed_at value for that repository).
- Runs git pull --ff-only per repo (skippable via --skip-pull for tests).
- Enumerates commits via 'git log <since>..HEAD --format=...' using
  ASCII control-character separators (US/RS) for safe multi-line
  commit message parsing.
- Counts files-changed per SHA via git diff-tree.
- Emits JSON in commit.md §3.2 shape.

CLI surface:
- --repos crmbuilder[,ClevelandBusinessMentoring]
- --engagement-db-export <path>
- --repo-root <path> + --repo-root-override REPO=PATH for multi-repo
- --branch main
- --skip-pull
- --output <path> (default stdout)

Tests: 8 covering happy path, bootstrap (no snapshot), since-snapshot
filtering, multi-line message parsing, merge commit parent extraction,
lowercase SHA normalization, non-git repo error, CLI end-to-end.

Authority: DEC-222 (emit-time helper, full records in payload),
methodology §5.5 (commit enumeration range)."

# Per the 'you commit, I push' convention in Claude Code context,
# do NOT push here. Doug reviews and pushes manually:
#   git pull --rebase origin main
#   git push
```

---

## Done

Reply with:

- pytest result for tests/crmbuilder_v2/scripts/test_enumerate_commits.py: 8 passed
- Full v2 suite: `<scripts-baseline>` + 8 = `<post-count>` passed, 0 failed
- CLI help works: `uv run python crmbuilder-v2/scripts/enumerate_commits.py --help` shows expected usage
- Smoke test against this repo: N commits found (number depends on commits.json snapshot state)
- Commit SHA
- Next: PI-030 is complete after all three slices land. Backfill (PI-033) and UI (PI-031) are separate downstream conversations.
