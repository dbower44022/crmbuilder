# CLAUDE-CODE-PROMPT-v2-ui-v0.5-B-engagement-schema-and-api

**Last Updated:** 05-16-26 21:00
**Series:** v2-ui-v0.5
**Slice:** B (2 of 5)
**Status:** Ready to execute (after slice A passes)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`
**Companion schema:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md`
**Predecessor slice:** v2-ui-v0.5-A (foundation + dogfood migration)

## Purpose

This is the second of five slices that build CRMBuilder v2 UI v0.5. This prompt builds slice **B — Engagement Schema, Access Layer, and REST API**.

Slice B layers the engagement entity's full implementation on top of slice A's foundation. Five categories of work:

1. **Engagement dataclass and status enum.** Fleshed out from slice A's stub at `access/engagement_models.py`.

2. **Access-layer repository.** `access/engagement.py` against the meta DB pool from slice A — eight standard methods with validation per `engagement.md` §3.5.

3. **REST API surface.** Eight standard endpoints at `api/routers/engagements.py` consuming the slice-A `get_meta_db` dependency. Replaces slice A's stub healthcheck endpoint.

4. **JSON snapshot hook.** Writes to the meta DB regenerate `PRDs/product/crmbuilder-v2/db-export/meta/engagements.json` per the standard v0.3+ pattern (DEC-022, DEC-008).

5. **Client extensions.** Eight new methods in `ui/client.py` mirroring the access-layer methods, with envelope unwrapping per the CLAUDE.md API envelope contract.

After this slice, the engagement REST API is operable end-to-end via direct calls or external scripts. No UI exposes it yet (slice C builds the management panel). The CRMBUILDER row created by slice A is exercisable via GET / PUT / PATCH / DELETE; new engagement records can be created via POST; identifier auto-assignment works (POST `/engagements` with `engagement_identifier` omitted assigns `ENG-NNN`).

This slice does NOT add any UI surface, any switching mechanism, any single-gesture creation flow, the version bump, or the README release note.

## Project context

Slice A landed the meta DB schema, the two-database API server wiring with a single healthcheck endpoint, the `ActiveEngagementContext` QObject, the dogfood migration module, and the empty Engagements sidebar group container. The meta DB exists on Doug's machine with one engagement row (CRMBUILDER) created by the dogfood migration.

