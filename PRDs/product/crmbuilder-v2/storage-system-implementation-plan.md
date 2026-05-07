# CRMBuilder v2 — Storage System v0.1 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-07-26
**Status:** Approved for execution
**Companion PRD:** `storage-system-PRD-v0.1.md`
**Executing prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-B-storage-system.md`

---

## 1. Overview

This plan implements the v0.1 storage system specified in
`storage-system-PRD-v0.1.md`. The build is single-pass with incremental
commits, each commit landing a coherent slice of the system. No staged
release boundary is needed because the PRD's acceptance criteria define
a single "functioning" gate, and a partial system has no operational
value (the access layer alone does not retire the markdown files; the
markdown files are only retired after migration runs end-to-end).

The order below is dictated by dependency: schema must exist before the
access layer; the access layer must exist before the API; the API
must exist before the MCP server; everything must exist before the
bootstrap migration can run.

---

## 2. Implementation Choices

### 2.1 Language and runtime

- **Python 3.12+** (matches the existing repository's `requires-python`
  pin in `pyproject.toml`). No need to introduce a separate Python
  version constraint.

### 2.2 ORM / query layer — SQLAlchemy 2.0

SQLAlchemy 2.0's typed Declarative API is the query layer. Rationale:

- **Schema growth is imminent.** v0.1 covers project-management
  entities, but Step 0 follow-on adds methodology entities (personas,
  fields, processes, requirements, etc.). Raw SQL with a thin wrapper
  becomes painful at that scale.
- **Validation hooks are clean.** Column types, CHECK constraints, and
  `validates()` decorators give us a single declarative surface for
  controlled-vocabulary enforcement.
- **Pairs with Alembic for migrations** (see 2.3).
- **Transaction model is explicit.** `Session.begin()` blocks make the
  transactional JSON-export hook (PRD section 6.3) straightforward.

Alternative considered: raw `sqlite3` plus a hand-rolled repository
layer. Rejected — short-term simpler but accumulates ad-hoc code as the
schema grows.

### 2.3 Migration tool — Alembic

Standard companion to SQLAlchemy. Per PRD section 9 (Open Questions),
the choice should be deliberate and documented during the v0.1 build.
Alembic is the lowest-friction option for a SQLAlchemy-based project:
auto-generation of migrations from model diffs, plus support for
hand-written migrations when needed (e.g., data backfills).

The v0.1 build commits one baseline migration (`0001_initial_schema`).
Future schema work generates new migration files; the access layer
applies pending migrations on startup.

### 2.4 Web framework — FastAPI

Specified by DEC-005 and PRD section 6.1. Pydantic v2 (FastAPI's
dependency) handles request/response validation at the HTTP edge;
business validation lives in the access layer per PRD section 6.2.

### 2.5 MCP framework — official `mcp` Python SDK

The Anthropic-maintained `mcp` package
(`pip install mcp`). It is the canonical implementation, supports
stdio transport for local development (PRD section 4.4), and supports
HTTP transport for hosted deployment when that decision is made.

### 2.6 HTTP client (MCP → REST) — httpx

Async-capable, used by FastAPI's own `TestClient`. Lets us reuse the
same client patterns in MCP and tests.

### 2.7 Test framework — pytest

Already a project dependency. We add `pytest-asyncio` for async-aware
tests (FastAPI TestClient sync paths cover most cases; async needed
only for MCP-side tests).

### 2.8 JSON export design

- **Layout:** one JSON file per entity type plus one for `references`
  and one for `change_log`. All files live under
  `PRDs/product/crmbuilder-v2/db-export/`.
- **Format:** `json.dumps(data, sort_keys=True, indent=2,
  ensure_ascii=False)` — stable key ordering, predictable diffs.
- **Atomicity:** write to a sibling tempfile via `tempfile.NamedTemporaryFile`
  in the same directory, `os.replace()` into final location.
- **Transaction integration:** export runs inside the SQLAlchemy
  `Session.begin()` block; if the export raises, the SQLAlchemy
  transaction rolls back. After commit, the tempfile rename is
  unconditional (rename is itself atomic on POSIX).
- **Scope:** export rewrites all entity files on every write. v0.1
  data volume is small (low hundreds of records at most), so a full
  rewrite is acceptable. Optimisation deferred until necessary.

### 2.9 Configuration

Environment variables with defaults, parsed by a Pydantic Settings
class:

| Variable | Default | Description |
|---|---|---|
| `CRMBUILDER_V2_DB_PATH` | `<repo>/crmbuilder-v2/data/v2.db` | SQLite file path |
| `CRMBUILDER_V2_EXPORT_DIR` | `<repo>/PRDs/product/crmbuilder-v2/db-export/` | JSON export directory |
| `CRMBUILDER_V2_API_HOST` | `127.0.0.1` | REST API host |
| `CRMBUILDER_V2_API_PORT` | `8765` | REST API port |
| `CRMBUILDER_V2_API_BASE_URL` | `http://127.0.0.1:8765` | URL the MCP server uses to reach the API |

