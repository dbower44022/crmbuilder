# Multi-tenancy Routing — Investigation Report

**Last Updated:** 05-19-26 13:00
**Status:** Investigation complete. Input to the multi-tenancy routing fix planning conversation.
**Companion:** `multi-tenancy-routing-fix-planning-kickoff.md` (the planning conversation that consumes this report).
**Origin:** Produced by Claude Code on 05-19-26 from a read-only investigation prompted by two related bugs surfacing during the SES-001 paper-test apply attempt.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-19-26 13:00 | Doug Bower / Claude (Code) | Initial capture of Claude Code's investigation output. Light Markdown polish only — content unchanged from the source diagnostic. |

---

## Context — what happened

The slice D multi-tenancy work introduced per-engagement DBs at `crmbuilder-v2/data/engagements/{engagement_code}.db` and a meta DB at `crmbuilder-v2/data/engagements.db`. The desktop UI's "Open Engagement" flow writes `crmbuilder-v2/data/engagements/current_engagement.json` to record which engagement is currently selected. CRMBUILDER.db (3.1MB) and CBM.db (401KB) both exist and are correctly populated.

Two bugs surfaced during today's SES-001 paper-test apply attempt:

**Bug 1 — API ignores `current_engagement.json` and connects to legacy `v2.db` on startup.** After restarting the API via plain shell (`uv run crmbuilder-v2-api &`), GET requests like `/sessions` return `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: sessions`. Direct inspection of `crmbuilder-v2/data/v2.db` shows zero tables — it's an empty SQLite file. The API defaulted to it instead of routing to either CRMBUILDER.db or CBM.db per `current_engagement.json` (which correctly said CRMBUILDER, `set_at` 2026-05-19T15:55:17). The desktop UI presumably starts the API some other way that triggers per-engagement routing; the plain-shell `uv run` path does not.

**Bug 2 — Export hook writes snapshots to the wrong engagement's `engagement_export_dir`.** During the SES-001 apply (when CBM was active), the export hook rendered CBM's content into the dogfood CRMBUILDER engagement's `engagement_export_dir` (`PRDs/product/crmbuilder-v2/db-export/`), clobbering CRMBUILDER's snapshots. CBM's `engagement_export_dir` (`/home/doug/Dropbox/Projects/ClevelandBusinessMentors/PRDs/methodology-records/db-export`) received nothing. DB-layer writes routed correctly (CBM.db got the records); the render layer did not. Working tree damage was recovered via `git checkout HEAD --` in the crmbuilder repo. CBM.db retains the records (SES-001 / DEC-001..003 / PI-001 / 3 refs).

Likely shared root cause: the slice D refactor wired multi-tenancy at the DB-write path but missed two adjacent paths (API startup DB selection; export-hook render-target selection). Both default to the legacy single-tenant path / ENG-001's `engagement_export_dir`.

---

## A. API startup DB resolution

Code path:

1. `pyproject.toml` `[project.scripts]` → `crmbuilder-v2-api = "crmbuilder_v2.cli:run_api"`.
2. `crmbuilder-v2/src/crmbuilder_v2/cli.py:17-49` — `run_api()`:
   - Calls `needs_migration()` (`migration/dogfood_v0_5.py:127`); runs the one-shot v0.5 migration if it returns True.
   - Calls `get_settings()` (`config.py:48-50`) which returns the lru-cached `Settings()` instance.
   - Hands `create_app()` to `uvicorn.run(..., host=settings.api_host, port=settings.api_port)`.
3. `config.py:22-46` — `Settings`:
   - `db_path` default: `<repo>/crmbuilder-v2/data/v2.db` (lines 29-31).
   - `export_dir` default: `<repo>/PRDs/product/crmbuilder-v2/db-export` (lines 32-38).
   - `db_url` property: `f"sqlite:///{self.db_path}"` (lines 43-45).
   - All four fields are overridable via `CRMBUILDER_V2_*` env vars (env_prefix at line 24).
4. `access/db.py:37-45` — `get_engine()` caches an engine built from `s.db_url`.

**Why today's plain-shell restart landed on v2.db.** `cli.py:run_api()` never reads `current_engagement.json`. It reads Settings defaults plus any `CRMBUILDER_V2_*` env vars present in the shell that launched it. With `CRMBUILDER_V2_DB_PATH` unset, `Settings.db_path` falls back to `<repo>/crmbuilder-v2/data/v2.db`.

