# Claude Code Implementation Prompt — Step 15c: Document Generation, Data Browser, Mode Integration

## Context

You are implementing **Step 15c of the CRM Builder Automation roadmap** — the third and final sub-step that completes the User Interface (Section 14 of the L2 PRD).

- **Step 15a (complete)** — Schema bump for ISS-012, mode integration, Project Dashboard, Work Item Detail, Common UI Patterns
- **Step 15b (complete)** — Session Orchestration, Import Review, Impact Analysis Display
- **Step 15c (this prompt)** — Document Generation view (14.7), Data Browser (14.8), Integration with Existing Panels (14.9)

After Step 15c, only Step 16 remains (CBM integration testing). The full Requirements mode application will be functionally complete.

The complete design is in the Level 2 PRD at `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`.

**Read Sections 14.7, 14.8, and 14.9 of the L2 PRD before writing any UI code.** Also re-read Section 14.10 and the work you did in Steps 15a and 15b so your code follows the established conventions.

This is step 15c of 16. Steps 9 (database), 10 (workflow), 11 (prompts), 12 (importer), 13 (impact analysis), 14 (docgen), 15a, and 15b are complete with **953 tests passing**. L2 PRD is at v1.13 with ISS-001 through ISS-015 tracked.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. **Read the existing `automation/ui/` package before starting** — Steps 15a and 15b established conventions you must follow:

- **Pure-logic modules separate from Qt widgets** (`navigation.py`, `client_context.py`, `dashboard_logic.py`, `work_item_logic.py`, `session_logic.py`, `import_logic.py`, `impact_logic.py` are all Qt-free)
- **Common widgets in `automation/ui/common/`** — reuse them, don't duplicate
- **Drill-down stack and breadcrumb** — `automation/ui/navigation.py`; views get pushed onto the stack via RequirementsWindow methods
- **Signal-based navigation** between child widgets and the RequirementsWindow — look at how `tab_sessions.py` emits `generate_requested(int)` and bubbles up through `SessionsTab` to `RequirementsWindow._on_navigate_to_session`
- **Engine state transitions stay in `header_actions.py` and `impact_view.py`** — Step 15c should not add new `engine.revise/complete/start/block/unblock` call sites unless there's a clear reason

Step 15c will reuse these existing modules:

- `automation/impact/engine.py` — `ImpactAnalysisEngine.analyze_proposed_change()` for Data Browser pre-commit analysis
- `automation/docgen/generator.py` — `DocumentGenerator.generate()`, `generate_batch()`, `get_stale_documents()`, `push()` for the Documents view
- `automation/ui/impact/precommit_confirm.py` — `PrecommitConfirmDialog` built in Step 15b for the Data Browser to wire up
- `automation/ui/impact/shared_presentation.py` — shared impact display used in 4 contexts including the Data Browser's pre-commit dialog

## Where the Code Goes

Three new sub-packages within `automation/ui/` plus updates to existing files:

```
automation/
└── ui/
    ├── documents/                    # NEW — Section 14.7 Document Generation View
    │   ├── __init__.py
    │   ├── documents_view.py         # Main container (sidebar entry)
    │   ├── documents_logic.py        # Pure Python: inventory assembly, staleness grouping, sort order (Qt-free)
    │   ├── document_inventory.py     # 14.7.1 — grouped list of all documents
    │   ├── document_row.py           # Single document entry widget
    │   ├── staleness_expansion.py    # 14.7.2 — expandable staleness summary per row
    │   ├── generation_flow.py        # 14.7.4 — inline pipeline progress display
    │   ├── batch_controls.py         # 14.7.5 — multi-select + Regenerate Selected controls
    │   └── generation_logic.py       # Pure Python: state machine for generation progress (Qt-free)
    ├── browser/                      # NEW — Section 14.8 Data Browser
    │   ├── __init__.py
    │   ├── browser_view.py           # Main container (sidebar entry)
    │   ├── browser_logic.py          # Pure Python: tree assembly, record detail mapping, edit state (Qt-free)
    │   ├── navigation_tree.py        # 14.8.1 — left-hand tree widget with search
    │   ├── tree_model.py             # Pure Python: tree data model driven by schema FK relationships (Qt-free)
    │   ├── record_detail.py          # 14.8.2 — form layout for record display
    │   ├── record_editor.py          # 14.8.3 — edit mode with type-constrained inputs
    │   ├── fk_selector.py            # 14.8.3 — searchable FK dropdown selector
    │   ├── related_records.py        # 14.8.2 — collapsible groups of FK back-references
    │   ├── audit_trail.py            # 14.8.7 — ChangeLog history panel
    │   └── record_creator.py         # 14.8.6 — new record flow (inserts exempt from impact analysis)
    └── mode_integration/             # NEW — Section 14.9 Integration with Existing Panels
        ├── __init__.py
        ├── instance_association.py   # 14.9.3 — client ↔ instance association logic (Qt-free)
        ├── deployment_guidance.py    # 14.9.2 — guidance message for crm_deployment work item
        └── mode_transition.py        # 14.9.2 — helpers for mode switching with context preservation
```

