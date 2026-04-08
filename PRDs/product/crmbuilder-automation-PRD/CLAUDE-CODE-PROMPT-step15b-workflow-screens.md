# Claude Code Implementation Prompt — Step 15b: Workflow Screens

## Context

You are implementing **Step 15b of the CRM Builder Automation roadmap** — the second of three sub-steps that together implement the User Interface (Section 14 of the L2 PRD).

- **Step 15a (complete)** — Schema bump for ISS-012, mode integration, Project Dashboard, Work Item Detail, Common UI Patterns. Doug verified the application launches and the basic navigation works.
- **Step 15b (this prompt)** — Workflow screens: Session Orchestration (14.4), Import Review (14.5), Impact Analysis Display (14.6).
- **Step 15c (later prompt)** — Reference screens and integration: Document Generation (14.7), Data Browser (14.8), Integration with Existing Panels (14.9).

The complete design is in the Level 2 PRD at `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`.

**Read Sections 14.4, 14.5, and 14.6 of the L2 PRD before writing any UI code.** Also re-read Section 14.10 (Common UI Patterns) — the patterns it defines apply across all of Step 15b. Step 15a already implemented the common widgets (status badges, action badges, severity indicators, staleness indicators, readable_first formatting, confirmation dialog, error display, toast notifications, loading state). Step 15b reuses these.

This is step 15b of 16. Steps 9–14 + 15a are complete with **882 tests passing**.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. **Read the existing Step 15a code in `automation/ui/`** before writing anything new — your code must follow the same conventions Claude Code established there:

- Pure-logic modules separate from Qt widgets (`navigation.py`, `client_context.py`, `dashboard_logic.py`, `work_item_logic.py` are Qt-free)
- Common widgets in `automation/ui/common/`
- Drill-down stack and breadcrumb logic in `automation/ui/navigation.py`
- Shared dataclasses for screen state (e.g., `WorkItemRow`, `ProjectSummary` in `dashboard_logic.py`)

The Step 15a placeholder toasts in `header_actions.py` will be replaced by real navigation calls in this step. Look for `show_toast(self, "...coming in Step 15b")` calls and replace them with proper drill-down stack pushes.

## Where the Code Goes

Three new directories under `automation/ui/`, each parallel to the existing `dashboard/` and `work_item/` directories:

```
automation/
└── ui/
    ├── session/                       # NEW — Section 14.4 Session Orchestration
    │   ├── __init__.py
    │   ├── session_view.py            # The session orchestration container
    │   ├── session_logic.py           # Pure-Python data assembly (NO Qt)
    │   ├── pre_generation.py          # 14.4.1 — pre-generation configuration
    │   ├── prompt_display.py          # 14.4.3 — sectioned prompt display
    │   └── session_history.py         # 14.4.5 — previous sessions panel
    ├── importer/                      # NEW — Section 14.5 Import Review
    │   ├── __init__.py
    │   ├── import_view.py             # The import review container
    │   ├── import_logic.py            # Pure-Python state machine (NO Qt)
    │   ├── progress_indicator.py      # 14.5.1 — 7-stage progress bar
    │   ├── stage_receive.py           # 14.5.2 — Stage 1: paste JSON
    │   ├── stage_parse.py             # 14.5.3 — Stage 2: parse error display
    │   ├── stage_review.py            # 14.5.5 — Stage 5: proposed record review
    │   ├── proposed_record_widget.py  # Single proposed record card
    │   ├── stage_commit.py            # 14.5.6 — Stage 6: commit confirmation
    │   └── stage_trigger.py           # 14.5.7 — Stage 7: trigger results
    └── impact/                        # NEW — Section 14.6 Impact Analysis Display
        ├── __init__.py
        ├── impact_view.py             # The Impact Review sidebar view (14.6.5)
        ├── impact_logic.py            # Pure-Python data assembly (NO Qt)
        ├── shared_presentation.py     # 14.6.1 — shared format used in 4 contexts
        ├── review_actions.py          # 14.6.2 — No Action Needed / Flag for Revision
        ├── bulk_review.py             # 14.6.3 — bulk review controls
        └── precommit_confirm.py       # 14.6.4 — pre-commit confirmation dialog
```

