# SESSION PROMPT: CRM Builder Automation — Schema Validation Findings

## Session Goal

Address findings from prototype database schema validation using CBM data. Resolve schema refinements, evaluate a proposed addition, and clarify PRD ambiguities. The output will be targeted edits to the L2 PRD document and new decisions or issue resolutions as appropriate.

## Context

### What Was Validated?

The database schema defined in Sections 3–8 of the L2 PRD was prototyped with CBM (Cleveland Business Mentors) implementation data. The prototype populated all tables, exercised FK chains, tested cross-reference queries, and validated the 10 data query paths defined in Sections 10.3 and 13.3. The schema passed all structural tests — no constraint violations, all FK chains valid, all validation paths return meaningful data.

### Key Documents

Read these files from the crmbuilder repo:
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (detailed design — Sections 3–14 complete)

Relevant schema sections:
- Section 4.4 (FieldOption) — no timestamps currently defined beyond common conventions
- Section 5.1–5.3 (ProcessEntity, ProcessField, ProcessPersona) — cross-reference tables, no timestamps beyond common conventions
- Section 6.3 (WorkItem) — item_type and phase values
- Section 6.4 (Dependency) — no uniqueness constraint currently specified
- Section 4.8 (Process) — no tier/priority column
- Section 8.2 (LayoutRow) — no CHECK constraint on cell population
- Section 13.11.1 (GenerationLog) — document_type is TEXT with no constraint

### Findings to Address

#### Finding 1: Add UNIQUE(work_item_id, depends_on_id) to Dependency Table

**Section:** 6.4 (Dependency)

The Dependency table allows duplicate rows — the same dependency pair could be inserted twice. This is a data integrity gap. A UNIQUE constraint on (work_item_id, depends_on_id) prevents accidental duplicates without restricting valid usage.

**Proposed resolution:** Add "A UNIQUE constraint on (work_item_id, depends_on_id) prevents duplicate dependency declarations" to Section 6.4.

**Decision needed:** Is this straightforward enough to apply, or are there cases where duplicate dependency rows would be valid?

#### Finding 2: Add Timestamps to FieldOption and Cross-Reference Tables

**Section:** 4.4 (FieldOption), 5.1 (ProcessEntity), 5.2 (ProcessField), 5.3 (ProcessPersona)

The L2 PRD states in Section 4 that "All tables follow common conventions. Every table has id (INTEGER PRIMARY KEY auto-increment), created_at, and updated_at timestamps." However, these tables may benefit from explicit confirmation that the common conventions apply, particularly because:
- FieldOption is a child of Field — tracking when individual options were added or modified supports the audit trail
- Cross-reference tables are created during domain_overview imports and replaced during process_definition imports (DEC-036) — timestamps help trace when cross-references were established

**Proposed resolution:** Confirm that the common conventions statement in Section 4 already covers these tables. No schema change needed — just verification that the "all tables" statement is intended to be comprehensive.

**Decision needed:** Does the existing "all tables" convention statement suffice, or should these tables be called out explicitly?

#### Finding 3: Add CHECK Constraints on LayoutRow and GenerationLog

**Section:** 8.2 (LayoutRow), 13.11.1 (GenerationLog)

LayoutRow: A row with both cell_1_field_id and cell_2_field_id NULL is meaningless — it would render as an empty row. A CHECK constraint ensuring at least one cell is non-null prevents invalid data.

GenerationLog: The document_type column accepts any TEXT value, but only eight specific values are valid (master_prd, entity_inventory, entity_prd, domain_overview, process_document, domain_prd, yaml_program_files, crm_evaluation_report). A CHECK constraint validates against this enumeration.

**Proposed resolution:** Add CHECK constraints to both tables in their respective schema sections.

**Decision needed:** Should CHECK constraints be applied broadly to all enumerated-value TEXT columns in the schema (item_type on WorkItem, session_type on AISession, change_type on ChangeLog, etc.), or only to these two specific cases?

#### Finding 4: Consider Adding tier Column to Process Table

**Section:** 4.8 (Process)

