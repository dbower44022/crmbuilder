# CLAUDE-CODE-PROMPT-v2-ui-v0.5-A-foundation-and-dogfood-migration

**Last Updated:** 05-16-26 21:00
**Series:** v2-ui-v0.5
**Slice:** A (1 of 5)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`
**Companion architecture:** `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md`
**Companion schema:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md`
**Predecessor slice:** v2-ui-v0.4-F (UI v0.4 closeout — v0.4 test suite passing as of SES-024)

## Purpose

This is the first of five slices that build the CRMBuilder v2 desktop UI v0.5 per the companion PRD and implementation plan. This prompt builds slice **A — Foundation and Dogfood Migration**.

Slice A lays the multi-engagement routing foundation and migrates the existing dogfood `v2.db` into the new engagement model. Eight categories of work:

1. **Meta DB infrastructure.** A separate SQLite file at `crmbuilder-v2/data/engagements.db` with its own Alembic migration chain, hosting the `engagements` registry table.

2. **Per-engagement DB convention.** A `crmbuilder-v2/data/engagements/` directory (gitignored) holding one DB file per engagement at `{engagement_code}.db`.

3. **Two-database API server wiring.** The API subprocess connects to both the meta DB and the active engagement's DB simultaneously, with FastAPI dependency injection routing `/engagements/*` to the meta DB pool and all other endpoints to the active engagement DB pool. A single healthcheck endpoint verifies the wiring; full engagement endpoints land in slice B.

4. **`ActiveEngagementContext` singleton QObject** in the desktop with an `active_engagement_changed(object)` Qt signal mirroring v1's `ActiveClientContext`. Cross-restart load from `current_engagement.json`.

5. **Lazy-migration helper.** A `run_engagement_migrations(engagement_code)` function that opens a per-engagement DB directly and applies the existing v0.4 Alembic chain to head. Invoked at activation time (slice D) and at API startup if the env-var-pointed path is stale.

6. **Dogfood migration module.** A self-contained module at `crmbuilder-v2/src/crmbuilder_v2/migration/dogfood_v0_5.py` performing the eight-step backup-create-verify-delete sequence per `multi-engagement-architecture.md` §3.7 and PRD §5.4. Invoked by the engine launcher at first launch.

7. **Engagements sidebar group container.** New empty container above Governance in `panels/sidebar.py`. The engagement panel populates the entry in slice C.

8. **Refresh-service extension.** `db-export/meta/engagements.json` added to the file-watch map.

After this slice, Doug's machine is migrated: `v2.db` is gone, `engagements/CRMBUILDER.db` exists with matching row counts, the meta DB exists with the CRMBUILDER row, `current_engagement.json` points at CRMBUILDER. The application launches with CRMBUILDER as the active engagement and operates exactly as it did under v0.4 — but the infrastructure for multi-engagement is now in place.

This slice does NOT add any engagement REST endpoints beyond the healthcheck (slice B), any engagement panel UI (slice C), any switching mechanism or top-strip widget (slice D), the version bump or README release note (slice E). It does NOT write any session, decision, or planning records — those are authored at the v0.5 build's closeout per the in-sandbox close-out convention.

## Project context

UI v0.4 shipped as the most recent v2 release (SES-024 slice F closeout, 05-15-26). The v0.4 build added four new methodology entity types (`domain`, `entity`, `process`, `crm_candidate`) under a new Methodology sidebar group. v0.5 closes the engagement-routing gap: v0.4's methodology tables and v2's governance tables both live in a single SQLite file at `crmbuilder-v2/data/v2.db` that hosts the v2-build's own dogfood (24 sessions, 86 decisions, 17 planning items, 66 references, 222 change-log entries). Running CBM Phase 1 against the dogfood instance would mix two unrelated bodies of data into one file. v0.5 operationalises DEC-039's "one v2 instance per engagement, separate SQLite, separate API port" finding into a designed feature.

The minimum-viable scope philosophy applies. Slice A is the foundation; if it lands wrong, every downstream slice carries the consequence. The dogfood migration is bundled with foundation because foundation alone is a non-functional intermediate state (meta DB exists but no engagement records and the dogfood data is still at the old path).

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug Bower`
   - `git config user.email` should return `dbower44022@users.noreply.github.com`
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm the storage system is operational. Verify-first, only start if not already running:
   - First check: `curl -sf http://127.0.0.1:8765/health` — if it returns 200, the API is already running; proceed to step 6.
   - If the health check fails, start the API in the background: `uv run crmbuilder-v2-api &`. Wait ~3 seconds, then re-run the health check. If still failing, stop and report.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. Note the test count; this is the regression net for slice A.
