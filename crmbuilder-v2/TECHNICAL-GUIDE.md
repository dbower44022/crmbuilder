# CRMBuilder v2 — Technical Guide

Architecture, extension patterns, and engineering conventions for
contributors to the v2 stack. Operator-facing docs live in
`USER-GUIDE.md`; the operations reference (env vars, REST surface,
troubleshooting) is in the project `README.md`. The authoritative
specs are under `PRDs/product/crmbuilder-v2/`.

---

## Stack overview

```
┌────────────────────────────────────────────────────────────┐
│  PySide6 desktop UI                                        │
│  crmbuilder_v2.ui — windows, panels, dialogs, widgets      │
└───────┬────────────────────────────────────┬───────────────┘
        │                                    │
        │  HTTP via httpx                    │  HTTP via httpx
        │  (synchronous, off-UI-thread)      │  (asynchronous)
        ▼                                    ▼
┌────────────────────────┐    ┌──────────────────────────────┐
│  REST API              │◄───┤  MCP server                  │
│  crmbuilder_v2.api     │    │  crmbuilder_v2.mcp_server    │
│  FastAPI + Pydantic v2 │    │  ~40 thin tool wrappers      │
└──────────┬─────────────┘    └──────────────────────────────┘
           │ Python function calls
           ▼
┌──────────────────────────────────────────────────────────┐
│  Access layer                                            │
│  crmbuilder_v2.access — repositories, change_log,        │
│  exporter, validation, transactions                      │
└──────────┬───────────────────────────────────────────────┘
           │ SQLAlchemy 2.0
           ▼
┌──────────────────────────────────────────────────────────┐
│  SQLite — crmbuilder-v2/data/v2.db                       │
└──────────┬───────────────────────────────────────────────┘
           │ JSON export hook fires on every successful write
           ▼
┌──────────────────────────────────────────────────────────┐
│  PRDs/product/crmbuilder-v2/db-export/*.json (git)       │
└──────────────────────────────────────────────────────────┘
```

The four layers are deliberately separate: the access layer is
reusable from scripts and tests without HTTP; the REST API is the
durable productization-path interface (DEC-005); the MCP server is a
swappable thin adapter; the UI is one of three peers, not the entry
point.

### Layer responsibilities

| Layer | Module | Owns |
|---|---|---|
| Database | (file on disk) | ACID transactions, FK constraints |
| Access layer | `crmbuilder_v2.access` | SQLAlchemy queries, validation, change_log emission, JSON export hook, controlled vocabulary |
| REST API | `crmbuilder_v2.api` | HTTP envelope, Pydantic request schemas, exception → status mapping |
| MCP server | `crmbuilder_v2.mcp_server` | Tool definitions, REST proxying |
| UI | `crmbuilder_v2.ui` | Windows, panels, dialogs, file-watch refresh, threading |

**Conduct framework (out-of-process).** v2 stores methodology artifacts produced by stakeholder-facing interviews. The conduct of those interviews is governed by `PRDs/process/conduct/` in the parent crmbuilder repo — `charter.md`, `kickoff.md`, and `question-library.md`. These files are methodology-agnostic and operate upstream of v2's storage; v2 does not enforce or implement conduct rules. See USER-GUIDE.md "Conduct framework for stakeholder-facing interviews" for the operational view.

---

## Access layer

The only code that touches SQLAlchemy directly. Eight repository
modules under `crmbuilder_v2/access/repositories/` (one per entity
type) follow a uniform pattern:

```python
def get(session, identifier) -> dict
def list_all(session, **kwargs) -> list[dict]
def create(session, *, identifier, ...) -> dict
def update(session, identifier, **fields) -> dict       # not on append-only types
def delete(session, identifier) -> dict
def upsert(session, *, identifier, **fields) -> dict   # for bootstrap idempotency
```

Each mutating function emits a row to `change_log` via
`access.change_log.emit(...)` capturing before/after diff and the
current actor (default `claude_session`).

### Conventions

- **Identifiers as the public PK.** Internal `id` is an
  autoincrement integer; everything API/UI-facing addresses by
  `identifier` (DEC-NNN, RSK-NNN, etc.).
- **`_resolve_<entity>_id` helpers** translate identifier strings to
  integer FKs. Both `None` and the empty string return `None`. The
  caller's `if value is not None` guard distinguishes
  "don't touch" (None) from "clear the FK" (empty string). Pattern
  established for `supersedes` in v0.1 slice H; extended to topics'
  `parent_topic` in v0.2 slice F.
