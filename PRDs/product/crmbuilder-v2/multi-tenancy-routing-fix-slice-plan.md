# Multi-tenancy Routing Fix — Slice Plan

**Version:** 1.0
**Last Updated:** 05-19-26 16:00
**Status:** Approved — build conversations may open against the per-slice prompts.
**Companions:**
- `multi-tenancy-routing-investigation-report.md` — the diagnostic input.
- `multi-tenancy-routing-fix-planning-kickoff.md` — the planning conversation kickoff that produced this plan.
- `prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-A-helpers-cli-gate.md` — slice A executable prompt.
- `prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-B-ui-refactor-affordances.md` — slice B executable prompt.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-19-26 16:00 | Doug Bower / Claude (Claude.ai) | Initial approved plan produced by the SES-044 planning conversation. Seven architectural decisions (DEC-108..114) settled; two-slice build plan. |

---

## 1. Purpose

This plan converts the seven architectural decisions taken in the SES-044 planning conversation into an executable two-slice build plan. The slices fix the two multi-tenancy routing bugs surfaced during the SES-001 paper-test apply attempt on 05-19-26 (Investigation Report §A and §B):

- **Bug 1.** The CLI-launched API ignores `current_engagement.json` and connects to the post-migration empty `v2.db`. UI-launched API works only because the UI's `_route_api_at_active_engagement` (`ui/app.py:226-253`) inlines the env-var-set + cache-reset pattern before spawning the subprocess. There is no shared helper.
- **Bug 2.** The export hook writes snapshots against `Settings.export_dir` which resolves engagement-blindly to the engine-repo default. Under any non-CRMBUILDER engagement, writes silently clobber CRMBUILDER's `db-export/`. Same gap exists in `force_export()` and `access/repositories/catalog/exports.py`.

This plan addresses both bugs with one shared fix: extract two helpers (`resolve_active_engagement`, `route_settings_to_engagement`) that the CLI calls at startup and the UI calls during engagement activation. Apply a centralized gate (`assert_export_dir_ready`) at every active export-write path. Add `--engagement <code>` as a CLI flag, plus the supporting fail-loud error messaging.

Out of scope: cross-engagement references, snapshot replay/restore, engagement deletion, and the `/admin/runtime-info` diagnostic API endpoint (deferred per DEC-112).

---

## 2. Architectural decisions

The seven Phase 1 decisions from SES-044 are recorded as DEC-108 through DEC-114. The plan assumes their outcomes throughout; references back to each decision identify which slice executes the outcome.

| Decision | Outcome | Executed in |
|---|---|---|
| DEC-108 — Fresh-install behavior with no marker | Fail loud always; no auto-pick | Slice A |
| DEC-109 — Missing `engagement_export_dir` in meta DB | Refuse the write; new `EngagementExportDirNotConfigured` exception | Slice A |
| DEC-110 — Plumbing model | Env var + cache reset (matches existing pattern); `CRMBUILDER_V2_EXPORT_DIR` added to Settings | Slice A |
| DEC-111 — `--engagement <code>` CLI flag | Land in slice A; flag wins over marker; ephemeral (does not persist to marker) | Slice A |
| DEC-112 — `/admin/runtime-info` endpoint | Defer entirely; file follow-on PI if needed | (deferred) |
| DEC-113 — Catalog / force_export / bootstrap scope | Centralized gate at all active write paths via `assert_export_dir_ready` helper | Slice A |
| DEC-114 — Fail-loud vs auto-create on missing dir | Fail loud if engagement_export_dir doesn't exist on disk; new `EngagementExportDirMissing` exception | Slice A |

---

## 3. Implementation choices

Choices that follow from prior decisions and do not warrant their own decision record are recorded here for traceability.

**Helper module location.** `resolve_active_engagement()` and `route_settings_to_engagement(code)` live in a new module `crmbuilder-v2/src/crmbuilder_v2/runtime/engagement_routing.py`. The `runtime/` package is new for this slice — it captures cross-cutting startup-and-routing concerns that don't belong in `access/`, `api/`, or `migration/`. `assert_export_dir_ready(s)` lives in the same module since it's the export-side complement to `route_settings_to_engagement`.

**Exception module location.** New exceptions live in `crmbuilder-v2/src/crmbuilder_v2/runtime/exceptions.py`:

- `UnknownEngagementError` — raised by `route_settings_to_engagement` when the code isn't in the meta DB.
- `EngagementExportDirNotConfigured` — raised at write time when `engagement_export_dir` is null in the meta DB.
- `EngagementExportDirMissing` — raised at write time when `engagement_export_dir` is set but doesn't exist as a directory on disk.

The export-side exceptions are sibling subclasses of a new base `EngagementExportDirError` so `session_scope`, `force_export`, and the catalog write path can catch the umbrella class if they need to.

**Settings env var addition.** `CRMBUILDER_V2_EXPORT_DIR` is added to `crmbuilder-v2/src/crmbuilder_v2/config.py` as a sibling of `CRMBUILDER_V2_DB_PATH` using the same `env_prefix` mechanism (line 24). Empty string is treated as unset throughout.

**Unconfigured sentinel value.** When `engagement_export_dir` is null in the meta DB, `route_settings_to_engagement` sets `CRMBUILDER_V2_EXPORT_DIR` to the literal string `__UNCONFIGURED__`. Any export-write path checks for this sentinel via `assert_export_dir_ready` before writing. About_dialog's display path renders the sentinel as `(not configured)` for human consumption.

**CLI argparse.** `crmbuilder-v2/src/crmbuilder_v2/cli.py:run_api()` gains an `argparse` step parsing `--engagement <code>` (optional, string). When present, it wins over the marker file and emits a yellow log line if both are set and disagree. When absent, the marker file drives. When neither is set, fail loud per DEC-108.

**bootstrap/migrate.py investigation.** `crmbuilder-v2/src/crmbuilder_v2/bootstrap/migrate.py:64` uses `settings.export_dir.parent` to derive a markdown-source location. Slice A reads the surrounding code; if the path is engine-scoped (always loads from the engine repo regardless of active engagement), hardcode the path and remove the `settings.export_dir.parent` indirection. If engagement-scoped, apply `assert_export_dir_ready` like the other consumers.

**Apply order at runtime.** The helper does its work in this exact order so caches are reset against the final env-var state:

1. Query meta DB for the engagement record (raises `UnknownEngagementError` if missing).
2. Compute per-engagement db_path via `migration.lazy_migration.engagement_db_path(code)`.
3. Set `os.environ["CRMBUILDER_V2_DB_PATH"]` to that path.
4. Set `os.environ["CRMBUILDER_V2_EXPORT_DIR"]` to `engagement_export_dir` if non-null, else `__UNCONFIGURED__`.
5. Call `config.reset_settings_cache()`.
6. Call `access.db.reset_engine_cache()`.
7. Call `access.meta_db.reset_meta_engine_cache()` if `data_dir()` would resolve differently from before.
8. Re-init pools via `access.meta_db.init_meta_db_pool()`.

---

## 4. Directory tree

The new files and edited file locations relative to the crmbuilder repo root:

```
crmbuilder-v2/src/crmbuilder_v2/
├── runtime/                            # NEW PACKAGE
│   ├── __init__.py                     # NEW (empty re-export)
│   ├── engagement_routing.py           # NEW (helpers + gate)
│   └── exceptions.py                   # NEW (3 exceptions + base)
├── cli.py                              # MODIFIED — argparse, resolve+route, fail-loud
├── config.py                           # MODIFIED — CRMBUILDER_V2_EXPORT_DIR env var
├── access/
│   ├── db.py                           # MODIFIED — gate in session_scope and force_export
│   └── repositories/
│       └── catalog/
│           └── exports.py              # MODIFIED — gate at write path
├── bootstrap/
│   └── migrate.py                      # MODIFIED IF engagement-scoped (investigation gates)
└── ui/
    ├── app.py                          # MODIFIED — _route_api_at_active_engagement uses helpers
    ├── about_dialog.py                 # MODIFIED — "(not configured)" / "(missing)" display
    ├── active_engagement_context.py    # MODIFIED — resolve_active_engagement reused
    ├── dialogs/
    │   └── engagement_edit.py          # MODIFIED — null-export_dir field emphasis
    └── panels/
        └── engagements.py              # MODIFIED — Open Engagement warning band

crmbuilder-v2/tests/crmbuilder_v2/
├── runtime/                            # NEW
│   ├── __init__.py                     # NEW
│   ├── test_engagement_routing.py      # NEW
│   └── test_export_gate.py             # NEW
├── api/
│   └── test_cli_engagement_flag.py     # NEW
└── ui/
    └── test_app_engagement_routing.py  # NEW (slice B; uses pytest-qt)
```

