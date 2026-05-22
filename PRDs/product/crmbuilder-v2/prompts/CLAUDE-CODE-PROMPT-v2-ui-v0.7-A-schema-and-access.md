# Claude Code Prompt — v0.7 Slice A: Schema, Migrations, vocab.py, Access Layer

**Last Updated:** 05-22-26 17:30
**Release:** v0.7 (governance entity release)
**Slice:** A — foundation; schema migrations + vocab.py update + ORM models + repository modules
**Predecessor:** Slice F of v0.6 (styling workstream); v0.7 build-planning conversation (SES-055)
**Successor slice:** Slice B (REST API endpoints)
**PRD:** `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`
**Implementation plan section:** §2.1

---

## Task

Implement the storage-layer and access-layer foundation for the six new governance entity types: `workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event`. This is the first of six slices in the v0.7 release.

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md` — release PRD, sections 1–4 substantive; section 3.1 (storage layer), section 3.2 (access layer), section 4.1 (references-row addressing), section 4.2 (migration sequencing), section 4.3 (vocab.py aggregated update).
3. `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` section 2.1 (this slice's deliverables and acceptance criteria) and section 3 (cross-cutting concerns).
4. All six schema specifications under `PRDs/product/crmbuilder-v2/governance-schema-specs/` — sections 3.1 (Identity), 3.2 (Fields), 3.3 (Relationships), 3.4 (Lifecycle), 3.5 (API Surface for endpoint signatures), 3.7 (Acceptance Criteria). Special attention to `close_out_payload.md` v1.1 (first-success-transitions semantics in §3.4.3) and `deposit_event.md` (born-terminal append-only deviation; no `_updated_at`, no `_deleted_at` columns).
5. `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — current controlled vocabulary; the consolidation target.
6. `crmbuilder-v2/migrations/versions/0007_v0_4_create_domains_table.py` — migration precedent for CHECK constraint extensions and table creation pattern.
7. `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py` and `domains.py` — repository module precedents.

## Deliverables

Per the implementation plan §2.1 in full. Summary:

1. **Migration** `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py`:
   - Extend `refs.source_type`, `refs.target_type`, `refs.relationship_kind` CHECK constraints.
   - Extend `change_log.entity_type` CHECK constraint.
   - Add `reference_identifier` column to `refs` with `^REF-\d{4}$` GLOB CHECK; back-fill existing rows by `id` order.
   - Create the seven new tables (workstreams, conversations, reference_books, reference_book_versions, work_tickets, close_out_payloads, deposit_events).
   - Forward and backward reversible.

2. **`vocab.py` update**:
   - 8 new entries in `REFERENCE_RELATIONSHIPS`.
   - 6 new entries in `ENTITY_TYPES`.
   - New source-target clauses in `_kinds_for_pair()`.

3. **ORM models** for the seven new tables and the `Reference` model extension.

4. **Repository modules** (workstreams.py, conversations.py, reference_books.py, work_tickets.py, close_out_payloads.py, deposit_events.py) with status-transition validation, edge-required-at-terminal rules, at-most-one rules, atomic deposit_event POST, lazy close_out_payload creation, first-success-transitions semantics.

5. **Unit tests** at `tests/crmbuilder_v2/access/repositories/` per slice §2.1 acceptance.

## Working style

- Follow existing precedents: file layout, import patterns, type hints, docstring style match the methodology-entity slices (v0.4 A through E).
- One commit per logical step; the migration may be its own commit.
- Run `uv run pytest tests/crmbuilder_v2/access/` after each commit; full suite (`uv run pytest tests/crmbuilder_v2/`) before merge.
- Do NOT touch routers or UI in this slice.

## Pre-flight

```
curl -sf http://127.0.0.1:8765/health
uv run pytest tests/crmbuilder_v2/ -v
git pull --rebase origin main
```

## Acceptance gate

Per implementation plan §2.1. Bullet list:

- Migration applies cleanly forward and backward.
- All seven tables exist with correct columns and constraints.
- vocab.py registrations correct; `_kinds_for_pair` returns expected kind sets for new pairs.
- Repository methods exist with expected signatures.
- Status-transition validation per spec §3.4 for each entity.
- Edge-required-at-terminal rules fire correctly (work_ticket consumed, close_out_payload applied with first-success-transitions, all five supersession rules).
- At-most-one rules (work_ticket single-use, close_out_payload single-producer).
- Atomic deposit_event POST: row + parent edge + wrote_record edges + close_out_payload transition (on success vs ready) in one transaction; lazy-creates close_out_payload if missing.
- `uv run pytest tests/crmbuilder_v2/` green.

## Out of scope

- REST routers — Slice B.
- UI panels — Slice C.
- Apply script modifications — Slice D.
- PI-022 backfill — Slice E.
- Documentation updates and version bump — Slice F.
