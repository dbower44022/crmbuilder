# Session Prompt: L2 PRD Design Items — Commits 2 and 3

## Context

A design session resolved four UI gaps (Client Creation, Deployment Tab, Instance-to-Client Association, Deploy Wizard Scope) and produced 22 new decisions (DEC-054 through DEC-075) and 3 new issues (ISS-016 Resolved, ISS-017, ISS-018). The L2 PRD updates are being applied across three commits:

- **Commit 1 (complete, v1.14):** Section 3.1 Client schema rewrite, new Sections 6.5 Instance and 6.6 DeploymentRun, all Section 15 decision entries, all Section 16 issue entries.
- **Commit 2 (this session):** Section 14.1 rewrite, Section 14.2 rename, Section 14.9 rewrite, administrator→implementor and Project Dashboard→Requirements Dashboard sweeps across §14.3–§14.10.
- **Commit 3 (this session):** New Section 14.11 Clients Tab, new Section 14.12 Deployment Tab.

## Repository

`dbower44022/crmbuilder`

## Required Reading at Start of Session

1. `CLAUDE.md` (root)
2. `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` — the v1.14 document with Commit 1 already applied. Read Section 14 in full to understand the current state before editing.
3. This session prompt for the drafted prose to apply.

## Key Decisions Driving These Edits

- **DEC-055:** Three peer tabs (Clients, Requirements, Deployment) replace the mode-selector pattern.
- **DEC-056:** Selecting a client on the Clients tab establishes the global active client.
- **DEC-057:** Active client name shown inline in Requirements and Deployment tab labels.
- **DEC-058:** Clients tab uses master/detail layout.
- **DEC-059:** App launch restores last_active_tab and last_selected_client_id.
- **DEC-062:** Deployment tab uses sidebar mirroring Requirements tab.
- **DEC-063:** Deployment sidebar: Instances, Deploy, Configure, Verify, Output.
- **DEC-064:** Deployment tab fully scoped to active client.
- **DEC-065:** Phase status banner with Mark Complete on Deployment content.
- **DEC-068:** Active-instance picker on Deployment tab.
- **DEC-070–075:** Deploy Wizard scenarios and supported deployment targets.

All decisions are already recorded in Section 15 (Commit 1). This session applies the corresponding prose to Section 14.

## Commit 2: Section 14.1, 14.2, 14.9 Rewrites + Sweeps

### Section 14.1 — Full Rewrite

Replace the existing 14.1.1 (Mode Architecture), 14.1.2 (Requirements Mode Navigation), and 14.1.3 (Client Selection and Context) with the following three subsections.

#### 14.1.1 Tab Architecture

The main window is organized as three peer tabs displayed in a persistent tab strip at the top of the window: Clients, Requirements, and Deployment. The implementor switches between tabs at any time by clicking the tab labels. Each tab contains a self-contained workspace and the three tabs share no panels.

The Clients tab is where client implementations are created, reviewed, and edited. It is the only place in the application where the active client is selected. Selecting a client on the Clients tab establishes that client as the global active client for the Requirements and Deployment tabs. Section 14.11 specifies the Clients tab in detail.

The Requirements tab contains the automation panels for managing the requirements lifecycle: the Requirements Dashboard, Work Item Detail, Session Orchestration, Import Review, Impact Analysis, Document Generation, and Data Browser. This tab is the primary workspace from project creation through YAML generation and CRM Selection (Phases 1–9). All Requirements tab content operates against the active client's database.

The Deployment tab contains the panels for provisioning, configuring, and verifying CRM instances: Instances, Deploy, Configure, Verify, and Output. This tab is the primary workspace for CRM Deployment, CRM Configuration, and Verification (Phases 10–12). Deployment tab content is fully scoped to the active client; the implementor cannot operate the Deployment tab against an instance belonging to a different client. Section 14.12 specifies the Deployment tab in detail.

