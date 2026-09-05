"""Back-fill ``withdraws`` edges for withdrawals recorded by status alone.

PI-462 (REQ-560 / DEC-1034) registers the ``withdraws`` reference kind: the
withdrawing decision → the artifact it withdrew without replacing. Withdrawals
recorded before the kind existed carry only the status change and, at best, an
``is_about`` edge from the decision. This script finds them and proposes the
missing edge.

A candidate is a (decision, artifact) pair where

* the decision's title or decision text says "withdraw", and
* the artifact is in status ``Withdrawn`` / ``Cancelled`` (case-insensitive;
  decisions, planning items, projects), and
* the decision already carries an ``is_about`` edge to that artifact.

Dry-run by default: prints one ``DEC-NNN withdraws <type> <id>`` line per
edge it would create. ``--apply`` posts them (an existing edge 409s and is
skipped). Reads the cloud API named by ``CRMBUILDER_V2_API_BASE_URL`` /
``CRMBUILDER_V2_API_TOKEN`` (``crmbuilder-v2/data/crmbuilder.env``), engagement
``ENG-001`` unless ``--engagement`` says otherwise. Not run automatically —
the orchestrator decides.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

_WITHDRAWN = {"withdrawn", "cancelled"}
_LISTS = {"decision": "/decisions", "planning_item": "/planning-items", "project": "/projects"}


def _api(base: str, token: str, engagement: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Engagement": engagement,
            "Content-Type": "application/json",
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _identifier(row: dict) -> str:
    for key in ("identifier", "decision_identifier", "planning_item_identifier",
                "project_identifier"):
        if row.get(key):
            return row[key]
    raise KeyError(f"no identifier in {sorted(row)}")


def _status(row: dict) -> str:
    for key in ("status", "decision_status", "planning_item_status", "project_status"):
        if row.get(key):
            return str(row[key])
    return ""


def candidates(get) -> list[tuple[str, str, str]]:
    """Return ``(decision_id, target_type, target_id)`` triples to create."""
    withdrawn: dict[tuple[str, str], str] = {}
    for kind, path in _LISTS.items():
        status, env = get(path)
        if status != 200:
            print(f"warning: GET {path} -> {status}; skipped", file=sys.stderr)
            continue
        for row in env["data"]:
            if _status(row).lower() in _WITHDRAWN:
                withdrawn[(kind, _identifier(row))] = _status(row)
    _, env = get("/decisions")
    withdrawing = {
        _identifier(d)
        for d in env["data"]
        if "withdraw" in f"{d.get('title', '')} {d.get('decision', '')}".lower()
    }
    _, env = get("/references")
    have = {
        (r["source_id"], r["target_type"], r["target_id"])
        for r in env["data"]
        if r["source_type"] == "decision" and r["relationship"] == "withdraws"
    }
    out = []
    for r in env["data"]:
        if r["source_type"] != "decision" or r["relationship"] != "is_about":
            continue
        key = (r["target_type"], r["target_id"])
        if r["source_id"] in withdrawing and key in withdrawn:
            triple = (r["source_id"], *key)
            if triple not in have and triple not in out:
                out.append(triple)
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apply", action="store_true", help="post the edges (default: dry run)")
    p.add_argument("--engagement", default="ENG-001")
    args = p.parse_args(argv)
    base = os.environ.get("CRMBUILDER_V2_API_BASE_URL", "").rstrip("/")
    token = os.environ.get("CRMBUILDER_V2_API_TOKEN", "")
    if not base or not token:
        print("set CRMBUILDER_V2_API_BASE_URL and CRMBUILDER_V2_API_TOKEN", file=sys.stderr)
        return 2

    def get(path):
        return _api(base, token, args.engagement, path)

    triples = candidates(get)
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[{mode}] {len(triples)} withdraws edge(s) to create")
    for dec, ttype, tid in triples:
        print(f"  {dec} withdraws {ttype} {tid}")
        if args.apply:
            status, env = _api(
                base, token, args.engagement, "/references",
                {"source_type": "decision", "source_id": dec, "target_type": ttype,
                 "target_id": tid, "relationship": "withdraws"},
            )
            print(f"    -> {status}" + ("" if status in (201, 409) else f" {env}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
