# Claude Code Implementation Prompt — Step 15a: Schema Bump + UI Scaffolding

## Context

You are implementing **Step 15a of the CRM Builder Automation roadmap** — the first of three sub-steps that together implement the User Interface (Section 14 of the L2 PRD). Step 15 is the largest section in the L2 PRD with 10 main subsections and ~50 nested subsections, so it has been split into three sub-prompts:

- **Step 15a (this prompt)** — Schema bump for ISS-012, plus UI scaffolding: mode integration (Section 14.1), Project Dashboard (Section 14.2), Work Item Detail (Section 14.3).
- **Step 15b (later prompt)** — Workflow screens: Session Orchestration (14.4), Import Review (14.5), Impact Analysis Display (14.6).
- **Step 15c (later prompt)** — Reference screens and integration: Document Generation (14.7), Data Browser (14.8), Integration with Existing Panels (14.9), Common UI Patterns (14.10).

The complete design is in the Level 2 PRD at `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`.

**Read Sections 14.1, 14.2, 14.3, and 14.10 of the L2 PRD before writing any UI code.** Section 14.10 (Common UI Patterns) is essential because it defines status badges, action badges, conflict severity indicators, staleness indicators, the human-readable-first display rule, the "buttons never disabled" rule, confirmation prompts, error and warning presentation, toast notifications, loading states, and the client context indicator. These patterns apply across all of Step 15 — read them now.

This is step 15 of 16. Steps 9 (database), 10 (workflow), 11 (prompts), 12 (importer), 13 (impact analysis), and 14 (docgen) are complete with 797 tests passing.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. **The existing CRM Builder application lives in `espo_impl/`.** Read it before writing any UI code:

- `espo_impl/main.py` — application entry point
- `espo_impl/main_window.py` — main window class (if it exists; otherwise look for the equivalent)
- `espo_impl/panels/` (or wherever the existing Instance/Program/Deploy/Output panels live)

The L2 PRD says the new Requirements mode panels live alongside the existing Deployment mode panels. **You must not modify the existing panels** — they are the working CRM Builder deployment workflow and have their own state. Your job is to add a new mode and a new set of panels, plus a mode selector that lets the administrator switch between modes.

## Where the Code Goes

This step has two distinct concerns: a schema bump and the UI scaffolding. **Make these two separate commits** so each can be reviewed independently.

### Schema bump (commit 1)

The change goes in the existing `automation/db/` package. This is the **only** time we are modifying Step 9's locked code, and it is justified because Section 12.11 explicitly defers this column to Step 15 and ISS-012 documents the deferral.

```
automation/
└── db/
    ├── client_schema.py    # ADD: action_required column to ChangeImpact CREATE TABLE
    └── migrations.py       # ADD: a new migration that ALTERs ChangeImpact for existing databases
```

### UI scaffolding (commit 2)

A new top-level package for the Requirements mode panels. The existing `espo_impl/` package is touched only minimally — to add the mode selector and to register the new mode.