The `<repo>` placeholder is resolved at runtime to the directory
containing `pyproject.toml`. The defaults make `crmbuilder-v2-api`
and `crmbuilder-v2-mcp` runnable from a fresh checkout with no
configuration.

---

## 3. Repository Layout

All v2 code lives under a new `crmbuilder-v2/` directory at the repo
root, separate from `espo_impl/` and `automation/` per DEC-003. The
package is added to `[tool.hatch.build.targets.wheel]` and to
`[project.scripts]` so the v2 entry points are installable.

```
crmbuilder-v2/
├── alembic.ini
├── data/                                  # gitignored: runtime SQLite file
│   └── .gitkeep
├── migrations/                            # Alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
└── src/
    └── crmbuilder_v2/
        ├── __init__.py
        ├── config.py                       # Pydantic Settings
        ├── access/
        │   ├── __init__.py
        │   ├── db.py                       # engine + session factory
        │   ├── models.py                   # SQLAlchemy ORM
        │   ├── vocab.py                    # controlled vocabularies
        │   ├── exceptions.py               # ValidationError, NotFound, etc.
        │   ├── change_log.py               # change_log emission
        │   ├── exporter.py                 # JSON export hook
        │   └── repositories/
        │       ├── __init__.py
        │       ├── charter.py
        │       ├── status.py
        │       ├── decisions.py
        │       ├── sessions.py
        │       ├── risks.py
        │       ├── planning_items.py
        │       ├── topics.py
        │       └── references.py
        ├── api/
        │   ├── __init__.py
        │   ├── main.py                     # FastAPI app factory
        │   ├── deps.py                     # session dependency
        │   ├── envelope.py                 # response wrapper helpers
        │   ├── schemas.py                  # Pydantic v2 request/response models
        │   ├── errors.py                   # exception → HTTP mapping
        │   └── routers/
        │       ├── __init__.py
        │       ├── charter.py
        │       ├── status.py
        │       ├── decisions.py
        │       ├── sessions.py
        │       ├── risks.py
        │       ├── planning_items.py
        │       ├── topics.py
        │       ├── references.py
        │       └── orientation.py
        ├── mcp_server/
        │   ├── __init__.py
        │   ├── server.py                   # stdio entry point
        │   └── tools.py                    # tool definitions
        ├── bootstrap/
        │   ├── __init__.py
        │   ├── parsers/
        │   │   ├── __init__.py
        │   │   ├── charter.py
        │   │   ├── decisions.py
        │   │   ├── sessions.py
        │   │   └── status.py
        │   └── migrate.py                  # CLI entry point
        └── cli.py                          # crmbuilder-v2-api / crmbuilder-v2-mcp / crmbuilder-v2-bootstrap

tests/
└── crmbuilder_v2/
    ├── conftest.py                         # tmp DB / tmp export dir fixtures
    ├── access/
    │   ├── test_charter.py
    │   ├── test_status.py
    │   ├── test_decisions.py
    │   ├── test_sessions.py
    │   ├── test_risks.py
    │   ├── test_planning_items.py
    │   ├── test_topics.py
    │   ├── test_references.py
    │   ├── test_change_log.py
    │   └── test_exporter.py
    ├── api/
    │   ├── test_charter.py
    │   ├── test_status.py
    │   ├── test_decisions.py
    │   ├── test_sessions.py
    │   ├── test_risks.py
    │   ├── test_planning_items.py
    │   ├── test_topics.py
    │   ├── test_references.py
    │   └── test_orientation.py
    ├── mcp_server/
    │   └── test_smoke.py
    └── bootstrap/
        ├── test_parsers.py
        └── test_migrate.py
```

PRD documents (the PRD itself, this plan, and any companion artifacts)
remain in `PRDs/product/crmbuilder-v2/`, per PRD section 6.5.