The Requirements and Deployment tabs display the active client name inline in the tab label — for example, "Requirements — CBM" and "Deployment — CBM". When no client is selected, the labels read "Requirements (no client selected)" and "Deployment (no client selected)" and the tab content area shows an empty-state message directing the implementor to the Clients tab. The tab labels themselves remain enabled and clickable in all states, consistent with the buttons-never-disabled pattern (Section 14.10.6).

Each tab preserves its internal navigation state independently. Switching from Requirements to Deployment and back returns the implementor to the same screen they left. Switching the active client on the Clients tab resets the internal state of the Requirements and Deployment tabs, since they now operate against a different client.

On application launch, the previously active tab and the previously selected client are restored from per-machine application preferences (last_active_tab and last_selected_client_id). On first-ever launch, or when the previously selected client's project folder or database file is missing, the application opens the Clients tab with no client selected.

#### 14.1.2 Requirements Tab Navigation

The Requirements tab uses two navigation mechanisms: a sidebar for top-level views and a drill-down stack for work-item-specific actions.

The sidebar contains four entries: Requirements Dashboard, Data Browser, Documents, and Impact Review. The Requirements Dashboard is selected by default when the implementor enters the Requirements tab. Selecting a sidebar entry replaces the content area with that view and resets the drill-down stack.

The drill-down stack manages navigation within the Requirements Dashboard view. When the implementor selects a work item on the Requirements Dashboard, the content area transitions to the Work Item Detail view. From Work Item Detail, actions such as Import Review or Session Orchestration push a new screen onto the stack. A breadcrumb trail above the content area shows the current path — for example, "Requirements Dashboard > Mentor Onboarding (MR-ONBOARD) > Import Review" — and each segment is a clickable link that pops the stack back to that level. The breadcrumb is visible only when the stack depth exceeds one.

The Data Browser, Documents, and Impact Review sidebar entries are cross-cutting views that operate outside the drill-down stack. They are accessible at any time regardless of the current stack state. If the implementor is deep in a drill-down (for example, reviewing an import) and clicks Data Browser in the sidebar, the Data Browser view appears. If they click Requirements Dashboard again, the drill-down stack is restored to its previous state.

All Requirements tab navigation operates within the active client context. There is no client selector on the Requirements tab itself — switching clients is done by going to the Clients tab and selecting a different client.

#### 14.1.3 Active Client Context

The active client is the client implementation that the Requirements and Deployment tabs currently operate against. There is exactly one active client at a time, or none if the implementor has not yet selected one.

The active client is established by selecting a client in the master/detail list on the Clients tab. Section 14.11 specifies the Clients tab interaction in detail. When a client is selected, the application:

1. Sets that client as the active client for the application session
2. Updates Client.last_opened_at for that client
3. Updates the Requirements and Deployment tab labels to display the client name
4. Loads the client's database from {project_folder}/.crmbuilder/{code}.db and makes it available to all Requirements and Deployment tab queries
5. Persists the selection to per-machine preferences as last_selected_client_id for restoration on the next launch

The client context is available to every screen in the Requirements and Deployment tabs. All database queries, prompt generation, import processing, document generation, instance management, and deployment operations operate against the active client's database.

When no client is currently active (first-ever launch, or the previously selected client became unavailable), the Requirements and Deployment tabs display empty-state messages directing the implementor to the Clients tab. All sidebar entries and content areas in those tabs are inert until a client is selected, but the tabs themselves remain navigable.

When the active client's crm_platform and deployment_model columns are populated (after CRM Selection completes in Phase 9), the Deployment tab uses those values to default the Deploy Wizard's scenario selection (Section 14.12.5). Until Phase 9 completes, those columns are NULL and the Deploy Wizard requires explicit selection on its first step.

### Section 14.2 — Rename and Targeted Edits

