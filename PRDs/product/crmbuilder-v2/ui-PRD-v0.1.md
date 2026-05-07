# CRMBuilder v2 — User Interface PRD

**Version:** 0.1 (draft)
**Last Updated:** 05-07-26 16:45
**Status:** Draft — pending approval

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-07-26 | Initial draft. Specifies a standalone PySide6 desktop application that consumes the storage system REST API. v0.1 covers read-only views for all seven governance entities and full create/read/update/delete operations for decisions. Captures seven architectural decisions (DEC-018 through DEC-024) for recording in the v2 database after PRD approval. |

---

## 1. Overview

### Purpose

This document specifies the requirements for the CRMBuilder v2 user interface (UI) v0.1: a standalone PySide6 desktop application that lets a local user view and edit content stored in the v2 storage system. It is the build specification handed to Claude Code, which produces its own implementation plan from these requirements and executes it through a series of prompts. This PRD specifies what a functioning UI must do; how to assemble it across slices is captured separately in the implementation plan.

### Background

CRMBuilder v2's storage system landed as v0.1 on 05-07-26 (per change log entries through commit `12b96bc`, `52620da`, `03209a8`). The storage system exposes governance and methodology artifacts through three surfaces: a Python access layer for in-process callers, a REST API at `http://127.0.0.1:8765`, and an MCP stdio server for Claude clients.

Today the only practical way to view or edit the storage system's content outside a Claude session is `curl` against the REST API or direct inspection of the git-tracked JSON snapshots. Both work; neither is comfortable for browsing twenty decisions or scanning recent sessions, and neither offers a confirmation surface for writes. The UI specified by this PRD addresses that gap: a desktop application that puts a navigable interface over the storage system, lets the user read all governance content at a glance, and supports full lifecycle editing for the highest-frequency write target (decisions).

### Source decisions

This PRD does not re-derive architectural decisions; it specifies requirements grounded in the following decision records, which should be considered authoritative.

Existing decisions:

- **DEC-005 — Storage stack: SQLite + access layer + REST API + MCP server.** Establishes the four-layer architecture this UI consumes. The REST API is the durable productization-path interface; this UI uses it as such.
- **DEC-011 — Session orientation protocol (tiered).** Defines the read patterns the UI's read-only views are designed around — current charter, current status, recent sessions, decisions for a given session.

Forthcoming decisions (to be recorded after this PRD is approved, see Section 11):

- **DEC-018 — UI is a standalone application, not embedded in the v1 PySide6 app.** Preserves the v1/v2 release-cycle separation principle.
- **DEC-019 — UI consumes the REST API over HTTP, not the access layer directly.** Dogfoods the productization-path interface and keeps the UI portable across single-process, multi-process, and future remote configurations.
- **DEC-020 — v0.1 scope: read-only across all entities, full CRUD for decisions only.** Establishes a narrow, useful first slice.
- **DEC-021 — Sidebar navigation with master/detail panes.** Establishes the screen pattern.
- **DEC-022 — File-watch on `db-export/` for live refresh, manual Refresh button as fallback.** Leverages the snapshot side channel as a free change signal.
- **DEC-023 — Detect-then-launch API subprocess management.** Cooperates with externally-running API instances rather than fighting them.
- **DEC-024 — Native Qt look for v0.1; styling pass deferred.** Defers visual design until the structure is solid.

---

## 2. Scope

### In Scope

The following are required deliverables for v0.1.

1. **Standalone PySide6 desktop application.** Console script `crmbuilder-v2-ui` registered alongside the existing three (`crmbuilder-v2-api`, `crmbuilder-v2-mcp`, `crmbuilder-v2-bootstrap-db`) in the v2 package's `pyproject.toml`. Code lives at `crmbuilder-v2/src/crmbuilder_v2/ui/`.

2. **REST API client.** A typed Python client module that wraps the storage system REST endpoints, parses the envelope response shape, surfaces validation/conflict/not-found errors as typed exceptions, and runs every call through a `QThread` worker so the UI thread never blocks on I/O.

3. **REST API server lifecycle management.** On launch, the UI probes the configured API URL. If a server is already running, the UI uses it. If not, the UI spawns `crmbuilder-v2-api` as a managed subprocess, waits for readiness, and tracks ownership so it terminates only the subprocess it spawned itself. Includes a new `GET /health` endpoint added to the API.

