# SESSION PROMPT: CRM Builder Automation — Prompt Generator Design

## Session Goal

Design Section 10 (Prompt Generator) of the CRM Builder Automation L2 PRD. The output will replace the placeholder in the existing L2 document.

## Context

### What is the Prompt Generator?

The Prompt Generator is one of the six components of CRM Builder Automation. When the administrator is ready to work on a work item, the application reads the database and assembles a complete AI session prompt — including all relevant context, locked decisions, open issues, and specific instructions for what the session needs to produce. The administrator copies the prompt into Claude.ai and runs the session.

The Prompt Generator eliminates manual context assembly, which is the first problem identified in the L1 PRD: "Before each AI session, the administrator must identify which prior documents to upload, what decisions have been locked, and what open issues remain."

### Key Documents

Upload these files from the crmbuilder repo into this conversation:
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` (strategic vision)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (detailed design — Sections 3–9 are complete)
- `PRDs/process/CRM-Builder-Document-Production-Process.docx` (v1.6 — the 12-phase process)
- `PRDs/process/interviews/interview-master-prd.md` (Phase 1 interview guide)
- `PRDs/process/interviews/guide-entity-definition.md` (Phase 2 interview guide)
- `PRDs/process/interviews/interview-process-definition.md` (Phase 5 interview guide)
- `PRDs/process/interviews/guide-domain-reconciliation.md` (Phase 6 reconciliation guide)

### How the Current Process Works (Without Automation)

Today, the administrator manually assembles context for each AI session:

1. **Master PRD session** — No prior context needed. Administrator provides information verbally.
2. **Entity Discovery session** — Upload Master PRD.
3. **Entity Definition sessions** — Upload Master PRD + Entity Inventory + all prior Entity PRDs.
4. **Domain Overview sessions** — Upload Master PRD + Entity Inventory + Entity PRDs for entities in this domain.
5. **Process Definition sessions** — Upload Domain Overview + all prior process documents for this domain.
6. **Domain Reconciliation sessions** — Upload Master PRD + Entity Inventory + relevant Entity PRDs + all process documents for the domain.
7. **YAML Generation sessions** — Upload Domain PRD + Entity PRDs + all prior YAML files.
8. **CRM Selection session** — Upload approved Domain PRDs + YAML program files.

Each session also uses an interview guide (from crmbuilder/PRDs/process/interviews/) that tells Claude how to conduct the conversation and what structured output to produce.

The Prompt Generator must automate all of this: reading the database to assemble the equivalent context, selecting the right interview guide, including relevant decisions and issues, and packaging it into a prompt the administrator copies into Claude.ai.

### Database Tables Relevant to This Section

**Requirements Layer:** Domain, Entity, Field, FieldOption, Relationship, Persona, BusinessObject, Process, ProcessStep, Requirement

**Cross-Reference Layer:** ProcessEntity, ProcessField, ProcessPersona

**Management Layer:** Decision, OpenIssue, WorkItem, Dependency

**Audit Layer:** AISession

**Layout Layer:** LayoutPanel, LayoutRow, LayoutTab, ListColumn

### Workflow Engine Context (Section 9)

The Workflow Engine determines which work items are ready. When the administrator selects a ready work item and clicks "Generate Prompt," the Prompt Generator takes over. It receives the work_item_id and must:
1. Determine the work item type (master_prd, entity_prd, domain_overview, process_definition, etc.)
2. Assemble the appropriate context from the database
3. Include the right interview guide or instructions
4. Include relevant locked decisions and open issues
5. Specify the structured output format the AI must produce at the end
6. Package everything into a copyable text block

### Locked Decisions Relevant to This Section

- **DEC-002:** AI sessions are external. Conversations run in Claude.ai, not embedded in the application. The application generates prompts and imports structured results.
- **DEC-005:** All changes go through managed process — no direct edits that bypass impact analysis and audit tracking.
- **DEC-015:** Domain overview as gateway to process work. The domain_overview document replaces the need to upload Master PRD + Entity Inventory + Entity PRDs separately.

### Open Issues Relevant to This Section

- **ISS-002:** Structured output format. The specific format (JSON schema, YAML schema, or other) for the structured output block that AI sessions must produce has not been defined. This section should address or advance this issue.

## What This Session Must Produce

Design the Prompt Generator section covering:

1. **Prompt structure** — What is the standard structure of a generated prompt? What sections does every prompt contain (context, instructions, output format, etc.)? How is the prompt organized so Claude can parse it effectively?

2. **Context assembly rules per work item type** — For each of the 12 work item types, what data does the Prompt Generator read from the database to assemble context? This is the database equivalent of "upload these files." Some types may not need prompts (e.g., crm_configuration, verification are tool-driven).

3. **Decision and issue inclusion** — How does the Prompt Generator determine which decisions and open issues to include in a prompt? All of them? Only those scoped to the relevant domain/entity/process? What about global decisions?

4. **Interview guide selection** — How does the Prompt Generator select and include the appropriate interview guide? Are the guides stored in the database, referenced by file path, or embedded in the prompt template?

5. **Structured output format** — What format must the AI produce at the end of each session for the Import Processor to parse? This should address ISS-002. Consider: JSON vs. YAML, what fields are required, how different work item types produce different output structures.

6. **Revision prompts** — When a work item is reopened for revision (session_type = "revision"), how does the prompt differ from the initial session? What additional context is needed (e.g., the reason for revision, the specific changes requested)?

7. **Clarification prompts** — When the administrator needs to ask follow-up questions about a completed session (session_type = "clarification"), what context is included?

8. **Prompt templates** — Should the Prompt Generator use templates (one per work item type) that are filled with database data? Where are templates stored? How are they versioned?

9. **Context size management** — Claude has a finite context window. How does the Prompt Generator handle cases where the full context exceeds what fits? What gets prioritized? What gets summarized or omitted?

## Output Format

Produce the content as structured text organized by subsection (10.1, 10.2, etc.) that can be incorporated into the L2 PRD Word document. Include any new decisions that should be added to Section 15 and any new open issues for Section 16.

## Working Style

- Discuss and resolve one design question at a time before moving to the next
- Ask for confirmation before finalizing each subsection
- If a design question has multiple viable approaches, present the options with tradeoffs and ask for a decision
- Flag any schema changes needed (new columns, new tables, modified constraints)
- Reference the existing interview guides to ground the discussion in how sessions actually work today