Plus updates to existing files:

```
automation/ui/requirements_window.py                    # MODIFY: register Documents and Data Browser sidebar entries, add staleness summary link
automation/ui/work_item/header_actions.py               # MODIFY: wire "Generate Document" action (currently a placeholder) to the Documents view scoped to the work item
automation/ui/work_item/tab_documents.py                # MODIFY: wire the "Generate Document" tab action to the Documents view
automation/ui/work_item/detail_view.py                  # MODIFY: show the 14.9.2 guidance message for crm_deployment/crm_configuration/verification work items
automation/ui/dashboard/staleness_summary.py            # MODIFY: replace the "coming in Step 15c" toast with a real link to the Documents view filtered to stale items
espo_impl/ui/main_window.py                             # MODIFY: implement 14.9.3 auto-select of associated instance when switching to Deployment mode
```

### Tests

```
automation/tests/
├── test_ui_documents_logic.py        # Pure-logic tests for documents_logic + generation_logic
├── test_ui_browser_logic.py          # Pure-logic tests for browser_logic + tree_model
├── test_ui_mode_integration.py       # Pure-logic tests for instance_association + mode_transition
├── test_ui_documents_view.py         # Light import-and-construct tests
└── test_ui_browser_view.py           # Light import-and-construct tests
```

Same testing strategy as 15a/15b: pure-Python logic gets unit tests; Qt widgets get only import-and-construct tests. No pytest-qt.

## Foundation — Existing API Surface

### Document Generator — `automation.docgen.generator`

```python
from automation.docgen.generator import DocumentGenerator

docgen = DocumentGenerator(conn, master_conn=master_conn, project_folder=project_folder)

# Single generation
result = docgen.generate(work_item_id, mode="final")   # or mode="draft"
# result has: file_path or file_paths, warnings, git_commit_hash, error, generation_log_id

# Batch generation
results = docgen.generate_batch([wi1, wi2, wi3], mode="final")
# Each document committed individually; failures isolated per document

# Staleness detection
stale = docgen.get_stale_documents()
# Returns list of StaleDocument dataclass: work_item_id, item_type, last_generated_at,
# latest_change_at, change_count, change_summary

# Optional git push
pushed = docgen.push()
```

The Documents view is the primary UI consumer. Do NOT call `run_full_import()`-equivalent shortcuts — use the staged methods for interactive feedback.

**Important:** The DocumentGenerator requires a `project_folder` at construction. For Step 15c, the project folder comes from the client context's `crm_platform` / instance profile association (Section 14.9.3), or from a configuration setting. Flag this as an ambiguity if the existing client context doesn't already expose a project folder path.

### Impact Analysis Engine — `automation.impact.engine`

```python
from automation.impact.engine import ImpactAnalysisEngine

impact = ImpactAnalysisEngine(conn)

# Pre-commit analysis for Data Browser edits and deletes
proposed_impacts = impact.analyze_proposed_change(
    table_name="Field",
    record_id=42,
    change_type="update",    # or "delete"
    new_values={"field_type": "text"},   # for updates; omit for deletes
    rationale=None,  # collected by the UI, passed through for engine awareness
)
# Returns list of ProposedImpact objects — not yet persisted
```

