# SESSION PROMPT: CRM Builder Automation — Document Generator Design

## Session Goal

Design Section 13 (Document Generator) of the CRM Builder Automation L2 PRD. The output will replace the placeholder in the existing L2 document.

## Context

### What is the Document Generator?

The Document Generator produces Word documents and YAML program files from the current database state. It is the reverse of the Import Processor — where the Import Processor takes AI session output and writes it to the database, the Document Generator reads from the database and produces formatted deliverables.

The generator addresses the L1 PRD's core vision (Section 3): "Documents are generated on demand from the current database state. An Entity PRD, a Process Document, a Domain PRD, or a YAML program file can be regenerated at any time and will always reflect the current definitions. Documents are never edited directly — all changes flow through the managed change process."

The success criterion (L1 Section 9) is: "Any PRD document or YAML file can be regenerated from the database and match the expected content."

### Key Documents

Read these files from the crmbuilder repo:
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` (strategic vision — see Sections 3, 6.5, 7.6, 9)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (detailed design — Sections 3–12 are complete)

Section 10.5.2 (Type-Specific Payloads) is particularly important because it defines the data categories for each work item type — the Document Generator queries these same data categories to produce documents.

Section 12.10 (Document Staleness Detection) establishes how the Impact Analysis Engine determines which documents are stale and need regeneration.

### How Document Generation Works Today

Today, documents are produced manually through AI conversations and Word document templates:
- The administrator conducts an AI session in Claude.ai, which produces document content
- For process documents and Entity PRDs, Node.js generator templates (`generate-process-doc-template.js`, `generate-entity-prd-template.js`) in `PRDs/process/templates/` produce formatted Word documents from data objects
- These templates use the `docx` npm package and are data-driven: a data object at the top defines the content, a rendering engine below produces the formatted .docx
- Generated documents follow strict formatting standards (Arial font, #1F3864 headers, field tables with alternating shading, etc.)

In the automated flow:
1. Data lives in the database, imported through the Import Processor (Section 11)
2. The administrator requests document generation for a specific work item or document type
3. The Document Generator queries the database for all data relevant to that document type
4. The generator renders the data through a formatting template, producing a Word document or YAML file
5. The output is saved to the client's project folder

### Document Types and Their Database Sources

The generator must support producing these document types, each backed by different database tables:

**Master PRD** — Organization overview (from Client.organization_overview), personas (from Persona), domains and sub-domains (from Domain with parent_domain_id), processes per domain (from Process), Cross-Domain Services (from Domain where is_service = TRUE), system scope.

**Entity Inventory** — Entity list with classification and mapping (from Entity, BusinessObject). Shows how business objects map to CRM entities.

**Entity PRD** — One per entity. Entity metadata (from Entity), fields with full detail (from Field, FieldOption), relationships (from Relationship), dynamic logic, layout guidance (from LayoutPanel, LayoutRow, LayoutTab), decisions and open issues scoped to this entity (from Decision, OpenIssue where entity_id matches).

**Domain Overview** — One per domain. Domain purpose (from Domain.domain_overview_text), personas in domain (from ProcessPersona joined through Process.domain_id), process inventory (from Process where domain_id matches), data reference (from ProcessEntity, ProcessField joined through domain processes).

**Process Document** — One per process. Process metadata (from Process), triggers, personas (from ProcessPersona), workflow steps (from ProcessStep), requirements (from Requirement), data references (from ProcessEntity, ProcessField), decisions and open issues scoped to this process.

**Domain PRD (Reconciliation Output)** — One per domain. Reconciliation narrative (from Domain.domain_reconciliation_text), consolidated personas, conflict resolutions, consolidated data reference, cross-process gaps. Decisions and open issues scoped to this domain.

**YAML Program Files** — Per entity. Field definitions (from Field, FieldOption), relationship configurations (from Relationship), layout definitions (from LayoutPanel, LayoutRow, LayoutTab, ListColumn). Output format is YAML, not Word.

**CRM Evaluation Report** — Platform recommendations, requirements coverage. This is the only document type that may include product names.

### Integration Points with Other Components

**Impact Analysis Engine (Section 12):** Section 12.10 establishes document staleness detection. The Document Generator consumes this information to present the administrator with a list of stale documents. A document is stale when ChangeLog.changed_at > WorkItem.completed_at for any record owned by that work item.

**Workflow Engine (Section 9):** The Document Generator should only produce final documents for work items in complete status. The question of whether draft/preview generation is available for in-progress work items is a design decision for this section.

**Import Processor (Section 11):** The Import Processor populates the database; the Document Generator reads from it. They are inverse operations. The structured output format (Section 10.5.2) defines the data categories that exist in the database — the Document Generator queries the same categories.

**Prompt Generator (Section 10):** The Prompt Generator reads from the database to assemble prompts; the Document Generator reads from the database to assemble documents. Both query similar data but for different purposes and in different output formats.

### Existing Templates and Formatting Standards

Two generator templates already exist in the crmbuilder repo (`PRDs/process/templates/`):
- `generate-process-doc-template.js` — Produces process documents using the `docx` npm package
- `generate-entity-prd-template.js` — Produces Entity PRDs, data-driven with an ENTITY object at top

These templates encode the document formatting standards:
- Font: Arial throughout
- Colors: Header bg #1F3864, header text white; title/heading color #1F3864; alt row shading #F2F7FB; table borders #AAAAAA
- Body: 11pt; small 10pt; ID/description 8pt
- US Letter, 1" margins
- Field tables: two rows per field with alternating shading
- Requirement tables: two columns (ID + Requirement)
- Human-readable-first identifier rule in all contexts
- Workflow diagrams embedded if PNG exists

### Locked Decisions Relevant to This Section

- **DEC-005:** All changes go through managed process — documents are generated from the database, never edited directly.
- **DEC-029:** Structured output format is JSON — the Import Processor stores JSON; the Document Generator reads the committed database records, not the raw JSON.
- **DEC-032:** Prompt templates stored as files per work item type — establishes the pattern of file-based templates.
- **DEC-039:** Post-commit analysis for imports, pre-commit for direct edits — the Impact Analysis Engine provides staleness information that the Document Generator consumes.

### What the L1 PRD Says

**Section 6.5 (Document Generator):** "Produces Word documents and YAML program files from the current database state. Supports generating Entity PRDs, Process Documents, Domain PRDs, the Master PRD, and YAML program files. Documents are always regenerable and never edited directly."

**Section 7.6 (Document Generation on Demand):** "Any document type can be generated from the current database state at any time: Master PRD, Entity PRDs, Process Documents, Domain PRDs, and YAML program files. Generated documents always reflect the current definitions. If the database has changed since the last time a document was generated, the application flags which documents are stale."

**Section 9 (Success Criteria):** "Any PRD document or YAML file can be regenerated from the database and match the expected content."

## What This Session Must Produce

Design the Document Generator section covering:

1. **Overview** — What is the generator's role? When does it run? What are its inputs and outputs? How does it relate to the existing manual template approach?

2. **Document type catalog** — Which document types does the generator support? For each type, what is the output format (Word or YAML), what work item type produces it, and what is the document's purpose? Include all types listed above plus any others identified during design.

3. **Data query layer** — For each document type, what database tables are queried and how is the data assembled? This is the reverse mapping of the Import Processor's payload-to-record mapping (Section 11.3). Define the query logic that produces a complete data set for each document type.

4. **Template architecture** — How are document templates structured? Are they code-based (like the existing JS templates), declarative, or a hybrid? Where are they stored? How are they versioned? How do they encode the formatting standards?

5. **Rendering pipeline** — What is the step-by-step process from "administrator requests generation" to "document file produced"? How does the generator assemble data, apply the template, and produce output?

6. **Staleness detection and presentation** — Building on Section 12.10, how does the generator present stale documents to the administrator? How does the administrator request regeneration? What happens to the previous version of a generated document?

7. **Output management** — Where are generated files stored? How are they named? How does the generator handle versioning (e.g., does it overwrite or create a new file)? How does the file path convention work with the existing project folder structure?

8. **Draft vs. final generation** — Can the administrator generate a preview or draft document for a work item that is still in progress? Or is generation restricted to completed work items? What are the tradeoffs?

9. **YAML generation specifics** — How does YAML output differ from Word document output? What is the YAML file structure? How do YAML files map to the existing CRM Builder deployment workflow (the programs/ folder)?

10. **Relationship to existing templates** — The crmbuilder repo already has `generate-process-doc-template.js` and `generate-entity-prd-template.js`. Does the automated system reuse, extend, or replace these? How is backward compatibility maintained?

11. **Generation tracking** — How is the generation event recorded? Should there be a GenerationLog table tracking when each document was generated and from what database state? How does this interact with staleness detection?

12. **Workflow diagram integration** — Process documents embed workflow diagram PNGs. How does the generator handle diagrams? Are they stored in the database or referenced from the file system? How does the generator know whether a diagram exists?

13. **Schema changes** — Does this section require any new tables or columns beyond what is already defined?

## Output Format

Produce the content as structured text organized by subsection (13.1, 13.2, etc.) that can be incorporated into the L2 PRD Word document. Include any new decisions that should be added to Section 15 and any new open issues for Section 16.

## Working Style

- Discuss and resolve one design question at a time before moving to the next
- Ask for confirmation before finalizing each subsection
- If a design question has multiple viable approaches, present the options with tradeoffs and ask for a decision
- Flag any schema changes needed (new columns, new tables, modified constraints)
- Reference the existing generator templates when discussing template architecture
- Consider the relationship between the Document Generator and the existing CRM Builder docgen tooling (in `tools/docgen/`)
- Keep the section consistent in depth and style with Sections 9–12