The JSON export directory is at `PRDs/product/crmbuilder-v2/db-export/`,
per PRD section 4.5 (proposed location adopted as final). Files there
are git-tracked. The runtime SQLite file at `crmbuilder-v2/data/v2.db`
is gitignored.

---

## 4. Build Sequence

Each numbered step lands as one or more `v2:`-prefixed commits.
Acceptance criteria from PRD section 8 are cross-referenced.

### Step 1 — Plan + status update (this commit)

Plan committed. Status updated to reflect v0.1 build in progress.

### Step 2 — Package scaffold

- Create `crmbuilder-v2/` directory tree (empty package files,
  `data/.gitkeep`, `db-export/.gitkeep`).
- Add `crmbuilder-v2` package to root `pyproject.toml` (dependencies,
  build target, scripts).
- Add `crmbuilder-v2/data/v2.db*` to `.gitignore`.
- Run `uv sync` to lock new dependencies.

Exit: `uv run python -c "import crmbuilder_v2"` succeeds.

### Step 3 — Schema (acceptance criterion #1)

- SQLAlchemy ORM models for charter, status, decisions, sessions,
  risks, planning_items, topics, references, change_log.
- Indexes: `(source_type, source_id)` and `(target_type, target_id)`
  on references; identifier UNIQUE indexes on each entity table.
- CHECK constraints encoding controlled vocabularies (status enums,
  operation enums, etc.) — belt-and-braces in addition to access-layer
  validation, since SQLite enforces CHECK at the database boundary.
- Alembic baseline migration `0001_initial_schema`.
- `crmbuilder-v2-bootstrap-db` CLI command applies migrations to the
  configured DB path.

Exit: applying the migration on a fresh DB produces all tables; tables
inspectable via `sqlite3 .schema`.

### Step 4 — Access layer (acceptance criterion #2)

- Session factory using SQLAlchemy 2.0's typed Session.
- Per-entity repositories with CRUD methods.
- `vocab.py` exporting frozen sets of allowed values.
- `validators.py` (or equivalent decorator-based hooks on models)
  rejecting controlled-vocab violations at write time.
- `change_log.py` emitting one entry per mutating call (insert,
  update, delete) with operation type, entity type, identifier,
  timestamp, actor, and a JSON before/after diff.
- `exporter.py` rewriting all JSON export files inside the same
  transaction as the database write, atomic via tempfile + rename.
- `exceptions.py` defining structured errors:
  `ValidationError(field, code, message)`, `NotFoundError`,
  `ConflictError` (e.g., identifier already exists), wrapped with
  enough metadata for the API layer to translate to HTTP status.

The access layer's public API is package-level functions (e.g.,
`crmbuilder_v2.access.decisions.create(...)`) so scripts and tests
can use it without instantiating an HTTP client.

Sessions repository **disallows updates**, enforcing the append-only
rule from DEC-013. Create, read, list, delete only. (Delete is
permitted — append-only refers to historical content, and a record
written by mistake should be removable. Deletion lands in change_log.)

Charter and Status repositories handle versioning: every write
inserts a new row with the next version number; the latest is
identified by an `is_current` flag. Read returns the current row by
default; query parameter selects a historical version.

Decisions repository allows updates (notably for status:
Active → Superseded), with full before/after diff in change_log.
The `supersedes` and `superseded_by` columns are foreign keys to
other decision rows; cycles are rejected.

Exit: pytest unit tests in `tests/crmbuilder_v2/access/` pass.

### Step 5 — REST API (acceptance criterion #3)

- FastAPI app factory with one router per entity plus an
  `orientation` router for DEC-011 reads.
- Pydantic v2 schemas for request and response bodies. Response
  envelope: `{"data": <body>, "meta": {<count, version, etc.>},
  "errors": null}` for success; `{"data": null, "meta": {},
  "errors": [{"code", "field", "message"}, ...]}` for failure.
- HTTP status mapping: 200/201 for success; 400 for validation
  errors; 404 for not found; 409 for conflict; 500 for unexpected.
- OpenAPI auto-generated at `/openapi.json`; Swagger UI at `/docs`.
- Endpoints summarised in the table below.

