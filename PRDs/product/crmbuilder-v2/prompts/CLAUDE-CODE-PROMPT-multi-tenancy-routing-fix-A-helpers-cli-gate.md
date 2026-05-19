# CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-A-helpers-cli-gate

**Last Updated:** 05-19-26 16:00
**Operating mode:** DETAIL
**Series:** multi-tenancy-routing-fix
**Slice:** A — Backend: helpers, gate, CLI routing
**Status:** Ready to execute
**Companions:**
- `PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md` — overall plan (§5 slice A section is authoritative for acceptance criteria).
- `PRDs/product/crmbuilder-v2/multi-tenancy-routing-investigation-report.md` — diagnostic context.

---

## Purpose

Land the backend half of the multi-tenancy routing fix. Extract two helpers (`resolve_active_engagement`, `route_settings_to_engagement`), add an export-write gate (`assert_export_dir_ready`), wire the CLI to use them at startup, add the `--engagement <code>` flag, add the `CRMBUILDER_V2_EXPORT_DIR` env var to Settings, and apply the gate at the three active export-write sites (`session_scope`, `force_export`, catalog exporter). Investigate `bootstrap/migrate.py:64` and apply the right fix based on whether it's engine-scoped or engagement-scoped.

After this slice lands:
- CLI-launched API gets the full fix.
- UI-launched API continues working unchanged on its existing inline code path (slice B refactors it).
- Bugs 1 and 2 from the investigation are functionally resolved on the CLI path.

This slice does NOT touch any PySide6 widgets, dialogs, or panels — those land in slice B.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts.

5. **Read CLAUDE.md and the companion documents:**

   - `CLAUDE.md` (root) — review the "v2 API responses use a {data, meta, errors} envelope" note and the "Direct-API writes for prefixed-identifier entity types compute the identifier client-side" note; not load-bearing for this slice but worth being aware of.
   - `PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md` — slice A section (§5) is authoritative for acceptance criteria and file:line touch points.
   - `PRDs/product/crmbuilder-v2/multi-tenancy-routing-investigation-report.md` — §A, §B, §C, §D, §E, §G are the diagnostic context for the implementation.

6. **Verify the v0.5 multi-tenancy code is in place.** Confirm these files exist (slice A consumes them; if any are missing, stop and report):

   ```bash
   ls -la crmbuilder-v2/src/crmbuilder_v2/cli.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/config.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/db.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/meta_db.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/engagement.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/repositories/catalog/exports.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/exporter.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/migration/lazy_migration.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/bootstrap/migrate.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/ui/app.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/ui/active_engagement_context.py
   ```

7. **Read the relevant code paths.** Read `cli.py:17-49`, `config.py:22-46`, `access/db.py:64-140`, `access/exporter.py:113-129`, `access/meta_db.py:29-97`, `migration/lazy_migration.py:43-51`, `access/engagement.py` (find the existing function that reads a single engagement record by code), `bootstrap/migrate.py:60-70` (the section using `settings.export_dir.parent`). Do not modify yet.

8. **Confirm sparse-checkout includes the v2 source.** `git sparse-checkout list` should include `crmbuilder-v2/` and `PRDs/`. If sparse-checkout is restricting visibility, stop and report.

9. **Confirm the test suite is currently green.** Baseline before any changes:

   ```bash
   cd crmbuilder-v2
   uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
   cd ..
   ```

   Note the passing count. Stop and report if anything is failing before slice A starts.

---

## Workflow

The workflow is nine numbered steps. Each step's acceptance is the test invocation noted at its end. If any acceptance fails, stop and report; do not continue.

### Step 1 — Create the `runtime/` package and exceptions

Create the new package directory and exception module.

```bash
mkdir -p crmbuilder-v2/src/crmbuilder_v2/runtime
```

Create `crmbuilder-v2/src/crmbuilder_v2/runtime/__init__.py` as an empty file (no exports — modules import directly).

Create `crmbuilder-v2/src/crmbuilder_v2/runtime/exceptions.py` containing:

- `class EngagementError(Exception)` — base class for engagement-related runtime errors.
- `class UnknownEngagementError(EngagementError)` — raised when an engagement code is not in the meta DB. Carries `code` and optionally `available_codes` attributes for inclusion in error messages.
- `class EngagementExportDirError(EngagementError)` — intermediate base for export_dir-specific errors. Allows callers to catch the umbrella class.
- `class EngagementExportDirNotConfigured(EngagementExportDirError)` — raised when `engagement_export_dir` is null in the meta DB. Carries `code` attribute.
- `class EngagementExportDirMissing(EngagementExportDirError)` — raised when `engagement_export_dir` is set but the path doesn't exist on disk. Carries `code` and `path` attributes.

