# CRMBuilder v2 — UI v0.1 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-07-26 17:30
**Status:** Draft — pending approval
**Companion PRD:** `ui-PRD-v0.1.md`
**Executing prompt series:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-{A..H}-*.md`

---

## 1. Overview

This plan implements the v0.1 desktop UI specified in `ui-PRD-v0.1.md`. Unlike the storage system build (single-pass, single execution prompt), the UI build is decomposed into eight independently testable slices, each delivered as its own prompt. Each prompt produces a working state of the application that exercises a coherent slice of the PRD's acceptance criteria.

The slice boundaries are dictated by dependency and natural review checkpoints. Scaffold before lifecycle, lifecycle before HTTP client, client before list/detail base, base before per-entity panels, panels before refresh wiring, read-only complete before write, polish last.

After all eight prompts execute cleanly, every acceptance criterion in PRD section 6 is satisfied. No staged release boundaries are needed within the slices — the application is functional and useful from prompt D onward (all read-only views), with each subsequent prompt strictly additive.

---

## 2. Implementation Choices

### 2.1 Language and runtime

- **Python 3.12+** (matches the existing repository's `requires-python` pin in `pyproject.toml`). Same constraint as the storage system.

### 2.2 Desktop framework — PySide6

Specified by the PRD. PySide6 is already the desktop framework used by the existing CRM Builder v1 application, so the development environment, tooling knowledge, and packaging story are already established in this codebase.

Alternative considered: PyQt6. Rejected — license terms (GPL/commercial) are more restrictive than PySide6's LGPL, and there is no functional advantage for v2's needs.

### 2.3 HTTP client — httpx (sync mode)

`httpx` is already a dependency in the v2 package (used by the MCP server). The UI uses its synchronous client (`httpx.Client`) inside `QThread` workers rather than its async client.

Rationale: mixing asyncio with Qt's event loop is doable (e.g., `qasync`) but adds non-trivial complexity that is not justified for v0.1's needs. Synchronous calls inside short-lived `QThread` workers are the canonical Qt pattern for HTTP work and keep the threading model legible.

Alternative considered: `requests`. Rejected only to avoid adding a second HTTP library; both would work fine.

### 2.4 Subprocess management — QProcess

Qt's native subprocess wrapper. Integrates with the Qt event loop, emits signals on stdout/stderr/exit, and survives suspension better than `subprocess.Popen` in a Qt application. Used for spawning and supervising `crmbuilder-v2-api`.

### 2.5 File watching — QFileSystemWatcher

Qt's native filesystem watcher. Cross-platform (uses inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows). Single class, signal-based — fits the rest of the UI's signal/slot architecture without adapter code.

Alternative considered: `watchdog`. Rejected — third-party dependency providing capabilities Qt already exposes natively.

### 2.6 Test framework — pytest + pytest-qt

`pytest` is already a project dependency. `pytest-qt` adds Qt-aware fixtures (`qtbot`, `qapp`) and is the standard for testing PySide6 / PyQt code.

UI testing scope for v0.1 is deliberately modest: smoke tests that the application launches, that each panel renders without raising, and that the storage client's error mapping is correct. Full interaction-level UI tests (clicking through dialogs, asserting on visible state) are deferred to v0.2 — they are higher-cost than they're worth at this stage.

### 2.7 Logging — Python's standard `logging` module

No third-party logging library. `RotatingFileHandler` to `~/.crmbuilder-v2/ui.log`, 10MB rotation, keep 3. Console handler at INFO by default, DEBUG when launched with `--verbose`.

### 2.8 Threading model

Every HTTP call goes through a `QThread` worker built on the worker/object pattern: a plain `QObject` carrying the work, moved to a `QThread`, with start/finished signals. The UI thread connects to `finished` signals to update widgets when calls complete.

No `time.sleep`, no synchronous network I/O on the UI thread. No nested event loops. No threading primitives outside Qt's signal/slot mechanism for cross-thread communication.

### 2.9 Error handling

The storage client maps HTTP status codes to typed exceptions (`ValidationError`, `NotFoundError`, `ConflictError`, `ConnectionError`, etc., as enumerated in PRD section 4.11). Workers re-raise these into the UI thread via the signal payload. Panels and dialogs handle them locally — there is no single global error sink.

Generic uncaught exceptions trigger a top-level error dialog and are logged with full traceback. The application does not silently suppress unexpected errors.

---

## 3. Directory and File Layout

The UI lives entirely under `crmbuilder-v2/src/crmbuilder_v2/ui/`. No top-level layout changes elsewhere in the v2 package.

```
crmbuilder-v2/
└── src/crmbuilder_v2/
    ├── ui/
    │   ├── __init__.py
    │   ├── app.py                          # QApplication + main window
    │   ├── main_window.py                  # Sidebar + content stack
    │   ├── sidebar.py                      # Left navigation list
    │   ├── splash.py                       # Startup splash screen
    │   ├── crash_banner.py                 # Subprocess-died banner
    │   ├── server_lifecycle.py             # Detect-then-launch QProcess wrapper
    │   ├── client.py                       # httpx-based StorageClient
    │   ├── exceptions.py                   # ValidationError, NotFoundError, etc.
    │   ├── workers.py                      # QThread worker pattern
    │   ├── refresh.py                      # QFileSystemWatcher service
    │   ├── styling.py                      # Minimal QSS stub
    │   ├── about_dialog.py                 # About window
    │   ├── base/
    │   │   ├── __init__.py
    │   │   ├── list_detail_panel.py        # Reusable list+detail base
    │   │   └── versioned_panel.py          # Variant for charter/status
    │   ├── panels/
    │   │   ├── __init__.py
    │   │   ├── charter.py
    │   │   ├── status.py
    │   │   ├── decisions.py
    │   │   ├── sessions.py
    │   │   ├── risks.py
    │   │   ├── planning_items.py
    │   │   ├── topics.py
    │   │   └── references.py
    │   └── dialogs/
    │       ├── __init__.py
    │       ├── decision_create.py
    │       ├── decision_edit.py
    │       ├── decision_delete.py
    │       └── error.py
    ├── api/
    │   └── routers/
    │       └── health.py                   # NEW — added in v2-ui-A
    └── cli.py                              # Add run_ui()