The Data Browser's edit and delete flows call this method, show the results using the existing `PrecommitConfirmDialog` from `automation/ui/impact/precommit_confirm.py`, collect the rationale, and on confirmation write the data change, ChangeLog entries, and ChangeImpact records in a single transaction.

**The transaction write is the Data Browser's responsibility, not the engine's.** `analyze_proposed_change()` is read-only — it returns in-memory impact objects without writing anything. The Data Browser's edit commit flow handles the actual transaction:

1. Call `analyze_proposed_change()` to compute the impact set
2. Show `PrecommitConfirmDialog` with the impacts
3. If confirmed with rationale, open a transaction
4. Write the UPDATE/DELETE to the target table
5. Write ChangeLog entries
6. Write ChangeImpact rows (with `action_required=FALSE` initially — they are user-created impacts, not auto-generated)
7. Commit

### PrecommitConfirmDialog — `automation.ui.impact.precommit_confirm`

```python
from automation.ui.impact.precommit_confirm import PrecommitConfirmDialog

dialog = PrecommitConfirmDialog(proposed_impacts, parent=self)
if dialog.exec():
    rationale = dialog.get_rationale()
    # proceed with the write
else:
    # cancelled
```

Built in Step 15b with no caller. Step 15c's Data Browser is its caller.

### Schema — `automation.db.client_schema`

Read `client_schema.py` to build the Data Browser's tree model. The tree structure follows foreign key relationships:

- Domain → Process → {ProcessStep, Requirement, ProcessEntity, ProcessField, ProcessPersona}
- Entity → {Field → FieldOption, Relationship, LayoutPanel → {LayoutRow, LayoutTab}, ListColumn}
- Persona (flat)
- Decision (flat)
- OpenIssue (flat)

Sub-domains nest under their parent via `parent_domain_id`. Services (`is_service=TRUE`) appear in a separate "Services" branch.

The `Client` table lives in the master database (for Master PRD and CRM Evaluation Report data). The Data Browser is primarily concerned with the client database, but you may need to expose Client table editing through a separate top-level entry. Flag this as an ambiguity — the L2 PRD doesn't explicitly address whether the Client record is editable through the Data Browser.

### Existing CRM Builder — `espo_impl/`

Read `espo_impl/ui/main_window.py` to understand the current structure. Step 15a added the mode selector and wrapped the existing deployment panels in a container. Step 15c's Section 14.9 work needs to:

1. Read the existing Instance panel's instance profile to find the `project_folder` path
2. When switching from Deployment mode to Requirements mode, auto-select the client whose `crm_platform` matches the selected instance (Section 14.9.3)
3. When switching from Requirements mode to Deployment mode, auto-select the instance associated with the current client (Section 14.9.3)

The existing Instance panel code is in `espo_impl/` somewhere — look for the module that manages instance profiles. **You may need to read files outside the Step 15c scope to understand the integration point** — that's fine, as long as you don't modify them.

## Definition of Done

This step is complete when **all** of the following are true:

### Section 14.7 — Document Generation View

1. **Documents view** (`documents/documents_view.py`) is the main container, registered as the "Documents" sidebar entry in RequirementsWindow. Replaces the placeholder from Step 15a.

2. **Two entry points** per Section 14.7:
   - Documents sidebar entry — cross-cutting, shows all document types
   - Generate Document action on Work Item Detail header — scoped to a single work item with a "Show All Documents" toggle
   - Both entry points use the same view with different initial scope

3. **Document Inventory** (`documents/document_inventory.py` + `document_row.py`) implements Section 14.7.1:
   - Eight document types grouped per Section 13.2: Master PRD, Entity Inventory, Entity PRDs, Domain Overviews, Process Documents, Domain PRDs, YAML Program Files, CRM Evaluation Report
   - Each entry shows: document name (human-readable-first), work item status badge, document status (not generated / current / stale / draft only), last final generation timestamp, output file path
   - Sort order per Section 14.7.2: stale first, then current, draft only, not generated
   - Pure-Python sort and grouping logic in `documents_logic.py`

