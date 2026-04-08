# Claude Code Implementation Prompt — Step 15c: Document Generation, Data Browser, Existing Panel Integration

## Context

You are implementing **Step 15c of the CRM Builder Automation roadmap** — the third and final sub-step of the User Interface (Section 14 of the L2 PRD). Steps 15a and 15b are complete:

- **Step 15a (complete)** — Schema bump for ISS-012, mode integration, Project Dashboard, Work Item Detail, Common UI Patterns
- **Step 15b (complete)** — Workflow screens: Session Orchestration (14.4), Import Review (14.5), Impact Analysis Display (14.6), plus the 15b cleanup (tab_sessions navigation, gitignore, and an incidental bug fix in `_on_navigate_to_session`)
- **Step 15c (this prompt)** — Document Generation View (14.7), Data Browser (14.8), Integration with Existing Panels (14.9)

After Step 15c completes, the automation roadmap has one remaining step: Step 16 (CBM integration testing with end-to-end validation).

The complete design is in the Level 2 PRD at `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`.

**Read Sections 14.7, 14.8, and 14.9 of the L2 PRD before writing any UI code.** Section 14.8 (Data Browser) is the largest single screen in Step 15c — read 14.8.1 through 14.8.8 carefully. Also re-read Section 14.10 if you need to remind yourself of the common UI patterns established in Step 15a.

This is step 15c of 16. Steps 9 (database), 10 (workflow), 11 (prompts), 12 (importer), 13 (impact analysis), 14 (docgen), 15a (UI scaffolding), and 15b (workflow screens) are complete with **953 tests passing**.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. **Read the existing `automation/ui/` package** before starting — Steps 15a and 15b established conventions you must follow:

- `automation/ui/requirements_window.py` — the mode container with sidebar and drill-down stack. The "Documents" and "Data Browser" sidebar entries are currently placeholders — this step replaces them with real views.
- `automation/ui/navigation.py` — pure-Python drill-down stack and breadcrumb logic
- `automation/ui/client_context.py` — client selection state
- `automation/ui/common/` — shared widgets (status badges, toasts, confirmation dialogs, etc.). Reuse these.
- `automation/ui/impact/precommit_confirm.py` — **the pre-commit confirmation dialog built during Step 15b but not yet wired up. Step 15c's Data Browser is its caller.** Look at its API before implementing Data Browser save handling.
- `automation/ui/impact/shared_presentation.py` — the Section 14.6.1 shared impact display used in four contexts. Step 15c reuses it for Data Browser pre-commit confirmation (Section 14.6.4).
- `automation/ui/work_item/header_actions.py` — the action handlers from Steps 15a and 15b. The `generate_document` action currently shows a placeholder toast — Step 15c replaces it with a real navigation push to the Document Generation View.

Also read `espo_impl/ui/main_window.py` again — Step 15c's integration with existing panels (Section 14.9) mostly relies on the mode selector already in place from Step 15a. The only change is auto-selecting the instance/client when switching modes (Section 14.9.3).

## Where the Code Goes

Three new sub-packages within `automation/ui/`, parallel to the existing `session/`, `importer/`, and `impact/` directories:

