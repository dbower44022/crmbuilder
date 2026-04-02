# SESSION PROMPT: CRM Builder Automation — Workflow Engine Design

## Session Goal

Design Section 9 (Workflow Engine) of the CRM Builder Automation L2 PRD. The output will replace the placeholder in the existing L2 document.

## Context

### What is CRM Builder Automation?

CRM Builder is being extended from a CRM deployment tool into a full lifecycle platform. The new "Automation" feature introduces a structured SQLite database as the single source of truth for all requirements data — domains, entities, processes, fields, decisions, and open issues. PRD documents and YAML program files become generated outputs from the database rather than hand-crafted artifacts.

AI sessions run externally in Claude.ai (not embedded in the app). The app generates session prompts, the administrator runs the session, and structured results are imported back into the database. All changes go through a managed process with impact analysis and audit trail.

### Key Documents

Upload these files from the crmbuilder repo into this conversation:
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` (strategic vision)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (detailed design — database schema is complete, Sections 9–14 are placeholders)
- `PRDs/process/CRM-Builder-Document-Production-Process.docx` (the current 9-phase process that the workflow engine must manage)

### Database Tables Relevant to This Section

**WorkItem** — tracks phase and status for every work item:
- id, item_type (master_prd, business_object_discovery, entity_prd, process_definition, domain_reconciliation, yaml_generation, stakeholder_review), domain_id, entity_id, process_id, phase, status (not_started, ready, in_progress, complete, blocked), blocked_reason, started_at, completed_at

**Dependency** — declares ordering between work items:
- id, work_item_id, depends_on_id

**AISession** — records each AI conversation:
- id, work_item_id, session_type (initial, revision, clarification), generated_prompt, raw_output, structured_output, import_status (pending, imported, partial, rejected), started_at, completed_at

### The 9-Phase Process the Engine Must Manage

```
Phase 1: Master PRD             → 1 work item
Phase 2: Entity Definition      → 1 work item for Business Object Discovery
                                   + 1 work item per entity (Entity PRDs)
Phase 3: Process Definition     → 1 work item per business process
                                   (dependency-ordered within each domain)
Phase 4: Domain Reconciliation  → 1 work item per domain
Phase 5: Stakeholder Review     → 1 work item per domain (outside Claude)
Phase 6: YAML Generation        → 1 work item per domain
Phase 7: CRM Selection          → 1 work item
Phase 8: CRM Configuration      → tool-driven (existing CRM Builder functionality)
Phase 9: Verification           → tool-driven (existing CRM Builder functionality)
```

### Locked Decisions Relevant to This Section

- **DEC-005:** All changes go through managed process — no direct edits that bypass impact analysis and audit tracking.
- **DEC-006:** ProcessField and ProcessEntity include optional step-level granularity via nullable process_step_id.
- **DEC-007:** Domain sort_order is display preference only. Domains have no cross-domain dependencies. Dependency enforcement operates at the process and entity level.

## What This Session Must Produce

Design the Workflow Engine section covering:

1. **Status calculation logic** — How does the engine determine a work item's status from its dependencies? When does "not_started" become "ready"? When does "ready" become "in_progress"? When does a completed dependency trigger recalculation of downstream items?

2. **Dependency graph construction** — When the administrator creates a new client implementation, what work items and dependencies are created automatically? What happens when new entities or processes are added mid-project (e.g., Business Object Discovery identifies 9 entities — how do 9 entity_prd work items and their dependencies get created)?

3. **Phase ordering rules** — What are the concrete dependency rules? For example:
   - All entity_prd work items depend on business_object_discovery
   - Each process_definition work item depends on the entity_prd work items for entities it references
   - Process definitions within a domain depend on prior processes in sort_order
   - domain_reconciliation depends on all process_definitions in that domain
   - yaml_generation depends on domain_reconciliation and stakeholder_review for the domain

4. **Available work calculation** — How does the engine determine what work items are available to the administrator right now? This feeds the Project Dashboard.

5. **Status transitions and side effects** — What happens when a work item is marked complete? What happens when a completed work item needs revision (e.g., a stakeholder review sends an Entity PRD back for changes)?

6. **Blocked state handling** — Under what conditions does a work item become blocked? How is the blocked reason communicated? How does unblocking work?

7. **Cross-phase dependencies** — How does the engine handle the fact that Process Definition (Phase 3) depends on Entity PRDs (Phase 2) at the entity level, not the phase level? (i.e., a process can start as soon as the entities it references are defined, even if other entities are still in progress)

## Output Format

Produce the content as structured text organized by subsection (9.1, 9.2, etc.) that can be incorporated into the L2 PRD Word document. Include any new decisions that should be added to Section 15 and any new open issues for Section 16.

## Working Style

- Discuss and resolve one design question at a time before moving to the next
- Ask for confirmation before finalizing each subsection
- If a design question has multiple viable approaches, present the options with tradeoffs and ask for a decision
- Flag any schema changes needed (new columns, new tables, modified constraints)