4. **Staleness indicators** (`documents/staleness_expansion.py`) implement Section 14.7.2:
   - Below each stale document: count of ChangeLog entries post-dating last generation, brief change summary
   - Expandable to show individual ChangeLog entries contributing to staleness
   - Uses `docgen.get_stale_documents()` for the data source

5. **Generation Actions** (on each document row) implement Section 14.7.3:
   - **Generate Final** — available when work item status is `complete`; runs `docgen.generate(wi, mode="final")`
   - **Generate Draft** — available when work item status is `in_progress`; runs `docgen.generate(wi, mode="draft")`
   - **Buttons are never disabled** per Section 14.10.6 — clicking an inapplicable action shows an explanatory toast

6. **Generation Flow** (`documents/generation_flow.py`) implements Section 14.7.4:
   - Inline pipeline progress display below the document entry
   - Six stages: Query → Validate → Render → Write → Git Commit (final only) → GenerationLog (final only)
   - Warning pause at validate step if validation produces warnings — administrator can proceed or cancel
   - Confirmation panel on completion: file path, warnings accepted, git commit hash
   - "Open File" action opens the generated file in the system default application
   - "Push to Remote" action offers optional `docgen.push()` with failure reporting

7. **Batch Regeneration** (`documents/batch_controls.py`) implements Section 14.7.5:
   - Checkbox on each document entry for multi-select
   - "Regenerate Selected" button appears when one or more documents are selected
   - "Select All Stale" shortcut
   - Calls `docgen.generate_batch()` which commits each document individually
   - Progress indicator shows current document name
   - Pause on validation warnings with proceed/skip options
   - Batch summary at the end: success count, skipped, failures
   - Single git push offered after all commits complete
   - **Final mode only** — draft generation is not batchable

8. **Staleness summary link** in `dashboard/staleness_summary.py` is updated:
   - The Step 15a placeholder toast ("Coming in Step 15c") is replaced with a real link that navigates to the Documents view filtered to stale documents

### Section 14.8 — Data Browser

9. **Data Browser view** (`browser/browser_view.py`) is the main container, registered as the "Data Browser" sidebar entry in RequirementsWindow. Replaces the placeholder from Step 15a.

10. **Navigation Tree** (`browser/navigation_tree.py` + `tree_model.py`) implements Section 14.8.1:
    - Left-hand panel
    - Hierarchical organization per Section 14.8.1:
      - Domains → Processes → {ProcessSteps, Requirements, cross-references}; sub-domains nested; services in separate branch
      - Entities → {Fields → FieldOptions, Relationships, LayoutPanels → {LayoutRows, LayoutTabs}, ListColumns}
      - Personas (flat)
      - Decisions (flat, sortable by identifier)
      - Open Issues (flat, sortable by identifier)
    - Each node shows record name in human-readable-first format with count badge on expandable nodes
    - Search field above the tree filters nodes by name/code/identifier as the administrator types
    - Pure-Python tree model in `tree_model.py` driven by the schema FK relationships — test without Qt

11. **Record Detail** (`browser/record_detail.py`) implements Section 14.8.2:
    - Main area to the right of the tree
    - Shows all column values for the selected record in a form layout
    - Read-only by default
    - Fields organized into logical groups (identifying info, type info, type-specific properties)
    - FK references displayed as clickable links showing the referenced record's name
    - Clicking an FK link navigates the tree to that record
    - **Related Records section** below the form: collapsible groups of records that reference the selected record via FK back-references, with counts and clickable entries

12. **Editing** (`browser/record_editor.py` + `fk_selector.py`) implements Section 14.8.3:
    - "Edit" button switches the form to edit mode
    - Editable fields become type-constrained input controls:
      - String → text input
      - Enum → dropdown
      - Boolean → checkbox
      - Integer → number input
      - FK → searchable dropdown (`fk_selector.py`) populated from the referenced table
    - Read-only fields (id, created_at, updated_at, created_by_session_id) remain non-editable even in edit mode
    - "Save" button commits changes
    - "Cancel" button reverts to original values and returns to read-only mode

