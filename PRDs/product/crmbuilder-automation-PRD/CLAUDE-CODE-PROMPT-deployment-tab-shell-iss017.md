# Claude Code Prompt — Deployment Tab Shell and Legacy Instance Migration (ISS-017)

## Purpose

L2 PRD v1.16 fills in the Deployment tab as a five-entry sidebar panel
scoped to the active client, and it moves CRM instance profiles out of
the legacy `data/instances/*.json` files into a new per-client Instance
table (introduced by Prompt A). This prompt implements the Deployment
tab shell — all five sidebar entries, the active-instance picker, and
the phase status banner — and the one-time migration from legacy JSON
files into the per-client Instance tables (resolving ISS-017).

This is **Prompt C** of a five-prompt sequence (A–E) implementing
L2 PRD v1.16 design items.

- Prompt A (merged): Schema migrations for Instance and DeploymentRun
  (`CLAUDE-CODE-PROMPT-schema-instance-deploymentrun.md`)
- Prompt B (merged): Tab restructure + Clients tab UI
  (`CLAUDE-CODE-PROMPT-tab-restructure-clients-tab.md`)
- **Prompt C (this file): Deployment tab shell + legacy JSON migration**
- Prompt D: Deploy Wizard internals (three scenarios)
- Prompt E: Terminology sweeps (administrator → implementor,
  Dashboard → Requirements Dashboard)

Prompt B left the Deployment tab as a placeholder. This prompt replaces
that placeholder with the real sidebar layout and hooks up the existing
`espo_impl` logic behind thin wrappers. The Deploy Wizard itself is
stubbed — the "Start Deploy Wizard" button is wired up but launches a
not-yet-implemented dialog that Prompt D will replace.

## Authoritative Source

All behavior in this prompt is specified in
`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`
(v1.16). The specific sections are:

- **Section 14.12** — Deployment Tab (all subsections)
  - 14.12.1 Layout (five sidebar entries)
  - 14.12.2 Active-Instance Picker and Phase Status Banner
  - 14.12.3 Instances Entry
  - 14.12.4 Deploy Entry (history table + wizard launch button; wizard
    internals are Prompt D)
  - 14.12.6 Supported Deployment Targets
  - 14.12.7 Configure Entry
  - 14.12.8 Verify Entry
  - 14.12.9 Output Entry
  - 14.12.10 Empty States
  - 14.12.11 Schema Note
- **Section 14.9** — Cross-Tab Workflows
  - 14.9.1 Phase Handoff from Requirements to Deployment (Mark
    Complete behavior on the phase status banner)
  - 14.9.3 YAML File Handoff (the Configure entry reads from the same
    `{project_folder}/programs/` directory that the Document Generator
    writes to)
- **Section 16.17 / ISS-017** — Legacy JSON instance migration

**Explicitly out of scope for Prompt C (do not implement here):**

- **Section 14.12.5** (Deploy Wizard) and its subsections 14.12.5.1 /
  14.12.5.2 — these are Prompt D. The wizard launch button in the
  Deploy entry must be wired up but its click handler shows a
  "Not yet implemented — see Prompt D" message box.
- **ISS-018** (encrypted credential storage) — credentials remain
  plaintext in v1 per §14.12.3.
- Terminology sweeps (Prompt E).

Read the sections listed above before writing code. The section text
is authoritative for field lists, column lists, empty-state copy, and
scoping rules — this prompt summarizes intent but does not reproduce
the spec verbatim.

## Scope — What This Prompt Does

### 1. Deployment tab shell (replace Prompt B placeholder)

Replace the placeholder Deployment tab introduced by Prompt B with a
real sidebar-plus-content-area layout mirroring the Requirements tab
structure (§14.1.2 / §14.12.1). Put this under
`automation/ui/deployment/` alongside the Requirements tab code. Keep
the Qt-free pure-logic separation used throughout `automation/ui/`:
view-models and data access go in modules that do not import PySide6
and are unit-testable; PySide6 widgets live in sibling files that wrap
the pure-logic modules.

The sidebar has five entries per §14.12.1:

1. **Instances** (selected by default)
2. **Deploy**
3. **Configure**
4. **Verify**
5. **Output**

Each entry preserves its internal state independently when the
implementor switches between entries. The whole tab subscribes to the
active-client context infrastructure from Prompt B — when the active
client changes, every entry refreshes against the new client's
database, and when no client is active the entire tab shows the
no-active-client empty-state message and hides the picker and phase
status banner (§14.12.10).

### 2. Active-instance picker and phase status banner (§14.12.2)

Implement a persistent header above the content area containing:

- **Active-instance picker** — dropdown listing all instances
  belonging to the active client, each displayed as
  `"{name} ({environment})"`. Defaults to the client's default
  instance (row with `Instance.is_default = TRUE`) on first entry to
  the tab in a session. Selection persists for the application
  session and applies to all four instance-scoped entries (Deploy,
  Configure, Verify, Output). Displays a red status indicator next
  to any instance whose connectivity check is failing. Connectivity
  check is the existing check from `espo_impl` — do not reimplement.
- **Phase status banner** — shown only on Deploy, Configure, and
  Verify entries (Instances and Output do not display it per
  §14.12.2). Displays the corresponding Phase 10/11/12 work item
  (`crm_deployment`, `crm_configuration`, verification), its current
  status badge using the existing badge component from the
  Requirements tab, and a "Mark Complete" action. Clicking Mark
  Complete updates the work item's status through the existing
  workflow-engine API without requiring a tab switch (§14.9.1).

### 3. Instances entry (§14.12.3)

List-plus-detail pane for the active client's instance profiles.

- **List** — one row per instance with columns: name, code,
  environment, URL, default flag, connectivity status.
- **+ New Instance button** above the list — opens the instance
  creation form. The form captures name, code, environment, URL,
  username, password, description, and is_default. The code and
  environment fields are required and become read-only after
  creation.
- **Detail pane** below the list — shows the selected instance's
  full details with inline editing of name, description, URL,
  username, and password. Code and environment are read-only.
- **Default flag semantics** — exactly one instance per client may
  be marked as the default. Setting the default flag on a different
  instance clears it from the previous default in the same
  transaction.
- **Storage** — all reads and writes go through the per-client
  database's Instance table (created by Prompt A). No JSON file
  access anywhere in this entry. Credentials are stored as plaintext
  per §14.12.3 and ISS-018 deferral.

### 4. Deploy entry — history table + stub launch button (§14.12.4)

Implement the Deploy entry as specified in §14.12.4 **except** for the
wizard internals. Specifically:

- "Start Deploy Wizard" button at the top of the entry.
- Deployment history table below the button, listing each previous
  wizard run for any instance belonging to the active client, with
  columns: instance name, scenario, started_at, completed_at, outcome
  (success / failure), and a link to the Output entry filtered to
  that run's log.
- History is read from the DeploymentRun table in the per-client
  database (Prompt A schema).
- **Stub behavior**: clicking "Start Deploy Wizard" opens a modal
  dialog with the text "Deploy Wizard not yet implemented — see
  Prompt D." and a single OK button. Do not write any deployment
  logic. Do not create new DeploymentRun rows. The button must be
  wired up and reachable so that Prompt D can replace the click
  handler without touching the surrounding view.

### 5. Configure, Verify, and Output entries as thin wrappers (§14.12.7–§14.12.9)

These three entries wrap existing `espo_impl` behavior, scoped to the
active client's project folder and the active instance from the
picker. Do not rewrite or duplicate the underlying implementation.

- **Configure entry (§14.12.7)** — lists YAML files in
  `{project_folder}/programs/` with name, last modified timestamp,
  and most recent run outcome. Exposes the existing check-then-act
  configuration actions. The `{project_folder}` is resolved from the
  active client; the target instance is resolved from the picker
  (§14.9.3). If `{project_folder}/programs/` does not exist or is
  empty, show the empty-state copy from §14.12.10.
- **Verify entry (§14.12.8)** — displays the verification spec's
  test cases and provides a "Run Verification" action that executes
  them against the active instance and records results. The detailed
  test-execution behavior is specified elsewhere and is out of scope
  for this prompt beyond wiring the existing execution path.
- **Output entry (§14.12.9)** — color-coded log output from deploy,
  configure, and verify operations for the active client's
  instances. Filterable by source operation and by instance.
  Credentials must be masked before display using the existing
  `[password]` substitution pattern from the legacy Output panel.
  Does not display the phase status banner.

If an existing `espo_impl` module requires modification to support
scoping by active client / active instance rather than global state,
make the minimal surgical change required and call it out in the PR
description. Do not refactor beyond what is necessary.

### 6. Empty states (§14.12.10)

Implement the three empty-state cases:

- **No instances yet for the active client** — Instances entry shows
  an empty-state message and a prominent "+ New Instance" button.
  Deploy entry shows an empty-state message directing the
  implementor to create an instance first or run the wizard (which
  will create one). Configure, Verify, and Output entries show
  empty-state messages directing the implementor to Instances or
  Deploy.
- **No active client selected** — all five entries show the
  no-active-client empty-state message; the active-instance picker
  and phase status banner are hidden.
- **No YAML files in `{project_folder}/programs/`** — Configure
  entry shows its own empty-state copy.

Use exact wording from §14.12.10 where the PRD provides it; otherwise
match the tone of existing empty-state messages in the Requirements
tab.

### 7. Legacy JSON instance migration — one-time runner (ISS-017)

Implement a one-time migration that reads existing `data/instances/*.json`
profiles and inserts them into the corresponding per-client Instance
table.