- **Soft-delete only for decisions** (DEC-013): `delete()` flips
  `status` to `Deleted` and leaves the row. All other entity types
  hard-delete.
- **Controlled vocabularies** in `access/vocab.py` are CHECK-constrained
  in the schema and validated in `require_in()`. New values require an
  Alembic migration.

### Sessions, exporter, change_log

`access.db.session_scope()` is the standard transactional context:

```python
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import decisions

with session_scope() as s:
    decisions.create(s, identifier="DEC-032", ...)
    # commit + JSON export run automatically on context exit
```

On commit, the exporter (`access/exporter.py`) atomically rewrites
all eight entity-type snapshot files plus `change_log.json`. Pass
`session_scope(export=False)` to skip the export — used in tests and
in the bootstrap migration.

The `actor` field on every change_log row comes from a
`contextvars.ContextVar`. Override with `change_log.set_actor("manual")`
around scripts; remember to reset it.

### Exceptions

```
AccessLayerError
├── ValidationError(field_errors=[FieldError(...)], message=...)
├── NotFoundError(entity_type, identifier)
└── ConflictError(message)
```

The REST API maps these to HTTP status codes in `api/errors.py`:

| Exception | Status |
|---|---|
| `ValidationError` | 400 |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| (FastAPI request shape) | 422 |
| Anything else | 500 |

---

## REST API

`api/main.py` builds a FastAPI app with a router per entity type
plus `health` and `orientation`. Every successful response is wrapped
in the envelope:

```json
{ "data": <payload>, "meta": {}, "errors": null }
```

`api/envelope.py` provides `ok(data)` and `err(errors)`. Routers
should never construct envelopes directly.

### Adding a new endpoint

Concrete pattern from `api/routers/decisions.py`:

```python
from fastapi import APIRouter
from crmbuilder_v2.access.repositories import decisions
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import DecisionCreateIn, DecisionUpdateIn

router = APIRouter(prefix="/decisions", tags=["decisions"])

@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(decisions.list_all(s, include_deleted=include_deleted))

@router.post("", status_code=201)
def create(body: DecisionCreateIn):
    with writable_session() as s:
        return ok(decisions.create(s, **body.model_dump()))
```

Pydantic input schemas in `api/schemas.py` use `extra="forbid"` so
unknown fields produce a 422.

### Error mapping

`writable_session()` and `readonly_session()` are FastAPI
dependencies that wrap `access.db.session_scope()` and translate
access-layer exceptions into HTTPException with the envelope shape.
You don't need to catch exceptions in routers; let them propagate.

---

## Deploy runs and the deploy worker

`crmbuilder_v2/deploy/` (PI-419, REQ-522) is the service-side provisioning
path — the first background job in v2.

* **Data.** `deploy_runs` (`DEP-NNN`; `access/repositories/deploy_runs.py`)
  is a non-governed operational table like `publish_runs`, but with a
  non-terminal lifecycle: `queued → running → succeeded |
  succeeded_with_issues | failed | cancelled`. `deploy_run_state` is the
  resume checkpoint (droplet id/IP, DNS record, SSH key, per-phase status,
  verification, cancel flag); `deploy_run_log` a capped, pre-masked list of
  `[ts, level, message]`. `provider_credentials` holds one opaque secret ref
  per provider per engagement. Both alembic heads carry the delta
  (`0123` / pg `0080`).
* **Claim.** `claim_next_run` is a single conditional `UPDATE` keyed on the
  row id *and* "queued, or running with a heartbeat older than
  `deploy_worker_stale_seconds`", so two workers cannot hold one run. The
  worker claims with engagement enforcement off and no active engagement,
  then executes inside `active_engagement(run.engagement_id)`.
* **Runner.** `deploy/runner.py::run_deploy` walks
  `DEPLOY_RUN_PHASE_ORDER`, checkpointing after each phase; completed phases
  are skipped on resume, `create_droplet` also recovers a server by the run's
  tag. The SSH phases are the unchanged v1 functions in
  `automation/core/deployment/ssh_deploy.py`; the run's generated ed25519 key
  (`deploy/keys.py`) is materialised to a 0600 temp file only for the length
  of an SSH session because `connect_ssh` takes a path. Everything external
  is injected through `RunnerDeps` — the tests fake providers, SSH, secrets
  and the clock (`tests/crmbuilder_v2/deploy/test_runner.py`).
