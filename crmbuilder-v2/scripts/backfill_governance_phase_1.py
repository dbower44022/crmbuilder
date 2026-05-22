#!/usr/bin/env python3
"""PI-022 Phase 1 backfill — the governance entity schema-design workstream.

One-off script that creates the ~50 governance records and ~70 reference
edges representing the workstream itself. Idempotent on re-run: each POST
treats HTTP 409 as already-present.

Creates (in this fixed order to satisfy edge-required rules):

* WS-001 workstream (status ``in_flight``; Slice F transitions to ``complete``).
* RB-001 … RB-010 reference_book records (+ extra version rows for RB-005
  and RB-007 which carry v1.0 and v1.1).
* WT-001 … WT-008 work_ticket records (status ``drafted``; later transitioned
  to ``consumed`` once the conversation edge is in place).
* CONV-001 … CONV-008 conversation records (status ``in_flight`` initially;
  later transitioned to ``complete`` with the session edge in place).
* session-record edges for each conversation.
* WT consumption edges, then WT → ``consumed`` transitions.
* CONV → ``complete`` transitions.
* COP-001 … COP-008 close_out_payload records (status ``ready``).
* DEP-001 … DEP-008 deposit_event records (POST atomically transitions the
  matching COP to ``applied`` per Slice A's first-success semantics).
* WS-001 master-plan edge inbound from RB-001.

Run with the v0.7 API up at http://127.0.0.1:8765 (or override with
``--base``). Stdout is teed to
``PRDs/product/crmbuilder-v2/deposit-event-logs/backfill-phase-1.log``.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = "http://127.0.0.1:8765"

# Conversation ↔ session ↔ work_ticket ↔ close_out_payload mapping. The
# governance workstream's seven schema-design conversations plus the
# build-planning conversation.
_CONVERSATIONS: list[dict[str, Any]] = [
    {
        "conv": "CONV-001", "ses": "SES-047", "wt": "WT-001", "cop": "COP-001",
        "title": "Governance entity schema-design workstream established",
        "purpose": "Stand up the governance entity schema-design workstream and its master plan",
        "kickoff": "governance-entity-schema-workstream-establishing-kickoff.md",
        "payload": "ses_047.json",
        "predecessor": None,
    },
    {
        "conv": "CONV-002", "ses": "SES-048", "wt": "WT-002", "cop": "COP-002",
        "title": "Workstream entity schema designed",
        "purpose": "Specify the workstream entity type and lock the cross-spec precedents",
        "kickoff": "schema-design-kickoff-workstream.md",
        "payload": "ses_048.json",
        "predecessor": "CONV-001",
    },
    {
        "conv": "CONV-003", "ses": "SES-049", "wt": "WT-003", "cop": "COP-003",
        "title": "Conversation entity schema designed",
        "purpose": "Specify the conversation entity type",
        "kickoff": "schema-design-kickoff-conversation.md",
        "payload": "ses_049.json",
        "predecessor": "CONV-002",
    },
    {
        "conv": "CONV-004", "ses": "SES-050", "wt": "WT-004", "cop": "COP-004",
        "title": "Reference book entity schema designed",
        "purpose": "Specify the reference_book entity type and the documentary-lifecycle precedent",
        "kickoff": "schema-design-kickoff-reference-book.md",
        "payload": "ses_050.json",
        "predecessor": "CONV-003",
    },
    {
        "conv": "CONV-005", "ses": "SES-051", "wt": "WT-005", "cop": "COP-005",
        "title": "Work ticket entity schema designed",
        "purpose": "Specify the work_ticket entity type and the consumed-requires-edge precedent",
        "kickoff": "schema-design-kickoff-work-ticket.md",
        "payload": "ses_051.json",
        "predecessor": "CONV-004",
    },
    {
        "conv": "CONV-006", "ses": "SES-052", "wt": "WT-006", "cop": "COP-006",
        "title": "Close-out payload entity schema designed",
        "purpose": "Specify the close_out_payload entity type and reconcile cross-spec consistency",
        "kickoff": "schema-design-kickoff-close-out-payload.md",
        "payload": "ses_052.json",
        "predecessor": "CONV-005",
    },
    {
        "conv": "CONV-007", "ses": "SES-054", "wt": "WT-007", "cop": "COP-007",
        "title": "Deposit event entity schema designed",
        "purpose": "Specify the deposit_event entity type with born-terminal append-only semantics",
        "kickoff": "schema-design-kickoff-deposit-event.md",
        "payload": "ses_054.json",
        "predecessor": "CONV-006",
    },
    {
        "conv": "CONV-008", "ses": "SES-055", "wt": "WT-008", "cop": "COP-008",
        "title": "Governance entity build-planning conversation closed",
        "purpose": "Integrate the six per-entity specs into a coherent v0.7 release plan",
        "kickoff": "governance-schema-build-planning-kickoff.md",
        "payload": "ses_055.json",
        "predecessor": "CONV-007",
    },
]

# Reference books with versions (label, ISO datetime).
_REFERENCE_BOOKS: list[dict[str, Any]] = [
    {
        "id": "RB-001", "title": "Governance entity schema-design workstream plan",
        "kind": "workstream_master_plan",
        "file_path": "PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md",
        "versions": [("1.0", "2026-05-20T00:00:00")],
    },
    {
        "id": "RB-002", "title": "Governance entity schema spec guide",
        "kind": "methodology_guide",
        "file_path": "PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md",
        "versions": [("1.0", "2026-05-20T00:00:00")],
    },
    {
        "id": "RB-003", "title": "Workstream schema specification",
        "kind": "schema_specification",
        "file_path": "PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md",
        "versions": [("1.0", "2026-05-20T23:30:00")],
    },
    {
        "id": "RB-004", "title": "Conversation schema specification",
        "kind": "schema_specification",
        "file_path": "PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md",
        "versions": [("1.0", "2026-05-21T06:00:00")],
    },
    {
        "id": "RB-005", "title": "Reference book schema specification",
        "kind": "schema_specification",
        "file_path": "PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md",
        "versions": [("1.0", "2026-05-21T14:50:00"), ("1.1", "2026-05-21T15:30:00")],
    },
    {
        "id": "RB-006", "title": "Work ticket schema specification",
        "kind": "schema_specification",
        "file_path": "PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md",
        "versions": [("1.0", "2026-05-21T18:00:00")],
    },
    {
        "id": "RB-007", "title": "Close-out payload schema specification",
        "kind": "schema_specification",
        "file_path": "PRDs/product/crmbuilder-v2/governance-schema-specs/close_out_payload.md",
        "versions": [("1.0", "2026-05-21T19:30:00"), ("1.1", "2026-05-22T17:30:00")],
    },
    {
        "id": "RB-008", "title": "Deposit event schema specification",
        "kind": "schema_specification",
        "file_path": "PRDs/product/crmbuilder-v2/governance-schema-specs/deposit_event.md",
        "versions": [("1.0", "2026-05-22T17:00:00")],
    },
    {
        "id": "RB-009", "title": "Governance entity Product Requirements Document v0.1",
        "kind": "product_requirements_document",
        "file_path": "PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md",
        "versions": [("0.1", "2026-05-22T17:30:00")],
    },
    {
        "id": "RB-010", "title": "Governance entity implementation plan",
        "kind": "implementation_plan",
        "file_path": "PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md",
        "versions": [("0.1", "2026-05-22T17:30:00")],
    },
]

# Conversation status / lifecycle dates per the PRD (~05-20-26 → 05-22-26).
_WORKSTREAM_STARTED = "2026-05-20T22:00:00"
_CONV_DATE_BY_ID = {
    "CONV-001": "2026-05-20T22:00:00",
    "CONV-002": "2026-05-20T23:30:00",
    "CONV-003": "2026-05-21T06:00:00",
    "CONV-004": "2026-05-21T15:30:00",
    "CONV-005": "2026-05-21T18:00:00",
    "CONV-006": "2026-05-21T19:30:00",
    "CONV-007": "2026-05-22T17:00:00",
    "CONV-008": "2026-05-22T17:30:00",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


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


def _log_result(label: str, status: int, payload: dict) -> bool:
    if status in (200, 201, 204):
        print(f"  ✓ {label} (HTTP {status})")
        return True
    if status == 409:
        print(f"  · {label} already present (HTTP 409) — skipping")
        return True
    # The case-insensitive name/title uniqueness check fires BEFORE the
    # identifier-collision check, so a re-run of an idempotent create
    # comes back as 422 ``duplicate`` rather than 409. Treat duplicate as
    # already-present so the script is genuinely re-runnable.
    if status == 422 and isinstance(payload, dict):
        errors = payload.get("errors") or []
        if any(e.get("code") == "duplicate" for e in errors):
            print(f"  · {label} already present (HTTP 422 duplicate) — skipping")
            return True
    errors = payload.get("errors") if isinstance(payload, dict) else payload
    print(f"  ✗ {label} FAILED (HTTP {status}): {errors}", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Stage builders
# ---------------------------------------------------------------------------


def create_workstream() -> bool:
    body = {
        "workstream_identifier": "WS-001",
        "workstream_name": "Governance entity schema-design workstream",
        "workstream_purpose": (
            "Close the gap between V2's governance database role and its actual "
            "coverage of the planning-and-execution machinery itself"
        ),
        "workstream_description": (
            "Seven schema-design conversations (SES-047 through SES-052 plus "
            "SES-054) plus a build-planning conversation (SES-055) produce the "
            "six per-entity schema specifications and the integrating PRD that "
            "deliver v0.7's six new governance entity types: workstream, "
            "conversation, reference_book, work_ticket, close_out_payload, and "
            "deposit_event."
        ),
        "workstream_status": "in_flight",
        "timestamps": {"workstream_started_at": _WORKSTREAM_STARTED},
    }
    status, payload = _request("POST", "/workstreams", body)
    return _log_result("workstream WS-001", status, payload)


def create_reference_books() -> bool:
    ok = True
    for rb in _REFERENCE_BOOKS:
        body = {
            "reference_book_identifier": rb["id"],
            "reference_book_title": rb["title"],
            "reference_book_description": rb["title"],
            "reference_book_kind": rb["kind"],
            "reference_book_file_path": rb["file_path"],
            "reference_book_status": "active",
            "versions": [
                {
                    "version_label": label,
                    "version_date": date,
                    "version_summary": f"{rb['title']} v{label}",
                }
                for label, date in rb["versions"]
            ],
        }
        status, payload = _request("POST", "/reference-books", body)
        ok &= _log_result(f"reference_book {rb['id']}", status, payload)
        if status == 409:
            # Add any missing versions individually.
            for label, date in rb["versions"]:
                vbody = {
                    "version_label": label,
                    "version_date": date,
                    "version_summary": f"{rb['title']} v{label}",
                }
                vstatus, vpayload = _request(
                    "POST", f"/reference-books/{rb['id']}/versions", vbody
                )
                _log_result(f"  version {rb['id']}@{label}", vstatus, vpayload)
    return ok


def create_work_tickets() -> bool:
    ok = True
    for conv in _CONVERSATIONS:
        body = {
            "work_ticket_identifier": conv["wt"],
            "work_ticket_title": f"Kickoff: {conv['title']}",
            "work_ticket_description": (
                f"Kickoff prompt for {conv['conv']} ({conv['ses']}). "
                f"Source: PRDs/product/crmbuilder-v2/{conv['kickoff']}."
            ),
            "work_ticket_kind": "kickoff_prompt",
            "work_ticket_file_path": f"PRDs/product/crmbuilder-v2/{conv['kickoff']}",
            "work_ticket_status": "drafted",
        }
        status, payload = _request("POST", "/work-tickets", body)
        ok &= _log_result(f"work_ticket {conv['wt']}", status, payload)
    return ok


def create_conversations() -> bool:
    ok = True
    for conv in _CONVERSATIONS:
        # CONVERSATION belongs_to_workstream edge is required at create.
        refs = [
            {
                "source_type": "conversation", "source_id": conv["conv"],
                "target_type": "workstream", "target_id": "WS-001",
                "relationship": "conversation_belongs_to_workstream",
            }
        ]
        if conv["predecessor"]:
            refs.append(
                {
                    "source_type": "conversation", "source_id": conv["conv"],
                    "target_type": "conversation", "target_id": conv["predecessor"],
                    "relationship": "conversation_succeeds_conversation",
                }
            )
        date = _CONV_DATE_BY_ID[conv["conv"]]
        body = {
            "conversation_identifier": conv["conv"],
            "conversation_title": conv["title"],
            "conversation_purpose": conv["purpose"],
            "conversation_description": (
                f"Schema-design conversation for the governance entity workstream "
                f"({conv['ses']})."
            ),
            "conversation_status": "in_flight",
            "timestamps": {
                "conversation_kickoff_drafted_at": date,
                "conversation_ready_at": date,
                "conversation_started_at": date,
            },
            "references": refs,
        }
        status, payload = _request("POST", "/conversations", body)
        ok &= _log_result(f"conversation {conv['conv']}", status, payload)
    return ok


def create_session_edges() -> bool:
    ok = True
    for conv in _CONVERSATIONS:
        body = {
            "source_type": "conversation", "source_id": conv["conv"],
            "target_type": "session", "target_id": conv["ses"],
            "relationship": "conversation_records_session",
        }
        status, payload = _request("POST", "/references", body)
        ok &= _log_result(
            f"edge {conv['conv']} records_session {conv['ses']}", status, payload
        )
    return ok


def create_consumption_edges_and_consume_work_tickets() -> bool:
    ok = True
    for conv in _CONVERSATIONS:
        ref_body = {
            "source_type": "conversation", "source_id": conv["conv"],
            "target_type": "work_ticket", "target_id": conv["wt"],
            "relationship": "conversation_opens_against_work_ticket",
        }
        status, payload = _request("POST", "/references", ref_body)
        ok &= _log_result(
            f"edge {conv['conv']} opens_against {conv['wt']}", status, payload
        )
        # Transition WT to consumed.
        # WT must be at "ready" before "consumed" is a valid successor of
        # "drafted". Walk drafted → ready → consumed.
        for new_status in ("ready", "consumed"):
            patch_body: dict[str, Any] = {"work_ticket_status": new_status}
            status, payload = _request(
                "PATCH", f"/work-tickets/{conv['wt']}", patch_body
            )
            if status == 409 or (
                status == 422
                and "invalid_status_transition" in str(payload)
            ):
                # Already at this status from a prior run.
                continue
            ok &= _log_result(
                f"{conv['wt']} -> {new_status}", status, payload
            )
    return ok


def complete_conversations() -> bool:
    ok = True
    for conv in _CONVERSATIONS:
        body = {"conversation_status": "complete"}
        status, payload = _request(
            "PATCH", f"/conversations/{conv['conv']}", body
        )
        if status == 422 and "invalid_status_transition" in str(payload):
            # Likely already complete.
            continue
        ok &= _log_result(
            f"{conv['conv']} -> complete", status, payload
        )
    return ok


def create_close_out_payloads() -> bool:
    ok = True
    for conv in _CONVERSATIONS:
        date = _CONV_DATE_BY_ID[conv["conv"]]
        refs = [
            {
                "source_type": "close_out_payload", "source_id": conv["cop"],
                "target_type": "conversation", "target_id": conv["conv"],
                "relationship": "close_out_payload_produced_by_conversation",
            }
        ]
        body = {
            "close_out_payload_identifier": conv["cop"],
            "close_out_payload_title": f"Close-out payload for {conv['conv']} ({conv['ses']})",
            "close_out_payload_description": (
                f"Apply payload produced at {conv['conv']}'s close ({conv['ses']})."
            ),
            "close_out_payload_file_path": (
                f"PRDs/product/crmbuilder-v2/close-out-payloads/{conv['payload']}"
            ),
            "close_out_payload_status": "ready",
            "timestamps": {"close_out_payload_ready_at": date},
            "references": refs,
        }
        status, payload = _request("POST", "/close-out-payloads", body)
        ok &= _log_result(f"close_out_payload {conv['cop']}", status, payload)
    return ok


def create_deposit_events(payloads_root: Path, logs_root: Path) -> bool:
    ok = True
    for idx, conv in enumerate(_CONVERSATIONS, start=1):
        dep_id = f"DEP-{idx:03d}"
        # Reconstruct records_summary from the payload's section counts;
        # build wrote_record edges for sessions/decisions/planning_items
        # (skip references — REF-NNNN lookup adds complexity for limited
        # value during backfill).
        payload_path = payloads_root / conv["payload"]
        wrote: list[dict[str, str]] = []
        summary = {"sessions": 0, "decisions": 0, "planning_items": 0, "references": 0}
        if payload_path.exists():
            try:
                ses_data = json.loads(payload_path.read_text())
            except json.JSONDecodeError:
                ses_data = {}
            session = ses_data.get("session")
            if isinstance(session, dict) and session.get("identifier"):
                wrote.append(
                    {
                        "target_type": "session", "target_id": session["identifier"],
                        "relationship": "deposit_event_wrote_record",
                    }
                )
                summary["sessions"] = 1
            for d in ses_data.get("decisions") or []:
                ident = d.get("identifier")
                if ident:
                    wrote.append(
                        {
                            "target_type": "decision", "target_id": ident,
                            "relationship": "deposit_event_wrote_record",
                        }
                    )
            summary["decisions"] = sum(
                1 for d in ses_data.get("decisions") or [] if d.get("identifier")
            )
            for pi in ses_data.get("planning_items") or []:
                ident = pi.get("identifier")
                if ident:
                    wrote.append(
                        {
                            "target_type": "planning_item", "target_id": ident,
                            "relationship": "deposit_event_wrote_record",
                        }
                    )
            summary["planning_items"] = sum(
                1 for pi in ses_data.get("planning_items") or [] if pi.get("identifier")
            )
        # Write the historical-log placeholder file.
        log_disk_path = logs_root / f"{dep_id.lower().replace('-', '_')}-historical.log"
        if not log_disk_path.exists():
            log_disk_path.parent.mkdir(parents=True, exist_ok=True)
            log_disk_path.write_text(
                f"# {dep_id} historical-apply placeholder\n"
                f"# This apply ran pre-v0.7 (before deposit_event logging existed).\n"
                f"# Backfilled by scripts/backfill_governance_phase_1.py on "
                f"{datetime.now(UTC).isoformat()}.\n"
            )
        log_repo_relative = (
            f"PRDs/product/crmbuilder-v2/deposit-event-logs/{log_disk_path.name}"
        )
        # Parent edge + wrote_record edges.
        references = [
            {
                "target_type": "close_out_payload", "target_id": conv["cop"],
                "relationship": "deposit_event_applies_close_out_payload",
            }
        ] + wrote
        body = {
            "deposit_event_identifier": dep_id,
            "deposit_event_title": f"Apply of {conv['cop']} (historical backfill)",
            "deposit_event_description": (
                f"Backfilled deposit_event for the historical apply of {conv['cop']} "
                f"({conv['ses']}) by PI-022 Phase 1."
            ),
            "deposit_event_outcome": "success",
            "deposit_event_records_summary": summary,
            "deposit_event_apply_context": {
                "apply_script_version": "0.7.0",
                "invocation": "scripts/backfill_governance_phase_1.py",
                "runner": "backfill_script",
            },
            "deposit_event_log_file_path": log_repo_relative,
            "target_file_path": (
                f"PRDs/product/crmbuilder-v2/close-out-payloads/{conv['payload']}"
            ),
            "references": references,
        }
        status, payload = _request("POST", "/deposit-events", body)
        ok &= _log_result(f"deposit_event {dep_id}", status, payload)
    return ok


def create_master_plan_edge() -> bool:
    body = {
        "source_type": "workstream", "source_id": "WS-001",
        "target_type": "reference_book", "target_id": "RB-001",
        "relationship": "workstream_planned_in_reference_book",
    }
    status, payload = _request("POST", "/references", body)
    return _log_result("WS-001 planned_in RB-001", status, payload)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify() -> None:
    print("\n=== Verification ===")
    for path, expected in [
        ("/workstreams", 1),
        ("/conversations", 8),
        ("/work-tickets", 8),
        ("/close-out-payloads", 8),
        ("/deposit-events", 8),
        ("/reference-books", 10),
    ]:
        status, payload = _request("GET", path)
        data = payload.get("data") if isinstance(payload, dict) else None
        n = len(data) if isinstance(data, list) else 0
        marker = "✓" if n >= expected else "⚠"
        print(f"  {marker} GET {path}: {n} records (expected ≥{expected})")
    for kind, expected in [
        ("conversation_belongs_to_workstream", 8),
        ("conversation_succeeds_conversation", 7),
        ("conversation_records_session", 8),
        ("conversation_opens_against_work_ticket", 8),
        ("close_out_payload_produced_by_conversation", 8),
        ("deposit_event_applies_close_out_payload", 8),
        ("workstream_planned_in_reference_book", 1),
    ]:
        status, payload = _request(
            "GET", f"/references?relationship_kind={kind}"
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        n = len(data) if isinstance(data, list) else 0
        marker = "✓" if n >= expected else "⚠"
        print(f"  {marker} edges {kind}: {n} (expected ≥{expected})")


class _TeeStream:
    def __init__(self, primary, secondary) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, data):
        n = self._primary.write(data)
        try:
            self._secondary.write(data)
        except (OSError, ValueError):
            pass
        return n

    def flush(self):
        for stream in (self._primary, self._secondary):
            try:
                stream.flush()
            except (OSError, ValueError):
                pass


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=BASE)
    parser.add_argument(
        "--payloads-root", type=Path,
        default=Path("PRDs/product/crmbuilder-v2/close-out-payloads"),
    )
    parser.add_argument(
        "--logs-root", type=Path,
        default=Path("PRDs/product/crmbuilder-v2/deposit-event-logs"),
    )
    args = parser.parse_args()
    BASE = args.base
    args.logs_root.mkdir(parents=True, exist_ok=True)

    log_path = args.logs_root / "backfill-phase-1.log"
    original_stdout = sys.stdout
    log_handle: io.TextIOWrapper | None = None
    try:
        log_handle = log_path.open("w", encoding="utf-8")
        sys.stdout = _TeeStream(original_stdout, log_handle)
        print("=== PI-022 Phase 1 backfill ===")
        print(f"Base: {BASE}")
        print(f"Started: {datetime.now(UTC).isoformat()}\n")

        steps = [
            ("Workstream WS-001", create_workstream),
            ("Reference books RB-001..010", create_reference_books),
            ("Work tickets WT-001..008", create_work_tickets),
            ("Conversations CONV-001..008", create_conversations),
            ("Session-record edges", create_session_edges),
            ("Consumption edges + WT consumed", create_consumption_edges_and_consume_work_tickets),
            ("Conversation completion", complete_conversations),
            ("Close-out payloads COP-001..008", create_close_out_payloads),
            (
                "Deposit events DEP-001..008",
                lambda: create_deposit_events(args.payloads_root, args.logs_root),
            ),
            ("Master plan edge WS-001 -> RB-001", create_master_plan_edge),
        ]
        all_ok = True
        for name, fn in steps:
            print(f"\n=== {name} ===")
            ok = fn()
            all_ok &= ok
        verify()
        print(f"\nFinished: {datetime.now(UTC).isoformat()}")
        return 0 if all_ok else 1
    finally:
        if log_handle is not None:
            sys.stdout = original_stdout
            try:
                log_handle.close()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