- Rename heading "14.2 Project Dashboard" → "14.2 Requirements Dashboard"
- Replace intro paragraph: "The Project Dashboard is the default view in Requirements mode and the administrator's primary workspace." → "The Requirements Dashboard is the default view in the Requirements tab and the implementor's primary workspace."
- In 14.2.1: "without requiring the administrator to scan" → "without requiring the implementor to scan"
- In 14.2.2: "represent work the administrator has already started" → "represent work the implementor has already started"; "The administrator is free to select" → "The implementor is free to select"
- In 14.2.5: "Clicking a work item row anywhere on the dashboard" → "Clicking a work item row anywhere on the Requirements Dashboard"; breadcrumb example "Dashboard > {Work Item Name}" → "Requirements Dashboard > {Work Item Name}"
- In 14.2.6: "the administrator is aware" → "the implementor is aware"

### Section 14.9 — Full Rewrite

Replace the existing six subsections (14.9.1 through 14.9.6) with the following three subsections.

#### 14.9 Cross-Tab Workflows

The Requirements and Deployment tabs serve different phases of the project lifecycle but they are not isolated from each other. This section defines the workflows that span both tabs — specifically, how work begun in one tab triggers work in the other, and how discoveries made during deployment are fed back into the requirements layer.

#### 14.9.1 Phase Handoff from Requirements to Deployment

When the CRM Selection work item completes (Phase 9), the active client's crm_platform and deployment_model columns are populated with the selected values. At this point the project is ready for CRM Deployment, and the crm_deployment work item appears as ready on the Requirements Dashboard.

The crm_deployment, crm_configuration, and verification work items are tracked in the Requirements tab for status, dependencies, and completion, but the actual work happens in the Deployment tab. When the implementor selects one of these three work items in the Requirements tab, the Work Item Detail view displays a guidance message indicating that the work is performed in the Deployment tab and suggesting that the implementor switch tabs.

The corresponding work item is also surfaced inside the Deployment tab as the phase status banner above each Deploy/Configure/Verify entry (Section 14.12.2). The Mark Complete action on that banner updates the work item's status without requiring the implementor to leave the Deployment tab. This bidirectional surfacing ensures that the implementor can drive the workflow from whichever tab they happen to be in.

#### 14.9.2 Post-Deployment Feedback Loop

After the CRM is configured and verified, the implementor may discover issues that require requirements-layer changes — a field type that does not work as expected, a layout that needs adjustment, a relationship that needs modification, or a process that was missed. The Deployment tab does not include UI for editing requirements; the implementor switches to the Requirements tab and makes the change through the Data Browser (Section 14.8) or by reopening the relevant work item for revision (Section 9.7.2).

Changes made through the Data Browser trigger impact analysis (Section 12) as usual, recording the change in the audit trail and surfacing any downstream effects. If the change affects YAML output, the implementor regenerates the affected YAML through the Documents view (Section 14.7), then switches back to the Deployment tab and uses the Configure entry to reapply the updated YAML to the active instance.

The Workflow Engine does not automatically reopen completed work items based on deployment-discovered issues. The implementor decides whether the issue warrants a formal revision (which reopens the work item and propagates regression to dependents) or a direct edit through the Data Browser (which records the change without reopening the work item). This is a deliberate choice — many deployment-discovered issues are minor adjustments that do not warrant the cost of regenerating downstream documents, and the implementor is in the best position to judge.

#### 14.9.3 YAML File Handoff

The Document Generator produces YAML files in {project_folder}/programs/ (Section 13.7). The Deployment tab's Configure entry (Section 14.12.7) reads from the same directory. This creates an automatic handoff: YAML files generated in the Requirements tab are immediately visible in the Configure entry without any manual transfer step.

The implementor can verify the generated YAML files by opening the Configure entry before running configuration. Files generated for one client are written under that client's project folder and are therefore visible only when that client is the active client.

### Sweeps Across §14.3–§14.10

Apply these two find-and-replace operations across all of Sections 14.3 through 14.10 (inclusive):

