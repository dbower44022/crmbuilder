# Schema Prototype Findings

## 1. Schema Issues Discovered

### 1.1 No Issues Prevented Population

The schema accepted all CBM data without constraint violations. All 805
records inserted cleanly, and `PRAGMA foreign_key_check` returned zero
errors after re-enabling FK enforcement.

### 1.2 Circular FK References Require Deferred Loading

Several tables have circular FK dependencies:

- `Domain.created_by_session_id` -> `AISession.id`, but
  `AISession.work_item_id` -> `WorkItem.id`, and
  `WorkItem.domain_id` -> `Domain.id`

**Impact:** Population scripts must either disable FK checking during
bulk load or insert records with nullable FK columns set to NULL and
backfill later. Both approaches work; the prototype uses
`PRAGMA foreign_keys = OFF` during load.

**Recommendation:** Document the expected load order in the
implementation. Alternatively, consider SQLite deferred FK constraints
if the app uses transactions.

### 1.3 FieldOption Lacks created_at/updated_at

The `FieldOption` table has no timestamp columns, unlike every other
table in the schema. This means option value changes cannot be tracked
through the standard `updated_at` pattern.

**Recommendation:** Add `created_at` and `updated_at` to FieldOption for
consistency. Option value changes are tracked through ChangeLog, but the
missing timestamps break the convention established by all other tables.

### 1.4 Cross-Reference Tables Lack Timestamps

`ProcessEntity`, `ProcessField`, and `ProcessPersona` have no
`created_at` / `updated_at` columns. Since these are populated during
AI session imports, timestamp tracking would support audit queries.

**Recommendation:** Add `created_at` to cross-reference tables, or
document that their creation is tracked solely through the parent
AISession's timestamps.

### 1.5 LayoutRow FK to Field Is Optional But Semantically Required

`LayoutRow.cell_1_field_id` is nullable per schema, but a row with both
cells NULL has no purpose. The schema allows it.

**Recommendation:** Consider adding a CHECK constraint:
`CHECK (cell_1_field_id IS NOT NULL OR cell_2_field_id IS NOT NULL)`

---

## 2. L2 PRD Ambiguities Found

### 2.1 Client Table: `code` Column Not in Task Prompt

The L2 PRD Section 3.1 (Table 1) defines `code TEXT NOT NULL UNIQUE` on
the Client table. The task prompt specified a simpler schema without
`code`. The prototype follows the L2 PRD.

### 2.2 Domain Hierarchy: Sub-Domains vs. Processes

The Master PRD lists CR sub-domains (CR-PARTNER, CR-MARKETING, CR-EVENTS,
CR-REACTIVATE) in the Process Tier Summary table alongside actual
processes. The L2 PRD schema models them as Domain records with
`parent_domain_id`. This is correct but requires care during data
population: the sub-domain codes appear in a "process" context in the
Master PRD but must be inserted as Domains, not Processes.

### 2.3 WorkItem Scope Ambiguity for Cross-Domain Entities

The WorkItem table has `entity_id` and `domain_id` as separate nullable
FKs. For entity_prd work items on cross-domain entities (Contact, Account),
the `domain_id` is NULL because no single domain owns the entity. This is
correct per the schema but means the dashboard query cannot group these
items under a domain. The `primary_domain_id` on Entity could serve as a
fallback, but the L2 PRD does not specify this behavior.

### 2.4 ChangeImpact.action_required Default Timing

Section 12.11 states `action_required` is "set to TRUE when the
administrator flags an impact for revision." Section 12.7.4 says the
same column with `DEFAULT FALSE`. The two are consistent, but the
prototype found that the default is only meaningful when `reviewed = TRUE`.
When `reviewed = FALSE`, `action_required` has no semantic meaning yet.

### 2.5 GenerationLog.document_type Values vs. Table 30

Table 30 lists 8 document types, but the `document_type` column in
Table 31 (GenerationLog) lists different labels:
- Table 30: "Entity Inventory" / Table 31: "entity_inventory"
- Table 30: "Process Document" / Table 31: "process_document"
- Table 30: "Domain PRD" / Table 31: "domain_prd"

These are consistent (Table 31 uses snake_case identifiers), but there is
no CHECK constraint or enum definition in the schema. The application must
enforce valid values.

### 2.6 Dependency Table Has No Unique Constraint

The `Dependency` table allows duplicate `(work_item_id, depends_on_id)`
pairs. While population scripts avoid duplicates, a UNIQUE constraint
would prevent data integrity issues.

**Recommendation:** Add `UNIQUE(work_item_id, depends_on_id)`.

### 2.7 WorkItem Phase Values Are Free Text

The `phase` column is `TEXT NOT NULL` with no CHECK constraint. The
prototype uses "Phase 1" through "Phase 11", but nothing prevents
inconsistent values. A CHECK constraint or normalization to a Phase
lookup table would improve integrity.

---

## 3. Table and Row Counts

### Master Database (`crmbuilder_master.db`)

| Table   | Rows |
|---------|------|
| Client  |    1 |

### Client Database (`cbm_client.db`)