```
automation/
└── ui/                              # NEW
    ├── __init__.py
    ├── requirements_window.py       # The Requirements mode container (sidebar + content area)
    ├── client_context.py            # Client selection state and context propagation
    ├── navigation.py                # Drill-down stack and breadcrumb logic
    ├── common/                      # Section 14.10 — shared widgets and patterns
    │   ├── __init__.py
    │   ├── status_badges.py         # 14.10.1 — status badge widget
    │   ├── action_badges.py         # 14.10.2 — action badge widget
    │   ├── severity_indicators.py   # 14.10.3 — conflict severity indicators
    │   ├── staleness_indicators.py  # 14.10.4 — staleness indicators
    │   ├── readable_first.py        # 14.10.5 — human-readable-first formatting helpers
    │   ├── confirmation.py          # 14.10.7 — confirmation prompt dialog
    │   ├── error_display.py         # 14.10.8 — error and warning presentation
    │   ├── toast.py                 # 14.10.9 — toast notifications
    │   ├── loading.py               # 14.10.10 — loading state widgets
    │   └── client_indicator.py      # 14.10.11 — client context indicator widget
    ├── dashboard/                   # Section 14.2 — Project Dashboard
    │   ├── __init__.py
    │   ├── dashboard_view.py        # The dashboard container
    │   ├── summary_bar.py           # 14.2.1 — project summary bar
    │   ├── work_queue.py            # 14.2.2 — actionable work queue (Continue Work + Ready)
    │   ├── inventory.py             # 14.2.3 — full project inventory grouped by phase
    │   ├── filters.py               # 14.2.4 — filter controls
    │   └── staleness_summary.py     # 14.2.6 — staleness summary banner
    └── work_item/                   # Section 14.3 — Work Item Detail
        ├── __init__.py
        ├── detail_view.py           # The work item detail container
        ├── header.py                # 14.3.2 — header content
        ├── header_actions.py        # 14.3.3 — header action buttons
        ├── tab_dependencies.py      # 14.3.4 — Dependencies tab
        ├── tab_sessions.py          # 14.3.5 — Sessions tab (read-only display)
        ├── tab_documents.py         # 14.3.6 — Documents tab (read-only display)
        └── tab_impacts.py           # 14.3.7 — Impacts tab (read-only display)
```

Plus the integration into the existing application:

```
espo_impl/
├── main_window.py                   # MODIFY: add mode selector at top
└── (any new files needed for mode switching, kept minimal)
```

The existing Instance/Program/Deploy/Output panels are **not modified**. Only the main window receives a mode selector, and the mode selector swaps the content area between the existing panels (Deployment mode) and the new Requirements mode container.

### Tests

```
automation/tests/
├── test_ui_schema_migration.py      # Verifies the action_required column migration
├── test_ui_navigation.py            # Drill-down stack and breadcrumb logic (no Qt widgets)
├── test_ui_client_context.py        # Client context state (no Qt widgets)
├── test_ui_dashboard_logic.py       # Dashboard data assembly logic (no Qt widgets)
└── test_ui_work_item_logic.py       # Work item detail action availability logic (no Qt widgets)
```

**UI code testing strategy:** Most logic should live in pure-Python helper functions and classes that can be tested without Qt. The Qt widgets should be thin layers that bind data to display. Test the helpers thoroughly and leave the Qt widget integration for manual inspection. Do not pull in pytest-qt for this step — it adds complexity and the headless environment doesn't reliably support widget testing. Instead, write your code so the testable parts are separable from the Qt parts.

For modules that combine logic and Qt heavily (e.g., the dashboard view), at minimum write a test that imports the module to verify it compiles and that PySide6 imports work. The actual widget behavior is for Doug to verify by running the application.

## Foundation — Existing API Surface

### Database — `automation.db.connection`

```python
from automation.db.connection import connect, transaction
```

Same pattern as Steps 9–14. The UI is mostly read-only against the database, with workflow transitions delegated to the WorkflowEngine.

### Workflow Engine — `automation.workflow.engine`

```python
from automation.workflow.engine import WorkflowEngine

engine = WorkflowEngine(conn)
engine.start(work_item_id)              # Start Work action
engine.complete(work_item_id)           # Mark Complete action
engine.revise(work_item_id, reason)     # Reopen for Revision action
engine.block(work_item_id, reason)      # Block action
engine.unblock(work_item_id)            # Unblock action
engine.get_status(work_item_id)
engine.get_phase_for(work_item_id)
engine.get_available_work()             # Drives the Continue Work + Ready queues
```

These methods exist and are tested. Your UI calls them — you do not implement workflow transitions yourself.

### Other engines

You will need to import these for read-only data display (their write operations are owned by Step 15b):

```python
from automation.prompts.generator import PromptGenerator       # Step 15b uses
from automation.importer.pipeline import ImportProcessor       # Step 15b uses
from automation.impact.engine import ImpactAnalysisEngine      # this step reads
from automation.docgen.generator import DocumentGenerator      # Step 15c uses
```

