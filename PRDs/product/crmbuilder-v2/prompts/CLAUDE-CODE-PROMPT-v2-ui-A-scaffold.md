# CLAUDE-CODE-PROMPT-v2-ui-A-scaffold

**Last Updated:** 05-07-26 18:15
**Series:** v2-ui
**Slice:** A (1 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`

## Purpose

This is the first of eight slices that build the CRMBuilder v2 desktop UI per the companion PRD and implementation plan. This prompt builds slice **A — Scaffold**.

Slice A produces a launchable but mostly-empty PySide6 application — sidebar visible with all eight entity entries, content area shows a placeholder, no data wiring yet. It also adds the new `GET /health` endpoint to the existing storage system REST API. Server-lifecycle subprocess management, HTTP client wiring, panel content, and the file-watch refresh service are all explicitly out of scope for this slice and will be delivered by subsequent prompts (B through F).

This prompt also writes the planning session and seven architectural decisions for the UI work into the v2 database as part of its setup, capturing the conversation that produced the companion PRD.

## Project context

The v2 storage system has been operational since 05-07-26. Charter, status, decisions, sessions, risks, planning items, topics, and references all live in `crmbuilder-v2/data/v2.db` and are exposed through the REST API (`http://127.0.0.1:8765`) and the MCP stdio server.

The v2 desktop UI is a separate workstream that consumes the storage system through its REST API. Per DEC-018 (one of the decisions you will write in step 1 below), the UI is a standalone application — it does not modify the existing v1 PySide6 application, and it does not extend the v1 application's window with new tabs.

The full architectural framing is captured in the companion PRD and plan. This prompt assumes you have read both end-to-end before executing.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug`
   - `git config user.email` should return `doug@dougbower.com`
   - If not set, configure: `git config user.name "Doug"` and `git config user.email "doug@dougbower.com"`.
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm the storage system is operational:
   - `uv run crmbuilder-v2-api &` to start the API in the background.
   - `curl http://127.0.0.1:8765/charter` should return a 200 with the current charter envelope.
   - If the API will not start cleanly, stop and report.

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry point. Pay particular attention to the "CRMBuilder v2 — Methodology Rearchitecture" section.
2. `crmbuilder-v2/README.md` — operational reference for the storage system, including the REST surface and the MCP tools list.
3. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — the requirements you are implementing. All slices.
4. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — the slice breakdown. Pay particular attention to **Step A** in section 4.
5. **Tier 2 orientation** (per DEC-011), via either MCP or the JSON snapshots:
   - Current charter
   - Current status
   - SES-003 (most recent prior session) and any earlier sessions referenced from it
   - DEC-005 (storage stack), DEC-011 (orientation protocol), DEC-013 (sessions append-only), DEC-017 (storage stack implementation choices)

## Step 1 — Write planning records to the database

Before any code changes, capture the planning conversation that produced the companion PRD and plan. Write these records via the running REST API (or via MCP if your client is connected — both reach the same database).

### Decisions (seven new records, DEC-018 through DEC-024)

Each decision below should be written as a `POST /decisions` call. All have `decision_date: "05-07-26"` and `status: "Active"`. Pull the full body text for each from PRD section 1 (Source Decisions, Forthcoming Decisions). Use the title given here verbatim:

- **DEC-018** — UI is a standalone application, not embedded in the v1 PySide6 app
- **DEC-019** — UI consumes the REST API over HTTP, not the access layer directly
- **DEC-020** — v0.1 scope: read-only across all entities, full CRUD for decisions only
- **DEC-021** — Sidebar navigation with master/detail panes
- **DEC-022** — File-watch on `db-export/` for live refresh, manual Refresh button as fallback
- **DEC-023** — Detect-then-launch API subprocess management
- **DEC-024** — Native Qt look for v0.1; styling pass deferred

For each decision, use the verbatim body text in **Appendix A** below for the `context`, `decision`, `rationale`, `alternatives_considered`, and `consequences` fields. Do not summarize, paraphrase, or compose new text — the body text in Appendix A is the canonical record of the planning conversation and should land in the database exactly as written.

### Session (one new record, SES-004)

Write a `POST /sessions` call with:

- `identifier: "SES-004"`
- `title: "UI v0.1 planning"`
- `session_date: "05-07-26"`
- `status: "Complete"`
- `topics_covered`: a paragraph summarizing the seven architectural questions addressed in the planning conversation (standalone-vs-embedded, transport choice, scope, layout, refresh strategy, server lifecycle, styling).
- `summary`: a paragraph summarizing the outcome — that the planning conversation produced the v0.1 PRD, the implementation plan, and the v2-ui prompt series specification.
- `artifacts_produced`: enumerate `ui-PRD-v0.1.md`, `ui-implementation-plan.md`, and the v2-ui prompt series.
- `in_flight_at_end`: empty.

### References (seven new records)

For each of DEC-018 through DEC-024, write a `POST /references` call:

- `source_type: "session"`
- `source_id: "SES-004"`
- `target_type: "decision"`
- `target_id: "DEC-NNN"` (one per decision)
- `relationship: "decided_in"`

### Status update

Append a new status version via `PUT /status`. The new payload should reflect that UI v0.1 is now in build, slice A in progress. Preserve the rest of the prior status content as much as it remains accurate. Bump the version.

### Verify

After the writes:

- The `db-export/` directory should have updated `decisions.json`, `sessions.json`, `references.json`, `status.json`, and `change_log.json` files. Inspect them and confirm the expected records are present.
- Commit all changes under `db-export/` in a single commit: `v2: ui v0.1 planning records — SES-004, DEC-018 through DEC-024`.

## Step 2 — Add `GET /health` endpoint to the API

This is the only modification to existing storage-system code in this slice.

### Files

- `crmbuilder-v2/src/crmbuilder_v2/api/routers/health.py` (new). Register an `APIRouter` with prefix `/health` and a single `GET ""` route that returns `ok({"ok": True})` (using the existing envelope helper from `api/envelope.py`). No DB access, no readonly_session — the endpoint is a pure liveness check.
- `crmbuilder-v2/src/crmbuilder_v2/api/main.py` — wire the new router into the FastAPI app alongside the existing routers.
- `tests/crmbuilder_v2/api/test_health.py` (new) — one test that hits `/health` via the FastAPI TestClient and asserts:
  - HTTP 200
  - `data == {"ok": True}`
  - `errors is None`

### Verify

- `uv run pytest tests/crmbuilder_v2/api/test_health.py -v` passes.
- With the API running, `curl -s http://127.0.0.1:8765/health | jq .` returns the documented envelope.

Commit: `v2: api adds GET /health endpoint`.

## Step 3 — UI package scaffold

### Files (all under `crmbuilder-v2/src/crmbuilder_v2/ui/`)

Create the following with the contents described. All other files listed in the implementation plan section 3 should be created as **empty modules with only a docstring**, ready to be filled in by later slices. Do not pre-implement anything for slices B through H.

#### `__init__.py`

Module docstring only.

#### `app.py`

`build_application()` factory function:

- Constructs a `QApplication` (singleton, reuse if one already exists).
- Sets the application name `CRMBuilder v2`.
- Loads the QSS stub from `styling.py` and applies it to the application.
- Returns the `QApplication` instance.

`main(argv)` entry function:

- Parses arguments. Supports `--verbose` flag for DEBUG-level logging. No other args in this slice.
- Configures Python logging to a `RotatingFileHandler` at `~/.crmbuilder-v2/ui.log` (10MB rotation, keep 3) plus a console handler. Default level INFO; DEBUG when `--verbose` is set. Create the log directory if it does not exist.
- Calls `build_application()`.
- Constructs `MainWindow()` and shows it.
- Calls `app.exec()` and returns the exit code.

#### `main_window.py`

`MainWindow(QMainWindow)`:

- Sets window title `CRMBuilder v2`.
- Sets a sensible default size (1200x800).
- Splits the central widget into a sidebar (left, fixed width 200px) and a content area (right, expanding).
- Sidebar instance is `Sidebar()` from `sidebar.py`.
- Content area is a `QStackedWidget` with one placeholder page per sidebar entry. Each placeholder is a `QLabel` with text "Panel for {entity name} — implemented in slice D or E."
- Wires the sidebar's selection-changed signal to swap the stack.
- Default selection on launch: Decisions.
- Menu bar: File menu with Quit action; Help menu with placeholder About action (will be wired in slice H).

#### `sidebar.py`

`Sidebar(QListWidget)`:

- Adds eight entries in this order: Charter, Status, Decisions, Sessions, Risks, Planning Items, Topics, References.
- Single-selection.
- Emits a `selection_changed(str)` signal with the entry text on selection.
- Visual styling: fixed-width, indented padding, accent color on selected row from the QSS stub.

#### `splash.py`

`Splash(QSplashScreen)`:

- Subclass of `QSplashScreen`.
- Constructed with a simple `QPixmap` (e.g., 400x200) drawn programmatically — solid background in `#1F3864`, white text "Starting storage server…" centered. No image asset file required.
- The splash is created and shown by `app.py` but is not yet integrated with the lifecycle (which lands in slice B). For this slice, the splash can be shown for a fixed half-second on launch as a smoke check that it renders, then dismissed.

#### `crash_banner.py`

Empty module with docstring. Wired in slice B.

#### `server_lifecycle.py`

Empty module with docstring. Wired in slice B.

#### `client.py`

Empty module with docstring. Wired in slice C.

#### `exceptions.py`

Empty module with docstring. Wired in slice C.

#### `workers.py`

Empty module with docstring. Wired in slice C.

#### `refresh.py`

Empty module with docstring. Wired in slice F.

#### `styling.py`

`apply_stylesheet(app: QApplication)`:

- Loads a QSS string with these rules:
  - Default font: `Arial`, 10pt.
  - Selected `QListWidget::item` has background `#1F3864` and white text.
  - `QPushButton` focus border uses `#1F3864`.
- Calls `app.setStyleSheet(qss)`.
- Document why `#1F3864` and Arial are the choices (matches v2 document standards) in a module-level comment.

#### `about_dialog.py`

Empty module with docstring. Wired in slice H.

#### `base/__init__.py`, `base/list_detail_panel.py`, `base/versioned_panel.py`

Empty modules with docstrings. Wired in slices C and E.

#### `panels/__init__.py` and per-entity panel files

Empty modules with docstrings. Wired in slices D and E.

#### `dialogs/__init__.py` and per-dialog files

Empty modules with docstrings. Wired in slice G.

### `cli.py` extension

Add a `run_ui()` function that calls `crmbuilder_v2.ui.app.main(sys.argv)` and returns the exit code. Existing `run_api()`, `run_mcp()`, `bootstrap_db()`, `bootstrap_content()` functions are not modified.

### `pyproject.toml` changes

Add to the `[project] dependencies`:
- `PySide6>=6.7,<7`

Add to `[dependency-groups] dev`:
- `pytest-qt>=4.4,<5`

Add to `[project.scripts]`:
- `crmbuilder-v2-ui = "crmbuilder_v2.cli:run_ui"`

Run `uv sync` to update the lockfile.

### Test fixtures

`tests/crmbuilder_v2/ui/conftest.py` (new):

- Sets `QT_QPA_PLATFORM=offscreen` early via `os.environ.setdefault` at the top of the module so headless test runs work in CI.
- Provides a `qapp` fixture (uses pytest-qt's built-in if sufficient, or thin wrapper) and a `qtbot` fixture (pytest-qt built-in).

### Smoke test

`tests/crmbuilder_v2/ui/test_smoke.py` (new):

- One test that constructs `MainWindow` (using `qapp` and `qtbot` fixtures), asserts the sidebar has exactly eight entries with the expected labels in order, and asserts the content stack has eight pages.
- One test that constructs the splash without raising.

### Verify

- `uv run pytest tests/crmbuilder_v2/ui/ -v` passes.
- `uv run pytest tests/crmbuilder_v2/ -v` shows the full v2 suite (existing 96 tests + the new health and UI smoke tests) passing.
- `uv run crmbuilder-v2-ui` launches a window. Visually verify:
  - The sidebar is on the left with eight entries, Decisions selected by default.
  - The content area shows the placeholder label for Decisions.
  - Clicking each sidebar entry swaps the content area to that entity's placeholder.
  - The accent color appears on the selected sidebar row.
  - The window closes cleanly without error.
- After window closes, no Python or Qt errors in stderr or in `~/.crmbuilder-v2/ui.log`.

Commit: `v2: ui scaffold — package, console script, sidebar shell`.

## Step 4 — Push and report

1. Push all commits: `git push origin main`.
2. Report back to Doug with the structure described under "Reporting" below.

## Acceptance gates

This slice is complete when all of the following are true:

1. `uv run crmbuilder-v2-ui` launches and presents the sidebar with eight entries plus a placeholder content area. (PRD AC#1 — partially.)
2. Sidebar navigation swaps the content area to the corresponding placeholder.
3. `curl http://127.0.0.1:8765/health` returns 200 with `{"data": {"ok": true}, "meta": {}, "errors": null}`. (PRD AC#14.)
4. The full v2 test suite (existing + new) passes.
5. Planning records are present in the v2 database: SES-004, DEC-018 through DEC-024, seven `decided_in` references from SES-004, and an updated current status.
6. The `db-export/` directory reflects all the new records.
7. Three commits are on `origin/main`:
   - `v2: ui v0.1 planning records — SES-004, DEC-018 through DEC-024`
   - `v2: api adds GET /health endpoint`
   - `v2: ui scaffold — package, console script, sidebar shell`

## Out of slice

The following are explicitly **not** in scope for this prompt and should be left as empty modules:

- Server lifecycle (probe, spawn, ownership, splash dismissal on ready, crash banner) — slice B.
- HTTP client, typed exceptions, worker pattern, list/detail base — slice C.
- Any populated entity panels — slices D and E.
- File-watch refresh — slice F.
- Decisions create/edit/delete dialogs — slice G.
- About dialog content, friction polish — slice H.

Resist the urge to "get a head start" on later slices. Each slice has its own review pass, and that integrity matters more than getting ahead.

## Constraints

- **No edits to v1 code or methodology.** v2 work is strictly additive to v1 per DEC-003. The existing CRMBuilder v1 PySide6 application, automation pipeline, and methodology guides under `PRDs/process/` are not modified.
- **No new dependencies beyond PySide6 and pytest-qt.** Both are listed above. Anything else requires prior approval.
- **Do not modify the `vocab.py` or any access-layer code.** The UI consumes the REST surface; the access layer is unchanged in this slice.
- **Do not modify `bootstrap/` or any migration code.** Planning records are written via the live API, not through bootstrap migration.
- **Stop and ask if uncertain.** If the PRD or plan leaves a substantive question unresolved, stop and surface it rather than choosing silently.

## Reporting

After execution, produce a completion report (in your final response to Doug, not as a committed file unless asked) covering:

- **Acceptance gates** — pass/fail for each of the seven gates above.
- **Files created** — full list of files added to the repository, grouped by purpose (planning records, health endpoint, UI scaffold, tests).
- **Records written** — confirmation that SES-004, DEC-018 through DEC-024, the seven references, and the status update all wrote successfully and appear in `db-export/`.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Visual verification** — short description of what was visible when `crmbuilder-v2-ui` was launched, including any cosmetic rough edges that the H slice should clean up.
- **Deviations from this prompt** — anything that diverged from these instructions, with reason.
- **New decisions or open questions surfaced during execution** — anything that came up that should be captured as a new DEC or as an item for the next planning conversation. Do not silently make architectural choices that should have been planning decisions.
- **What slice B will need** — any setup or context that B should be aware of.

---

## Appendix A — Decision body text (verbatim)

The text below is to be written verbatim into the `context`, `decision`, `rationale`, `alternatives_considered`, and `consequences` fields of each decision record. Do not paraphrase or summarize. Multi-line fields are written as-is into the database; the access layer treats them as opaque strings.

### DEC-018 — UI is a standalone application, not embedded in the v1 PySide6 app

**context**

The v2 storage system needs a way for a local user to view and edit governance content outside Claude sessions. Today the only options are curl against the REST API or direct inspection of the JSON snapshots — neither is comfortable for browsing or editing. A user-interface workstream is the natural answer. The existing CRMBuilder v1 PySide6 application already has a tabbed structure (Configure, Verify, Audit, Deployment) and could plausibly host the v2 UI as an additional tab.

**decision**

The v2 UI is a separate PySide6 desktop application installed as its own console script (`crmbuilder-v2-ui`), with its own main window, separate from the existing v1 application. The v1 application is not modified.

**rationale**

V1 and v2 have distinct purposes, distinct release cycles, and per DEC-003 are tracked as separate workstreams. Embedding the v2 UI as a tab in the v1 application entangles those release cycles — every v1 release would have to consider the v2 surface, and every v2 surface change would have to coordinate with v1 testing. The v2 separation principle established in DEC-003 is most cleanly preserved by keeping the v2 UI in its own application.

**alternatives_considered**

- New tab in the existing v1 application's main window. Rejected — entangles release cycles and contradicts the v2 separation principle from DEC-003. Reusing window chrome is a small benefit; the cost in coupling is larger.
- Both standalone and embedded, with shared widgets and two integration points. Rejected — premature; pays the cost of two integrations before either is proven valuable. A standalone app whose widgets happen to be reusable later is a strictly better starting position.

**consequences**

A new console script `crmbuilder-v2-ui` is registered alongside `crmbuilder-v2-api` and `crmbuilder-v2-mcp`. UI code lives at `crmbuilder-v2/src/crmbuilder_v2/ui/`, in the v2 package, separate from the v1 codebase. The v1 codebase is unaffected by UI work. If a v1 tab is wanted later, it can be added as a thin wrapper that hosts a subset of the v2 UI's widgets — the standalone app does not preclude that path.

---

### DEC-019 — UI consumes the REST API over HTTP, not the access layer directly

**context**

Per DEC-005 the storage stack has two viable Python entry points: the access layer (importable directly from any Python process in the repository) and the REST API (a network endpoint at `http://127.0.0.1:8765`). The v2 UI runs in the same process tree on the same machine as the storage system, so it could plausibly consume either interface.

**decision**

The UI consumes the storage system exclusively through its REST API, treating the API as a black box reached at the configured base URL. The UI does not import or call the access-layer modules directly.

**rationale**

The REST API is the durable productization-path interface per DEC-005 — when productization happens, it becomes the hosted endpoint with authentication added. Building the UI as a REST client makes the UI dogfood that interface and surfaces bugs in the contract early, where they are cheap to fix. The error envelope, status codes, validation behavior, and OpenAPI surface are specified and tested at the REST boundary. If the UI consumed the access layer directly, the REST surface would not be exercised by a real consumer and could drift from real consumer needs. The added cost — a second process must be running — is small and is addressed by DEC-023 (subprocess management).

**alternatives_considered**

- Direct access-layer imports. Rejected — skips validation of the REST surface; couples the UI to access-layer Python signatures rather than the durable HTTP contract; complicates any future remote or multi-host operation; loses the natural symmetry with the MCP server, which is itself a thin client of the REST API.
- Hybrid (a `StorageClient` protocol with both HTTP and access-layer implementations behind it, selectable by config). Rejected — over-engineered for v0.1; the abstraction adds maintenance burden to validate a tradeoff that is not needed at this stage. If a direct-access path becomes worth having later, it can be added as a second implementation behind the existing client interface without rework.

**consequences**

The UI requires the REST API process to be running. DEC-023 specifies how the UI ensures this. The UI cannot bypass API-level validation, which is the intent — every write goes through the same Pydantic and access-layer checks that any other consumer goes through. If the API ever gains authentication, the UI gains it too, with no code changes beyond credential handling. A future remote/multi-host configuration is possible without rearchitecting the UI's data layer; only the file-watch refresh strategy (DEC-022) would need replacement.

---

### DEC-020 — v0.1 scope: read-only across all entities, full CRUD for decisions only

**context**

The storage system has seven first-class entity types (charter, status, decisions, sessions, risks, planning items, topics) plus the references graph that connects them. Each entity needs at minimum a viewing surface, and several plausibly need an editing surface. Some have non-trivial edit semantics: charter and status are versioned (replace creates a new version), sessions are append-only per DEC-013, and references-as-edges is its own subsystem. v0.1 needs to ship in a reasonable timeframe without committing to designing every edit surface up front.

**decision**

v0.1 of the UI ships read-only views for all seven entities and the references graph, plus full create/read/update/delete operations for decisions only. All other entities receive read-only treatment in v0.1; their edit surfaces are deferred to v0.2.

**rationale**

Decisions are the highest-frequency write target — recording a decision after a planning conversation is a routine operation that benefits substantially from a UI surface. Sessions are append-only with effectively one writer (the closing Claude conversation per DEC-013); they do not need a UI write path in v0.1. Charter and status are versioned replace operations whose UX (replace versus edit, version history browsing, payload editor for arbitrary JSON) deserves its own design conversation rather than a quick first cut. Risks, planning items, and topics are lower-frequency and can wait. References-as-edges is its own subsystem — a graph view with create/delete edge interaction is a separate design problem and is its own slice of work. Concentrating v0.1 write surface on a single entity allows the architectural pieces (subprocess management, threading, error envelope handling, file watching, dialog patterns) to be proven on a single end-to-end path before being generalized.

**alternatives_considered**

- Read-only across all entities, with no write surface anywhere. Rejected — leaves the most common write operation (recording a decision) without a UI path, which is a real gap in the value v0.1 delivers. The point of building a UI is partly so writes do not have to go through curl or MCP for routine operations.
- Full CRUD across all seven entities. Rejected — multiplies design and build effort by a factor of roughly seven without proportional value. Charter/status versioning, references graph, and append-only sessions are each separate design conversations that should not be done in parallel with the basic infrastructure work. Trying to do all of them at once produces a worse outcome on each.

**consequences**

After v0.1, the UI cannot yet be the sole interface for v2 governance. Sessions, risks, planning items, topics, references, and charter/status updates continue to be written through MCP or via curl. v0.2 is the intended workstream that closes those gaps, prioritized by the friction observed during v0.1 use. The architecture put in place for decisions CRUD (HTTP client, dialog pattern, error surfacing, refresh wiring) generalizes naturally to the other entities, so v0.2 is largely additive rather than requiring rework.

---

### DEC-021 — Sidebar navigation with master/detail panes

**context**

The v2 UI must let the user move between seven entity types and the references graph. Common navigation paradigms include top tabs, sidebar navigation, dashboard with drill-in, and single-page-with-anchors. The choice shapes the entire app structure, the visual language, and how cleanly the app scales as v2 grows beyond governance entities into methodology entities (personas, processes, requirements, etc.) in follow-on work.

**decision**

The UI uses a left-hand sidebar with one entry per entity type (Charter, Status, Decisions, Sessions, Risks, Planning Items, Topics, References). Selecting a sidebar entry swaps the right pane to that entity's view. Each entity's view uses a master/detail layout — list of records on the left, detail of the selected record on the right. Charter and status, being singletons with version history, use a slight variant in which the list pane shows version numbers and the detail pane shows the selected version's payload.

**rationale**

Sidebar navigation scales as v2 grows. Eight entries today; methodology entities planned for follow-on work (personas, processes, requirements, manual-config items, test specs) become additional sidebar entries with no overflow problem. The existing CRM Builder v1 Deployment tab uses a sidebar+content pattern, so the visual language is already established in the codebase — this reduces the design surface for v2. Master/detail within an entity view matches the natural shape of every governance entity: a list of identifiers and titles to scan, and a record to read in full when selected. The structure is uniform across entities, which keeps the per-entity panel implementation lightweight.

**alternatives_considered**

- Top tabs (one per entity). Rejected — eight tabs is at the cramped end of the QTabWidget pattern; the methodology entities planned for v2 follow-on would push it past viable. Tabs also imply parallel workflows, which is not really what is happening here — the user is looking at one body of governance data and navigating between facets of it.
- Dashboard home with summary cards drilling into per-entity lists. Rejected for v0.1 — adds design and code work without proportional value at this stage. A dashboard can layer onto a working sidebar app later as a "Home" entry.
- Single scrolling page with anchor jumps. Rejected — does not scale beyond a few entities with small data, and breaks down entirely when one entity has more than a handful of records.

**consequences**

The main window structure is a sidebar (left, fixed-width) plus a `QStackedWidget` (right, swapping per selection). Each entity's panel implements a common master/detail interface, sharing a base class (`ListDetailPanel`) for the layout and toolbar shape. Adding a new entity in future work means adding a sidebar entry and a new panel module — the main window and the base class do not change. Charter and status panels use a versioned variant of the base class.

---

### DEC-022 — File-watch on db-export/ for live refresh, manual Refresh button as fallback

**context**

The v2 UI is concurrent with the rest of the v2 stack. Claude can write to the storage system via MCP while the UI is open. The user can edit a decision in the UI while Claude is mid-conversation. The UI needs a strategy for keeping its rendered data current without requiring the user to remember to refresh manually and without generating a steady drip of API calls when nothing has changed.

**decision**

A `QFileSystemWatcher` watches the `PRDs/product/crmbuilder-v2/db-export/` directory. When a snapshot file in that directory changes, the affected entity panel refetches silently from the API. Every panel also exposes a manual Refresh button as a fallback for cases where the file watcher misses an event (network filesystems, OS-specific event coalescing).

**rationale**

The JSON snapshots are atomically rewritten on every successful database write — this is an existing architectural property of the storage system, established for git-tracking purposes. The mtime of a snapshot file changes if and only if a write happened to the corresponding entity table. This makes the snapshot directory a perfect change signal that exists for free, without any addition to the storage system. Using a file watcher is a Qt-native pattern (`QFileSystemWatcher`), integrates with the rest of the UI's signal/slot architecture, and produces no work when the database is idle. The manual Refresh button covers the cases where the file watcher's underlying OS mechanism is unreliable.

**alternatives_considered**

- Periodic polling on a `QTimer`. Rejected — generates a steady drip of GETs on every panel even when nothing has changed; choosing the polling interval is a tradeoff between freshness and noise that a signal-based mechanism avoids entirely.
- Manual refresh only. Rejected — forces the user to remember to refresh; "I just recorded the decision but I don't see it" friction is guaranteed to happen and is exactly the friction a UI should remove.
- WebSocket push from the API to the UI. Rejected for v0.1 — adds a bidirectional channel and corresponding server-side state for what is currently a localhost-only single-client problem. The complexity is not justified at this scale.

**consequences**

The UI process must have read access to the snapshot directory. Both UI and API processes must agree on the snapshot directory path; this is achieved by both reading from `crmbuilder_v2.config.get_settings()`, which sources from the same environment variables. The file-watch mechanism only works on a shared filesystem — if a future configuration runs the UI and API on separate hosts, the refresh strategy will need replacement. A "stale" indicator on sidebar entries communicates writes to non-displayed entity types so the user knows something has changed even when not currently looking at it.

---

### DEC-023 — Detect-then-launch API subprocess management

**context**

The v2 UI requires the REST API process (`crmbuilder-v2-api`) to be running. The MCP server also requires the API to be running — Claude clients connecting via MCP are blocked otherwise. A common day-to-day flow has both Claude (via MCP) and the user (via the UI) wanting to talk to the API simultaneously, often with the user having already launched the API in a terminal so MCP can use it. The UI's startup behavior needs to handle both the case where the API is already running and the case where it is not.

**decision**

On startup, the UI probes the configured API URL (`GET /health` with a one-second timeout). If the API responds, the UI uses it and tracks ownership as "external". If no response, the UI spawns `crmbuilder-v2-api` as a managed `QProcess` subprocess, tracks ownership as "owned", and waits for readiness by polling `/health` every 250ms for up to 10 seconds. On UI shutdown, the UI terminates only subprocesses it spawned itself; externally-launched API processes are left alone.

**rationale**

The "MCP needs the API too" overlap is the common case, not an edge case. A "always launch our own" policy would fail when the API is already running, because the spawn would collide on the configured port. A "always require external launch" policy would burden the user with a setup step that the UI can do for them. Detect-then-launch handles both cases gracefully and adds only a single boolean of state to the UI (the ownership flag). The 10-second wait with 250ms polling gives 40 chances to detect readiness, which is sufficient for any realistic API startup time on the local machine.

**alternatives_considered**

- Always launch (own the subprocess unconditionally). Rejected — fails when the API is already running, which is the common case for users running MCP. Would force the user to choose between MCP and the UI, which is the wrong choice to put in front of them.
- Always require external launch (UI does not spawn anything). Rejected — pushes setup burden onto the user for what the UI can handle automatically. Worst end-user experience.

**consequences**

The UI spawns the API with `QProcess`, surfaces stderr in failure dialogs, and shows a "Starting storage server…" splash while waiting for readiness. A new `GET /health` endpoint is added to the API to provide a probe target — this is a small additive change to the existing API surface and is delivered alongside the first slice of UI work. If the owned subprocess crashes mid-session, the UI surfaces a non-modal banner with a Reconnect button and disables data-dependent UI; no background retry loop runs, so the user controls when to retry.

---

### DEC-024 — Native Qt look for v0.1; styling pass deferred

**context**

The v2 UI could ship with a designed visual language (custom palette, typography, spacing, widget styling), with native Qt defaults, or somewhere between. The choice carries different cost: a real designed pass is a substantial workstream with its own design conversations, while native Qt is essentially free. v0.1 needs to ship a functional application without committing to a visual identity that is likely to change once a working app exists to react to.

**decision**

v0.1 ships with native Qt look on whatever platform it runs on, plus a minimal QSS stub applying `#1F3864` as accent color and Arial as the default font. A real designed visual pass is deferred to v0.2 or later.

**rationale**

Styling is genuinely a separate problem from "does the navigation, data flow, refresh, and CRUD work." Doing both at once means changes in either dimension feel like they break the other. Native Qt rendering on Linux/macOS/Windows is functional and unembarrassing for a developer/product-owner tool — it is not great visual design, but it is not bad either. Deferring the styling decision until a working app exists produces better design decisions than designing in the abstract. The minimal QSS stub costs essentially nothing and gives the v2 UI a small visual link to v2 document standards (the navy color `#1F3864` and the Arial font both come from those standards), so the v2 UI feels visually adjacent to the v2 documents it represents without committing to a full visual identity.

**alternatives_considered**

- Match the v1 PySide6 application's existing styling (palette, fonts, QSS). Rejected — ties v0.1 to v1's visual decisions; a designed visual pass is best done with the working v2 UI to react to, and v2's design language can plausibly diverge from v1's.
- Distinct designed visual identity for v2 from day one. Rejected — design effort competes with functional effort in v0.1; design work without a working app to react to tends to produce decisions that need rework as soon as the app exists. Deferring is the cheaper path even after the eventual styling pass is paid for.

**consequences**

The application uses native Qt widget rendering. A small `styling.py` module applies a QSS string at app startup that sets the default font to Arial and gives selected list items and focused buttons the navy accent. A real styling pass is a v0.2 design conversation conducted with the working v0.1 app in front of both parties. If user feedback during v0.1 surfaces specific styling friction (low contrast, illegible at small sizes, awkward focus indicators), targeted fixes can be applied during the v0.1 polish slice without committing to a full designed pass.
