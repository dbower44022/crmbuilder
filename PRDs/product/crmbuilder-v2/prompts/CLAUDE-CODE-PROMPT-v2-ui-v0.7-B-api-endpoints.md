# Claude Code Prompt — v0.7 Slice B: REST API endpoints

**Last Updated:** 05-22-26 17:30
**Release:** v0.7 (governance entity release)
**Slice:** B — REST API routers and envelope handling for the six new entity types
**Predecessor slice:** Slice A (schema and access layer) — must have shipped
**Successor slice:** Slice C (desktop UI panels)
**PRD:** `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`
**Implementation plan section:** §2.2

---

## Task

Implement the REST API routers for the six new governance entity types. Endpoint sets per the per-entity specs' §3.5; deposit_event reduced to POST + GET only per its born-terminal append-only posture.

## Read this first

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md` §3.3 (REST API).
3. `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` §2.2 (this slice's deliverables).
4. The six schema specs' §3.5 sections for endpoint signatures, filters, and identifier auto-assignment behavior. Special attention: reference_book version sub-endpoints (§3.5.2); deposit_event reduced surface (§3.5.1).
5. `crmbuilder-v2/src/crmbuilder_v2/api/routers/domains.py` and `decisions.py` — router precedents.
6. `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py` (or wherever the `{data, meta, errors}` envelope is implemented) — canonical envelope handling.

## Deliverables

Per implementation plan §2.2:

1. **Router modules** at `crmbuilder-v2/src/crmbuilder_v2/api/routers/`:
   - `workstreams.py` — standard eight-endpoint set per spec §3.5.
   - `conversations.py` — standard eight-endpoint set.
   - `reference_books.py` — standard eight-endpoint set plus three version-management sub-endpoints (`GET /reference-books/{id}/versions`, `POST /reference-books/{id}/versions`, `GET /reference-books/{id}/version-at?as_of=...`).
   - `work_tickets.py` — standard eight-endpoint set with list-endpoint `?kind=` and `?status=` filters.
   - `close_out_payloads.py` — standard eight-endpoint set with `?status=` filter.
   - `deposit_events.py` — POST `/deposit-events`, GET `/deposit-events`, GET `/deposit-events/{identifier}`, GET `/deposit-events/next-identifier` only. PUT, PATCH, DELETE, restore NOT registered; framework default returns HTTP 405.

2. **Router registration** in the main API app; prefixes and tags per V2 convention.

3. **Integration tests** at `tests/crmbuilder_v2/api/routers/` per slice §2.2 acceptance, including: happy path, validation failure with envelope shape, list filters, identifier auto-assignment, deposit_event HTTP 405 responses, reference_book version sub-endpoints.

## Working style

- Each router wraps the matching repository module from Slice A.
- Filter parameters parsed from query string; default values per each spec.
- All responses return `{data, meta, errors}` envelope.
- One commit per router module; tests in the same commit as their router.
- `uv run pytest tests/crmbuilder_v2/api/` after each commit; full suite before merge.

## Pre-flight

```
curl -sf http://127.0.0.1:8765/health
uv run pytest tests/crmbuilder_v2/ -v
git pull --rebase origin main
```

## Acceptance gate

Per implementation plan §2.2:

- All endpoints return correct HTTP status and envelope shape.
- Deposit_event router responds HTTP 405 to PUT/PATCH/DELETE/restore.
- List endpoint filters work: `?include_deleted=true`, `?kind=`, `?status=`, `?outcome=`.
- Identifier auto-assignment helpers work without collision under concurrent POSTs.
- Reference_book version sub-endpoints work as specified.
- `uv run pytest tests/crmbuilder_v2/` green.

## Out of scope

- UI panels — Slice C.
- Apply script modifications — Slice D.
- Backfill — Slice E.
- Documentation and version bump — Slice F.