Each exception has a default `__str__` rendering matching the messages specified in DEC-108..114. Reference the slice plan §3 for exact text.

**Acceptance:** `uv run python -c "from crmbuilder_v2.runtime.exceptions import UnknownEngagementError, EngagementExportDirNotConfigured, EngagementExportDirMissing; print('imports OK')"` prints `imports OK` from inside `crmbuilder-v2/`.

### Step 2 — Add `CRMBUILDER_V2_EXPORT_DIR` env var to Settings

Edit `crmbuilder-v2/src/crmbuilder_v2/config.py`:

- The `Settings` class currently has `db_path: Path` declared with a default and the `env_prefix = "CRMBUILDER_V2_"` mechanism wiring `CRMBUILDER_V2_DB_PATH` env var to it. The class also has `export_dir: Path` declared at lines 32-38.
- Confirm: `export_dir` is currently declared with a default but NOT bound to the env var. (Investigation §B notes: "A full grep for `CRMBUILDER_V2_EXPORT_DIR` returns no results in the source tree.")
- The standard pydantic-settings env_prefix mechanism binds any declared field automatically — verify by reading the field declarations vs how `db_path` is declared. If `export_dir` is declared identically to `db_path`, the env var binding is already there for the asking; the bug was that nothing in the codebase ever set the env var.
- Whatever the current binding state, ensure `Settings.export_dir` resolves from `CRMBUILDER_V2_EXPORT_DIR` env var when set, and falls back to the existing default otherwise. Treat empty string as unset.
- Add a class-level docstring or inline comment noting the sentinel value `__UNCONFIGURED__` is reserved as a valid env var value indicating "operator hasn't configured export_dir; writes should fail loud."

**Acceptance:** Write a one-off Python script in `/tmp/test_export_env.py` that sets `CRMBUILDER_V2_EXPORT_DIR=/tmp/foo`, calls `reset_settings_cache()`, calls `get_settings()`, and asserts `settings.export_dir == Path("/tmp/foo")`. Run from inside `crmbuilder-v2/`. Should print `OK`. Clean up the file after.

### Step 3 — Create `runtime/engagement_routing.py` with the three helpers

Create `crmbuilder-v2/src/crmbuilder_v2/runtime/engagement_routing.py` containing three public functions plus one private module-level constant.

**Constant.** `UNCONFIGURED_SENTINEL = "__UNCONFIGURED__"`.

**Function 1.** `resolve_active_engagement() -> str | None`:

- Computes `marker_path = data_dir() / "current_engagement.json"` using `access.meta_db.data_dir()`.
- If `marker_path` doesn't exist, returns `None`.
- If it exists, opens and parses JSON. Returns the value at key `"engagement_code"` (or whatever key the v0.5 migration writes; read `migration/lazy_migration.py` or `ui/active_engagement_context.py` to confirm the exact key name).
- If JSON parse fails, returns `None` and logs a warning. (Better to fail loud at routing time than to misroute on corrupt marker; the caller decides what to do with None.)

**Function 2.** `route_settings_to_engagement(code: str) -> None`:

- Queries the meta DB for the engagement record matching `code`. Use the existing repository function (likely `access.engagement.get_engagement_by_code(code)` or equivalent — confirm by reading `access/engagement.py`).
- If no record, raises `UnknownEngagementError(code=code, available_codes=<list from meta DB>)`.
- Computes `db_path = engagement_db_path(code)` via `migration.lazy_migration.engagement_db_path`.
- Sets `os.environ["CRMBUILDER_V2_DB_PATH"] = str(db_path)`.
- If `engagement_export_dir` on the record is a non-empty string, sets `os.environ["CRMBUILDER_V2_EXPORT_DIR"]` to that value. Otherwise sets it to `UNCONFIGURED_SENTINEL`.
- Calls `config.reset_settings_cache()`.
- Calls `access.db.reset_engine_cache()`.
- Conditionally calls `access.meta_db.reset_meta_engine_cache()` — only if the new `data_dir()` differs from the previous `data_dir()` (use the previous `Settings` instance before resetting). For first-time routing in a fresh process this is moot; for re-routing within a long-running UI process this matters.
- Calls `access.meta_db.init_meta_db_pool()` to re-init pools against the new state.