```
automation/
└── ui/
    ├── documents/                    # NEW — Section 14.7 Document Generation View
    │   ├── __init__.py
    │   ├── documents_view.py         # The main document generation container
    │   ├── documents_logic.py        # Pure-Python inventory assembly, staleness filter (Qt-free)
    │   ├── inventory.py              # 14.7.1 — document inventory list
    │   ├── document_row.py           # Single document entry widget with actions
    │   ├── staleness_display.py      # 14.7.2 — staleness summary widget
    │   ├── generation_flow.py        # 14.7.4 — step-by-step generation progress
    │   └── batch_regeneration.py     # 14.7.5 — multi-select and batch controls
    ├── data_browser/                 # NEW — Section 14.8 Data Browser (largest screen)
    │   ├── __init__.py
    │   ├── browser_view.py           # The main data browser container (tree + detail split)
    │   ├── browser_logic.py          # Pure-Python tree assembly, FK resolution (Qt-free)
    │   ├── nav_tree.py               # 14.8.1 — navigation tree widget
    │   ├── record_detail.py          # 14.8.2 — record detail form widget
    │   ├── form_fields.py            # Type-specific input controls for edit mode
    │   ├── related_records.py        # 14.8.2 — Related Records section
    │   ├── editing.py                # 14.8.3 — edit mode orchestration
    │   ├── precommit_handler.py      # 14.8.4 — calls ImpactAnalysisEngine + PrecommitConfirmDialog
    │   ├── deletion.py               # 14.8.5 — delete flow with transitive trace
    │   ├── creation.py               # 14.8.6 — new record creation
    │   └── audit_trail.py            # 14.8.7 — ChangeLog history panel
    └── integration/                  # NEW — Section 14.9 Existing Panel Integration
        ├── __init__.py
        ├── mode_association.py       # Pure-Python: client ↔ instance association logic
        ├── deployment_guidance.py    # 14.9.2 — guidance message widgets for Deployment-executed work items
        └── output_panel_hiding.py    # 14.9.4 — hook to hide Output panel in Requirements mode
```

Plus updates to existing files:

```
automation/ui/work_item/header_actions.py    # MODIFY: replace "coming in Step 15c" toast for generate_document with navigation
automation/ui/work_item/detail_view.py       # MODIFY: wire crm_deployment/crm_configuration/verification work items to show guidance
automation/ui/requirements_window.py         # MODIFY: wire Documents and Data Browser sidebar entries; register mode-switch hooks
espo_impl/ui/main_window.py                  # MODIFY: auto-select instance/client on mode switch (Section 14.9.3); hide Output in Requirements mode (Section 14.9.4)
```

The changes to `espo_impl/ui/main_window.py` are the second time we're touching that file (first time was the Step 15a mode selector). Keep the changes surgical. Read the Step 15a commit (`38c58bd`) to see the existing pattern before modifying.

### Tests

```
automation/tests/
├── test_ui_documents_logic.py        # Pure-logic tests for documents_logic.py
├── test_ui_documents_view.py         # Light import-and-construct tests
├── test_ui_data_browser_logic.py     # Pure-logic tests for browser_logic.py (tree assembly, FK resolution)
├── test_ui_data_browser_view.py      # Light import-and-construct tests
├── test_ui_data_browser_precommit.py # Integration test: edit → precommit → impact detection → confirm
├── test_ui_integration_logic.py      # Pure-logic tests for mode_association.py
└── test_ui_integration_view.py       # Light import-and-construct tests
```

Same testing strategy as Steps 15a and 15b: pure-Python helpers get unit tests, Qt widgets get "imports cleanly" tests. Doug verifies UI behavior manually.

## Foundation — Existing API Surface

### Document Generator — `automation.docgen.generator`

```python
from automation.docgen.generator import DocumentGenerator

generator = DocumentGenerator(
    conn=client_conn,
    master_conn=master_conn,
    project_folder=project_folder_path,
)

# Single generation
result = generator.generate(work_item_id, mode="final")  # or mode="draft"

# Batch generation
results = generator.generate_batch(work_item_ids, mode="final")

# Query stale documents
stale = generator.get_stale_documents()

# Optional push after commit
success = generator.push()
```

`generate()` returns a `GenerationResult` dataclass with `file_path` (or `file_paths` for multi-file YAML), `error`, `warnings`, `git_commit_hash`, and `generation_log_id` fields. Read `automation/docgen/generator.py` and `automation/docgen/pipeline.py` to confirm the exact result shape before wiring the view.

`get_stale_documents()` returns a list of `StaleDocument` dataclass instances with `work_item_id`, `item_type`, `last_generated_at`, `latest_change_at`, `change_count`, and `change_summary` fields. This is what drives the Document Inventory's staleness display.

### Impact Analysis Engine — `automation.impact.engine`