The `impact/shared_presentation.py` module is the **single source of truth** for the impact row presentation format used in four places per Section 14.6:
1. Import Review trigger stage (Section 14.5.7) — used by `importer/stage_trigger.py`
2. Work Item Detail Impacts tab (Section 14.3.7) — used by `work_item/tab_impacts.py` (already exists from Step 15a as a placeholder; you will wire it up)
3. Data Browser pre-commit confirmation (Section 14.8) — used by `impact/precommit_confirm.py`
4. Impact Review sidebar view (Section 14.6.5) — used by `impact/impact_view.py`

The `precommit_confirm.py` module is the dialog that the Data Browser will invoke in Step 15c. It is implemented now so that the impact display logic is complete and tested in this step. Step 15c will plug it in.

### Tests

```
automation/tests/
├── test_ui_session_logic.py          # Pure-logic tests for session view assembly
├── test_ui_import_logic.py           # Pure-logic tests for import state machine
└── test_ui_impact_logic.py           # Pure-logic tests for impact assembly and review actions
```

Same convention as Step 15a — test the pure-logic helpers thoroughly, leave Qt widgets for manual inspection.

## Foundation — Existing API Surface

### Step 15a UI conventions (read these first)

```
automation/ui/__init__.py
automation/ui/requirements_window.py    # the mode container — you may need to add navigation hooks
automation/ui/navigation.py             # drill-down stack (READ-ONLY for this step)
automation/ui/client_context.py         # client state (READ-ONLY for this step)
automation/ui/common/                   # all common widgets (READ-ONLY for this step)
automation/ui/dashboard/                # reference for module structure conventions
automation/ui/work_item/                # the screens that push your new views onto the stack
```

Pay particular attention to:
- `automation/ui/work_item/header_actions.py` — currently has placeholder toasts for `generate_prompt`, `run_import`, `view_impact_analysis`. Replace these with real drill-down pushes onto the navigation stack.
- `automation/ui/work_item/tab_impacts.py` — currently a placeholder. Wire it up to use `impact/shared_presentation.py` and `impact/review_actions.py`.
- `automation/ui/common/` — reuse the existing widgets. Do not create new versions of status badges, severity indicators, confirmation dialogs, etc. If a new common widget is needed, add it to `common/` and document why.

### Engines

```python
from automation.prompts.generator import PromptGenerator
from automation.importer.pipeline import ImportProcessor
from automation.impact.engine import ImpactAnalysisEngine
from automation.workflow.engine import WorkflowEngine
```

These are the engines you call. Note their important properties:

**PromptGenerator** (`automation/prompts/generator.py`):
- `generate(work_item_id, session_type='initial', revision_reason=None, clarification_topic=None) -> str`
- Returns the assembled prompt text and creates an AISession row with `import_status='pending'`
- Validates that the work item is in `ready` or `in_progress` status; raises ValueError otherwise
- The session orchestration view's "Generate Prompt" button calls this

**ImportProcessor** (`automation/importer/pipeline.py`):
- Six staged methods for the seven-stage pipeline:
  - `receive(work_item_id, raw_text) -> ai_session_id` (Stage 1)
  - `parse(ai_session_id) -> envelope_dict` (Stage 2)
  - `map(ai_session_id) -> ProposedBatch` (Stage 3)
  - `detect_conflicts(batch) -> ProposedBatch` (Stage 4)
  - `commit(ai_session_id, batch, accepted_record_ids=None) -> CommitResult` (Stage 6)
  - `trigger(ai_session_id, commit_result) -> TriggerResult` (Stage 7)
