#!/usr/bin/env python3
"""PI-024 Phase 2 backfill — prior workstreams.

One-off script that creates the six prior-workstream records (WS-002 through
WS-007), three master-plan reference_book records (RB-011 through RB-013),
and three ``workstream_planned_in_reference_book`` edges. Idempotent on
re-run: each POST treats HTTP 409 (and 422 duplicate) as already-present.

Creates (in this fixed order to satisfy edge-required rules):

* RB-011, RB-012, RB-013 — master-plan reference_book records for WS-003,
  WS-004, WS-005 respectively. Kind: ``workstream_master_plan``. Status:
  ``active``. One v1.0 version per RB matching the document's ``Last
  Updated`` timestamp.

* WS-002 through WS-007 — six workstream records, status ``complete`` with
  both ``workstream_started_at`` and ``workstream_completed_at`` backdated
  per the lifecycle-date reconstruction strategy approved in DEC-176
  (Option B — session-date range, with Option C fallback for workstreams
  lacking clean session bookends).

* WS-003 → RB-011, WS-004 → RB-012, WS-005 → RB-013 — three master-plan
  edges (``workstream_planned_in_reference_book``).

WS-002 (catalog ingestion), WS-006 (CBM paper test), and WS-007 (multi-
tenancy fix) are backfilled bare per DEC-177 (Option B — bundle only clean
cases). Their planning material spans multiple documents without a single
workstream-plan-style master document; master-plan reference_book records
deferred to a future reference-book backfill phase.

Run with the V2 API up at http://127.0.0.1:8765 (or override with --base).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:8765"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

_REFERENCE_BOOKS: list[dict[str, Any]] = [
    {
        "id": "RB-011",
        "title": "Methodology entity schema-design workstream plan",
        "description": (
            "Master plan for WS-003 — establishes the four-entity scope "
            "(domain, entity, process, crm_candidate), the sequence of four "
            "per-entity schema-design conversations plus a v0.4-build-"
            "planning conversation, and the schema-spec methodology guide "
            "template."
        ),
        "kind": "workstream_master_plan",
        "file_path": "PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md",
        "version_label": "1.0",
        "version_date": "2026-05-11T16:00:00",
    },
    {
        "id": "RB-012",
        "title": "User-interface v0.5 engagement-management workstream plan",
        "description": (
            "Master plan for WS-004 — establishes multi-engagement "
            "architecture, engagement schema, REST API extension for "
            "engagement routing, and the engagement-management UI."
        ),
        "kind": "workstream_master_plan",
        "file_path": "PRDs/product/crmbuilder-v2/v0.5-engagement-management-workstream-plan.md",
        "version_label": "1.0",
        "version_date": "2026-05-16T14:00:00",
    },
    {
        "id": "RB-013",
        "title": "User-interface v0.6 styling workstream plan",
        "description": (
            "Master plan for WS-005 — establishes the design pass (tokens, "
            "component visual decisions, application priorities) and the "
            "six-slice implementation arc."
        ),
        "kind": "workstream_master_plan",
        "file_path": "PRDs/product/crmbuilder-v2/styling-workstream-plan.md",
        "version_label": "1.0",
        "version_date": "2026-05-16T14:00:00",
    },
]


_WORKSTREAMS: list[dict[str, Any]] = [
    {
        "id": "WS-002",
        "name": "Catalog ingestion",
        "purpose": (
            "Bring the base entity catalog into the V2 database as "
            "authoritative reference data, retiring the YAML research "
            "deliverable and exposing the catalog via REST and MCP."
        ),
        "description": (
            "A PRD-driven workstream that ingests the base entity catalog "
            "(42 entries across 5 tiers, 414 attributes, 228 source "
            "citations) from YAML into the V2 database, retiring "
            "PRDs/product/crmbuilder-v2/research/base-entity-catalog/ as "
            "source-of-truth. Produces nine SQLAlchemy tables, a one-time "
            "Alembic data migration, a catalog access layer, REST endpoints, "
            "and four read-only MCP tools (catalog_search, catalog_get_"
            "entity, catalog_get_cross_system_map, catalog_gap_check). "
            "End-state: V2's UI, API, and MCP server serve catalog content "
            "without external file dependencies. Planning ran 05-09-26 "
            "(PRD authored); execution was a single Claude Code-driven build "
            "session on 05-14-26 (SES-016)."
        ),
        "notes": (
            "Planning material spans catalog-ingestion-PRD-v0.1.md and "
            "catalog-ingestion-implementation-plan.md; no single workstream-"
            "plan-style master document exists. Master-plan reference_book "
            "record deferred per DEC-177. workstream_started_at uses "
            "DEC-176 Option C fallback (PRD Last Updated 05-09-26); "
            "workstream_completed_at is SES-016's session_date."
        ),
        "started_at": "2026-05-09T00:00:00",
        "completed_at": "2026-05-14T00:00:00",
    },
    {
        "id": "WS-003",
        "name": "Methodology entity schema design",
        "purpose": (
            "Design four methodology entity schemas (domain, entity, "
            "process, crm_candidate) under minimum-viable scope, enabling "
            "V2 to host methodology content for the CBM redo test."
        ),
        "description": (
            "The user-interface version 0.4 release arc. Mid-planning, "
            "redirected v0.4 from a UI-polish release to a methodology-"
            "entity-schema-design workstream after the planning conversation "
            "surfaced that preparing V2 to serve as the system of record "
            "for CBM redo (governance plus methodology content) was the "
            "higher-leverage next step. Produced four per-entity schema "
            "specifications in four sequential design conversations, a "
            "v0.4-build-planning conversation that integrated them, and "
            "six implementation slices (A–F) that shipped the release. "
            "First and largest of the prior workstreams; established the "
            "schema-spec methodology guide template and the parent-prefix "
            "field-naming and source-first relationship-kind naming "
            "conventions (DEC-046, DEC-048) that all later schema "
            "workstreams inherit. Spans SES-011 through SES-024."
        ),
        "notes": None,
        "started_at": "2026-05-11T00:00:00",
        "completed_at": "2026-05-15T00:00:00",
    },
    {
        "id": "WS-004",
        "name": "User-interface v0.5 engagement management",
        "purpose": (
            "Establish multi-engagement architecture in V2 — per-engagement "
            "SQLite isolation, engagement-management UI, and single-gesture "
            "engagement creation-plus-activation."
        ),
        "description": (
            "The user-interface version 0.5 release arc. Opened immediately "
            "after v0.4 shipped to close the architectural gap that v0.4's "
            "methodology entity schemas needed to live in client-specific "
            "databases (not the CRMBuilder dogfood) for the CBM paper test "
            "to be meaningful. Produced multi-engagement architecture "
            "(per-engagement SQLite files, meta database tracking "
            "engagements), engagement schema and access layer, REST API "
            "extension for engagement routing, engagement-management panel "
            "UI, and a top-strip picker for engagement switching. Three "
            "planning/architecture conversations followed by five "
            "implementation slices (A–E) plus follow-ups. Spans SES-025 "
            "through SES-035."
        ),
        "notes": None,
        "started_at": "2026-05-16T00:00:00",
        "completed_at": "2026-05-17T00:00:00",
    },
    {
        "id": "WS-005",
        "name": "User-interface v0.6 styling",
        "purpose": (
            "Apply a coherent design pass across V2's desktop UI — tokens, "
            "component styling, dialogs, status treatments — bringing v0.4 "
            "and v0.5's work to production-ready visual quality."
        ),
        "description": (
            "The user-interface version 0.6 release arc. A design-pass "
            "conversation (05-16-26) captured tokens, component visual "
            "decisions, application priorities, and acceptance criteria; "
            "six implementation slices (A–F) covered foundation "
            "infrastructure + About dialog, sidebar + master-pane delegate, "
            "panel retrofits + ReferencesSection rewrite, dialogs and form "
            "controls, status/error/warning + crash banner, and closeout "
            "with the v0.6.0 release and WCAG contrast build gate. Spans "
            "SES-027 through SES-043."
        ),
        "notes": None,
        "started_at": "2026-05-16T00:00:00",
        "completed_at": "2026-05-18T00:00:00",
    },
    {
        "id": "WS-006",
        "name": "Cleveland Business Mentors paper test",
        "purpose": (
            "Validate the four v0.4 methodology entity schemas (domain, "
            "entity, process, crm_candidate) against existing Cleveland "
            "Business Mentoring domain content, producing findings and a "
            "single decision about whether CBM redo Phase 1 ships on v0.4 "
            "as-is or requires schema amendments first."
        ),
        "description": (
            "A methodology-validation workstream that ran the v0.4 "
            "methodology entity schemas against real-world CBM domain "
            "content. Originally deferred when v0.4 shipped (co-mingling "
            "dogfood and client content in one V2 database was the "
            "friction); re-flagged ready on 05-18-26 after v0.5 engagement "
            "isolation closed the gap. Produced methodology-schemas-cbm-"
            "paper-test-findings.md with one blocking finding — a "
            "sub-domain hierarchy amendment to the domain schema — "
            "recorded as planning item 001 in the Cleveland Business "
            "Mentors engagement."
        ),
        "notes": (
            "Cross-engagement: the paper-test conversation sessions live in "
            "the CBM engagement database, not CRMBUILDER's. PI-025 will "
            "face a cross-engagement decision when wiring conversation-"
            "membership edges back to this workstream record. Lifecycle-"
            "date reconstruction uses DEC-176 Option C fallback throughout "
            "(kickoff Last Updated 05-18-26 → findings Last Updated "
            "05-19-26). Planning material spans kickoff + findings "
            "documents; no workstream-plan-style master document, so "
            "master-plan reference_book record deferred per DEC-177."
        ),
        "started_at": "2026-05-18T00:00:00",
        "completed_at": "2026-05-19T00:00:00",
    },
    {
        "id": "WS-007",
        "name": "Multi-tenancy routing fix",
        "purpose": (
            "Diagnose and remediate engagement-routing bugs that the CBM "
            "paper test exposed in v0.5's initial implementation."
        ),
        "description": (
            "A two-session investigation-and-remediation workstream that "
            "opened after the CBM paper test surfaced engagement-routing "
            "bugs v0.5 hadn't fully covered. SES-044 produced the planning "
            "conversation (seven architectural decisions, two-slice build "
            "plan, slice prompts authored); SES-045 executed the fixes "
            "(in-process re-route on engagement switch, connection and "
            "version introspection)."
        ),
        "notes": (
            "Planning material spans multi-tenancy-routing-fix-planning-"
            "kickoff.md, multi-tenancy-routing-fix-slice-plan.md, and "
            "multi-tenancy-routing-investigation-report.md; no single "
            "workstream-plan-style master document. Master-plan "
            "reference_book record deferred per DEC-177."
        ),
        "started_at": "2026-05-19T00:00:00",
        "completed_at": "2026-05-20T00:00:00",
    },
]


_MASTER_PLAN_EDGES: list[tuple[str, str]] = [
    ("WS-003", "RB-011"),
    ("WS-004", "RB-012"),
    ("WS-005", "RB-013"),
]


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


def create_reference_books() -> bool:
    ok = True
    for rb in _REFERENCE_BOOKS:
        body = {
            "reference_book_identifier": rb["id"],
            "reference_book_title": rb["title"],
            "reference_book_description": rb["description"],
            "reference_book_kind": rb["kind"],
            "reference_book_file_path": rb["file_path"],
            "reference_book_status": "active",
            "versions": [
                {
                    "version_label": rb["version_label"],
                    "version_date": rb["version_date"],
                    "version_summary": f"{rb['title']} v{rb['version_label']}",
                }
            ],
        }
        status, payload = _request("POST", "/reference-books", body)
        ok &= _log_result(f"reference_book {rb['id']}", status, payload)
    return ok


def create_workstreams() -> bool:
    ok = True
    for ws in _WORKSTREAMS:
        body: dict[str, Any] = {
            "workstream_identifier": ws["id"],
            "workstream_name": ws["name"],
            "workstream_purpose": ws["purpose"],
            "workstream_description": ws["description"],
            "workstream_status": "complete",
            "timestamps": {
                "workstream_started_at": ws["started_at"],
                "workstream_completed_at": ws["completed_at"],
            },
        }
        if ws.get("notes"):
            body["workstream_notes"] = ws["notes"]
        status, payload = _request("POST", "/workstreams", body)
        ok &= _log_result(f"workstream {ws['id']} ({ws['name']})", status, payload)
    return ok


def create_master_plan_edges() -> bool:
    ok = True
    for ws_id, rb_id in _MASTER_PLAN_EDGES:
        body = {
            "source_type": "workstream",
            "source_id": ws_id,
            "target_type": "reference_book",
            "target_id": rb_id,
            "relationship": "workstream_planned_in_reference_book",
        }
        status, payload = _request("POST", "/references", body)
        ok &= _log_result(f"{ws_id} planned_in {rb_id}", status, payload)
    return ok


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify() -> None:
    print("\n=== Verification ===")
    for path, expected in [
        ("/workstreams", 7),
        ("/reference-books", 13),
    ]:
        status, payload = _request("GET", path)
        data = payload.get("data") if isinstance(payload, dict) else None
        n = len(data) if isinstance(data, list) else 0
        marker = "✓" if n >= expected else "⚠"
        print(f"  {marker} GET {path}: {n} records (expected ≥{expected})")
    status, payload = _request(
        "GET", "/references?relationship_kind=workstream_planned_in_reference_book"
    )
    data = payload.get("data") if isinstance(payload, dict) else None
    n = len(data) if isinstance(data, list) else 0
    marker = "✓" if n >= 4 else "⚠"
    print(f"  {marker} edges workstream_planned_in_reference_book: {n} (expected ≥4)")
    # Spot-check workstream lifecycle timestamps on WS-002 (Option C started_at)
    # and WS-007 (Option B both ends).
    for ws_id in ("WS-002", "WS-007"):
        status, payload = _request("GET", f"/workstreams/{ws_id}")
        if status == 200:
            d = payload.get("data") or {}
            print(
                f"  ✓ {ws_id}: status={d.get('workstream_status')} "
                f"started={d.get('workstream_started_at')} "
                f"completed={d.get('workstream_completed_at')}"
            )
        else:
            print(f"  ⚠ {ws_id}: GET failed (HTTP {status})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=BASE,
        help=f"API base URL (default: {BASE})",
    )
    args = parser.parse_args()
    BASE = args.base

    print(f"PI-024 prior-workstreams backfill against {BASE}\n")

    stages: list[tuple[str, callable]] = [
        ("Reference books (RB-011 .. RB-013)", create_reference_books),
        ("Workstreams (WS-002 .. WS-007)", create_workstreams),
        ("Master-plan edges", create_master_plan_edges),
    ]

    all_ok = True
    for label, fn in stages:
        print(f"\n--- {label} ---")
        all_ok &= fn()

    verify()

    if not all_ok:
        print("\n✗ One or more stages failed. See errors above.", file=sys.stderr)
        return 1
    print("\n✓ PI-024 backfill complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