```python
from automation.impact.engine import ImpactAnalysisEngine

impact_engine = ImpactAnalysisEngine(conn)

# Pre-commit analysis for direct edits (Data Browser's core flow)
proposed_impacts = impact_engine.analyze_proposed_change(
    table_name="Field",
    record_id=42,
    change_type="update",  # or "delete"
    new_values={"label": "Client Status", "field_type": "enum"},
    rationale=None,  # will be collected in the UI
)
```

The `analyze_proposed_change()` method returns a list of `ProposedImpact` objects without writing anything to the database. The Data Browser presents these via `PrecommitConfirmDialog` (Step 15b) and, on confirm, writes the change + ChangeLog + ChangeImpact rows in a single transaction.

**Important — the write after confirmation is not yet implemented in `automation.impact.precommit`.** Step 13 built `analyze_proposed_change()` but left the actual commit step as a TODO because Step 15 was too far away to know the UI contract. You will likely need to add a companion method like `impact_engine.commit_proposed_change(table_name, record_id, change_type, new_values, rationale, proposed_impacts)` or write the commit logic in `data_browser/precommit_handler.py` directly, using `transaction(conn)`.

**Look at `automation/impact/precommit.py` first** to see what exists. If a commit method exists with the right signature, use it. If not, implement the write in `data_browser/precommit_handler.py` and document the deviation clearly.

### Workflow Engine — `automation.workflow.engine`

```python
from automation.workflow.engine import WorkflowEngine

engine = WorkflowEngine(conn)
status = engine.get_status(work_item_id)  # for determining generatable state
```

The Document Generation View checks work item status to determine which generation mode is available (complete → final; in_progress → draft; others → neither). It does not call workflow state transitions.

The Data Browser does not call the Workflow Engine — all database mutations go through `ImpactAnalysisEngine` (for pre-commit analysis) or direct writes through `transaction(conn)` (for inserts which are exempt from impact analysis per Section 12.2).

### Schema — `automation.db.client_schema`

Read `automation/db/client_schema.py` for exact column names. The Data Browser's record detail form reads and writes essentially every table — Domain, Entity, Field, FieldOption, Relationship, Persona, Process, ProcessStep, Requirement, ProcessEntity, ProcessField, ProcessPersona, LayoutPanel, LayoutRow, LayoutTab, ListColumn, Decision, OpenIssue, BusinessObject. You do not need to hand-code forms for every table — a generic form renderer that reads column types from `PRAGMA table_info` is the right approach, with optional table-specific overrides for tables that need special handling.

## Definition of Done

### Section 14.7 — Document Generation View

1. **Document Generation View** (`documents/documents_view.py`) is accessible from two entry points:
   - The "Documents" sidebar entry in Requirements mode — shows all documents across the project
   - The Generate Document action on the Work Item Detail header — filtered to a single work item, with a "Show All Documents" toggle

2. **Document Inventory** (`documents/inventory.py` + `document_row.py`) implements Section 14.7.1:
   - Lists every work item that produces a generated document
   - Grouped by the 8 document types from Section 13.2
   - Each entry shows: document name (human-readable-first), work item status badge, document status (not generated / current / stale / draft only), most recent final generation timestamp, output file path
   - **Sort:** stale documents at the top, then current, then draft only, then not generated (Section 14.7.2)
   - Queries `DocumentGenerator.get_stale_documents()` for the staleness data and the GenerationLog table for current/draft-only/not-generated classification

3. **Staleness indicators** (`documents/staleness_display.py`) implements Section 14.7.2:
   - For stale documents, show a summary below the document entry: count of ChangeLog entries post-dating the most recent final generation, brief description of what changed
   - Expandable to show the individual ChangeLog entries
   - The change description can be assembled from the ChangeImpact and ChangeLog data

4. **Generation actions** per document entry implement Section 14.7.3:
   - **Generate Final** — available when work item is complete; runs `DocumentGenerator.generate(mode="final")`
   - **Generate Draft** — available when work item is in_progress; runs `DocumentGenerator.generate(mode="draft")`
   - For other statuses, clicking shows an explanatory message per Section 14.10.6 (buttons-never-disabled)

