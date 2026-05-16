# Update Prompt: Process Definition Guide v2.6 → v2.7 — Add Entity Relationships Established and Fields Touched From Other Process Documents Sub-Sections to Section 8

## Context

I'm working on the CBM CRM implementation methodology. On 05-16-26 a structural and content review of MN-INTAKE (the Client Intake process document in the Mentoring domain) produced two revisions in sequence: v2.5 → v2.6 (commit `2c82d5b` in `dbower44022/ClevelandBusinessMentoring`) introduced two new opening sub-sections to Section 8 (Data Collected) of the process document, and v2.6 → v2.7 (commit `8a6b076`) added a formal Change Log section. The two opening sub-sections introduced in v2.6 are the methodologically novel contribution that this prompt propagates back into the interview guide.

The new opening sub-sections are:

1. **Entity Relationships Established** — a single consolidated table enumerating every structural relationship created by the process. Columns are Relationship | Related Entities | Link Type | PRD Reference | Established At. This is structurally parallel to (and inspired by) the Section 4 Entity Relationships sub-section that methodology-guide v1.6 canonicalized at the Domain Product Requirements Document level on the same day. The process-document version differs in two ways: (a) it covers relationships *established by this process* rather than *all relationships in the domain*, and (b) its Established At column points to the specific workflow step or system requirement that creates each link.

2. **Fields Touched From Other Process Documents** — a table listing externally-owned fields that this process writes to. Columns are Field Name | Owning Entity | Canonical Reference | Populated By. This is structurally parallel to the "CR-MARKETING fields touched by MN-INTAKE" sub-section that the Mentoring Domain Product Requirements Document v1.1 introduced earlier on 05-16-26. The process-document version makes the same content visible at one level lower in the documentation hierarchy.

These two sub-sections close two gaps that the MN-INTAKE review surfaced:

- Relationships were referenced in requirements and workflow text but were not consolidated anywhere, making the structural picture of what a process creates invisible at a glance.
- Fields owned by other process documents but written to by this process were mentioned only in scattered requirement text, with no traceability to the canonical definition site.

This prompt updates the **Phase 4 Process Definition Interview Guide** to specify both sub-sections as required opening sub-sections of Section 8 (Data Collected) of every process document going forward.

This is a methodology-guide update only. Existing process documents (in MN, MR, CR, FU) are not retroactively propagated by this prompt — they will adopt the convention at their next revision opportunity, similar to how methodology-guide v1.6's Domain Product Requirements Document convention was propagated to the existing Domain Product Requirements Documents in a separate companion prompt.

Before doing any work, please:
1. Read the CLAUDE.md in this repo (`dbower44022/crmbuilder`)
2. Read `PRDs/process/interviews/interview-process-definition.md` (current v2.6) end-to-end so the addition fits the existing structure and tone
3. Optionally consult the precedent prompt for the Domain Reconciliation Guide update at `PRDs/process/interviews/UPDATE-PROMPT-Domain-Reconciliation-Guide-Entity-Relationships.md` for the analogous structural change at the Domain Product Requirements Document level

## The Change

Update `PRDs/process/interviews/interview-process-definition.md` from v2.6 to v2.7, adding two required Section 8 opening sub-section specifications.

## Specific Edits Required

### File: `PRDs/process/interviews/interview-process-definition.md`

#### 1. Header

- Version: `2.6` → `2.7`
- Last Updated: current session timestamp in `MM-DD-YY HH:MM` format

#### 2. "What the Process Document Must Contain" table (currently around line 50)

Update the Section 8 row to reflect the new opening sub-section structure. The current row reads:

> | 8 | Data Collected | Fields this process creates or updates (new data). Grouped by entity with full field-level detail. |

Update to:

> | 8 | Data Collected | Fields this process creates or updates (new data). Opens with two consolidated sub-sections: **Entity Relationships Established** (every structural relationship created by this process in a single table) and **Fields Touched From Other Process Documents** (externally-owned fields written to by this process). Followed by per-entity field tables with full field-level detail. |

#### 3. Section 8 specification — add new sub-section spec at the start

Insert a new sub-section between the existing "Section 8 — Data Collected (New Data)" introduction (currently around line 646) and the existing "### 8.1 Opening" (currently around line 656).