13. **Pre-Commit Impact Analysis** (in `browser/record_editor.py`) implements Section 14.8.4:
    - On Save click, call `impact.analyze_proposed_change(table_name, record_id, change_type="update", new_values=...)`
    - If impact set is empty, write the change immediately and show a brief confirmation
    - If impact set is non-empty, show `PrecommitConfirmDialog` with the impacts
    - On confirmation with rationale, open a transaction and write: the UPDATE, ChangeLog entries, ChangeImpact rows (with `action_required=FALSE` initially)
    - On cancellation, no data is written and the form stays in edit mode with the administrator's changes preserved
    - Wrap the write in `automation.db.connection.transaction(conn)`

14. **Record Deletion** (in `browser/record_editor.py`) implements Section 14.8.5:
    - "Delete" button initiates deletion
    - Call `impact.analyze_proposed_change(table_name, record_id, change_type="delete")`
    - Transitive tracing is enabled for deletes (this is an impact engine behavior, not a UI flag)
    - PrecommitConfirmDialog shows a stronger warning message: "Deleting this record will affect {N} downstream records. This action cannot be undone."
    - Orphaned child records are listed in the impact set; the application does NOT cascade-delete them
    - On confirmation with rationale, write the DELETE, ChangeLog entries, and ChangeImpact rows in a single transaction

15. **Record Creation** (`browser/record_creator.py`) implements Section 14.8.6:
    - "New Record" button at the top of the record detail area
    - Creates a new record in the currently selected table (inferred from tree selection)
    - Form appears in edit mode with all fields empty except schema defaults
    - FK fields that can be inferred from tree context are pre-populated (e.g., creating a new Field while "Contact" entity is selected pre-populates `entity_id=Contact.id`)
    - **Inserts are exempt from pre-commit impact analysis** per Section 12.2 — write directly with ChangeLog entries, no ChangeImpact rows
    - Still wrap in `transaction(conn)`

16. **Audit Trail Access** (`browser/audit_trail.py`) implements Section 14.8.7:
    - "History" button opens a collapsible panel below the form
    - Shows ChangeLog entries for the selected record
    - Each entry: timestamp, change type, field name, old value, new value, rationale, source (AISession name or "Direct Edit")
    - Ordered by timestamp descending

17. **Navigation from Other Views** (Section 14.8.8):
    - The `impact_table.py` widget from Step 15b has a clickable link in each impact row for "affected record identifier"
    - Wire these links to navigate to the Data Browser and select the target record in the tree
    - Similarly, foreign key references in Import Review proposed records (Step 15b `proposed_record_widget.py`) should link to existing records in the Data Browser
    - **These wiring changes require minor modifications to Step 15b files** — this is authorized for Step 15c

### Section 14.9 — Integration with Existing Panels

18. **Mode Boundary** (Section 14.9.1) is implicit — Requirements mode covers Phases 1–9, Deployment mode covers Phases 10–12. No code required; Steps 15a/15b already separate the two modes via the mode selector.

19. **Transition from Requirements to Deployment** (`mode_integration/deployment_guidance.py`) implements Section 14.9.2:
    - For work items of type `crm_deployment`, `crm_configuration`, or `verification`, the Work Item Detail view displays a guidance message explaining that the work is performed in Deployment mode
    - The Mark Complete action remains available for administrator confirmation that the external work succeeded
    - Modify `work_item/detail_view.py` to show this guidance when the work item is one of these three types
    - The guidance message can be a banner at the top of the detail area, or a highlighted section in the header

20. **Instance Association** (`mode_integration/instance_association.py`) implements Section 14.9.3:
    - Pure-Python logic that given a Client record's `crm_platform` value, finds the matching instance profile from the existing Instance panel data source
    - Pure-Python logic that given an instance profile, finds the matching Client record
    - Tested without Qt
    - Reads the existing instance profiles from `espo_impl/` — you will need to identify the module that exposes them. Flag as an ambiguity if the structure is unclear.

