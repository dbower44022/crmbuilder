# Claude Code Prompt — Tab Restructure and Clients Tab for L2 PRD v1.16

## Purpose

L2 PRD v1.16 replaces the existing mode selector with three peer tabs
(Clients, Requirements, Deployment) and introduces a new Clients tab as
the application's entry point for managing client implementations. This
prompt implements the tab restructure, the full Clients tab, the
active-client context infrastructure that the other tabs will subscribe
to, and a placeholder Deployment tab.

This is **Prompt B** of a five-prompt sequence (A–E) implementing L2 PRD
v1.16 design items. Prompt A (schema migrations for Instance and
DeploymentRun) is already merged.

- Prompt A (merged): Schema migrations
- **Prompt B (this file): Tab restructure + Clients tab UI**
- Prompt C: Deployment tab internals + legacy JSON instance migration
- Prompt D: Deploy Wizard rewrite (three scenarios)
- Prompt E: Terminology sweeps (administrator → implementor,
  Dashboard → Requirements Dashboard)

## Authoritative Source

All behavior in this prompt is specified in
`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`
(v1.16). The specific sections are:

- **Section 14.1.1** — Tab Architecture (three peer tabs)
- **Section 14.1.3** — Active Client Context
- **Section 14.9** (Clients tab portions) — cross-tab workflow context
- **Section 14.11** — Clients Tab (full specification)
- **DEC-055** — Replace mode selector with three peer tabs
- **DEC-057** — Tab labels display active client name inline
- **DEC-059** — Persist last_active_tab and last_selected_client_id

Read those sections before writing code. The section text is
authoritative for field lists, empty-state copy, validation rules, and
rollback behavior — this prompt summarizes intent but does not
reproduce the spec verbatim.

## Scope — What This Prompt Does

### 1. Preferences module (new)

Create `automation/config/preferences.py` — a Qt-free wrapper around
persistent per-machine preferences storage. The module must be
unit-testable without importing PySide6. Use a plain JSON file at a
per-machine location (for example `~/.config/crmbuilder/preferences.json`
on Linux; use `platformdirs` or `os.path.expanduser` — no Qt dependency).

The module exposes at minimum:

- `get_last_active_tab() -> str | None` — returns `"clients"`,
  `"requirements"`, `"deployment"`, or None
- `set_last_active_tab(tab: str) -> None`
- `get_last_selected_client_id() -> int | None`
- `set_last_selected_client_id(client_id: int | None) -> None`

Unknown keys, corrupt JSON, or missing files must return None / be
recreated without raising. The module must be safe to import before
any Qt code runs.

Add tests at `tests/config/test_preferences.py` using a temp directory
to isolate from real user config.

### 2. Active-client context (new)

Create `automation/ui/active_client_context.py` — the single source of
truth for which client the Requirements and Deployment tabs are
operating against. The context:

- Holds the currently active `Client` row (or None)
- Owns the open SQLite connection to the active client's database,
  opening it on activation and closing the previous one on change
- Emits a Qt signal `active_client_changed(client_or_none)` whenever
  the active client changes (including to None)
- Provides a `set_active_client(client)` method that performs the open
  + signal emission + `Client.last_opened_at` update + preferences
  persistence in order, rolling back the connection change if the
  open fails
- Provides a `clear()` method to deactivate

Split the pure-logic state transitions from the Qt `QObject` shell so
the transitions are testable Qt-free. One acceptable pattern: a pure
`ActiveClientState` dataclass in `automation/core/active_client_state.py`
holding the non-Qt state and validation, and a thin `QObject` wrapper
in `automation/ui/active_client_context.py` that owns the signal and
delegates.

Reachability is a precondition for activation: if the reachability
check (see item 4 below) returns a red state, `set_active_client` must
raise or return a result indicating failure and must NOT change the
current active client or emit the signal. The caller (Clients tab) is
responsible for displaying the error.

Add tests at `tests/core/test_active_client_state.py` for the pure
state transitions. A small `tests/ui/test_active_client_context.py`
may exercise the signal emission using `pytestqt` if the existing
suite already uses it; otherwise skip the Qt-level test and rely on
the pure-state coverage.

### 3. Reachability check (new)

Create a pure-logic function (location: `automation/core/client_reachability.py`
or colocated with `active_client_state.py` — pick whichever fits the
existing module layout) that takes a `Client` row and returns a
result describing:

- `is_reachable: bool`
- `error: str | None` — human-readable explanation when not reachable

The check must verify:

- `project_folder` is not NULL and exists on disk as a directory
- `{project_folder}/.crmbuilder/{code}.db` exists as a file
- The database opens and a trivial `SELECT 1` succeeds