7. **Confirm the dogfood is at the v0.4 path.** `ls -la crmbuilder-v2/data/v2.db` should show the existing file. `ls -la crmbuilder-v2/data/engagements.db` and `ls -la crmbuilder-v2/data/engagements/` should both fail (no migration has run yet). If either v0.5 path already exists, stop and report — the migration may have been partially applied.
8. **Verify dogfood row counts before migration.** Capture baseline counts via API for verification against post-migration state:

   ```bash
   for ep in sessions decisions planning_items references change_log catalog_entities; do
     COUNT=$(curl -sf http://127.0.0.1:8765/${ep} | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data', [])))")
     echo "${ep}: ${COUNT}"
   done
   ```

   Record the counts; the migration verification step asserts against these. Note that the API response is the `{data, meta, errors}` envelope; the `.data` field is the list. (Per CLAUDE.md API envelope contract.)

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry. Pay particular attention to:
   - The "CRMBuilder v2 — Methodology Rearchitecture" section overall
   - The API envelope contract `{data, meta, errors}` (every endpoint returns this shape)
   - The prefixed-identifier rule (POST bodies must include the computed identifier for prefixed entity types; helpers like `compute_next_session_identifier` exist for governance entities; the engagement entity is new and slice B implements its `next_engagement_identifier` helper)
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` — release requirements. All slices.
3. `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md` — slice breakdown. Pay particular attention to **Step A** in section 4 and section 5 (Migration Ordering).
4. `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — the routing architecture this slice implements. Read §3.1, §3.2, §3.3, §3.6 (lazy migrations), §3.7 (dogfood migration spec — the eight steps slice A executes), §3.10 (two-database API server detail). The activation sequence (§4) is slice D, not slice A.
5. `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md` §3.1, §3.2, §3.3 — the schema you are creating in the meta DB. Validation and API surface (§3.5) belong to slice B; slice A creates only the table structure.
6. v1 precedent files (read briefly to understand the pattern v0.5 mirrors):
   - `automation/db/master_schema.py` — v1's master DB schema with the Client table; precedent for the meta DB pattern.
   - `automation/ui/active_client_context.py` — v1's active-client context; precedent for `ActiveEngagementContext`.
7. v2 storage and UI surfaces you will modify or add to:
   - `crmbuilder-v2/migrations/` — latest revision; identify the next revision number. The meta DB Alembic chain at `crmbuilder-v2/migrations/meta/` is brand new (slice A creates it).
   - `crmbuilder-v2/src/crmbuilder_v2/access/` — the existing access layer; the meta DB pool lives parallel to the existing per-engagement DB pool.
   - `crmbuilder-v2/src/crmbuilder_v2/api/` — the existing API server; the two-database wiring extends the existing FastAPI app.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` — application shell.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/sidebar.py` — sidebar rendering.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — `QFileSystemWatcher` and the entity-type → panel signal map.
8. `.gitignore` — note the existing structure; new entries land for `crmbuilder-v2/data/engagements.db`, `crmbuilder-v2/data/engagements/`, `crmbuilder-v2/data/current_engagement.json`, and `crmbuilder-v2/data/v2.db.pre-v0.5-backup`.

## Step 1 — Meta DB Alembic chain and initial migration

Create the meta DB's Alembic chain as a separate chain from the per-engagement Alembic chain.

### 1.1 Alembic configuration

Create:
- `crmbuilder-v2/migrations/meta/alembic.ini` — minimal Alembic config pointing at `crmbuilder-v2/data/engagements.db` via `sqlalchemy.url` (the URL can be resolved at run time from the same config-loading helper used by the per-engagement chain).
- `crmbuilder-v2/migrations/meta/env.py` — Alembic env script following the existing v0.4 `env.py` pattern (offline + online modes; logging configuration; metadata import; sqlalchemy URL from config).

### 1.2 Initial migration

Create `crmbuilder-v2/migrations/meta/versions/0001_create_engagements_table.py`:

```python
"""create engagements table

Revision ID: 0001
Revises:
Create Date: 2026-05-16 21:00:00
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create engagements table with all ten columns per engagement.md §3.2
    # Constraints:
    # - engagement_identifier UNIQUE, CHECK regex ^ENG-\d{3}$
    # - engagement_code CHECK regex ^[A-Z][A-Z0-9]{1,9}$ + UNIQUE (case-insensitive)
    # - engagement_name UNIQUE (case-insensitive)
    # - engagement_status CHECK IN ('active', 'paused', 'archived')
    # - engagement_purpose NOT NULL
    # - audit timestamps default-set
    ...

def downgrade() -> None:
    # DROP TABLE engagements
    ...
```

Implementation: create the table with PRAGMA-enforced CHECK constraints where SQLite supports them; case-insensitive uniqueness via `COLLATE NOCASE` on the indexed columns or via separate unique indexes on `LOWER(...)` expressions. The choice mirrors the v0.4 entity tables' pattern.

### 1.3 Meta DB Alembic entry-point

Add a console-script entry point or a CLI helper in `crmbuilder-v2/src/crmbuilder_v2/migration/meta_alembic.py` that wraps `alembic` invocations against the meta DB's chain. The helper is called by the engine launcher to apply the meta DB chain at desktop startup.

## Step 2 — Meta DB connection management

Create `crmbuilder-v2/src/crmbuilder_v2/access/meta_db.py`:

```python
class MetaDBConfig:
    PATH = "crmbuilder-v2/data/engagements.db"  # resolved at runtime to absolute path

def get_meta_db_connection() -> Connection:
    """Return a connection from the meta DB pool. Independent from the
    per-engagement DB pool."""
    ...

def init_meta_db_pool() -> None:
    """Initialize the meta DB connection pool. Called once at API startup."""
    ...
```

Key points:
- The meta DB pool is separate from the per-engagement DB pool. The existing pool initialization in the access layer (which currently uses `CRMBUILDER_V2_DB_PATH`) is unchanged; a second pool is added for the meta DB.
- Use SQLite WAL mode for both pools per the v0.4 pattern.
- The meta DB path is hard-coded relative to the engine repo (not configurable via environment variable in v0.5; the env var `CRMBUILDER_V2_DB_PATH` continues to point at the active engagement DB).

## Step 3 — Two-database API server wiring

Modify `crmbuilder-v2/src/crmbuilder_v2/api/` to maintain two connection pools and route requests appropriately.

### 3.1 FastAPI app initialization

At API subprocess startup, initialize both pools:

```python
@app.on_event("startup")
async def startup():
    init_meta_db_pool()  # NEW
    init_engagement_db_pool()  # existing, renamed for clarity
```

### 3.2 Dependency injection

Define two dependency functions for FastAPI:

```python
def get_meta_db() -> Connection:
    """Yield a connection from the meta DB pool."""
    ...

def get_engagement_db() -> Connection:
    """Yield a connection from the active engagement DB pool."""
    ...
```

Existing routers continue to use `get_engagement_db` (renamed from whatever the v0.4 helper was called). Engagement routes in slice B will use `get_meta_db`.

### 3.3 Healthcheck endpoint

Add a single endpoint to verify the wiring works end-to-end in slice A:

```python
@router.get("/engagements/healthcheck")
async def engagement_healthcheck(db: Connection = Depends(get_meta_db)):
    # Verify the meta DB connection is alive; return engagement count
    count = db.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
    return envelope_response({"status": "ok", "engagement_count": count})
```

The endpoint uses the standard `{data, meta, errors}` envelope per CLAUDE.md. The response wrapping is the same helper the rest of the API uses.

## Step 4 — `ActiveEngagementContext` QObject

Create `crmbuilder-v2/src/crmbuilder_v2/ui/active_engagement_context.py`:

```python
from PySide6.QtCore import QObject, Signal

class ActiveEngagementContext(QObject):
    active_engagement_changed = Signal(object)  # emits Engagement | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engagement: "Engagement | None" = None

    def engagement(self) -> "Engagement | None": ...
    def engagement_identifier(self) -> str | None: ...
    def engagement_code(self) -> str | None: ...

    def set_engagement(self, engagement: "Engagement | None") -> None:
        """Update active engagement; emits signal."""
        self._engagement = engagement
        self.active_engagement_changed.emit(engagement)

    def clear(self) -> None:
        self.set_engagement(None)

    def load_from_disk(self) -> None:
        """Read current_engagement.json and populate self._engagement.
        If file missing, malformed, or references unreachable engagement,
        clear state and emit signal."""
        ...

    def persist_to_disk(self) -> None:
        """Atomically write current_engagement.json from self._engagement."""
        ...
```