**Suggested new sub-section text** (adapt to match the existing voice and structure of the guide; the AI should not copy this verbatim if a more natural integration is possible):

```markdown
### 8.0 Required Opening Sub-Sections in the Produced Document

Section 8 of the produced process document **must open with two
consolidated sub-sections before the per-entity field tables.** These
sub-sections surface structural context that the per-entity tables
depend on but that would otherwise be invisible at a glance.

These are document-output requirements, not interview activities.
The AI compiles the content for both sub-sections from material
collected throughout the interview (per Sections 8.5 and 8.6 below)
and presents them at the opening of Section 8 in the final document.

**Sub-section 1: Entity Relationships Established.** A single
consolidated table enumerating every structural relationship created
by this process. Required columns:

| Relationship | Related Entities | Link Type | PRD Reference | Established At |

- **Relationship.** Human-readable name in business terms (e.g.,
  "Primary Engagement Contact → Engagement", "Engagement Contacts →
  Engagement"). For relationships with a semantic role, use a
  parenthetical to disambiguate.
- **Related Entities.** The two endpoints of the relationship in
  `Entity1 ↔ Entity2` form (use `↔` for many-to-many, `→` for
  directional).
- **Link Type.** `manyToOne`, `oneToMany`, `manyToMany`, or
  `manyToOne (native Contact-to-Account)` and similar annotations
  for native platform relationships.
- **PRD Reference.** Where the relationship's field is canonically
  defined. If defined in this process document, cite the DAT
  identifier (e.g., `MN-INTAKE-DAT-024`). If owned by another
  document, cite that document's identifier (e.g., `MN-MATCH-DAT-021`
  or `Engagement Entity PRD`).
- **Established At.** The workflow step or system requirement that
  creates the link (e.g., `Workflow Step 2`, `MN-INTAKE-REQ-007`,
  or both separated by a semicolon when both apply).

**Sub-section 2: Fields Touched From Other Process Documents.** A
single consolidated table listing every externally-owned field that
this process writes to. Required columns:

| Field Name | Owning Entity | Canonical Reference | Populated By |

- **Field Name.** The field name as it appears in its canonical
  definition (e.g., `prospectStatus`, `Engagement Contacts`).
- **Owning Entity.** The entity the field lives on (e.g., `Contact`,
  `Engagement`).
- **Canonical Reference.** The document or sub-domain that owns the
  field definition (e.g., `CR-MARKETING Sub-Domain Overview v1.0;
  Contact Entity PRD`).
- **Populated By.** The REQ identifier in this process document that
  causes the field to be written (e.g., `MN-INTAKE-REQ-012`).

These two tables consolidate cross-document and structural references
that would otherwise be scattered across narrative prose, workflow
steps, and individual field descriptions. They make the process
document self-describing at the structural level.

**Source for the tables:**

The Entity Relationships Established table is compiled from the
relationships discovered during the interview (Section 8.5 below).
The Fields Touched From Other Process Documents table is compiled
from the field consistency checks against prior documents (Section
7.4) plus any cross-document field writes discovered during the
workflow walkthrough.

**Precedent:**

This convention was introduced in MN-INTAKE v2.6 (05-16-26,
`dbower44022/ClevelandBusinessMentoring` commit `2c82d5b`), which
produced a 5-row Entity Relationships Established table and a 4-row
Fields Touched From Other Process Documents table for the Client
Intake process. The convention is the process-document analog of
the Section 4 Entity Relationships sub-section canonicalized at the
Domain Product Requirements Document level by methodology-guide v1.6
(`guide-domain-reconciliation.md`) on the same day. Future process
documents follow this pattern.
```

#### 4. Section 8.5 "Relationships Created" — update to reference the consolidated table

The current 8.5 (around line 724) describes capturing relationships as business-language data items. Add a brief sentence at the end of the section noting that all relationships captured here will be consolidated into the Entity Relationships Established sub-section at the opening of Section 8 of the produced document.

Suggested addition (one short paragraph appended to existing 8.5 content):

```markdown
**Output consolidation.** Every relationship captured here is
collected into the Entity Relationships Established sub-section
that opens Section 8 of the produced document (see Section 8.0
above). The conversational capture during this step is the source;
the consolidated table is the output rendering. The AI should not
mention the consolidated table during the interview — it is a
post-interview compilation step.
```