**Function 3.** `assert_export_dir_ready(s: Settings) -> None`:

- Reads `s.export_dir`.
- If `str(s.export_dir)` equals `UNCONFIGURED_SENTINEL` (or `Path(UNCONFIGURED_SENTINEL)`), raises `EngagementExportDirNotConfigured(code=<active engagement code from marker, if available>)`.
- If `s.export_dir` is a Path that does not exist as a directory on disk (`s.export_dir.is_dir()` is False), raises `EngagementExportDirMissing(code=<active engagement code from marker>, path=s.export_dir)`.
- Otherwise returns None silently.

Imports needed: `from ..config import Settings, reset_settings_cache`; `from ..access import db as access_db`; `from ..access import meta_db`; `from ..access import engagement as engagement_repo`; `from ..migration.lazy_migration import engagement_db_path`; `from .exceptions import UnknownEngagementError, EngagementExportDirNotConfigured, EngagementExportDirMissing`. Adjust import paths to match the actual codebase layout.

**Acceptance:** `uv run python -c "from crmbuilder_v2.runtime.engagement_routing import resolve_active_engagement, route_settings_to_engagement, assert_export_dir_ready; print('OK')"` from inside `crmbuilder-v2/`.

### Step 4 — Wire `cli.py:run_api()` to use the helpers + add `--engagement` flag

Edit `crmbuilder-v2/src/crmbuilder_v2/cli.py`:

The current `run_api()` (lines 17-49 per the investigation):
1. Calls `needs_migration()` and runs migration if so.
2. Calls `get_settings()` (returns lru-cached Settings instance).
3. Hands `create_app()` to uvicorn.

Replace with the following sequence (preserving the migration step):

1. Parse CLI args via `argparse`. Single optional flag: `--engagement` (string, default None). Define a clear `--help` describing the flag.
2. Run the migration check (`needs_migration()` → `run_migration()`) — unchanged.
3. Determine the active engagement:
   - If `--engagement <code>` was passed: use that code. Also call `resolve_active_engagement()`; if the marker exists and disagrees, emit a yellow-flagged stderr message: `"--engagement <flag> overrides current_engagement.json (<marker>)"` (use ANSI escape codes for color, or skip color if not a TTY). If marker agrees, no log line.
   - Else: call `resolve_active_engagement()`. If it returns a code, use it. If None, fail loud per DEC-108.
4. Call `route_settings_to_engagement(active_code)`:
   - If it raises `UnknownEngagementError`: render the error message (`"Unknown engagement '<code>'. Available: <comma-separated codes>."` or, if the marker was the source, `"Active engagement '<code>' not found in meta DB. Activate a valid engagement via the desktop UI or pass --engagement <code>."`). Print to stderr. Exit with code 2.
5. Call `get_settings()` — now picks up the routed env vars.
6. Hand to uvicorn — unchanged.

Failure path: write the error message to stderr, also print to stdout so the UI subprocess capture sees it, then `sys.exit(2)`.

**Acceptance:**
- `uv run crmbuilder-v2-api --help` shows the new `--engagement` flag with its description.
- Without `current_engagement.json` and no flag: exits with code 2 and the fail-loud message (test from a temp directory). Set `CRMBUILDER_V2_DATA_DIR` or whatever the env var is that controls `data_dir()` to a fresh tmp path with an empty engagements meta DB to simulate.

### Step 5 — Apply the gate at `session_scope` and `force_export`

Edit `crmbuilder-v2/src/crmbuilder_v2/access/db.py`:

- At `session_scope` (line ~93-102 area, immediately before the `staging = write_staging(snapshot, s.export_dir)` line): insert `assert_export_dir_ready(s)`.
- At `force_export` (line ~137 area, immediately before `staging = write_staging(snapshot, s.export_dir)`): insert `assert_export_dir_ready(s)`.
- Import: `from ..runtime.engagement_routing import assert_export_dir_ready`.

The gate raises before any side effect to disk, so `write_staging` does not run on a misconfigured engagement. The DB transaction in `session_scope` should still roll back on exception per existing context-manager semantics — verify by reading the current `session_scope` exception-handling code.

**Acceptance:** Create a one-off Python script in `/tmp` that opens `session_scope` with `CRMBUILDER_V2_EXPORT_DIR=__UNCONFIGURED__`. Assert the context manager raises `EngagementExportDirNotConfigured`. Clean up.

### Step 6 — Apply the gate at the catalog exporter

