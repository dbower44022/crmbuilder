# Session Prompt — Migrate Entity Inventory + Domain PRD Parsers to Path B

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-12-26
**Prerequisite:** Read `CLAUDE.md` in both `crmbuilder` and `ClevelandBusinessMentoring` repos.

---

## Context

This is the continuation of the Path A → Path B parser migration that
began on 04-10-26. Two of the four parsers have been migrated:

| Priority | Parser | Status |
|---|---|---|
| 1 | Process document | ✅ Done (Bugs 4+5 fixed) |
| 2 | Entity PRD | ✅ Done (Bug 6 fixed) |
| 3 | Entity inventory | **This session** |
| 4 | Domain PRD | **This session** |

When both are complete, the entire `automation/cbm_import/` directory
can be deleted. That deletion is the final deliverable of this session.

### Established Pattern

All prior migrations followed the same pattern:

1. Inspect the Path A parser to understand what it extracts
2. Inspect the Path B mapper to understand the expected payload shape
3. Inspect real CBM documents to understand source structure
4. Design the adapter one decision at a time (confirm each)
5. Author a `CLAUDE-CODE-PROMPT-*.md` for Claude Code to implement
6. Test against real CBM documents
7. Tombstone the legacy parser with `NotImplementedError`

Reference implementations:
- `automation/importer/parsers/master_prd_docx.py` — first migration
- `automation/importer/parsers/process_doc_docx.py` — process doc (Bugs 4+5)
- `automation/importer/parsers/entity_prd_docx.py` — entity PRD (Bug 6)
- Shared infrastructure: `automation/importer/parsers/__init__.py`
  (`ParseWarning`, `ParseReport`, error classes)

---

## Priority 3: Entity Inventory Parser

### Path A Parser

`automation/cbm_import/parsers/entity_inventory.py` (123 lines)

Extracts:
- `business_objects` — list of `{name, entity_name, status, resolution}`
- `entities` — list of `{name, code, entity_type, is_native}`

**Known gap (Bug 7):** Never tested against the new schema. The parser
uses heuristic column scanning rather than positional parsing, which
makes it fragile. It does not extract domain assignment or discriminator
info.

### Path B Mapper

`automation/importer/mappers/business_object_discovery.py` (224 lines)

Expected payload shape (`business_objects` list, each entry):
- `name` — business concept name
- `classification` — "entity", "process", "persona", "field_value",
  "lifecycle_state", "relationship"
- `entity_name`, `entity_code` — when classification == "entity"
- `entity_type`, `is_native` — entity properties
- `source_domains` — list of domain codes (first entry used for
  `primary_domain_id`)
- `singular_label`, `plural_label` — display labels
- `description` — prose
- `fields` — initial fields for entity-classified BOs
- `options` — enum options within fields
- `process_code` — when classification == "process"
- `persona_code`, `persona_mapping` — when classification == "persona"

Also consumes `envelope.decisions` and `envelope.open_issues`.

### Source Document: CBM-Entity-Inventory.docx v1.4

Located at `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/CBM-Entity-Inventory.docx`.

**Structure:**

- **Table 0** (header): 6-row, 2-col key/value (`Document Type`,
  `Implementation`, `Version`, `Status`, `Last Updated`,
  `Source Documents`).
- **Table 1** (Entity Map): 29 rows x 7 cols. Header:
  `PRD Entity Name | CRM Entity | Native / Custom | Entity Type |
  Discriminator | Disc. Value | Domain(s)`.
  This is the core inventory table. Each row maps a PRD-level business
  concept to a CRM entity. Multiple business concepts can map to the
  same CRM entity (e.g. "Client Contact" and "Mentor Contact" both map
  to Contact). The `Domain(s)` column is comma-separated domain codes.
- **Tables 2–9** (Entity Detail Cards): 5-row, 2-col key/value per
  entity. Header: `Entity Type | <value>`. Rows: `Display Label
  (Singular)`, `Display Label (Plural)`, **`Owning Domain`**,
  `Activity Stream`. Note: the `Owning Domain` row is exactly the
  "Primary Domain" concept from the Entity PRD adapter design. Parse it
  the same way: `Name (CODE)` → extract code.