Return a result with a specific error message for each failure mode.
Close the probe connection before returning. Add unit tests covering
each failure mode using tmp directories and a real SQLite file.

### 4. Clients tab (new)

Create `automation/ui/clients_tab.py` implementing §14.11 in full.

Layout — master/detail:

- Left pane: sortable list of all clients from the master database
  with columns Name, Code, Project Folder, Last Opened. Default sort
  is `last_opened_at DESC NULLS LAST`. Column headers are clickable
  to change the sort.
- Left pane header: "+ New Client" button that swaps the detail pane
  to the Create Client form.
- Right pane: detail view of the currently selected row, or an empty
  placeholder when no row is selected.

Detail pane shows the fields listed in §14.11.2 with the editability
rules specified there (Name and Description inline editable; Code,
Project Folder, Database File, Created, Last Opened read-only; CRM
Platform and Deployment Model read-only and displayed only when the
client row's `crm_platform` / `deployment_model` columns are
populated). Inline edits to Name and Description save to the master
database and refresh the list row in place.

Below the metadata fields, display the reachability indicator (green
or red) with the specific error inline when red. A red client refuses
activation per §14.11.2 — clicking its row displays the error in the
detail pane but does NOT change the active client.

Create Client form (§14.11.3):

- Four fields: Name, Code, Description, Project Folder, with the
  validation rules from the spec. Validation errors render inline
  below the offending field.
- On Save: perform the five-step creation sequence from §14.11.3 in
  order. Each step's output must be tracked so rollback can undo only
  what was created by this operation. Rollback rules:
  - The master row is not inserted if any prior step fails
  - The `.crmbuilder/` directory is removed only if this operation
    created it
  - The database file is removed only if this operation created it
  - Each of the standard subfolders (`PRDs/`, `programs/`, `reports/`,
    `Implementation Docs/`) is removed only if this operation created
    it; pre-existing subfolders are never removed
- Implement the creation logic as a pure function in
  `automation/core/create_client.py` that takes a parameter object
  and a factory for running client migrations, returns a result
  object, and handles rollback internally. The Clients tab calls the
  pure function and renders the result. The pure function must be
  unit-testable with a tmp filesystem.
- On success, the new client becomes the active client (via the
  active-client context), the list refreshes, the new row is
  selected, and the detail pane returns to the standard detail view.

Empty state (§14.11.4): when the master database has zero Client
rows, the list pane shows the no-clients message and the detail pane
shows only a "+ New Client" button as the single action.

No delete action in v1 (§14.11.5). Do not add one.

Tests:

- `tests/core/test_create_client.py` — covers happy path plus every
  rollback branch (project folder missing, migration failure, master
  insert failure, pre-existing subfolders preserved across rollback,
  etc.) using tmp directories.
- `tests/ui/test_clients_tab_logic.py` — pure-logic tests for any
  list-sorting, validation, and state transitions that can be
  exercised without instantiating the Qt widget. Follow the Qt-free
  separation pattern already established in the existing automation
  UI tests.

### 5. Tab restructure in `main_window.py`

Replace the existing mode selector with a `QTabWidget` containing
three tabs: Clients, Requirements, Deployment.

- **Clients tab** — hosts `ClientsTab` from item 4. No active client
  is required to use this tab.
- **Requirements tab** — reparent the existing Requirements workspace
  wholesale. The existing sidebar, drill-down stack, and all screens
  remain exactly as they are today. The only change is (a) its parent
  is now the new Requirements tab widget instead of whatever the mode
  selector put it under, and (b) it consumes the new active-client
  context instead of whatever mechanism it uses today. Minimize the
  diff inside the Requirements workspace itself.
- **Deployment tab** — stub. Create
  `automation/ui/deployment_tab_stub.py` that renders a placeholder
  empty state. Copy: "The Deployment tab will be rebuilt in a
  forthcoming release. Deployment, configuration, and verification
  are temporarily unavailable from `main`." The legacy
  `instance_panel.py`, `program_panel.py`, `deploy_panel.py`, and
  `output_panel.py` files remain in the codebase untouched but are
  NOT wired into the new tab structure. They become unreachable from
  the UI until Prompt C replaces the stub.

Tab label updates (DEC-057): the Requirements and Deployment tabs
display the active client name inline via `QTabWidget.setTabText()`,
driven by the active-client context signal. Format:

- Active client present: `"Requirements — {client.name}"` and
  `"Deployment — {client.name}"`
- No active client: `"Requirements (no client selected)"` and
  `"Deployment (no client selected)"`

The Clients tab label is always `"Clients"`.