For Step 15a specifically, you only need direct interaction with `WorkflowEngine` and the database; the other engines are queried only to display historical/summary data on tabs.

### Phase mapping

```python
from automation.workflow.phases import get_phase, get_phase_name
```

Use this for the dashboard's full project inventory grouping by phase (Section 14.2.3).

### Schema — `automation.db.client_schema`

Read `automation/db/client_schema.py` for exact column names. Read `automation/db/migrations.py` to understand the existing migration pattern before writing the new one.

## Definition of Done — Schema Bump (Commit 1)

1. **`automation/db/client_schema.py`** is modified to add `action_required BOOLEAN NOT NULL DEFAULT FALSE` to the `ChangeImpact` CREATE TABLE statement. The column goes after `reviewed_at` and before the FOREIGN KEY clause. New databases created from scratch will have this column.

2. **A new migration** is added to `automation/db/migrations.py` that ALTERs the existing ChangeImpact table to add the column. SQLite supports `ALTER TABLE ChangeImpact ADD COLUMN action_required INTEGER NOT NULL DEFAULT 0`. Use INTEGER with 0/1 values since SQLite stores BOOLEAN as INTEGER. The migration must be idempotent — running it twice should not error.

3. **The migration is registered** in the migration runner so existing client databases get the column automatically on next open.

4. **Migration test** (`test_ui_schema_migration.py`) verifies:
   - A fresh database created via `run_client_migrations()` has the column
   - An old database created without the column gets the column added when migrations are re-run
   - The column has the correct default (0/FALSE)
   - Running migrations twice does not error

5. **No other changes to existing Step 9 code.** Specifically, do not modify any other column, do not modify any other table, do not add any other migrations.

6. **Schema version** in the schema_version table is bumped per the existing migration convention. Read the migration runner first to confirm how versioning works.

7. **Existing 797 tests still pass.** The Step 13 impact engine has tests that may need to be updated if they check ChangeImpact column count or schema; if so, update the tests to include the new column. Do not modify the impact engine code itself.

8. **Linter clean.**

9. **Commit 1 message:**

```
Bump ChangeImpact schema with action_required column (ISS-012)

Adds action_required BOOLEAN NOT NULL DEFAULT FALSE to ChangeImpact
table per L2 PRD Section 12.11. The column was deferred from Step 13
because Step 9 schema was locked. Step 15 needs the column to
support administrator review actions per Section 14.6.2 (post-commit
review actions: flag for revision vs. mark as no action needed).

New migration added; existing databases get the column on next open.
```

## Definition of Done — UI Scaffolding (Commit 2)

10. **PySide6 mode selector** is added to the existing main window. The selector is a persistent control at the top of the window with two options: "Requirements" and "Deployment". Selecting a mode replaces the content area below.

11. **Read the existing `espo_impl/main_window.py`** (or equivalent) before modifying it. Make minimal surgical changes — add the mode selector, a content area, and the swap logic. Do not refactor the existing panels. Do not change their behavior. The existing panels become the "Deployment mode" content; they continue to work exactly as they do today.

12. **The Requirements mode container** (`requirements_window.py`) implements Section 14.1.2:
    - Sidebar with four entries: Dashboard, Data Browser, Documents, Impact Review
    - Default selection is Dashboard
    - Selecting a sidebar entry replaces the content area
    - Drill-down stack within Dashboard view (Work Item Detail, etc.)
    - Breadcrumb above content area, visible only when stack depth > 1
    - Each breadcrumb segment is clickable and pops the stack to that level

    For Step 15a, only the Dashboard sidebar entry needs to be functional. The Data Browser, Documents, and Impact Review entries can be placeholders that show "Coming in Step 15b/15c" — they will be implemented in subsequent prompts.

13. **Client selector** (`client_context.py` + `common/client_indicator.py`) implements Section 14.1.3:
    - A client selector above the sidebar that draws from the master database's Client table
    - Changing the client resets all Requirements mode state
    - The currently selected client name is displayed prominently
    - The client context is available to every screen in Requirements mode (provide it via the requirements_window or a shared context object — your choice)
    - All database queries operate against the selected client's database file