#### 5. Section 7.4 "Check Against Prior Process Documents" — update to flag cross-document writes

The current 7.4 (around line 610) describes verifying field consistency against prior process documents. Add a brief sentence noting that when this process *writes to* (not just references) a field owned by a prior document, that write must be captured for the Fields Touched From Other Process Documents sub-section.

Suggested addition (one short paragraph appended to existing 7.4 content, before "### 7.5 Assign Identifiers"):

```markdown
**Distinction between reference and write.** This step covers
*reading* fields defined by prior documents. When this process
additionally *writes to* such a field (for example, MN-INTAKE
writes to the CR-MARKETING-owned `prospectStatus` field on Contact
during application processing), capture the write as a system
requirement in Section 6 and add the field to the Fields Touched
From Other Process Documents sub-section that opens Section 8 of
the produced document (see Section 8.0). Reads stay in Section 7
proper; writes are surfaced in the Section 8 opening table for
traceability to their canonical definition.
```

#### 6. Changelog section (existing section at the end of the guide)

Add a new v2.7 entry at the top of the Changelog table. Match the format of existing entries. The entry should:

- Cite the MN-INTAKE v2.6 / v2.7 precedent (`dbower44022/ClevelandBusinessMentoring` commits `2c82d5b` and `8a6b076`, 05-16-26)
- Cite methodology-guide v1.6 (`guide-domain-reconciliation.md`) as the Domain Product Requirements Document level analog
- Note that the v2.7 specification covers Section 8 only; Section 7 retains its existing structure for read-only references
- Note that retroactive propagation to existing process documents is out of scope for this guide update and will happen at each document's next revision opportunity

#### 7. Cross-references to verify

After making the edits, search the rest of the guide for any references to Section 8's structure or "Data Collected" that may need wording updates. In particular:

- The Section Checklist (currently around line 192)
- The Completeness Check (currently around line 1003)
- The Summary template (currently around line 1029)
- The Document Production section (currently around line 1049)

Do not invent new content or add scope beyond the two opening sub-sections. Only update wording where existing text references Section 8's structure in a way that the new sub-sections make outdated.

## What NOT to Change

- Do not change the existing Section 8 per-entity field-table specification — it is preserved unchanged, just preceded by the two new opening sub-sections.
- Do not change Section 7 (Process Data) to add a parallel "Relationships Referenced" opening sub-section. The methodology question of whether read-only relationships warrant a consolidated table in Section 7 is open but out of scope for v2.7. Surface it as a possible future extension in the Changelog entry only if natural; do not author it.
- Do not change any other section of the guide (Sections 1, 2, 3, 4, 5, 6, 9, 10, the Critical Rules section, the carry-forward handling block, etc.).
- Do not modify any other guide file (`guide-domain-reconciliation.md`, `guide-entity-definition.md`, `interview-master-prd.md`, `guide-carry-forward-updates.md`, etc.).
- Do not modify the Document Production Process docx file.
- Do not modify any process document in the CBM repo — retroactive propagation across existing process documents is intentionally out of scope.

## Documents to Upload

Upload the following with this prompt:
1. `PRDs/process/interviews/interview-process-definition.md` (current v2.6)

Optionally for reference (but not required, since the precedent is described in this prompt):
2. The current MN-INTAKE.docx v2.7 from the CBM repo at `PRDs/MN/MN-INTAKE.docx` (commit `8a6b076` in `dbower44022/ClevelandBusinessMentoring`) — this is the precedent document showing both sub-sections rendered in their final form.

## Output

Produce an updated `interview-process-definition.md` v2.7 and commit it to the `dbower44022/crmbuilder` repo, replacing the existing v2.6 file. Use a single commit titled `methodology: process definition guide v2.7 — add Entity Relationships Established and Fields Touched From Other Process Documents sub-section requirements` and write a brief commit body noting that the v2.7 update specifies the two opening sub-sections as required for Section 8 of every process document, sourced by the MN-INTAKE v2.6 / v2.7 precedent on 05-16-26.

After the work is committed, state that the methodology-guide update is complete and that the next step is propagation across the existing process documents in MN, MR, CR, and FU as each comes up for revision (no companion bulk-propagation prompt is authored for this convention — adoption is opportunistic rather than dedicated, to avoid version churn across 20+ process documents). Provide a brief summary of what changed for review.