21. **Mode Transition Auto-Select** (in `espo_impl/ui/main_window.py`):
    - When switching from Deployment mode to Requirements mode, if the currently selected instance has a matching Client record, auto-select that client
    - When switching from Requirements mode to Deployment mode, if the currently selected client has a `crm_platform` and a matching instance profile exists, auto-select that instance
    - The administrator can override the auto-selection manually in either mode
    - This is a small modification to `main_window.py` — reuse `mode_integration/instance_association.py` for the lookup logic

22. **Output Panel Availability** (Section 14.9.4): the Output panel is not displayed in Requirements mode. No code required — Step 15a's mode swap already handles this because the Requirements mode container does not include the Output panel.

23. **YAML File Handoff** (Section 14.9.5): no code required. The Document Generator writes YAML files to `programs/` in the project folder, and the existing Program panel reads from the same directory. The handoff is implicit.

24. **Post-Deployment Feedback** (Section 14.9.6): no new code required. This section describes a workflow that uses the Data Browser (Section 14.8) for post-deployment changes. The Data Browser implemented in this step is the primary mechanism. No special handling needed.

### Wiring updates

25. **`requirements_window.py`** is updated:
    - "Documents" sidebar entry no longer a placeholder — opens DocumentsView
    - "Data Browser" sidebar entry no longer a placeholder — opens BrowserView

26. **`work_item/header_actions.py`** is updated:
    - The `generate_document` action handler pushes DocumentsView scoped to the current work item instead of showing a toast

27. **`work_item/tab_documents.py`** is updated:
    - The "Generate Document" action on the tab navigates to DocumentsView scoped to the current work item

28. **`work_item/detail_view.py`** is updated:
    - Shows deployment guidance message (from `mode_integration/deployment_guidance.py`) when work item type is `crm_deployment`, `crm_configuration`, or `verification`

29. **`dashboard/staleness_summary.py`** is updated:
    - Placeholder toast replaced with real navigation to DocumentsView filtered to stale documents

30. **`espo_impl/ui/main_window.py`** is updated:
    - Mode transition hooks call `instance_association.py` helpers to auto-select the associated client/instance

31. **Step 15b files modified for Data Browser navigation**:
    - `automation/ui/impact/shared_presentation.py` or `impact_table.py` — "affected record identifier" link navigates to Data Browser
    - `automation/ui/importer/proposed_record_widget.py` — FK reference links navigate to Data Browser for existing records

### Universal requirements

32. **PySide6 imports stay isolated to widget modules.** Pure-logic modules (`documents_logic.py`, `generation_logic.py`, `browser_logic.py`, `tree_model.py`, `instance_association.py`, `mode_transition.py`) must not import PySide6.

33. **The Data Browser is the only place in the UI that writes directly to the database** (besides the Step 15b ChangeImpact review state writes). All writes use `transaction(conn)` and create ChangeLog entries.

34. **Engine state transitions still go through `header_actions.py`** (and `impact_view.py` for the Reopen for Revision action). Step 15c does NOT add new `engine.start/complete/revise/block/unblock` call sites.

35. **No HTTP / API calls.** Option B integration is preserved.

36. **All tests pass:** `uv run pytest automation/tests/ -v`. Target: 953 existing + new logic tests, no failures.

37. **Linter clean:** `uv run ruff check automation/`

38. **Application launches:** `uv run crmbuilder` opens the application. Doug verifies manually:
    - Clicking "Documents" in the Requirements sidebar opens the Documents view with the document inventory
    - Clicking "Data Browser" opens the Data Browser with the tree and an empty detail area
    - Selecting a tree node shows the record detail
    - Clicking "Generate Document" on a Work Item Detail header opens the Documents view scoped to that work item
    - The staleness summary link on the Dashboard navigates to the Documents view

## Working Style