* **Worker.** `deploy/worker.py::DeployWorker` is one class in two homes: a
  daemon thread started by the API lifespan when
  `CRMBUILDER_V2_DEPLOY_WORKER_INPROCESS` is true (the default), or the
  standalone `crmbuilder-v2-deploy-worker` console script (set the flag false
  on the API then). A heartbeat thread keeps the claim fresh through long,
  quiet SSH phases. Under test the flag is forced off by `conftest.py`;
  worker tests drive `run_once()`.
* **API.** `/provider-credentials` and `/deploy-runs` are admin-gated
  (`require_permission("admin")`). Secret plaintext crosses only in request
  bodies through `api/secret_boundary.py` (shared with the instances router);
  responses never carry refs. `GET /deploy-runs/{id}?log_after=N` is the
  polling contract the progress dialog uses.
* **Boundary.** Provisioning a *customer* server is product behaviour; the
  CRMBuilder production host is refused by `deploy/spec.py::is_protected_host`
  at request time and again in the runner (GVR-240 / DEC-946). Nothing is ever
  destroyed on failure (DEC-945) — the history panel flags what still exists.
* **Providers.** `deploy/providers/` are thin `requests` wrappers (no SDKs:
  the production venv cannot install packages). Cloudflare records are always
  `proxied: false` (GVR-182).

## Publish gates and the design-version stamp

The publish path (`crmbuilder_v2/publish/service.py`, PI-411 —
REQ-495/496/497; DEC-973/974/980/981/982) runs three gates around the
existing generate → validate → backup → deploy → verify flow:

* **Plan identity (REQ-496).** `plan_fingerprint_for` computes a SHA-256
  identity (`access/apply_plan.fingerprint_plan`) over the scoped program
  contents with the volatile provenance header stripped, the target
  instance identifier, and the declared per-instance setting values —
  everything that determines what gets written, and where. Every run
  (validate/preview included) reports it; a real publish carrying
  `expected_plan_fingerprint` re-derives and refuses, writing nothing,
  when they differ. Refused runs record no `publish_runs` row.
* **Additive-only automatic applies (REQ-497 / DEC-982).** A real publish
  *without* an approved fingerprint is an automatic apply:
  `access/apply_plan.screen_automatic` classifies each change and a
  removal, narrowing, or type change refuses the whole run, naming each
  declined change. The reviewed path is preview → approve → resubmit with
  the fingerprint. No mode flag can defeat the refusal.
* **Design-version stamp (REQ-495).** A publish may name the frozen
  release it runs under (`release`; existence + freeze validated before
  anything touches the target, DEC-980). If — and only if — the run's
  terminal status is `succeeded`, the stamp is upserted into the
  instance's single `CNetworkStandard` record: `standardVersion` (the
  release identifier) and `planFingerprint` in the same write, with
  `appliedAt`/`appliedBy`/`appliedByTool` (DEC-981). Partial applies,
  `succeeded_with_issues`, refusals and aborts leave the previous stamp
  untouched. The record is readable by the instance's ordinary API role
  (verified live, DEC-973) and writable only by the applier's admin
  credential. `publish_runs.publish_run_plan_fingerprint` carries the
  identity; the run summary carries the release and stamp outcome.
* **Stored feature selection (REQ-546 / PI-444).** `instances.
  instance_feature_selection` is a JSON list of design-entity identifiers
  (`ENT-NNN`; NULL = full design — identifiers, not filenames, so an entity
  rename cannot detach the selection; migrations 0129/SQLite + 0086/PG).
  `_run_publish` resolves it via
  `access/reconcile_apply.feature_selection_scope` (identifier → generated
  program filename) when no per-run scope is supplied; an explicit scope
  wins for that run only. A selection resolving to nothing refuses the run
  (`selection_matches_nothing`) instead of widening to a full publish.
  Validate-only stays full-design — it is the dialog's discovery surface —
  but reports the resolution so the publish dialog pre-checks its scope
  list. `publish_runs` summaries carry `scope_source`
  (`stored_selection`/`explicit_scope`/`full_design`) and the applied
  selection; `FeatureSelectionDialog` (instances panel) edits it via PATCH.