During prototype validation, processes naturally fell into tiers — core processes (essential to the domain), important processes (valuable but not blocking), and enhancement processes (nice-to-have). This classification affects dependency ordering, stakeholder review prioritization, and implementation sequencing.

The current schema captures sort_order within a domain but has no concept of priority tier. Adding a tier column (TEXT, nullable, values: core, important, enhancement) would allow the Workflow Engine and Project Dashboard to surface tier-based prioritization.

**Proposed resolution:** Evaluate whether this adds enough value to justify the schema addition and the downstream implications (Prompt Generator context, Import Processor mapping, Document Generator rendering).

**Decision needed:** Is process tier a concept that belongs in the schema, or is it better handled as an administrator convention outside the data model?

#### Finding 5: Sub-Domain Codes in Process Context

**PRD ambiguity**

The Master PRD defines sub-domain codes (e.g., CR-PARTNER, CR-MARKETING) that appear in process context — process codes include the sub-domain prefix (CR-PARTNER-INTAKE). In the schema, sub-domains are Domain records with parent_domain_id set (DEC-018). The Process record's domain_id points to the sub-domain Domain record.

The ambiguity is in how the Master PRD import (Section 11.3.1) handles this. The master_prd mapper creates Domain records for both top-level domains and sub-domains, and Process records with domain_id referencing the sub-domain. But the process code includes the sub-domain code as a prefix — is this enforced by the schema, or is it a naming convention enforced only by the interview guide?

**Proposed resolution:** Clarify in Section 11.3.1 or Section 11.12 (Identifier Management) whether process code prefixes are validated against their parent domain code, or whether the naming convention is advisory only.

#### Finding 6: WorkItem Scope for Cross-Domain Entities

**PRD ambiguity**

Entities like Contact and Account span multiple domains. Their entity_prd work items need an entity_id (set) but also optionally a domain_id. Section 6.3 defines WorkItem with both entity_id and domain_id as nullable FKs. For cross-domain entities, domain_id on the entity_prd work item would be NULL — the entity belongs to the client, not a specific domain (DEC-003).

The ambiguity is whether NULL domain_id on an entity_prd work item is the intended design, or whether primary_domain_id (DEC-021) should be used to scope the work item to the entity's primary domain.

**Proposed resolution:** Clarify in Section 6.3 or Section 9.4.3 whether entity_prd work items set domain_id to the entity's primary_domain_id or leave it NULL.

#### Finding 7: Phase Values Are Free Text

**PRD ambiguity**

WorkItem.item_type uses enumerated values (Section 9.9 lists: master_prd, business_object_discovery, entity_prd, domain_overview, process_definition, domain_reconciliation, stakeholder_review, yaml_generation, crm_selection, crm_deployment, crm_configuration, verification). These values implicitly map to phases (Phase 1, Phase 2, etc.), but there is no explicit phase column or mapping table.

The Project Dashboard (Section 14) groups work items by phase for display. The phase-to-item_type mapping is currently implicit — the application must know that entity_prd is Phase 2, process_definition is Phase 5, etc.

The ambiguity is whether this mapping should be explicit in the schema (a phase column on WorkItem, or a phase lookup table) or remain as application logic.

**Proposed resolution:** Evaluate whether a phase column or lookup table adds value, or whether the item_type-to-phase mapping is simple enough to live in application code.

## What This Session Must Produce

For each finding:
1. Discuss the proposed resolution
2. Make a decision (new DEC-* entry if warranted, or agree it's a minor clarification)
3. Identify the specific text changes needed in the L2 PRD

After all findings are resolved, apply the changes to the L2 PRD document and commit.

## Output Format

Each resolved finding should produce:
- The decision or clarification
- The specific L2 PRD section and paragraph to modify
- The new or revised text

New decisions go in Section 15. Resolved ambiguities update the relevant schema or design sections directly.

## Working Style

- Discuss and resolve one finding at a time before moving to the next
- Start with the straightforward constraint additions (Findings 1–3), then the schema addition question (Finding 4), then the PRD ambiguities (Findings 5–7)
- For Finding 4, present the tradeoffs before asking for a decision
- Keep changes minimal — surgical edits to existing text, not section rewrites