Edit `crmbuilder-v2/src/crmbuilder_v2/access/repositories/catalog/exports.py`:

- The function returning `s.export_dir / "catalog" / "entities"` at line 57-59 (investigation §G.1) is the gate point. Before computing the path, call `assert_export_dir_ready(s)`.
- Import: `from ...runtime.engagement_routing import assert_export_dir_ready`. (Adjust import depth to match the actual nesting.)

**Acceptance:** Run any existing catalog test that exercises export. With the gate in place and an unconfigured Settings, the test should raise `EngagementExportDirNotConfigured`. Update the test fixture to set `engagement_export_dir` if needed.

### Step 7 — Investigate `bootstrap/migrate.py:64` and apply the appropriate fix

Read `crmbuilder-v2/src/crmbuilder_v2/bootstrap/migrate.py` lines 50-80 (broad context around line 64). The `settings.export_dir.parent` usage is described in investigation §G.3 as "probably engine-scoped."

Decision tree:

- If the path is engine-scoped (always derives a path under the engine repo regardless of which engagement is active, e.g., the v0.1 bootstrap import that reads from `PRDs/product/crmbuilder-v2/` directly): replace `settings.export_dir.parent` with a hardcoded path expression (e.g., compute the engine repo root from `__file__`). Add a comment explaining the path is engine-scoped, not engagement-scoped. Do NOT apply the gate — this isn't a per-engagement write path.
- If the path is engagement-scoped (consumes per-engagement content): keep the `settings.export_dir.parent` reference but add `assert_export_dir_ready(s)` before computing the path. Treat it as another consumer site like §G.1 and §G.2.

Document which branch was taken in the commit message.

**Acceptance:** No regressions in any test that exercises `bootstrap/migrate.py`. If no test exercises it, manually verify by tracing the call graph: which caller(s) invoke this function, and what happens to them under the changed code path?

### Step 8 — Write new tests

Create the following test files. Each test uses pytest fixtures for isolation.

**`crmbuilder-v2/tests/crmbuilder_v2/runtime/__init__.py`** — empty.

**`crmbuilder-v2/tests/crmbuilder_v2/runtime/test_engagement_routing.py`** — at minimum:

- `test_resolve_no_marker_returns_none`
- `test_resolve_valid_marker_returns_code`
- `test_resolve_corrupt_marker_returns_none_and_warns`
- `test_route_unknown_code_raises_UnknownEngagementError`
- `test_route_valid_code_sets_db_path_env_var`
- `test_route_engagement_with_export_dir_sets_export_dir_env_var`
- `test_route_engagement_with_null_export_dir_sets_sentinel`
- `test_route_engagement_with_empty_string_export_dir_treated_as_null`
- `test_route_resets_settings_cache_so_subsequent_get_settings_reflects_change`
- `test_route_twice_to_different_engagement_reflects_second_engagement_after_caches_reset`

**`crmbuilder-v2/tests/crmbuilder_v2/runtime/test_export_gate.py`** — at minimum:

- `test_assert_ready_with_unconfigured_sentinel_raises_EngagementExportDirNotConfigured`
- `test_assert_ready_with_nonexistent_path_raises_EngagementExportDirMissing`
- `test_assert_ready_with_existing_directory_returns_none`
- `test_assert_ready_with_empty_string_export_dir_treats_as_unconfigured` (verify whatever interpretation Settings applies)

**`crmbuilder-v2/tests/crmbuilder_v2/api/test_cli_engagement_flag.py`** — at minimum (use `subprocess.run` to invoke the actual CLI binary):

- `test_no_marker_no_flag_fails_loud_exit_2`
- `test_marker_only_starts_normally` (note: this test starts a real uvicorn briefly; consider a fast-exit mechanism or use `--check-only` flag if you add one; otherwise mark `@pytest.mark.slow` and use a short SIGTERM)
- `test_flag_overrides_marker_with_log_line`
- `test_flag_matches_marker_no_log_line`
- `test_bogus_flag_fails_loud_exit_2_with_available_codes`
- `test_bogus_marker_fails_loud_exit_2`