14. **Project Dashboard** (`dashboard/`) implements Section 14.2:
    - **Layout** (14.2.1): three vertical areas — summary bar, work queue, collapsible inventory
    - **Project summary bar** (14.2.1): client name, total work item count, counts by status using status badges
    - **Actionable work queue** (14.2.2): two groups in this order — Continue Work (in_progress) then Ready to Start (ready). Each row shows the work item name (human-readable-first format), phase name, item_type, status badge, started_at (in_progress) or dependency indicator (ready), and a staleness indicator if applicable. Items ordered by phase ascending then domain sort_order within phase.
    - **Full project inventory** (14.2.3): collapsible section, grouped by phase per the table in Section 14.2.3. Use `automation.workflow.phases.get_phase` and `get_phase_name` for the mapping. Each phase group shows phase number, phase name, completion indicator. Within each phase, items by domain sort_order. Blocked items show blocked_reason. Not_started items show dependency indicator.
    - **Filtering and sorting** (14.2.4): domain filter, phase filter, status filter; defaults to all. Active filters shown as removable tags. Default sort is phase ascending then domain sort_order; column header clicks override.
    - **Work item selection** (14.2.5): clicking a row pushes Work Item Detail onto the drill-down stack and updates the breadcrumb.
    - **Staleness summary** (14.2.6): banner between summary bar and work queue when any completed work item has a stale document. Shows count and a link (placeholder for Step 15c — the link target view does not exist yet).

15. **Work Item Detail** (`work_item/`) implements Section 14.3:
    - **Layout** (14.3.1): persistent header + tabbed detail area with four tabs (Dependencies, Sessions, Documents, Impacts). Last-selected tab is preserved when navigating away and back.
    - **Header content** (14.3.2): work item name (human-readable-first), phase name + number, status badge, blocked_reason if blocked, started_at if in_progress, completed_at + staleness indicator if complete, item_type, scoping info (domain/entity/process name).
    - **Header actions** (14.3.3): all 9 action buttons listed in 14.3.3. **Buttons are never disabled per Section 14.10.6** — clicking an inapplicable action shows an explanatory message describing why it's not available and what conditions must be met. The action handlers call WorkflowEngine methods (start, complete, revise, block, unblock); they delegate to other views for prompt generation, import, document generation (placeholders for Steps 15b/15c — the views don't exist yet, but the buttons should still be wired to push placeholder views or show "Coming in Step 15b/15c" toasts).
    - **Dependencies tab** (14.3.4): two sections — upstream and downstream dependents. Each row clickable, navigates to that work item's detail view (drill-down stack push, breadcrumb extends). For not_started items, incomplete upstream dependencies are highlighted. For blocked items with upstream revision cause, the reopened upstream is highlighted.
    - **Sessions tab** (14.3.5): list of AISession records, descending by creation date. Each entry shows session_type, creation timestamp, import_status, estimated token count. Expanding shows prompt context summary, import results, administrator notes. "View Raw Output" action opens scrollable text display. For unprocessed clarification sessions, a "Generate Prompt" action — for Step 15a this can be a placeholder.
    - **Documents tab** (14.3.6): list of GenerationLog entries for this work item. Shows generation timestamp, mode, file path, git commit hash. Staleness indicator at top per Section 13.6.1. "Generate Document" action — placeholder for Step 15c.
    - **Impacts tab** (14.3.7): list of ChangeImpact records where this work item is the affected item (reverse direction from Section 12.8.1). Grouped by source change. Shows impact description, review status, source change summary. Unreviewed first. Review actions — placeholder for Step 15b.