**Requirements:**

- **Location** — `automation/migrations/instance_json_migration.py`
  as a Qt-free module, unit-testable, with a single public entry
  point `run_migration(master_db, instances_dir) -> MigrationReport`.
- **Trigger** — invoked automatically at application startup after
  the master database and per-client databases are opened, before
  the main window is shown. Also exposed as a CLI entry point
  (`uv run crmbuilder-migrate-instances`) so Doug can re-run it
  manually.
- **Idempotency** — safe to re-run. The migration records its own
  completion in a `MigrationState` row (reuse the existing migration
  tracking mechanism if one exists; otherwise add the minimal row
  needed). On subsequent runs, it re-scans the JSON directory and
  only inserts rows that do not already exist in the target Instance
  table, matched by `code`. Never overwrites existing Instance rows.
- **Client resolution** — each legacy JSON file is mapped to a
  client by the existing convention used by `instance_panel.py`
  today. Read `instance_panel.py` to determine the convention before
  writing the migration; do not guess. If a JSON file cannot be
  confidently mapped to exactly one client, the migration skips it
  and records a warning in the MigrationReport rather than
  inserting into an arbitrary client's database.
- **Field mapping** — map legacy JSON fields to the new Instance
  columns (name, code, environment, url, username, password,
  description, is_default). Fields that did not exist in the legacy
  JSON format (code, environment, is_default) are synthesized per
  the rules in §16.17:
  - `code` — derived from the legacy filename / name; collision
    within a single client appends `-2`, `-3`, etc.
  - `environment` — defaults to `production` unless the legacy name
    contains an obvious substring (`test`, `dev`, `staging`) that
    maps to a valid environment value from the Instance CHECK
    constraint.
  - `is_default` — true for the first instance migrated into a
    given client; false for the rest.
- **Migrated file handling** — after successful insert, rename the
  source JSON file to `{original}.migrated` rather than deleting.
  This preserves the legacy data for rollback and makes re-runs
  cleanly idempotent.
- **MigrationReport** — returned by `run_migration` and logged at
  startup. Includes: number of JSON files scanned, number of rows
  inserted, number skipped (with reason), number already migrated,
  list of any warnings. If the report contains warnings, surface
  them to the user in a startup dialog after the main window opens.
- **Empty-directory case** — if `data/instances/` does not exist or
  contains no `*.json` files, the migration completes silently and
  records "nothing to migrate" in the MigrationReport.

## Scope — What This Prompt Does NOT Do

- Does not implement the Deploy Wizard internals (Prompt D).
- Does not implement encrypted credential storage (ISS-018 — deferred).
- Does not touch terminology (Prompt E).
- Does not add or modify schema — Instance and DeploymentRun tables
  already exist from Prompt A. If a schema gap is discovered while
  implementing this prompt, stop and surface it rather than adding
  columns here.
- Does not rewrite `espo_impl` logic — the Configure, Verify, and
  Output entries are thin wrappers over existing behavior.
- Does not delete legacy `data/instances/*.json` files — the
  migration renames them to `.migrated`.

## Testing

- Unit tests for `automation/migrations/instance_json_migration.py`
  covering: empty directory, single file happy path, multiple files
  into one client, multiple files across multiple clients, code
  collision handling, environment inference, is_default assignment,
  idempotent re-run, unresolvable-client skip with warning, already-
  migrated skip, and the `.migrated` rename.
- Unit tests for the Deployment tab view-models (Qt-free layer)
  covering: active-instance picker population and default selection,
  picker persistence across entry switches, phase status banner
  work-item resolution per entry, empty-state resolution for all
  three cases in §14.12.10, and Instances entry default-flag
  semantics (setting a new default clears the previous).
- Widget smoke tests for the five sidebar entries — instantiate each,
  verify it renders without error against a fixture per-client
  database containing zero, one, and multiple instances.
- Full regression: `uv run pytest tests/ -v` must pass and `ruff`
  must be clean. The current baseline is 953 tests passing.

## Deliverables

- `automation/ui/deployment/` — sidebar, header (picker + banner),
  and the five entry views, split into Qt-free view-model modules
  and PySide6 widget modules.
- `automation/migrations/instance_json_migration.py` — one-time
  migration module.
- CLI entry point `crmbuilder-migrate-instances` wired up in
  `pyproject.toml`.
- Application startup wiring so the migration runs before the main
  window is shown and any warnings are surfaced afterward.
- Unit and widget tests per the Testing section above.
- ISS-017 marked **Resolved** in `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`
  §16.17 in a follow-up PRD edit (out of scope for this code PR, but
  note the need in the PR description).

## Out-of-Scope Reminders

- Deploy Wizard internals — Prompt D.
- Encrypted credential storage — ISS-018.
- Terminology sweeps — Prompt E.