Note: the `Engagement` dataclass is defined in slice B. Slice A's `active_engagement_context.py` imports from `crmbuilder_v2.access.engagement_models` which slice A creates as a stub containing just the dataclass shape and the `EngagementStatus` enum. Slice B fleshes out the repository against this dataclass.

The stub at `crmbuilder-v2/src/crmbuilder_v2/access/engagement_models.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class EngagementStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"

@dataclass
class Engagement:
    engagement_identifier: str
    engagement_code: str
    engagement_name: str
    engagement_purpose: str
    engagement_status: EngagementStatus
    engagement_last_opened_at: datetime | None
    engagement_export_dir: str | None
    engagement_created_at: datetime
    engagement_updated_at: datetime
    engagement_deleted_at: datetime | None
```

## Step 5 — Application shell integration

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/app.py`:

- Instantiate `ActiveEngagementContext` at app startup.
- Call `context.load_from_disk()` after Qt application is initialized but before the main window is shown.
- Pass the context to the storage client constructor and to any subprocess launcher (env-var injection happens in slice D's activation flow; in slice A, the env-var-pointed DB is set by the engine launcher at startup).
- Wire the context to be accessible via a dependency-injection helper that panels can consume.

## Step 6 — Sidebar Engagements group container

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/panels/sidebar.py` to introduce a new sidebar group titled "Engagements" positioned above the existing Governance group. The group is initially empty; slice C populates the single entry. Mirrors v0.4's slice-A introduction of the empty Methodology group container.

The group's container styling inherits from `styling-design-pass.md` if the styling workstream's tokens module has shipped by the time slice A executes; otherwise inline values matching the existing Governance group's appearance with a TODO comment for token replacement.

## Step 7 — Refresh service extension

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` to add `PRDs/product/crmbuilder-v2/db-export/meta/engagements.json` to the file-watch map. The mapping is from the file path to a signal that the engagement management panel (slice C) will subscribe to.

The slice-A change is just adding the file path to the map. Slice C registers the engagement panel as a subscriber.

## Step 8 — Lazy-migration helper

Create or extend `crmbuilder-v2/src/crmbuilder_v2/migration/lazy_migration.py`:

```python
def run_engagement_migrations(engagement_code: str) -> None:
    """Open the engagement's DB directly (bypassing the API),
    apply the per-engagement Alembic chain to head, close.
    Raises MigrationError on failure."""
    path = f"crmbuilder-v2/data/engagements/{engagement_code}.db"
    # alembic upgrade head against this path
    ...
```

Slice A includes the helper because slice D's activation flow consumes it. The helper is also used by the dogfood migration in step 9 (the per-engagement chain applies idempotently to the post-copy `CRMBUILDER.db`, ensuring the alembic_version table is properly tracked).

## Step 9 — Dogfood migration module

Create `crmbuilder-v2/src/crmbuilder_v2/migration/__init__.py` (empty) and `crmbuilder-v2/src/crmbuilder_v2/migration/dogfood_v0_5.py`:

```python
from dataclasses import dataclass

@dataclass
class MigrationResult:
    success: bool
    steps_completed: list[str]
    error: str | None
    row_count_verifications: dict[str, tuple[int, int]]  # table -> (source, dest)

def needs_migration() -> bool:
    """True if v2.db exists at old path AND meta DB is missing or empty."""
    ...

def run_dogfood_migration() -> MigrationResult:
    """Execute the eight-step dogfood migration per DEC-084 / PRD §5.4.
    Idempotent on rerun."""
    ...