- **Table 10** (Cross-Domain Matrix): 18 rows x 6 cols. Columns:
  `CRM Entity | MN | MR | CR * | FU * | Domain Count`. Checkmarks
  indicate which domains use each entity. This is a summary/cross-check
  of Table 1's Domain(s) column. The adapter can use it as validation
  but should NOT be the primary data source — Table 1 is primary.
- **Table 11** (Open Issues): 9 rows x 3 cols.
  `ID | Issue | Resolution Path`. Note: 3 columns, not 2.
- **Sections 1–7** structured as Heading 1:
  1. Overview
  2. Entity Map (contains Table 1)
  3. Shared Entity Summary (Heading 2 per shared entity, each has a
     detail card table + prose)
  4. Custom Entity Summary (Heading 2 per custom entity, each has a
     detail card table + prose)
  5. Cross-Domain Entity Matrix (contains Table 10)
  6. Open Issues (contains Table 11)
  7. Next Steps

### Key Design Considerations

1. **The adapter must produce `business_objects` entries, not just
   entities.** The mapper expects the full classification taxonomy. Each
   Table 1 row is a business concept (PRD Entity Name column) that may
   map to an entity (when CRM Entity column is populated) or may be
   unclassified.

2. **Entity detail cards (Tables 2–9) enrich the entity records** with
   labels, owning domain, and activity stream. The adapter must match
   detail cards to their parent entity by position (Section 3 detail
   cards correspond to shared entities, Section 4 to custom entities)
   or by content match (the detail card's heading says "3.1 Contact
   (Native — Person Type)" and the detail card table's Display Label
   should match).

3. **The `Owning Domain` row in detail cards** is the `primary_domain_id`
   source for entity-classified business objects. Parse as `Name (CODE)`
   and include in `source_domains[0]`. This means Bug 7 (untested
   domain assignment) is fixed by this migration — entities will get
   their primary domain from the detail card, just as Bug 6 was fixed
   for Entity PRDs.

4. **Open Issues table has 3 columns** (`ID | Issue | Resolution Path`),
   not the 2-column format used by process docs and entity PRDs. The
   adapter must handle this and include the Resolution Path in the
   description.

5. **New error class:** `EntityInventoryParseError(Exception)` in
   `parsers/__init__.py`.

6. **Work item type:** `business_object_discovery` (matching the mapper
   name, not `entity_inventory`).

7. **Fixture:** Copy `CBM-Entity-Inventory.docx` to
   `automation/tests/fixtures/cbm-entity-inventory-v1.4.docx`. Verify
   internal version is `1.4`.

---

## Priority 4: Domain PRD Parser

### Path A Parser

`automation/cbm_import/parsers/domain_prd.py` (123 lines)

Extracts:
- `domain_code` — from header table or filename heuristic
- `domain_overview_text` — from overview section or full-doc fallback
- `domain_reconciliation_text` — from reconciliation section
- `decisions` — via regex scanning paragraphs and tables for DEC- patterns

**Known gap (Bug 8):** Never tested against the new schema. The parser
extracts only text blobs and decision identifiers. The Domain PRD is
actually a rich, structured reconciliation document (per-process
summaries, consolidated data reference with 7-column field tables,
per-process requirement tables, Decisions Made table with 4 columns,
Open Issues table with 4 columns).

### Path B Mapper

`automation/importer/mappers/domain_reconciliation.py` (159 lines)

Expected payload shape:
- `domain_overview_narrative` — reconciled overview text
- `personas` — list of persona updates with consolidated roles
- `conflict_resolutions` — list of Decision records with affected items
- `consolidated_data_reference` — list of entity→deduplicated-fields
  updates

Also consumes `envelope.decisions` and `envelope.open_issues`.

There is also `automation/importer/mappers/domain_overview.py` (190 lines)
with work_item_type `domain_overview`. The Domain PRD is the
*reconciliation* output, not the overview. The correct mapper is
`domain_reconciliation` with work_item_type `domain_reconciliation`.

### Source Document: CBM-Domain-PRD-Mentoring.docx v1.0

Located at `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MN/CBM-Domain-PRD-Mentoring.docx`.

**Structure:**