Slice B turns the engagement entity into a fully-operable CRUD surface. The validation rules in `engagement.md` §3.5 are the source of truth: identifier regex, code regex (mirroring v1's Client.code constraint exactly), case-insensitive uniqueness on name and code, status enum, status-transition validation, export-dir validation, soft-delete semantics, identifier auto-assignment with concurrent-insert safety. The eight standard endpoints follow the v0.3+ pattern established for every methodology entity.

The slice is acceptance-gated on full validation correctness and on the API envelope shape matching the existing v2 contract.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity is set (`Doug Bower`, `dbower44022@users.noreply.github.com`).
4. Pull latest from origin: `git pull --rebase origin main`.
5. **Verify slice A is in place.** `crmbuilder-v2/data/engagements.db` exists. `crmbuilder-v2/data/engagements/CRMBUILDER.db` exists. `crmbuilder-v2/migrations/meta/versions/0001_create_engagements_table.py` exists. `crmbuilder-v2/src/crmbuilder_v2/access/meta_db.py` exists. `crmbuilder-v2/src/crmbuilder_v2/access/engagement_models.py` exists with the `Engagement` dataclass stub and `EngagementStatus` enum. If any are missing, slice A did not complete; stop and report.
6. Confirm API operational: `curl -sf http://127.0.0.1:8765/engagements/healthcheck` should return 200 with `engagement_count: 1`. If not, start with `uv run crmbuilder-v2-api &` and re-check.
7. Confirm slice A's test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`.

## Reading order

1. `crmbuilder/CLAUDE.md` — API envelope contract, prefixed-identifier rule, methodology-rearchitecture section.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` §2, §4, §5.
3. `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md` Step B.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md` — full document. §3.2 (fields), §3.3 (constraints), §3.4 (status lifecycle), §3.5 (validation + endpoints), §3.7 (acceptance criteria) are the authoritative requirements.
5. v0.4 entity precedent files (read briefly to mirror the pattern):
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/domain.py` — repository pattern for methodology entities
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/domains.py` — REST endpoint pattern
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` — client method pattern
6. Slice A's deliverables:
   - `crmbuilder-v2/src/crmbuilder_v2/access/meta_db.py` — confirm `get_meta_db_connection()` signature
   - `crmbuilder-v2/src/crmbuilder_v2/access/engagement_models.py` — extend if needed
   - `crmbuilder-v2/src/crmbuilder_v2/api/` — confirm `get_meta_db` dependency function signature

## Step 1 — Engagement dataclass and status enum

Verify `crmbuilder-v2/src/crmbuilder_v2/access/engagement_models.py` from slice A contains both the `Engagement` dataclass with ten fields and the `EngagementStatus` enum. If any field is missing or typed incorrectly per `engagement.md` §3.2, extend.

If slice A's stub used `str | None` for any field that needs typed handling (e.g., `engagement_status` should round-trip as `EngagementStatus` even though stored as TEXT), refactor here. The dataclass is the access-layer's canonical shape; downstream code (API routers, UI client) consumes this type.

Add helper methods to the dataclass:
- `to_dict() -> dict` for API envelope serialization (status as `str` value, datetimes as ISO 8601 strings, null fields as `None`)
- `from_row(row: sqlite3.Row) -> Engagement` for SELECT result hydration

## Step 2 — Access-layer repository

Create `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py` against the meta DB. Eight methods:

```python
def list_engagements(*, include_deleted: bool = False) -> list[Engagement]:
    """SELECT all engagements ordered by engagement_last_opened_at DESC NULLS LAST.
    By default excludes soft-deleted. Returns hydrated Engagement objects."""

def get_engagement(identifier: str) -> Engagement:
    """SELECT by engagement_identifier. Raises NotFoundError on miss."""

def create_engagement(
    *,
    engagement_identifier: str | None = None,
    engagement_code: str,
    engagement_name: str,
    engagement_purpose: str,
    engagement_status: EngagementStatus = EngagementStatus.ACTIVE,
    engagement_export_dir: str | None = None,
) -> Engagement:
    """Validate all fields per §3.5; auto-assign identifier if omitted via
    next_engagement_identifier() with row-lock+retry; INSERT; return hydrated row.
    Raises ValidationError for any §3.5 violation."""

def update_engagement(identifier: str, **fields) -> Engagement:
    """Full-replace PUT semantics. Validate all fields; UPDATE; return hydrated row.
    The engagement_identifier must match the URL identifier (caller enforces).
    The engagement_code is immutable post-creation; if provided in fields with
    a different value, raise ValidationError(field='engagement_code',
    code='immutable_field')."""

def patch_engagement(identifier: str, **fields) -> Engagement:
    """Partial-update PATCH semantics. Only specified fields are validated and
    updated. Status transitions: all three transitions (active ↔ paused ↔ archived)
    are valid; invalid enum value raises ValidationError(field='engagement_status',
    code='invalid_enum_value'). engagement_code immutable post-creation."""

def delete_engagement(identifier: str) -> Engagement:
    """Soft-delete: SET engagement_deleted_at = NOW WHERE engagement_identifier = ?
    AND engagement_deleted_at IS NULL. Idempotent: already-deleted returns the
    record unchanged. Returns the hydrated post-delete row."""

def restore_engagement(identifier: str) -> Engagement:
    """SET engagement_deleted_at = NULL WHERE engagement_identifier = ? AND
    engagement_deleted_at IS NOT NULL. Not-soft-deleted raises
    ValidationError(code='not_soft_deleted'). Returns post-restore row."""

def next_engagement_identifier() -> str:
    """Compute the next available ENG-NNN identifier. Reads MAX(engagement_identifier)
    against the meta DB; increments. Concurrent-insert safety: identifier conflict
    on INSERT retries up to 3 times with a fresh MAX read between attempts."""
```

All methods invoke the JSON-snapshot regeneration hook on write success (see Step 4).

### 2.1 Validation rules

Per `engagement.md` §3.5:

- `engagement_identifier` format: `^ENG-\d{3}$`. ValidationError if provided in POST body with wrong format.
- `engagement_code` format: `^[A-Z][A-Z0-9]{1,9}$` (mirrors v1's Client.code constraint exactly: 2-10 chars, starts with uppercase letter, remaining are uppercase letters or digits). Case-insensitive unique within meta DB (CHECK via `LOWER(engagement_code)` index or COLLATE NOCASE — match the slice A schema choice).
- `engagement_name`: non-empty (after strip), case-insensitive unique within meta DB.
- `engagement_purpose`: non-empty (after strip). No upper bound.
- `engagement_status`: must be one of the three enum values. Default `active` on create when omitted.
- `engagement_export_dir`: when provided, must be an absolute path AND the directory must exist AND be writable. Validated by calling `os.access(path, os.W_OK)` after `os.path.isdir(path)`. Null is valid.
- All timestamps: server-set; never accepted from request body. PUT body containing timestamp fields silently drops them.

### 2.2 Error envelope

ValidationError uses the existing v2 error envelope shape. The `errors` array entries each have `code` (string slug like `invalid_format`, `not_unique`, `invalid_enum_value`, `immutable_field`, `not_soft_deleted`, `directory_not_writable`), `field` (the field name when applicable), and `message` (human-readable). Multiple validation errors in one POST/PUT body produce multiple entries in the `errors` array.

## Step 3 — REST API surface

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/engagements.py`. Eight endpoints:

```python
router = APIRouter(prefix="/engagements", tags=["engagements"])

@router.get("")
async def list_engagements(
    include_deleted: bool = False,
    db = Depends(get_meta_db),
) -> dict:
    """Returns {data: [Engagement.to_dict(), ...], meta: {}, errors: []}.
    Default excludes soft-deleted."""

@router.get("/next-identifier")
async def next_identifier(db = Depends(get_meta_db)) -> dict:
    """Returns {data: {next: 'ENG-NNN'}, meta: {}, errors: []}."""

@router.get("/{identifier}")
async def get_engagement(identifier: str, db = Depends(get_meta_db)) -> dict:
    """Returns {data: Engagement.to_dict(), meta: {}, errors: []}.
    404 if not found."""

@router.post("")
async def create_engagement(body: dict, db = Depends(get_meta_db)) -> dict:
    """POST body matches Engagement fields except auto-set ones. Identifier
    omission triggers auto-assignment. Returns 201 with envelope."""

@router.put("/{identifier}")
async def update_engagement(identifier: str, body: dict, db = Depends(get_meta_db)) -> dict:
    """Full-replace PUT. Body identifier must match URL identifier (422 if mismatch
    via code='identifier_mismatch')."""

@router.patch("/{identifier}")
async def patch_engagement(identifier: str, body: dict, db = Depends(get_meta_db)) -> dict:
    """Partial-update PATCH."""

@router.delete("/{identifier}")
async def delete_engagement(identifier: str, db = Depends(get_meta_db)) -> dict:
    """Soft-delete; idempotent."""

@router.post("/{identifier}/restore")
async def restore_engagement(identifier: str, db = Depends(get_meta_db)) -> dict:
    """Restore from soft-delete. 422 if not soft-deleted."""
```

Replace slice A's `/engagements/healthcheck` stub with the full router. The healthcheck path doesn't need to persist — it was scaffolding.

All endpoints use the standard `envelope_response()` / `envelope_error()` helpers from the existing API code. Status codes:

- 200 OK: GET, PUT, PATCH, DELETE (soft-delete on already-deleted), POST `/restore` (successful)
- 201 Created: POST `/engagements` (successful)
- 404 Not Found: GET / PUT / PATCH / DELETE / POST `/restore` on non-existent identifier
- 422 Unprocessable Entity: validation errors (all the ValidationError raises from Step 2)

The `?include_deleted=true` query parameter on GET `/engagements` is the only documented query parameter. GET `/engagements/{identifier}` returns soft-deleted records as well (no parameter; the resource is identified directly).

Register the router in the FastAPI app initialization. The slice-A two-database wiring already has `get_meta_db` as the dependency function; the new router consumes it.

## Step 4 — JSON snapshot hook

Add (or extend, if a hook framework already exists from v0.4) a post-commit hook that regenerates `PRDs/product/crmbuilder-v2/db-export/meta/engagements.json` after any access-layer write to the engagements table.

The snapshot format mirrors the existing entity-export pattern: a JSON array of full records ordered consistently for git diffability (sort by `engagement_identifier` ascending). Each record contains all ten fields including soft-deleted timestamps; timestamps serialized as ISO 8601 UTC strings; nulls preserved.

The hook is invoked synchronously within the same transaction as the write — failure to regenerate is a transaction failure. Mirrors the v0.3+ pattern.

The directory `PRDs/product/crmbuilder-v2/db-export/meta/` is created if not present (the slice-A dogfood migration created it; defensive `mkdir(parents=True, exist_ok=True)`).

## Step 5 — Storage client extensions

Add eight methods to `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`:

```python
def list_engagements(self, *, include_deleted: bool = False) -> list[Engagement]:
    """GET /engagements; unwrap envelope; hydrate dataclasses; raise on
    non-200."""

def get_engagement(self, identifier: str) -> Engagement: ...
def create_engagement(self, *, code, name, purpose, status='active', export_dir=None,
                       identifier=None) -> Engagement: ...
def update_engagement(self, identifier: str, **fields) -> Engagement: ...
def patch_engagement(self, identifier: str, **fields) -> Engagement: ...
def delete_engagement(self, identifier: str) -> Engagement: ...
def restore_engagement(self, identifier: str) -> Engagement: ...
def next_engagement_identifier(self) -> str: ...
```

Each method handles the envelope unwrapping per the CLAUDE.md API envelope contract: `data` extracted, `errors` translated into typed exceptions (ValidationError with field/code/message; NotFoundError; ConflictError). Mirror the v0.4 client method pattern for the four methodology entity types.

## Step 6 — Tests

### 6.1 `tests/crmbuilder_v2/access/test_engagement.py`

Tests covering all repository methods. Per-method test groups:

- `list_engagements`: happy path with 0/1/many records; `include_deleted` flag toggles soft-deleted visibility; ordering by `engagement_last_opened_at DESC NULLS LAST` (verify null-last semantics).
- `get_engagement`: hit / miss; soft-deleted record is returned.
- `create_engagement`: happy path (with all fields); identifier auto-assignment (omitted identifier); default `active` status; null `engagement_export_dir`; validation errors for each rule in §3.5 (invalid identifier format, invalid code format including each constraint clause, lowercase code, code starting with digit, code too short, code too long, invalid status enum, non-existent export_dir, non-writable export_dir, missing required field, duplicate code (case-insensitive), duplicate name (case-insensitive)).
- `update_engagement`: happy path; identifier-mismatch in body raises; `engagement_code` immutable raises; full-replace semantics (omitted fields reset to defaults — actually no, full-replace requires all fields per PUT semantics; if a field is omitted, raise validation error).
- `patch_engagement`: partial-update; each status transition (active→paused, active→archived, paused→active, paused→archived, archived→active, archived→paused — all six valid); invalid enum value raises; code-immutability raises.
- `delete_engagement`: happy path; idempotency (delete on already-deleted returns unchanged record).
- `restore_engagement`: happy path; restore on not-soft-deleted raises.
- `next_engagement_identifier`: returns ENG-001 against empty table; returns ENG-002 after ENG-001 exists; returns ENG-NNN+1 against any existing MAX; handles concurrent inserts (simulate by manually creating ENG-001, calling next_engagement_identifier, then before the INSERT runs creating ENG-002 in another transaction, then attempting the INSERT — the retry should pick up ENG-003).

### 6.2 `tests/crmbuilder_v2/api/test_engagements_api.py`

Tests covering all endpoints:

- GET `/engagements`: 200; envelope shape; data array; include_deleted flag.
- GET `/engagements/next-identifier`: 200; data.next is a valid ENG-NNN string.
- GET `/engagements/{id}`: 200; 404 envelope on miss with errors array.
- POST `/engagements`: 201; identifier auto-assignment on omission; 422 envelope with errors array for each validation rule; 422 with `code: 'not_unique'` and `field: 'engagement_code'` for duplicate code.
- PUT `/engagements/{id}`: 200; 404 on miss; 422 on body-identifier-mismatch with `code: 'identifier_mismatch'`; 422 on code-mutation attempt with `code: 'immutable_field'`.
- PATCH `/engagements/{id}`: 200; partial update; 422 on invalid status enum.
- DELETE `/engagements/{id}`: 200; envelope shows engagement_deleted_at set; idempotent re-delete.
- POST `/engagements/{id}/restore`: 200; 422 on not-soft-deleted with `code: 'not_soft_deleted'`.

Every test asserts the envelope shape (`{data, meta, errors}`) per the CLAUDE.md API envelope contract.

### 6.3 JSON snapshot tests

Inside or alongside the above modules, verify that each successful write regenerates `db-export/meta/engagements.json` with the expected content and ordering. Tests can use a temp directory for the export path (configurable via a test-only fixture that overrides the export-path constant).

## Acceptance verification

Before committing:

1. **All slice B tests pass.** `uv run pytest tests/crmbuilder_v2/access/test_engagement.py tests/crmbuilder_v2/api/test_engagements_api.py -v` — green.
2. **Full v0.5 suite passes.** `uv run pytest tests/crmbuilder_v2/ -v` — no failures.
3. **CRMBUILDER row is accessible via the API.** `curl -sf http://127.0.0.1:8765/engagements/ENG-001 | python3 -m json.tool` returns the CRMBUILDER record in the standard envelope shape.
4. **POST round-trips.** `curl -X POST http://127.0.0.1:8765/engagements -H 'Content-Type: application/json' -d '{"engagement_code":"TESTENG","engagement_name":"Test Engagement","engagement_purpose":"Verification only"}'` returns 201 with envelope; the response data contains an auto-assigned `engagement_identifier` of `ENG-002`. Follow up with DELETE to clean up.
5. **JSON snapshot regenerates.** After the POST in step 4 (or the cleanup DELETE), `PRDs/product/crmbuilder-v2/db-export/meta/engagements.json` reflects the post-write state.
6. **Validation correctness sanity.** `curl -X POST http://127.0.0.1:8765/engagements -H 'Content-Type: application/json' -d '{"engagement_code":"bad","engagement_name":"x","engagement_purpose":"y"}'` returns 422 with envelope.errors containing entries for code format violation (lowercase + too short).

If any verification step fails, stop and report.

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/access/engagement.py \
        crmbuilder-v2/src/crmbuilder_v2/access/engagement_models.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/engagements.py \
        crmbuilder-v2/src/crmbuilder_v2/api/ \
        crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
        tests/crmbuilder_v2/access/test_engagement.py \
        tests/crmbuilder_v2/api/test_engagements_api.py
git commit -m "v2: v0.5 slice B — engagement schema, access layer, REST API (eight standard endpoints, validation, JSON snapshot hook)"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT add any UI surface (panel, dialog, widget, top-strip — all in slices C and D).
- Do NOT add switching mechanism or activation worker (slice D).
- Do NOT bump `__version__` (slice E).
- Do NOT modify the meta DB schema (frozen at slice A's `0001_create_engagements_table.py`; slice B builds on the schema, doesn't change it).
- Do NOT modify the activation sequence or attempt to PATCH `engagement_last_opened_at` via the API in any flow (slice D wires this in).
- Do NOT remove the `/engagements/healthcheck` endpoint until the full router is in place and the full test suite passes; replace it cleanly within Step 3.
- Do NOT write any session, decision, or planning records to the database (those land at v0.5 build closeout).
- Do NOT modify v0.4 entity behavior. The existing methodology entity types (domain, entity, process, crm_candidate) and governance entity types (sessions, decisions, etc.) are unchanged by slice B.

---

*End of prompt.*