The Edit Engagement dialog and Engagements panel file names assume the v0.5 build's actual locations; slice B starts with a code-read to confirm before editing.

---

## 5. Build sequence

### Slice A — Backend: extract helpers, gate, CLI routing

**Scope.** Everything that doesn't touch PySide6 widgets. Builds the helper module, the gate, the new exceptions, the env var, the CLI flag, the fail-loud error path, and the consumer-site fixes. CLI-launched API gets the full fix. UI-launched API continues working on the inline path in `ui/app.py` — slice B refactors the UI to use the new helpers, but the inline path is identical-in-behavior so it doesn't regress.

**File:line touch points.**

| Path | Change |
|---|---|
| `crmbuilder-v2/src/crmbuilder_v2/runtime/__init__.py` | NEW — empty file, makes `runtime/` a package |
| `crmbuilder-v2/src/crmbuilder_v2/runtime/exceptions.py` | NEW — `EngagementError`, `UnknownEngagementError`, `EngagementExportDirError`, `EngagementExportDirNotConfigured`, `EngagementExportDirMissing` |
| `crmbuilder-v2/src/crmbuilder_v2/runtime/engagement_routing.py` | NEW — `resolve_active_engagement()`, `route_settings_to_engagement(code)`, `assert_export_dir_ready(s)` |
| `crmbuilder-v2/src/crmbuilder_v2/config.py:22-46` | EDIT — add `export_dir: Path` env var binding (matches `db_path` pattern) |
| `crmbuilder-v2/src/crmbuilder_v2/cli.py:17-49` | EDIT — argparse `--engagement`, resolve, route, fail loud per DEC-108 |
| `crmbuilder-v2/src/crmbuilder_v2/access/db.py:64-117` | EDIT — `session_scope` calls `assert_export_dir_ready(s)` before `write_staging` |
| `crmbuilder-v2/src/crmbuilder_v2/access/db.py:120-140` | EDIT — `force_export()` calls `assert_export_dir_ready(s)` before `write_staging` |
| `crmbuilder-v2/src/crmbuilder_v2/access/repositories/catalog/exports.py:57-59` | EDIT — gate `assert_export_dir_ready(s)` before returning the snapshot target path |
| `crmbuilder-v2/src/crmbuilder_v2/bootstrap/migrate.py:64` | INVESTIGATE; EDIT IF engagement-scoped (drop `settings.export_dir.parent` if engine-scoped; apply gate if engagement-scoped) |
| `crmbuilder-v2/tests/crmbuilder_v2/runtime/test_engagement_routing.py` | NEW — helper unit tests |
| `crmbuilder-v2/tests/crmbuilder_v2/runtime/test_export_gate.py` | NEW — gate unit tests |
| `crmbuilder-v2/tests/crmbuilder_v2/api/test_cli_engagement_flag.py` | NEW — CLI integration tests |

**Acceptance criteria.**

- A1. `crmbuilder-v2-api` started in a fresh shell with no env vars and no `current_engagement.json` fails loud with exit code 2 and message `"No active engagement. Activate one via the desktop UI's Engagements panel, or pass --engagement <code> when running the API standalone."` Exit happens before uvicorn binds the port.
- A2. `crmbuilder-v2-api` with `current_engagement.json` pointing at a valid code starts normally, with the API serving against the per-engagement DB. `GET /sessions` against CRMBUILDER returns the dogfood sessions; against CBM returns CBM's sessions.
- A3. `crmbuilder-v2-api --engagement CBM` overrides any marker file and starts against CBM. If the marker says CRMBUILDER, a yellow log line `"--engagement CBM overrides current_engagement.json (CRMBUILDER)"` is emitted; if it agrees, no log line.
- A4. `crmbuilder-v2-api --engagement BOGUS` (code not in meta DB) exits with code 2 and message `"Unknown engagement 'BOGUS'. Available: CRMBUILDER, CBM."` (enumerated from meta DB).
- A5. `crmbuilder-v2-api` with `current_engagement.json` pointing at a code not in the meta DB exits with code 2 and message `"Active engagement 'X' not found in meta DB. Activate a valid engagement via the desktop UI or pass --engagement <code>."`
- A6. With an active engagement whose `engagement_export_dir` is null in the meta DB, any POST/PUT/DELETE against the API (which triggers `session_scope` commit + snapshot export) returns HTTP 500 with body containing the `EngagementExportDirNotConfigured` message. The DB record DOES roll back. The `db-export/` directory is NOT touched.
- A7. With an active engagement whose `engagement_export_dir` points at a path that does not exist on disk, any write returns HTTP 500 with body containing the `EngagementExportDirMissing` message. The configured path is NOT auto-created.
- A8. With an active engagement whose `engagement_export_dir` is set and the directory exists, writes succeed and the snapshot lands in `engagement_export_dir/`. Subdirectories below (e.g., `catalog/entities/`) continue to be auto-created.
- A9. The catalog exporter (`access/repositories/catalog/exports.py`) writes to `engagement_export_dir/catalog/entities/` not the global default. Gated by `assert_export_dir_ready` like `session_scope`.
- A10. `force_export()` is gated identically to `session_scope`. Calling `force_export` with no configured export_dir raises `EngagementExportDirNotConfigured`.
- A11. The `bootstrap/migrate.py:64` path either no longer reads `settings.export_dir.parent` (if engine-scoped, hardcoded) or is gated like other consumers (if engagement-scoped). Slice A's commit message documents which.
- A12. New unit tests cover: happy-path resolve + route; missing marker; bad code; missing meta-DB record; null export_dir → sentinel; nonexistent export_dir on disk → `EngagementExportDirMissing`; existing export_dir → gate passes; concurrent route to different engagement → cache resets propagate.
- A13. Existing test suite passes. `uv run pytest tests/crmbuilder_v2/ -v` returns green.