| Method | Path | Purpose |
|---|---|---|
| GET | `/charter` | Current charter |
| GET | `/charter/versions/{version}` | Specific historical version |
| PUT | `/charter` | Replace charter (creates new version) |
| GET | `/status` | Current status |
| GET | `/status/versions/{version}` | Specific historical version |
| PUT | `/status` | Replace status (creates new version) |
| GET | `/decisions` | List decisions |
| GET | `/decisions/{id}` | One decision (e.g., DEC-007) |
| POST | `/decisions` | Create |
| PATCH | `/decisions/{id}` | Update (e.g., supersede) |
| DELETE | `/decisions/{id}` | Delete |
| GET | `/sessions` | List, with `?limit=N` for orientation |
| GET | `/sessions/{id}` | One session |
| POST | `/sessions` | Create (no PATCH; append-only) |
| DELETE | `/sessions/{id}` | Delete |
| GET / POST / PATCH / DELETE | `/risks[/{id}]` | Risks CRUD |
| GET / POST / PATCH / DELETE | `/planning-items[/{id}]` | Planning items CRUD |
| GET / POST / PATCH / DELETE | `/topics[/{id}]` | Topics CRUD |
| GET / POST / DELETE | `/references` | References CRUD (no update — delete + recreate) |
| GET | `/orientation/recent-sessions?limit=N` | Last N sessions |
| GET | `/orientation/decisions-for-session/{id}` | Decisions referenced by session |
| GET | `/references/from/{type}/{id}` | All refs where entity is source |
| GET | `/references/to/{type}/{id}` | All refs where entity is target |
| GET | `/references/touching/{type}/{id}` | Both directions |

Exit: pytest integration tests in `tests/crmbuilder_v2/api/` pass.
OpenAPI document loads at `/openapi.json`.

### Step 6 — MCP server (acceptance criterion #4)

- `crmbuilder_v2.mcp_server.server` boots the official MCP SDK
  with stdio transport.
- Tool definitions wrap REST API endpoints. One tool per logical
  read/write, named with verbs Claude can match from natural-language
  prompts (e.g., `get_current_charter`, `get_current_status`,
  `list_recent_sessions`, `get_decision`, `list_decisions_for_session`,
  `create_decision`, `create_session`, `add_reference`,
  `list_references_from`, `list_references_to`,
  `list_references_touching`, etc.).
- The MCP server holds a single `httpx.AsyncClient` against
  `CRMBUILDER_V2_API_BASE_URL` and translates each tool call into
  the corresponding HTTP request.
- No business logic, validation, or direct database access — pure
  protocol translation, per PRD section 4.4.

Exit: `crmbuilder-v2-mcp` runs over stdio. Smoke test in
`tests/crmbuilder_v2/mcp_server/test_smoke.py` confirms each tool
invokes the expected REST endpoint (mocked transport).

### Step 7 — Bootstrap migration (acceptance criteria #5, #6, #8)

- Per-file parsers in `bootstrap/parsers/` extract the structured
  content from each markdown file:
  - `charter.md` → singleton charter row, with section bodies in
    a JSON column; the markdown's change-log table seeds the
    charter's version history (one historical version row per
    change-log entry, plus the current version).
  - `decisions.md` → eleven decision rows (DEC-001..DEC-011).
  - `sessions.md` → one session row (SES-001).
  - `status.md` → singleton status row.
- `bootstrap/migrate.py` orchestrates: open access-layer session,
  parse each file, upsert each record by identifier (UPDATE if
  exists, INSERT otherwise — idempotency requirement from PRD
  section 4.6), create the implicit cross-references
  (SES-001 `decided_in` DEC-001..DEC-011), commit transaction.
- `crmbuilder-v2-bootstrap` CLI entry point invokes the migration.
- Migration test (`tests/crmbuilder_v2/bootstrap/test_migrate.py`):
  parses fixture markdown copies, asserts post-migration database
  state matches expected fields, asserts running migration twice
  produces identical state, asserts orientation queries (Tier 2
  reads) return content equivalent to the source markdown.

Exit: migration passes its tests on fixtures.

### Step 8 — Run migration on real bootstrap files

- Execute `crmbuilder-v2-bootstrap` against the actual files in
  `PRDs/product/crmbuilder-v2/`.
- Verify acceptance criterion #8 manually (`curl /charter`,
  `curl /orientation/recent-sessions?limit=1`, etc.).
- Delete the four source markdown files in the same commit that
  lands the populated `db-export/` JSON snapshots.
- Update `CLAUDE.md` to describe the post-migration orientation
  protocol: MCP queries are primary; the JSON export directory is
  the file-based fallback for sessions where the MCP server is
  not connected. Remove references to the deleted markdown files.

