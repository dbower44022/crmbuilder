# CRMBuilder v2 — UI v0.5 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-16-26 21:00
**Status:** Draft — pending approval
**Companion PRD:** `ui-PRD-v0.5.md`
**Predecessor plan:** `ui-v0.4-implementation-plan.md` (shipped per SES-024 slice F closeout, 05-15-26)
**Executing prompt series:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-{A..E}-*.md`

---

## Change Log

**Version 0.1 (05-16-26 21:00):** Initial draft. Five-slice breakdown for v0.5 build: foundation infrastructure plus dogfood migration combined in slice A, engagement schema + access layer + REST endpoints in slice B, engagement management panel UI in slice C, switching mechanism + top-strip + picker + single-gesture creation+activation flow in slice D, closeout in slice E. Migration ordering enforced through slice dependency chain (meta DB schema in A; engagement table in B; per-engagement DB schemas inherit v0.4's chain unchanged). Slice A's foundation-plus-migration combination is monitored for size at execution time; the A1/A2 split fallback is documented.

---

## 1. Overview

This plan implements the v0.5 desktop UI specified in `ui-PRD-v0.5.md`. v0.5 is decomposed into five independently testable slices, each delivered as its own Claude Code prompt. Each prompt produces a working state of the application that exercises a coherent subset of the PRD's acceptance criteria.

Slice boundaries follow the hybrid pattern established by v0.3 and v0.4 — foundation + feature slices + dedicated closeout — adapted for v0.5's engagement-management scope. Slice A delivers foundation infrastructure plus the dogfood migration (combined because foundation alone is a non-functional intermediate state — meta DB exists but no engagement records and the dogfood data is still at the old path). Slices B through D layer engagement-management capability: schema and API surface; management panel UI; switching mechanism plus the single-gesture creation+activation flow. Slice E is mechanical closeout (version bump, README, regression pass, end-to-end smoke including a CBM engagement creation).

After all five prompts execute cleanly, every acceptance criterion in PRD section 7 is satisfied. The application becomes incrementally usable: after Slice A the dogfood is migrated and CRMBUILDER is the active engagement, with foundation infrastructure in place but no user-facing engagement-management UI; after Slice B the engagement REST API is operable via direct calls or external scripts but no UI exposes it; after Slice C the engagement management panel renders and CRUD works for non-switching operations; after Slice D the switching flow works end-to-end and single-gesture engagement creation is operable; after Slice E the release is shippable.

```
Slice A (foundation + dogfood migration)
    │
    └──> Slice B (engagement schema + access layer + REST API)
            │
            └──> Slice C (engagement management panel UI)
                    │
                    └──> Slice D (switching mechanism + top-strip + picker + single-gesture creation+activation)
                            │
                            └──> Slice E (closeout)
```

The dependency chain is strictly linear in v0.5 because each subsequent slice consumes the previous slice's output: B's schema requires A's meta DB; C's UI requires B's API; D's switching requires C's panel and the ActiveEngagementContext from A; E's smoke requires D's switching plus B's CRUD plus A's migration. Unlike v0.4's slices C/D/E which had partial independence around different entity types, v0.5's slices are vertically dependent.

---

## 2. Implementation Choices

### 2.1 Language and runtime

Unchanged from v0.1–v0.4. Python 3.12+, matching `pyproject.toml`'s `requires-python` pin.

### 2.2 Desktop framework — PySide6

Unchanged.

### 2.3 HTTP client — httpx (sync mode)

Unchanged.

### 2.4 Subprocess management — QProcess

Unchanged. Slice D's kill-relaunch dance extends the existing subprocess-management pattern: SIGTERM with 5-second timeout, SIGKILL escalation, port-release polling, `/health` exponential-backoff polling on relaunch.

### 2.5 File watching — QFileSystemWatcher

Unchanged from v0.4. Slice A extends the refresh-service entity-type map to cover the new meta DB export file (`db-export/meta/engagements.json`). Slice C wires the engagement management panel to this file plus to `active_engagement_changed` signals.

### 2.6 Test framework — pytest + pytest-qt

Unchanged. `qtbot` and `qapp` fixtures continue.

### 2.7 Logging — Python's standard `logging` module

Unchanged. RotatingFileHandler at `~/.crmbuilder-v2/ui.log`. Slice A adds new log streams for the activation sequence (each of the 12 steps emits a log line at INFO level) and the dogfood migration (each of the 8 steps).

### 2.8 Threading model

Unchanged. Worker/object pattern; `run_in_thread` helper. The dogfood migration runs synchronously at launch (no worker thread; the launch waits for migration completion before showing the main window). Activation sequence runs on a background QThread driven by a new `ActivationWorker` per Slice D §4.

### 2.9 Error handling

Unchanged. Typed exceptions in the storage client; inline-on-field for validation errors with `field`; modal `ErrorDialog` for everything else. The new error envelopes specific to v0.5 (`invalid_status_transition` on engagement status — though all three transitions are valid, the validator returns this for non-enum values; `invalid_export_dir` for export-dir validation failures; `forbid_active_engagement_delete` for §5.6's enforcement) follow the existing v2 4xx convention with the standard `{data: null, meta: ..., errors: [...]}` envelope per the CLAUDE.md API envelope contract.

### 2.10 Existing dialog framework — `EntityCrudDialog`

v0.2's `EntityCrudDialog` and v0.3/v0.4's extensions remain the base. The engagement entity panel uses `EntityCrudDialog` for create and edit dialogs and `EntityCrudDeleteDialog` for delete dialogs, with one v0.5-specific extension to `EntityCrudDeleteDialog` for the forbid-active-engagement behavior (§5.6 of the PRD).

### 2.11 Existing reference-create dialog — `ReferenceCreateDialog`

v0.3's cascading-vocab `ReferenceCreateDialog` is not exercised by engagement in v0.5 because engagement has no relationships. The dialog reads `RELATIONSHIP_RULES` at dialog-open time and is unaffected; no vocabulary additions in slice A.

### 2.12 New for v0.5 — `ActiveEngagementContext`

Slice A introduces a singleton QObject in the desktop application mirroring v1's `ActiveClientContext` pattern:

```python
class ActiveEngagementContext(QObject):
    active_engagement_changed = Signal(object)  # emits the new Engagement record, or None on clear

    def __init__(self): ...
    def engagement_identifier(self) -> str | None: ...
    def engagement_code(self) -> str | None: ...
    def engagement(self) -> Engagement | None: ...
    def set_engagement(self, engagement: Engagement | None) -> None: ...
    def clear(self) -> None: ...
