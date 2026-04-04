# SESSION PROMPT: CRM Builder Automation — Import Processor Design

## Session Goal

Design Section 11 (Import Processor) of the CRM Builder Automation L2 PRD. The output will replace the placeholder in the existing L2 document.

## Context

### What is the Import Processor?

The Import Processor is one of the six components of CRM Builder Automation. After the administrator completes an AI session in Claude.ai, the session produces a JSON structured output block. The administrator pastes this block into the application, and the Import Processor parses it, maps it to proposed database records, presents those records for review, and — upon confirmation — commits them to the database.

The Import Processor is the bridge between the external AI session and the structured database. It addresses two problems from the L1 PRD: ensuring that AI-produced data goes through review before entering the system, and maintaining the audit trail that links every database record to the session that created it.

### Key Documents

Read these files from the crmbuilder repo:
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` (strategic vision — see Sections 6.4, 7.4, 7.5, 7.7)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (detailed design — Sections 3–10 are complete)
- `PRDs/process/CRM-Builder-Document-Production-Process.docx` (the 12-phase process)

Section 10 (Prompt Generator) is particularly important because it defines the structured output format (Section 10.5) that the Import Processor must parse, including the common JSON envelope and all nine type-specific payload structures.

### How Import Works in the Current Flow

Today there is no structured import. The AI session produces a Word document, which the administrator reviews, edits, and commits to the Git repository. The "import" is manual — the administrator reads what Claude produced and decides what to keep.

In the automated flow:
1. The Prompt Generator assembles a prompt containing a Structured Output Specification.
2. The administrator runs the session in Claude.ai.
3. At the end of the conversation, Claude produces a JSON block following the specification.
4. The administrator copies the JSON and pastes it into the Import Processor.
5. The Import Processor parses the JSON, validates it, and presents proposed database records.
6. The administrator reviews the proposed records — accepting, modifying, or rejecting individual items.
7. Upon confirmation, the Import Processor writes the accepted records to the database.
8. The Import Processor triggers downstream effects: workflow engine recalculation, dependency graph construction (for master_prd and business_object_discovery imports), and audit trail creation.

### Database Tables Relevant to This Section

**Requirements Layer (target tables for import):** Domain, Entity, Field, FieldOption, Relationship, Persona, BusinessObject, Process, ProcessStep, Requirement

**Cross-Reference Layer (target tables):** ProcessEntity, ProcessField, ProcessPersona

**Management Layer:** Decision, OpenIssue, WorkItem, Dependency

**Audit Layer:** AISession (stores raw output and links to work item), ChangeLog (records every field-level modification)

**Layout Layer (target tables):** LayoutPanel, LayoutRow, LayoutTab, ListColumn

**Master Database:** Client (organization_overview, crm_platform columns)

### Structured Output Format (from Section 10.5)

The Import Processor receives a JSON block with this common envelope:

```json
{
  "output_version": "1.0",
  "work_item_type": "<type>",
  "work_item_id": <integer>,
  "session_type": "initial | revision | clarification",
  "payload": { <type-specific data> },
  "decisions": [ <new decisions> ],
  "open_issues": [ <new or updated open issues> ]
}
```

Nine work item types produce structured output: master_prd, business_object_discovery, entity_prd, domain_overview, process_definition, domain_reconciliation, yaml_generation, crm_selection, and crm_deployment. Each has a different payload structure defined in Section 10.5.2.

### Workflow Engine Integration Points

The Import Processor must trigger Workflow Engine actions at specific points:

- **After master_prd import (Section 9.4.2):** The engine creates the business_object_discovery work item and its dependency on master_prd.

- **After business_object_discovery import (Section 9.4.3):** This is the primary dependency graph construction event. The import creates Entity records and BusinessObject resolution links. The engine creates work items for all remaining phases: entity_prd (one per entity), domain_overview (one per domain), process_definition (one per process), domain_reconciliation (one per domain), stakeholder_review, yaml_generation, crm_selection, crm_deployment, crm_configuration, and verification — with all dependency wiring.

- **After any import that completes a work item:** The engine transitions the work item to complete and runs downstream recalculation (Section 9.7.1).

- **Revision imports:** The work item is already in_progress (reopened). The import updates existing records rather than creating new ones. Upon completion, the engine runs the same downstream recalculation.

### Locked Decisions Relevant to This Section

- **DEC-002:** AI sessions are external. The application generates prompts and imports structured results.
- **DEC-005:** All changes go through managed process — no direct edits that bypass impact analysis and audit tracking.
- **DEC-009:** Stored status with event-driven recalculation. The Import Processor must trigger status recalculation after committing records.
- **DEC-010:** Dependency graph built progressively. The Import Processor triggers graph construction at specific import points.
- **DEC-013:** Cascade regression on revision. Revision imports may trigger downstream status changes.
- **DEC-029:** Structured output format is JSON with common envelope and type-specific payloads.
- **DEC-031:** Three session types with distinct behavior. Initial creates new records, revision updates existing records, clarification conditionally produces output.

### Schema Changes from Section 10

The Prompt Generator design added columns that the Import Processor must populate:

- **Domain:** parent_domain_id, is_service, domain_overview_text, domain_reconciliation_text
- **Entity:** primary_domain_id
- **Field:** is_native
- **Client:** organization_overview, crm_platform

## What This Session Must Produce

Design the Import Processor section covering:

1. **Import pipeline** — What is the end-to-end flow from pasting JSON to committed records? What are the stages (parse, validate, map, review, confirm, commit, trigger)? What happens at each stage?

2. **JSON parsing and validation** — How does the processor validate the JSON envelope? What checks are performed (output_version compatibility, work_item_type matching the current work item, required fields present)? How are malformed or incomplete JSON blocks handled?

3. **Payload-to-record mapping per work item type** — For each of the nine work item types, how does the processor map the payload data to specific database tables and columns? Which records are created, which are updated, and which cross-references are established? This is the inverse of the Prompt Generator's context assembly rules.

4. **Review and confirmation workflow** — How does the administrator review proposed records before they are committed? What does the review screen show? Can the administrator accept, modify, or reject individual records? What happens to rejected records — are they discarded or flagged for later? How granular is the review (record-level, field-level)?

5. **Conflict detection** — When imported data conflicts with existing database records (e.g., a field with the same name already exists with a different type), how is the conflict detected, presented, and resolved? What types of conflicts are checked?

6. **Partial import handling** — What happens when the administrator accepts some proposed records but rejects others? Is the import atomic (all or nothing) or can it be partial? What about records that depend on other records within the same import (e.g., a Field that references an Entity being imported in the same batch)?

7. **Session type handling** — How does the processor behave differently for initial, revision, and clarification session types? Initial creates new records. Revision updates existing records — how does the processor identify which records to update? Clarification may or may not produce output.

8. **Decisions and open issues** — The envelope's top-level decisions and open_issues arrays follow a consistent format. How are these mapped to Decision and OpenIssue records? How is scoping determined (domain_id, entity_id, process_id, etc.)?

9. **Audit trail creation** — How does the processor record the import in the audit trail? What gets stored in AISession? How does ChangeLog capture individual field-level changes? How is the link maintained between imported records and their source session?

10. **Downstream triggers** — After import is committed, what downstream actions are triggered? Workflow engine recalculation, dependency graph construction, work item status transitions — what is the sequence? Are these synchronous or asynchronous?

11. **Error handling and recovery** — What happens if the import fails partway through (e.g., database write error after some records are committed)? Is there a rollback mechanism? How are errors presented to the administrator?

12. **Identifier management** — AI sessions assign identifiers (e.g., MN-INTAKE-REQ-001). How does the Import Processor validate identifier uniqueness? How does it handle identifier conflicts? Does it auto-assign identifiers or preserve the AI-assigned ones?

## Output Format

Produce the content as structured text organized by subsection (11.1, 11.2, etc.) that can be incorporated into the L2 PRD Word document. Include any new decisions that should be added to Section 15 and any new open issues for Section 16.

## Working Style

- Discuss and resolve one design question at a time before moving to the next
- Ask for confirmation before finalizing each subsection
- If a design question has multiple viable approaches, present the options with tradeoffs and ask for a decision
- Flag any schema changes needed (new columns, new tables, modified constraints)
- Reference Section 10's payload definitions when discussing record mapping — the Import Processor must handle exactly what the Prompt Generator specifies
- Consider the interaction with the Impact Analysis Engine (Section 12, not yet designed) — imports may need to trigger impact analysis before committing