* **The security program and the access-change gate (REQ-519 / REQ-521,
  PI-417, DEC-998).** Roles and teams belong to no entity, so the
  generated model may carry one entity-less program, `security.yaml`
  (`EntityProgram.is_security`), holding the deployable schema's
  top-level `roles:` and `teams:` blocks; only confirmed records emit and
  the rest defer by name. Filtered tabs are entity-bound and emit as
  their entity's `filteredTabs:` block, with `scope` derived from the
  label and the filter compiled from the neutral condition (a filter the
  audit stored in EspoCRM report-filter form defers — no neutral reader
  yet). `reconcile_compare.SECURITY_PROGRAM_MEMBERS` (role, team) routes
  to `security.yaml` in `publish_scope_for_member`;
  `PUBLISHABLE_GLOBAL_MEMBERS` (role, team, filtered_tab) opens the
  publish direction on attribute rows; a filtered tab's presence row stays
  view-only like a field's. `POST /reconcile/publish` for a role or team
  (`reconcile_access.ACCESS_MEMBER_TYPES`) refuses with 409 unless
  `confirm_access_change` is set, and refuses again unless
  `confirm_access_removal` is set when `assess_access_publish` finds any
  level the instance currently grants being lowered (`GET
  /reconcile/assess-access-publish` reports target, changes and removals
  first). The gate sits before target resolution, so a refusal never
  reaches the instance.
* **Generation parity (LSN-071).** `generate_design_yaml` — the
  generation a publish actually runs — must read every `list_*` reader on
  the `DesignClient` protocol that `EspoCrmAdapter.run` reads;
  `tests/crmbuilder_v2/publish/test_service.py::
  test_generate_design_yaml_reads_the_same_lists_as_the_adapter_run` pins
  the set by name. A new emitted block needs a test that starts at this
  function and asserts the block appears in the artifact.