**Test plan.**

- Helper tests verify the resolve+route mechanics in isolation using monkeypatched env vars and fixture meta DBs.
- Gate tests verify each of the three exception conditions raises the right exception with the right message.
- CLI integration tests use `subprocess.run` to exercise the actual `crmbuilder-v2-api` entry point with various env-var + flag + marker-file combinations; assert exit code, stderr, and stdout content.
- Existing tests for `session_scope`, `force_export`, and the catalog exporter need their fixtures updated to set `engagement_export_dir` (or to expect the new exceptions when it's null).

**Dependencies.** None. Slice A is independently shippable: CLI-launched API gets the full fix; UI-launched API continues working on its existing inline code path (no regression).

---

### Slice B — UI refactor + UI affordances + integration

**Scope.** Refactor the UI to use the helpers from slice A. Surface the new failure conditions to operators via warning bands, dialog emphasis, and graceful error handling. End with integration tests across a two-engagement state to verify the full UI-launched path matches the CLI-launched path.

**File:line touch points.**

| Path | Change |
|---|---|
| `crmbuilder-v2/src/crmbuilder_v2/ui/app.py:226-253` | EDIT — `_route_api_at_active_engagement` calls the slice-A helpers instead of duplicating the inline logic |
| `crmbuilder-v2/src/crmbuilder_v2/ui/active_engagement_context.py:32-138` | EDIT — uses `resolve_active_engagement` (slice A helper) instead of duplicating the JSON read |
| `crmbuilder-v2/src/crmbuilder_v2/ui/about_dialog.py:148` | EDIT — displays `(not configured)` for `__UNCONFIGURED__` sentinel; `(missing)` if path doesn't exist on disk; raw path otherwise |
| `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_edit.py` (path TBD) | EDIT — null-export_dir field renders with visual emphasis (red border or warning icon); save validates path exists if non-null, with confirm-anyway override |
| `crmbuilder-v2/src/crmbuilder_v2/ui/panels/engagements.py` (path TBD) | EDIT — Open Engagement flow surfaces warning band when activating an engagement with null or missing export_dir |
| `crmbuilder-v2/src/crmbuilder_v2/ui/error_handler.py` or equivalent | EDIT — UI catches new exceptions and renders helpful operator messages |
| `crmbuilder-v2/tests/crmbuilder_v2/ui/test_app_engagement_routing.py` | NEW — pytest-qt integration tests |

**Acceptance criteria.**

- B1. `_route_api_at_active_engagement` in `ui/app.py` no longer inlines the env-var-set + cache-reset code. It calls `runtime.engagement_routing.route_settings_to_engagement(code)` directly. Functional behavior is identical to pre-fix (UI-launched API still routes correctly).
- B2. `ActiveEngagementContext` (`ui/active_engagement_context.py`) uses `runtime.engagement_routing.resolve_active_engagement()` to read the marker file instead of duplicating the JSON parse. Existing Signal/Slot behavior preserved.
- B3. The About dialog's "Snapshot directory" line renders `(not configured)` when the sentinel is in effect, `(missing — <path>)` when the configured path doesn't exist on disk, and the raw path otherwise. The Snapshot directory line never shows the literal string `__UNCONFIGURED__`.
- B4. The Engagements panel's Open Engagement flow shows a yellow warning band immediately under the active-engagement header when the activated engagement has `engagement_export_dir = null`. Text: `"This engagement has no export directory configured. Reads will work; writes are disabled until you set one via Edit Engagement."` Includes a "Set export directory…" link button that opens Edit Engagement focused on the field.
- B5. The Engagements panel's Open Engagement flow shows a red warning band when the activated engagement has `engagement_export_dir` set but the path doesn't exist on disk. Text: `"Configured export directory does not exist on disk: <path>. Either create the directory or update the engagement via Edit Engagement."` Includes a "Edit engagement…" link button.
- B6. The Edit Engagement dialog's `engagement_export_dir` field renders with subtle visual emphasis (warning-amber border or icon) when null. On save, if the field is non-null and the path doesn't exist, the dialog prompts: `"The path '<path>' does not exist. Save anyway? You can create the directory later."` with [Save anyway] / [Cancel] buttons.
- B7. When a UI-triggered write raises `EngagementExportDirNotConfigured` or `EngagementExportDirMissing`, the UI renders the message in the error dialog rather than the raw traceback. The error dialog includes a "Edit engagement…" action button.
- B8. Integration tests exercise the full UI-launched path with a two-engagement state (CRMBUILDER + CBM): switch from CRMBUILDER to CBM, write a record, verify it lands in CBM.db AND CBM's export_dir. Switch back to CRMBUILDER, write a record, verify it lands in CRMBUILDER.db AND CRMBUILDER's export_dir. No cross-contamination.
- B9. Existing test suite passes. `uv run pytest tests/crmbuilder_v2/ -v` returns green.

**Test plan.**

- pytest-qt integration tests with a temp-data-dir fixture creating two engagements with distinct `engagement_export_dir` paths.
- Existing UI tests (about_dialog, engagements panel, engagement_edit dialog) updated to cover the new visual states.
- Manual smoke at slice end: open desktop UI, switch engagements via Engagements panel, verify warning bands appear at the right times, verify edit dialog visual emphasis, verify writes go to the right place.

**Dependencies.** Slice A must land first — slice B imports from `crmbuilder_v2.runtime.engagement_routing` and `crmbuilder_v2.runtime.exceptions`.

---

## 6. Dependency chain

Strictly sequential: **A → B**. No parallelism. Slice A is independently shippable on its own (CLI works; UI continues on legacy inline path). Slice B requires slice A's module to exist.

---

## 7. Test target

Slice A adds approximately 25–35 new tests:
- ~10 helper unit tests (`test_engagement_routing.py`)
- ~6 gate unit tests (`test_export_gate.py`)
- ~5 CLI integration tests (`test_cli_engagement_flag.py`)
- ~8 updates to existing `session_scope` / `force_export` / catalog tests

Slice B adds approximately 8–12 new tests:
- ~6 pytest-qt integration tests for the warning-band UI states
- ~4 updates to existing dialog / panel tests

Total new test count after both slices: ~33–47. Roll into the existing `uv run pytest tests/crmbuilder_v2/ -v` invocation; no separate test target.

---

## 8. Migration ordering

None. The fix changes runtime routing behavior but does not alter any database schema, persistence format, or stored data. Existing engagements (CRMBUILDER and CBM) work unchanged after the fix lands. The previously-mis-routed snapshots in `PRDs/product/crmbuilder-v2/db-export/` from the 05-19-26 paper-test apply attempt were already recovered via `git checkout HEAD --`; nothing in this fix touches them.

---

## 9. Version source

This is a maintenance fix, not a release. `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` stays at `0.6.0` through both slices. No README entry. No closeout `__version__` bump.

The fix discharges PI-021 once slice B lands.

---

## 10. Closeout discipline

Each slice closes out by:

1. Slice ends when all acceptance criteria pass and the full test suite is green.
2. Commit per the slice prompt's commit-message scaffold.
3. Doug pushes.
4. PI-021 status update on slice B close: `Open` → `Closed (resolved)` via the desktop UI's planning-items panel or via direct API. No new session record per slice — the work is captured under SES-044's `is_about` PI-021 reference; subsequent build conversations can author per-slice SES records if their content warrants (e.g., if slice A's investigation of `bootstrap/migrate.py:64` surfaces something worth recording).

No version bump or release note required — see §9.

---

*End of slice plan.*