For tests that need a real meta DB, use the existing v2 test fixture pattern (search the repo for existing `meta_db` test fixtures — there's likely a `conftest.py` that sets up a temp data dir with engagements).

Update existing tests that exercise `session_scope`, `force_export`, or the catalog exporter to ensure their fixtures set `engagement_export_dir` to a valid existing directory (or to expect the new exceptions when null).

**Acceptance:** `uv run pytest tests/crmbuilder_v2/runtime/ -v` and `uv run pytest tests/crmbuilder_v2/api/test_cli_engagement_flag.py -v` both green.

### Step 9 — Run the full test suite

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -50
cd ..
```

Stop and report any failures.

If green, proceed to commit.

---

## Acceptance gate

Before committing, verify every acceptance criterion from §5 slice A of the slice plan:

- A1 — A13 as enumerated. Walk through each.
- The bootstrap/migrate.py finding documented for the commit message.
- The full test suite passes (`uv run pytest tests/crmbuilder_v2/ -v` returns 0 with no failures).

---

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/runtime/
git add crmbuilder-v2/src/crmbuilder_v2/cli.py
git add crmbuilder-v2/src/crmbuilder_v2/config.py
git add crmbuilder-v2/src/crmbuilder_v2/access/db.py
git add crmbuilder-v2/src/crmbuilder_v2/access/repositories/catalog/exports.py
git add crmbuilder-v2/src/crmbuilder_v2/bootstrap/migrate.py   # only if changed
git add crmbuilder-v2/tests/crmbuilder_v2/runtime/
git add crmbuilder-v2/tests/crmbuilder_v2/api/test_cli_engagement_flag.py
# plus any existing tests that needed fixture updates

git status   # confirm only expected files staged
```

Commit message:

```
v2: multi-tenancy routing fix slice A — helpers, gate, CLI flag, fail-loud

Resolves Bug 1 (API startup ignores current_engagement.json) and
Bug 2 (export hook writes to wrong engagement's export_dir) on the
CLI-launched API path. UI-launched API continues working on the
existing inline path; slice B refactors the UI to use these helpers.

New module crmbuilder_v2.runtime with:
- resolve_active_engagement() — single resolver for the marker file
- route_settings_to_engagement(code) — env-var set + cache reset
- assert_export_dir_ready(s) — gate raising on unconfigured/missing

New exceptions:
- UnknownEngagementError
- EngagementExportDirNotConfigured
- EngagementExportDirMissing

Settings env var addition:
- CRMBUILDER_V2_EXPORT_DIR (sibling of CRMBUILDER_V2_DB_PATH)

CLI changes (cli.py:run_api):
- Adds --engagement <code> flag (DEC-111); flag wins over marker
  with yellow log line on disagreement; flag is ephemeral, does
  not persist to current_engagement.json
- Resolves active engagement via resolve_active_engagement()
- Routes via route_settings_to_engagement() before reading Settings
- Fails loud (exit 2) when no active engagement is available
  (DEC-108): "No active engagement. Activate one via the desktop
  UI's Engagements panel, or pass --engagement <code> when running
  the API standalone."

Gate application sites (DEC-113):
- access/db.py:session_scope — before write_staging
- access/db.py:force_export — before write_staging
- access/repositories/catalog/exports.py — at the path-return site

bootstrap/migrate.py investigation outcome:
- {DESCRIBE: engine-scoped (hardcoded path) OR engagement-scoped (gated)}

Failure semantics (DEC-109, DEC-114):
- Null engagement_export_dir in meta DB -> sentinel
  __UNCONFIGURED__ -> EngagementExportDirNotConfigured on write
- Set engagement_export_dir but path missing on disk ->
  EngagementExportDirMissing on write
- Subdirectories below the configured root continue to be
  auto-created with mkdir(parents=True, exist_ok=True)

Tests added:
- tests/crmbuilder_v2/runtime/test_engagement_routing.py — 10 cases
- tests/crmbuilder_v2/runtime/test_export_gate.py — 4 cases
- tests/crmbuilder_v2/api/test_cli_engagement_flag.py — 6 cases
- Existing fixtures updated for the new gate behavior

Full regression: uv run pytest tests/crmbuilder_v2/ -v passes.

Slice B follows: UI refactor of _route_api_at_active_engagement to
use these helpers, plus operator-facing affordances (warning bands
on Open Engagement when export_dir is null or missing, dialog field
emphasis, error-dialog handling).

Refs SES-044, DEC-108..DEC-111, DEC-113, DEC-114, PI-018.
```

Doug pushes.

---

## Done

After commit lands and Doug pushes:

- CLI-launched API is fully fixed.
- UI-launched API continues working unchanged.
- The slice B prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-B-ui-refactor-affordances.md` is ready for a separate build conversation to execute.

**Next build step:** slice B. Opens against the slice B prompt in a fresh Claude Code session.