Post-v0.5 migration, `dogfood_v0_5.py:336-339` deletes the legacy `v2.db` after copying its contents to `engagements/CRMBUILDER.db` (backup retained at `v2.db.pre-v0.5-backup`). SQLAlchemy + SQLite auto-create an empty file on connection when the configured path doesn't exist — hence today's "no such table: sessions". `needs_migration()` (`dogfood_v0_5.py:135-137`) returns True only when `v2.db.exists()` AND NOT `engagements/CRMBUILDER.db.exists()`; once the post-migration state is reached the gate is False so the migration doesn't re-run.

**Why the desktop UI works and the CLI does not.** `ui/app.py:226-253` — `_route_api_at_active_engagement(active, log)` reads the current engagement code from `ActiveEngagementContext` (which itself loaded `current_engagement.json` at `ui/active_engagement_context.py:32-34, 85-138`), computes `engagement_db_path(code)` (`migration/lazy_migration.py:43-51`), sets `os.environ["CRMBUILDER_V2_DB_PATH"]` to that path, and calls `reset_settings_cache()` + `reset_engine_cache()` so the next `get_settings()` picks up the override. The UI does this before spawning the API subprocess, so the subprocess inherits the env var. The CLI `crmbuilder-v2-api` skips this entire step.

---

## B. Export hook render-target resolution

Code path:

1. `access/db.py:64-117` — `session_scope()` is the atomic write context manager.
   - Line 93: `s = settings or get_settings()`.
   - Line 102: `staging = write_staging(snapshot, s.export_dir)`.
2. `access/db.py:120-140` — `force_export()` mirrors the same pattern at line 137.
3. `access/exporter.py:113-129` — `write_staging(snapshot, export_dir)` writes `.json.tmp` files into the directory given.
4. `config.py:32-38` — `Settings.export_dir` default: `<repo>/PRDs/product/crmbuilder-v2/db-export`.

**What is missing.** The exporter never reads the meta DB. There is no code path anywhere in `access/exporter.py`, `access/db.py`, `access/engagement.py`, `api/main.py`, `api/deps.py`, or `migration/lazy_migration.py` that consults `engagement_export_dir` from the active engagement's row in the meta DB and overrides `Settings.export_dir`.

A full grep for `Settings.export_dir` / `s.export_dir` / `settings.export_dir` returns these consumers — none of which routes per-engagement:

- `access/db.py:102`  →  `staging = write_staging(snapshot, s.export_dir)`
- `access/db.py:137`  →  `staging = write_staging(snapshot, s.export_dir)`
- `access/repositories/catalog/exports.py:59`  →  `return s.export_dir / "catalog" / "entities"`
- `bootstrap/migrate.py:64`  →  `return settings.export_dir.parent`
- `ui/about_dialog.py:148`  →  `("Snapshot directory", str(settings.export_dir))`

A full grep for `CRMBUILDER_V2_EXPORT_DIR` returns no results in the source tree — there is no env var override path equivalent to `CRMBUILDER_V2_DB_PATH`.

`access/meta_exporter.py:21-37` — `meta_export_dir()` is hardcoded to the engine repo's `db-export/meta/` by design (the meta DB is per-install, not per-engagement, so its snapshot correctly lives with the engine). That's intentional, not a bug.

**Why CBM's contents wrote into CRMBUILDER's export_dir today.** When the UI activated CBM, `_route_api_at_active_engagement` set `CRMBUILDER_V2_DB_PATH=…/engagements/CBM.db` and reset caches. The next `get_settings()` returned a fresh Settings. Because `CRMBUILDER_V2_EXPORT_DIR` was not set (no code anywhere sets it), `Settings.export_dir` fell back to the default `<repo>/PRDs/product/crmbuilder-v2/db-export` — which happens to be CRMBUILDER's configured `engagement_export_dir`. So when the SES-001 apply committed against CBM.db, the post-flush snapshot was correctly built from CBM.db but written to CRMBUILDER's path. **This would happen identically under the desktop-UI-launched API; it isn't specific to the plain-shell start path.**

---

## C. Shared resolver or duplicated logic

There is no single resolver for "the active engagement at runtime." The concept is computed in two places, with no shared helper:

