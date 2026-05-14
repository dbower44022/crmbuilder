# CLAUDE-CODE-PROMPT-v2-ui-v0.4-B-domains-panel

**Last Updated:** 05-12-26 10:30
**Series:** v2-ui-v0.4
**Slice:** B (2 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`
**Companion schema spec:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md`
**Predecessor slice:** v2-ui-v0.4-A (foundation — vocab additions, refs CHECK migration, Methodology sidebar group container, eight retrofitted next-identifier helpers, spec guide section 6 amendment)

## Purpose

This is the second of six slices in v0.4. This prompt builds slice **B — Domains panel end-to-end**.

Slice B implements the `domain` entity type fully per `domain.md` — schema migration, access-layer methods, REST endpoints, desktop panel with master and detail views, CRUD dialogs, and tests covering all 14 acceptance criteria from `domain.md` section 3.7. After this slice, `domain` is the first methodology entity available in v2; consultants can author Phase 1 Domain Inventory records through the desktop app.

This slice is the template for slices C, D, E. The shape of the deliverables repeats with entity-specific adjustments. Slice B is also the first slice to populate an entry under the Methodology sidebar group that slice A introduced.

## Project context

Slice A landed the foundation: `vocab.py` admits the four new entity types and the two new relationship kinds; the refs table's CHECK constraints have been extended; the Methodology sidebar group container is in place; and the eight retrofitted next-identifier helpers ship on the existing governance entities. With foundation in place, this slice introduces the first methodology entity type, building the panel and supporting infrastructure entirely scoped to `domain`.

The spec is authoritative. This prompt cites the spec's section numbers rather than restating the content; read `domain.md` first, then return here for slice-execution guidance.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug Bower`
   - `git config user.email` should return `dbower44022@users.noreply.github.com`
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm slice A is at HEAD or recently committed (look for the slice-A commit message in `git log -5`).
6. Confirm the storage system is operational. Verify-first, only start if not already running:
   - First check: `curl -sf http://127.0.0.1:8765/health` — if it returns 200, the API is already running; proceed to step 7.
   - If the health check fails, start the API in the background: `uv run crmbuilder-v2-api &`. Wait ~3 seconds, then re-run. If the second check still fails, stop and report to Doug.
7. Confirm slice A's tests pass: `uv run pytest tests/crmbuilder_v2/ -v`. Cumulative count from prior slice; this is the regression net for slice B.

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry, especially the v2 section.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` section 4.3 (Domains panel) and section 6 (Slice B acceptance criteria).
3. `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md` section 4 Step B.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — the authoritative spec for this slice. All 14 acceptance criteria in section 3.7 are the slice's gate.
5. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` section 6 (post-amendment from slice A) for the cross-spec conventions.
6. Slice A's vocab additions in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — confirm the foundation is in place and `domain` appears in `ENTITY_TYPES`.
7. Existing v0.3 governance-entity panels as patterns to follow:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py` — typical entity panel structure
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_create.py`, `decision_edit.py`, `decision_delete.py` — dialog patterns
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py` (or wherever the decisions repository lives) — repository structure
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/decisions.py` — REST endpoint patterns
   - The latest decisions Alembic migration — table-creation migration pattern

## Step 1 — Alembic migration: create the `domains` table

Create a new Alembic revision named something like `0NNN_v0_4_create_domains_table.py` with `0NNN` the next available revision number.

The migration creates the `domains` table per `domain.md` section 3.2. Required columns:

| Column | Type | Constraints |
|--------|------|-------------|
| `domain_identifier` | TEXT | PRIMARY KEY, format `^DOM-\d{3}$` (CHECK constraint), unique |
| `domain_name` | TEXT | NOT NULL, non-empty trimmed (CHECK or access-layer); case-insensitive unique (covered by an index or by the access layer per v2's existing pattern for this) |
| `domain_status` | TEXT | NOT NULL, default `'candidate'`, CHECK in `('candidate', 'confirmed', 'deferred')` |
| `domain_purpose` | TEXT | NOT NULL |
| `domain_description` | TEXT | NOT NULL |
| `domain_notes` | TEXT | NULL allowed |
| `domain_created_at` | DATETIME | NOT NULL, default current_timestamp |
| `domain_updated_at` | DATETIME | NOT NULL, default current_timestamp |
| `domain_deleted_at` | DATETIME | NULL allowed |

Match v2's existing patterns for soft-delete columns (a nullable `*_deleted_at` field), CHECK constraints (use `_check_in` helper from `vocab.py` if appropriate; or inline the values), and identifier-format constraints. The case-insensitive name uniqueness is enforced at the access layer per v2's existing convention — no `UNIQUE` index on `domain_name` itself; rather, the access-layer `create_domain` and update paths query for existing rows by `LOWER(domain_name)` and reject duplicates.

Forward and backward reversible. Verify both directions apply cleanly against a database that has slice A's foundation migration applied.

## Step 2 — Access-layer repository: `access/domain.py`

Create `crmbuilder-v2/src/crmbuilder_v2/access/domain.py` (or under `access/repositories/domain.py` depending on the existing module layout — match the convention of the existing repositories).

The repository exposes eight methods per `domain.md` section 3.7 acceptance criterion 5:

- `list_domains(include_deleted: bool = False) -> list[Domain]`
- `get_domain(identifier: str) -> Domain | None`
- `create_domain(name: str, purpose: str, description: str, notes: str | None = None, status: str = "candidate", identifier: str | None = None) -> Domain`
- `update_domain(identifier: str, **kwargs) -> Domain` — full replace; identifier in body must match path; mismatch raises validation error
- `patch_domain(identifier: str, **kwargs) -> Domain` — partial update
- `delete_domain(identifier: str) -> Domain` — soft delete; sets `domain_deleted_at`; idempotent
- `restore_domain(identifier: str) -> Domain` — clears `domain_deleted_at`; raises if not soft-deleted
- `next_domain_identifier() -> str` — returns the next available `DOM-NNN` identifier

Validation rules per spec section 3.5:

- **Identifier format.** `^DOM-\d{3}$`. Raise validation error on mismatch.
- **Identifier auto-assignment.** When `identifier` is None in `create_domain`, query for the max existing `domain_identifier` (including soft-deleted rows), increment the numeric suffix, format as `DOM-NNN`. Concurrent identifier-assignment behavior: follow v0.3 governance-entity precedent (likely access-layer lock on the row-assignment query).
- **Name uniqueness.** Case-insensitive within the engagement. Query existing rows with `LOWER(domain_name) = LOWER(<new value>)` and reject if any non-soft-deleted match exists.
- **Status enum.** Reject any value outside `{candidate, confirmed, deferred}`.
- **Status-transition validation.** Per spec section 3.4.1: from `candidate`, valid successors are `confirmed`, `deferred`. From `confirmed`, valid successor is `deferred`. From `deferred`, valid successor is `confirmed`. No regression to `candidate` from either `confirmed` or `deferred`. Invalid transitions raise an error with envelope `{"error": "invalid_status_transition", "from": ..., "to": ...}`.
- **Soft-delete semantics.** `delete_domain` sets `domain_deleted_at` to current UTC; idempotent (re-DELETE on already-soft-deleted is a no-op returning the record). `restore_domain` clears `domain_deleted_at`; raises if the record is not soft-deleted.

JSON-export hook: after any DB-changing operation, regenerate `db-export/domains.json`. Follow v2's existing JSON-export hook pattern.

## Step 3 — REST API router: `api/routers/domains.py`

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/domains.py` with the eight standard endpoints per `domain.md` section 3.5.1:

- `GET /domains` (with `?include_deleted=true`)
- `GET /domains/{identifier}`
- `POST /domains`
- `PUT /domains/{identifier}`
- `PATCH /domains/{identifier}`
- `DELETE /domains/{identifier}`
- `POST /domains/{identifier}/restore`
- `GET /domains/next-identifier`

Mirror the existing decisions router for structural patterns. Each endpoint delegates to the access-layer repository.

The `next-identifier` endpoint returns `{"next": "<DOM-NNN>"}` per the established retrofit pattern from slice A.

Error responses use the v2 error envelope. Status-transition errors return HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`. Identifier format errors return HTTP 422 with the existing v2 envelope. Name uniqueness errors return HTTP 422 with the existing v2 envelope.

Register the router in the API application's main module (`api/app.py` or wherever existing routers are registered).

## Step 4 — Desktop UI panel: `ui/panels/domains.py`

Create the Domains panel at `crmbuilder-v2/src/crmbuilder_v2/ui/panels/domains.py`. The class extends `ListDetailPanel`.

### 4.1 Sidebar registration

Register the panel under the Methodology sidebar group container introduced by slice A, at position #1 (first entry). The registration happens in `ui/app.py` (or wherever existing panels register).

### 4.2 Master pane

Columns: Identifier / Name / Status / Updated. Stored fields are `domain_identifier`, `domain_name`, `domain_status`, `domain_updated_at` respectively.

Default sort: Identifier ascending.

Right-click context menu: New / Edit / Delete / Restore (Restore appears on soft-deleted rows when the `?include_deleted=true` toggle is active per v0.3's pattern).

Override `_create_master_widget` returning the default `QTableView` configuration. Override `_build_context_menu` populating with the four actions and wiring each to the panel's existing handler slots (which mirror the toolbar buttons).

### 4.3 Detail pane

Vertical layout per spec section 3.6.3:

1. `domain_identifier` — read-only label
2. `domain_name` — single-line text editor
3. `domain_purpose` — single-line text editor, placeholder "One sentence"
4. `domain_description` — multi-line text editor, placeholder "Brief paragraph"
5. `domain_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
6. `domain_status` — combo box with the three enum values; restrict available choices to valid successors of the current status per the transition map
7. `ReferencesSection` widget — renders inbound references (none in slice B; populates as slices C and D bring entity and process records that reference domains)

### 4.4 CRUD dialogs

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/domain_crud.py` (or split into `domain_create.py`, `domain_edit.py`, `domain_delete.py` matching the v0.3 governance-entity pattern).

- **Create dialog** extends `EntityCrudDialog`. Fields in section-3.2 order matching the detail pane; identifier not shown (server-assigned); status defaults to `candidate`.
- **Edit dialog** same shape as create; identifier read-only; status combo restricted to valid successors.
- **Delete dialog** extends `EntityCrudDeleteDialog`. User types `DOM-NNN` value to enable Delete button; confirmation soft-deletes.

### 4.5 File-watch wiring

Connect the panel's refresh handler to the `domains_changed` signal that slice A wired up in `ui/refresh.py`. The panel refreshes its master pane on external changes.

## Step 5 — Storage client extensions

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` to add eight methods mirroring the access-layer repository:

- `list_domains(include_deleted: bool = False) -> list[dict]`
- `get_domain(identifier: str) -> dict`
- `create_domain(...) -> dict`
- `update_domain(identifier, ...) -> dict`
- `patch_domain(identifier, ...) -> dict`
- `delete_domain(identifier) -> dict`
- `restore_domain(identifier) -> dict`
- `next_domain_identifier() -> str`

Each method wraps an HTTP call to the corresponding REST endpoint and returns the parsed JSON body. Mirror the v0.3 client method patterns.

## Step 6 — Tests

Create three test modules covering all 14 acceptance criteria from `domain.md` section 3.7. Follow the v0.3 governance-entity test patterns.

### 6.1 `tests/crmbuilder_v2/access/test_domain.py`

Cover criteria 1–5 and 8 (schema migration, identifier format constraint, name uniqueness, status enum and transition, access-layer methods with happy-path and error-case tests, soft-delete/restore round-trip).

Required tests include:

- Schema migration creates `domains` table with all nine columns and correct types.
- Insertion with malformed identifier (e.g., `DOM-1` instead of `DOM-001`) raises validation error.
- Inserting a second row with `domain_name` matching an existing row by lowercase raises uniqueness violation.
- Status enum rejects values outside the three-value set.
- Transition validation rejects `confirmed → candidate` and `deferred → candidate`; permits `candidate → confirmed`, `candidate → deferred`, `confirmed → deferred`, `deferred → confirmed`.
- All eight repository methods exist and pass happy-path tests.
- `next_domain_identifier()` against an empty DB returns `DOM-001`; against existing records returns max + 1.
- Concurrent-POST test: two simultaneous create calls do not assign the same identifier (verify via the access layer's lock or retry mechanism).
- Soft-delete sets `domain_deleted_at`; the record disappears from `list_domains()` default; appears in `list_domains(include_deleted=True)`. Restore clears `domain_deleted_at`; restoring a non-soft-deleted record raises.

### 6.2 `tests/crmbuilder_v2/api/test_domains_api.py`

Cover criterion 6 (REST endpoints) and 7 (identifier auto-assignment).

Tests include:

- All eight endpoints return correct HTTP status and JSON shape for happy-path inputs.
- POST with malformed identifier returns 422.
- POST with omitted identifier auto-assigns and returns the assigned value in the response body.
- PATCH with an invalid transition returns 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.
- DELETE on an existing record returns 200, soft-deletes; subsequent GET returns 404 by default and 200 with `?include_deleted=true`.
- POST `/restore` on a soft-deleted record clears `deleted_at`. Restore on a non-soft-deleted record returns 422.
- `GET /domains/next-identifier` returns `{"next": "<DOM-NNN>"}` for the next available identifier.

### 6.3 `tests/crmbuilder_v2/ui/test_domains_panel.py`

Cover criteria 9–14 (sidebar position, master pane columns and sort, detail pane fields in order, CRUD dialogs end-to-end, file-watch refresh, sample CBM-redo records).

Tests include (use `qtbot` and `qapp` fixtures per v0.3 pattern):

- Sidebar contains a "Domains" entry under the Methodology group at position #1.
- Master pane displays four columns in the correct order; sort by Identifier ascending.
- Right-click context menu shows New / Edit / Delete / Restore (Restore conditional on `?include_deleted=true` toggle).
- Detail pane renders the seven fields in section-3.2 order; identifier is read-only; notes collapsed under "Internal notes" header.
- Create dialog: open, fill in name/purpose/description, submit, confirm new row appears in master pane with auto-assigned identifier.
- Edit dialog: select a row, open edit, change status, submit, confirm change persists.
- Delete dialog: select a row, open delete, type the identifier, confirm Delete enables, click Delete, confirm row disappears from default master pane and appears under `?include_deleted=true`.
- File-watch refresh: write a row via direct REST call, confirm desktop master pane reflects the change within the file-watch interval.
- Sample CBM-redo records: programmatically author 4 domain records (e.g., Mentoring, Mentor Recruitment, Client Recruiting, Fundraising), transition statuses from `candidate` to `confirmed`, restart the app (or simulate restart by reloading from REST), confirm records persist.

## Acceptance verification

Before committing, run each of the following and confirm:

1. **Slice B tests pass.** `uv run pytest tests/crmbuilder_v2/access/test_domain.py tests/crmbuilder_v2/api/test_domains_api.py tests/crmbuilder_v2/ui/test_domains_panel.py -v` — all 14 acceptance criteria covered and green.
2. **Slice A tests still pass.** `uv run pytest tests/crmbuilder_v2/access/test_vocab_v0_4.py tests/crmbuilder_v2/api/test_next_identifier_retrofit.py -v` green.
3. **Full v0.3 test suite still passes.** `uv run pytest tests/crmbuilder_v2/ -v` returns no failures.
4. **Alembic migration applies forward and backward.** `uv run alembic upgrade head` then `uv run alembic downgrade -1` then `uv run alembic upgrade head` — all succeed.
5. **Manual smoke.** Open the desktop app; click Domains in the Methodology sidebar group; create a domain through the New dialog; confirm it appears in the master pane and persists across app restart.

If any step fails, stop and report before committing.

## Commit

```bash
git add crmbuilder-v2/migrations/0NNN_v0_4_create_domains_table.py \
        crmbuilder-v2/src/crmbuilder_v2/access/domain.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/domains.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/domains.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/domain_crud.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
        tests/crmbuilder_v2/access/test_domain.py \
        tests/crmbuilder_v2/api/test_domains_api.py \
        tests/crmbuilder_v2/ui/test_domains_panel.py
git commit -m "v2: v0.4 slice B — Domains panel end-to-end"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT add any `entity`, `process`, or `crm_candidate` work — those are slices C, D, E respectively.
- Do NOT register relationship-kind values involving `domain` from the source side (none exist in v0.4; inbound from entity and process are registered in slices C and D).
- Do NOT modify the spec guide — slice A handled the section 6 amendment.
- Do NOT bump `__version__` or update the README — those land in slice F.
- Do NOT write any session, decision, or planning-item records — see `ui-PRD-v0.4.md` section 11 for the canonical list (SES-017, SES-018, DEC-068 through DEC-074, PI-013/014/015). Doug authors those at v0.4 closeout through the desktop dialog.
- Do NOT add a master-pane Domains column or any cross-domain rendering — `domain` has no outgoing references in v0.4.
- Do NOT introduce any storage architecture changes beyond the additive ones called for above.

---

*End of prompt.*
