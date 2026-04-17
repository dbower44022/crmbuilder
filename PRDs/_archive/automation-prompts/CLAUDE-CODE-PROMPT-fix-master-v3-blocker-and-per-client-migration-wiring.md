# Claude Code Prompt — Fix Master DB v3 Blocker, Wire Per-Client Migrations, and Heal Existing Databases

## Purpose

Prompts A through C shipped new schema (Instance, DeploymentRun on the
per-client database; relaxed `database_path` constraint on the master
database) and the v3 migrations to produce it, but three problems are
blocking the application on Doug's existing installation:

1. **Master v3 migration is blocked on existing data.** The v3 master
   migration pre-check aborts when any `Client` row has
   `project_folder IS NULL`. Doug's existing `CBM` row has
   `project_folder = NULL` because v2's backfill could not match the
   row's `database_path` to the expected convention and skipped it
   with a warning. v3 correctly refuses to proceed; the app logs
   "Could not initialize master database" and continues without the
   rebuild. Client creation then fails with
   `NOT NULL constraint failed: Client.database_path` because the
   old constraint is still in place.

2. **Per-client v3 migration is defined but not running against
   existing client databases.** `_client_v3` in
   `automation/db/migrations.py` creates the `Instance` and
   `DeploymentRun` tables, but Doug's existing `cbm-client.db` does
   not have those tables. `run_client_migrations()` is not being
   invoked on existing client databases during the normal
   open-client path at application startup — only on new-client
   creation and in a few explicit call sites. Existing clients never
   get upgraded.

3. **The "Could not initialize master database" failure is swallowed
   as a WARNING and the app keeps running.** The user sees a broken
   Clients tab and a cryptic log line, with no indication that a
   migration aborted or what to do about it.

This prompt fixes all three. It is a bugfix prompt, not part of the
v1.16 series.

## Investigation First — Do Not Skip

Before writing any code, perform these read-only investigation steps
against the repository to confirm the current state and avoid
guessing:

1. Read `automation/db/migrations.py` end to end. Note the current
   master and client migration lists, the `run_master_migrations`
   and `run_client_migrations` function signatures, and how
   `schema_version` is tracked.
2. Read `automation/db/master_schema.py` — confirm the declared
   (fresh-install) `Client` table and the current
   `MASTER_SCHEMA_VERSION` constant.
3. Read `automation/core/create_client.py` — confirm the INSERT
   statement for new clients and what it does and does not supply.
4. Trace every call site of `run_client_migrations` in the codebase.
   Identify whether the app startup path (master DB open →
   enumerate clients → open per-client DB) actually runs per-client
   migrations. This is what we need to fix in Part 2.
5. Read `espo_impl/main.py` and `espo_impl/ui/main_window.py` to
   locate the startup sequence where the master DB is opened and
   where per-client databases become involved. Identify where the
   migration failure is currently being caught and logged as a
   warning.
6. Confirm whether any other `Client` rows besides CBM exist in the
   master DB by reading the actual database file at
   `/home/doug/Dropbox/Projects/crmbuilder/automation/data/master.db`
   with the Python `sqlite3` module. Do not use the `sqlite3` CLI —
   it is not installed on this machine. Read-only access only at
   this stage.

If the investigation surfaces anything that contradicts the
assumptions above (for example, per-client migrations are in fact
already wired into startup), **stop and report findings before
implementing**. Do not silently change the plan.

## Scope — What This Prompt Does

### Part 1 — Heal Doug's existing master database

The goal is to let the v3 master migration run successfully on Doug's
machine so that `Client.database_path` becomes nullable and client
creation works.

The v3 pre-check is correct and must not be weakened. Instead, heal
the data that is causing it to abort.

1. **Add a new startup heal step** in the master migration path, run
   **before** the migration loop. The heal step identifies `Client`
   rows with `project_folder IS NULL` that can be unambiguously
   repaired and repairs them in place.
2. **Repair rule**: for each row with `project_folder IS NULL`, look
   at `database_path`. If `database_path` follows the convention
   `.../automation/data/{code-lowercase}-client.db` (i.e., the row's
   database lives inside the crmbuilder repo's own `automation/data`
   directory), the heal step cannot guess the external project
   folder and must leave the row alone — v3 will then abort with
   its existing clear error. This is the conservative path.
3. **Alternative repair via master configuration**: also support a
   manual override. Add an optional `project_folder_overrides`
   argument to `run_master_migrations(..., project_folder_overrides:
   dict[str, str] | None = None)`. Keys are Client `code` values;
   values are the project folder path to set. The heal step applies
   overrides before checking the general repair rule.
4. **Wire the override through startup** so that Doug can resolve
   his specific case. In `espo_impl/main.py` (or wherever
   `run_master_migrations` is called at startup), read a JSON file
   at `automation/data/migration-overrides.json` if present and pass
   its contents as `project_folder_overrides`. The file format is a
   flat object mapping client code to project folder path, e.g.:
   ```json
   { "CBM": "/home/doug/Dropbox/Projects/ClevelandBusinessMentors" }
   ```
   If the file is absent, pass `None`. The file is gitignored — add
   it to `.gitignore` if not already covered — because it contains
   machine-specific absolute paths.
5. **Create the override file for Doug as part of this fix**. Write
   `automation/data/migration-overrides.json` with the single entry
   `{"CBM": "/home/doug/Dropbox/Projects/ClevelandBusinessMentors"}`.
   Do not commit the file — only create it in Doug's working
   directory — but make sure the code path to read it is committed.
6. **Back up the master database before the heal step touches it.**
   Copy `master.db` to `master.db.pre-v3-heal-{timestamp}` in the
   same directory. If the heal step fails midway, the user has a
   trivial rollback.