1. **UI side** — `ui/active_engagement_context.py` — `ActiveEngagementContext` Qt object reads `current_engagement.json` on construction, exposes `engagement_code()` and `active_engagement_changed(object)` Signal. PySide6-coupled; not callable from headless CLI.
2. **CLI side** — does not resolve. `run_api()` in `cli.py:17-49` reads Settings (which pulls from env vars or defaults) and starts uvicorn. The active engagement is implicit in whatever env var the launching process happens to have set.

Within the access layer, "active engagement" is encoded only in `Settings.db_path`, and only when something upstream has set `CRMBUILDER_V2_DB_PATH`. The exporter, the catalog exports module, and the about dialog all read `Settings.export_dir` directly with no per-engagement awareness.

`access/meta_db.py:29-52` — `data_dir()` papers over the post-activation `Settings.db_path` shape (with `data/engagements/` parent) versus the legacy `data/` shape, to keep meta-DB lookups stable. This is the closest thing to a multi-tenancy-aware shared helper, but its concern is only "where is data/", not "which engagement is active right now."

---

## D. Runtime engagement switch capability

The API server runs against a single Settings instance per process. Switching the active engagement after launch requires:

- New env var value for `CRMBUILDER_V2_DB_PATH`.
- `reset_settings_cache()` from `config.py:53-55`.
- `reset_engine_cache()` from `access/db.py:54-61`.
- `reset_meta_engine_cache()` from `access/meta_db.py:90-97` (only if the meta DB pool was bound to a stale path, which can happen because `meta_db_path()` derives from `data_dir()` which derives from `Settings.db_path`).
- Re-init pools via `init_meta_db_pool()`.

These hooks exist but there is no API endpoint that triggers them. The UI calls them in-process during `_route_api_at_active_engagement` (`ui/app.py:226-253`) before spawning the API subprocess, so the subprocess starts with the new env var baked in. After that, switching engagements requires restarting the API subprocess.

**Correct startup invocation that wires per-engagement routing properly today: the UI's spawn path is the only one.** There is no documented standalone-CLI equivalent. The closest is:

```bash
CRMBUILDER_V2_DB_PATH=$(python3 -c "from crmbuilder_v2.migration.lazy_migration import engagement_db_path; print(engagement_db_path('CBM'))") \
  uv run crmbuilder-v2-api
```

… but that still won't fix Bug 2 — it routes the DB connection correctly but `Settings.export_dir` still resolves to the global default, so writes against CBM.db will still clobber CRMBUILDER's snapshots.

---

## E. Proposed fix paths

### Bug 1 fix — API startup DB resolution

**Approach.** Extract a single shared helper `resolve_active_engagement() → str | None` that reads `current_engagement.json` from `data_dir() / "current_engagement.json"` (the same path the migration writes to and the UI reads from) and returns the active engagement code. Add a partner helper `route_settings_to_engagement(code) -> None` that wraps the env-var-set + cache-reset pattern currently inlined in `ui/app.py:226-253`. Update `cli.py:run_api()` so the lines:

```python
# pseudo
if needs_migration():
    ...
# NEW: route to active engagement before reading settings
active_code = resolve_active_engagement()
if active_code is not None:
    route_settings_to_engagement(active_code)
settings = get_settings()
```

Update `ui/app.py:_route_api_at_active_engagement` to call the new shared helpers instead of duplicating the logic.

**Failure mode coverage.** Fresh install: `current_engagement.json` missing → helper returns None → no override → CLI falls back to the legacy default which `needs_migration()` will have just migrated away from. Need to decide what fresh-install should do here — either auto-pick the lone engagement if there's exactly one, or fail loudly with a "no active engagement" error.

**Slice count:** 1 slice. Maybe 1.5 if the fresh-install behavior gets its own design decision.

### Bug 2 fix — Per-engagement export_dir resolution