```

The context is owned by the application shell and accessed via dependency injection. Panels listening to `active_engagement_changed` re-fetch from the API on engagement change.

### 2.13 New for v0.5 — two-database API server

Slice A extends the API server to maintain two simultaneous SQLite connections. The meta DB connection is opened at API subprocess startup from the hard-coded path `crmbuilder-v2/data/engagements.db`; the active engagement DB connection is opened from `CRMBUILDER_V2_DB_PATH` per the existing v0.4 pattern. Connection pools are separated; FastAPI dependency injection routes `/engagements/*` handlers to the meta DB pool and all other handlers to the active engagement DB pool.

### 2.14 New for v0.5 — 12-step activation sequence

Slice D introduces an `ActivationWorker` QThread that executes the 12-step sequence per `multi-engagement-architecture.md` §4 with the question-6 amendment from PRD §3 (PATCH `engagement_last_opened_at` deferred until after new API subprocess is up). The worker emits progress signals at each step; the picker UI's "Switching engagement..." overlay binds to these signals. Failure at any step aborts cleanly and surfaces an error via the existing `ErrorDialog` pattern.

### 2.15 New for v0.5 — dogfood migration module

Slice A introduces `crmbuilder-v2/src/crmbuilder_v2/migration/dogfood_v0_5.py` as a self-contained module with a single `run_dogfood_migration() -> MigrationResult` entry point. Invoked by the engine launcher when the migration-needed state is detected (existing `v2.db` plus missing or empty meta DB). Idempotent: rerun after a successful first run exits cleanly. Runs synchronously at launch before the main window is shown.

---

## 3. Directory and File Layout

The UI lives under `crmbuilder-v2/src/crmbuilder_v2/ui/`. The storage layer lives under `crmbuilder-v2/src/crmbuilder_v2/access/` and `crmbuilder-v2/src/crmbuilder_v2/api/`. v0.5 introduces one new entity type (engagement), one new module group for migration (`migration/`), one new access-layer module, one new API router, one new UI panel, one new UI dialog set, one new top-strip widget, one new activation-worker module, plus extensions to the existing app shell, refresh service, and storage client.

```
crmbuilder-v2/
└── src/crmbuilder_v2/
    ├── access/
    │   ├── engagement.py                        # NEW (slice B) — engagement repository against meta DB
    │   ├── engagement_models.py                 # NEW (slice B) — Engagement dataclass + EngagementStatus enum
    │   ├── meta_db.py                           # NEW (slice A) — meta DB connection management; separate from per-engagement DB connection pool
    │   └── (existing modules)                   # UNCHANGED in their content; the connection-management abstraction in A makes existing per-engagement-DB access continue working unchanged
    ├── api/
    │   ├── envelope.py                          # UNCHANGED — existing {data, meta, errors} envelope
    │   ├── routers/
    │   │   ├── engagements.py                   # NEW (slice B) — eight standard endpoints against meta DB
    │   │   └── (existing routers)               # UNCHANGED — continue using active engagement DB connection
    │   └── (existing modules)                   # UNCHANGED
    ├── migration/                               # NEW (slice A) — module directory
    │   ├── __init__.py                          # NEW (slice A)
    │   └── dogfood_v0_5.py                      # NEW (slice A) — one-shot dogfood migration
    ├── ui/
    │   ├── active_engagement_context.py         # NEW (slice A) — singleton QObject + signal
    │   ├── activation_worker.py                 # NEW (slice D) — 12-step activation QThread
    │   ├── app.py                               # MODIFIED (slice A) — instantiates ActiveEngagementContext + two-database client; (slice D) — instantiates top-strip widget above sidebar
    │   ├── client.py                            # MODIFIED across slices — engagement methods + next_engagement_identifier helper
    │   ├── refresh.py                           # MODIFIED (slice A) — file-watch map extended for db-export/meta/engagements.json
    │   ├── widgets/
    │   │   ├── engagement_top_strip.py          # NEW (slice D) — top-strip widget above sidebar
    │   │   ├── engagement_picker.py             # NEW (slice D) — picker dropdown
    │   │   ├── activation_overlay.py            # NEW (slice D) — "Switching engagement..." overlay
    │   │   └── (existing widgets)               # UNCHANGED
    │   ├── panels/
    │   │   ├── engagement_panel.py              # NEW (slice C) — ListDetailPanel subclass for engagement
    │   │   ├── sidebar.py                       # MODIFIED (slice A) — Engagements group container above Governance
    │   │   └── (existing panels)                # UNCHANGED
    │   └── dialogs/
    │       ├── engagement_crud.py               # NEW (slice C) — Create/Edit dialogs as EntityCrudDialog subclasses
    │       ├── engagement_delete.py             # NEW (slice C) — Delete dialog with forbid-active behavior per PRD §5.6
    │       ├── new_engagement_dialog.py         # NEW (slice D) — Single-gesture creation+activation; subclasses engagement_crud.EngagementCreateDialog
    │       └── (existing dialogs)               # UNCHANGED

crmbuilder-v2/migrations/
├── (existing revisions)                          # UNCHANGED
└── meta/                                         # NEW (slice A) — separate Alembic chain for meta DB
    ├── alembic.ini                               # NEW (slice A) — meta DB Alembic config
    ├── env.py                                    # NEW (slice A) — meta DB Alembic env
    └── versions/
        └── 0001_create_engagements_table.py      # NEW (slice A) — meta DB initial migration

crmbuilder-v2/data/
├── engagements.db                                # gitignored — created by slice A migration
├── engagements/                                  # gitignored directory — created by slice A migration
│   └── CRMBUILDER.db                             # gitignored — moved from v2.db by slice A migration
├── current_engagement.json                       # gitignored — written by slice D activation
└── v2.db.pre-v0.5-backup                         # gitignored — left by slice A migration for user-initiated cleanup

PRDs/product/crmbuilder-v2/db-export/
├── meta/                                         # NEW (slice A) — created by meta DB export
│   └── engagements.json                          # NEW (slice A) — generated by access-layer hook
└── (existing exports)                            # unchanged in shape; sourced from CRMBUILDER engagement after migration

tests/crmbuilder_v2/
├── access/
│   ├── test_engagement.py                       # NEW (slice B)
│   ├── test_meta_db_connection.py               # NEW (slice A) — two-database connection isolation
│   └── (existing tests)                         # UNCHANGED; run against CRMBUILDER engagement after migration
├── api/
│   ├── test_engagements_api.py                  # NEW (slice B)
│   ├── test_two_database_routing.py             # NEW (slice A) — engagement endpoints serve meta DB; other endpoints serve active engagement DB
│   └── (existing tests)                         # UNCHANGED
├── migration/
│   └── test_v0_5_dogfood_migration.py           # NEW (slice A) — idempotency, row-count verification, backup-and-recovery, three install scenarios
├── ui/
│   ├── test_active_engagement_context.py        # NEW (slice A)
│   ├── test_engagement_panel.py                 # NEW (slice C)
│   ├── test_engagement_crud_dialogs.py          # NEW (slice C) — including forbid-active-delete edge cases
│   ├── test_engagement_top_strip.py             # NEW (slice D)
│   ├── test_engagement_picker.py                # NEW (slice D)
│   ├── test_activation_worker.py                # NEW (slice D) — 12-step sequence, failure modes
│   ├── test_new_engagement_flow.py              # NEW (slice D) — single-gesture creation+activation with three failure-mode tests
│   └── (existing tests)                         # UNCHANGED
└── integration/
    └── test_v0_5_end_to_end.py                  # NEW (slice E) — full migration → engagement creation → switching → return-to-dogfood smoke
```

---

## 4. Slice Breakdown

### Step A — Foundation and Dogfood Migration

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.5-A-foundation-and-dogfood-migration.md`

**Deliverables:**

- `access/meta_db.py`: meta DB connection management (separate connection pool from the per-engagement DB pool). Module exports `get_meta_db_connection()` and `MetaDBConfig` with hard-coded path `crmbuilder-v2/data/engagements.db`. Concurrent-safe per the v0.4 SQLite-WAL pattern.
- Alembic chain for the meta DB at `crmbuilder-v2/migrations/meta/` with `alembic.ini`, `env.py`, and the initial migration `0001_create_engagements_table.py` per `engagement.md` §3.2: ten columns with constraints (identifier format `^ENG-\d{3}$`, code regex `^[A-Z][A-Z0-9]{1,9}$` case-insensitive unique, name case-insensitive unique, status enum `active`|`paused`|`archived`, export_dir validated when set, audit timestamps). Forward and backward reversible. Note: actual schema creation lives here in slice A; the access-layer repository and validation logic come in slice B.
- `api/` extensions wiring the two-database API server: a second SQLite connection opened at API subprocess startup; FastAPI dependency injection routes engagement endpoints to the meta DB pool. No engagement endpoint implementations in slice A — those land in slice B. Slice A puts the routing infrastructure in place and exposes a single `GET /engagements/healthcheck` returning `{"status": "ok"}` to verify the wiring works end-to-end.
- `ui/active_engagement_context.py`: QObject singleton with `active_engagement_changed(object)` Qt signal per §2.12. Owned by the application shell; accessed via dependency injection. Reads `current_engagement.json` at app launch to restore the last-active engagement; emits signal accordingly.
- `ui/app.py` extensions: instantiate `ActiveEngagementContext` at app startup; pass to API client constructor; pass to subprocess launcher (env-var injection); attach `current_engagement.json` cross-restart load.
- `ui/refresh.py` extensions: file-watch map extended for `db-export/meta/engagements.json`. The engagement panel's registration happens in slice C; slice A just adds the file to the watch map.
- `migration/dogfood_v0_5.py`: one-shot migration module per PRD §5.4 / DEC-084 with eight steps (backup, create meta DB, run meta DB Alembic to head, INSERT CRMBUILDER row with `engagement_export_dir` set to the absolute path of `db-export/`, copy `v2.db` to `engagements/CRMBUILDER.db`, verify row counts for all eight tracked tables plus catalog tables, delete original `v2.db`, refresh JSON snapshots). Idempotent on rerun. `MigrationResult` dataclass returns success/failure plus per-step diagnostics.
- Engine launcher integration (`crmbuilder-v2-api` entrypoint): invokes `run_dogfood_migration()` at startup when the migration-needed state is detected. Three install scenarios per PRD §5.4. UI shows "Upgrading to v0.5: migrating engagement..." indicator during migration; main window blocked until migration completes.
- Lazy migration helper: `run_engagement_migrations(engagement_code)` function that opens `engagements/{code}.db` directly, runs `alembic upgrade head` against the per-engagement Alembic chain, closes. Invoked by the activation sequence in slice D; included in slice A so the API server can also call it at startup if `CRMBUILDER_V2_DB_PATH` points at a stale DB.
- `.gitignore` extensions: `crmbuilder-v2/data/engagements.db`, `crmbuilder-v2/data/engagements/`, `crmbuilder-v2/data/current_engagement.json`, `crmbuilder-v2/data/v2.db.pre-v0.5-backup`.
- Sidebar "Engagements" group container introduction in `panels/sidebar.py`: a new group rendered above Governance with the position appropriate to its v2-install-level scope. The group is empty in slice A (the engagement panel populates the entry in slice C). Mirrors v0.4's slice A introduction of the empty Methodology group container.
- Tests: `tests/crmbuilder_v2/access/test_meta_db_connection.py` covering connection-pool isolation between the meta DB and the active engagement DB. `tests/crmbuilder_v2/api/test_two_database_routing.py` verifying engagement-prefix routes hit the meta DB pool and other routes hit the active engagement DB pool. `tests/crmbuilder_v2/migration/test_v0_5_dogfood_migration.py` covering the three install scenarios (migration-needed, fresh-install, already-migrated), row-count verification for all eight tracked tables plus catalog tables, idempotency on rerun, backup-and-recovery on simulated failure. `tests/crmbuilder_v2/ui/test_active_engagement_context.py` covering the QObject lifecycle, signal emission, cross-restart load from `current_engagement.json`, drift recovery when file references missing engagement.

**Acceptance gates:**

- Architecture criteria 1 (meta DB schema migration applies cleanly forward and backward).
- Architecture criteria 3 (dogfood migration runs cleanly on a fresh v0.5 launch against a v0.4 database; all eight tracked tables plus catalog tables have row counts in the new path matching the source; `.pre-v0.5-backup` exists; original `v2.db` removed).
- Architecture criteria 4 (idempotent migration; rerun after successful first run is a no-op).
- Architecture criteria 6 (lazy migrations apply on activation — partial here; full coverage in slice D).
- Architecture criteria 8 (API server connects to both databases; engagement-prefix routes hit meta DB; other routes hit active engagement DB).
- Architecture criteria 11 (drift recovery on unreachable engagement — partial; full coverage when picker UI lands in slice D).
- Entity criterion 1 (meta DB schema migration applies cleanly with all ten columns and constraints).
- Entity criterion 10 (engagement endpoints serve from the meta DB — verified via the slice-A healthcheck endpoint; full endpoint coverage in slice B).
- v0.4 regression suite remains green: `uv run pytest tests/crmbuilder_v2/ -v` passes against the migrated CRMBUILDER engagement.
- The application launches against an existing `v2.db`, executes the migration, and reaches the main window with CRMBUILDER as the active engagement (in-memory context populated; `current_engagement.json` written).

**Out of slice:** engagement API endpoints (slice B); engagement panel UI (slice C); switching mechanism (slice D); top-strip widget (slice D); single-gesture creation flow (slice D); version bump and README (slice E).

**Size note:** if the slice prompt exceeds ~800 lines or shows Claude Code degradation during execution, the slice splits into A1 (foundation infrastructure: meta DB connection management, Alembic chain, two-database API server wiring, ActiveEngagementContext, sidebar group container, refresh-service extension) and A2 (dogfood migration module + engine launcher integration + lazy-migration helper). The split decision is made when the slice-A prompt is drafted, not pre-committed in this plan. A split makes v0.5 a six-slice release; the implementation plan is updated to reflect six slices.

---

### Step B — Engagement Schema, Access Layer, and REST API

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.5-B-engagement-schema-and-api.md`

**Deliverables:**

- `access/engagement_models.py`: `Engagement` dataclass with all ten fields per `engagement.md` §3.2; `EngagementStatus` enum (`active`, `paused`, `archived`).
- `access/engagement.py`: repository against the meta DB with eight standard methods: `list_engagements`, `get_engagement`, `create_engagement`, `update_engagement` (full replace), `patch_engagement` (partial), `delete_engagement` (soft), `restore_engagement`, `next_engagement_identifier`. Validation per `engagement.md` §3.5: identifier format `^ENG-\d{3}$` with unique constraint, code regex `^[A-Z][A-Z0-9]{1,9}$` case-insensitive unique within meta DB, name case-insensitive unique within meta DB, status enum, status-transition validation (all three transitions valid; invalid enum values return 422), export-dir validation when set (must be existing writable directory; absolute path), soft-delete semantics. Identifier auto-assignment with concurrent-insert safety per the v0.3-established pattern (row-level locking; retry on conflict).
- `api/routers/engagements.py`: eight standard endpoints per `engagement.md` §3.5.1: GET `/engagements` (with `?include_deleted=true`), GET `/engagements/{identifier}`, POST `/engagements` (server-assigned identifier on omission), PUT `/engagements/{identifier}` (full replace; mismatched identifier in body returns 422), PATCH `/engagements/{identifier}` (partial update; status-transition validation applied), DELETE `/engagements/{identifier}` (soft-delete; idempotent), POST `/engagements/{identifier}/restore` (restore on already-restored returns 422), GET `/engagements/next-identifier` (returns `{"next": "ENG-NNN"}`). All endpoints serve from the meta DB pool established in slice A. All responses use the v2 `{data, meta, errors}` envelope.
- Access-layer hook regenerating `db-export/meta/engagements.json` on write per the standard v0.3+ pattern. The hook is invoked from each write method (create, update, patch, delete, restore) within the same transaction.
- `ui/client.py` extensions: eight new methods mirroring the access-layer methods: `list_engagements()`, `get_engagement(id)`, `create_engagement(...)`, `update_engagement(id, ...)`, `patch_engagement(id, ...)`, `delete_engagement(id)`, `restore_engagement(id)`, `next_engagement_identifier()`. Each method handles the API envelope unwrapping (per CLAUDE.md API envelope contract) and surfaces typed errors.
- Tests: `tests/crmbuilder_v2/access/test_engagement.py` covering all repository methods' happy paths plus error cases (invalid identifier format, invalid code regex including lowercase / leading-digit / out-of-range-length cases, case-insensitive uniqueness on both code and name, status enum, status transitions, export-dir validation, soft-delete semantics, restore semantics, identifier auto-assignment concurrent-safety). `tests/crmbuilder_v2/api/test_engagements_api.py` covering all eight endpoints' happy paths plus 4xx error envelopes (400, 404, 409, 422) with correct envelope shape. Tests verify post-write JSON-snapshot regeneration.

**Acceptance gates:**

- Entity criteria 2 (`engagement_identifier` format constraint enforced).
- Entity criterion 3 (`engagement_code` constraint enforced including case-insensitive uniqueness).
- Entity criterion 4 (`engagement_status` enum + transition validation; default `active` on omission; invalid enum returns 422; free transitions accepted).
- Entity criterion 5 (`engagement_export_dir` validation when set).
- Entity criterion 6 (access-layer methods exist with expected signatures; happy path and at least one error case each pass).
- Entity criterion 7 (REST endpoints return expected responses including 4xx envelope shape).
- Entity criterion 8 (identifier auto-assignment helper; POST with identifier omitted assigns the same value; concurrent POSTs don't collide).
- Entity criterion 9 (soft-delete and restore round-trip including per-engagement DB file not touched).
- Entity criterion 10 (engagement endpoints serve from the meta DB — full coverage; cross-database isolation test from slice A continues passing).
- Slice A tests continue to pass.

**Out of slice:** any UI panel (slice C); switching mechanism (slice D); single-gesture creation flow (slice D); v0.5 README and version bump (slice E).

---

### Step C — Engagement Management Panel UI

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.5-C-engagement-management-panel.md`

**Deliverables:**

- `ui/panels/engagement_panel.py`: `ListDetailPanel` subclass registered as the only entry in the Engagements sidebar group (the group container was introduced in slice A). Master pane columns per PRD §5.1: Identifier (mono, small), Code (mono, small), Name (body), Status (body, status-aware coloring), Last Opened (body, relative date formatted via the format chosen at PRD Open Question 3 — working assumption "N hours/days ago" / "—" when null; refinable during slice C if needed). Default sort by Last Opened descending. Active engagement marked with left accent bar plus Lucide check icon in Identifier column. Soft-deleted rows render in `color.neutral.500` with leading Lucide trash-2 icon when `?include_deleted=true` is active. Right-click context menu: New / Edit / Delete / Restore (Restore on soft-deleted rows). The panel does NOT include "Activate" in the context menu (PRD §5.2 establishes the picker as the switching gesture).
- `ui/dialogs/engagement_crud.py`: `EntityCrudDialog` subclasses for Create and Edit. Create dialog form per PRD §5.1: code (with regex constraint hint visible — "2-10 characters, uppercase letters and digits, must start with a letter"), name, purpose (multi-line, 80px min height), status combo (three values, default `active`), export-dir (text input with directory-browser button; placeholder "Optional — leave blank to disable auto-export"; tooltip per PRD §5.1). Edit dialog identical except `engagement_code` is read-only (rename is v0.6+ candidate per PRD Out of Scope). The Create dialog in slice C creates the meta DB row only; single-gesture creation+activation flow lands in slice D as a `NewEngagementDialog` subclass that extends the slice C Create dialog with the file-creation and activation steps.
- `ui/dialogs/engagement_delete.py`: `EntityCrudDeleteDialog` subclass with the forbid-active-engagement behavior per PRD §5.6. Comparison against `ActiveEngagementContext.engagement_identifier`; when the target is active, the standard edge-text confirmation is replaced with the redirect message and the Delete button is replaced with "Switch engagement" (opens the picker — picker introduced in slice D, so in slice C the button is wired but inert; alternatively wired to the management panel's master pane if picker isn't yet present, with a TODO comment for slice D wiring). Last-engagement edge case per PRD §5.6 (the only engagement on the install) shows the "Create engagement" affordance instead of "Switch engagement".
- Empty-state rendering per PRD §5.1: "No engagements yet" + secondary hint + "Create Engagement" button (opens the slice-C Create dialog — single-gesture flow not present until slice D, so in slice C the button creates the engagement record + file but doesn't activate).
- Refresh-service registration: the panel registers itself with the refresh service to receive `db-export/meta/engagements.json` file-watch events. The panel also subscribes to `active_engagement_changed` Qt signals from `ActiveEngagementContext` to refresh the active-engagement marker (left accent bar + check icon position).
- `ui/client.py` extensions (if not already present from slice B): nothing new in slice C; the panel consumes the slice-B-shipped client methods.
- Tests: `tests/crmbuilder_v2/ui/test_engagement_panel.py` covering master pane rendering (column order, default sort, status-aware coloring, active-engagement marker, soft-deleted styling), context menu actions, file-watch refresh on JSON-snapshot regeneration, signal-driven refresh on engagement-changed. `tests/crmbuilder_v2/ui/test_engagement_crud_dialogs.py` covering Create dialog field set + validation, Edit dialog with code-read-only behavior, Delete dialog forbid-active edge cases (multi-engagement and last-engagement), Restore dialog standard pattern.

**Acceptance gates:**

- Architecture criterion 10 (exports land in engagement's export_dir; dogfood exports land at `db-export/`; null `engagement_export_dir` produces log warning and no file writes — partial coverage; full coverage in slice D after switching exercises export hooks on multiple engagements).
- Entity criterion 6 (access-layer methods exercised via UI: panel CRUD operations exercise the slice-B-shipped methods).
- Entity criterion 12 (sample CBM engagement record creation — partial: the dialog can create the record but the file-creation and activation steps are not yet exposed via the UI; full coverage in slice D).
- Slice A, B tests continue to pass.
- Manual smoke: open the desktop, navigate to the Engagements sidebar entry, see the engagement panel with the CRMBUILDER row, edit the CRMBUILDER record's purpose, save, observe the JSON snapshot refresh and the panel re-render.

**Out of slice:** switching mechanism (slice D); top-strip widget (slice D); picker dropdown (slice D); single-gesture creation flow (slice D); end-to-end CBM-creation smoke (slice E).

---

### Step D — Engagement Switching, Top-Strip, Picker, and Single-Gesture Creation

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.5-D-engagement-switching.md`

**Deliverables:**

- `ui/widgets/engagement_top_strip.py`: top-strip widget per PRD §5.2. Renders inside the sidebar container above the sidebar group entries. Content row: active engagement's `engagement_name` (body), code in parentheses (small, `color.neutral.500`), right-aligned Lucide chevron-down at 14px. Clicking opens the picker. Empty-state rendering when no engagement is active: "No engagement selected" in `color.neutral.500` with caret operable. Subscribes to `active_engagement_changed` Qt signal for refresh.
- `ui/widgets/engagement_picker.py`: picker dropdown per PRD §5.2. Anchored below the top-strip, width matches strip, `radius.subtle` corners, `shadow.dialog` elevation. Rows: live engagements first ordered by `engagement_last_opened_at` descending; paused and archived engagements next, rendered in `color.neutral.500` and sorted to the bottom within their bucket; active engagement marked with leading Lucide check icon in `color.accent.default`. Hover row in `color.neutral.100`. Footer item "Manage engagements..." separated by hairline divider; clicking opens the management panel (navigates to the Engagements sidebar entry). Row click on non-active engagement triggers activation via `ActivationWorker`.
- `ui/widgets/activation_overlay.py`: "Switching engagement..." overlay widget per PRD §5.2. Centred over the main window during activation. Binds to `ActivationWorker` progress signals; shows step description from the worker's signal payload. On activation failure, overlay converts to error state with "Retry" + "Stay in <previous engagement>" affordances.
- `ui/activation_worker.py`: QThread implementing the 12-step activation sequence per `multi-engagement-architecture.md` §4 with the question-6 amendment per PRD §3. Step list:
  1. User-gesture entry point (called with target engagement record).
  2. Reachability check: read engagement from meta DB; verify not soft-deleted; compute DB path; verify file exists and is readable.
  3. Pre-flight Alembic: open engagement's DB directly; run `alembic upgrade head`; close.
  4. Kill API subprocess: SIGTERM with 5s timeout; SIGKILL escalation; wait for port 8765 release.
  5. Kill MCP subprocess: same pattern.
  6. Write `current_engagement.json` atomically (write to `.tmp` then rename).
  7. Update in-memory `ActiveEngagementContext` to new engagement.
  8. Launch new API subprocess with `CRMBUILDER_V2_DB_PATH=engagements/{code}.db` and `CRMBUILDER_V2_API_PORT=8765`. Poll `/health` with exponential backoff (initial 100ms, max 5s, total 30s) until 200 OK.
  9. Launch new MCP subprocess; subprocess wired to the new API.
  10. PATCH `engagement_last_opened_at` via the new API (deferred from step 7 in the original sequence per the question-6 amendment).
  11. Emit `active_engagement_changed` signal on `ActiveEngagementContext`.
  12. UI restore: dismiss overlay; return to interactive state.

  Progress signal emitted after each step's success or failure for the overlay's binding. Failure at any step aborts the sequence; previous engagement remains active.

- `ui/dialogs/new_engagement_dialog.py`: subclass of slice-C's engagement Create dialog implementing the single-gesture creation+activation flow per PRD §5.3. On Submit, runs three sequential operations behind one click:
  1. POST `/engagements` via the slice-B-shipped `client.create_engagement()`. On failure, dialog stays open with inline error per v0.3 validation-error pattern.
  2. Desktop creates `engagements/{code}.db` and runs `alembic upgrade head` against it using the slice-A-shipped `run_engagement_migrations()` helper. On failure, the dialog DELETEs the meta DB row to roll back and shows an error.
  3. Desktop initiates activation via `ActivationWorker` against the new engagement record. On failure after both creates succeed, dialog body converts to error state with "Try switching now" + "Stay in <previous engagement>" affordances. The engagement record persists.

  Progress indicator shows three labels: "Creating engagement record..." → "Initializing database..." → "Switching to <name>..." Each transitions to Lucide check on success or Lucide circle-x on failure.

  The slice C "Create Engagement" button (in the engagement panel context menu and in the empty-state) is rewired in slice D to open `NewEngagementDialog` instead of the slice C `EngagementCreateDialog`.

- `ui/app.py` extensions: instantiate `EngagementTopStrip` and dock it above the sidebar group entries inside the sidebar container. Wire `ActiveEngagementContext` and the top-strip's signal subscriptions.
- `ui/dialogs/engagement_delete.py` extension: the "Switch engagement" button placeholder from slice C is rewired to open the engagement picker. The "Create engagement" affordance in the last-engagement edge case is rewired to open `NewEngagementDialog`.

- Tests: `tests/crmbuilder_v2/ui/test_engagement_top_strip.py` covering rendering, active-engagement display, empty-state, signal-driven refresh. `tests/crmbuilder_v2/ui/test_engagement_picker.py` covering row ordering, status-aware coloring, footer item, hover/selected states, click-to-switch behavior. `tests/crmbuilder_v2/ui/test_activation_worker.py` covering the 12-step sequence happy path, each step's failure mode (reachability fail, migration fail, port-release timeout, MCP kill failure, API health-check timeout, MCP launch failure, PATCH failure), signal emission at each step. `tests/crmbuilder_v2/ui/test_new_engagement_flow.py` covering single-gesture happy path, POST failure (dialog stays open), file-creation failure (meta DB row rolled back), activation failure after both creates succeed (record persists; affordances appear).

**Acceptance gates:**

- Architecture criterion 2 (discovery returns expected results; soft-deleted engagements excluded by default; `?include_deleted=true` includes them).
- Architecture criterion 5 (active state round-trips; `current_engagement.json` written; `engagement_last_opened_at` updated; cross-restart picks up correctly).
- Architecture criterion 6 (lazy migrations apply on activation — full coverage; "Upgrading engagement database..." indicator shows; activation succeeds against a stale DB).
- Architecture criterion 7 (identifier scope works; CBM creation produces SES-001 in CBM's DB after switching; dogfood remains at SES-027+).
- Architecture criterion 9 (MCP server lifecycle mirrors API; MCP subprocess killed and relaunched on switch).
- Architecture criterion 12 (engagement CRUD round-trips end-to-end; create → file appears → activate → switch back → switch to new engagement).
- Architecture criterion 13 (switch UX shows progress; gestures during switch handled; switch completes within a few seconds; panels refresh).
- Entity criterion 11 (`engagement_last_opened_at` updated on activation via the deferred PATCH; meta DB row reflects update; GET returns new value).
- Entity criterion 12 (sample dogfood and CBM engagement records — full coverage: Doug can run v0.5 first launch against existing `v2.db`, dogfood migration creates ENG-001/CRMBUILDER, Doug creates ENG-002/CBM via single-gesture flow, activation switches to CBM).
- Slice A, B, C tests continue to pass.

**Out of slice:** version bump (slice E); README (slice E); end-to-end smoke including return-to-dogfood (slice E); status update (operator-authored after slice E).

---

### Step E — Closeout

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.5-E-closeout.md`

**Deliverables:**

- `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.5.0"`.
- README at `crmbuilder-v2/README.md` extended with a v0.5 release-note entry matching v0.4's format: one-paragraph summary plus a bullet list of release highlights (engagement entity type, multi-engagement routing infrastructure, dogfood migration, Engagements sidebar group with top-strip switching, single-gesture engagement creation, deferred User Process Guide v0.2 update).
- Final regression test pass: `uv run pytest tests/crmbuilder_v2/ -v` returns green across the full suite (v0.4 tests + all new v0.5 tests).
- Final integration smoke `tests/crmbuilder_v2/integration/test_v0_5_end_to_end.py`: full lifecycle in one test — start from a v0.4-state `v2.db`, run the migration, verify CRMBUILDER is active and operable, create a CBM engagement via the New Engagement dialog with single-gesture creation+activation, verify CBM is active and empty, create a session in CBM (verify it gets SES-001), switch back to CRMBUILDER via the picker, verify CRMBUILDER's sessions table contains SES-027+ (the dogfood sessions), switch back to CBM, verify CBM's session count is now 1 and identifier is SES-001 (per-engagement scope confirmed).
- Final manual integration smoke: open the desktop app, confirm Engagements sidebar group renders with one entry; confirm top-strip shows the active engagement; click the strip and confirm picker opens with correct row ordering; click an inactive engagement and confirm activation succeeds with the overlay showing progress; click "Manage engagements..." in the picker and confirm it opens the management panel; click the sidebar "Engagements" entry and confirm same panel opens; confirm About dialog shows v0.5.0.

**Acceptance gates:**

- E1 through E8 per PRD section 7.
- Cumulative acceptance: all 13 architecture-level criteria, all 12 entity-level criteria, and all closeout criteria (E1–E8) pass.

**Out of slice:** status-entity versioned-replace from "v0.4 complete" to "v0.5 complete" (authored through the desktop UI by the operator after slice E lands, not in Claude Code); session records for any of the build-execution conversations (authored through the desktop New Session dialog at conversation close per DEC-029); the User Process Guide v0.2 update (deferred to v0.6 per PRD §2 Out of Scope).

---

## 5. Migration Ordering

Two migration chains land across the five slices:

| Slice | Migration | Purpose |
|-------|-----------|---------|
| A | `crmbuilder-v2/migrations/meta/versions/0001_create_engagements_table.py` | Creates `engagements` table in the meta DB with all ten columns and constraints. First migration in the meta DB's own Alembic chain. |
| A | (no per-engagement migration) | The per-engagement Alembic chain is unchanged from v0.4. The dogfood migration copies `v2.db` (which has the full v0.4 chain applied) to `engagements/CRMBUILDER.db`; the existing migrations apply to a new engagement DB created via the activation flow's lazy-migration mechanism. |
| B | (no schema migration) | Slice B implements the access layer and REST endpoints against the schema landed in slice A. |
| C | (no schema migration) | UI work only. |
| D | (no schema migration) | UI and orchestration only. |
| E | (no schema migration) | Closeout has no schema change. |

Forward-and-backward reversibility is required for the meta DB initial migration. The per-engagement DB Alembic chain inherits the v0.4 reversibility posture unchanged.

The ordering is enforced by the slice dependency chain: meta DB schema in A must precede any engagement access-layer or API work in B; the dogfood migration in A must run before any per-engagement DB access through the new path.

---

## 6. Test Target

`uv run pytest tests/crmbuilder_v2/ -v` continues as the test target across all five slices. Each slice's acceptance gate includes the requirement that prior slices' tests continue to pass — every slice is acceptance-gated on the cumulative test suite.

Test counts per slice (estimates):

- Slice A: ~40-55 new tests (meta DB connection isolation, two-database routing, ActiveEngagementContext lifecycle, dogfood migration including three install scenarios and idempotency and recovery, sidebar group container, refresh-service extension)
- Slice B: ~50-65 new tests (engagement repository methods + validation + concurrent identifier assignment, eight REST endpoints + envelope correctness + 4xx error shapes, JSON-snapshot regeneration on writes)
- Slice C: ~30-40 new tests (panel rendering + sort + status coloring + active marker + soft-deleted styling, CRUD dialogs including forbid-active-delete edge cases, file-watch refresh + signal-driven refresh)
- Slice D: ~40-55 new tests (top-strip rendering + signal subscription, picker dropdown + row ordering + status-aware rendering + hover-select states, activation worker happy path + each step's failure mode + signal emission, single-gesture flow + three failure modes)
- Slice E: ~5-10 new tests (end-to-end smoke); full regression pass on all prior

Estimated cumulative new tests for v0.5: ~165-225, on top of v0.4's existing suite. The numbers are rough; actual counts depend on test granularity choices made during slice execution.

---

## 7. Version Source

Per the CLAUDE.md v2 version-source convention, `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` is the single source of the version string. The About dialog reads via `importlib.metadata` with `__version__` as fallback.

Slice E sets `__version__` to `"0.5.0"`. No other file carries the version.

---

## 8. Closeout Discipline

After Slice E passes, the operator (Doug) writes:

- The session record for the v0.5-Conversation-2 build-planning conversation (this conversation, SES-029 per the renumbering settled in PRD §13) through the v0.3-shipped desktop New Session dialog per DEC-029, OR via the Claude Code apply prompt per the in-sandbox-close-out convention. The kickoff prompt is captured verbatim in `topics_covered`; the conversation summary follows the seed prompt.
- The session record for any Claude Code execution conversation that contributed to v0.5 build, written at the close of that conversation through the desktop dialog.
- The seven DEC-NNN records (DEC-098 through DEC-104 per the renumbering settled in PRD §13) authored via direct API or via the apply prompt.
- The status-entity versioned-replace update from "v0.4 complete" to "v0.5 complete" through the v0.3-shipped desktop versioned-replace dialog. Authored against the post-migration CRMBUILDER engagement (since v0.5 makes the dogfood an engagement with its own scoped governance content).

None of the above are produced inside Claude Code slices; all are operator-authored after the slice work completes.

---

*End of document.*
