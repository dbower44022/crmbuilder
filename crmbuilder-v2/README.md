# CRMBuilder v2 — Storage System

The structured-database source of truth for CRMBuilder v2 governance and
methodology artifacts. This README covers setup, day-to-day operation,
and maintenance. The architectural rationale lives in the PRDs and
decisions records (see [Reference](#reference)).

---

## Table of contents

- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Setup](#setup)
- [Operation](#operation)
- [REST API surface](#rest-api-surface)
- [MCP tools](#mcp-tools)
- [User interface](#user-interface)
- [Maintenance](#maintenance)
- [Development](#development)
- [Reference](#reference)

---

## Architecture

Four-layer stack, plus a JSON-export side channel:

```
┌──────────────────────────────────────────────┐
│  Claude.ai / Claude Desktop / Claude Code   │
└────────────────────┬─────────────────────────┘
                     │ MCP tool calls (stdio)
┌────────────────────▼─────────────────────────┐
│  MCP Server (crmbuilder_v2.mcp_server)       │
│  Stateless adapter; ~40 tools                │
└────────────────────┬─────────────────────────┘
                     │ HTTP (httpx.AsyncClient)
┌────────────────────▼─────────────────────────┐
│  REST API (crmbuilder_v2.api)                │
│  FastAPI + Pydantic v2; envelope responses   │
└────────────────────┬─────────────────────────┘
                     │ Python function calls
┌────────────────────▼─────────────────────────┐
│  Access layer (crmbuilder_v2.access)         │
│  Repositories, validation, transactions,     │
│  change_log emission, JSON export hook       │
└────────────────────┬─────────────────────────┘
                     │ SQLAlchemy 2.0 / SQL
┌────────────────────▼─────────────────────────┐
│  SQLite database — crmbuilder-v2/data/v2.db  │
└──────────────────────────────────────────────┘
                     │
                     │ on every successful write
┌────────────────────▼─────────────────────────┐
│  JSON snapshots — git-tracked, atomic        │
│  PRDs/product/crmbuilder-v2/db-export/       │
└──────────────────────────────────────────────┘
```

**Layer responsibilities:**

| Layer | Module | Responsibility |
|---|---|---|
| SQLite | (file on disk) | Storage; ACID transactions |
| Access layer | `crmbuilder_v2.access` | Validation, transactions, change_log emission, JSON export hook. The only code that touches SQLAlchemy directly. |
| REST API | `crmbuilder_v2.api` | Stable client interface. Pydantic request validation; envelope responses; OpenAPI auto-generated. |
| MCP server | `crmbuilder_v2.mcp_server` | Thin protocol adapter from MCP tool calls to REST. No business logic. |
| JSON export | `crmbuilder_v2.access.exporter` | Per-write atomic snapshot of all entity tables to `db-export/`. |

The reason for the layering is in [DEC-005](#reference) — REST API is the durable productization-path interface; MCP is swappable; access layer is reusable from scripts, tests, and the existing PySide6 app without HTTP.

---

## Quick start

From a fresh checkout:

```bash
# Install dependencies (adds sqlalchemy, alembic, fastapi, uvicorn,
# pydantic-settings, httpx, mcp on top of v1's deps).
uv sync

# Run the test suite (96 tests should pass).
uv run pytest tests/crmbuilder_v2/

# Start the REST API on http://127.0.0.1:8765.
uv run crmbuilder-v2-api

# In another terminal, point an MCP client at the stdio server.
uv run crmbuilder-v2-mcp
```

The database is already populated with v0.1 governance content (16
decisions, 3 sessions, 4 charter versions, 4 status versions, 17
references) via the bootstrap migration. The git-tracked JSON
snapshots in `PRDs/product/crmbuilder-v2/db-export/` mirror that state.

---

## Setup

### Requirements

- Python 3.12+ (matches the root `pyproject.toml` pin)
- `uv` for dependency resolution
- Optional: a SQLite browser (`sqlitebrowser`, DB Browser for SQLite,
  `sqlite3` CLI, or VS Code's SQLite extension) for ad-hoc inspection

### Console scripts

`pyproject.toml` registers four entry points:

| Command | Function | Purpose |
|---|---|---|
| `crmbuilder-v2-api` | `crmbuilder_v2.cli:run_api` | Start FastAPI under uvicorn |
| `crmbuilder-v2-mcp` | `crmbuilder_v2.cli:run_mcp` | Start the MCP stdio server |
| `crmbuilder-v2-bootstrap-db` | `crmbuilder_v2.cli:bootstrap_db` | Materialise the schema on a fresh DB file |
| `crmbuilder-v2-bootstrap` | `crmbuilder_v2.cli:bootstrap_content` | Import the four governance markdown files (only useful if they exist on disk; the live system retired them at commit `12b96bc`) |

### Configuration

All settings come from environment variables with sensible defaults
rooted at the repo. Defaults are live in
`crmbuilder-v2/src/crmbuilder_v2/config.py`:

| Env var | Default | Purpose |
|---|---|---|
| `CRMBUILDER_V2_DB_PATH` | `<repo>/crmbuilder-v2/data/v2.db` | SQLite file |
| `CRMBUILDER_V2_EXPORT_DIR` | `<repo>/PRDs/product/crmbuilder-v2/db-export/` | JSON snapshot directory |
| `CRMBUILDER_V2_API_HOST` | `127.0.0.1` | REST API bind host |
| `CRMBUILDER_V2_API_PORT` | `8765` | REST API port |
| `CRMBUILDER_V2_API_BASE_URL` | `http://127.0.0.1:8765` | URL the MCP server uses to reach the API |

A `.env` file is **not** loaded automatically — set vars in your
shell or invocation if you need to override defaults.

### Initial database bootstrap

The repo ships with the JSON snapshots of the v0.1 state, but the
SQLite file itself is gitignored (`*.db` in the root `.gitignore`).
Materialise it from a fresh checkout with:

```bash
uv run crmbuilder-v2-bootstrap-db
```

This calls `Base.metadata.create_all` on the configured DB path. The
schema is identical to what the Alembic baseline (`0001_initial_schema`)
produces, so subsequent Alembic migrations apply normally.

To reproduce the live state, see [Restoring from JSON snapshots](#restoring-from-json-snapshots).

### Wiring Claude Desktop / Claude Code

Add an MCP server entry pointing at `crmbuilder-v2-mcp`. Example for
Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "crmbuilder-v2": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/home/doug/Dropbox/Projects/crmbuilder",
        "crmbuilder-v2-mcp"
      ]
    }
  }
}
```

The MCP server requires the REST API to be running — start
`crmbuilder-v2-api` in a separate terminal (or as a service) first.
Connection is `http://127.0.0.1:8765` by default.

---

## Operation

### Common workflows

#### Reading current state (Tier 2 orientation per DEC-011)

Through MCP (most natural during a Claude session):

- `get_current_charter()`
- `get_current_status()`
- `list_recent_sessions(limit=3)`
- `get_decision("DEC-007")` — for a specific record
- `list_decisions_for_session("SES-002")` — decisions a session covered

Through HTTP:

```bash
curl -s http://127.0.0.1:8765/charter | jq .
curl -s http://127.0.0.1:8765/status | jq .
curl -s "http://127.0.0.1:8765/orientation/recent-sessions?limit=3" | jq .
curl -s http://127.0.0.1:8765/decisions/DEC-007 | jq .
curl -s http://127.0.0.1:8765/orientation/decisions-for-session/SES-002 | jq .
```

Through the JSON snapshots (no server needed — read static files):

```bash
jq . PRDs/product/crmbuilder-v2/db-export/decisions.json
jq '.[] | select(.is_current == true)' PRDs/product/crmbuilder-v2/db-export/charter.json
```

The snapshots reflect the database state as of the most recent successful
write. Use them as a fallback when MCP isn't connected, for git diffs,
or for read-only inspection without booting the API.

#### Recording a new decision

```bash
curl -s -X POST http://127.0.0.1:8765/decisions \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "DEC-018",
    "title": "Short title",
    "decision_date": "05-08-26",
    "status": "Active",
    "context": "...",
    "decision": "...",
    "rationale": "...",
    "alternatives_considered": "...",
    "consequences": "..."
  }'
```

Or via MCP (in a Claude session):
> "Add a decision DEC-018 titled 'X', dated 05-08-26, status Active.
> Context is ... Rationale is ..."

After the call, `db-export/decisions.json` and `db-export/change_log.json`
are updated atomically. Commit those alongside any other artifacts.

#### Recording a new session (append-only)

```bash
curl -s -X POST http://127.0.0.1:8765/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "SES-004",
    "title": "Some working session",
    "session_date": "05-08-26",
    "status": "Complete",
    "topics_covered": "...",
    "summary": "...",
    "in_flight_at_end": "..."
  }'
```

Sessions are append-only per DEC-013 — there is no PATCH endpoint and
no `update()` repository method. If you need to correct a session
record that was written incorrectly, delete it and re-create it.

#### Linking a session to its decisions

After creating SES-004 and DEC-018, materialise the implicit
"decided in" reference:

```bash
curl -s -X POST http://127.0.0.1:8765/references \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "session",
    "source_id": "SES-004",
    "target_type": "decision",
    "target_id": "DEC-018",
    "relationship": "decided_in"
  }'
```

The bootstrap migration did this automatically by parsing each
session's `Decisions made:` field. Going forward, references are
created explicitly through the API or MCP.

The reference vocabulary (per DEC-006) is `is_about`, `supersedes`,
`decided_in`, `affects`, `covers`, `blocks`, `references`. New values
require a deliberate edit to
`crmbuilder_v2/access/vocab.py:REFERENCE_RELATIONSHIPS` plus an Alembic
migration that updates the CHECK constraint on the `refs` table.

#### Updating charter or status

Both are versioned: every PUT creates a new version row and demotes
the previous current row. Reads return the latest version unless a
specific version is requested.

```bash
curl -s -X PUT http://127.0.0.1:8765/charter \
  -H "Content-Type: application/json" \
  -d '{"payload": { ... full charter payload ... }}'
```

Read a specific historical version:

```bash
curl -s http://127.0.0.1:8765/charter/versions/2 | jq .
```

#### Superseding a decision

```bash
# Create the superseding decision first.
curl -s -X POST .../decisions -d '{"identifier": "DEC-020", ...}'

# Mark the old one Superseded and link the chain.
curl -s -X PATCH http://127.0.0.1:8765/decisions/DEC-005 \
  -H "Content-Type: application/json" \
  -d '{"status": "Superseded", "superseded_by": "DEC-020"}'

curl -s -X PATCH http://127.0.0.1:8765/decisions/DEC-020 \
  -H "Content-Type: application/json" \
  -d '{"supersedes": "DEC-005"}'
```

The change_log captures the full before/after diff of every update.

### Working from Python (no HTTP)

The access layer is importable. Useful for scripts, migrations, and
the future PySide6 app integration:

```python
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import decisions, sessions, references

with session_scope() as s:
    decisions.create(
        s,
        identifier="DEC-018",
        title="Short title",
        decision_date="05-08-26",
        status="Active",
    )
    sessions.create(
        s,
        identifier="SES-004",
        title="Working session",
        session_date="05-08-26",
        status="Complete",
    )
    references.create(
        s,
        source_type="session",
        source_id="SES-004",
        target_type="decision",
        target_id="DEC-018",
        relationship="decided_in",
    )
```

`session_scope()` opens a transaction, commits on success, and runs
the JSON export hook atomically. Pass `export=False` for read-only
work that should skip the export rewrite.

### Attribution in the change log

The `change_log` table stores every mutation with an `actor` field
chosen from `{claude_session, migration, manual}`. Default is
`claude_session`. Override for scripts or one-shot ops:

```python
from crmbuilder_v2.access.change_log import set_actor

set_actor("manual")
try:
    with session_scope() as s:
        ...
finally:
    set_actor("claude_session")
```

The bootstrap migration tags all its writes `actor=migration`.

---

## REST API surface

OpenAPI is auto-generated and served at:

- Swagger UI: http://127.0.0.1:8765/docs
- OpenAPI JSON: http://127.0.0.1:8765/openapi.json

All responses use the envelope shape:

```json
{ "data": <body or null>, "meta": {...}, "errors": null | [...] }
```

Errors return a non-2xx status with `errors` populated:

```json
{
  "data": null,
  "meta": {},
  "errors": [{ "code": "validation_error", "field": "status", "message": "..." }]
}
```

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/charter` | Current charter |
| `GET` | `/charter/versions` | All charter versions, newest first |
| `GET` | `/charter/versions/{n}` | Specific historical version |
| `PUT` | `/charter` | Replace charter (creates new version) |
| `GET` | `/status` | Current status (same shape as charter) |
| `GET` | `/status/versions` | All status versions |
| `GET` | `/status/versions/{n}` | Specific historical version |
| `PUT` | `/status` | Replace status |
| `GET` | `/decisions` | List decisions |
| `GET` | `/decisions/{id}` | One decision (e.g. `DEC-007`) |
| `POST` | `/decisions` | Create |
| `PATCH` | `/decisions/{id}` | Update |
| `DELETE` | `/decisions/{id}` | Delete |
| `GET` | `/sessions[?limit=N]` | List sessions, newest first |
| `GET` | `/sessions/{id}` | One session |
| `POST` | `/sessions` | Create (append-only — no PATCH) |
| `DELETE` | `/sessions/{id}` | Delete |
| `GET / POST / PATCH / DELETE` | `/risks[/{id}]` | Risks CRUD |
| `GET / POST / PATCH / DELETE` | `/planning-items[/{id}]` | Planning items CRUD |
| `GET / POST / PATCH / DELETE` | `/topics[/{id}]` | Topics CRUD |
| `GET` | `/references` | List all references |
| `POST` | `/references` | Create reference |
| `POST` | `/references/delete` | Delete reference (tuple in body) |
| `GET` | `/references/from/{type}/{id}` | Refs where entity is source |
| `GET` | `/references/to/{type}/{id}` | Refs where entity is target |
| `GET` | `/references/touching/{type}/{id}` | Both directions |
| `GET` | `/orientation/recent-sessions?limit=N` | Last N sessions |
| `GET` | `/orientation/decisions-for-session/{id}` | Decisions referenced by a session |

HTTP status mapping:

| Status | Cause |
|---|---|
| 200 | Success (read or update) |
| 201 | Successful create |
| 400 | Access-layer ValidationError (controlled-vocab violation, missing required field) |
| 404 | Access-layer NotFoundError |
| 409 | Access-layer ConflictError (duplicate identifier or duplicate reference tuple) |
| 422 | FastAPI request-shape validation (e.g. unknown field in body) |
| 500 | Unhandled exception |

---

## MCP tools

40 tools are registered. Names are verbs Claude can match from a
natural-language prompt. Full source: `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py`.

| Surface | Tools |
|---|---|
| Charter | `get_current_charter`, `get_charter_version`, `list_charter_versions`, `replace_charter` |
| Status | `get_current_status`, `get_status_version`, `list_status_versions`, `replace_status` |
| Decisions | `get_decision`, `list_decisions`, `create_decision`, `update_decision`, `delete_decision` |
| Sessions | `get_session`, `list_sessions`, `list_recent_sessions`, `create_session`, `delete_session`, `list_decisions_for_session` |
| Risks | `get_risk`, `list_risks`, `create_risk`, `update_risk`, `delete_risk` |
| Planning items | `get_planning_item`, `list_planning_items`, `create_planning_item`, `update_planning_item`, `delete_planning_item` |
| Topics | `get_topic`, `list_topics`, `create_topic`, `update_topic`, `delete_topic` |
| References | `list_references`, `add_reference`, `delete_reference`, `list_references_from`, `list_references_to`, `list_references_touching` |

Each tool wraps a single REST call. To add a tool, add a wrapper in
`tools.py` and a corresponding REST endpoint if one doesn't already exist.

---

## User interface

A standalone PySide6 desktop application for browsing and editing
storage system content.

```bash
uv run crmbuilder-v2-ui
```

The UI auto-launches the storage API (`crmbuilder-v2-api`) if it isn't
already running, and shuts it down on close. If the API is already
running externally (e.g., for the MCP server), the UI uses the
existing instance instead of spawning a duplicate.

Features:

- Sidebar navigation across all eight v2 entity types: Charter,
  Status, Decisions, Sessions, Risks, Planning Items, Topics,
  References.
- Master/detail layout per entity. Detail panes render full record
  content with cross-entity reference links (e.g., a decision's
  "Decided in" link navigates to the corresponding session).
- Live refresh via filesystem watcher on the snapshot directory:
  writes from MCP or other consumers update visible panels within
  ~500 ms; non-visible panels show a stale-data indicator. Content
  hashing suppresses no-op rewrites from the storage exporter so
  only entities with real changes signal staleness.
- Full create / edit / delete operations for decisions, with
  client-side format validation for the identifier (`DEC-NNN`) and
  decision date (`MM-DD-YY`). Delete is soft-delete by status; the
  row stays in the database with `status='Deleted'` so cross-entity
  references to it continue to resolve. Other entities are read-only
  in v0.1.
- Help → About surfaces app version, API URL, database path, and
  snapshot directory.

Logs land at `~/.crmbuilder-v2/ui.log`. Full requirements:
`PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`.

---

## Maintenance

### Schema migrations (Alembic)

The Alembic environment lives at `crmbuilder-v2/migrations/`. Always
run from the repo root with `-c crmbuilder-v2/alembic.ini`:

```bash
# Create a new revision after editing models.py.
uv run alembic -c crmbuilder-v2/alembic.ini revision --autogenerate \
  -m "add personas table"

# Review the generated file in crmbuilder-v2/migrations/versions/
# and rename it to a stable form like 0002_add_personas.py.

# Apply pending migrations.
uv run alembic -c crmbuilder-v2/alembic.ini upgrade head

# Inspect current schema version.
uv run alembic -c crmbuilder-v2/alembic.ini current
```

Notes:

- The Alembic env reads the DB URL from `crmbuilder_v2.config.get_settings()`,
  not from `alembic.ini`. To migrate against an alternate DB, set
  `CRMBUILDER_V2_DB_PATH` before invoking Alembic.
- The autogenerate diff is approximate: review it. Renames are detected
  as drop+create unless you provide a hint.
- `render_as_batch=True` is enabled in `migrations/env.py` so SQLite
  ALTER-style migrations work.
- Don't edit the baseline (`0001_initial_schema.py`) after the fact —
  add a new migration that does the schema change you need.

### JSON export consistency

The exporter rewrites all entity files atomically on every successful
write. If you ever see a `db-export/*.json.tmp` file leftover, the
previous write hit something fatal between flush and rename. Cleanup:

```bash
rm PRDs/product/crmbuilder-v2/db-export/*.json.tmp
```

To force a re-export from current DB state without making any
mutations:

```python
from crmbuilder_v2.access.db import force_export
force_export()
```

This is the recovery path if exports drift from the database (which
shouldn't happen, but `force_export` self-heals it).

### Backups

The git-tracked JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/`
are the durable backup. Every successful write produces a snapshot
delta; commit those alongside any related work and you have full
history through `git log`.

The SQLite file at `crmbuilder-v2/data/v2.db` is a derived artifact —
it is gitignored. Treat it as cache: deletable, recoverable from
the snapshots.

### Restoring from JSON snapshots

If `data/v2.db` is lost or corrupted:

```bash
rm -f crmbuilder-v2/data/v2.db
uv run crmbuilder-v2-bootstrap-db
```

This recreates an empty DB. To reload the v0.1 state from the
git-tracked exports, run a one-shot loader:

```python
import json
from datetime import datetime
from pathlib import Path

from crmbuilder_v2.access.change_log import set_actor
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import (
    ChangeLog, Charter, Decision, PlanningItem, Reference,
    Risk, Session, Status, Topic,
)

EXPORT = Path("PRDs/product/crmbuilder-v2/db-export")
TABLES = [
    ("charter", Charter), ("status", Status), ("decisions", Decision),
    ("sessions", Session), ("risks", Risk),
    ("planning_items", PlanningItem), ("topics", Topic),
    ("references", Reference), ("change_log", ChangeLog),
]

set_actor("manual")
with session_scope(export=False) as s:
    for name, model in TABLES:
        for row in json.loads((EXPORT / f"{name}.json").read_text()):
            for col, val in list(row.items()):
                if "_at" in col and isinstance(val, str):
                    row[col] = datetime.fromisoformat(val)
            # 'references' surfaces 'relationship'; the model uses
            # 'relationship_kind'.
            if "relationship" in row and model is Reference:
                row["relationship_kind"] = row.pop("relationship")
            s.add(model(**row))
```

This is a recovery path, not a routine operation. Most often you'll
restore by `git checkout` of the SQLite file from a recent state, or
just rebootstrap and let normal Tier 2 reads work off the JSON snapshots.

### Restoring the original markdown governance files

The four bootstrap markdown files (`charter.md`, `decisions.md`,
`sessions.md`, `status.md`) were retired at commit `12b96bc`. Recover
them with:

```bash
git show 12b96bc^:PRDs/product/crmbuilder-v2/charter.md > /tmp/charter.md
git show 12b96bc^:PRDs/product/crmbuilder-v2/decisions.md > /tmp/decisions.md
git show 12b96bc^:PRDs/product/crmbuilder-v2/sessions.md > /tmp/sessions.md
git show 12b96bc^:PRDs/product/crmbuilder-v2/status.md > /tmp/status.md
```

You can then re-run `crmbuilder-v2-bootstrap` against `/tmp` if you
need to import a fresh copy into a clean database (idempotent —
existing rows are upserted in place, no duplicates).

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ConflictError: decision 'DEC-NNN' already exists` on POST | Identifier reused | PATCH the existing record, or use a different identifier |
| `NotFoundError` on PATCH or DELETE | Identifier doesn't exist | Verify with GET first |
| `ValidationError: status must be one of [...]` | Controlled-vocab violation | Use only the values listed in `crmbuilder_v2/access/vocab.py` |
| `httpx.ConnectError` from MCP | API not running | Start `crmbuilder-v2-api` in another terminal |
| FK constraint failure | Referenced row missing or pragma off | Engine should set `PRAGMA foreign_keys=ON` automatically; if you see this, your shell session lost the connect listener — recreate the engine |
| `db-export/*.json.tmp` files accumulating | Crash mid-export-promotion | Delete them; next successful write self-heals |
| Tests fail with `database is locked` | Stale connection | `crmbuilder_v2.access.db.reset_engine_cache()` or drop the test DB and rerun |
| `alembic current` shows blank | DB never had Alembic stamps applied (e.g., created via `bootstrap_database`) | Run `alembic stamp head` once, then future migrations work |

### Adding a new vocabulary value

Controlled vocabularies are deliberately gated in
`crmbuilder_v2/access/vocab.py`. To add a new reference relationship,
for example:

1. Add the value to `REFERENCE_RELATIONSHIPS`.
2. Generate a migration that drops and recreates the CHECK constraint
   on `refs.relationship_kind` with the expanded set.
3. Update the operator-facing documentation (this README, MCP tool
   descriptions in `tools.py`).
4. Apply the migration: `alembic upgrade head`.

The deliberate gate is the point — DEC-006 asks for the vocabulary
to grow consciously, not by accident.

### Re-bootstrapping

To completely wipe and reload from scratch (loses change_log history):

```bash
rm -f crmbuilder-v2/data/v2.db
uv run crmbuilder-v2-bootstrap-db
# Then either:
#  (a) run the recovery loader above to restore from JSON snapshots, or
#  (b) re-run crmbuilder-v2-bootstrap if you've recovered the markdown
#      sources via git show.
```

### Running tests

```bash
# Just the v2 suite (96 tests, ~40s).
uv run pytest tests/crmbuilder_v2/

# A specific layer.
uv run pytest tests/crmbuilder_v2/access/
uv run pytest tests/crmbuilder_v2/api/
uv run pytest tests/crmbuilder_v2/mcp_server/
uv run pytest tests/crmbuilder_v2/bootstrap/

# With coverage.
uv run pytest tests/crmbuilder_v2/ --cov=crmbuilder_v2
```

The v2 fixtures (`tests/crmbuilder_v2/conftest.py`) provision a fresh
SQLite DB and JSON-export directory per test. They do not touch
`crmbuilder-v2/data/v2.db` or `PRDs/product/crmbuilder-v2/db-export/`.

---

## Development

### Adding a new entity type (the four-step pattern)

1. **Model**: add a SQLAlchemy class to
   `crmbuilder_v2/access/models.py` with controlled-vocab CHECK
   constraints, indexes, FK relations.
2. **Repository**: add a module under
   `crmbuilder_v2/access/repositories/` with `get`, `list_all`,
   `create`, `update` (if not append-only), `delete`, and `upsert`
   for bootstrap idempotency. Emit change_log entries via
   `change_log.emit`.
3. **Router**: add a router under `crmbuilder_v2/api/routers/` and
   register it in `crmbuilder_v2/api/main.py`. Add request schemas
   to `crmbuilder_v2/api/schemas.py`.
4. **MCP tools**: add wrappers in
   `crmbuilder_v2/mcp_server/tools.py` mirroring the new endpoints.

Then:

5. **Vocabulary** updates in `crmbuilder_v2/access/vocab.py` if the
   entity introduces new controlled values, plus an Alembic migration
   to extend any CHECK constraints.
6. **Exporter**: append the new model + filename to
   `_EXPORT_TABLES` in `crmbuilder_v2/access/exporter.py`.
7. **Tests**: add fixtures under `tests/crmbuilder_v2/access/`,
   `api/`, and `mcp_server/` matching the existing patterns.
8. **Migration**: `alembic revision --autogenerate -m "add <entity>"`,
   review, rename to `00NN_add_<entity>.py`, `alembic upgrade head`.

### File map (for orientation)

```
crmbuilder-v2/
├── alembic.ini                       # Alembic config (read by all alembic commands)
├── data/                             # gitignored; runtime SQLite file
├── migrations/                       # Alembic env + versions
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
└── src/crmbuilder_v2/
    ├── __init__.py
    ├── cli.py                        # console-script entry points
    ├── config.py                     # Pydantic Settings
    ├── access/
    │   ├── db.py                     # engine, session_scope, force_export
    │   ├── models.py                 # SQLAlchemy ORM
    │   ├── vocab.py                  # controlled vocabularies
    │   ├── exceptions.py             # AccessLayerError hierarchy
    │   ├── change_log.py             # actor contextvar + emit()
    │   ├── exporter.py               # JSON snapshot hook
    │   ├── _helpers.py               # to_dict, require_string, require_in
    │   └── repositories/             # one per entity
    ├── api/
    │   ├── main.py                   # FastAPI app factory
    │   ├── deps.py                   # writable_session / readonly_session
    │   ├── envelope.py               # ok() / err()
    │   ├── errors.py                 # AccessLayerError → HTTP mapping
    │   ├── schemas.py                # Pydantic request models
    │   └── routers/                  # one per entity + orientation
    ├── mcp_server/
    │   ├── server.py                 # FastMCP boot
    │   └── tools.py                  # 40 tool definitions
    └── bootstrap/
        ├── migrate.py                # CLI entry; orchestrates parsers + access layer
        └── parsers/                  # markdown → row dicts
            ├── _md.py
            ├── charter.py
            ├── decisions.py
            ├── sessions.py
            └── status.py

tests/crmbuilder_v2/
├── conftest.py                       # tmp DB / tmp export dir fixtures
├── access/
├── api/
├── mcp_server/
└── bootstrap/
    ├── fixtures/                     # test markdown
    └── test_migrate.py
```

### Linting

```bash
uv run ruff check crmbuilder-v2/src/ tests/crmbuilder_v2/
uv run ruff format crmbuilder-v2/src/ tests/crmbuilder_v2/
```

The repo's ruff config (`pyproject.toml [tool.ruff]`) targets
Python 3.12, line length 88, with the same rule set used by v1.

---

## Reference

Authoritative documents (in this repo):

- `PRDs/product/crmbuilder-v2/storage-system-PRD-v0.1.md` — what the
  system must do.
- `PRDs/product/crmbuilder-v2/storage-system-implementation-plan.md` —
  the build plan executed to produce v0.1.
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-B-storage-system.md`
  — the executing prompt.

Authoritative governance content (in the database; mirrored in
`db-export/`):

- **Charter** — current scope, foundations, current state.
- **Status** — phase, active work, pending lists.
- **Decisions** — DEC-001 through DEC-017.
  Particularly load-bearing: DEC-003 (v1/v2 boundary), DEC-004
  (database as source of truth), DEC-005 (storage stack), DEC-006
  (universal references), DEC-007 (topics table), DEC-008 (renders),
  DEC-011 (orientation protocol), DEC-013 (sessions append-only),
  DEC-016 (definition of done), DEC-017 (implementation stack).
- **Sessions** — SES-001 (initial planning), SES-002 (planning
  dimension #5), SES-003 (v0.1 build).
- **References** — 17 cross-entity links (decided_in relationships
  between sessions and the decisions they produced).

Read any of these via `get_decision("DEC-005")` etc. through MCP, the
REST API, or by `jq`-ing the corresponding JSON snapshot.

The v1 codebase, methodology guides, and CBM client repo are out of
scope for this system per DEC-003 and continue to live at their
existing locations.