**Approach.** When `route_settings_to_engagement(code)` runs (the helper from Bug 1's fix), it should also look up `engagement_export_dir` from the meta DB for `code` and set `CRMBUILDER_V2_EXPORT_DIR` (or directly override `Settings.export_dir`) before the cache reset. Logic:

```python
# pseudo
meta_row = get_engagement(code)  # exists in access/engagement.py
if meta_row.engagement_export_dir:
    os.environ["CRMBUILDER_V2_EXPORT_DIR"] = meta_row.engagement_export_dir
else:
    os.environ.pop("CRMBUILDER_V2_EXPORT_DIR", None)
    # falls back to Settings default — operator hasn't configured export_dir
reset_settings_cache()
reset_engine_cache()
```

This requires no change to `access/db.py` or `access/exporter.py` — they continue reading `Settings.export_dir`, but now Settings re-resolves with the new env var on each `get_settings()` post-reset.

**Edge cases.** Engagement has `engagement_export_dir = None`: writes should either fail loudly (preventing the silent fallback to ENG-001's dir, which is what bit us today) or fall back to a per-engagement scratch dir under `data/engagements/{code}/db-export/`. Today's behavior — silently fall back to global default — is the bug; the safest replacement is to refuse the write until `engagement_export_dir` is set.

**Slice count:** 1 slice if it ships alongside Bug 1's helper. 2 slices if the "no export_dir → refuse vs fall back" decision is deferred to a separate planning conversation.

---

## F. Shared workstream framing

**Single workstream, single planning conversation.** The two bugs share a root cause (no shared "active engagement" resolver; multi-tenancy was only half-wired in slice D) and a single fix shape (the new `resolve_active_engagement` + `route_settings_to_engagement` helpers handle both). Splitting the workstream would force the second fix to either duplicate the first fix's helper or wait on it, and the planning conversation will want to resolve both bugs' edge-case questions (fresh-install behavior; no-export_dir behavior) together.

**Proposed planning item title:** "Complete v0.5 multi-tenancy routing: API startup engagement resolution + per-engagement export_dir."

**Scope:** Bug 1 + Bug 2 fixes per section E; refactor `ui/app.py:_route_api_at_active_engagement` to use the new shared helpers; failing-loud behavior decided for fresh-install and missing-export_dir cases; backfill an `--engagement <code>` arg on `crmbuilder-v2-api` for ops use; tests for both routing paths.

**Slice count estimate:** 2 slices. Slice A — extract helpers, route in CLI, fix both env vars; tests. Slice B — UI refactor to use shared helpers, edge-case behavior decisions, integration tests against a two-engagement state.

---

## G. Anything else found

1. **Catalog exports same gap.** `access/repositories/catalog/exports.py:57-59` returns `s.export_dir / "catalog" / "entities"` for catalog snapshots — same per-engagement-blindness as Bug 2. Any catalog write under CBM would also clobber CRMBUILDER's catalog snapshots. Would be fixed by the same Bug 2 fix because the consumer reads `Settings.export_dir`.
2. **`force_export()` same gap.** `access/db.py:120-140` has the same gap as `session_scope()`. It is currently safe because nothing calls it routinely in production paths, but any recovery / manual-snapshot-regenerate operation would hit the bug too. Same fix.
3. **`bootstrap/migrate.py:64`** uses `settings.export_dir.parent` to derive a markdown-source location for the initial-bootstrap import. Probably engine-scoped and not engagement-scoped, but worth confirming during the planning conversation — if it consumes per-engagement content, it has the same bug.
4. **`about_dialog.py:148`** displays `Settings.export_dir` to the user as the "Snapshot directory." After the fix, this string will change depending on active engagement — fine, but worth noting for the UI behavior.
5. **No `--engagement` flag on `crmbuilder-v2-api`.** The CLI accepts no arguments at all. For ops convenience (and for the apply prompts we ran today), an explicit `--engagement CBM` flag would be useful so operators can verify routing without setting an env var manually.
6. **No `/active-engagement` endpoint.** The apply prompt assumed `/active-engagement` exists for pre-flight verification; it doesn't. The OpenAPI surface only exposes `/engagements` and `/engagements/{id}`. Worth either adding `/active-engagement` or `/admin/runtime-info` to surface this without needing to read `current_engagement.json` directly. Marginal — file as a quality-of-life follow-on, not load-bearing.
7. **The export hook silently creates empty directories.** `access/exporter.py:115` calls `export_dir.mkdir(parents=True, exist_ok=True)` before writing — so today's behavior of silently writing to the wrong location is doubly insidious: it not only writes to the wrong place, it auto-creates the wrong directory tree if needed. After the fix the helper should fail-loud rather than auto-create, OR the access layer should validate `engagement_export_dir` against an allow-list at write time.

---

## What the investigation did NOT do

- Did not modify any source file.
- Did not run the API or post to it.
- Did not commit or stash.
- Did not run the proposed fix; section E describes it only.
- Did not investigate cross-engagement references, snapshot replay/restore, or engagement deletion.

---

*End of document.*
