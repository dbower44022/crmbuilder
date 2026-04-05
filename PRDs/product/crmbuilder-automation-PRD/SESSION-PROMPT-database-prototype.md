# SESSION PROMPT: CRM Builder Automation — Database Schema Prototype

## Session Goal

Create a working SQLite database implementing the schema defined in the CRM Builder Automation L2 PRD (Sections 2–8, with schema changes from Sections 9–13), populate it with data extracted from the Cleveland Business Mentors (CBM) implementation documents, and validate the schema through representative queries.

## Context

### Why This Step

The L2 PRD design phase is complete — Sections 9 through 14 define the Workflow Engine, Prompt Generator, Import Processor, Impact Analysis Engine, Document Generator, and User Interface. Before implementation begins, the database schema needs validation with real data. CBM is the live proof-of-concept implementation with substantial existing documentation: a Master PRD, Entity Inventory, five Entity PRDs, two complete domains with process documents and reconciled Domain PRDs, and a partial third domain.

This prototype proves the schema can hold the actual data CBM has produced, that the relationships between tables work as designed, and that the queries the application will need (dashboard status, prompt context assembly, impact analysis tracing, document generation) return correct results.

### Key Documents

**Schema source (crmbuilder repo):**
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` — Sections 2–8 define the base schema; Sections 9.9, 10.10, 12.11, and 13.13 define schema changes

**CBM data sources (ClevelandBusinessMentoring repo):**
- `PRDs/CBM-Master-PRD.docx` — Client overview, domains, processes, personas
- `PRDs/CBM-Entity-Inventory.docx` — Entity list with classifications and domain participation
- `PRDs/entities/Contact-Entity-PRD.docx` — 16 native + 38 custom fields, 7 contactType values
- `PRDs/entities/Account-Entity-PRD.docx` — 19 native + 21 custom fields, 3 accountType values
- `PRDs/entities/Engagement-Entity-PRD.docx` — 19 custom fields, status-driven dynamic logic
- `PRDs/entities/Session-Entity-PRD.docx` — 10 native + 8 custom fields
- `PRDs/entities/Dues-Entity-PRD.docx` — Dues entity
- `PRDs/MN/MN-INTAKE.docx` through `PRDs/MN/MN-CLOSE.docx` — 5 MN process documents
- `PRDs/MN/CBM-Domain-PRD-Mentoring.docx` — MN Domain PRD (reconciliation output)
- `PRDs/MR/MR-RECRUIT.docx` through `PRDs/MR/MR-DEPART.docx` — 5 MR process documents
- `PRDs/MR/CBM-Domain-PRD-MentorRecruitment.docx` — MR Domain PRD
- `PRDs/CR/CBM-Domain-Overview-ClientRecruiting.docx` — CR Domain Overview
- `PRDs/CR/PARTNER/CBM-SubDomain-Overview-Partner.docx` — Partner sub-domain overview
- `PRDs/services/NOTES/NOTES-MANAGE.docx` — Notes service process document

### What the L2 PRD Defines

**Section 2 — Two-Database Model:** Master database (one Client table) stored in app data directory. Per-client SQLite database stored at path from Client record.

**Section 3 — Master Database:** Client table with id, name, description, database_path, created_at, updated_at. Schema changes add organization_overview (TEXT), crm_platform (TEXT).

**Section 4 — Requirements Layer (9 tables):** Domain, Entity, Field, FieldOption, Relationship, Persona, BusinessObject, Process, ProcessStep, Requirement. Schema changes add: Domain.parent_domain_id, Domain.is_service, Domain.domain_overview_text, Domain.domain_reconciliation_text; Entity.primary_domain_id; Field.is_native.

**Section 5 — Cross-Reference Layer (3 tables):** ProcessEntity, ProcessField, ProcessPersona.

**Section 6 — Management Layer (4 tables):** Decision, OpenIssue, WorkItem, Dependency. Schema changes add: WorkItem.status_before_blocked.

**Section 7 — Audit Layer (3 tables):** AISession, ChangeLog, ChangeImpact. Schema changes add: ChangeImpact.action_required.

**Section 8 — Layout Layer (4 tables):** LayoutPanel, LayoutRow, LayoutTab, ListColumn.

**Section 13.13 — GenerationLog (1 table):** New table in the Audit layer for document generation tracking.

Total: 1 master database table + 24 client database tables.

## What This Session Must Produce

### Deliverable 1: Schema Creation Script

A Python script (`create_schema.py`) that creates both databases:
1. Master database (`crmbuilder_master.db`) with the Client table
2. A CBM client database (`cbm_client.db`) with all 24 tables

The script must implement:
- All columns from Sections 3–8 including nullable/not-null constraints, defaults, and foreign keys
- All schema changes from Sections 9.9, 10.10, 12.11, and 13.13
- Common conventions: every table has id (INTEGER PRIMARY KEY AUTOINCREMENT), created_at (TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP), updated_at (TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)
- Tables with AI session origin: created_by_session_id (INTEGER, nullable, FK to AISession.id)
- Foreign key enforcement enabled (PRAGMA foreign_keys = ON)

### Deliverable 2: Data Population Script

A Python script (`populate_cbm.py`) that reads the CBM documents and populates both databases with real CBM data. The script should populate:

**Master database:**
- Client record for CBM with organization_overview from the Master PRD

**Requirements Layer — full population:**
- All Domain records (MN, MR, CR, FU) including sub-domains (CR has PARTNER and MARKETING sub-domains) and the Notes service
- All Entity records (Contact, Account, Engagement, Session, Dues, plus any others from Entity Inventory)
- All Field records from Entity PRDs — Contact and Account fully, others as available
- All FieldOption records for enum/multiEnum fields
- All Relationship records from Entity PRDs
- All Persona records from Master PRD
- BusinessObject records from Entity Inventory classifications
- All Process records from Master PRD
- ProcessStep records from MN domain process documents (at minimum MN-INTAKE and MN-MATCH fully populated)
- Requirement records from MN domain process documents (at minimum MN-INTAKE and MN-MATCH)

**Cross-Reference Layer — representative population:**
- ProcessEntity records for MN domain processes showing which entities each process uses
- ProcessField records for MN-INTAKE showing which fields are collected/displayed/evaluated
- ProcessPersona records for MN domain processes

**Management Layer — full structure:**
- Decision records — at minimum the MN and MR reconciliation decisions
- OpenIssue records — key open issues from Entity PRDs and process docs
- WorkItem records for the entire CBM project covering all 11 phases
- Dependency records wiring the complete dependency graph per Section 9.4

**Audit Layer — sample records:**
- AISession records simulating the sessions that produced each document (master_prd, business_object_discovery, entity_prd sessions, process_definition sessions)
- ChangeLog entries for a representative subset (at minimum the Contact entity creation and a field update)
- ChangeImpact entries simulating one impact analysis result

**Layout Layer — representative population:**
- LayoutPanel, LayoutRow, LayoutTab, and ListColumn records for at least the Contact entity

**GenerationLog — sample records:**
- Generation records for at least two document types

### Deliverable 3: Validation Query Script

A Python script (`validate_schema.py`) that runs queries exercising the key application paths and prints results:

1. **Dashboard query** — Available work calculation per Section 9.6: show Continue Work (in_progress) and Ready to Start (ready) items ordered by phase then domain sort_order
2. **Dependency graph query** — For a specific work item, show all upstream dependencies and their statuses, and all downstream dependents
3. **Prompt context assembly** — For a process_definition work item, assemble the context per Section 10.3.5: domain overview text, personas, entities with fields, prior process data
4. **Impact analysis trace** — For a Field change, query all cross-reference paths per Section 12.3.1: ProcessField, LayoutRow, ListColumn, Persona references
5. **Document generator query** — For a Process Document, assemble the data per Section 13.3.5: process with steps, personas, requirements, entity/field cross-references
6. **Staleness detection** — Find work items whose documents are stale per Section 13.6.1: ChangeLog entries post-dating the most recent GenerationLog
7. **Unresolved changes** — Find change sets with unreviewed ChangeImpact records per Section 12.7.3
8. **Work item mapping** — Map flagged ChangeImpact records to affected work items per Section 12.8.1
9. **Decision and issue inclusion** — For a process_definition work item, find relevant decisions and issues per Section 10.4 relevance cascade
10. **Audit trail** — Trace a field value back to the AISession that created it, per Section 7.7

Each validation query should print a labeled result showing the query returned meaningful data. Queries that return empty results or errors indicate schema problems.

## Working Style

- Read CLAUDE.md from the crmbuilder repo first
- Read the L2 PRD schema sections (2–8) and schema change sections (9.9, 10.10, 12.11, 13.13) before writing any code
- Read CBM documents to extract actual data values — do not invent placeholder data when real data is available
- Create the schema script first and run it to verify table creation
- Create the population script next and run it, fixing any constraint violations
- Create the validation script last and run all 10 queries
- If a schema issue is discovered during population or validation, fix the schema and document what changed and why
- Discuss issues one at a time and wait for confirmation before proceeding

## Scope Boundaries

**In scope:**
- All 25 tables (1 master + 24 client) with complete column definitions
- CBM data population from existing documents — use real identifiers, real field names, real process steps
- Validation queries proving the schema supports all major application paths
- Documentation of any schema issues discovered

**Out of scope:**
- Application code (no PySide6, no UI, no workflow engine implementation)
- Schema migration tooling (ISS-003)
- Automated document parsing — the population script can use hard-coded data extracted by reading the documents
- Full data migration of every field from every document — representative coverage is sufficient
- Layout data beyond one or two entities — layout details can be expanded later

## Output Location

All scripts and database files should be created in a `prototype/` directory within the crmbuilder repo at `prototype/`. The directory is temporary — it validates the schema design and will not become production code. The scripts serve as executable documentation of the schema.

## Success Criteria

1. Both databases create without errors with foreign key enforcement on
2. CBM data populates without constraint violations
3. All 10 validation queries return non-empty, correct results
4. The dependency graph shows the correct phase ordering for CBM's project
5. Cross-reference queries trace from a field change to affected processes
6. The prompt context assembly query produces a coherent context for a process_definition work item
7. Any schema issues discovered are documented with the resolution