```

The eight steps per PRD §5.4:

1. **Backup.** Copy `crmbuilder-v2/data/v2.db` to `crmbuilder-v2/data/v2.db.pre-v0.5-backup`. Verify file size matches source.

2. **Create meta DB and run Alembic.** Create empty SQLite file at `crmbuilder-v2/data/engagements.db`. Run the meta DB Alembic chain to head (calling the helper from step 1.3).

3. **INSERT CRMBUILDER engagement row.** Open the meta DB; INSERT a row with these field values:
   - `engagement_identifier`: `"ENG-001"`
   - `engagement_code`: `"CRMBUILDER"`
   - `engagement_name`: `"CRMBuilder v2"`
   - `engagement_purpose`: `"Dogfood instance hosting the v2 build's own governance content (sessions, decisions, planning items, methodology catalog)."`
   - `engagement_status`: `"active"`
   - `engagement_export_dir`: the absolute path of `PRDs/product/crmbuilder-v2/db-export/` computed from the engine repo root via `pathlib.Path(__file__).parent.parent.parent.parent.parent / "PRDs/product/crmbuilder-v2/db-export"`. Resolve to absolute.
   - `engagement_created_at`, `engagement_updated_at`: current ISO 8601 UTC timestamp
   - `engagement_last_opened_at`, `engagement_deleted_at`: null

4. **Copy v2.db.** Copy `crmbuilder-v2/data/v2.db` to `crmbuilder-v2/data/engagements/CRMBUILDER.db`. Create the `engagements/` directory if not present.

5. **Verify row counts.** Open both `v2.db` and `engagements/CRMBUILDER.db`. For each of the v0.4 tables — `sessions`, `decisions`, `planning_items`, `risks`, `topics`, `references` (a.k.a. `refs`), `charter`, `status`, `change_log`, plus the four v0.4 methodology entity tables (`domains`, `entities`, `processes`, `crm_candidates`), plus the catalog tables (`catalog_entities`, `catalog_fields`, `catalog_personas`) — query `SELECT COUNT(*) FROM <table>` against both. Record source and destination counts; fail if any pair mismatches. Close both connections.

6. **Delete original v2.db.** `os.remove("crmbuilder-v2/data/v2.db")`. The `.pre-v0.5-backup` copy remains.

7. **Refresh JSON snapshots.** Trigger the existing access-layer hook that regenerates `db-export/` from the per-engagement DB content. Trigger the meta DB hook to regenerate `db-export/meta/engagements.json` (the meta DB hook is new in slice A; access-layer write methods aren't shipped until slice B, but the snapshot regeneration helper can be invoked directly here).

8. **Write `current_engagement.json`.** Atomically write the file with `engagement_identifier="ENG-001"`, `engagement_code="CRMBUILDER"`, `set_at=<ISO 8601 UTC>`.

Idempotency: at function entry, call `needs_migration()`. If false (meta DB exists with CRMBUILDER row AND `engagements/CRMBUILDER.db` exists AND `v2.db` does NOT exist at old path), return `MigrationResult(success=True, steps_completed=["already_migrated"], ...)` immediately.

Failure recovery: any step's failure is captured in `MigrationResult.error`. The `.pre-v0.5-backup` is preserved (it's never deleted by the migration). The user is shown the error and instructed to revert by deleting the new files and reverting code to the prior v2 release. A failed migration does NOT continue to subsequent steps.

## Step 10 — Engine launcher integration

Modify the `crmbuilder-v2-api` console-script entry point (or the equivalent launcher hook) to:

1. Apply the meta DB Alembic chain at startup (idempotent; no-op if already at head).
2. Detect the migration-needed state via `needs_migration()`.
3. If migration needed: invoke `run_dogfood_migration()`. Show UX progress (this is a desktop concern, so the dogfood-migration UX surface is in `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` rather than the API entrypoint — the launcher exposes a callable that the desktop wraps with a "Upgrading to v0.5: migrating engagement..." progress indicator).
4. Fresh-install case (no `v2.db`, no migration needed): proceed normally; the engagement panel's empty state in slice C handles the no-engagement case.
5. Already-migrated case: log "Dogfood already at v0.5 path; proceeding" and continue.

The desktop progress indicator wraps the migration call:

```python
# in ui/app.py, called before main window show
if migration.needs_migration():
    show_progress_dialog("Upgrading to v0.5: migrating engagement...")
    result = migration.run_dogfood_migration()
    hide_progress_dialog()
    if not result.success:
        show_error_dialog("Migration failed", result.error)
        sys.exit(1)