Exit: acceptance criterion #6 (markdown removed, content in DB,
git history shows the migration commit).

### Step 9 — Close out (PRD doesn't explicitly require this but the prompt does)

- Append SES-002 ("v0.1 Storage System Build") via the API/MCP
  (database-resident; the markdown sessions log is gone).
- Update database-resident status: phase → "Build (v0.1 complete)",
  pending lists trimmed accordingly.
- Add any new DEC-NNN records for architectural decisions made
  during execution that warrant capture.
- Push to `origin/main`.

---

## 5. Acceptance Criteria Mapping

| PRD #8 criterion | Step | Verification |
|---|---|---|
| 1. Schema deployed | Step 3 | `sqlite3 .schema` shows all tables and indexes |
| 2. Access layer operational | Step 4 | Access-layer test suite passes |
| 3. REST API operational | Step 5 | API integration test suite passes; `/openapi.json` loads |
| 4. MCP server operational | Step 6 | MCP smoke test passes; manual stdio invocation returns tool list |
| 5. JSON exports generated | Step 4 / Step 8 | After any write, `db-export/` updates atomically; diffs match |
| 6. Bootstrap content migrated | Steps 7–8 | Migration commit shows markdown deletion + populated DB exports |
| 7. Test suite passing | All steps | `uv run pytest tests/crmbuilder_v2/` exits 0 |
| 8. Session orientation works | Step 8 | `curl` and MCP tool calls return content equivalent to pre-migration markdown |

---

## 6. Open Questions

These are surfaced for visibility; none are blockers for execution
because each has an acceptable default that I will use unless Doug
indicates otherwise.

1. **Charter and status section structure: JSON column or separate
   columns?** Defaulting to a single JSON column per record (the
   PRD permits either). Reason: charter sections evolve (Open
   Planning Items will shrink as planning dimensions resolve, and
   the methodology entity sections will be added later). Avoiding a
   column-per-section schema lock-in costs nothing in v0.1 because
   queries don't currently filter by section content.

2. **Sessions append-only enforcement.** DEC-013 says "Session
   records are append-only — once written, they are not edited."
   The API exposes POST and DELETE only — no PATCH. Edits to
   in-flight sessions are not supported; a session record is
   written once, in its final form, when the conversation closes.
   Confirming this is the intended behaviour.

3. **MCP server transport for development.** Defaulting to stdio
   (matches the PRD's section 4.4 minimum). HTTP transport is
   stubbed via SDK config but not exercised in v0.1.

4. **Test coverage of Alembic migration.** Defaulting to "schema
   matches model definitions after migration runs"; no test of
   downgrade paths because v0.1 has no prior migration to downgrade
   to. Future migrations should test downgrade.

5. **CLAUDE.md update scope.** The current `CLAUDE.md` v2 routing
   section directs sessions to read four markdown files in Tier 2.
   Once those are deleted, the section needs to point at MCP tools
   (primary) and the JSON exports under `db-export/` (file-based
   fallback when MCP is not connected). Defaulting to: rewrite
   the section in the migration commit.

If any of these defaults is wrong, surface before the corresponding
step lands.

---

## 7. Milestones

The phase boundaries below are review checkpoints. Per DEC-016,
"done" means Doug has reviewed and judged sufficient to proceed.

| Milestone | After step | What's reviewable |
|---|---|---|
| Plan landed | 1 | This document |
| Scaffold up | 2 | Importable empty package + lockfile |
| Schema deployed | 3 | DB file, `.schema` output |
| Access layer green | 4 | Test suite output |
| REST API green | 5 | Test suite output, `/openapi.json` |
| MCP server green | 6 | Smoke test output |
| Migration tested | 7 | Migration test output on fixtures |
| Migration applied | 8 | Real DB populated, markdown deleted, JSON exports git-tracked |
| v0.1 closed out | 9 | SES-002 record, status update, push |

If anything below the "Migration applied" milestone fails review,
the iteration happens within the corresponding step. If "Migration
applied" fails review, it's a roll-forward — the migration is
fixed and re-run; the rollback path is the SQLite file backup
captured before migration runs.

---

## 8. Constraints (restated from prompt)

- No edits to v1 code (`espo_impl/`, `automation/`).
- No edits to v1 PRDs or methodology guides under `PRDs/process/`.
- No edits to CBM repository content.
- No new external service dependencies; everything runs locally.
- Stop and ask if uncertainty arises that the PRD and v2
  governance docs cannot resolve.
