# PI-α — Postgres: dev quickstart + migration runbook

**Status:** v0.1 (06-02-26). Operational companion to
`pi-alpha-postgres-foundation-architecture.md`. Covers standing up Postgres for
dev/test, running the schema baseline, migrating `v2-unified.db` into Postgres,
and validating the result.

**One switch.** The v2 store is Postgres when `CRMBUILDER_V2_DATABASE_URL` is set
to a SQLAlchemy Postgres URL; unset, it is the SQLite file at `db_path`. Nothing
else changes — the unified row-level `engagement_id` schema and the scope
filter/stamp are dialect-agnostic. **SQLite remains the default**; flip to
Postgres only after rehearsing the migration (the Deployment-phase decision).

```
CRMBUILDER_V2_DATABASE_URL='postgresql+psycopg://user:pw@host:5432/crmbuilder_v2'
```

---

## 1. Dev / test Postgres (Docker)

```bash
cd crmbuilder-v2
docker compose -f docker-compose.dev.yml up -d        # PG16, container crmb_pg_dev, host port 55432
export CRMBUILDER_V2_DATABASE_URL='postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2'
# … work …
docker compose -f docker-compose.dev.yml down          # stop (ephemeral; nothing persisted)
```

Port 55432 (not 5432) avoids clashing with a host Postgres. CI uses the same
image as a service (`.github/workflows/postgres-tests.yml`) on 5432.

## 2. Create the schema on Postgres

Two equivalent ways. Use the Alembic baseline for a tracked production schema;
`create_all` is what the tests and the migration script use internally.

```bash
# Alembic baseline (tracked — stamps 0001_pg_baseline so future PG migrations apply)
CRMBUILDER_V2_DATABASE_URL='…' uv run alembic -c migrations/pg/alembic.ini upgrade head
```

The SQLite chain at `migrations/` (0001-0039) is **not** for Postgres — PG has its
own chain at `migrations/pg/`. Never run the SQLite chain against a PG DB.

## 3. Migrate `v2-unified.db` → Postgres

The just-built, validated unified SQLite DB is the migration source. The script
stands up the schema (unless `--no-create-schema`), copies every table preserving
`engagement_id`, resets PG sequences, and validates.

```bash
# Schema created by the script (create_all):
uv run python -m crmbuilder_v2.migration.sqlite_to_postgres \
    --sqlite crmbuilder-v2/data/v2-unified.db \
    --postgres 'postgresql+psycopg://user:pw@host:5432/crmbuilder_v2'

# …or against a schema already applied via the Alembic baseline:
uv run python -m crmbuilder_v2.migration.sqlite_to_postgres \
    --sqlite crmbuilder-v2/data/v2-unified.db \
    --postgres '…' --no-create-schema
```

Output reports per-engagement row counts, sequences reset, and `isolation on PG`.
The migration **refuses a non-empty target** (drop/recreate the schema to re-run).

What it does, precisely (see the module docstring):
- copies through SQLAlchemy Core bound to `Base.metadata`, so the type system
  round-trips JSON-text→JSONB, `0/1`→bool, ISO→`timestamptz`;
- inserts in `Base.metadata.sorted_tables` (FK-parent) order with FK enforcement
  **on** — no superuser / `session_replication_role` needed;
- two-passes the only intra-table integer self-FKs (`decisions.supersedes_id`/
  `superseded_by_id`, `topics.parent_topic_id`): insert NULLed, then UPDATE;
- resets every `SERIAL` sequence to `MAX(id)` so the next ORM insert can't collide.

## 4. Validate

The script's own validation (D9 acceptance) asserts per-engagement per-table
row-count parity vs the source, identifier-set parity, no NULL `engagement_id`,
and a cross-engagement isolation check (the PI-123 leak-test) through the scoped
ORM on Postgres. A non-`ok` result prints the mismatches and exits non-zero.

To re-run the harness test against a live PG:

```bash
CRMBUILDER_V2_TEST_PG_URL='postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2' \
    uv run pytest tests/crmbuilder_v2/migration/test_sqlite_to_postgres.py -q
```

## 5. Run the suite on Postgres

```bash
CRMBUILDER_V2_TEST_PG_URL='postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2' \
    uv run --directory crmbuilder-v2 pytest ../tests/crmbuilder_v2/access ../tests/crmbuilder_v2/api -q
```

The gate routes `v2_env` at Postgres, builds the schema once, and resets each
test with a reverse-FK DELETE + sequence reset. Intrinsically-SQLite tests
(type-affinity reflection, `sqlite_master`/two-file routing) are auto-skipped on
PG; the UI suite (needs a display, dialect-agnostic) and the `main`-branch-guarded
`test_apply_close_out` are out of scope for the PG run.

## 6. Production (DigitalOcean Managed Postgres) — outline

Pinned in detail at PI-α's Deployment phase (architecture doc §7). Sketch:
1. Provision managed Postgres; capture the connection URL (with `sslmode=require`).
2. `alembic -c migrations/pg/alembic.ini upgrade head` against it.
3. `sqlite_to_postgres … --no-create-schema` from a copy of the blessed
   `v2-unified.db`.
4. Point the API service at it via `CRMBUILDER_V2_DATABASE_URL`; keep SQLite as a
   rollback for a window; then flip the default.

---

## Cross-references
- `pi-alpha-postgres-foundation-architecture.md` (design + §8.5 build notes).
- `crmbuilder-v2/src/crmbuilder_v2/migration/sqlite_to_postgres.py`,
  `crmbuilder-v2/migrations/pg/`, `crmbuilder-v2/docker-compose.dev.yml`,
  `.github/workflows/postgres-tests.yml`.