- Plus `run_full_import(work_item_id, raw_text, accept_all=True) -> ImportResult` for tests
- Step 15b uses the staged methods because the UI is interactive — Stage 5 (Review) requires administrator action between detect_conflicts and commit
- The `accepted_record_ids` parameter on `commit()` is a set of `source_payload_path` strings identifying which proposed records the administrator accepted. Pass `None` to accept all (default behavior).

**ImpactAnalysisEngine** (`automation/impact/engine.py`):
- `analyze_session(ai_session_id) -> AnalysisResult` — used by Stage 7 trigger display
- `analyze_pending_sessions() -> list[AnalysisResult]` — bulk consume IMPACT_ANALYSIS_NEEDED markers
- `analyze_proposed_change(table_name, record_id, change_type, new_values=None, rationale=None) -> list[ProposedImpact]` — used by `precommit_confirm.py`
- `get_affected_work_items(change_impact_ids) -> list[AffectedWorkItem]` — used by Impact Review sidebar
- `get_stale_work_items() -> list[StaleWorkItem]` — used by dashboard and Impact Review sidebar

**WorkflowEngine** (`automation/workflow/engine.py`):
- `revise(work_item_id) -> list[int]` — called from Impact Review sidebar's "Reopen for Revision" action. Note: per ISS-013, the engine does **not** accept a revision reason. The reason is collected by the UI for display purposes and passed to PromptGenerator at prompt-generation time, not to the engine. Store the reason temporarily in client_context or a similar place so the next call to PromptGenerator can use it.

### Database — `automation.db.connection`

```python
from automation.db.connection import connect, transaction
```

Step 15b's UI is mostly read-only, with all writes delegated to the engines (Importer's commit, ImpactAnalysisEngine's review action updates). The one direct UI write is the impact review actions (`reviewed`, `action_required`, `reviewed_at` columns on ChangeImpact) — these can be done directly from `impact/review_actions.py` since they don't involve any cross-record logic, but **wrap them in `transaction()`**.

## Definition of Done — Session Orchestration (Section 14.4)

1. **Session view container** (`session/session_view.py`):
   - Pushed onto the drill-down stack from `work_item/header_actions.py` when the administrator clicks "Generate Prompt"
   - Breadcrumb extends to show "Dashboard > {Work Item Name} > Generate Prompt"
   - Receives the work item id and session type (initial, revision, clarification) at construction
   - Uses `pre_generation.py` for the configuration step, then transitions to `prompt_display.py` after generation

2. **Pre-generation configuration** (`session/pre_generation.py`) implements Section 14.4.1:
   - For **initial sessions**: displays work item name, type, phase. Single "Generate Prompt" button.
   - For **revision sessions**: displays the revision reason (read from client_context or wherever it was stored when the administrator clicked "Reopen for Revision"; if none stored, prompts for one now). Editable text field for change instructions. "Generate Prompt" button.
   - For **clarification sessions**: editable text field for the question/topic. "Generate Prompt" button.

3. **Prompt generation** (Section 14.4.2):
   - Calls `PromptGenerator.generate(work_item_id, session_type, revision_reason=..., clarification_topic=...)`
   - Synchronous, with a brief loading indicator (use `common/loading.py`)
   - On success, transitions to the prompt display
   - On failure, shows an error using `common/error_display.py`
   - **Stale guide warning**: if PromptGenerator returns a placeholder for a missing guide (per ISS handling in Step 11), display the warning per Section 14.4.2 — administrator can continue or cancel

