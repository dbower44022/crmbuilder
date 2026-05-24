#!/usr/bin/env python3
"""PI-026 Phase 4 backfill — historical applies as deposit_events.

One-off script that creates 24 close_out_payload records (COP-009..COP-032)
and 24 deposit_event records (DEP-020..DEP-043) for the historical close-out
applies that landed before the deposit_event entity wiring was complete (i.e.,
before the v0.7 release). Each historical close-out gets a placeholder
log file (dep_NNN-historical.log) and the supporting reference edges:

- 24 close_out_payload records, each born `ready` then transitioned to
  `applied` atomically by the matching deposit_event POST. Each carries the
  required `close_out_payload_produced_by_conversation` edge to its CONV
  parent record (CONVs from PI-025).
- 24 deposit_event records, each with outcome=success, records_summary
  computed from the actual wrote_record edges authored, apply_context
  with apply_script_version="backfill" / runner="backfill_script" /
  per-record invocation, and log_file_path pointing at the placeholder log.
  Each carries one outbound deposit_event_applies_close_out_payload edge
  (parent COP) plus zero-or-more deposit_event_wrote_record edges (the
  session, decisions, and planning_items the historical apply created).
  References-as-wrote_record-targets — originally settled in DEC-206 with
  forward-then-reverse-then-skip resolution per DEC-208 — was found at
  execution time to be unimplementable against the deployed schema: the
  API's request validator rejects target_type="reference" with HTTP 400
  because `reference` is not in vocab.ENTITY_TYPES, even though
  `vocab._kinds_for_pair` speculatively admits it for the
  deposit_event_wrote_record kind. Pragmatic disposition (Option I, per
  the post-discovery conversation): skip references entirely and mirror
  Phase 1's pattern; records_summary.references stays 0; the schema-vs-
  spec contradiction surfaces as future work. The forward/reverse resolver
  and skip log are retained as diagnostic-only output for the data-quality
  finding on ses_030 (DEC-105/106/107 plus PI-001 reference resolve to
  SES-036, not SES-030 — the apparent duplicate-session artifact).
- 24 placeholder log files at PRDs/product/crmbuilder-v2/deposit-event-logs/
  with three-line content per the Phase 1 convention.

Idempotent on re-run: each POST treats HTTP 409 (and 422 duplicate) as
already-present and skipped. Log file writes check existence first and
skip if present.

Discharges Phase 4 of PI-022 per the kickoff at
PRDs/product/crmbuilder-v2/pi-026-historical-applies-deposit-events-backfill-kickoff.md
and per DEC-206..210 settled in SES-066. SES-001 and SES-046 historical
close-outs are excluded per DEC-210 (no CONV parent records exist).

Run with the V2 API up at http://127.0.0.1:8765 (or override with --base).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

BASE = "http://127.0.0.1:8765"


def _normalize_ses_date(raw: str) -> str:
    """Normalize ``MM-DD-YY`` or ``YYYY-MM-DD`` to ISO ``YYYY-MM-DD``."""
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw  # already YYYY-MM-DD
    parts = raw.split("-")
    if len(parts) == 3 and len(parts[2]) == 2:
        mm, dd, yy = parts
        return f"20{yy}-{mm}-{dd}"
    return raw


# ---------------------------------------------------------------------------
# Inventory: per-close-out metadata for PI-026's 24 backfilled records.
#
# Each entry: payload (filename), cop (identifier), dep (identifier),
# conv (CONV parent identifier), ses (session the apply landed),
# session_date (raw from snapshot — heterogeneous formats normalized).
# ---------------------------------------------------------------------------

_CLOSE_OUTS: list[dict[str, str]] = [
    {"payload": "ses_012.json", "cop": "COP-009", "dep": "DEP-020", "conv": "CONV-010", "ses": "SES-012", "session_date": "05-11-26"},
    {"payload": "ses_013.json", "cop": "COP-010", "dep": "DEP-021", "conv": "CONV-011", "ses": "SES-013", "session_date": "05-12-26"},
    {"payload": "ses_014.json", "cop": "COP-011", "dep": "DEP-022", "conv": "CONV-012", "ses": "SES-014", "session_date": "05-12-26"},
    {"payload": "ses_015.json", "cop": "COP-012", "dep": "DEP-023", "conv": "CONV-013", "ses": "SES-015", "session_date": "05-12-26"},
    {"payload": "ses_025.json", "cop": "COP-013", "dep": "DEP-024", "conv": "CONV-023", "ses": "SES-025", "session_date": "05-16-26"},
    {"payload": "ses_026.json", "cop": "COP-014", "dep": "DEP-025", "conv": "CONV-024", "ses": "SES-026", "session_date": "05-16-26"},
    {"payload": "ses_027.json", "cop": "COP-015", "dep": "DEP-026", "conv": "CONV-025", "ses": "SES-027", "session_date": "05-16-26"},
    {"payload": "ses_029.json", "cop": "COP-016", "dep": "DEP-027", "conv": "CONV-026", "ses": "SES-029", "session_date": "05-16-26"},
    {"payload": "ses_030.json", "cop": "COP-017", "dep": "DEP-028", "conv": "CONV-027", "ses": "SES-030", "session_date": "05-17-26"},
    {"payload": "ses_031.json", "cop": "COP-018", "dep": "DEP-029", "conv": "CONV-028", "ses": "SES-031", "session_date": "05-17-26"},
    {"payload": "ses_032.json", "cop": "COP-019", "dep": "DEP-030", "conv": "CONV-029", "ses": "SES-032", "session_date": "05-17-26"},
    {"payload": "ses_033.json", "cop": "COP-020", "dep": "DEP-031", "conv": "CONV-030", "ses": "SES-033", "session_date": "05-17-26"},
    {"payload": "ses_034.json", "cop": "COP-021", "dep": "DEP-032", "conv": "CONV-031", "ses": "SES-034", "session_date": "05-17-26"},
    {"payload": "ses_035.json", "cop": "COP-022", "dep": "DEP-033", "conv": "CONV-032", "ses": "SES-035", "session_date": "05-17-26"},
    {"payload": "ses_036.json", "cop": "COP-023", "dep": "DEP-034", "conv": "CONV-033", "ses": "SES-036", "session_date": "05-16-26"},
    {"payload": "ses_037.json", "cop": "COP-024", "dep": "DEP-035", "conv": "CONV-034", "ses": "SES-037", "session_date": "05-18-26"},
    {"payload": "ses_038.json", "cop": "COP-025", "dep": "DEP-036", "conv": "CONV-035", "ses": "SES-038", "session_date": "05-18-26"},
    {"payload": "ses_039.json", "cop": "COP-026", "dep": "DEP-037", "conv": "CONV-036", "ses": "SES-039", "session_date": "05-18-26"},
    {"payload": "ses_040.json", "cop": "COP-027", "dep": "DEP-038", "conv": "CONV-037", "ses": "SES-040", "session_date": "05-18-26"},
    {"payload": "ses_041.json", "cop": "COP-028", "dep": "DEP-039", "conv": "CONV-038", "ses": "SES-041", "session_date": "05-18-26"},
    {"payload": "ses_042.json", "cop": "COP-029", "dep": "DEP-040", "conv": "CONV-039", "ses": "SES-042", "session_date": "05-18-26"},
    {"payload": "ses_043.json", "cop": "COP-030", "dep": "DEP-041", "conv": "CONV-040", "ses": "SES-043", "session_date": "05-18-26"},
    {"payload": "ses_044.json", "cop": "COP-031", "dep": "DEP-042", "conv": "CONV-041", "ses": "SES-044", "session_date": "05-19-26"},
    {"payload": "ses_053.json", "cop": "COP-032", "dep": "DEP-043", "conv": "CONV-043", "ses": "SES-053", "session_date": "05-22-26"},
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | None]:
    url = f"{BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read())
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = None
        return exc.status, payload
    except urllib.error.URLError as exc:
        print(f"✗ Network error on {method} {path}: {exc.reason}", file=sys.stderr)
        return 0, None


def _log_result(label: str, status: int, payload: dict[str, Any] | None) -> bool:
    if status in (200, 201):
        print(f"  ✓ {label}")
        return True
    if status == 409:
        print(f"  · {label} (already present — SKIP)")
        return True
    # Treat 422 with duplicate-shaped error info as already-present.
    if status == 422 and payload is not None:
        errors = payload.get("errors") or []
        for err in errors:
            msg = (err.get("message") or "").lower()
            kind = (err.get("kind") or "").lower()
            if "duplicate" in msg or "unique" in msg or "already" in msg or kind == "duplicate":
                print(f"  · {label} (422 duplicate — SKIP)")
                return True
    print(f"  ✗ {label}: HTTP {status}")
    if payload is not None:
        print(f"      {json.dumps(payload)[:500]}", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Reference resolver (DEC-208: forward → reverse → skip)
# ---------------------------------------------------------------------------


def _build_reference_lookup() -> tuple[dict[tuple, str], dict[tuple, str]]:
    """Fetch all references and build forward/reverse lookup tables.

    Returns (forward, reverse) where:
      forward[(source_type, source_id, target_type, target_id, kind)] = REF-NNNN
      reverse[(target_type, target_id, source_type, source_id, kind)] = REF-NNNN

    Reverse table keys are the inverse direction; resolution code uses this
    to handle the ses_001-style direction-inverted snapshot vs payload
    mismatch (DEC-208 case (b)).
    """
    status, payload = _request("GET", "/references?limit=4000")
    if status != 200 or payload is None:
        print(f"✗ Cannot fetch references for resolution lookup (HTTP {status})", file=sys.stderr)
        sys.exit(2)
    refs = payload.get("data") or []
    forward: dict[tuple, str] = {}
    reverse: dict[tuple, str] = {}
    for r in refs:
        fkey = (r["source_type"], r["source_id"], r["target_type"], r["target_id"], r["relationship"])
        rkey = (r["target_type"], r["target_id"], r["source_type"], r["source_id"], r["relationship"])
        forward[fkey] = r["reference_identifier"]
        reverse[rkey] = r["reference_identifier"]
    print(f"  Built reference lookup: {len(refs)} references indexed")
    return forward, reverse


def _resolve_reference(
    pref: dict[str, str],
    forward: dict[tuple, str],
    reverse: dict[tuple, str],
) -> tuple[str | None, str]:
    """Resolve a payload reference entry to its REF-NNNN identifier.

    Returns (ref_identifier_or_None, resolution_kind) where resolution_kind
    is one of "forward", "reverse", or "skip".
    """
    key = (pref["source_type"], pref["source_id"], pref["target_type"], pref["target_id"], pref["relationship"])
    if key in forward:
        return forward[key], "forward"
    if key in reverse:
        return reverse[key], "reverse"
    return None, "skip"


# ---------------------------------------------------------------------------
# Close-out-payload creation
# ---------------------------------------------------------------------------


def create_close_out_payloads() -> bool:
    ok = True
    for entry in _CLOSE_OUTS:
        ready_at = f"{_normalize_ses_date(entry['session_date'])}T12:00:00"
        refs = [
            {
                "source_type": "close_out_payload", "source_id": entry["cop"],
                "target_type": "conversation", "target_id": entry["conv"],
                "relationship": "close_out_payload_produced_by_conversation",
            }
        ]
        body = {
            "close_out_payload_identifier": entry["cop"],
            "close_out_payload_title": f"Close-out payload for {entry['conv']} ({entry['ses']})",
            "close_out_payload_description": (
                f"Apply payload produced at {entry['conv']}'s close ({entry['ses']}). "
                f"Backfilled by PI-026 (Phase 4 of PI-022) on {datetime.now(UTC).date().isoformat()}."
            ),
            "close_out_payload_file_path": (
                f"PRDs/product/crmbuilder-v2/close-out-payloads/{entry['payload']}"
            ),
            "close_out_payload_status": "ready",
            "timestamps": {"close_out_payload_ready_at": ready_at},
            "references": refs,
        }
        status, payload = _request("POST", "/close-out-payloads", body)
        ok &= _log_result(f"close_out_payload {entry['cop']} (for {entry['ses']})", status, payload)
    return ok


# ---------------------------------------------------------------------------
# Deposit-event creation
# ---------------------------------------------------------------------------


def create_deposit_events(
    payloads_root: Path,
    logs_root: Path,
    forward: dict[tuple, str],
    reverse: dict[tuple, str],
) -> bool:
    ok = True
    total_forward = 0
    total_reverse = 0
    total_skip = 0
    skip_log: list[tuple[str, dict[str, str]]] = []

    for entry in _CLOSE_OUTS:
        payload_path = payloads_root / entry["payload"]
        if not payload_path.exists():
            print(f"✗ Payload file not found: {payload_path}", file=sys.stderr)
            ok = False
            continue
        try:
            ses_data = json.loads(payload_path.read_text())
        except json.JSONDecodeError as exc:
            print(f"✗ Cannot parse {entry['payload']}: {exc}", file=sys.stderr)
            ok = False
            continue

        # Build wrote_record edges and matching records_summary counts.
        wrote: list[dict[str, str]] = []
        summary = {"sessions": 0, "decisions": 0, "planning_items": 0, "references": 0}

        # Session
        session = ses_data.get("session")
        if isinstance(session, dict) and session.get("identifier"):
            wrote.append({
                "target_type": "session", "target_id": session["identifier"],
                "relationship": "deposit_event_wrote_record",
            })
            summary["sessions"] = 1

        # Decisions
        for d in ses_data.get("decisions") or []:
            ident = d.get("identifier")
            if ident:
                wrote.append({
                    "target_type": "decision", "target_id": ident,
                    "relationship": "deposit_event_wrote_record",
                })
                summary["decisions"] += 1

        # Planning items
        for p in ses_data.get("planning_items") or []:
            ident = p.get("identifier")
            if ident:
                wrote.append({
                    "target_type": "planning_item", "target_id": ident,
                    "relationship": "deposit_event_wrote_record",
                })
                summary["planning_items"] += 1

        # References — resolution runs for diagnostic reporting only; the
        # wrote_record edges to references are NOT authored. DEC-206
        # originally chose to include references-as-wrote_record-targets
        # (with forward-then-reverse-then-skip resolution per DEC-208),
        # but execution surfaced that target_type="reference" is rejected
        # by the API request validator (`reference` not in
        # vocab.ENTITY_TYPES) despite the speculative admission in
        # `vocab._kinds_for_pair`. Pragmatic disposition: skip references
        # entirely, mirror Phase 1's pattern, records_summary.references
        # stays 0. The resolver below still runs so the data-quality
        # exception log (ses_030's DEC-105/106/107 + PI-001) is preserved
        # as diagnostic output for future cleanup work.
        for pref in ses_data.get("references") or []:
            ref_id, kind = _resolve_reference(pref, forward, reverse)
            if ref_id is None:
                total_skip += 1
                skip_log.append((entry["payload"], pref))
                continue
            if kind == "forward":
                total_forward += 1
            else:
                total_reverse += 1
            # Intentionally not appending to `wrote` and not incrementing
            # summary["references"] — see block comment above.

        # Write the placeholder log file.
        log_disk_path = logs_root / f"{entry['dep'].lower().replace('-', '_')}-historical.log"
        if not log_disk_path.exists():
            log_disk_path.parent.mkdir(parents=True, exist_ok=True)
            log_disk_path.write_text(
                f"# {entry['dep']} historical-apply placeholder\n"
                f"# This apply ran pre-v0.7 (before deposit_event logging existed).\n"
                f"# Backfilled by scripts/backfill_pi_026_historical_applies_deposit_events.py on "
                f"{datetime.now(UTC).isoformat()}.\n"
            )
        log_repo_relative = (
            f"PRDs/product/crmbuilder-v2/deposit-event-logs/{log_disk_path.name}"
        )

        # Parent edge + wrote_record edges.
        references = [
            {
                "target_type": "close_out_payload", "target_id": entry["cop"],
                "relationship": "deposit_event_applies_close_out_payload",
            }
        ] + wrote

        body = {
            "deposit_event_identifier": entry["dep"],
            "deposit_event_title": f"Apply of {entry['cop']} (historical backfill, {entry['ses']})",
            "deposit_event_description": (
                f"Backfilled deposit_event for the historical apply of {entry['cop']} "
                f"({entry['ses']}) by PI-026 (Phase 4 of PI-022). "
                f"Records summary: {summary['sessions']} session, {summary['decisions']} decisions, "
                f"{summary['planning_items']} planning items, {summary['references']} references."
            ),
            "deposit_event_outcome": "success",
            "deposit_event_records_summary": summary,
            "deposit_event_apply_context": {
                "apply_script_version": "backfill",
                "invocation": (
                    f"backfill_pi_026: ../PRDs/product/crmbuilder-v2/close-out-payloads/{entry['payload']}"
                ),
                "runner": "backfill_script",
            },
            "deposit_event_log_file_path": log_repo_relative,
            "deposit_event_error_info": None,
            "references": references,
        }
        status, payload = _request("POST", "/deposit-events", body)
        ok &= _log_result(f"deposit_event {entry['dep']} (for {entry['cop']})", status, payload)

    print()
    print(f"Reference resolution totals across all 24 close-outs:")
    print(f"  forward-resolved: {total_forward}")
    print(f"  reverse-resolved: {total_reverse}")
    print(f"  skipped (unresolvable in either direction): {total_skip}")
    if skip_log:
        print(f"\nSkipped references (data-quality exceptions, per DEC-208):")
        for payload_name, pref in skip_log:
            print(
                f"  {payload_name}: {pref['source_type']}:{pref['source_id']} -> "
                f"{pref['target_type']}:{pref['target_id']} ({pref['relationship']})"
            )
    expected_forward = 125  # 132 total forward-resolvable - 7 in ses_046 deferred per DEC-210 = 125
    expected_reverse = 0  # ses_001's 3 reverse-direction-only references are out of scope (DEC-210)
    expected_skip = 4  # ses_030's 4 unresolvable references remain in scope
    print()
    print(f"Expected per DEC-208 / DEC-210: forward={expected_forward}, reverse={expected_reverse}, skip={expected_skip}")
    if (total_forward, total_reverse, total_skip) != (expected_forward, expected_reverse, expected_skip):
        print(f"⚠ Reference resolution counts diverged from expected; investigate data drift.", file=sys.stderr)

    return ok


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_record_counts() -> bool:
    """Re-fetch heads and verify expected counts."""
    ok = True

    status, payload = _request("GET", "/close-out-payloads?limit=200")
    cops = (payload or {}).get("data") or []
    cop_ids = sorted(c["close_out_payload_identifier"] for c in cops)
    pi_026_cops = [c for c in cop_ids if "COP-009" <= c <= "COP-032"]
    print(f"  COP-009..COP-032 present: {len(pi_026_cops)}/24")
    if len(pi_026_cops) != 24:
        ok = False

    status, payload = _request("GET", "/deposit-events?limit=200")
    deps = (payload or {}).get("data") or []
    dep_ids = sorted(d["deposit_event_identifier"] for d in deps)
    pi_026_deps = [d for d in dep_ids if "DEP-020" <= d <= "DEP-043"]
    print(f"  DEP-020..DEP-043 present: {len(pi_026_deps)}/24")
    if len(pi_026_deps) != 24:
        ok = False

    # Verify the parent edges for each new DEP are present.
    status, payload = _request("GET", "/references?limit=4000")
    refs = (payload or {}).get("data") or []
    applies_edges = [r for r in refs if r["relationship"] == "deposit_event_applies_close_out_payload"]
    pi_026_applies = [
        r for r in applies_edges
        if "DEP-020" <= r["source_id"] <= "DEP-043"
    ]
    print(f"  deposit_event_applies_close_out_payload edges from PI-026 DEPs: {len(pi_026_applies)}/24")
    if len(pi_026_applies) != 24:
        ok = False

    produced_edges = [r for r in refs if r["relationship"] == "close_out_payload_produced_by_conversation"]
    pi_026_produced = [
        r for r in produced_edges
        if "COP-009" <= r["source_id"] <= "COP-032"
    ]
    print(f"  close_out_payload_produced_by_conversation edges from PI-026 COPs: {len(pi_026_produced)}/24")
    if len(pi_026_produced) != 24:
        ok = False

    wrote_edges = [r for r in refs if r["relationship"] == "deposit_event_wrote_record"]
    pi_026_wrote = [
        r for r in wrote_edges
        if "DEP-020" <= r["source_id"] <= "DEP-043"
    ]
    # Per Option I (see module docstring): wrote_record edges to references
    # are NOT authored; expected count drops from the original 221 (which
    # assumed DEC-206's reference-inclusion) to 96 = 24 session + 63 decision
    # + 9 planning_item.
    expected_wrote = 96
    print(f"  deposit_event_wrote_record edges from PI-026 DEPs: {len(pi_026_wrote)}/{expected_wrote}")
    if len(pi_026_wrote) != expected_wrote:
        ok = False

    # Verify each PI-026 COP transitioned to `applied`
    applied_count = sum(
        1 for c in cops
        if c["close_out_payload_identifier"] in {e["cop"] for e in _CLOSE_OUTS}
        and c["close_out_payload_status"] == "applied"
    )
    print(f"  PI-026 COPs in `applied` status: {applied_count}/24 (transitioned by DEP POST)")
    if applied_count != 24:
        ok = False

    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser(description="PI-026 Phase 4 backfill")
    parser.add_argument(
        "--base", default=BASE,
        help=f"V2 API base URL (default: {BASE})",
    )
    parser.add_argument(
        "--payloads-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "PRDs/product/crmbuilder-v2/close-out-payloads",
        help="Path to close-out-payloads directory in the repo root.",
    )
    parser.add_argument(
        "--logs-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "PRDs/product/crmbuilder-v2/deposit-event-logs",
        help="Path to deposit-event-logs directory in the repo root.",
    )
    args = parser.parse_args()

    BASE = args.base

    print("=" * 72)
    print(f"PI-026 Phase 4 backfill — historical applies as deposit_events")
    print(f"  Base URL: {BASE}")
    print(f"  Payloads root: {args.payloads_root}")
    print(f"  Logs root: {args.logs_root}")
    print("=" * 72)

    # API health
    status, _ = _request("GET", "/health")
    if status != 200:
        print(f"✗ API health check failed (HTTP {status}); start the API and retry.", file=sys.stderr)
        return 2

    # Build reference resolution lookup tables.
    print("\nBuilding reference lookup tables...")
    forward, reverse = _build_reference_lookup()

    # Pre-flight: verify the 24 CONV parents and DEP-019 / DEC-206..210 are present.
    print("\nPre-flight: verifying CONV parents and SES-066 apply landed...")
    for entry in _CLOSE_OUTS:
        status, _ = _request("GET", f"/conversations/{entry['conv']}")
        if status != 200:
            print(
                f"✗ Required CONV parent {entry['conv']} not found "
                f"(HTTP {status}); PI-025 must have applied first.",
                file=sys.stderr,
            )
            return 2
    status, _ = _request("GET", "/deposit-events/DEP-019")
    if status != 200:
        print(
            f"✗ DEP-019 (SES-066 apply's lazy-created DEP) not found "
            f"(HTTP {status}); apply SES-066 close-out first.",
            file=sys.stderr,
        )
        return 2
    print("  All 24 CONV parents present; SES-066 apply landed.")

    # Step 1: create close_out_payloads (born `ready`).
    print("\nStep 1: Creating close_out_payload records (COP-009..COP-032)...")
    if not create_close_out_payloads():
        print("✗ COP creation step had failures; halting.", file=sys.stderr)
        return 1

    # Step 2: create deposit_events (atomically transitions COPs to `applied`).
    print("\nStep 2: Creating deposit_event records (DEP-020..DEP-043) and placeholder log files...")
    if not create_deposit_events(args.payloads_root, args.logs_root, forward, reverse):
        print("✗ DEP creation step had failures; halting.", file=sys.stderr)
        return 1

    # Step 3: verify counts.
    print("\nStep 3: Verifying record counts...")
    if not verify_record_counts():
        print("⚠ Verification did not match expected counts; review output above.", file=sys.stderr)
        return 1

    print("\n" + "=" * 72)
    print("PI-026 Phase 4 backfill: complete.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