| Table           | Rows | Layer              |
|-----------------|------|--------------------|
| Domain          |    9 | Requirements       |
| Entity          |   11 | Requirements       |
| Field           |  148 | Requirements       |
| FieldOption     |  108 | Requirements       |
| Relationship    |   13 | Requirements       |
| Persona         |   13 | Requirements       |
| BusinessObject  |   22 | Requirements       |
| Process         |   15 | Requirements       |
| ProcessStep     |   56 | Requirements       |
| Requirement     |   85 | Requirements       |
| ProcessEntity   |   19 | Cross-Reference    |
| ProcessField    |   38 | Cross-Reference    |
| ProcessPersona  |   24 | Cross-Reference    |
| Decision        |   26 | Management         |
| OpenIssue       |   15 | Management         |
| WorkItem        |   53 | Management         |
| Dependency      |   97 | Management         |
| AISession       |   21 | Audit              |
| ChangeLog       |    2 | Audit              |
| ChangeImpact    |    3 | Audit              |
| GenerationLog   |    2 | Audit              |
| LayoutPanel     |    3 | Layout             |
| LayoutRow       |   16 | Layout             |
| LayoutTab       |    0 | Layout             |
| ListColumn      |    6 | Layout             |
| **TOTAL**       |**805**|                   |

### Work Item Status Distribution

| Status      | Count |
|-------------|-------|
| complete    |    23 |
| ready       |    13 |
| not_started |    17 |

---

## 4. Validation Query Results

All 10 validation queries (23 sub-queries) returned non-empty results.

| # | Query | Result |
|---|-------|--------|
| 1 | Dashboard: Available Work | 13 ready items across Phases 2, 3, 4, 6 |
| 2a | Dependency Graph: Upstream | 1 upstream dep (MN domain_overview) |
| 2b | Dependency Graph: Downstream | 2 downstream deps (MN-MATCH, MN domain_reconciliation) |
| 3a | Prompt Context: Domain Overview | MN domain overview text retrieved |
| 3b | Prompt Context: Personas | 6 distinct personas across 11 role assignments |
| 3c | Prompt Context: Entities | 4 entities (ACT:40, CON:58, ENG:21, SES:18 fields) |
| 3d | Prompt Context: Prior Processes | 1 prior process (MN-INTAKE: 6 steps, 9 reqs) |
| 4a | Impact: ProcessField | 1 process (MN-MATCH) uses mentorStatus |
| 4b | Impact: LayoutRow | 1 layout row in Mentor Status panel |
| 4c | Impact: ListColumn | 1 list column (position 6, width 10%) |
| 4d | Impact: Persona Discriminator | 3 personas use contactType (Mentor, Member, Client) |
| 5a | DocGen: Process Metadata | MN-INTAKE with triggers and completion criteria |
| 5b | DocGen: Steps | 6 steps with types and performers |
| 5c | DocGen: Requirements | 9 requirements (MN-INTAKE-REQ-001 through 009) |
| 5d | DocGen: Personas | 2 personas (Client as initiator, Client Admin as performer) |
| 5e | DocGen: Entity Usage | 3 entities (ACT created, CON created, ENG created) |
| 5f | DocGen: Field Usage | 14 fields across 3 entities with usage types |
| 6 | Staleness Detection | 1 stale doc (Contact Entity PRD, field changed 2026-04-05) |
| 7 | Unresolved Changes | 1 change set with 1 unreviewed + 1 action_required impact |
| 8 | Work Item Impact Mapping | 1 action_required impact mapped to process_definition:MN-MATCH |
| 9a | Decision Cascade | 20 decisions (2 domain + 18 entity-scoped) |
| 9b | Issue Cascade | 14 issues (2 high, 8 medium, 4 low priority) |
| 10 | Audit Trail | 1 change traced to MR domain_reconciliation session |

### Initial Query 1 Fix

Query 1 initially returned empty because all work items were either
`complete` or `not_started`. The population script was updated to compute
`ready` status by checking which `not_started` items have all dependencies
in `complete` status — simulating the Workflow Engine's status calculation
(L2 PRD Section 9.3). This produced 13 ready items.

---

## 5. Recommendations for Schema Refinements

### High Priority

1. **Add UNIQUE constraint to Dependency:** `UNIQUE(work_item_id, depends_on_id)`
   prevents duplicate dependency edges.

2. **Add timestamps to FieldOption:** `created_at` and `updated_at` for
   consistency with all other tables.

3. **Add CHECK constraint to LayoutRow:** Ensure at least one cell is
   populated: `CHECK (cell_1_field_id IS NOT NULL OR cell_2_field_id IS NOT NULL)`.

### Medium Priority

4. **Add timestamps to cross-reference tables:** `ProcessEntity`,
   `ProcessField`, `ProcessPersona` should have at least `created_at`.

5. **Add CHECK constraint for GenerationLog.document_type:** Enforce the
   8 valid document type identifiers from Table 30/31.

6. **Normalize WorkItem.phase:** Either add a CHECK constraint for
   "Phase 1" through "Phase 11" or store as INTEGER with a mapping.

### Low Priority

7. **Document circular FK load order:** The implementation guide should
   specify the table insertion order or the use of deferred FK checking.

8. **Consider adding `tier` to Process:** The Master PRD assigns tiers
   (Core, Important, Enhancement) to each process, but the Process table
   has no column for this. It could be stored as a field or derived from
   the process document.

9. **Consider `is_sub_domain` computed column or view:** To simplify
   queries that distinguish top-level domains from sub-domains, a view
   filtering on `parent_domain_id IS NOT NULL` would be useful.