5. **Generation flow** (`documents/generation_flow.py`) implements Section 14.7.4:
   - Displays the 6-step pipeline progress inline below the document entry
   - Steps: Querying database → Validating data → Rendering → Writing file → (final only: Committing to git → Recording generation)
   - On validation warnings, pauses and presents them; administrator can proceed or cancel
   - On completion, shows the result panel with output file path, validation warnings, git commit hash
   - "Open File" action opens the file in the system default application
   - "Push to Remote" action offers optional git push

6. **Batch regeneration** (`documents/batch_regeneration.py`) implements Section 14.7.5:
   - Checkbox on each document entry for multi-selection
   - "Regenerate Selected" button appears when ≥1 document is selected
   - "Select All Stale" shortcut
   - Sequential processing through `DocumentGenerator.generate_batch()`
   - Batch progress indicator shows current document
   - On validation warning, pauses on that document; administrator proceeds or skips
   - Batch summary at the end: generated successfully, skipped, failed
   - Optional git push offered once after all commits
   - **Final generation only** — draft is a single-document preview action

### Section 14.8 — Data Browser

7. **Data Browser view** (`data_browser/browser_view.py`) is accessible from the "Data Browser" sidebar entry. It is independent of the drill-down stack (cross-cutting view).

8. **Navigation tree** (`data_browser/nav_tree.py`) implements Section 14.8.1:
   - Left-side tree panel organized by FK hierarchy:
     - Domains → processes → process steps, requirements, cross-references
     - Entities → fields → field options; entities → relationships, layout records
     - Personas (flat list)
     - Decisions (flat list, sortable by identifier)
     - Open Issues (flat list, sortable by identifier)
   - Sub-domains nest under parent; services (`is_service = TRUE`) in a separate "Services" branch
   - Each node shows record name in human-readable-first format with a count badge on expandable nodes (e.g., "Contact (14 fields)")
   - Search field above the tree that filters by name, code, or identifier as the administrator types

9. **Record detail** (`data_browser/record_detail.py`) implements Section 14.8.2:
   - Selecting a tree node displays the record's detail in the main area
   - Form layout with logical groups (identifying info, type info, type-specific properties for Field records)
   - Read-only by default
   - Foreign key references display as clickable links showing the referenced record's name (resolved via a lookup helper — **put this in `browser_logic.py`** so it's Qt-free and testable)
   - Clicking a FK link navigates the tree to that record

10. **Related Records section** (`data_browser/related_records.py`) implements Section 14.8.2 trailing paragraphs:
    - Below the form, lists records that reference the selected record via foreign keys
    - Grouped by target table (e.g., a Process shows related ProcessSteps, Requirements, ProcessEntity, ProcessField, ProcessPersona)
    - Collapsible groups with record counts
    - Each related record is clickable and navigates the tree to it

11. **Editing** (`data_browser/editing.py` + `form_fields.py`) implements Section 14.8.3:
    - "Edit" button switches the form to edit mode
    - Editable fields become input controls constrained by type: text inputs for strings, dropdowns for enums, checkboxes for booleans, number inputs for integers
    - Foreign key references use searchable dropdowns populated with records from the referenced table
    - Read-only fields: `id`, `created_at`, `updated_at`, `created_by_session_id`
    - "Save" button triggers the pre-commit flow
    - "Cancel" reverts and returns to read-only mode
    - Use a generic form renderer driven by `PRAGMA table_info` rather than hand-coding per-table forms. Table-specific overrides (if any) go in a small dispatch dict.

12. **Pre-commit impact analysis** (`data_browser/precommit_handler.py`) implements Section 14.8.4:
    - On Save, call `ImpactAnalysisEngine.analyze_proposed_change(table, record_id, "update", new_values)`
    - If the impact set is empty, proceed immediately — write the change and ChangeLog entries in a single transaction, show a brief confirmation, return to read-only mode
    - If the impact set is non-empty, open `PrecommitConfirmDialog` (from `automation/ui/impact/precommit_confirm.py`) and display the impact set
    - The dialog requires a rationale text field (Section 14.6.4)
    - On confirm, write the data change + ChangeLog entries + ChangeImpact records in a single transaction (use `transaction(conn)`)
    - On cancel, no data is written, the record stays in edit mode with changes preserved

