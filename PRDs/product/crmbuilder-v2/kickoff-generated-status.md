# Kickoff — Generate Status versions from stored records

**Status:** governed, building.
**Records (ENG-001):** decision DEC-954 · requirement REQ-527 (confirmed) · planning item PI-433 · project PRJ-114 · session SES-366 · conversation CNV-330.
**Decided:** 2026-08-30, Doug, after an executive review of what the Status object is used for and whether it is still necessary.

## The problem

Status is the engagement's versioned "state of the union" — the DB successor of `status.md`, twin of Charter, a free-form JSON payload refreshed by hand at session close-outs via `PUT /status`. Its session-orientation content (`reading_order_for_new_sessions`, `live_inventory`, `blockers`, `pending`) was superseded by the CLAUDE.md session-bootstrap protocol (TOP-013 + governance rules, preferences, reference pointers, lessons) and dropped at v17. What remains — direction, what shipped, what is next — is provided by nothing else in the store, but hand authoring has drifted twice: ~12 sessions before v17, and ~11 weeks before this session (v18, 06-13-26, still reports `version_label 0.7.0`). Nothing in code, rules or references reads Status; a stale singleton is worse than none.

## The decision (DEC-954)

Keep the Status singleton and its history. Generate each new version from stored records, with an optional human narrative. Retiring Status (loses the only narrative summary) and gating the manual refresh (re-applies a discipline that failed twice) were rejected.

## The design

**Payload shape.** The five legacy fields are kept for continuity, one field is added:

| Field | Source |
|---|---|
| `title` | `"<engagement name> status"` |
| `phase` | The in-flight projects' names, joined; "No project in flight" when none |
| `version_label` | `crmbuilder_v2.__version__` |
| `metadata` | `Last Updated` (MM-DD-YY), `Generated At` (ISO), `Previous Version` (int or null) |
| `active_work` | The narrative paragraph supplied by the user, or empty |
| `generated` | See below |

`generated` carries: `in_flight_projects` (identifier, name), `active_releases` (identifier, title, status — any non-terminal status), `resolved_since_previous` (planning items whose status is Resolved and whose last update is after the previous version's `created_at`; all Resolved items when there is no previous version), `open_planning_items` (`counts` by active status plus `items` for Ready / In Progress / In Review), `recent_sessions` (five most recent by creation: identifier, title, status), `previous_version_created_at`.

**Layers.**
1. `access/status_snapshot.py` — `build_status_payload(session, *, narrative)` assembles the dict from the existing repositories; pure read.
2. `access/repositories/status.py` — `generate(session, *, narrative)` = build + `replace`.
3. `api/routers/status.py` — `GET /status/preview?narrative=` (no write) and `POST /status/generate` body `{"narrative": str | null}` (writes a version, returns the record).
4. `mcp_server/tools.py` — `preview_generated_status(narrative)` (read) and `create_generated_status(narrative)` (write; the `create_` prefix places it in the write partition).
5. `ui/client.py` — `preview_status`, `generate_status`. `ui/dialogs/status_generate.py` — narrative field + read-only preview + Save. `ui/panels/status.py` — a **Generate Version** action beside **New Version**.
6. Tests: access (`tests/crmbuilder_v2/access/test_status_snapshot.py`), api (`test_charter_status.py`), ui (`test_status_generate.py`).
7. First generated version cut on ENG-001, superseding v18.

**Out of scope.** Changing the hand-edit path (`PUT /status`, New Version) — it stays for corrections. Reconciling `PRDs/process/v2-user-process-guide.md`'s close-out instruction — that is folded into the Master CRMBuilder PRD consolidation. Rendering Status as a client-facing document.

**Terminology.** No new glossary term is coined: "Generate Version" uses the existing word *version*; `generated` is a payload key, not a term.
