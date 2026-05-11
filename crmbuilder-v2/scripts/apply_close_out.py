#!/usr/bin/env python3
"""Apply a close-out JSON payload to the v2 API.

Reads a single JSON payload file containing any combination of session,
decisions, planning_items, and references records, and POSTs each to the
local v2 REST API at http://127.0.0.1:8765. Idempotent on re-run: each
POST treats HTTP 409 conflict as already-present and continues.

The payload file format is sectioned JSON. All sections are optional;
present sections are processed in this fixed order (session → decisions
→ planning_items → references) so that references can target records
created earlier in the same payload:

    {
      "label": "<human-readable description of this payload>",
      "session": { ... session fields ... },
      "decisions": [ { ... }, { ... }, ... ],
      "planning_items": [ { ... }, { ... }, ... ],
      "references": [ { ... }, { ... }, ... ]
    }

Each section is a list of records (except session, which is a single
record) following the v2 REST API request body shape for that endpoint.
See the existing apply_*.py scripts or the v2 REST docs for the field
shapes per entity type.

This script supersedes the per-conversation apply_ses_NNN_records.py
pattern. Future close-out conversations should:
  1. Commit a payload file to PRDs/product/crmbuilder-v2/close-out-payloads/
     named ses_NNN.json (where NNN is the session identifier number).
  2. Run this script with the payload path.

The session record IS written by this script via direct API. This
departs from the prior session-record-at-close convention (in which
sessions were authored through the v0.3 desktop New Session dialog).
The convention shift is documented in the SES-012 session record's
in_flight_at_end and is tracked as PI-008 (inbox folder watcher in the
v0.3 desktop app) for the v0.4-build-planning conversation.

Usage:
    cd crmbuilder-v2
    uv run python scripts/apply_close_out.py <path-to-payload.json>

Example:
    uv run python scripts/apply_close_out.py \\
      ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_012.json

Exit code 0 on full success; non-zero only if a non-409 error is
encountered or the payload file cannot be read.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8765"

# Section name → API endpoint path. Order matters: session first so that
# references targeting it can be authored later in the same run.
_SECTION_ENDPOINTS: list[tuple[str, str, bool]] = [
    # (section_name, endpoint_path, is_singular)
    ("session", "/sessions", True),
    ("decisions", "/decisions", False),
    ("planning_items", "/planning-items", False),
    ("references", "/references", False),
]


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read().decode()
        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            payload = {"raw": body_bytes}
        return e.code, payload
    except urllib.error.URLError as e:
        return 0, {"error": "connection_failed", "detail": str(e)}


def _log(label: str, status: int, payload: dict) -> bool:
    """Print result; return True on success-or-409, False on real error."""
    if status in (200, 201, 204):
        print(f"  ✓ {label} (HTTP {status})")
        return True
    if status == 409:
        print(f"  · {label} already present (HTTP 409) — skipping")
        return True
    if status == 0:
        print(f"  ✗ {label} CONNECTION FAILED: {payload}", file=sys.stderr)
        return False
    errors = payload.get("errors") or payload.get("detail") or payload
    print(f"  ✗ {label} FAILED (HTTP {status}): {errors}", file=sys.stderr)
    return False


def _record_label(section: str, record: dict) -> str:
    """Produce a short label for log output."""
    ident = record.get("identifier")
    if ident:
        return f"POST {section}  {ident}"
    src = record.get("source_id")
    tgt = record.get("target_id")
    rel = record.get("relationship")
    if src and tgt and rel:
        return f"POST {section}  {src} {rel} {tgt}"
    return f"POST {section}  <unidentified record>"


def _check_api_reachable() -> bool:
    status, payload = _request("GET", "/health")
    if status == 200:
        return True
    if status == 0:
        print(
            f"\n✗ Cannot reach v2 API at {BASE}.\n"
            f"  Start it with: uv run crmbuilder-v2-api &\n"
            f"  Detail: {payload}\n",
            file=sys.stderr,
        )
        return False
    print(
        f"\n✗ v2 API at {BASE} returned HTTP {status} on /health.\n"
        f"  Detail: {payload}\n",
        file=sys.stderr,
    )
    return False


def main() -> int:
    global BASE

    parser = argparse.ArgumentParser(
        description="Apply a close-out JSON payload to the v2 API.",
    )
    parser.add_argument(
        "payload_path",
        type=Path,
        help="Path to the JSON payload file to apply.",
    )
    parser.add_argument(
        "--base",
        default=BASE,
        help=f"Override the v2 API base URL (default: {BASE}).",
    )
    args = parser.parse_args()

    BASE = args.base

    if not args.payload_path.exists():
        print(f"✗ Payload file not found: {args.payload_path}", file=sys.stderr)
        return 2

    try:
        with args.payload_path.open() as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Failed to parse payload JSON: {e}", file=sys.stderr)
        return 2

    label = payload.get("label", str(args.payload_path.name))
    print(f"=== Applying close-out payload ===")
    print(f"Source: {args.payload_path}")
    print(f"Label:  {label}\n")

    if not _check_api_reachable():
        return 2

    ok = True
    total_processed = 0

    for section, endpoint, is_singular in _SECTION_ENDPOINTS:
        if section not in payload or not payload[section]:
            continue
        records = [payload[section]] if is_singular else payload[section]
        print(f"=== {section} ({len(records)} record{'s' if len(records) != 1 else ''}) ===")
        for record in records:
            status, response = _request("POST", endpoint, record)
            ok &= _log(_record_label(section, record), status, response)
            total_processed += 1
        print()

    if ok:
        print(f"✓ All {total_processed} operations complete.")
        return 0
    print(
        f"✗ One or more of {total_processed} operations failed. "
        f"See stderr for details. Re-running is safe (409 = already present).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