- **Read Sections 14.7, 14.8, and 14.9 of the L2 PRD before writing any UI code.** Section 14.8 is the largest single screen in the application — read it carefully, especially 14.8.4 (pre-commit impact analysis on edits) and 14.8.5 (deletion with transitive tracing).
- **Read the existing `automation/ui/` package** to understand Steps 15a and 15b conventions. Match them.
- **Read `automation/docgen/generator.py` and `automation/impact/engine.py`** to understand the engine APIs you're calling.
- **Read `espo_impl/`** to understand the instance profile data structure for Section 14.9.3. Do not modify espo_impl code except for `main_window.py`.
- **Implement in this order:** documents/ → browser/ → mode_integration/. Within each, do the pure-logic modules first, then the widgets. Data Browser is the biggest piece; expect it to take the most time.
- **Write tests alongside each pure-logic module.**
- **Surface ambiguities, do not invent answers.** Examples to flag rather than guess:
  - Where does the `project_folder` path come from for `DocumentGenerator` construction? The L2 PRD implies it comes from the instance profile, but Step 15a's client context may not expose it yet.
  - Section 14.8 doesn't explicitly address whether the Client table (in the master database) is editable through the Data Browser. Decide and document.
  - Section 14.8.5 says "Referential integrity enforcement for whether the delete is permitted before orphaned references are resolved is implementation-specific." What does the SQLite schema actually enforce? Does `ON DELETE CASCADE` or `ON DELETE RESTRICT` exist anywhere in `client_schema.py`?
  - The `espo_impl/` instance profile data structure is not documented in the prompt. Read the existing code to find the right entry point.
  - The Data Browser edit flow writes ChangeImpact rows with `action_required=FALSE` initially, but the user is deciding to make this change, so should `action_required` actually be `TRUE`? Read Section 14.6.2 to see how Flag for Revision semantically relates to direct edits.
- **Do not modify Steps 9–14.** Do not modify Step 15a/15b code except where explicitly listed in the "Wiring updates" section.
- **Do not pull in pytest-qt.** Test pure-Python logic only.
- **No HTTP calls.**

## Out of Scope for Step 15c

- CBM integration testing — Step 16
- Modifying any code in Steps 9–14
- Modifying Step 15a/15b code except the listed wiring updates
- New engine state transition call sites outside `header_actions.py` and `impact_view.py`
- Pulling in pytest-qt
- HTTP / API calls
- Modifying existing `espo_impl/` panels beyond the main_window.py mode transition hooks

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 14.7** — Document Generation View (entire section)
- **Section 14.8** — Data Browser (entire section, especially 14.8.4 and 14.8.5)
- **Section 14.9** — Integration with Existing Panels (entire section)
- **Section 14.10** — Common UI Patterns (re-read as needed)
- **Section 13** — Document Generator API
- **Section 12.5** — Pre-commit impact analysis flow
- **Section 12.2** — Insert operations exempt from impact analysis

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches
- [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/ui/` returns zero matches
- [ ] `grep -rn "PySide6" automation/ui/documents/documents_logic.py automation/ui/documents/generation_logic.py automation/ui/browser/browser_logic.py automation/ui/browser/tree_model.py automation/ui/mode_integration/instance_association.py automation/ui/mode_integration/mode_transition.py` returns zero matches (logic modules are Qt-free)
- [ ] `grep -rn "engine\.start\|engine\.complete\|engine\.block\|engine\.unblock" automation/ui/` returns matches only in `header_actions.py`
- [ ] `grep -rn "engine\.revise" automation/ui/` returns matches only in `header_actions.py` and `impact/impact_view.py`
- [ ] `grep -rn "coming in Step 15c" automation/ui/` returns zero matches (all Step 15c placeholders from 15a/15b are now real)
- [ ] All items in the Definition of Done are met
- [ ] All tests pass (target: 953 + new logic tests, no failures)
- [ ] Linter is clean
- [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, or `automation/docgen/` was modified
- [ ] Step 15a/15b code modified only in the "Wiring updates" section's listed files
- [ ] The Documents and Data Browser sidebar entries are no longer placeholders
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in Sections 14.7–14.9 and how you resolved them are documented in your final report

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.
