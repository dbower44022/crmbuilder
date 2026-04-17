# Claude Code Prompt — Fix Client.database_path NOT NULL Migration Gap

## Purpose

Master databases created before the `project_folder` refactor still
carry a `NOT NULL` constraint on `Client.database_path`, because the
v2 migration added `project_folder` as the new canonical location
field but never rebuilt the `Client` table to relax the old
`database_path` constraint. Fresh installs get the correct schema
from `automation/db/master_schema.py` (where `database_path` is
declared nullable), but existing databases on disk still enforce
the old constraint.

`automation/core/create_client.py` inserts only
`(name, code, description, project_folder)` and does not supply a
`database_path`. On any master database that was originally created
under the v1 schema, this insert fails at runtime with:

```
Client Creation failed: NOT NULL constraint failed: Client.database_path
```

This is a pre-existing latent bug that was exposed by the v1.16
Clients tab work — it is not caused by Prompts B or C and is not
part of the v1.16 series.

## Scope — What This Prompt Does

### 1. Add master database migration v3

Add a new migration `_master_v3` to `automation/db/migrations.py`
that rebuilds the `Client` table to match the current
`master_schema.py` definition. Append `(3, _master_v3)` to
`MASTER_MIGRATIONS`.

Because SQLite cannot `ALTER COLUMN` to relax a `NOT NULL`
constraint, the migration must use the standard SQLite 12-step
table redefinition pattern:

1. Create a new table `Client_new` with the **current**
   `master_schema.py` column definitions (including
   `database_path TEXT` nullable and `project_folder TEXT NOT NULL
   UNIQUE`).
2. Copy all rows from `Client` into `Client_new`, preserving
   `id`, `created_at`, `updated_at`, and every other column value.
3. Drop the old `Client` table.
4. Rename `Client_new` to `Client`.

Wrap the entire rebuild in a single transaction. Use
`PRAGMA foreign_keys = OFF` around the rebuild if foreign-key
checking is enabled, then restore the prior setting — follow the
pattern from the SQLite documentation's "Making Other Kinds Of
Table Schema Changes" section.

The new table definition must be a single source of truth.
**Do not copy-paste the CREATE TABLE statement from
`master_schema.py`.** Import `CLIENT_TABLE` (or whichever constant
holds the current definition) from `automation.db.master_schema`
and execute it against a temporary table name. If the constant
hard-codes the table name `Client`, add a small helper or
parameterize the SQL so the v3 migration can create `Client_new`
without duplicating the column list. Confirm with the existing
`master_schema.py` layout before deciding the cleanest approach.

### 2. Pre-check for NULL project_folder rows

Before starting the table rebuild, `_master_v3` must run a
pre-check:

```sql
SELECT id, code FROM Client WHERE project_folder IS NULL
```

If any rows are returned, **abort the migration immediately** by
raising a clear exception that lists the offending rows. Do not
attempt to auto-fix. Do not proceed with the table rebuild. The
error message must be actionable, e.g.:

```
Cannot apply master migration v3: the following Client rows have
NULL project_folder and cannot be migrated to the new schema.
Resolve manually before running the migration.
  - Client id=3 code=CBM
  - Client id=7 code=ACME
```

Rationale: the new `Client` table declares `project_folder NOT NULL`.
If v2's backfill from `database_path` hit its path-mismatch warning
and skipped a row, that row will still have `project_folder IS NULL`
and the table rebuild would fail partway through with a cryptic
constraint error. A pre-check with a clear message is cheap insurance
and matches the conservative pattern already used in v2 (which
warns and skips rather than guessing).

### 3. Preserve rows losslessly

The rebuild must copy every column currently on `Client` to
`Client_new`, including:

- `id` (preserve the primary key value, do not let autoincrement
  reassign it)
- `name`, `code`, `description`
- `database_path` (copy as-is — the column is retained for
  backward compatibility per the comment in `master_schema.py`)
- `organization_overview`
- `project_folder`
- `crm_platform`, `deployment_model`
- `last_opened_at`, `created_at`, `updated_at`

If the existing `Client` table on disk is missing any of these
columns (e.g., a very old database that never ran v2), the
migration runner should have already applied v2 first, which
adds `project_folder`, `deployment_model`, and `last_opened_at`.
Assume v2 has run; do not special-case pre-v2 databases in v3.

### 4. Tests

Add tests to `tests/db/test_master_migrations.py` covering:

- **Happy path**: create a v1-era database (table with
  `database_path NOT NULL`, no `project_folder` column), run all
  migrations through v3, verify that (a) the final schema has
  `database_path` nullable, (b) all rows are preserved with
  identical values including `id`, and (c) an INSERT that omits
  `database_path` succeeds.
- **Preserves row identity**: confirm `id`, `created_at`, and
  `updated_at` values are preserved byte-for-byte across the
  rebuild.
- **Pre-check abort**: create a database where one Client row
  has `project_folder IS NULL` after v2, run v3, assert that it
  raises with a message listing the offending `id` and `code`,
  and assert that the database is unchanged (original `Client`
  table still present, no `Client_new` table left behind).
- **Idempotency via version tracking**: run migrations twice,
  confirm v3 runs exactly once (the existing migration runner
  should handle this; the test just verifies no double-rebuild).
- **Fresh database**: create a database from `master_schema.py`
  directly, run migrations, confirm v3 is a no-op because the
  version is already at or above 3 (or that it runs safely
  because the schema already matches — whichever the migration
  runner's convention is).

### 5. Verify the fix end-to-end

After the migration is in place, add one integration-style test
(or extend an existing one) that:

1. Creates a v1-era master database programmatically.
2. Runs migrations.
3. Calls `automation.core.create_client.create_client()` with
   valid parameters.
4. Asserts the client is created successfully and the returned
   row has the expected values.

This is the regression guard — it directly reproduces the user-
visible failure and confirms the fix.

## Scope — What This Prompt Does NOT Do

- Does not remove the `database_path` column. The column is
  retained for backward compatibility per the existing comment
  in `master_schema.py`.
- Does not modify `create_client.py` to backfill `database_path`.
  The column is deprecated; the correct fix is to relax the
  constraint, not to keep writing to a deprecated column.
- Does not touch per-client database schemas. This is a master
  database fix only.
- Does not modify the v1 or v2 migrations. Those are historical
  and must not be edited.
- Does not change `master_schema.py`. The declared schema is
  already correct; only existing on-disk databases are wrong.

## Testing

- `uv run pytest tests/db/test_master_migrations.py -v` must pass,
  including all new tests above.
- Full regression: `uv run pytest tests/ -v` must pass.
- `ruff` must be clean.
- Manually verify against Doug's local master database: after
  pulling this fix, starting the app, and creating a new client
  through the Clients tab "+ New Client" form, the creation
  succeeds without the NOT NULL error.

## Deliverables

- New `_master_v3` function in `automation/db/migrations.py`.
- `MASTER_MIGRATIONS` list updated to include `(3, _master_v3)`.
- New tests in `tests/db/test_master_migrations.py` covering the
  five cases listed in section 4 plus the integration test in
  section 5.
- Whatever minimal helper is needed to execute the current
  `Client` table definition against a temporary table name without
  duplicating the column list.