4. **Prompt display** (`session/prompt_display.py`) implements Section 14.4.3:
   - Six collapsible panels, one per prompt section (Session Header, Session Instructions, Context, Locked Decisions, Open Issues, Structured Output Specification)
   - Each panel header shows section name and **estimated token count** (compute as words × 1.3 — same heuristic as `automation/prompts/context_size.py`)
   - All panels collapsed by default
   - Above the panels: summary bar with **total estimated token count**, context window percentage consumed (assume 200K context for Claude 4.6 Opus), and any reduction strategies applied (read these from the prompt's HTML comment markers that `automation/prompts/generator.py` appends — see `pipeline.py` line 220-222 of generator.py)
   - **The prompt parsing logic** (splitting the prompt text into 6 sections, extracting reduction strategy comments, counting tokens) goes in `session_logic.py` as pure Python, not in the Qt widget

5. **Copy to clipboard + return** (Section 14.4.4):
   - Prominent "Copy to Clipboard" button above the section panels
   - Visual confirmation on click (label changes to "Copied" briefly)
   - "Return to Work Item" link below the copy button — pops the drill-down stack

6. **Session history panel** (`session/session_history.py`) implements Section 14.4.5:
   - Visible when the work item has prior AISession records
   - Shows the same session list as `work_item/tab_sessions.py` but scoped to this work item
   - Reuses any pure-logic helpers from `tab_sessions.py` if available; otherwise extract them into `session_logic.py`

7. **Pure-logic separation** (`session/session_logic.py`):
   - Token counting helper
   - Prompt section splitter (6 sections from a single text block)
   - Reduction strategy extractor (parses the HTML comment markers)
   - Estimated context window percentage calculator
   - All functions are Qt-free and unit-tested in `test_ui_session_logic.py`

8. **Header actions integration**: replace the placeholder toast in `work_item/header_actions.py` for the `generate_prompt` action with a real drill-down push that creates and shows a `SessionView`.

## Definition of Done — Import Review (Section 14.5)

9. **Import view container** (`importer/import_view.py`):
   - Pushed onto the drill-down stack from `work_item/header_actions.py` when the administrator clicks "Import Results"
   - Breadcrumb extends to show "Dashboard > {Work Item Name} > Import Review"
   - Stages are shown as a horizontal progress indicator at the top per Section 14.5.1
   - Stage content area below the progress indicator
   - "Cancel Import" action available at every stage before Commit; cancels and pops the drill-down stack

10. **Pipeline progress indicator** (`importer/progress_indicator.py`) implements Section 14.5.1:
    - Seven horizontal pill widgets: Receive, Parse, Map, Detect, Review, Commit, Trigger
    - Current stage highlighted; completed stages show a checkmark
    - Use the established palette colors (`#1F3864` for active, `#F2F7FB` for completed background)

11. **Stage 1 — Receive** (`importer/stage_receive.py`) implements Section 14.5.2:
    - Large QPlainTextEdit with placeholder "Paste the JSON output from your AI session"
    - "Parse" button below
    - If the AISession already has `raw_output` from a previous attempt, show a notification offering to reload (administrator accepts → text area populated; dismisses → starts fresh)
    - Empty input: inline error message; Parse button stays available

12. **Stage 2 — Parse** (`importer/stage_parse.py`) implements Section 14.5.3:
    - Calls `ImportProcessor.parse(ai_session_id)`
    - On success: auto-advance to Stage 3
    - On failure: display the parser error inline below the progress indicator. Show line/character position for syntax errors. Highlight the relevant portion of the pasted text if possible.
    - Administrator can edit the text area and retry, or cancel

13. **Stages 3 and 4 — Map and Detect** (Section 14.5.4):
    - These stages run automatically with no administrator interaction
    - Brief loading indicator showing "Mapping payload to records..." then "Detecting conflicts..."
    - On error: display the error and offer cancel
    - On success: transition to Stage 5

14. **Stage 5 — Review** (`importer/stage_review.py`) implements Section 14.5.5 — this is the largest UI component in Step 15b:
    - Proposed records grouped by category, in this order: domains, entities, personas, fields, field options, relationships, process steps, requirements, cross-references (ProcessEntity, ProcessField, ProcessPersona), layout records (panels, rows, tabs, list columns), decisions, open issues
    - Each category is a collapsible group with header showing category name + count
    - Categories with zero proposed records are omitted (do not display empty groups)
    - Per-category "Accept All" and "Reject All" buttons
    - Each proposed record rendered by `proposed_record_widget.py` (see #15)
    - Fixed summary bar at the bottom: counts (accepted, modified, rejected, unresolved error-severity conflicts) + Commit button
    - Commit button: if unresolved error-severity conflicts exist, clicking shows an explanatory message identifying the unresolved items rather than proceeding (per Section 11.11.1)

15. **Proposed record widget** (`importer/proposed_record_widget.py`):
    - Action badge ("Create" or "Update") using `common/action_badges.py`
    - Key identifying fields displayed prominently (name + code + table)
    - Field values in tabular layout
    - For updates: changed fields highlighted with current value vs. proposed value side by side; unchanged fields visually subdued
    - Conflict indicators using `common/severity_indicators.py` if Detect flagged this record
    - Dependency indicator if this record is referenced by other proposed records in the same batch
    - Three action controls: Accept (default), Modify, Reject
    - Modify switches to inline edit mode with editable inputs; "Accept with Changes" or "Cancel Edit"
    - Modified records show a "Modified" badge
    - Rejected records visually dimmed and moved to bottom of category group
    - Cascade warning when rejecting a record that has dependents in the batch — administrator can cascade-reject or cancel

16. **Import state machine** (`importer/import_logic.py`) — pure Python:
    - Tracks the current stage (Receive, Parse, Map, Detect, Review, Commit, Trigger, Done)
    - Tracks per-record acceptance state (accepted/modified/rejected) and modified field values
    - Computes accepted_record_ids set to pass to `ImportProcessor.commit()`
    - Detects unresolved error-severity conflicts
    - Computes cascade-reject sets for dependent records
    - Tested in `test_ui_import_logic.py` without Qt

17. **Stage 6 — Commit** (`importer/stage_commit.py`) implements Section 14.5.6:
    - Confirmation dialog showing final counts (create, update, reject) and any remaining warnings
    - On confirm: call `ImportProcessor.commit(ai_session_id, batch, accepted_record_ids=...)` with a loading indicator
    - On commit failure: display the error identifying the specific record/field; offer retry or cancel
    - On success: display commit results (ChangeLog count, AISession import_status, work item status transition)

18. **Stage 7 — Trigger** (`importer/stage_trigger.py`) implements Section 14.5.7:
    - Calls `ImportProcessor.trigger(ai_session_id, commit_result)`
    - Displays each trigger as it runs (graph construction, work item completion, downstream recalc, revision unblocking, impact analysis) with a checkmark on completion
    - For impact analysis: show the count of ChangeImpact records created and use `impact/shared_presentation.py` to render them
    - On trigger failure: display the failure, confirm committed data is preserved, offer retry
    - "Return to Work Item" link at the bottom — pops the drill-down stack

19. **Header actions integration**: replace the placeholder toast in `work_item/header_actions.py` for `run_import` with a real drill-down push that creates and shows an `ImportView`.

## Definition of Done — Impact Analysis Display (Section 14.6)

20. **Shared impact presentation** (`impact/shared_presentation.py`) implements Section 14.6.1:
    - Single function/widget that takes a list of ChangeImpact records and renders them in the standard format
    - Impact rows grouped by affected table, then split into "Requires Review" and "Informational" within each group
    - Requires Review impacts first with standard visual weight; informational impacts below in subdued styling
    - Each impact row displays: affected record identifier as a clickable link (clicks navigate to Data Browser — placeholder for Step 15c, show a toast for now), impact description, source change summary, review status indicator (for post-commit contexts)
    - Summary header: total count, requires review count, informational count, already reviewed count

21. **Review actions** (`impact/review_actions.py`) implements Section 14.6.2:
    - For records with `requires_review = TRUE`: two buttons — "No Action Needed" and "Flag for Revision"
    - For records with `requires_review = FALSE`: single "Acknowledge" button
    - All three actions update the ChangeImpact row in the database:
      - **No Action Needed** → `reviewed = TRUE`, `action_required = FALSE`, `reviewed_at = CURRENT_TIMESTAMP`
      - **Flag for Revision** → `reviewed = TRUE`, `action_required = TRUE`, `reviewed_at = CURRENT_TIMESTAMP`
      - **Acknowledge** → `reviewed = TRUE`, `action_required = FALSE`, `reviewed_at = CURRENT_TIMESTAMP`
    - All updates wrapped in `transaction(conn)`
    - **The action_required column was added in Step 15a (ISS-012)** so this code can rely on its existence

22. **Bulk review** (`impact/bulk_review.py`) implements Section 14.6.3:
    - Bulk action bar above each table group with multiple unreviewed impacts
    - "Mark All — No Action Needed" button (applies to requires_review impacts)
    - "Mark All — Acknowledge" button (applies to informational impacts)
    - Individual actions override bulk

23. **Pre-commit confirmation dialog** (`impact/precommit_confirm.py`) implements Section 14.6.4:
    - Modal dialog (or push onto drill-down stack — your choice based on what fits the existing pattern)
    - Receives a list of ProposedImpact objects from `ImpactAnalysisEngine.analyze_proposed_change()`
    - Renders the impacts using `shared_presentation.py` with the review status column omitted
    - Required rationale text field below the impact set (required when impact set is non-empty per Section 12.5.3)
    - "Confirm" and "Cancel" buttons
    - On confirm: returns the rationale to the caller (Step 15c's Data Browser will use this to write the change + ChangeLog + ChangeImpact in a single transaction)
    - On cancel: discards
    - Empty impact set: displays "No downstream records are affected by this change" and the rationale field is optional
    - Summary header: "This change affects {N} downstream records across {M} tables."
    - **Step 15b implements this dialog but does not yet have a caller** — the Data Browser in Step 15c will plug it in. Test it with a hand-built ProposedImpact list.

24. **Impact Review sidebar view** (`impact/impact_view.py`) implements Section 14.6.5:
    - Accessible from the sidebar (the "Impact Review" entry placeholder in `requirements_window.py` from Step 15a)
    - Two sections arranged vertically: **Unresolved Changes** at top, **Flagged Work Items** below

    **Unresolved Changes section:**
    - Lists all change sets with at least one unreviewed ChangeImpact record
    - A change set = ChangeImpact records sharing the same triggering transaction (common session_id for imports; common changed_at + null session_id for direct edits)
    - Each change set entry: change source (AI session type + work item name, or "Direct Edit"), timestamp, summary of what changed, counts of unreviewed and total impacts
    - Expanding a change set reveals the full impact set using `shared_presentation.py` with review actions from `review_actions.py`
    - When all impacts in a set are reviewed, the set moves to a collapsible "Resolved Changes" area at the bottom (or removed entirely — your choice for now, document the decision)
    - Empty state: "All changes have been reviewed."

    **Flagged Work Items section:**
    - ChangeImpact records where `action_required = TRUE`, grouped by affected work item per Section 12.8.1 mapping
    - Each entry: work item name (human-readable-first), count of flagged impacts, summary of flagged impact descriptions, revision eligibility per Section 12.8.2
    - For eligible (complete) work items: "Reopen for Revision" action available
    - Reopen for Revision: prompts for a revision reason (pre-populated with a summary of the flagged impacts) and optional change instructions, calls `WorkflowEngine.revise(work_item_id)`. Store the reason in client_context (or wherever) so the next PromptGenerator call can use it (per ISS-013, the engine itself does not store the reason).
    - For non-eligible work items: show the reason and recommended action
    - Empty state: "No work items are flagged for revision."

25. **Wire Impact Review sidebar entry**: in `automation/ui/requirements_window.py`, replace the "Impact Review" placeholder with an `ImpactView` instance.

26. **Wire Work Item Detail Impacts tab**: replace the placeholder in `work_item/tab_impacts.py` with real content. The tab uses `shared_presentation.py` and `review_actions.py` to display ChangeImpact records where this work item is the affected item (the reverse direction from Section 12.8.1).

27. **Header actions integration**: there is no "View Impact Analysis" header action — the Impacts tab on Work Item Detail is the entry point. The placeholder toast in `header_actions.py` for `view_impact_analysis` should be removed (it should never have existed; verify against Section 14.3.3).

## Definition of Done — Cross-Cutting

28. **Pure-logic modules are Qt-free.** Verify with `grep`:
    - `automation/ui/session/session_logic.py` — zero PySide6 imports
    - `automation/ui/importer/import_logic.py` — zero PySide6 imports
    - `automation/ui/impact/impact_logic.py` — zero PySide6 imports

29. **All multi-row writes use `transaction()`.** Specifically the impact review actions in `impact/review_actions.py`.

30. **The UI never modifies workflow state directly.** All state transitions go through `WorkflowEngine`. The UI calls `engine.revise()` for the Reopen for Revision action; everything else flows through engine methods.

31. **The UI never bypasses the engines.** Importer uses `ImportProcessor`; impact analysis uses `ImpactAnalysisEngine`. No raw SQL for these operations from UI code (the only exception is the impact review actions in #29 which are simple ChangeImpact column updates that have no engine method).

32. **No HTTP / API calls.** Option B integration preserved.

33. **No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, or `espo_impl/` is modified.** Steps 9–14 + 15a are locked. The only files in `automation/ui/` that you modify are:
    - `requirements_window.py` (wire the Impact Review sidebar entry)
    - `work_item/header_actions.py` (replace placeholder toasts with real drill-down pushes)
    - `work_item/tab_impacts.py` (replace placeholder with real impact display)

    All other Step 15a UI files are read-only references.

34. **pytest test suite** with **tests written alongside each pure-logic module**. Coverage requirements:
    - `test_ui_session_logic.py`: token counting, prompt section splitting, reduction strategy extraction, context window percentage calculation
    - `test_ui_import_logic.py`: state machine transitions, accepted_record_ids computation, unresolved error detection, cascade-reject computation
    - `test_ui_impact_logic.py`: change set grouping by session_id, work item mapping, review status computation, eligibility computation
    - All tests use real SQLite databases via `run_client_migrations()`, never mocks
    - Qt widgets do not need automated tests — Doug verifies manually

35. **All tests pass**: `uv run pytest automation/tests/ -v`. Target: 882 existing + new logic tests, no failures.

36. **Linter clean**: `uv run ruff check automation/`

37. **Application launches and the new screens work end-to-end** when Doug runs `uv run crmbuilder` after pulling. Doug will verify manually:
    - Click a work item → Work Item Detail
    - Click Generate Prompt → Session Orchestration view appears
    - Generate a prompt for a real work item → prompt displays in 6 collapsible sections
    - Copy to clipboard → confirmation appears
    - Return to Work Item → drill-down stack pops correctly
    - Click Import Results → Import Review view appears
    - Paste a JSON block → progress through the 7 stages
    - Stage 5 review → accept/modify/reject records, see conflict indicators
    - Commit → see commit results and trigger results
    - Click Impact Review in sidebar → unresolved changes and flagged work items appear
    - Review actions on impacts → status updates persist

## Working Style

- **Read Sections 14.4, 14.5, and 14.6 of the L2 PRD before writing any code.** Section 14.5.5 (Stage 5 Review) is the longest single subsection in Step 15b — read it carefully, the proposed record widget is the most complex component.
- **Read the existing Step 15a code in `automation/ui/`** to understand the conventions Claude Code established. Match them exactly.
- **Read the engine APIs in Steps 11, 12, 13** (`automation/prompts/`, `automation/importer/`, `automation/impact/`) to understand exactly what each method returns and what parameters it accepts.
- **Write tests alongside each pure-logic module**, not at the end.
- **Implement in this order**: impact/ (shared_presentation, review_actions, precommit_confirm, impact_view) → session/ (logic, view, prompt_display) → importer/ (logic, view, all stages, proposed_record_widget). Impact comes first because it's used by importer's Stage 7. Session comes second because it's the simplest of the three. Importer is last because it's the largest and depends on the impact display for Stage 7.
- **Surface ambiguities, do not invent answers.** Examples:
  - Section 14.4.3 mentions "Priority 4 content omitted" but Step 11 only documented Priority tiers 1, 2, and 3. Verify against `automation/prompts/context_size.py` and document the discrepancy.
  - Section 14.6.5 says resolved change sets either move to a "Resolved Changes" area or are removed entirely. Pick one, document the choice in your final report.
  - The Data Browser pre-commit confirmation dialog (`precommit_confirm.py`) needs to be implemented in Step 15b but has no caller until Step 15c. Test it with a hand-built ProposedImpact list, and document how Step 15c will plug it in.
  - For the revision reason flow (per ISS-013), the reason is collected at "Reopen for Revision" but stored where? Pick a sensible location (client_context, a new in-memory cache, or a dedicated field) and document.
- **Do not modify Steps 9–14 code or Step 15a code outside the explicit allowlist** in #33.
- **Do not pull in pytest-qt.** Test pure-logic only.
- **No HTTP / API calls.**

## Out of Scope for Step 15b

- Document Generation view (Section 14.7) — Step 15c
- Data Browser (Section 14.8) — Step 15c (the precommit_confirm dialog is implemented but not called)
- Integration with existing Deployment panels beyond what Step 15a already added (Section 14.9) — Step 15c
- Modifying any code in Steps 9–14
- Modifying Step 15a code outside the allowlist in #33
- Pulling in pytest-qt or running widget tests
- HTTP / API calls

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 14.4** — Session Orchestration (entire section)
- **Section 14.5** — Import Review Interface (entire section, especially 14.5.5)
- **Section 14.6** — Impact Analysis Display (entire section)
- **Section 14.10** — Common UI patterns (re-read; everything Step 15a established)
- **Section 10** — Prompt Generator API
- **Section 11** — Import Processor API (especially 11.4 Review and 11.6 Partial Import)
- **Section 12** — Impact Analysis Engine API (especially 12.4 ChangeImpact, 12.6 Impact Presentation, 12.7 Review Tracking)

You may find these useful for context but **do not implement them in Step 15b**:
- **Section 14.7** — Document Generation view (Step 15c)
- **Section 14.8** — Data Browser (Step 15c)

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "PySide6" automation/ui/session/session_logic.py automation/ui/importer/import_logic.py automation/ui/impact/impact_logic.py` returns zero matches (logic modules are Qt-free)
- [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/ui/` returns zero matches (Option B integrity preserved)
- [ ] `grep -rn "engine\.revise\|engine\.complete\|engine\.start\|engine\.block\|engine\.unblock" automation/ui/` returns matches only in `header_actions.py` and `impact/impact_view.py` (revise from Reopen for Revision action)
- [ ] `grep -rn "show_toast.*coming in Step 15b" automation/ui/` returns zero matches (all 15b placeholders replaced)
- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches (Step 9 fix verified, no regression)
- [ ] All items in the Definition of Done are met
- [ ] All tests pass (target: 882 existing + new logic tests, no failures)
- [ ] Linter is clean
- [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, or `espo_impl/` was modified
- [ ] No Step 15a UI code modified outside the allowlist in #33
- [ ] Application launches without errors after pulling
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in Sections 14.4–14.6 and how you resolved them are documented in your final report

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.