4. **Sidebar navigation.** Left-hand sidebar with one entry per entity type: Charter, Status, Decisions, Sessions, Risks, Planning Items, Topics, References. Selecting an entry swaps the right-hand content area to that entity's view.

5. **Master/detail entity views.** Each entity view presents a list pane (left) and a detail pane (right). Selecting a row in the list updates the detail pane to show that record's full content.

6. **Read-only views for six entities.** Charter, Status, Sessions, Risks, Planning Items, Topics, References each get a functional list+detail view that renders live data from the API.

7. **Versioned-content view variant for Charter and Status.** Both are singletons with version history. The list pane shows version numbers and timestamps; the detail pane shows the selected version's full payload. The current version is visually marked.

8. **Full create/read/update/delete for Decisions.** Beyond the read-only list+detail view, decisions get a Create dialog, an Edit dialog, and a Delete confirmation dialog. Writes go through the REST API; validation errors returned in the envelope surface as inline messages on the offending field. Supersedes/superseded-by linkage is editable through the Edit dialog.

9. **Live refresh.** A `QFileSystemWatcher` watches the JSON snapshot directory (`PRDs/product/crmbuilder-v2/db-export/`). When a snapshot file changes, the affected entity's currently-rendered list refetches from the API. Every list view also exposes a manual Refresh button as a fallback.

10. **Subprocess crash handling.** If a UI-spawned API subprocess dies unexpectedly while the UI is running, the UI displays a non-modal banner with a Reconnect button. Reconnect re-probes and, if still no server, re-spawns. The UI does not crash and does not silently retry in the background.

11. **Minimal styling stub.** Native Qt look across the application, with a small QSS layer applying `#1F3864` as accent color and Arial as the default font, matching the v2 document standards. No further design work.

### Out of Scope

The following are explicitly deferred to v0.2 or later.

- **Create/update/delete for entities other than decisions.** Sessions, risks, planning items, topics get read-only treatment in v0.1.
- **Charter and Status replace flows.** Both support versioned replacement via REST `PUT`, but the v0.1 UI does not expose that capability. Both stay read-only including version history browsing.
- **References graph view.** v0.1 displays references as plain text on each entity's detail pane (e.g., "Decided in: SES-002"). A graph-style visualization with create/delete edge interaction is deferred.
- **Change log activity feed.** The change log table captures every mutation but is not surfaced in v0.1.
- **Snapshot regeneration / DB management surfaces.** The UI does not expose buttons to bootstrap the DB, regenerate snapshots, or run migrations. Those operations remain command-line.
- **Real styling pass.** Native Qt with the minimal accent stub for v0.1; coherent visual design is a v0.2 conversation with a working app to react to.
- **Authentication, multi-user, remote operation.** v0.1 is single-user, localhost only. Aligns with the storage system's v0.1 posture.
- **App icon, About dialog beyond version string, splash branding.** Light polish included; full identity work deferred.

---

## 3. Architecture

### Process model

```
┌─────────────────────────────────────────────────────┐
│  PySide6 UI process (crmbuilder-v2-ui)              │
│                                                     │
│  ┌──────────────────┐    ┌──────────────────────┐   │
│  │  UI thread       │    │  QThread workers     │   │
│  │  (Qt event loop) │◄──►│  (HTTP calls)        │   │
│  └──────────────────┘    └──────────┬───────────┘   │
│                                     │               │
│  ┌──────────────────┐               │               │
│  │  QFileSystem-    │               │               │
│  │  Watcher         │               │               │
│  └──────────────────┘               │               │
└─────────────────────────────────────┼───────────────┘
                                      │ HTTP
┌─────────────────────────────────────▼───────────────┐
│  REST API subprocess (crmbuilder-v2-api)            │
│  Spawned by UI if not already running               │
└─────────────────────────────────────────────────────┘
                                      │
                                      │ writes
┌─────────────────────────────────────▼───────────────┐
│  SQLite database + JSON snapshot directory          │
└─────────────────────────────────────────────────────┘
                ▲
                │ filesystem events
                │ (snapshot changes)
                └────────── observed by QFileSystemWatcher
```

### Layer responsibilities