16. **Common UI patterns** (`common/`) implements Section 14.10:
    - **Status badges** (14.10.1): widget that takes a status string and renders a colored badge. Colors per Section 14.10.1 — research the L2 PRD for exact colors or use a sensible palette and document it. Statuses: not_started, ready, in_progress, complete, blocked.
    - **Staleness indicators** (14.10.4): a widget that takes a boolean stale flag and shows a visual badge.
    - **Human-readable-first formatting** (14.10.5): a helper function that takes a name and an identifier and returns "Name (IDENTIFIER)" format. This is the canonical place for the formatting rule. All UI display code uses this helper rather than building the string itself.
    - **Confirmation prompts** (14.10.7): a helper function that displays a modal confirmation dialog with a title, message, and OK/Cancel buttons. Returns True if confirmed.
    - **Error display** (14.10.8): helper for error/warning display.
    - **Toast notifications** (14.10.9): helper for non-modal transient notifications.
    - **Loading states** (14.10.10): helper widget for loading indicators.
    - **Client indicator** (14.10.11): widget showing the current client context (used in the requirements window header).
    - **Action badges** (14.10.2) and **severity indicators** (14.10.3) can be implemented as stubs in Step 15a since the screens that use them heavily are in Steps 15b/15c. The widgets exist but receive minimal usage.

17. **Navigation logic** (`navigation.py`):
    - Drill-down stack as a pure-Python data structure
    - Breadcrumb computation as a pure-Python function
    - Push, pop, pop-to-level operations
    - Tested in `test_ui_navigation.py` without any Qt imports

18. **Client context** (`client_context.py`):
    - State container for the current client (id, name, short_name, db path)
    - Tested in `test_ui_client_context.py` without any Qt imports

19. **Logic separation:** the dashboard and work item detail data assembly should live in pure functions/classes that can be tested without Qt. The tests `test_ui_dashboard_logic.py` and `test_ui_work_item_logic.py` exercise this logic. The Qt widgets are thin display layers that consume the data.

20. **The UI never modifies the database directly.** All writes go through the engines from Steps 10–14. The UI is a presentation layer.

21. **PySide6 imports are isolated to widget modules.** Pure-logic modules (`navigation.py`, `client_context.py`, dashboard/work-item logic helpers) must not import PySide6. This is enforceable and testable.

22. **All multi-row writes use `transaction()`.** N/A for Step 15a — there are no UI-initiated writes other than what the engines do internally.

23. **All tests pass** including the new ones: `uv run pytest automation/tests/ -v`. Target: 797 + new tests, no failures.

24. **Linter clean**: `uv run ruff check automation/`

25. **Application starts**: `uv run crmbuilder` (or whatever the existing entry point is) launches the application without crashing. The mode selector is visible, switching between modes works, the Dashboard loads when Requirements mode is selected, and clicking a work item navigates to the Work Item Detail view. **Doug will verify this manually after pulling the commit** — your tests do not need to launch the application.

26. **Commit 2 message:**

```
Implement Step 15a: UI scaffolding (Requirements mode, Dashboard, Work Item Detail)

PySide6 panels for the new Requirements mode integrated into the existing
CRM Builder application via a mode selector. Implements Sections 14.1, 14.2,
14.3, and 14.10 of the L2 PRD.

New package: automation/ui/
- requirements_window.py: mode container with sidebar and drill-down stack
- client_context.py: client selection and context propagation
- navigation.py: drill-down stack and breadcrumb logic (pure Python)
- common/: shared widgets and patterns from Section 14.10
- dashboard/: Project Dashboard from Section 14.2
- work_item/: Work Item Detail from Section 14.3

Existing espo_impl panels are unchanged. main_window.py receives a minimal
modification to add the mode selector and content swap logic.

Steps 15b and 15c will add the workflow screens, document generation,
data browser, and integration with existing deployment panels.
```

## Working Style