Tab-label state persistence (DEC-059): on startup, the main window
reads `last_active_tab` and `last_selected_client_id` from the
preferences module. If both are present, the active-client context
attempts to activate that client. If the client is missing or
unreachable, the main window falls back to opening the Clients tab
with no active client. If activation succeeds, the previously active
tab is restored. On every tab change or active-client change, the
main window writes the updated values to preferences.

Each tab preserves its internal navigation state independently when
the user switches tabs and back (this is the default `QTabWidget`
behavior — just don't destroy and recreate the tab contents on
switch). When the active client changes, the Requirements and
Deployment tabs reset their internal state per §14.1.1.

### 6. Context-driven empty states on Requirements tab

When no client is active, the Requirements tab content area shows an
empty-state message directing the implementor to the Clients tab, and
sidebar entries / content areas in the Requirements tab are inert
(but the tab itself remains clickable — buttons-never-disabled
pattern from §14.10.6). Implement this minimally: one wrapper widget
that either shows the empty state or the existing Requirements
workspace, switched via the active-client context signal. Do not
modify internal Requirements screens to handle the None case
individually.

The Deployment tab stub shows its placeholder regardless of active
client state — the whole tab is a stub in this prompt.

## Working Process — No Direct Source Edits

Per the project's working agreement, Claude Code (the agent running
this prompt) is the one allowed to modify application source files.
This prompt is the authoring step; Doug will run it via Claude Code.

All code changes in this prompt land on `main` via a single commit.
No behavioral changes to files outside the scopes listed above.
Specifically, do NOT touch:

- Any file under `espo_impl/` (legacy deployment code — Prompt C/D territory)
- `automation/db/` (Prompt A territory; schema is already in place)
- Any file under `data/instances/` (legacy JSON; Prompt C territory)
- Internal Requirements tab screens beyond the reparenting and
  active-client-context plumbing

## Out of Scope

- **Deployment tab internals.** The tab is a stub. No Instances,
  Deploy, Configure, Verify, or Output entries. Prompt C.
- **Deploy Wizard.** Prompt D.
- **Legacy JSON migration.** `data/instances/*.json` remains
  untouched. Prompt C reads it.
- **Terminology sweeps.** Do not rename `administrator` →
  `implementor` anywhere in this prompt. Do not rename "Dashboard" →
  "Requirements Dashboard". Prompt E.
- **Encryption of Instance credentials.** ISS-018, deferred.
- **Delete action on the Clients tab.** §14.11.5 — explicitly out of
  scope for v1.
- **Internal refactor of the Requirements workspace.** Reparent only.

## Completion Criteria

Before marking this prompt complete:

1. `automation/config/preferences.py` exists with the four functions
   listed and passing tests.
2. `automation/core/active_client_state.py` (pure) and
   `automation/ui/active_client_context.py` (Qt wrapper) exist with
   passing tests for the pure layer.
3. Reachability check module exists with passing tests covering each
   failure mode.
4. `automation/core/create_client.py` exists with passing tests
   covering happy path and every rollback branch.
5. `automation/ui/clients_tab.py` implements §14.11 in full: list
   with default sort, detail pane with inline edit on Name and
   Description, reachability indicator gating activation, Create
   Client form with inline validation and rollback, empty state, no
   delete action.
6. `automation/ui/deployment_tab_stub.py` renders the placeholder.
7. `main_window.py` uses a `QTabWidget` with three tabs, reparents
   the existing Requirements workspace into the Requirements tab,
   updates tab labels via the active-client context signal, and
   persists/restores `last_active_tab` and `last_selected_client_id`
   through the preferences module.
8. The existing `instance_panel.py`, `program_panel.py`,
   `deploy_panel.py`, and `output_panel.py` remain in the codebase
   unchanged and unreachable from the UI.
9. `uv run pytest tests/ -v` passes with zero failures.
10. `uv run ruff check automation/ tests/` passes clean.
11. Application launches, opens to the restored tab + client on
    startup (or Clients tab if no prior state), allows creating a
    new client with rollback on failure, and selecting a client
    updates the Requirements and Deployment tab labels.

## Commit

Commit with the message:

    L2 PRD v1.16 Prompt B: tab restructure + Clients tab

    - three peer tabs (Clients, Requirements, Deployment) replace mode selector (DEC-055)
    - ActiveClientContext owns client DB connection + change signal
    - preferences module persists last_active_tab + last_selected_client_id (DEC-059)
    - Clients tab: master/detail, Create Client form with rollback, reachability gate, no delete (§14.11)
    - Requirements workspace reparented into Requirements tab, no internal changes
    - Deployment tab is a placeholder stub; legacy panels unreachable until Prompt C
    - tab labels show active client name inline (DEC-057)

Push to `main` on the `dbower44022/crmbuilder` repo.