| Layer | Module | Responsibility |
|---|---|---|
| Application shell | `crmbuilder_v2.ui.app` | Qt application initialization, main window, sidebar, content area, lifecycle wiring |
| Storage client | `crmbuilder_v2.ui.client` | Typed REST methods, envelope parsing, error mapping. Pure Python; no Qt dependencies. |
| Workers | `crmbuilder_v2.ui.workers` | `QThread` wrappers around storage client calls. UI thread never blocks. |
| Server lifecycle | `crmbuilder_v2.ui.server_lifecycle` | Probe, spawn, track, terminate the API subprocess. `QProcess`-based. |
| Refresh service | `crmbuilder_v2.ui.refresh` | `QFileSystemWatcher` on the snapshot directory; emits per-entity-type "data changed" signals. |
| Entity panels | `crmbuilder_v2.ui.panels.*` | One module per entity type. Each builds a list+detail panel using the shared base classes. |
| Dialogs | `crmbuilder_v2.ui.dialogs.*` | Decision create/edit dialogs, delete confirmation, generic error dialog. |
| Base widgets | `crmbuilder_v2.ui.base` | Reusable list/detail panel base classes; styling stub; constants. |

### Configuration

The UI reads `crmbuilder_v2.config.get_settings()` directly — same source the API and access layer use. This guarantees the UI and the API agree on database path, snapshot directory, and API host/port without any duplicated configuration.

The `CRMBUILDER_V2_API_BASE_URL` setting determines where the UI probes for the API. The `CRMBUILDER_V2_EXPORT_DIR` setting determines what directory the file watcher watches.

---

## 4. Functional Requirements

### 4.1 Application startup

On launch, the UI follows this sequence.

1. Construct the Qt application.
2. Show a "Starting storage server…" splash screen (logo or text, no progress bar).
3. Probe `GET {api_base_url}/health` with a one-second timeout.
4. If 200, set ownership to "external" and proceed to step 7.
5. If no response, spawn `crmbuilder-v2-api` via `QProcess`, set ownership to "owned", and poll `/health` every 250ms for up to 10 seconds.
6. If the spawned subprocess never becomes ready, dismiss the splash, show a modal error dialog with the subprocess stderr captured, and exit.
7. Dismiss the splash, render the main window.

### 4.2 Application shutdown

On main window close, the UI follows this sequence.

1. Stop the file watcher.
2. Cancel any in-flight HTTP requests.
3. If ownership is "owned", terminate the API subprocess (graceful with SIGTERM, then SIGKILL after a 3-second timeout).
4. If ownership is "external", do nothing to the API process.
5. Exit.

### 4.3 Subprocess crash recovery

If the API subprocess we own exits unexpectedly while the UI is running, a non-modal banner appears across the top of the main window: "Storage server stopped. [Reconnect]". The Reconnect button re-runs the lifecycle probe-then-spawn from Section 4.1 starting at step 3. Until reconnected, all entity panels show a disabled state with a "No connection" overlay. No background retry loop runs.

### 4.4 Sidebar navigation

The sidebar is a single-column list with eight entries in this order: Charter, Status, Decisions, Sessions, Risks, Planning Items, Topics, References.

- Each entry is a clickable row with the entity name as a label.
- The selected entry is visually highlighted.
- On launch, the default selection is Decisions.
- Selecting an entry swaps the content area to that entity's panel. Panel state (selected row, scroll position) is preserved when switching away and back.

### 4.5 Master/detail entity panels

Every entity panel has the same internal structure:

- **Top toolbar:** entity-name title, manual Refresh button, status label ("12 records" / "Loading…" / "Connection lost"), and entity-specific action buttons (e.g., "New Decision" for the decisions panel).
- **List pane (left, ~40% width):** a `QTableView` with columns appropriate to the entity. Sortable by column header click. Single-row selection.
- **Detail pane (right, ~60% width):** read-only field display showing all fields of the selected record. For long text fields (context, decision, rationale, etc. on decisions), a scrollable read-only text widget. For relationship fields (supersedes/superseded_by on decisions, parent_topic on topics), a clickable link that navigates to the referenced record.

### 4.6 Per-entity column specifications

The list pane columns differ per entity. Detail pane shows all fields.

**Decisions:** Identifier, Title, Decision Date, Status, Superseded By.

