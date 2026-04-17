# SESSION PROMPT: CRM Builder Automation — User Interface Design

## Session Goal

Design Section 14 (User Interface) of the CRM Builder Automation L2 PRD. The output will replace the placeholder in the existing L2 document.

## Context

### What is the User Interface Section?

The User Interface section defines how the administrator interacts with every capability designed in Sections 9–13. The Workflow Engine (Section 9), Prompt Generator (Section 10), Import Processor (Section 11), Impact Analysis Engine (Section 12), and Document Generator (Section 13) are all backend components — they describe data structures, algorithms, and pipelines. Section 14 defines the screens, controls, navigation, and interaction patterns that expose these capabilities to the administrator.

CRM Builder is an existing PySide6 desktop application with panels for instance management, program file management, deployment, and output. The automation feature extends this application with new panels for requirements management and project orchestration. The existing panels remain for the final phases (CRM deployment and configuration).

### Key Documents

Read these files from the crmbuilder repo:
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` (strategic vision — see Sections 4, 6.7, 7.1, 7.3, 7.4, 7.5, 7.6, 7.7)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (detailed design — Sections 3–13 are complete)

The L1 PRD's Section 6.7 identifies the UI as the integration layer: "The existing CRM Builder desktop application, extended with new panels for project management, session orchestration, data review, and document generation." Section 7 describes key capabilities that each imply specific UI requirements.

### What the L1 PRD Says About the UI

**Section 4 (Target Users):** The primary user is the Implementation Administrator — manages a CRM implementation project, defines requirements through AI-assisted sessions, reviews imported data, resolves conflicts, approves generated documents. Needs a clear picture of project status: what is done, what is next, what is blocked.

**Section 7.1 (Project Dashboard):** "A single view showing the complete state of a client implementation. Every domain, entity, and process is listed with its current phase, completion status, and any blocking dependencies. The administrator can see at a glance what is done, what is in progress, what is available to work on next, and what is blocked."

**Section 7.3 (AI Session Orchestration):** "For each available work item, the application generates a session prompt... The administrator copies the prompt into Claude.ai, runs the session, and pastes the structured output back into the application for import."

**Section 7.4 (Structured Import with Review):** "AI session output is parsed into proposed database records. The administrator reviews each proposed record before it is committed — field by field if necessary. The import screen shows what will be created, what will be modified, and flags anything that conflicts with existing data. Nothing is written to the database without explicit confirmation."

**Section 7.5 (Managed Change Process):** "Every modification to the database... goes through impact analysis first. The application identifies all downstream items affected by the change, presents the full impact, and requires confirmation."

**Section 7.6 (Document Generation on Demand):** "Any document type can be generated from the current database state at any time... If the database has changed since the last time a document was generated, the application flags which documents are stale."

**Section 7.7 (Complete Audit Trail):** "The administrator can trace any field definition back to the session that created it and forward to every document that includes it."

### What the Completed L2 Sections Require from the UI

**Section 9 (Workflow Engine):**
- Project Dashboard must display work items in two groups: "Continue Work" (in_progress) and "Ready to Start" (ready), ordered by phase then domain (Section 9.6).
- Status badges for all five states: not_started, ready, in_progress, complete, blocked.
- Blocked items show blocked_reason. Administrator can manually block/unblock items (Section 9.8).
- Administrator triggers status transitions: ready → in_progress, in_progress → complete, complete → in_progress (revision).
- Dependency graph must be viewable — the administrator needs to understand why an item is not_started or blocked.

**Section 10 (Prompt Generator):**
- "Generate Prompt" action available on ready and in_progress work items.
- Generated prompt must be presented in a copyable format (the administrator copies it to Claude.ai).
- Prompt includes estimated token count and any reduction strategies applied (Section 10.9).
- For revision sessions, the administrator provides revision reason and optional change instructions before prompt generation.

**Section 11 (Import Processor):**
- Paste area for raw JSON output from AI sessions.
- Parse error display with line/character position for syntax errors.
- Proposed record review organized by category (Section 11.4.1): domains, entities, personas, fields, field options, relationships, process steps, requirements, cross-references, layout records, decisions, open issues.
- Each proposed record shows: action badge (create/update), field values, conflict indicators with severity (error/warning/info), accept/modify/reject controls.
- Bulk accept/reject per category (Section 11.4.2).
- Commit summary with counts by action (Section 11.4.3).
- Warning about unresolved errors blocking commit.
- Trigger status display after commit (Section 11.10).

**Section 12 (Impact Analysis Engine):**
- Post-commit impact review: grouped by affected table, split into "requires review" and "informational" (Section 12.6.1). Summary header with counts. Review actions per impact: "no action needed" or "flag for revision" (Section 12.7.1). Bulk review.
- Pre-commit confirmation for direct edits: impact set display with rationale text field and Confirm/Cancel (Section 12.6.4).
- Unresolved change sets display — changes with unreviewed impacts (Section 12.7.3).
- Work item mapping — flagged impacts grouped by affected work item with revision eligibility (Section 12.8).

**Section 13 (Document Generator):**
- Staleness indicators on completed work items in the dashboard (Section 13.6.2).
- Document generation view listing stale documents with change summaries.
- Draft/final generation toggle (Section 13.8).
- Generation progress and confirmation with file path and git commit hash.
- Optional git push action after generation.
- Batch regeneration for multiple stale documents (Section 13.7.4).

### Existing Application Architecture

The current CRM Builder application uses:
- **PySide6** — Qt for Python desktop framework.
- **Main window** (`main_window.py`) with a state machine managing panel visibility.
- **Instance panel** — list of CRM instances with CRUD.
- **Program panel** — YAML file list, driven by selected instance's project folder.
- **Output panel** — color-coded log output.
- **Deploy panel** — deployment section driven by selected instance context.
- **Import dialog** — self-contained four-step data import wizard (separate from the automation import).
- **Pattern:** Buttons are never disabled — click handlers show explanatory messages instead.
- **Pattern:** Content panels respond to instance selection.

### Locked Decisions Relevant to This Section

- **DEC-002:** AI sessions are external — run in Claude.ai, not embedded. The UI provides prompt generation and structured output import, not a chat interface.
- **DEC-005:** All changes go through managed process — the UI must enforce impact analysis confirmation for direct edits.
- **DEC-034:** Strictly linear import pipeline — the import UI follows a fixed sequence with a cancel option at any point.
- **DEC-041:** Generated documents committed to git automatically — the UI shows git commit status and offers optional push.
- **DEC-043:** Draft generation available for in-progress work items — the UI must support both generation modes.

## What This Session Must Produce

Design the User Interface section covering:

1. **Overview** — How the automation panels integrate into the existing CRM Builder main window. Navigation model (how the administrator moves between project management and CRM deployment). Client selection and context.

2. **Project Dashboard** — The central view. Work item display with status badges, phase grouping, staleness indicators. "Continue Work" and "Ready to Start" sections. Filtering and sorting. Dependency visualization. Summary statistics.

3. **Work Item Detail** — What the administrator sees when selecting a work item. Status, phase, dependencies (upstream and downstream), associated AI sessions, generation history from GenerationLog, impact history from ChangeImpact. Actions available by status.

4. **Session Orchestration** — The prompt generation and session management flow. How the administrator initiates a session, configures revision/clarification parameters, views the generated prompt with token count, copies it, and returns to import. Session history per work item.

5. **Import Review Interface** — The 7-stage pipeline UI. Paste input area, parse feedback, proposed record review with category organization, conflict indicators, accept/modify/reject controls, bulk actions, commit summary, trigger status. How the administrator modifies a proposed value during review.

6. **Impact Analysis Display** — Two variants: post-commit review after imports, and pre-commit confirmation before direct edits. Grouped impact presentation, review actions (no action / flag for revision), bulk review, summary header, unresolved change tracking. Work item revision mapping.

7. **Document Generation View** — Staleness summary, document selection, draft/final mode, generation progress, output confirmation with file path and git status. Batch regeneration workflow.

8. **Data Browser** — Direct viewing and editing of database records outside the import pipeline. Entity, field, process, persona, and other record types. This is where pre-commit impact analysis (Section 12.5) is triggered. How the administrator navigates the data model.

9. **Integration with Existing Panels** — How the automation panels coexist with Instance, Program, Deploy, and Output panels. Navigation between requirements management and CRM deployment. When the project reaches CRM Configuration (Phase 10), the existing panels take over.

10. **Common UI Patterns** — Shared conventions used across all panels: status badges and their visual design, staleness indicators, human-readable-first display rule, confirmation dialogs, error and warning presentation, toast notifications, loading states. The "buttons never disabled" pattern and how it applies to new panels.

## Output Format

Produce the content as structured text organized by subsection (14.1, 14.2, etc.) that can be incorporated into the L2 PRD Word document. Include any new decisions that should be added to Section 15 and any new open issues for Section 16.

## Working Style

- Discuss and resolve one design question at a time before moving to the next
- Ask for confirmation before finalizing each subsection
- If a design question has multiple viable approaches, present the options with tradeoffs and ask for a decision
- Reference specific section numbers from Sections 9–13 when describing UI requirements they impose
- Keep the section consistent in depth and style with Sections 9–13
- This section should define WHAT the UI presents and HOW the administrator interacts with it, not implementation details like specific Qt widget classes or layout code — those belong in implementation documentation
- Consider the administrator's workflow end-to-end: from opening the application to completing a full phase of work
