"""Planning items recorded as unstarted while their work is merged — PI-458.

REQ-556 / DEC-996. In one day four parallel sessions merged code without moving
the planning item governing it, leaving the store — the declared source of truth
— saying a delivered branch was unstarted, and leaving ``blocked_by`` edges shut
against finished work. Governance rules requiring real-time recording were in
force throughout and prevented none of it, so this reports the drift rather than
asking anyone for more discipline.

The data needed already exists: every code commit carries a ``Governed-By``
trailer naming its planning item, because a separate gate already requires one.

**What this deliberately does not do.** It never changes a status. Closing an
item rests on verifying its acceptance criteria, which is judgement; a check that
resolved an item it could not verify would manufacture exactly the false
assurance this exists to prevent. It also says nothing about an item merely
*stalled* — in progress with its work long delivered — which DEC-996 records as
a known remaining gap rather than an oversight.

The comparison itself is pure and unit-tested; only :func:`main` touches git or
the store, because a check that compares live records against real history cannot
be hermetic and should not pretend otherwise.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

#: The trailer every code commit carries, naming the planning item it is
#: governed by. ``Governed-By: trivial`` names no item and is skipped.
_GOVERNED_BY = re.compile(r"^Governed-By:\s*(PI-\d+)\s*$", re.MULTILINE)

#: The status meaning the work has not begun. A planning item with merged
#: commits may legitimately be in progress or terminal; only this one is a
#: contradiction (REQ-556).
UNSTARTED = "Draft"


@dataclass(frozen=True)
class Drift:
    """One planning item whose record contradicts what is merged."""

    planning_item: str
    status: str
    commits: tuple[str, ...]

    def describe(self) -> str:
        shown = ", ".join(self.commits[:5])
        more = f" (+{len(self.commits) - 5} more)" if len(self.commits) > 5 else ""
        return (
            f"{self.planning_item} is recorded {self.status!r} but has merged "
            f"work: {shown}{more}"
        )


def planning_items_in(commits: dict[str, str]) -> dict[str, tuple[str, ...]]:
    """``{planning item: the commits naming it}`` from ``{sha: message}``.

    A commit naming no planning item, or naming the trivial exemption rather
    than an item, contributes nothing — it is exempt by the gate that requires
    the trailer, not evidence about any item.
    """
    found: dict[str, list[str]] = {}
    for sha, message in commits.items():
        for identifier in dict.fromkeys(_GOVERNED_BY.findall(message or "")):
            found.setdefault(identifier, []).append(sha)
    return {k: tuple(v) for k, v in sorted(found.items())}


def drifted(
    items_to_commits: dict[str, tuple[str, ...]],
    statuses: dict[str, str],
) -> list[Drift]:
    """Planning items with merged commits whose record still says unstarted.

    An item absent from ``statuses`` is not reported: this check answers whether
    a known item's status contradicts its commits, and an unknown identifier is
    a different problem — a trailer naming an item that does not exist — which
    the trailer gate is the place to catch.
    """
    return [
        Drift(identifier, statuses[identifier], commits)
        for identifier, commits in items_to_commits.items()
        if statuses.get(identifier) == UNSTARTED
    ]


def merged_commits(ref: str = "origin/main", limit: int = 400) -> dict[str, str]:
    """``{short sha: full message}`` for the commits merged into ``ref``.

    Bounded rather than reading the whole history: the drift this catches is
    recent by nature, and an unbounded walk would re-report items settled long
    ago whose records were corrected by hand.
    """
    out = subprocess.run(
        ["git", "log", ref, f"-{limit}", "--format=%h%x00%B%x1e"],
        capture_output=True, text=True, check=True,
    ).stdout
    commits: dict[str, str] = {}
    for record in out.split("\x1e"):
        if "\x00" not in record:
            continue
        sha, message = record.split("\x00", 1)
        commits[sha.strip()] = message
    return commits


def _statuses(
    identifiers: list[str], *, base_url: str, token: str, engagement: str
) -> dict[str, str]:
    """Recorded status for each named planning item, read from the store.

    Read over the API rather than through the access layer on purpose. The
    local SQLite store was retired as a source of truth by the cloud cutover and
    may sit behind on migrations, so an access-layer read here would compare
    merged commits against a stale record and report drift that is an artefact
    of reading the wrong store — the precise class of confident wrong answer
    this check exists to surface.

    An identifier the store does not know is omitted rather than guessed at; see
    :func:`drifted`.
    """
    import json
    import urllib.error
    import urllib.request

    out: dict[str, str] = {}
    for identifier in identifiers:
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/planning-items/{identifier}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Engagement": engagement,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                record = json.load(response).get("data")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue  # unknown identifier — the trailer gate's concern
            raise
        if record:
            out[identifier] = record["status"]
    return out


def main(argv: list[str] | None = None) -> int:
    """Report planning items recorded as unstarted while their work is merged.

    Exit 0 when the record agrees with what is merged, 1 when it does not. A
    non-zero exit says a record is misleading, not that anything is broken —
    the fix is to move a status, and only a person can decide which.
    """
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--engagement", default="ENG-001")
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

    items = planning_items_in(merged_commits(args.ref, args.limit))
    if not items:
        print(f"No governed commits found on {args.ref}.")
        return 0
    findings = drifted(
        items,
        _statuses(
            list(items), base_url=base_url, token=token,
            engagement=args.engagement,
        ),
    )
    if not findings:
        print(
            f"{len(items)} planning item(s) with merged work on {args.ref}; "
            "none recorded as unstarted."
        )
        return 0
    print(
        f"{len(findings)} planning item(s) recorded as {UNSTARTED!r} while "
        f"their work is merged on {args.ref}:\n"
    )
    for finding in findings:
        print(f"  {finding.describe()}")
    print(
        "\nMove each to its true status. This check never does so itself: "
        "closing an item rests on verifying its acceptance criteria."
    )
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
