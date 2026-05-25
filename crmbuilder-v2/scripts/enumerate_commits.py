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
        --repo-root-override ClevelandBusinessMentoring=~/Dropbox/Projects/ClevelandBusinessMentors \\
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

    # --reverse asks git to emit commits in chronological order
    # (ascending committed_at), matching the order in which the apply
    # script will assign CM-NNNN identifiers. Doing this in git is more
    # robust than a Python post-sort, because same-second commits keep
    # their natural commit order rather than relying on stable-sort
    # behaviour against identical sort keys.
    log_output = _run(
        ["git", "log", "--reverse", log_range, f"--format={_GIT_LOG_FORMAT}"],
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

    return records


def _files_changed_count(sha: str, repo_root: Path) -> int:
    """Count files changed in commit ``sha``. Empty commits (allowed via
    ``git commit --allow-empty``) return 0. ``--root`` ensures the
    initial commit (no parent) compares against the empty tree rather
    than emitting nothing."""
    output = _run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha],
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