- **Table 0** (header): 7-row, 2-col key/value. Rows: `Domain` with
  `Mentoring (MN)` format, `Domain Code`, `Version`, `Status`,
  `Last Updated`, `Source`, `Processes`.
- **Section 1** Domain Overview: prose (Heading 1)
- **Section 2** Personas: Heading 2 per persona with role description
  prose
- **Section 3** Business Processes: Heading 2 per process (3.1 through
  3.5). Each process subsection has Heading 3 sub-sections mirroring
  the process document structure (Process Purpose, Process Triggers,
  Personas Involved, Process Workflow, Process Completion, System
  Requirements, Process Data, Data Collected). Each process has its own
  requirement table (ID | Requirement, 2-col).
- **Section 4** Data Reference: Heading 2 per entity, each with a
  7-column field table (`Field Name | Type | Req | Values | Default |
  ID | Defined In`). Note: 7 columns, not 6 — the extra column is
  `Defined In` which traces each field to its source process document.
  Field tables use the two-row-per-field pattern.
- **Section 5** Decisions Made: Table with 4 columns
  (`ID | Decision | Rationale | Made During`).
- **Section 6** Open Issues: Table with 4 columns
  (`ID | Issue | Question | Needs Input From`).

### Key Design Considerations

1. **The Domain PRD is the richest document type.** It aggregates
   content from all process documents in a domain. The adapter should
   extract all structured content, not just text blobs.

2. **Section 3 per-process requirement tables** should be extracted and
   correlated with the process code from the Heading 2. Each process's
   requirements can be passed through to the mapper for
   reconciliation/validation.

3. **Section 4 field tables are 7-column**, not 6. The `Defined In`
   column is useful metadata — include it in the field dict.

4. **Section 5 Decisions has 4 columns.** Extract as
   `{identifier, description, rationale, made_during, status: "locked"}`.
   The `rationale` and `made_during` are new fields compared to the
   2-column format in other document types.

5. **Section 6 Open Issues has 4 columns.** Extract as
   `{identifier, description, question, needs_input_from, status: "open"}`.

6. **Domain code extraction from header** — parse `Domain` row as
   `Name (CODE)`. `Domain Code` row provides a cross-check. Same
   pattern as process doc adapter.

7. **New error class:** `DomainPrdParseError(Exception)` in
   `parsers/__init__.py`.

8. **Work item type:** `domain_reconciliation` (matching the mapper).

9. **Fixture:** Copy `CBM-Domain-PRD-Mentoring.docx` to
   `automation/tests/fixtures/cbm-domain-prd-mentoring-v1.0.docx`.
   Verify internal version is `1.0`.

10. **The MR Domain PRD also exists** at
    `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MR/CBM-Domain-PRD-MentorRecruitment.docx`.
    Depending on time, it can serve as a second fixture to verify
    the adapter works across domains. If not, defer to follow-up.

---

## Final Step: Delete `automation/cbm_import/`

After both Priority 3 and Priority 4 are migrated, tombstoned, and
verified, **delete the entire `automation/cbm_import/` directory**. All
four Path A parsers will be tombstoned, and the only consumers of the
module are the tombstoned call sites.

Also delete or archive any tests in `automation/tests/` that exclusively
test Path A code (i.e. test files whose only remaining tests are
skipped due to tombstoning). Clean tests should still reference the Path
B adapters.

---

## Approach

Work through Priority 3 and Priority 4 sequentially, following the
established one-decision-at-a-time review process. For each:

1. Review the source document structure (already inspected above)
2. Walk design decisions one at a time
3. Author the CLAUDE-CODE-PROMPT
4. Doug runs it in Claude Code
5. Review results

After both are verified, author the final cleanup CLAUDE-CODE-PROMPT
to delete `automation/cbm_import/` and clean up the test suite.

---

## CBM File Locations

Doug's local clone of the CBM repo is at
`~/Dropbox/Projects/ClevelandBusinessMentors/` (short name, ending in
`Mentors`). The GitHub repo is `dbower44022/ClevelandBusinessMentoring`
(long name). Use the short name for local paths; use the long name for
GitHub references.

---

## Current Database State

After the 04-12-26 session, `automation/data/cbm-client.db` reflects
all Path B imports including Bug 5 (process domain assignment) and
Bug 6 (entity primary domain) fixes verified.