**Sessions:** Identifier, Title, Session Date, Status.

**Risks:** Identifier, Title, Probability, Impact, Status.

**Planning Items:** Identifier, Title, Type, Status.

**Topics:** Identifier, Name, Parent Topic.

**References:** Source, Relationship, Target. (Source and Target each render as `{type}:{id}` strings.)

**Charter and Status (versioned variant):** Version Number, Created At, Current. The list shows all versions newest-first; the current version row has a checkmark or bold indicator. The detail pane shows the selected version's `payload` (a JSON-shaped dict) rendered as a key/value display.

### 4.7 Decisions create flow

Triggered by clicking "New Decision" in the decisions panel toolbar. Opens a modal dialog with these inputs:

- **Identifier** — text field, required, format hint "DEC-NNN"
- **Title** — text field, required
- **Decision Date** — text field, required, format hint "MM-DD-YY"
- **Status** — dropdown, required, values from `DECISION_STATUSES` vocabulary (`Active`, `Superseded`, `Withdrawn`)
- **Context** — multi-line text area
- **Decision** — multi-line text area
- **Rationale** — multi-line text area
- **Alternatives Considered** — multi-line text area
- **Consequences** — multi-line text area
- **Supersedes** — text field with format hint "DEC-NNN" or empty
- **Superseded By** — text field with format hint "DEC-NNN" or empty
- **Save** and **Cancel** buttons

Save behavior:
- Empty optional fields are submitted as empty strings (matching the API schema defaults).
- The submission goes through a `QThread` worker.
- On success (HTTP 201), the dialog closes and the decisions list refreshes (the file watcher will also trigger a refresh, but the explicit refresh avoids any window where the UI looks stale).
- On HTTP 400 (validation error), the offending field is highlighted with the error message rendered inline. The dialog stays open.
- On HTTP 409 (duplicate identifier), the Identifier field is highlighted with "An identifier with this value already exists." The dialog stays open.
- On any other error, a generic error dialog appears and the dialog stays open.

### 4.8 Decisions edit flow

Triggered by clicking an "Edit" button in the decisions detail pane. Opens the same dialog shape as create, pre-populated with the current values. The Identifier field is read-only (cannot be changed).

Save behavior:
- Only fields that changed are submitted (the API supports partial updates via PATCH).
- On success (HTTP 200), the dialog closes and the decisions list+detail refreshes.
- Error handling matches create.

### 4.9 Decisions delete flow

Triggered by clicking a "Delete" button in the decisions detail pane. Opens a confirmation dialog: "Delete DEC-007 — Universal references pattern with controlled relationship vocabulary? This cannot be undone."

Confirm behavior:
- Sends `DELETE /decisions/{id}` through a worker.
- On success, the dialog closes, the list refreshes, and the detail pane clears (no row selected).
- On HTTP 409 (decision is referenced by other records), an error message in the confirmation dialog explains the conflict and offers only a Cancel button.
- On any other error, a generic error dialog appears.

### 4.10 Live refresh

A `QFileSystemWatcher` watches the snapshot directory (`CRMBUILDER_V2_EXPORT_DIR`). The watcher emits when any file in that directory changes. On a change event, the UI:

1. Determines which entity type's snapshot changed (filename matches entity-type to file-name mapping: `decisions.json`, `sessions.json`, etc.).
2. If the changed entity type matches the currently-displayed panel, refetch its list silently (no spinner, just swap data when ready).
3. If it doesn't match the current panel, mark the corresponding sidebar entry as "stale" (a small dot indicator), to be cleared when the user navigates to that panel and the refresh runs.

The manual Refresh button on every panel triggers an immediate refetch regardless of file-watcher state. It exists as a recovery mechanism when the watcher misses an event for any reason (network filesystem, OS-specific quirk).

### 4.11 Error handling

The REST API returns errors in the envelope shape:

```json
{
  "data": null,
  "meta": {},
  "errors": [{ "code": "validation_error", "field": "status", "message": "..." }]
}
```

The UI maps these to typed Python exceptions in the storage client:

| HTTP | Error code | Exception | UI surface |
|---|---|---|---|
| 400 | `validation_error` | `ValidationError` | Inline on offending field if `field` is populated; modal otherwise |
| 404 | `not_found` | `NotFoundError` | Modal error dialog |
| 409 | `conflict_error` | `ConflictError` | Inline if specific field implied; modal otherwise |
| 422 | `request_shape_error` | `RequestShapeError` | Modal — programmer error, should not occur in production |
| 500+ | (any) | `ServerError` | Modal error dialog with raw error text |
| (network) | n/a | `ConnectionError` | Banner "Storage server unreachable. [Reconnect]" |

---

## 5. Non-Functional Requirements

### 5.1 Threading

Every HTTP call runs in a `QThread` worker. The UI thread is reserved for Qt event handling, widget updates, and the file-watcher signal slot. No `time.sleep`, no synchronous network I/O on the UI thread.

### 5.2 Responsiveness

- Splash dismisses within 11 seconds of launch (10 for subprocess startup + 1 for probe).
- List refetch on a panel switch completes in under 500ms on localhost.
- Edit dialog open completes in under 100ms (data already in memory from the list).
- Manual Refresh feedback (status label change to "Loading…") appears within 50ms of click.

### 5.3 Resource use

- File watcher watches one directory; no recursive watching.
- HTTP client uses connection pooling (`httpx.AsyncClient` or `requests.Session`).
- Worker threads are short-lived and torn down after each call.
- No timer-based polling anywhere.

### 5.4 Logging

- The UI logs to a file at `~/.crmbuilder-v2/ui.log` (rotated at 10MB, keep 3).
- Log lines: subprocess lifecycle events, HTTP errors (status, URL, error code), file-watcher events.
- No request/response bodies logged (avoids accidental capture of governance content).
- `--verbose` flag at launch enables DEBUG level for troubleshooting.

### 5.5 Platform support

- Linux (primary development platform).
- macOS (verified to launch and interact correctly).
- Windows is not a v0.1 target. Code that doesn't deliberately diverge across platforms should still work on Windows; explicit Windows verification is deferred.

### 5.6 Dependencies

Adds to the existing v2 package's dependencies:
- `PySide6` (the desktop framework)
- `httpx` (already a dep for the MCP server) or `requests` — implementer's choice

No new build tools, no packaging changes beyond the new console script entry.

---

## 6. Acceptance Criteria

The UI v0.1 is considered functionally complete when all of the following are true.

1. `uv run crmbuilder-v2-ui` launches the application from a fresh checkout.
2. Application launch correctly handles both cases: API already running (does not spawn a duplicate), and API not running (spawns and waits for readiness).
3. Subprocess crash handling works: killing the API process while the UI is running surfaces the banner; clicking Reconnect successfully restarts the API and re-renders the panels.
4. All eight sidebar entries navigate to their panels and render live data from the API.
5. Charter and Status panels show version history with the current version marked.
6. References on decisions render in the detail pane and are clickable, navigating to the referenced session.
7. Decisions create flow successfully posts a new decision and the new row appears in the list.
8. Decisions edit flow successfully PATCHes an existing decision and the change is reflected.
9. Decisions delete flow successfully deletes a decision and the row disappears.
10. Validation errors from the API (e.g., invalid status value, duplicate identifier) display inline on the offending field, dialog stays open.
11. Writing a new decision via MCP while the UI is open causes the decisions list to update without manual refresh.
12. Manual Refresh button on every panel triggers a successful refetch.
13. Application shutdown cleanly terminates any owned subprocess and leaves no orphan processes.
14. The new `GET /health` endpoint on the API returns 200 with a `data: {"ok": true}` envelope.
15. The full app passes a smoke test on Linux. Behavior verified visually on macOS.

---

## 7. Implementation Approach

The implementation plan (`ui-implementation-plan.md`) breaks this PRD into eight prompts (`v2-ui-A` through `v2-ui-H`), each producing an independently testable slice. The implementation plan is the operational counterpart to this PRD and is approved separately.

In summary:

- **A — scaffold:** package skeleton, console script registration, empty main window with sidebar, `/health` endpoint.
- **B — server lifecycle:** detect-then-launch, splash, crash banner, ownership tracking.
- **C — HTTP client + list/detail base:** typed client, worker pattern, reusable base classes.
- **D — read-only views round 1:** decisions, sessions, risks.
- **E — read-only views round 2:** charter, status, topics, planning items, references.
- **F — file-watch refresh:** watcher, per-entity refresh, manual Refresh buttons.
- **G — decisions CRUD:** create, edit, delete dialogs with full error envelope handling.
- **H — polish + styling stub:** QSS for accent and font, About dialog, friction fixes.