After Part 1 lands, Doug starts the app, `run_master_migrations`
loads the override file, heals the `CBM` row's `project_folder`,
v3's pre-check passes, the table rebuild runs, and the master DB
reaches version 3 with `database_path` nullable.

### Part 2 — Wire per-client migrations into the normal startup path

`_client_v3` creates the Instance and DeploymentRun tables but
Doug's existing `cbm-client.db` does not have them. This means
`run_client_migrations` is not being invoked on existing client
databases when the app starts.

1. **Audit the client-open code path**. Identify every place in the
   app that opens a per-client SQLite connection for an existing
   client. The likely entry points are: active-client context
   initialization (`automation/ui/active_client_context.py`), the
   Clients tab's client-selection handler, and anything in
   `espo_impl` that opens a client DB directly.
2. **Route all of those through `run_client_migrations`.** Any code
   path that opens an existing client database must call
   `run_client_migrations(db_path)` first, which is idempotent — it
   checks `schema_version` and only applies pending migrations.
   Existing client databases will pick up `_client_v3` and gain the
   Instance and DeploymentRun tables automatically on the next
   startup.
3. **Do not add duplicate migration calls.** If a code path already
   calls `run_client_migrations`, leave it alone. The goal is to
   ensure every open-existing-client path calls it exactly once,
   not to add belt-and-suspenders calls.
4. **Surface per-client migration failures clearly.** If
   `run_client_migrations` raises while opening an existing client,
   the error must be shown to the user in a dialog, not silently
   logged as a warning. The app should refuse to activate a client
   whose database failed to migrate, so the user sees an explicit
   message rather than a half-working Deployment tab with missing
   tables.

### Part 3 — Stop swallowing master migration failures

In `espo_impl/main.py` (or `espo_impl/ui/main_window.py`, wherever
`run_master_migrations` is currently invoked), the migration failure
is being caught and logged as a `WARNING` with the app continuing
anyway. This is wrong — if the master DB migration fails, the app
cannot function correctly.

1. **On master migration failure, show a blocking error dialog**
   explaining what failed, the exception message, and a clear
   instruction to check
   `automation/data/migration-overrides.json` for a possible
   repair. The dialog must block the app from reaching the main
   window.
2. **Keep the warning log line** for headless / test environments
   where the dialog cannot be shown, but escalate it from WARNING
   to ERROR.
3. **Do not weaken the v3 pre-check**. The pre-check aborting is
   correct behavior — the fix is to heal the data upstream (Part 1)
   and surface the failure properly (Part 3), not to paper over it.

### Part 4 — Repair Doug's existing `cbm-client.db` on next startup

Once Parts 1 and 2 land and Doug restarts the app:

- Master DB heals, v3 runs, client creation works.
- `cbm-client.db` is opened through the active-client context, which
  now routes through `run_client_migrations`, which runs
  `_client_v3`, which adds the Instance and DeploymentRun tables.
- The Deployment tab's Instances entry then shows an empty list
  (correct — no instances have been migrated).
- Doug manually recreates his two CBM instances through the "+ New
  Instance" form, per §16.17's sanctioned fallback.

No code changes are needed for Part 4 beyond what Parts 1–3 deliver.
It is listed here so the implementer verifies the end-to-end path
mentally before considering the prompt complete.

## Tests

- **Master heal step**: unit tests covering (a) override file
  present with matching code → row healed, (b) override file absent
  → row untouched, pre-check aborts as before, (c) override file
  references a code that doesn't exist → warning, not error,
  (d) override applied, pre-check passes, v3 rebuild succeeds,
  (e) master DB backup file is created before heal runs.
- **Per-client migration wiring**: integration test that (a) creates
  a pre-v3 client database (no Instance / DeploymentRun tables),
  (b) opens it through the active-client context,
  (c) asserts Instance and DeploymentRun now exist and
  `schema_version` max is 3. Add this test to the existing per-client
  migration test file.
- **Startup failure dialog**: unit test using a mock dialog provider
  that asserts the blocking error dialog is shown when
  `run_master_migrations` raises, and that the app does not proceed
  to the main window.
- **Full regression**: `uv run pytest tests/ -v` must pass, `ruff`
  must be clean.

## Acceptance Criteria

After this prompt runs, Doug should be able to:

1. Pull `main`, start the app, and see no "Could not initialize
   master database" warning.
2. Create a new client through the Clients tab "+ New Client" form
   without any NOT NULL error.
3. Open the Deployment tab while CBM is the active client and see
   the Instances entry render with an empty list (no Instance
   table missing error).
4. Click "+ New Instance" and successfully create an Instance row
   in `cbm-client.db`.

If any of these fail, the fix is incomplete.

## Deliverables

- Updated `automation/db/migrations.py` — master migration heal
  step, `project_folder_overrides` parameter on
  `run_master_migrations`.
- Updated `espo_impl/main.py` (or equivalent startup file) — loads
  `migration-overrides.json`, passes to `run_master_migrations`,
  shows blocking error dialog on failure, escalates log level.
- Updated active-client-context / client-open paths — route through
  `run_client_migrations`, surface failures to the user.
- New file at `automation/data/migration-overrides.json` with the
  CBM entry (not committed to git; add to `.gitignore` if needed).
- New tests per the Tests section above.
- Short note in the PR description confirming Doug's Acceptance
  Criteria pass on his local machine after pulling the fix.

## Out of Scope

- Do not modify the v3 master migration itself or weaken the
  pre-check.
- Do not attempt to migrate the legacy `data/instances/*.json`
  files — §16.17 allows manual recreation and that is the chosen
  path for Doug's two CBM instances.
- Do not touch the v1.16 Prompt D (Deploy Wizard) work.