tests/
└── crmbuilder_v2/
    └── ui/
        ├── conftest.py                     # qtbot, fake API server fixtures
        ├── test_smoke.py                   # App launches, panels render
        ├── test_client.py                  # Error envelope mapping
        ├── test_server_lifecycle.py        # Probe / spawn / ownership
        └── test_refresh.py                 # File-watcher event handling
```

The new `health.py` API router is the only addition outside the `ui/` package — a small additive change to the existing storage-system API delivered alongside its first consumer in `v2-ui-A`.

---

## 4. Build Sequence

Each step lands as one or more `v2:`-prefixed commits and corresponds to one execution prompt. PRD acceptance criteria from section 6 are cross-referenced as `AC#N`.

### Step A — Scaffold

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-A-scaffold.md`

**Deliverables:**

- New `ui/` package directory with empty modules in place.
- `cli.py` extended with `run_ui()` entry function and `--verbose` flag handling.
- `pyproject.toml` adds `crmbuilder-v2-ui` console script and PySide6 to dependencies.
- `uv sync` adds PySide6 to the lockfile.
- Minimal `app.py` and `main_window.py`: a window with the sidebar populated with all eight entries, content area is a placeholder label, no data wiring.
- `splash.py`: simple QSplashScreen subclass with a "Starting storage server…" label (renders without subprocess logic yet).
- `styling.py`: QSS stub applying `#1F3864` accent color and Arial as default font.
- New `api/routers/health.py`: `GET /health` returns `{"data": {"ok": true}, "meta": {}, "errors": null}`. Wired into `api/main.py`.
- `tests/crmbuilder_v2/ui/conftest.py`: `qtbot` and `qapp` fixtures.
- `tests/crmbuilder_v2/ui/test_smoke.py`: imports the app module, instantiates the main window, asserts sidebar has eight entries.
- `tests/crmbuilder_v2/api/test_health.py`: hits `/health`, asserts 200 and envelope shape.

**Acceptance gates:**

