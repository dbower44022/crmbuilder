"""Backfill ``planning_item_belongs_to_project`` edges (PI-112 follow-on).

PI-112 implemented the lower two links of the target-model §7 containment chain
(Workstream->Planning Item, Work Task->Workstream) but missed the top one, so
Planning Items never rolled up under their Project. Migration 0033 adds the
``planning_item_belongs_to_project`` relationship kind; this script creates the
actual edges.

A Planning Item's Project is inferred from the conversation(s)/session(s) that
addressed, resolved, or are about it:

    PI  <--(addresses|resolves|is_about)--  conversation  --(belongs_to_project,
        or via its session's session_belongs_to_project)-->  Project
    PI  <--(any edge from a session)-- session --(session_belongs_to_project)--> Project

A PI with exactly one candidate Project is linked. Ambiguous (multiple
candidates) and unlinkable (no candidate — typically PIs predating the
Project model) PIs are reported and skipped. Idempotent: existing edges 409
and are skipped.

Usage:  uv run python scripts/backfill_pi_project_edges.py [--dry-run]
        (reads/writes the API at $CRMBUILDER_V2_API_BASE or 127.0.0.1:8765)
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import urllib.error
import urllib.request

_BASE = os.environ.get("CRMBUILDER_V2_API_BASE", "http://127.0.0.1:8765")


def _get(path: str):
    with urllib.request.urlopen(f"{_BASE}{path}", timeout=10) as r:
        return json.load(r)["data"]


def _post(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{_BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _infer() -> tuple[dict, dict, list]:
    refs = _get("/references")
    conv_proj, conv_sess, sess_proj = {}, {}, {}
    pi_convs = collections.defaultdict(set)
    pi_sessions = collections.defaultdict(set)
    for r in refs:
        st, si, k = r["source_type"], r["source_id"], r["relationship"]
        tt, ti = r["target_type"], r["target_id"]
        if k == "conversation_belongs_to_project":
            conv_proj[si] = ti
        elif k == "conversation_belongs_to_session":
            conv_sess[si] = ti
        elif k == "session_belongs_to_project":
            sess_proj[si] = ti
        if tt == "planning_item" and st == "conversation" and k in (
            "addresses", "resolves", "is_about"
        ):
            pi_convs[ti].add(si)
        if tt == "planning_item" and st == "session":
            pi_sessions[ti].add(si)

    def proj_of_conv(cv: str):
        if cv in conv_proj:
            return conv_proj[cv]
        s = conv_sess.get(cv)
        return sess_proj.get(s) if s else None

    pis = [p["identifier"] for p in _get("/planning-items")]
    linkable, ambiguous, unlinkable = {}, {}, []
    for pi in pis:
        projs = {proj_of_conv(cv) for cv in pi_convs.get(pi, ())}
        projs |= {sess_proj[s] for s in pi_sessions.get(pi, ()) if s in sess_proj}
        projs.discard(None)
        if len(projs) == 1:
            linkable[pi] = next(iter(projs))
        elif len(projs) > 1:
            ambiguous[pi] = sorted(projs)
        else:
            unlinkable.append(pi)
    return linkable, ambiguous, unlinkable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    linkable, ambiguous, unlinkable = _infer()
    print(
        f"PIs: {len(linkable) + len(ambiguous) + len(unlinkable)} | "
        f"linkable {len(linkable)} | ambiguous {len(ambiguous)} | "
        f"unlinkable {len(unlinkable)}"
    )
    if ambiguous:
        print("  ambiguous (skipped):", dict(sorted(ambiguous.items())))
    if unlinkable:
        print("  unlinkable (skipped, no Project path):", sorted(unlinkable))

    created = skipped = failed = 0
    for pi, proj in sorted(linkable.items()):
        edge = {
            "source_type": "planning_item", "source_id": pi,
            "target_type": "project", "target_id": proj,
            "relationship": "planning_item_belongs_to_project",
        }
        if args.dry_run:
            print(f"  [dry-run] {pi} -> {proj}")
            continue
        status, _ = _post("/references", edge)
        if status in (200, 201):
            created += 1
            print(f"  ✓ {pi} -> {proj}")
        elif status == 409:
            skipped += 1
        else:
            failed += 1
            print(f"  ✗ {pi} -> {proj} (HTTP {status})", file=sys.stderr)
    print(f"created {created} | already-present {skipped} | failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
