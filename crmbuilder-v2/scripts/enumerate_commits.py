#!/usr/bin/env python3
"""Enumerate commits for a close-out payload's `commits` section.

Per methodology §5.5: at close-out authoring time, the helper walks
`<last-ingested-sha-per-repo>..<current-HEAD-per-repo>` for each repo
the conversation touched. The "last-ingested SHA" is the
highest-`commit_committed_at` row already recorded for that repository.

PI-β removed the git-tracked `db-export/` JSON snapshot tree (the DB is
the source of truth), so the default source for the last-ingested SHA is
now the **live REST API** (`GET /commits?commit_repository=...` sorted by
`commit_committed_at desc`), not a `commits.json` file. The legacy
file-based source remains available via ``--engagement-db-export`` for
offline use, but it is no longer the default and is no longer required.

Output is a JSON array suitable to paste into the close-out payload's
`commits` section. Each entry conforms to the schema in
`governance-schema-specs/commit.md` §3.2.

Invocation (at close-out authoring time, with the API running):

    uv run python scripts/enumerate_commits.py \\
        --repos crmbuilder \\
        --api-base http://127.0.0.1:8765 \\
        --engagement CRMBUILDER \\
        --repo-root . \\
        --branch main

Or for a multi-repo conversation:

    uv run python scripts/enumerate_commits.py \\
        --repos crmbuilder,ClevelandBusinessMentoring \\
        --api-base http://127.0.0.1:8765 \\
        --engagement CRMBUILDER \\
        --repo-root . \\
        --repo-root-override ClevelandBusinessMentoring=~/Dropbox/Projects/ClevelandBusinessMentors \\
        --branch main

In practice most close-outs use ``--commits <sha,sha,...>`` (explicit-list
mode), which bypasses the last-ingested-SHA lookup entirely.

The helper writes JSON to stdout by default; use ``--output <path>`` to
write to a file. Exit code 0 on success; 1 on any git failure or
parse error; 2 on argument validation failure.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
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


class _ApiUnreachable(RuntimeError):
    """The REST API could not be reached or returned an unparseable body.

    Raised by :func:`_last_ingested_sha_from_api` so the caller can decide
    to degrade gracefully (warn + fall back to full history) rather than
    abort the whole enumeration."""


def _last_ingested_sha_from_api(
    api_base: str, repository: str, engagement: str
) -> str | None:
    """Return the SHA of the most recently committed commit row recorded
    for ``repository``, read from the live REST API.

    Queries ``GET {api_base}/commits?commit_repository=<repo>
    &sort=commit_committed_at&order=desc`` (the post-PI-β replacement for
    the deleted ``db-export/commits.json`` snapshot), unwraps the
    ``{data, meta, errors}`` envelope, and returns the first row's
    ``commit_sha``. Returns ``None`` when no commit has been ingested for
    the repository yet (first-ingestion case). Raises
    :class:`_ApiUnreachable` on a network/parse failure so the caller can
    fall back to full history."""
    query = urllib.parse.urlencode(
        {
            "commit_repository": repository,
            "sort": "commit_committed_at",
            "order": "desc",
        }
    )
    url = f"{api_base.rstrip('/')}/commits?{query}"
    request = urllib.request.Request(url, headers={"X-Engagement": engagement})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise _ApiUnreachable(
            f"could not read commits from {url}: {exc}"
        ) from exc
    rows = payload.get("data") or []
    if not rows:
        return None
    # The API already sorted descending by commit_committed_at, so the
    # first row is the most recent.
    return rows[0].get("commit_sha")


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


def _parse_log_output(
    log_output: str,
    repo_name: str,
    repo_root: Path,
    branch: str,
) -> list[dict]:
    """Parse the raw ``git log`` output (formatted with ``_GIT_LOG_FORMAT``)
    into a list of commit-record dicts in the methodology §4.1 shape.
    Factored out so both the range-mode and explicit-list-mode paths
    share the same record-construction logic."""
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


def _enumerate_repo_with_since(
    repo_name: str,
    repo_root: Path,
    branch: str,
    since: str | None,
    skip_pull: bool,
) -> list[dict]:
    """Enumerate commits for one repository given an already-resolved
    ``since`` SHA (or ``None`` for all of history). Shared by both the
    API-backed and file-backed range modes."""
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

    return _parse_log_output(log_output, repo_name, repo_root, branch)


def _enumerate_repo(
    repo_name: str,
    repo_root: Path,
    branch: str,
    db_export_dir: Path,
    skip_pull: bool,
) -> list[dict]:
    """Enumerate commits for one repository using the legacy file-based
    ``db-export/commits.json`` snapshot as the last-ingested-SHA source.
    Retained for offline use and back-compat; the default path is now
    :func:`_enumerate_repo_via_api`."""
    since = _last_ingested_sha(db_export_dir, repo_name)
    return _enumerate_repo_with_since(
        repo_name=repo_name,
        repo_root=repo_root,
        branch=branch,
        since=since,
        skip_pull=skip_pull,
    )


def _enumerate_repo_via_api(
    repo_name: str,
    repo_root: Path,
    branch: str,
    api_base: str,
    engagement: str,
    skip_pull: bool,
) -> list[dict]:
    """Enumerate commits for one repository using the live REST API as the
    last-ingested-SHA source. On an unreachable/unparseable API, warns and
    degrades to full history (over-inclusion produces 409s at apply time,
    not data corruption)."""
    try:
        since = _last_ingested_sha_from_api(api_base, repo_name, engagement)
    except _ApiUnreachable as exc:
        print(
            f"warning: {exc}; falling back to full history for {repo_name!r} "
            f"(pass --engagement-db-export for an offline source, or verify "
            f"the API is running at {api_base})",
            file=sys.stderr,
        )
        since = None
    return _enumerate_repo_with_since(
        repo_name=repo_name,
        repo_root=repo_root,
        branch=branch,
        since=since,
        skip_pull=skip_pull,
    )


def _enumerate_explicit_commits(
    repo_name: str,
    repo_root: Path,
    branch: str,
    commit_shas: list[str],
) -> list[dict]:
    """Enumerate exactly the named commit SHAs from the working tree,
    emitting records in chronological order (oldest first). Bypasses
    the since..HEAD range model entirely. Used when parallel
    workstreams interleave commits on the same branch and a range
    query would pull in unrelated commits — see PI-050 and SES-074's
    DEC-233 workaround.

    Each SHA is validated with ``git cat-file -e`` before enumeration;
    an unknown SHA raises ``RuntimeError`` naming the offending value.
    """
    if not (repo_root / ".git").exists():
        raise RuntimeError(
            f"repo_root {repo_root} is not a git repository "
            f"(no .git directory)"
        )

    # Validate each SHA before doing any further work, so a typo
    # fails fast with a clear message naming the offender.
    for sha in commit_shas:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=str(repo_root), capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"unknown commit SHA in {repo_name}: {sha!r} "
                f"(git cat-file: {result.stderr.strip() or 'no such object'})"
            )

    # ``git log --no-walk`` emits records for exactly the named commits
    # without traversing parents. Combined with ``--date-order``, git
    # sorts the output by commit date — we then pass ``--reverse`` to
    # flip into chronological (oldest-first) order, matching the range-
    # mode behaviour and the CM-NNNN identifier-assignment order the
    # apply script uses.
    log_output = _run(
        [
            "git", "log", "--no-walk", "--date-order", "--reverse",
            f"--format={_GIT_LOG_FORMAT}", *commit_shas,
        ],
        repo_root,
    )

    return _parse_log_output(log_output, repo_name, repo_root, branch)


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
        required=False,
        default=None,
        help=(
            "Comma-separated repository names (matching `commit_repository` "
            "values in the snapshot). Example: 'crmbuilder' or "
            "'crmbuilder,ClevelandBusinessMentoring'. Required in range "
            "mode; in --commits explicit-list mode, defaults to a single "
            "repository named 'crmbuilder' when omitted (override with "
            "--repos REPONAME)."
        ),
    )
    parser.add_argument(
        "--engagement-db-export",
        type=Path,
        required=False,
        default=None,
        help=(
            "Path to a legacy db-export directory containing "
            "`commits.json`, used as the last-ingested-SHA source instead "
            "of the live API. PI-β deleted the tracked db-export tree, so "
            "this is now an offline opt-in, not the default. Ignored when "
            "--commits is provided (explicit-list mode bypasses the "
            "since..HEAD range)."
        ),
    )
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8765",
        help=(
            "Base URL of the live REST API used to read the last-ingested "
            "SHA per repository (GET /commits?commit_repository=...&sort="
            "commit_committed_at&order=desc). The post-PI-β default source. "
            "Ignored when --engagement-db-export or --commits is provided. "
            "Default: http://127.0.0.1:8765."
        ),
    )
    parser.add_argument(
        "--engagement",
        default="CRMBUILDER",
        help=(
            "Engagement identifier/code sent as the X-Engagement header on "
            "API queries (default: CRMBUILDER). Ignored unless the API is "
            "the last-ingested-SHA source."
        ),
    )
    parser.add_argument(
        "--commits",
        default=None,
        help=(
            "Comma-separated list of full commit SHAs. When set, the "
            "helper emits commit-record JSON for exactly these SHAs in "
            "chronological order (oldest first), bypassing the "
            "since..HEAD range entirely. Use this when multiple "
            "workstreams interleave commits on `main` and the natural "
            "range would pull in unrelated commits (see PI-050 and "
            "SES-074's DEC-233 workaround). Each SHA is validated "
            "against the working tree's git history; an unknown SHA "
            "errors out by name."
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

    explicit_mode = args.commits is not None

    # In range mode, --repos is required. The last-ingested-SHA source is
    # the live API by default (post-PI-β); --engagement-db-export selects
    # the legacy file source instead. In explicit-list mode, --repos
    # defaults to "crmbuilder" and neither source is consulted. Surface a
    # warning when the operator supplied --engagement-db-export alongside
    # --commits so the misuse is visible.
    if explicit_mode:
        if args.engagement_db_export is not None:
            print(
                "warning: --engagement-db-export is ignored when --commits "
                "is provided (explicit-list mode bypasses the "
                "since..HEAD range)",
                file=sys.stderr,
            )
        repos_raw = args.repos if args.repos is not None else "crmbuilder"
    else:
        if args.repos is None:
            print(
                "error: --repos is required in range mode (omit --commits "
                "to use range mode, or pass --repos REPONAME explicitly)",
                file=sys.stderr,
            )
            return 2
        repos_raw = args.repos

    repos = [r.strip() for r in repos_raw.split(",") if r.strip()]
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

    if explicit_mode:
        commit_shas = [s.strip() for s in args.commits.split(",") if s.strip()]
        if not commit_shas:
            print(
                "error: --commits must name at least one commit SHA",
                file=sys.stderr,
            )
            return 2
        if len(repos) != 1:
            print(
                "error: --commits explicit-list mode requires exactly one "
                "repository in --repos (multi-repo enumeration with "
                "explicit SHAs requires separate invocations)",
                file=sys.stderr,
            )
            return 2
        repo = repos[0]
        repo_root = overrides.get(repo, args.repo_root).expanduser()
        try:
            all_records = _enumerate_explicit_commits(
                repo_name=repo,
                repo_root=repo_root,
                branch=args.branch,
                commit_shas=commit_shas,
            )
        except RuntimeError as exc:
            print(f"error enumerating {repo!r}: {exc}", file=sys.stderr)
            return 1
    else:
        all_records = []
        use_file_source = args.engagement_db_export is not None
        for repo in repos:
            repo_root = overrides.get(repo, args.repo_root).expanduser()
            try:
                if use_file_source:
                    records = _enumerate_repo(
                        repo_name=repo,
                        repo_root=repo_root,
                        branch=args.branch,
                        db_export_dir=args.engagement_db_export,
                        skip_pull=args.skip_pull,
                    )
                else:
                    records = _enumerate_repo_via_api(
                        repo_name=repo,
                        repo_root=repo_root,
                        branch=args.branch,
                        api_base=args.api_base,
                        engagement=args.engagement,
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