- `uv run crmbuilder-v2-ui` launches a window with the sidebar visible. No crash. (AC#1)
- `curl http://127.0.0.1:8765/health` returns 200 with the documented envelope. (AC#14)
- Smoke test passes.

**Out of slice:** subprocess management, HTTP wiring, panel content, refresh service.

---

### Step B — Server lifecycle

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-B-server-lifecycle.md`

**Deliverables:**

- `server_lifecycle.py`: `ServerLifecycle` class with methods `probe()`, `spawn()`, `terminate()`. Uses `QProcess` for spawning. Tracks ownership ("external" / "owned") as instance state. Emits signals `ready`, `crashed`, `terminated`.
- `splash.py` integration: shown at app start, dismissed when lifecycle emits `ready`.
- `crash_banner.py`: `CrashBanner` widget with text and a Reconnect button. Hidden by default. Shown when lifecycle emits `crashed`.
- `app.py` orchestration: on launch, run lifecycle probe-then-spawn, dismiss splash on ready, install banner on crash. On window close, terminate owned subprocess via `closeEvent`.
- `tests/crmbuilder_v2/ui/test_server_lifecycle.py`: probe with API running (mocked), probe with API not running (mocked, asserts spawn invoked), ownership tracking, terminate-only-owned semantics.

**Acceptance gates:**

- Launching with no API running spawns the API and the splash dismisses when ready. (AC#2)
- Launching with the API already running does not spawn a duplicate; splash dismisses on the first probe success. (AC#2)
- Killing the spawned API process while UI is running surfaces the crash banner. Reconnect button respawns successfully. (AC#3)
- Closing the UI cleanly terminates an owned subprocess; an externally-launched API stays running. (AC#13)

**Out of slice:** any panel content beyond the placeholder.

---

### Step C — HTTP client and list/detail base

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-C-http-client-and-list-detail-base.md`

**Deliverables:**

- `exceptions.py`: typed exceptions per PRD section 4.11 (`ValidationError`, `NotFoundError`, `ConflictError`, `RequestShapeError`, `ServerError`, `ConnectionError`). `ValidationError` and `ConflictError` carry `field` and `message` attributes parsed from the envelope.
- `client.py`: `StorageClient` with one method per REST endpoint the UI uses. Uses `httpx.Client` synchronously. Parses envelope, raises typed exceptions on non-2xx. Methods return plain dicts/lists (no model classes — JSON shape is the contract).
- `workers.py`: generic `Worker` QObject pattern. `run_worker(callable, on_success, on_error)` helper that creates a worker, moves it to a thread, wires signals, and starts.
- `base/list_detail_panel.py`: `ListDetailPanel` abstract base. Top toolbar (title, Refresh button, status label, action button slot), QTableView (left), detail widget container (right). Abstract methods: `fetch_records()`, `list_columns()`, `render_detail(record)`. Subclasses implement these three.
- A debug `panels/decisions.py` skeleton — barest possible decisions panel that uses `ListDetailPanel`, fetches via `StorageClient.list_decisions()`, renders identifier+title+status in the table, renders a stringified detail. Wired to the sidebar so navigating to "Decisions" actually shows live data.
- `tests/crmbuilder_v2/ui/test_client.py`: tests for envelope parsing, error code → exception mapping, `field` extraction on validation errors.

**Acceptance gates:**

- Navigating to the Decisions sidebar entry renders a table populated from live API data. (Partial AC#4 — one entity wired.)
- Killing the API while the panel is open results in a `ConnectionError` surfaced as the banner per Step B's behavior; navigating to Decisions afterward shows the panel in disabled state.
- Client test suite passes for all six exception types.

**Out of slice:** all other entity panels, refresh wiring, dialogs.

---

### Step D — Read-only views, round 1

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-D-readonly-views-round-1.md`

**Deliverables:**

- `panels/decisions.py`: full read-only implementation per PRD section 4.6 (Identifier, Title, Decision Date, Status, Superseded By columns; full detail). Replaces the C-step skeleton.
- `panels/sessions.py`: full read-only implementation. Columns per PRD 4.6.
- `panels/risks.py`: full read-only implementation. Columns per PRD 4.6.
- `client.py` extended with the methods these three panels need (`list_sessions`, `get_session`, `list_risks`, `get_risk`, plus the references-touching method for showing referenced records on detail panes).
- Reference rendering on decision detail panes: text rows like "Decided in: SES-002", clickable. Click switches the sidebar selection to Sessions and selects the referenced row.
- `tests/crmbuilder_v2/ui/test_smoke.py` extended to instantiate each new panel without raising.

**Acceptance gates:**

- Decisions, Sessions, Risks sidebar entries all navigate to functional panels rendering live data with PRD-specified columns. (Partial AC#4.)
- Selecting a row in any list updates the detail pane.
- Clicking a "decided_in" link on a decision detail navigates to the corresponding session.

**Out of slice:** refresh wiring, write operations.

---

### Step E — Read-only views, round 2

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-E-readonly-views-round-2.md`

**Deliverables:**

- `base/versioned_panel.py`: `VersionedPanel` base class for charter/status. Variant of `ListDetailPanel`: list shows version_number + created_at + current-marker; detail shows the version's payload as a key/value display.
- `panels/charter.py`: uses `VersionedPanel`. Fetches `/charter/versions`, detail uses `/charter/versions/{n}`.
- `panels/status.py`: same pattern as charter.
- `panels/topics.py`: read-only list+detail. Hierarchical display: child topics indented under parent.
- `panels/planning_items.py`: read-only list+detail. Columns per PRD 4.6.
- `panels/references.py`: read-only list-only (no detail pane needed, references have no further fields). Filterable by source type and target type via dropdowns above the table. Clicking source or target navigates to the referenced record.
- `client.py` extended with `list_charter_versions`, `get_charter_version`, `list_status_versions`, `get_status_version`, `list_topics`, `list_planning_items`, `list_references`, plus any missing get-by-id methods.

**Acceptance gates:**

- All eight sidebar entries navigate to functional read-only panels. (AC#4 complete.)
- Charter and Status panels show all versions with the current version visually marked. (AC#5)
- References on decision detail panes are clickable and navigate correctly. (AC#6)

**Out of slice:** refresh wiring, write operations.

---

### Step F — Live refresh

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-F-file-watch-refresh.md`

**Deliverables:**

- `refresh.py`: `RefreshService` class wrapping `QFileSystemWatcher`. Watches the configured `CRMBUILDER_V2_EXPORT_DIR`. On any file change in the directory, parses the filename, emits a `data_changed(entity_type)` signal. Maps `decisions.json` → `decision`, `sessions.json` → `session`, etc.
- `main_window.py` integration: `RefreshService` instance owned by main window. Each panel subscribes to `data_changed` for its entity type and refetches silently when the signal fires for its type.
- Sidebar staleness indicator: when `data_changed` fires for an entity type whose panel is not currently visible, the sidebar entry shows a small dot. The dot clears when the user navigates to that panel and the refresh completes.
- Manual Refresh button on every panel triggers an explicit refetch regardless of file-watcher state. Button is on every panel's toolbar (already present from B; this step wires it up).
- `tests/crmbuilder_v2/ui/test_refresh.py`: simulate a snapshot file change, assert the correct `data_changed` signal fires.

**Acceptance gates:**

- Writing a new decision via MCP (or directly via `curl`) while the UI has the Decisions panel open causes the new row to appear without manual intervention. (AC#11)
- Writing a new session while the Decisions panel is open causes the Sessions sidebar entry to show the staleness indicator. Navigating to Sessions clears the indicator and shows the new record.
- Manual Refresh button on every panel produces an immediate refetch with status label feedback. (AC#12)

**Out of slice:** write operations.

---

### Step G — Decisions CRUD

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-G-decisions-crud.md`

**Deliverables:**

- `dialogs/decision_create.py`: modal create dialog per PRD section 4.7. All eleven inputs (identifier, title, decision_date, status, context, decision, rationale, alternatives_considered, consequences, supersedes, superseded_by). Status is a dropdown bound to the controlled vocabulary fetched from the API or imported from the access layer's `vocab.py` (preferred — vocab is constants, not state). Save and Cancel buttons.
- `dialogs/decision_edit.py`: same dialog shape as create, pre-populated. Identifier field read-only.
- `dialogs/decision_delete.py`: confirmation dialog with the decision's identifier and title. Delete and Cancel buttons.
- `dialogs/error.py`: generic error dialog used by all three for unexpected errors.
- `panels/decisions.py` extended: "New Decision" button in toolbar opens create dialog. "Edit" and "Delete" buttons on detail pane open edit and delete dialogs.
- `client.py` extended with `create_decision`, `update_decision`, `delete_decision`.
- Inline error handling: validation errors from the API surface on the offending field (label turns red, error text shown beneath the field). `field` populated → inline; `field` missing → modal generic error.
- After successful create/edit/delete, the dialog closes and an explicit refresh runs (the file watcher will also trigger one, but explicit refresh prevents any stale-window flicker).
- `tests/crmbuilder_v2/ui/test_smoke.py` extended: instantiate each dialog without raising.

**Acceptance gates:**

- Decisions create flow: filling the dialog, clicking Save, seeing the new row in the list. (AC#7)
- Decisions edit flow: changing a field, clicking Save, seeing the change reflected. (AC#8)
- Decisions delete flow: confirming the dialog, seeing the row disappear. (AC#9)
- Submitting an invalid status value or duplicate identifier surfaces inline on the field; dialog stays open. (AC#10)

**Out of slice:** write operations for any other entity.

---

### Step H — Polish and styling stub

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-H-polish-and-styling-stub.md`

**Deliverables:**

- `about_dialog.py`: About dialog showing app name, version (read from `pyproject.toml` via `importlib.metadata`), API URL, DB path, snapshot directory.
- "Help → About" menu wired into the main window menu bar.
- `styling.py` final pass: refine the QSS stub so accent color is consistent on selected sidebar entries, table row selection, and button focus states. Confirm Arial renders correctly across panels.
- Friction fixes from D/E/G manual review: any rough edges noticed during the build (column widths, sort-order defaults, missing tooltips, awkward focus order). This step is the catch-all for the "noticed during review" backlog.
- README addition: `crmbuilder-v2/README.md` gets a new "User interface" section with a quick-start, a screenshot description (or actual screenshot if convenient), and a link to the PRD.
- macOS visual verification: launch on macOS, click through every panel and dialog, screenshot any platform-specific issues. Linux is the primary target; macOS is best-effort for v0.1.

**Acceptance gates:**

- About dialog shows the resolved configuration values. (Open Question #1 closed.)
- Styling stub applied consistently across all panels and dialogs. (Per PRD section 2 in scope item 11.)
- macOS launch + smoke-test path produces no crashes. (AC#15)
- All fifteen PRD acceptance criteria verified in a final pass.

**Out of slice:** anything labelled "deferred to v0.2" in PRD section 2.

---

## 5. Testing Strategy

### What we test in v0.1

- **Storage client error mapping (high coverage):** every error code path, envelope variations with and without `field`, network failure modes. The client is pure Python and easy to test without Qt.
- **Server lifecycle (medium coverage):** probe-success / probe-failure / spawn / ownership-tracking / terminate. Uses mocked `QProcess` via `pytest-qt`.
- **Refresh service (medium coverage):** snapshot file change → correct entity type signal. Uses real temp directory and real `QFileSystemWatcher`.
- **Smoke tests (low coverage, broad):** every panel instantiates without raising, every dialog instantiates without raising. Catches import-time and construction-time bugs.

### What we defer to v0.2

- Click-through interaction tests (filling a dialog, clicking Save, asserting on visible state). Higher-cost than v0.1 needs.
- Visual regression testing.
- Cross-platform automated runs (Linux is the CI target for v0.1).

### Target

- The full UI test suite runs in under 30 seconds.
- Adding the UI test suite does not slow the existing `pytest tests/crmbuilder_v2/` run by more than 30 seconds total.

---

## 6. Dependencies and Configuration

### New Python dependencies

Added to the root `pyproject.toml` `[project] dependencies` array:

- `PySide6` (latest 6.x stable as of build date)

Added to `[dependency-groups] dev`:

- `pytest-qt` (for Qt-aware test fixtures)

`httpx` is already present from the storage system build. No other new third-party dependencies.

### Configuration

The UI reads the same `crmbuilder_v2.config.get_settings()` as the API and access layer. No new environment variables. No config file. Existing settings used:

| Setting | Used for |
|---|---|
| `CRMBUILDER_V2_API_BASE_URL` | URL the UI probes and connects to |
| `CRMBUILDER_V2_API_HOST` / `CRMBUILDER_V2_API_PORT` | Used when spawning the subprocess (the spawned API reads these directly) |
| `CRMBUILDER_V2_EXPORT_DIR` | Directory the file watcher watches |
| `CRMBUILDER_V2_DB_PATH` | Surfaced in the About dialog (read-only) |

### File system locations

- Logs: `~/.crmbuilder-v2/ui.log` (rotated)
- Settings: none (everything from environment / `get_settings()`)
- Database: `crmbuilder-v2/data/v2.db` (existing; UI does not touch it directly)
- Snapshots: `PRDs/product/crmbuilder-v2/db-export/` (existing; UI watches but does not write)

---

## 7. Commit Strategy

Each prompt produces one or more commits, all prefixed `v2:` per the v2 commit convention. Suggested per-prompt commit shape:

| Prompt | Suggested commits |
|---|---|
| A | `v2: ui scaffold — package, console script, /health endpoint` |
| B | `v2: ui server lifecycle — detect, spawn, splash, crash banner` |
| C | `v2: ui storage client + list/detail base` |
| D | `v2: ui read-only panels — decisions, sessions, risks` |
| E | `v2: ui read-only panels — charter, status, topics, planning items, references` |
| F | `v2: ui file-watch refresh service` |
| G | `v2: ui decisions CRUD — create, edit, delete` |
| H | `v2: ui polish — about dialog, styling stub, friction fixes` |

After each prompt's commits land, the v2 status record gets a one-line update reflecting progress. At end of H, status is updated to "UI v0.1 complete" and a closing session record is appended.

---

## 8. Risk Register

Prompt-level risks (cross-cutting risks live in PRD section 9):

| Risk | Slice | Mitigation |
|---|---|---|
| `httpx.Client` synchronous calls inside `QThread` workers feel sluggish on first request due to connection setup | C | Reuse a single `httpx.Client` across calls — connection pooling makes subsequent requests fast. |
| `QFileSystemWatcher` on macOS sometimes misses fast-rewrite events (well-documented Qt behavior) | F | Manual Refresh button on every panel as documented fallback. |
| Decision dialog field validation drifts from access-layer validation as vocab evolves | G | Import from `crmbuilder_v2.access.vocab` directly rather than hard-coding values in the UI. Single source of truth. |
| Spawned subprocess inherits the current shell's broken environment (e.g., wrong `PATH`) and fails opaquely | B | Pass an explicit `QProcessEnvironment` derived from `os.environ`; capture stderr and surface in the failure dialog. |
| Test suite hangs on Qt event loop in CI without a display server | A | Configure pytest-qt to use the offscreen QPA platform (`QT_QPA_PLATFORM=offscreen`) in test runs. |

---

## 9. Order of Operations Across the Series

The eight prompts are strictly sequential — each builds on the previous. There is no opportunity to parallelize within v0.1.

After approval of this plan:

1. v2-ui-A is drafted and reviewed.
2. v2-ui-A is executed; results reviewed; any prompt-level fixes applied before proceeding.
3. Repeat through v2-ui-H.
4. After v2-ui-H acceptance, the seven UI decisions (DEC-018 through DEC-024) and the planning session (SES-004 or whatever's next) are written to the v2 database. Status updated to reflect UI v0.1 complete.

If review of any prompt's results surfaces a missed requirement that affects subsequent prompts, the affected later prompts are re-drafted before execution. The plan is a living document for the duration of the build — any material change is committed as a plan version bump (`0.2`, `0.3`, etc.) with an entry in the change log.

---

## 10. Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-07-26 | Initial draft. Decomposes the UI v0.1 build into eight sequential prompts (v2-ui-A through v2-ui-H), each with explicit deliverables, acceptance gates cross-referenced to PRD section 6, and out-of-slice notes. Captures implementation choices (PySide6, httpx sync, QProcess, QFileSystemWatcher, pytest-qt) and locks the directory layout under `crmbuilder-v2/src/crmbuilder_v2/ui/`. |