```

## Step 11 — `.gitignore` extensions

Append to `.gitignore`:

```
crmbuilder-v2/data/engagements.db
crmbuilder-v2/data/engagements/
crmbuilder-v2/data/current_engagement.json
crmbuilder-v2/data/v2.db.pre-v0.5-backup
```

## Step 12 — Tests

Add four new test modules:

### 12.1 `tests/crmbuilder_v2/access/test_meta_db_connection.py`

Tests for the two-pool connection management:

- `init_meta_db_pool()` succeeds; subsequent `get_meta_db_connection()` returns a usable connection.
- Connection-pool isolation: a transaction on the meta DB connection does not see changes from a concurrent transaction on the active engagement DB connection.
- Pool teardown on app shutdown closes both pools cleanly.

### 12.2 `tests/crmbuilder_v2/api/test_two_database_routing.py`

Tests for the FastAPI dependency-injection routing:

- A GET request to `/engagements/healthcheck` hits the meta DB pool. Verify by populating the meta DB with a test engagement row and observing it in the healthcheck count.
- A GET request to `/sessions` hits the active engagement DB pool. Verify by populating the active engagement DB with a test session and observing it in the response.
- The two pools are not cross-contaminated: a write to the meta DB does not appear in `/sessions`; a write to `/sessions` does not appear in the meta DB.

### 12.3 `tests/crmbuilder_v2/migration/test_v0_5_dogfood_migration.py`

Tests for the dogfood migration:

- **Migration-needed scenario.** Create a fixture `v2.db` with seeded rows in all tracked tables. Run `run_dogfood_migration()`. Verify all eight steps complete, all row counts match, `v2.db` is gone, `.pre-v0.5-backup` exists, `engagements.db` exists with CRMBUILDER row, `engagements/CRMBUILDER.db` exists.
- **Fresh-install scenario.** No `v2.db` present. `needs_migration()` returns False. Run launcher: meta DB is created, Alembic applies, no migration runs.
- **Already-migrated scenario.** Run migration once, verify success. Run again. Verify the second run returns immediately with `steps_completed=["already_migrated"]` and no file modifications.
- **Idempotency on partial failure recovery.** Simulate failure at step 5 (row-count mismatch) — verify `.pre-v0.5-backup` is preserved; verify the meta DB and `engagements/CRMBUILDER.db` are left in their partial state (per DEC-084's posture: the user reverts manually).
- **Row-count verification across all tracked tables.** All twelve tables (eight v0.3-or-earlier governance + four v0.4 methodology) plus the three catalog tables must have matching counts. A deliberately-corrupted source (mismatched count) fails verification.

### 12.4 `tests/crmbuilder_v2/ui/test_active_engagement_context.py`

Tests for the `ActiveEngagementContext` QObject:

- Default state is `None` engagement; signal not emitted on construction.
- `set_engagement(eng)` emits `active_engagement_changed` with the engagement; subsequent `engagement()` returns it.
- `clear()` emits the signal with `None`; subsequent `engagement()` returns `None`.
- `load_from_disk()` reads `current_engagement.json` and populates state; signal emits the engagement (or `None` on missing/malformed file).
- `persist_to_disk()` writes the file atomically (verify via a write that simulates a crash mid-write — the original file should be intact or fully replaced, never partially written).
- Drift recovery: `current_engagement.json` references a soft-deleted or missing engagement; `load_from_disk()` clears state and emits `None`.

## Acceptance verification

Before committing, run each of the following and confirm:

1. **Vocab and connection tests pass.** `uv run pytest tests/crmbuilder_v2/access/test_meta_db_connection.py -v` — all green.
2. **Routing tests pass.** `uv run pytest tests/crmbuilder_v2/api/test_two_database_routing.py -v` — all green.
3. **Migration tests pass.** `uv run pytest tests/crmbuilder_v2/migration/test_v0_5_dogfood_migration.py -v` — all green.
4. **Context tests pass.** `uv run pytest tests/crmbuilder_v2/ui/test_active_engagement_context.py -v` — all green.
5. **Meta DB Alembic applies forward and backward.** Run the meta DB Alembic chain: `upgrade head` → `downgrade base` → `upgrade head`. All three operations succeed.
6. **Full v0.5 test suite green.** `uv run pytest tests/crmbuilder_v2/ -v` — no failures. The pre-flight regression net is preserved.
7. **Dogfood migration runs on Doug's actual machine.** Stop the running API. Manually verify `v2.db` exists at old path and `engagements.db` does not. Restart with `uv run crmbuilder-v2-api &`; the launcher detects migration-needed and runs the dogfood migration. After completion: `v2.db` is gone, `v2.db.pre-v0.5-backup` exists, `engagements.db` exists, `engagements/CRMBUILDER.db` exists. The API responds at `http://127.0.0.1:8765/health` (200) and `http://127.0.0.1:8765/engagements/healthcheck` (returns `engagement_count: 1`). Existing API endpoints continue to work against the migrated `engagements/CRMBUILDER.db`.
8. **JSON snapshots refreshed.** `PRDs/product/crmbuilder-v2/db-export/` contains the existing snapshot files (sessions.json, decisions.json, etc.) with the same content as before migration (row counts unchanged because the migration is a verified copy). `PRDs/product/crmbuilder-v2/db-export/meta/engagements.json` exists and contains the CRMBUILDER row.
9. **Sidebar Engagements group renders.** Open the desktop app; confirm an "Engagements" group header renders above the Governance group. The group is empty in slice A; just confirm the header is present.
10. **Application launches with CRMBUILDER active.** `current_engagement.json` exists with `engagement_code="CRMBUILDER"`. The application's About dialog still shows v0.4.0 (the bump lands in slice E). All existing v0.4 panels (Sessions, Decisions, etc., plus the four methodology entity panels) operate against the migrated CRMBUILDER engagement.