---

## 8. Dependencies and Constraints

### Dependencies on the storage system

This UI depends on the storage system v0.1 being functional and the REST API being launchable. It also requires one small additive change: a new `GET /health` endpoint. That endpoint is delivered as part of `v2-ui-A` (the scaffold prompt) so the dependency lands at the same time as its first consumer.

### No changes to the access layer or schema

This UI does not require any changes to the SQLAlchemy models, vocab, repositories, or database schema. All required behavior is reachable through the existing REST surface.

### No changes to the v1 application

This UI is independent of the existing CRMBuilder v1 PySide6 application. v1 release cycles are unaffected.

### Constraint: process model assumes localhost

The detect-then-launch model assumes the UI and the API share a filesystem (so `QFileSystemWatcher` can observe API-side writes) and share a host (so `127.0.0.1` is meaningful). Multi-host operation is out of scope; if it becomes a requirement, the file-watch refresh strategy needs replacement.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `QFileSystemWatcher` misses events on some platforms or filesystems | Medium | Medium | Manual Refresh button on every panel as fallback; documented as a known limitation. |
| Subprocess startup race: probe times out before the API is actually ready | Low | Low | 10-second timeout with 250ms polling gives 40 chances; logged stderr from subprocess if it fails. |
| Validation errors from access layer don't always populate `field` in the envelope | Medium | Low | Fall back to modal error dialog when `field` is missing. Improvement to the API's error shape is a follow-up item, not a blocker. |
| User runs the UI against a different DB than the running API (env var mismatch) | Low | Medium | Both processes resolve config from the same `get_settings()`; the UI is the spawn-or-reuse decider, so it can't outvote itself. External-launch case: the UI displays the resolved DB path in the About dialog so the user can verify. |
| Long-running edit dialogs hold a stale view of the record | Low | Low | Out of scope for v0.1; last-write-wins is acceptable. v0.2 may introduce optimistic concurrency. |

---

## 10. Open Questions

1. **What does the v0.1 About dialog include?** Current proposal: app name, version (from `pyproject.toml`), API URL, DB path, snapshot directory. Acceptable to defer.
2. **Should the sidebar show counts per entity?** ("Decisions (16)", "Sessions (3)", etc.) Provides useful at-a-glance info but adds a refetch burden on every change. Recommend: defer to v0.2 once the file-watch path is proven.
3. **Should the application offer a "Copy as JSON" action on detail panes?** Useful for piping records into other tools or chats. Cheap to add. Recommend: defer to v0.2 unless trivially included.
4. **Should the references displayed on a decision detail pane be filterable by relationship type?** Decisions can have multiple inbound and outbound references. Recommend: simple list for v0.1, filterable in v0.2 if it gets noisy.

---

## 11. Decisions to Be Recorded

Per DEC-014 (every v2 conversation produces a session record) and standard practice, the planning conversation that produced this PRD should be captured in the v2 database after PRD approval. The session and decision records are written through the REST API or MCP server as part of the v2-ui-A prompt's setup steps.

Records to write:

- **SES-004** — UI v0.1 planning session. Status: Complete. Topics covered: standalone-vs-embedded, transport choice, scope, layout, refresh, server lifecycle, styling. Artifacts produced: this PRD (forthcoming implementation plan and prompt series).
- **DEC-018** — UI is a standalone application, not embedded in the v1 PySide6 app.
- **DEC-019** — UI consumes the REST API over HTTP, not the access layer directly.
- **DEC-020** — v0.1 scope: read-only across all entities, full CRUD for decisions only.
- **DEC-021** — Sidebar navigation with master/detail panes.
- **DEC-022** — File-watch on `db-export/` for live refresh, manual Refresh button as fallback.
- **DEC-023** — Detect-then-launch API subprocess management.
- **DEC-024** — Native Qt look for v0.1; styling pass deferred.
- **References** — `decided_in` from SES-004 to each of DEC-018 through DEC-024.

A status update reflecting that UI v0.1 is now in build is also appropriate at the same time.