1. **"Project Dashboard"** → **"Requirements Dashboard"** — only where it refers to the specific view (not generic uses of the word "dashboard").
2. **"administrator"** → **"implementor"** — all instances. The L2 PRD uses "implementor" as the standard role term going forward.

Do NOT sweep Sections 14.11 or 14.12 — those are new sections being inserted in Commit 3 and already use the correct terms.

### Commit 2 Deliverables

- Apply all Section 14.1, 14.2, 14.9 changes and both sweeps
- Bump version to 1.15, update Last Updated (format: MM-DD-YY HH:MM)
- Validate with pack.py/validate.py
- Verify with pandoc: zero matches for "Project Dashboard", zero matches for "administrator" in §14, zero matches for "Mode Architecture"
- Commit and push

## Commit 3: New Sections 14.11 and 14.12

### Section 14.11 Clients Tab

Insert after Section 14.10 (Common UI Patterns). Five subsections:

#### 14.11 Clients Tab

The Clients tab is the application's entry point for managing client implementations. It is the only place in the application where clients are created, where the active client is selected, and where client-level metadata is reviewed and edited. The Clients tab does not depend on having a client already selected — it is the surface through which client selection happens in the first place.

#### 14.11.1 Layout

The Clients tab uses a master/detail layout. The left pane is a sortable list of all client implementations registered in the master database. The right pane is the detail view for the currently selected client in the list, or an empty-state placeholder when no client is selected in the list.

Above the list, a "+ New Client" button opens the Create Client form (Section 14.11.3) in the detail pane. The list itself shows one row per client with the following columns: name, code, project folder, last opened. The default sort is by last_opened_at descending (most recently opened first), with NULL values sorted last. Clicking a column header changes the sort.

Selecting a row in the list both displays the client's detail in the right pane and establishes that client as the application's active client (Section 14.1.3). There is no separate "Open" action — selection and activation are the same gesture.

#### 14.11.2 Client Detail Pane

The detail pane displays the metadata for the currently selected client and provides inline editing for the fields the implementor is allowed to change after creation.

The pane shows the following fields: Name (inline editable), Code (read-only after creation), Description (inline editable), Project Folder (read-only after creation), Database File (read-only, displayed as {project_folder}/.crmbuilder/{code}.db for reference), Created (read-only timestamp), Last Opened (read-only timestamp), CRM Platform (read-only, displayed only after Phase 9 has populated Client.crm_platform), and Deployment Model (read-only, displayed only after Phase 9 has populated Client.deployment_model).

Code and project_folder are read-only after creation because changing either would orphan the client's database file. The implementor can edit name and description freely; saving an edit updates the master database and refreshes the list pane.

Below the metadata fields, the detail pane displays a status indicator showing whether the client's project folder and database file are reachable. A green indicator means both are present and the database opens successfully. A red indicator means one or both are missing or the database fails to open; the specific error is displayed inline. A client in the red state cannot be set as the active client for the Requirements and Deployment tabs — clicking its row in the list shows the error in the detail pane and refuses the activation. The implementor must repair the project folder, restore the database file, or remove the master row through external means before the client can be reactivated.

#### 14.11.3 Create Client Form

The Create Client form replaces the contents of the detail pane when the implementor clicks "+ New Client". The form captures four fields: Name (required, free text), Code (required, must match ^[A-Z][A-Z0-9]{1,9}$, must be unique in the master database), Description (optional, free text), and Project Folder (required, must be an absolute path, must exist on disk, must not already be in use by another client).

Validation runs on the Save action. Validation errors are displayed inline below the offending field, consistent with the error presentation pattern in Section 14.10.8. The form does not check the git status of the project folder, does not require the folder to be empty, and does not offer to initialize the folder — the project folder is treated as opaque, and the implementor is expected to have created or cloned the client's repository before opening the Create Client form.

