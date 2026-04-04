# SESSION PROMPT: CRM Builder Automation — Impact Analysis Engine Design

## Session Goal

Design Section 12 (Impact Analysis Engine) of the CRM Builder Automation L2 PRD. The output will replace the placeholder in the existing L2 document.

## Context

### What is the Impact Analysis Engine?

The Impact Analysis Engine traces the downstream effects of any data change in the system. When a field definition changes, the engine identifies every process that references that field, every cross-reference that links to it, every layout that displays it, and every document that would need regeneration. The engine produces a complete list of affected items so the administrator can understand the full scope of a change before or after it is committed.

The engine addresses the L1 PRD's requirement (Section 7.5) that every modification goes through impact analysis: "The application identifies all downstream items affected by the change, presents the full impact, and requires confirmation. The change, its rationale, its source, and its downstream effects are recorded in the audit trail."

### Key Documents

Read these files from the crmbuilder repo:
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` (strategic vision — see Sections 6.6, 7.5)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (detailed design — Sections 3–11 are complete)

Section 11 (Import Processor) is particularly important because it defines when impact analysis is triggered (Section 11.10.1 step 5) and establishes that clarification session modifications also trigger impact analysis (Section 11.7.3).

### How Impact Analysis Works in the Current Flow

Today there is no automated impact analysis. When the administrator edits a document — say, changing a field's data type in an Entity PRD — they must manually trace which process documents reference that field, which Domain PRDs include it, and which YAML files would need updating. This is error-prone and becomes increasingly difficult as the project grows.

In the automated flow:
1. A change occurs — either through an AI session import (Section 11) or through a direct administrator edit.
2. The change is recorded in ChangeLog with field-level detail.
3. The Impact Analysis Engine queries the cross-reference tables (ProcessEntity, ProcessField, ProcessPersona) and the dependency graph to identify all affected items.
4. The engine creates ChangeImpact records for each affected item, describing how it is affected.
5. The administrator reviews the impact — each affected item is marked as reviewed or flagged for action.
6. For items that require revision, the administrator may reopen work items, triggering the revision workflow (Section 9.7.2).

### Database Tables Relevant to This Section

**Cross-Reference Layer (primary query targets):** ProcessEntity, ProcessField, ProcessPersona — these tables are the foundation of impact analysis. Changing a field triggers a query across ProcessField to find every process that uses it. Changing an entity triggers a query across ProcessEntity.

**Audit Layer:**
- ChangeLog — every field-level modification, the input to impact analysis. Columns: session_id, table_name, record_id, change_type, field_name, old_value, new_value, rationale, changed_at.
- ChangeImpact — the output of impact analysis. Columns: change_log_id (FK to ChangeLog), affected_table, affected_record_id, impact_description, requires_review (boolean, default TRUE), reviewed (boolean, default FALSE), reviewed_at.

**Layout Layer:** LayoutPanel, LayoutRow, LayoutTab, ListColumn — a field change may affect layouts that display the field.

**Management Layer:** WorkItem, Dependency — impact analysis may surface the need to reopen work items.

**Requirements Layer:** All tables — these are both sources of changes and targets of impact.

### Integration Points with Other Components

**Import Processor (Section 11):** After committing records, the Import Processor triggers impact analysis for any update operations (Section 11.10.1 step 5). The engine receives the ChangeLog entries from the import transaction and traces their effects. Clarification session modifications also trigger impact analysis (Section 11.7.3).

**Workflow Engine (Section 9):** Impact analysis results may lead the administrator to reopen work items, triggering the revision workflow (Section 9.7.2) with cascade regression. The Impact Analysis Engine does not automatically reopen work items — it surfaces the information and the administrator decides.

**Document Generator (Section 13, not yet designed):** Impact analysis identifies which documents would need regeneration. The Document Generator will use staleness detection to flag documents whose source data has changed since last generation.

**Prompt Generator (Section 10):** When a revision session is triggered as a result of impact analysis, the Prompt Generator assembles the revision prompt with the change context.

### Locked Decisions Relevant to This Section

- **DEC-005:** All changes go through managed process — no direct edits that bypass impact analysis and audit tracking.
- **DEC-009:** Stored status with event-driven recalculation. Impact analysis operates on the committed state.
- **DEC-013:** Cascade regression on revision. Impact analysis may surface the need for revision, which triggers cascade regression in the Workflow Engine.
- **DEC-036:** Step-level cross-references replace process-level. Impact analysis can trace field changes to specific process steps, not just processes.

### What the L1 PRD Says

**Section 6.6 (Impact Analysis Engine):** "When a change is proposed, traces all references and dependencies to produce a complete list of affected items. For example, changing a field's data type on the Contact entity would surface every process that references that field, every domain PRD that includes it, and every YAML file that defines it."

**Section 7.5 (Managed Change Process):** "Every modification to the database — whether from an AI session import or an administrator-initiated change — goes through impact analysis first. The application identifies all downstream items affected by the change, presents the full impact, and requires confirmation. The change, its rationale, its source, and its downstream effects are recorded in the audit trail."

Note the L1 says "goes through impact analysis first" — implying pre-commit analysis. However, the Import Processor design (Section 11) commits data first, then triggers impact analysis post-commit. This tension needs to be resolved in this section. The question is whether impact analysis runs before or after data is committed, and whether the answer differs for imports vs. direct administrator edits.

## What This Session Must Produce

Design the Impact Analysis Engine section covering:

1. **Overview** — What is the engine's role? When does it run? What are its inputs and outputs?

2. **Change sources** — What types of changes trigger impact analysis? AI session imports (update operations), direct administrator edits, revision cascade effects? Are all changes treated the same or do different sources get different treatment?

3. **Pre-commit vs. post-commit analysis** — The L1 PRD implies pre-commit analysis ("goes through impact analysis first"), but the Import Processor commits first then triggers analysis. Resolve this: when does analysis run relative to the commit? Does it differ between import-triggered changes and direct administrator edits?

4. **Cross-reference query engine** — How does the engine trace affected items? For each change type (field modified, entity modified, persona modified, process modified, relationship modified, requirement modified), what tables are queried and what is the query logic? How does step-level granularity (DEC-036) enhance the precision of impact tracing?

5. **Impact propagation rules** — For each type of change, what downstream items are considered affected? A field type change affects: processes using the field (via ProcessField), layouts displaying the field (via LayoutRow, ListColumn), YAML configurations, and documents. Define the propagation rules for each change category.

6. **ChangeImpact record creation** — How are ChangeImpact records created? What goes into impact_description? How is requires_review determined — are all impacts flagged for review, or are some auto-resolved?

7. **Impact presentation** — How does the administrator see the impact? Is it grouped by affected table? By work item? By severity? Does the presentation distinguish between "this item needs revision" and "this item is informational"?

8. **Review tracking** — How does the administrator mark affected items as reviewed? Can they review individually or in bulk? What happens when all impacts for a change are reviewed — is the change considered fully resolved?

9. **Direct administrator edits** — How does the engine handle changes made directly by the administrator (outside of AI imports)? DEC-005 says all changes go through managed process. How does the administrator initiate a direct edit, and how does impact analysis fit into that flow?

10. **Interaction with revision workflow** — When impact analysis surfaces items that need revision, how does the administrator act on them? The engine doesn't automatically reopen work items — what is the workflow from "this item is affected" to "reopen this work item for revision"?

11. **Batch impact analysis** — An import may create many ChangeLog entries in a single transaction. Does the engine analyze each change independently or batch them? How are overlapping impacts deduplicated (e.g., two field changes in the same import both affect the same process)?

12. **Schema changes** — Does this section require any new tables or columns beyond what is already defined?

## Output Format

Produce the content as structured text organized by subsection (12.1, 12.2, etc.) that can be incorporated into the L2 PRD Word document. Include any new decisions that should be added to Section 15 and any new open issues for Section 16.

## Working Style

- Discuss and resolve one design question at a time before moving to the next
- Ask for confirmation before finalizing each subsection
- If a design question has multiple viable approaches, present the options with tradeoffs and ask for a decision
- Flag any schema changes needed (new columns, new tables, modified constraints)
- Reference Section 11's trigger points when discussing when impact analysis runs
- Consider the interaction with the Document Generator (Section 13, not yet designed) — impact analysis should identify which documents are stale without requiring the Document Generator to be fully specified