13. **Record deletion** (`data_browser/deletion.py`) implements Section 14.8.5:
    - "Delete" button triggers pre-commit impact analysis with `change_type="delete"` (transitive tracing per Section 12.3)
    - Modal dialog follows the same format as edit confirmation but with a stronger warning: "Deleting this record will affect {N} downstream records. This action cannot be undone."
    - For records with child records through FK (e.g., entity with fields), lists the child records that will be orphaned
    - Does NOT cascade-delete — the administrator addresses orphans as part of impact review
    - On confirm, write the delete + ChangeLog + ChangeImpact in a single transaction

14. **Record creation** (`data_browser/creation.py`) implements Section 14.8.6:
    - "New Record" button creates a new record in the currently selected table (inferred from tree selection)
    - Form appears in edit mode with empty fields (except schema defaults)
    - FK fields inferable from tree context are pre-populated (e.g., creating a new Field while the Contact entity node is selected pre-populates `entity_id` with Contact's id)
    - **Inserts are exempt from impact analysis per Section 12.2** — the record is written directly with ChangeLog entries on save
    - No pre-commit confirmation dialog for new records

15. **Audit trail access** (`data_browser/audit_trail.py`) implements Section 14.8.7:
    - "History" button opens a collapsible panel showing ChangeLog entries for the selected record
    - Each entry shows: timestamp, change type, field name, old value, new value, rationale, source (AISession name or "Direct Edit")
    - Ordered by timestamp descending
    - Read-only display

16. **Navigation from other views** implements Section 14.8.8:
    - The affected record identifier links in `automation/ui/impact/shared_presentation.py` should navigate to the Data Browser and select the target record (currently they show a placeholder toast per Step 15b — replace it with real navigation)
    - Foreign key references in the Import Review's proposed record display (from `automation/ui/importer/proposed_record_widget.py`) can also link to the Data Browser for existing records — if this was left as a placeholder in Step 15b, wire it; if it was implemented, confirm it still works

### Section 14.9 — Integration with Existing Panels

17. **Mode boundary clarity** (`integration/deployment_guidance.py`) implements Section 14.9.2:
    - When the administrator selects a `crm_deployment`, `crm_configuration`, or `verification` work item on the Dashboard, the Work Item Detail view displays a guidance message explaining that the work is performed in Deployment mode
    - The guidance message appears at the top of the detail area, above the header actions
    - The Mark Complete action is still available once the administrator has finished the deployment/configuration/verification externally
    - This is a new widget added to `work_item/detail_view.py` that shows conditionally based on item_type

18. **Instance association** (`integration/mode_association.py`) implements Section 14.9.3:
    - When switching from Requirements mode to Deployment mode, look up the client's `Client.crm_platform` field and find the matching instance profile in the existing instance storage (read `espo_impl/` to find the instance profile location and format)
    - If a matching instance exists, auto-select it in the Instance panel
    - When switching from Deployment mode to Requirements mode, do the reverse — look up the instance's `project_folder` field and auto-select the matching client
    - Implement the association logic as a pure-Python function in `mode_association.py` that takes client metadata and instance metadata and returns a match. Test it thoroughly.
    - Wire the function into the mode selector in `espo_impl/ui/main_window.py`. The wiring is small (~20 lines in main_window.py).

19. **Output panel hiding** (`integration/output_panel_hiding.py`) implements Section 14.9.4:
    - In Requirements mode, the Output panel is not displayed
    - In Deployment mode, the Output panel is displayed as currently implemented
    - The mode selector in `main_window.py` already swaps content containers via QStackedWidget — this step just ensures the Output panel is inside the Deployment container and not visible in Requirements mode
    - If the Output panel is currently a top-level panel that sits below the mode content, the mode selector may need to hide/show it explicitly

20. **YAML file handoff** (Section 14.9.5) — **no code changes required.** The Document Generator (Step 14) already writes YAML files to `programs/{entity_name}.yaml` in the project folder. The existing Program panel already reads from that directory. The handoff works automatically. Document this in your final report.

21. **Post-deployment feedback** (Section 14.9.6) — **no new code required.** The existing Data Browser (implemented in this step) and revision workflow (from Steps 10 and 15a) already provide the post-deployment feedback loop. Document this in your final report.

### Wiring updates

22. **`work_item/header_actions.py`** is updated:
    - The `generate_document` action handler pushes the Document Generation View (scoped to the current work item) instead of showing a toast
    - No other changes

23. **`work_item/detail_view.py`** is updated:
    - Shows the deployment guidance message widget (from `integration/deployment_guidance.py`) at the top of the detail area when the work item is `crm_deployment`, `crm_configuration`, or `verification`
    - No changes to the existing header, tabs, or actions for other item types

24. **`requirements_window.py`** is updated:
    - The "Documents" sidebar entry is no longer a placeholder — it opens the Document Generation View in sidebar mode (all documents)
    - The "Data Browser" sidebar entry is no longer a placeholder — it opens the Data Browser view
    - The mode-switch hook for instance association (Section 14.9.3) is wired to the mode selector

25. **`espo_impl/ui/main_window.py`** is updated:
    - Mode switch triggers the instance association logic from `integration/mode_association.py`
    - Output panel is hidden in Requirements mode and shown in Deployment mode (Section 14.9.4)
    - Keep all changes surgical — read the existing structure first before modifying

26. **`automation/ui/impact/shared_presentation.py`** is updated:
    - The "affected record identifier" link action navigates to the Data Browser instead of showing a placeholder toast (Section 14.6.1 / 14.8.8). If this was already a real navigation call in Step 15b (not a toast), confirm it still works; if it was a placeholder, wire it.

### Universal requirements

27. **PySide6 imports stay isolated to widget modules.** Pure-logic modules (`documents/documents_logic.py`, `data_browser/browser_logic.py`, `integration/mode_association.py`) must not import PySide6. Final-check grep enforces this.

28. **All multi-row writes use `transaction()`.** The Data Browser's commit flow writes the data change + ChangeLog + ChangeImpact records (if any) in a single transaction. Inserts write the record + ChangeLog in a single transaction.

29. **Engine delegation calls (`engine.start`, `complete`, `revise`, `block`, `unblock`)** still appear ONLY in `header_actions.py` and `impact/impact_view.py`. Step 15c does not add any new engine state transitions.

30. **No HTTP / API calls.** Option B integration is preserved.

31. **The Output panel hiding is the only modification to existing `espo_impl/` panels** beyond what Step 15a already did. Specifically, you are NOT modifying Instance panel, Program panel, Deploy panel, Deploy Wizard, or any other existing UI component beyond the main_window.py mode selector.

32. **All tests pass:** `uv run pytest automation/tests/ -v`. Target: 953 existing + new tests, no failures.

33. **Linter clean:** `uv run ruff check automation/`

34. **Application launches:** `uv run crmbuilder` opens the application without crashing. Doug verifies manually: the Documents sidebar entry opens the document inventory; the Data Browser sidebar entry opens the tree + detail split view; clicking a record shows its detail; clicking Edit allows modification; saving a change with downstream impacts shows the pre-commit dialog; switching modes auto-selects the instance/client association.

## Working Style

- **Read Sections 14.7, 14.8, and 14.9 of the L2 PRD before writing any UI code.** Section 14.8 in particular — it has the most subsections and the most complex behavior.
- **Read existing Step 9–15b code** to understand the engine APIs and UI conventions. The Data Browser's pre-commit flow is similar to the Import Review's Stage 5 Review flow (Step 15b) — study that as a reference.
- **Read `automation/impact/precommit.py`** to understand what the existing pre-commit API provides. If the commit-after-confirmation step is missing, document it clearly in your final report and implement the write path either in `impact/precommit.py` (if a small extension) or in `data_browser/precommit_handler.py` (if UI-specific). Your call; document the decision.
- **Read `espo_impl/ui/main_window.py`** before modifying it. The Step 15a mode selector added ~62 lines to this file. Step 15c adds maybe another 30–50 lines for the instance association and Output panel hiding. Keep it surgical.
- **Write tests alongside each pure-logic module.**
- **Implement in this order:** documents/ → data_browser/ → integration/. Each is independent except that the Data Browser's pre-commit handler uses the PrecommitConfirmDialog from Step 15b.
- **Surface ambiguities, do not invent answers.** Examples to flag rather than guess:
  - The Data Browser's generic form renderer — how to handle table-specific quirks (e.g., Layout table's dependency on sort_order within a panel, or Decision/OpenIssue's scope fields that may be multiple tables)? Start with a generic approach and document tables that need special handling.
  - Section 14.8.5 says "Referential integrity enforcement for whether the delete is permitted before orphaned references are resolved is implementation-specific." This is the PRD giving you license to choose. Pick a strategy (recommendation: allow the delete, flag the orphans as impact items, let the administrator resolve them through subsequent edits) and document the choice.
  - Section 14.9.3 instance profile lookup — where does the existing CRM Builder store instance profiles? Read `espo_impl/` to find out. If the storage format is not structured for easy matching, document the gap.
  - The YAML program file naming convention — `programs/{entity_name}.yaml`. Is `entity_name` the lowercased name, the code, or the raw name? Match what `automation/docgen/queries/yaml_program.py` and `automation/docgen/templates/yaml_program_template.py` already produce.
- **Do not modify Steps 9–14.** Do not modify Step 15a or 15b code except as listed in the "Wiring updates" section.
- **Do not modify any existing `espo_impl/` panels** beyond the main_window.py integration points.
- **Do not pull in pytest-qt.** Test pure-Python logic only.
- **No HTTP calls.**

## Out of Scope for Step 15c

- Step 16: CBM integration testing with end-to-end validation
- Modifying any code in Steps 9–14
- Modifying Step 15a or 15b code except the listed wiring updates
- Modifying existing `espo_impl/` Instance/Program/Deploy/Output panels beyond the main_window.py integration points
- Pulling in pytest-qt
- HTTP / API calls
- New migrations or schema changes

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 14.7** — Document Generation View (entire section)
- **Section 14.8** — Data Browser (entire section — 8 subsections)
- **Section 14.9** — Integration with Existing Panels (entire section)
- **Section 14.10** — Common UI Patterns (re-read)
- **Section 13** — Document Generator backend (the API your view calls)
- **Section 12.5** — Pre-commit analysis flow (what the Data Browser triggers)
- **Section 12.6.4** — Pre-commit confirmation presentation

You may find these useful for context but are not implementing them in Step 15c:
- **Section 16.13 (ISS-013)** — Revision reason collection timing (handled in Step 15b)
- **Section 16.14 (ISS-014)** — Stale guide detection (deferred to future work)

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches
- [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/ui/` returns zero matches
- [ ] `grep -rn "PySide6" automation/ui/documents/documents_logic.py automation/ui/data_browser/browser_logic.py automation/ui/integration/mode_association.py` returns zero matches (logic modules are Qt-free)
- [ ] `grep -rn "engine\.start\|engine\.complete\|engine\.block\|engine\.unblock" automation/ui/` returns matches only in `header_actions.py` (no new state transitions in 15c)
- [ ] `grep -rn "engine\.revise" automation/ui/` returns matches only in `header_actions.py` and `impact/impact_view.py` (unchanged from Step 15b)
- [ ] `grep -rn "coming in Step 15" automation/ui/` returns zero matches (all placeholders removed)
- [ ] All items in the Definition of Done are met
- [ ] All tests pass (target: 953 + new tests, no failures)
- [ ] Linter is clean
- [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/` (except possibly the precommit commit extension), `automation/docgen/`, or existing `espo_impl/` panels was modified beyond the listed wiring updates
- [ ] The "Documents" and "Data Browser" sidebar entries in `requirements_window.py` are no longer placeholders
- [ ] The `generate_document` action in `header_actions.py` is no longer a placeholder
- [ ] Mode switching auto-selects the matching instance/client where an association exists
- [ ] Output panel is hidden in Requirements mode
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in Sections 14.7–14.9 and how you resolved them are documented in your final report

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.