When validation passes, the application performs the following steps in order:

1. Creates the {project_folder}/.crmbuilder/ directory if it does not exist
2. Creates the SQLite database file at {project_folder}/.crmbuilder/{code}.db
3. Runs the schema migrations to initialize the client database (Sections 4 through 8)
4. Creates the standard subfolders inside the project folder if they do not already exist: PRDs/, programs/, reports/, and Implementation Docs/
5. Inserts the new row into the master database's Client table

If any of these steps fails, all changes are rolled back: the master row is not inserted, the .crmbuilder/ directory is removed if it was created by this operation, the database file is removed if it was created by this operation, and any subfolders created by this operation are removed. The form remains open with the specific failure displayed as an error so the implementor can correct and retry. Subfolders that already existed before the operation are never removed, regardless of whether the rollback occurs.

On successful creation, the new client is automatically selected in the list, becomes the application's active client, and the Requirements and Deployment tab labels update to reflect the new selection. The detail pane transitions from the Create Client form to the standard detail view of the newly created client.

#### 14.11.4 Empty State

When the master database contains no clients, the list pane displays a brief message stating that no clients exist yet, and the detail pane displays a "+ New Client" button as the only action. Once at least one client has been created, the empty state never reappears unless all clients are removed.

#### 14.11.5 No Delete Action

The Clients tab does not provide a delete action for client rows in v1. Removing a client requires deleting the master database row and the project folder through external means. This is intentional — deletion of a requirements database is a high-consequence action that affects an entire client implementation, and the safest way to perform it is outside the application. A future version may add a guarded delete action with confirmation and archival.

### Section 14.12 Deployment Tab

Insert after Section 14.11. Eleven subsections plus two nested sub-subsections under 14.12.5. The full prose is extensive — see the design session conversation for the complete drafted text of all subsections:

- 14.12 Deployment Tab (intro)
- 14.12.1 Layout
- 14.12.2 Active-Instance Picker and Phase Status Banner
- 14.12.3 Instances Entry
- 14.12.4 Deploy Entry
- 14.12.5 Deploy Wizard
  - 14.12.5.1 Self-Hosted Path
  - 14.12.5.2 Cloud-Hosted and Bring-Your-Own Paths
- 14.12.6 Supported Deployment Targets (includes a table)
- 14.12.7 Configure Entry
- 14.12.8 Verify Entry
- 14.12.9 Output Entry
- 14.12.10 Empty States
- 14.12.11 Schema Note

**IMPORTANT:** The full drafted prose for Section 14.12 was reviewed and confirmed in the design session but is too long to reproduce in this prompt. The implementing session should retrieve the conversation history for the complete text. Search for "Here's the draft for new Section 14.12 (Deployment Tab)" in the design session conversation. All subsection text was confirmed by Doug without changes.

### Commit 3 Deliverables

- Insert Sections 14.11 and 14.12 after Section 14.10
- Bump version to 1.16, update Last Updated (format: MM-DD-YY HH:MM)
- Validate with pack.py/validate.py
- Verify with pandoc: confirm "14.11 Clients Tab" and "14.12 Deployment Tab" headings, confirm "14.12.6 Supported Deployment Targets" table, confirm "EspoCRM" appears in §14.12.5.1
- Commit and push

## After Both Commits

Once v1.16 is committed:

1. Identify any User Guide updates needed based on the L2 PRD changes and apply them in a separate commit.
2. The session prompt for this work is at `PRDs/product/crmbuilder-automation-PRD/SESSION-PROMPT-l2-prd-design-items-commits2-3.md`.

## Working Approach

- Use Python scripts for XML generation (same pattern as Commit 1) — do not attempt manual str_replace on large XML blocks.
- For the §14.3–§14.10 sweep, use Python string replacement on the document.xml after unpacking.
- Unpack/edit/repack workflow with validation after each commit.
- git pull before unpacking per standing rule.