* **The `layout:` block and the writable split (REQ-519 / REQ-520, PI-427 /
  PI-418).** `adapters/espocrm/layouts.py` owns the neutral→EspoCRM layout
  type maps (`LAYOUT_TYPE_TO_ESPO`, the eighteen the engine writes;
  `AUDITED_LAYOUT_TYPE_TO_ESPO` adds the five portal variants the audit
  reads) and `render_layout`, a port of the V1 audit's reverse mappers —
  ported, not imported, because nothing under `crmbuilder_v2` may import
  the V1 audit (REQ-549); `tests/crmbuilder_v2/adapters/
  test_layout_program.py` checks the port against the V1 original on every
  fixture. `model._apply_layouts` renders each confirmed layout of an
  emitted entity under that entity's `layout:` key, resolving every placed
  field against the program (emitted field names, link names from the
  relationships blocks, the platform's own fields per base type; on a
  platform entity the CRM's `c`-prefixed custom fields reverse to their
  emitted names) and deferring by name otherwise; a panel layout that
  leaves `name` out sets `settings.autoPlaceName: false`. In the access
  layer `vocab.WRITABLE_LAYOUT_TYPES` / `PORTAL_LAYOUT_TYPES` split the
  type; `reconcile_compare.capability_reason` is the per-construct table
  behind the row field `capability_reason` (DEC-1033), consulted by
  `_attribute_capabilities`, by `reconcile_apply.capture_member_attribute`
  (layout joins `_GLOBAL_MEMBER_REPOS`; a portal variant is refused with
  the reason) and by `conformance._writable` (an ordinary layout's drift is
  `drifted`, a portal variant's `named_but_unwritable`). Migrations 0137
  (SQLite) / 0094 (PG) widen `ck_layout_type`; LSN-075 records why they
  were renumbered at merge.

## MCP server

`mcp_server/server.py` boots an `mcp.server.fastmcp.FastMCP` instance
and registers tools from `mcp_server/tools.py`. Each tool is a thin
wrapper around an `httpx.AsyncClient` call to the REST API:

```python
@mcp.tool()
async def get_decision(identifier: str) -> dict:
    """Return a single decision by identifier."""
    async with httpx.AsyncClient(base_url=settings.api_base_url) as c:
        r = await c.get(f"/decisions/{identifier}")
        r.raise_for_status()
        return r.json()["data"]
```

There is no business logic in the MCP layer. Adding a new tool is
boilerplate: define the function, document it (the docstring becomes
the tool description Claude sees), call the REST endpoint, return the
data payload.

The MCP server requires the REST API to be running. Wire it in Claude
Desktop / Claude Code via the config block shown in the README.

---

## UI

`crmbuilder_v2.ui` is a PySide6 desktop application. Hierarchy:

```
ui/
├── app.py                 # QApplication boot; main_window construction
├── main_window.py         # Top-level QMainWindow; phase tabs (REQ-526 / PI-432)
├── navigation.py          # Phase list (PRD §4), phase→steps map, identifier prefixes
├── panel_registry.py      # The one label→panel table; ALL_PANEL_LABELS; build_panel
├── phase_page.py          # One phase tab: phase-scoped sidebar + lazy panel stack
├── quick_open.py          # Ctrl+K finder (panels by name, records by identifier prefix)
├── sidebar.py             # Grouped sidebar with numbered step gutter + markers
├── server_lifecycle.py    # Detect-then-launch storage API subprocess
├── client.py              # StorageClient — typed httpx wrapper
├── exceptions.py          # Typed exception hierarchy
├── workers.py             # QThread Worker + run_in_thread helper
├── refresh.py             # File-watch refresh service (QFileSystemWatcher)
├── crash_banner.py        # Connection-lost banner widget
├── splash.py              # Startup splash
├── about_dialog.py        # Help → About
├── styling.py             # Stylesheet stub (DEC-024 — full pass deferred)
├── base/                  # Reusable bases
│   ├── list_detail_panel.py
│   ├── crud_dialog.py
│   ├── versioned_replace_dialog.py
│   └── versioned_panel.py
├── widgets/               # Cross-panel widgets
│   ├── date_field.py
│   ├── references_section.py
│   └── hierarchical_picker.py
├── panels/                # One per entity type
│   ├── decisions.py
│   ├── sessions.py
│   ├── risks.py
│   ├── planning_items.py
│   ├── topics.py
│   ├── references.py
│   ├── charter.py
│   └── status.py
└── dialogs/               # Per-entity create/edit/delete + shared error
    ├── decision_create.py
    ├── decision_edit.py
    ├── decision_delete.py
    ├── _decision_schema.py        # field schema shared by create/edit
    ├── (same trio + schema for risks, planning_items, topics)
    ├── charter_replace.py
    ├── status_replace.py
    └── error.py
```

### Threading model

**The UI thread never blocks.** Every HTTP call goes through a
`Worker` (QThread subclass in `workers.py`):

```python
worker = run_in_thread(
    self.fetch_records,                # runs on the worker thread
    on_success=self._on_fetch_success, # runs on the UI thread
    on_error=self._on_fetch_error,     # runs on the UI thread
    parent=self,
)
self._in_flight_workers.append(worker)
worker.finished.connect(self._on_worker_finished)
```

Critical: **the caller must keep a reference to the worker** until
`finished` fires; otherwise GC can destroy it before the slots run.
`ListDetailPanel._in_flight_workers` is the canonical pattern.

#### Stale-result rejection

When `refresh()` is called twice in quick succession, the older
worker's result must not overwrite the newer's. Solved with
**tokens**:

```python
self._refresh_counter += 1
token = self._refresh_counter
worker = run_in_thread(...)
self._refresh_tokens[id(worker)] = token

def _on_fetch_success(self, result):
    if not self._sender_is_current_refresh():
        return  # stale; ignore.
```

`_sender_is_current_refresh()` checks the current QObject `sender()`
against the token map. Only the most recent token's worker is
allowed to update state. Same pattern for the detail-pane extras
fetch.

### `StorageClient` (`ui/client.py`)

Synchronous wrapper around `httpx.Client`. Returns the `data`
payload from the envelope on 2xx; maps non-2xx via
`exceptions.from_response()` to the typed exception hierarchy:

```
StorageClientError
├── StorageConnectionError      # network-level failure
├── ServerError                 # 5xx and unexpected statuses
├── RequestShapeError           # 422 (FastAPI shape error — programmer bug)
├── NotFoundError               # 404
├── ConflictError               # 409
└── ValidationError             # 400 (carries field_errors())
```

Tests construct a `StorageClient` over `httpx.MockTransport` — no
network. See `tests/crmbuilder_v2/ui/test_client.py` for the full
matrix.

### Server lifecycle (`server_lifecycle.py`)

Detect-then-launch (DEC-023):

1. On startup, probe `GET /health` against the configured base URL.
2. If 2xx → existing API; the UI uses it.
3. If unreachable → spawn `crmbuilder-v2-api` as a subprocess; poll
   health until ready (timeout 10s); on success continue.
4. On window close, if we spawned the subprocess, send SIGTERM and
   wait briefly.

The lifecycle owns the subprocess; the rest of the UI uses the API
through `StorageClient` without knowing whether it's external or
spawned.

### File-watch refresh (`refresh.py`)

`RefreshService` wraps `QFileSystemWatcher` over the snapshot
directory. On any file modification within the export dir, it:

1. Reads the file, hashes its contents.
2. If the hash is unchanged from the last seen value → no signal
   (suppresses no-op rewrites the exporter performs on every commit).
3. If the hash differs → emit `data_changed(entity_type)` after a
   short debounce window (multi-write bursts coalesce to one signal).

`MainWindow` connects `data_changed` to the active panel's
`refresh()`; non-active panels mark themselves stale and refresh on
next selection. Manual Refresh buttons on each toolbar are the
fallback when the watcher misses a notification (filesystem
boundaries, NFS, etc.).

---

## UI base classes

### `ListDetailPanel`

Master/detail panel base. Subclasses implement four hooks:

```python
def entity_title() -> str
def fetch_records() -> list[dict]               # called on worker thread
def list_columns() -> list[ColumnSpec]
def render_detail(record: dict, extras: dict) -> QWidget
```

Optional hooks:

```python
def fetch_detail_extras(record: dict) -> dict   # for inbound references etc.
def _filter_strip_widget() -> QWidget | None    # filter dropdowns above the table
def _post_process_records(records) -> list[dict] # synthetic columns
def _strikethrough_for_record(record) -> bool   # row formatting (slice F)
def _select_by_identifier(identifier: str) -> bool  # custom selection (slice F)
```

Signals:

```python
connection_lost = Signal(str)        # promoted by main window to crash banner
navigate_requested = Signal(str, str) # cross-panel link click; (entity_type, id)
```

The default master pane is a `QTableView` over `_RecordTableModel`.
**Topics** overrides `_build_ui` to install a `QTreeView` instead;
this override-and-alias pattern is fragile and the v0.3 backlog
includes a proper master-pane factory refactor.

### `EntityCrudDialog`

Shared dialog base for the four full-CRUD entity types (Decisions,
Risks, Planning Items, Topics). Subclasses provide:

- A field schema (a tuple of field-spec dataclasses) describing the
  fields to render — text, multiline text, enum picker, hierarchical
  picker, date picker.
- A "create" or "edit" mode flag.
- A submit callback that translates the form data into a REST call.

The base handles:

- Field rendering driven by the schema.
- Client-side format validation (regex per field).
- Threaded submit via `run_in_thread`.
- Inline error rendering: API-side `ValidationError` field errors
  are placed under the offending field labels.
- `StorageConnectionError` rejects the dialog so the main window can
  surface the crash banner.

`EntityCrudDeleteDialog` is the trivial confirm-and-delete sibling.

### `VersionedReplaceDialog`

Used for Charter and Status. Layout: header label, monospace JSON
editor pre-populated with the current payload, Validate button, status
label, Save / Cancel.

- **Validate** parses the editor text as JSON and confirms it's a
  top-level object. Status label flips green ("Valid JSON") or red
  ("Invalid JSON: ...").
- Editing the text after validation invalidates the prior validation
  and disables Save until re-validated.
- **Save** re-validates, then calls the save callback through a
  worker. On success → `accept()`. On `ValidationError` with
  `field_errors`, errors render inline below the editor (slice F
  polish item 10). On other failures, fall back to `ErrorDialog`.

### Widgets

#### `DateField`

A composite widget pairing a `QLineEdit` with a calendar popup. Round-
trips the project's `MM-DD-YY` text format. Validates on blur and on
submit. Used by the Decisions and Sessions create/edit dialogs.

#### `ReferencesSection`

Pure rendering widget: takes a pre-fetched references payload (the
shape returned by `StorageClient.list_references_touching`) and
renders Inbound / Outbound sections grouped by relationship type.
Reference fetching happens at the panel level via
`fetch_detail_extras` so this widget is just layout.

Constructor accepts `exclude_relationships` to suppress relationships
already shown elsewhere on the detail pane (e.g., DecisionsPanel
suppresses outbound `supersedes` because Supersedes / Superseded By
are top-level fields).

Emits `navigate_requested(entity_type, identifier)` on link click.

#### `HierarchicalEntityPicker`

A reusable tree picker. Constructed with a flat record list plus a
`parent_field` key; builds an in-memory tree, displays it as a
`QTreeView`, and emits the selected identifier on confirm. Supports a
`current_id` for scroll-to-current and an `exclude_descendants_of` set
for cycle prevention. Used by the Topics create/edit dialogs;
designed so future hierarchical entity types can drop it in without
modification.

---

## Adding a new entity type

The eight-step pattern (also documented in the README's Development
section):

1. **Model** — add a SQLAlchemy class to `access/models.py` with
   CHECK constraints, indexes, FKs.
2. **Repository** — add a module under `access/repositories/` with
   `get`, `list_all`, `create`, `update`, `delete`, `upsert`.
3. **Vocabulary** — if the entity introduces new controlled values,
   add them to `access/vocab.py`.
4. **Exporter** — append `(filename, model)` to `_EXPORT_TABLES` in
   `access/exporter.py`.
5. **API router** — under `api/routers/`, plus Pydantic schemas in
   `api/schemas.py`. Register the router in `api/main.py`.
6. **MCP tools** — add wrappers in `mcp_server/tools.py`.
7. **UI** — panel under `ui/panels/`, dialogs under `ui/dialogs/`,
   one entry in `PANEL_REGISTRY` (`ui/panel_registry.py`) — that puts it
   in the alphabetical All-panels index of every phase tab — plus its
   `entity_type` in `ENTITY_TYPE_TO_SIDEBAR_LABEL` (`ui/main_window.py`)
   and, if quick open should find it by identifier, its prefix in
   `IDENTIFIER_PREFIX_TO_ENTITY_TYPE` (`ui/navigation.py`). Add it to a
   phase's step list in `DEFAULT_PHASE_STEPS` only if the PRD says that
   phase produces it.
8. **Migration** — `alembic revision --autogenerate -m "add <entity>"`,
   review, rename to `00NN_<topic>.py`, `alembic upgrade head`.

**Tests** parallel each layer:
`tests/crmbuilder_v2/access/test_<entity>.py`,
`tests/crmbuilder_v2/api/test_<entity>.py`,
`tests/crmbuilder_v2/mcp_server/test_smoke.py` (extend),
`tests/crmbuilder_v2/ui/test_<entity>_panel.py`,
`tests/crmbuilder_v2/ui/test_<entity>_dialogs.py`.

---

## Schema migrations

Alembic environment lives at `crmbuilder-v2/migrations/`. Always run
from the repo root with `-c crmbuilder-v2/alembic.ini`:

```bash
uv run alembic -c crmbuilder-v2/alembic.ini revision --autogenerate \
  -m "add personas table"
# review crmbuilder-v2/migrations/versions/<id>_add_personas_table.py
# rename to 0002_add_personas.py for stable ordering
uv run alembic -c crmbuilder-v2/alembic.ini upgrade head
```

Conventions:

- The Alembic env reads the DB URL from
  `config.get_settings()`, not `alembic.ini`. Set
  `CRMBUILDER_V2_DB_PATH` to migrate against an alternate DB.
- `render_as_batch=True` is enabled so SQLite-style ALTER works.
- Don't edit the baseline (`0001_initial_schema.py`); add a new
  migration instead.
- The autogenerate diff is approximate. Review it. Renames look like
  drop+create unless you provide a hint.

---

## Testing

Test layout mirrors source layout:

```
tests/crmbuilder_v2/
├── conftest.py                 # tmp DB / tmp export dir per test
├── access/                     # access-layer tests (use session_scope directly)
├── api/                        # FastAPI TestClient tests
├── mcp_server/                 # smoke tests for tool registration
├── ui/                         # pytest-qt tests
│   └── conftest.py             # offscreen Qt; build_client fixture; client_stub
└── bootstrap/                  # tests for legacy markdown bootstrap parsers
```

### Fixtures

- `v2_env` — provisions a fresh SQLite DB and JSON-export directory
  per test. The DB is the temporary file; the export dir is a
  temporary directory. Both are torn down at test exit.
- `client` (api) — FastAPI `TestClient`.
- `qapp` / `qtbot` (ui) — pytest-qt's standard fixtures.
- `client_stub` (ui) — `StorageClient` over `httpx.MockTransport`
  with empty-list defaults for all entity GETs.
- `build_client(handler)` (ui) — factory that constructs a
  `StorageClient` over a custom mock handler.
- `lifecycle_stub` (ui) — `ServerLifecycle` aimed at a dead URL for
  type-compatibility in tests that don't exercise lifecycle behavior.

### Patterns

- **Access tests** open `session_scope()` directly and assert against
  the resulting rows. They don't go through HTTP.
- **API tests** use FastAPI `TestClient`; the access layer is real,
  the database is a temp file.
- **UI tests** use `httpx.MockTransport` to fake responses. Panel
  tests instantiate the panel against the mock client and assert on
  rendered widgets via `qtbot.findChild`/`waitUntil`.
- **Worker tests** wait on `qtbot.waitUntil(lambda: state == expected)`
  rather than sleeping. Avoid `qtbot.wait(N)` when possible.
- **Stale-result tests** call `refresh()` twice with different
  responses and assert that only the second response is reflected.

### Running

```bash
uv run pytest tests/crmbuilder_v2/                    # all (~458 tests)
uv run pytest tests/crmbuilder_v2/access/             # one layer
uv run pytest tests/crmbuilder_v2/ui/test_show_deleted_toggle.py -v
uv run pytest tests/crmbuilder_v2/ --cov=crmbuilder_v2  # with coverage
```

The UI tests force the offscreen Qt platform plugin in
`tests/crmbuilder_v2/ui/conftest.py`, so there's no display
requirement.

---

## Conventions

### Logging

Module-level logger named after the dotted module path:

```python
import logging
_log = logging.getLogger("crmbuilder_v2.ui.panels.decisions")
```

UI logs land at `~/.crmbuilder-v2/ui.log` (configured in
`ui/app.py`). API logs go to stdout. Tests use the standard pytest
log capture; never write to the real log file from a test.

### Exceptions

- Don't introduce new exception types in routers — let access-layer
  exceptions propagate.
- In the UI, never `except Exception:` — catch the specific typed
  exception classes from `ui.exceptions`.
- `StorageConnectionError` is reserved for network-level failures.
  Don't manufacture it from anything else; the crash banner relies
  on it.

### Vocabulary changes

Adding a new value to a controlled vocabulary requires:

1. Add the value to the constant in `access/vocab.py`.
2. Generate an Alembic migration that drops and recreates the CHECK
   constraint with the expanded set.
3. Update the operator-facing docs (this guide, USER-GUIDE,
   `tools.py` MCP descriptions).
4. Apply the migration.

The deliberate gate is the point per DEC-006 — the vocabulary should
grow consciously.

### Reference relationship vocabulary

`access/vocab.py:REFERENCE_RELATIONSHIPS` lists the seven values:
`is_about`, `supersedes`, `decided_in`, `affects`, `covers`,
`blocks`, `references`, plus the typed kinds added since. `withdraws`
(REQ-560 / DEC-1034, PI-462) is decision → withdrawn governed record; its
pair rule is enforced in `references.create` as well as the dialogs. Same
change procedure as any other controlled vocabulary.

### Code style

- Python 3.12+, `from __future__ import annotations` everywhere.
- `ruff check` and `ruff format` configured in `pyproject.toml`.
- Type hints on public functions and methods.
- reStructuredText docstrings on modules and classes; brief one-line
  docstrings on private helpers.

### Git conventions

- Subject prefixed with `v2:` for any v2 work.
- Subject under 70 characters; details in the body.
- Co-Authored-By trailer for Claude Code work:
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- Slice work for the UI lands as one commit per logical change
  (storage support + UI feature + tests typically bundle if they're
  inseparable; polish bundles separately; closeout always separately).

---

## Performance notes

The system is sized for single-user governance content: hundreds of
records per entity type, never millions. Some implications:

- **No pagination** on REST list endpoints. Frontend renders the
  full list and lets QTableView/QTreeView virtualize.
- **No indices beyond what SQLite auto-creates** for primary keys
  and FKs. Adding indices makes sense if benchmarks show a hot path;
  no benchmarks exist today.
- **Synchronous httpx in the UI** is fine because every call runs
  off-thread. Async would force PySide6 + asyncio interop which
  isn't worth the complexity for this scale.
- **Full re-export on every write** is fine because the largest
  entity tables have <100 rows; the export is a few hundred KB total.

If v2 gains a methodology entity schema (personas, fields, processes,
requirements) and that schema produces tens of thousands of rows,
some of these assumptions will need revisiting. Document benchmarks
before optimising.

---

## Security model

v2 runs locally as a single-user desktop application. There is no
authentication on the REST API; it binds to 127.0.0.1 by default and
should not be exposed externally without an authenticating reverse
proxy.

Secrets do not enter v2. The only credential surface is v1's EspoCRM
deployment configuration, which lives entirely in v1's storage
(per-client SQLite + OS keyring).

If v2 ever moves to a hosted model, the REST API is the natural
authentication boundary; FastAPI dependencies on `writable_session`
would gain a token check.

---

## Reference

- `crmbuilder-v2/README.md` — operations reference.
- `crmbuilder-v2/USER-GUIDE.md` — operator walkthrough.
- `PRDs/product/crmbuilder-v2/storage-system-PRD-v0.1.md` — storage
  system requirements.
- `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — UI requirements
  (current).
- `PRDs/product/crmbuilder-v2/db-export/decisions.json` — the live
  decisions log; particularly load-bearing decisions: DEC-005
  (storage stack), DEC-006 (universal references), DEC-011
  (orientation protocol), DEC-013 (sessions append-only), DEC-022
  (file-watch refresh), DEC-023 (detect-then-launch), DEC-024
  (styling deferred), DEC-025 (no transcript capture), DEC-027 (v0.2
  scope), DEC-028–031 (v0.2 architectural decisions).