If any verification step fails, stop and report to Doug before committing. The `.pre-v0.5-backup` is the recovery point.

## Commit

Single commit:

```bash
git add crmbuilder-v2/migrations/meta/ \
        crmbuilder-v2/src/crmbuilder_v2/access/meta_db.py \
        crmbuilder-v2/src/crmbuilder_v2/access/engagement_models.py \
        crmbuilder-v2/src/crmbuilder_v2/api/ \
        crmbuilder-v2/src/crmbuilder_v2/migration/ \
        crmbuilder-v2/src/crmbuilder_v2/ui/active_engagement_context.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/sidebar.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py \
        tests/crmbuilder_v2/access/test_meta_db_connection.py \
        tests/crmbuilder_v2/api/test_two_database_routing.py \
        tests/crmbuilder_v2/migration/test_v0_5_dogfood_migration.py \
        tests/crmbuilder_v2/ui/test_active_engagement_context.py \
        .gitignore
git commit -m "v2: v0.5 slice A — foundation infrastructure and dogfood migration (meta DB, two-database API, ActiveEngagementContext, v2.db → engagements/CRMBUILDER.db)"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT implement the engagement REST endpoints beyond the healthcheck (those land in slice B).
- Do NOT add the engagement management panel (slice C).
- Do NOT add the top-strip widget or picker (slice D).
- Do NOT add the activation worker or single-gesture creation flow (slice D).
- Do NOT bump `__version__` to `0.5.0` (slice E).
- Do NOT add the README v0.5 release note (slice E).
- Do NOT write any session, decision, or planning records to the database. Per the in-sandbox close-out convention, those are authored at v0.5 build's closeout.
- Do NOT modify any v0.4 entity type's schema, access-layer methods, REST endpoints, or UI behavior. Slice A is strictly additive — the two-database routing extends the existing API; existing endpoints continue using the existing connection pattern (now renamed for clarity but functionally unchanged).
- Do NOT skip the `.pre-v0.5-backup` step. The backup is the recovery point if anything goes wrong; deleting `v2.db` before the backup is the one operation that loses data.
- Do NOT introduce engagement validation logic beyond what's in the meta DB schema's CHECK constraints. Full validation (regex enforcement at access-layer, status-transition rules, export-dir-must-be-writable-directory) lands in slice B.
- Do NOT remove or modify the existing `db-export/` content. The migration regenerates the snapshots from the new path; the content should be identical (it's a verified copy).

## If slice A bloats

If during execution this slice's prompt scope feels too large for one coherent Claude Code run, the slice can split into A1 (Steps 1–8 + 11 — foundation infrastructure, no migration) and A2 (Steps 9–10 + 12 step 3 — dogfood migration module, engine launcher integration, migration tests). The decision is made at execution time, not pre-committed. If you split, name the second prompt file `CLAUDE-CODE-PROMPT-v2-ui-v0.5-A2-dogfood-migration.md` and rename the existing file to `CLAUDE-CODE-PROMPT-v2-ui-v0.5-A1-foundation.md`; update the slice count in both prompts and in the implementation plan to reflect six slices.

---

*End of prompt.*