- **Read Sections 14.1, 14.2, 14.3, and 14.10 of the L2 PRD before writing any UI code.** Section 14.10 in particular — the common patterns apply across the entire UI and getting them right early saves rework later.
- **Read the existing `espo_impl/main_window.py`** (or equivalent) before modifying it. Make the smallest surgical change possible.
- **Read existing Step 9–14 code** to understand the engine APIs your UI calls.
- **Write tests alongside each pure-logic module**, not at the end. Qt widget code does not need tests.
- **Implement in this order**: schema bump (commit 1) → common widgets → navigation/client_context → dashboard/ → work_item/ → requirements_window → main_window integration. Each layer depends on earlier layers.
- **Surface ambiguities, do not invent answers.** Examples of things to flag rather than guess:
  - The L2 PRD doesn't specify exact colors for status badges. Use the existing palette from `automation/docgen/templates/formatting.py` (header background `#1F3864`, alternating row shading `#F2F7FB`, etc.) where they apply, and document any new colors you choose.
  - The existing main_window.py structure may differ from what this prompt assumes. Adapt your changes to fit the actual structure rather than rewriting it.
  - Section 14.1.3 says changing the client "discards in-progress review or import" with a confirmation prompt. For Step 15a there are no in-progress reviews/imports, so this is just a no-op confirmation. Implement the hook for future steps.
  - Section 14.2.6 staleness summary links to the Documents sidebar view. The Documents view doesn't exist until Step 15c. Make the link a placeholder that shows a toast or navigates to a stub view.
- **Do not modify Steps 9–14 code** except as explicitly required by the schema bump (commit 1 only modifies `client_schema.py` and `migrations.py`).
- **Do not modify the existing `espo_impl/` panels** other than `main_window.py`.
- **Do not pull in pytest-qt or any other Qt testing library.** Test the pure-Python logic, leave widget testing for manual inspection.
- **No HTTP / API calls.** Option B integration is preserved.

## Out of Scope for Step 15a

- Session Orchestration screens (Section 14.4) — Step 15b
- Import Review screens (Section 14.5) — Step 15b
- Impact Analysis Display screens (Section 14.6) — Step 15b
- Document Generation view (Section 14.7) — Step 15c
- Data Browser (Section 14.8) — Step 15c
- Integration with existing Deployment panels beyond the mode selector (Section 14.9) — Step 15c
- Modifying any code in Steps 9–14 except the ChangeImpact schema bump
- Pulling in pytest-qt or running widget tests
- HTTP / API calls

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 14.1** — Mode architecture, navigation, client selection
- **Section 14.2** — Project Dashboard (entire section)
- **Section 14.3** — Work Item Detail (entire section)
- **Section 14.10** — Common UI patterns (entire section)
- **Section 9** — Workflow Engine API (the methods your UI calls)
- **Section 14.2.3** — Phase mapping table (matches `automation/workflow/phases.py`)

You may find these useful for context but **do not implement them in Step 15a**:
- **Section 14.4–14.9** — Implemented in Steps 15b and 15c

## Final Check

Before declaring this step complete, verify:

- [ ] **Commit 1 (schema bump):**
  - [ ] `automation/db/client_schema.py` has `action_required` column on ChangeImpact
  - [ ] `automation/db/migrations.py` has a new idempotent migration
  - [ ] Migration test passes
  - [ ] Existing 797 tests still pass after the schema change
  - [ ] No other Step 9–14 code modified
- [ ] **Commit 2 (UI scaffolding):**
  - [ ] `grep -rn "PySide6" automation/ui/common/readable_first.py automation/ui/navigation.py automation/ui/client_context.py` returns zero matches (logic modules are Qt-free)
  - [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/ui/` returns zero matches
  - [ ] `grep -rn "engine\.revise\|engine\.complete\|engine\.start" automation/ui/` matches only delegation calls inside header_actions.py (UI delegates workflow transitions to the engine — this is correct usage)
  - [ ] All items in the Definition of Done are met
  - [ ] All tests pass (target: 797 existing + schema migration tests + new UI logic tests, no failures)
  - [ ] Linter is clean
  - [ ] No Step 9–14 code modified other than commit 1's schema bump
  - [ ] No existing `espo_impl/` panels modified other than the main window mode selector hook
  - [ ] Any deviations from the API sketch above are documented in your final report
  - [ ] Any ambiguities encountered in Sections 14.1–14.3 and 14.10 and how you resolved them are documented in your final report

When complete, commit with the descriptive messages above and report what was built. Do not push — leave that for Doug.
