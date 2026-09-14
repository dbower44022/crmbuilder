"""Stored references that point at a missing record — PI-502.

REQ-598 / DEC-1081. Creating a reference now requires both of its records to
exist (REQ-596), but references written before that check may still name a
record that is not there. A census of production on 2026-09-14 found seven of
13,787: two whose source was an unreplaced ``__SELF__`` placeholder, three
deposit-event back-references to planning items no longer present, one to an
instance held in another engagement, and one to a commit named by its short
hash.

This lists them, per engagement, with the relationship and the missing end, and
exits non-zero when it lists anything. **It never changes a reference.** Whether
a dangling reference should be deleted, re-pointed or left as history is a
judgement about what it was meant to say, which only a person can make.

The census runs in the store (``GET /references/dangling``), read over the API
for the same reason the planning-item drift check reads it there: the local
SQLite store is not a source of truth, and a census of a stale store would
report differences that are an artefact of reading the wrong one.

Exit codes: 0 no dangling reference; 1 at least one listed; 2 the check could
not run (no credentials, or the store could not be reached).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable

Fetch = Callable[[str, str], object]


def _fetcher(base_url: str, token: str) -> Fetch:
    def fetch(path: str, engagement: str) -> object:
        headers = {"Authorization": f"Bearer {token}"}
        if engagement:
            headers["X-Engagement"] = engagement
        request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", headers=headers)
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response).get("data")

    return fetch


def engagements(fetch: Fetch) -> list[str]:
    """Every engagement the store holds, by identifier."""
    rows = fetch("/engagements", "") or []
    return sorted(r["engagement_identifier"] for r in rows if r.get("engagement_identifier"))


def census(fetch: Fetch, engagement_ids: list[str]) -> dict[str, list[dict]]:
    """``{engagement: its dangling references}``, engagements with none omitted."""
    out: dict[str, list[dict]] = {}
    for engagement in engagement_ids:
        rows = fetch("/references/dangling", engagement) or []
        if rows:
            out[engagement] = list(rows)
    return out


def describe(row: dict) -> str:
    """One line per reference: what it says and which record is missing."""
    ident = row.get("reference_identifier") or f"id {row.get('id')}"
    missing = " and ".join(row.get("missing") or [])
    return (
        f"{ident}: {row['source_type']} {row['source_id']!r} "
        f"--{row['relationship']}--> {row['target_type']} {row['target_id']!r} "
        f"(missing: {missing})"
    )


def report(found: dict[str, list[dict]], checked: list[str]) -> tuple[str, int]:
    """The printed report and the exit code for a census result."""
    total = sum(len(rows) for rows in found.values())
    if not total:
        return (
            f"No reference points at a missing record in {len(checked)} "
            "engagement(s) checked.",
            0,
        )
    lines = [f"{total} reference(s) point at a record that does not exist:", ""]
    for engagement in sorted(found):
        lines.append(f"{engagement}:")
        lines += [f"  {describe(row)}" for row in found[engagement]]
    lines += [
        "",
        "Correct each by hand: delete it, re-point it, or leave it as history. "
        "This check never changes a reference.",
    ]
    return "\n".join(lines), 1


def main(argv: list[str] | None = None) -> int:
    """Report stored references to missing records; exit 1 when any exist."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engagement",
        action="append",
        help="check only this engagement (repeatable); default: every engagement",
    )
    args = parser.parse_args(argv)

    base_url = os.environ.get("CRMBUILDER_V2_API_BASE_URL")
    token = os.environ.get("CRMBUILDER_V2_API_TOKEN")
    if not base_url or not token:
        print(
            "Set CRMBUILDER_V2_API_BASE_URL and CRMBUILDER_V2_API_TOKEN. The "
            "check reads the store over the API deliberately — the local "
            "SQLite store is not a source of truth."
        )
        return 2
    fetch = _fetcher(base_url, token)
    try:
        checked = args.engagement or engagements(fetch)
        found = census(fetch, checked)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"The check could not run: {exc}")
        return 2
    text, code = report(found, checked)
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
