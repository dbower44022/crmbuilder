# CRM Builder — Entity PRD Interview Guide

**Version:** 1.1
**Last Updated:** 04-21-26
**Purpose:** AI interviewer guide for Phase 5 — Entity PRDs
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `guide-carry-forward-updates.md` — used when this interview discovers that an already-completed process document, Domain Overview, or Entity PRD needs to change.
**Authoring contract:** `authoring-standards.md` (Section 11 review checklist).

---

## How to Use This Guide

This guide is loaded as context for an AI conducting an Entity PRD
interview with the CRM administrator. The AI should read this guide
fully before beginning.

**The AI's role is that of a skilled analyst** — compiling the full
field list for the entity from the Phase 4 process documents,
proposing a structured model, and working with the administrator to
confirm or refine it one decision at a time. The AI brings
consolidation and thoroughness. The administrator brings domain
knowledge about how the entity should map to the CRM platform.

**One entity per conversation.** Each conversation produces exactly
one Entity PRD. Complex shared entities (Contact, Account) deserve a
dedicated session; do not bundle two entities into one conversation.

**Session length:** 45–75 minutes. Stop at 90 minutes regardless of
completion — schedule a follow-up rather than pushing through
fatigue.

**Input (required):**

- Master PRD
- Entity Inventory
- Persona source — either a separate Persona Inventory document (the spec-compliant Phase 3 output) or the Master PRD's Personas section with backing captured in the Master PRD or the implementation's `CLAUDE.md`. Both are accepted (see `guide-domain-overview.md` Persona Source Compatibility).
- Domain Overview for every domain that lists this entity in its Data Reference
- Every Phase 4 process document that uses this entity

**Input (optional, use when available):**

- Every previously-completed Entity PRD for entities that have a relationship to this entity. Common on cross-domain entities — the Contact Entity PRD's decisions create requirements the later Account Entity PRD must incorporate.

**On ordering with Phase 4.** Per process doc Rule 5.1, Entity PRDs
are produced **after** Phase 4 process documents, not before. This
was sometimes described as "retroactive" in earlier methodology
drafts; it is now the normal order. Process documents surface the
fields an entity actually needs, the enum values that actually
appear, and the relationships that actually matter. Writing Entity
PRDs before process documents guesses at these; writing them after
records them. The Data Reference section of the Domain Overview
(`guide-domain-overview.md` v1.1) explicitly annotates entities
without Entity PRDs as "pending Phase 5" — resolving those
annotations is the work of this session.

**Output:** One Word document — the Entity PRD — committed to the
implementation's repository at
`PRDs/entities/{EntityName}-Entity-PRD.docx`.

**Cardinality:** One Entity PRD per entity in the reconciled Entity
Inventory, including entities owned by Cross-Domain Services.

---

## What the Entity PRD Must Contain

The Entity PRD has ten required sections. An Entity PRD is not
complete until all ten sections are present and meet their
respective standards.

| # | Section | Content |
|---|---------|---------|
| 1 | Entity Overview | CRM entity name, Native/Custom, entity type, display labels (singular/plural), purpose description, activity stream on/off, contributing domains, and — for shared entities — discriminator field and value list. |
| 2 | Native Fields | Fields that already exist on the entity because of its type. Documented, not created. For each: native field name, PRD-name mapping, type, domains/processes that reference it. |
| 3 | Custom Fields | Fields created via YAML. The primary field table that Phase 9 YAML Generation reads. Full field-level detail per every field. |
| 4 | Relationships | All relationships involving this entity, consolidated from every contributing domain. Relationship name, related entity, link type, link names (both sides), labels (both sides), and source references. |
| 5 | Dynamic Logic Rules | Consolidated visibility and required-when rules, grouped by discriminator value for shared entities or by condition for non-shared entities. |
| 6 | Layout Guidance | Suggested panel/tab grouping for the entity's detail view. Recommendation only — final layout is set during YAML generation. |
| 7 | Implementation Notes | Workflow and automation rules, calculated-field formulas, validation beyond required/type, access-control notes. |
| 8 | Open Issues | Unresolved questions specific to this entity's implementation. |
| 9 | Decisions Made | Decisions made during this session. Each has identifier `{ENTITY-CODE}-DEC-NNN`, description, and rationale. Cross-entity decisions are cross-referenced. |
| 10 | Interview Transcript | Complete-but-condensed Q/A record of the session, organized by topic area with inline Decision callouts. Format specified in "Interview Transcript Format" below. |

**Completeness standard.** An Entity PRD is complete when every
native field for the entity's type is documented in Section 2; every
custom field defined by any Phase 4 process document that uses this
entity appears in Section 3 with full field-level detail; every
relationship is consolidated in Section 4; every decision is recorded
in Section 9 and appears as an inline Decision callout in Section 10;
and Section 10 captures every substantive exchange from the session.

**Field-level detail standard (Section 3).** Each custom field
entry must include field name (lowerCamelCase for implementation),
PRD field name and ID, type, required status (Yes/No/conditional —
with condition stated), allowed values (for enum/multiEnum), default
value, description, domain(s) that define or reference the field,
type-specific status (Yes/No — for shared entities), visibility rule
(for type-specific fields), and implementation notes (readOnly,
audited, min/max, unique, etc.).

---

## Critical Rules

1. **One entity per conversation.** Never attempt to define multiple entities in one session.

2. **Do not invent fields.** The Entity PRD consolidates what the Master PRD, Domain Overviews, and process documents define. If a field seems to be missing, it becomes an open issue or a carry-forward request — the AI does not silently add it.

3. **Native fields are documented, not created.** Distinguish clearly between native fields (already on the platform because of the entity type) and custom fields (created via YAML). Duplicate field creation is the most common downstream error and is prevented only here.

4. **Cross-domain consolidation is mandatory.** For entities that span multiple domains (Contact, Account, or any entity whose Entity Inventory row lists more than one source domain), the Entity PRD must include fields from every contributing domain. If a contributing domain has not yet completed its process documents, flag the entity as provisional and list the incomplete domains in Section 8.

5. **Identifiers are preserved.** Field identifiers assigned in process documents carry forward unchanged. The Entity PRD adds the lowerCamelCase implementation name alongside the PRD identifier — it does not reassign or renumber identifiers.

6. **No product names.** Entity PRDs are business-language documents. Do not mention specific CRM platforms (EspoCRM, Salesforce, HubSpot, etc.) in any section. Native/Custom and Entity Type are platform-neutral classifications and remain permitted.

7. **Batched decisions.** Do not ask about each field individually. Compile the full field inventory, sort fields into three buckets (clearly shared, clearly type-specific, needs discussion), confirm the first two buckets as groups, and resolve the third bucket one question at a time. See the batched-decision procedure in Section 3 below.

8. **One topic at a time.** When multiple items in the needs-discussion bucket are pending, present them sequentially, not as a batch. Await confirmation on each before moving to the next (process doc Section 7.4).

9. **Confirmation gates.** After completing each section of the Entity PRD, explicitly state the next section and ask for confirmation before proceeding. Never advance silently (process doc Section 7.3).

10. **Scope-change protocol.** If the interview surfaces a missing entity, a missing field on an already-defined entity, or a structural problem with the Entity Inventory, pause the session and follow the protocol in "Handling Discovered Updates to Prior Documents" below. Do not absorb scope changes into the current Entity PRD (process doc Section 10).

11. **One deliverable per conversation.** Every Entity PRD interview produces exactly one committed Word document at the repository path stated above (process doc Section 7.5).

---

## Before the Interview Begins

### Context Review

Before speaking to the administrator, read every input document. Specifically:

- Read the Master PRD's entry for this entity in the Key Data Categories of every domain that lists it.
- Read the Entity Inventory row for this entity: Native/Custom (preliminary), source domains, disambiguation notes.
- Read every Phase 4 process document that uses this entity. For each, note every field mentioned, every status value mentioned, every relationship mentioned, and every identifier assigned.
- Read every previously-completed Entity PRD for related entities. Note any decisions that create requirements for the current entity (example: "Primary Contact is on the Account-Contact relationship" in the Contact Entity PRD creates a requirement that the Account Entity PRD must implement).

### Session-Start Checklist (process doc Section 7.1)

1. Ask which implementation is being worked on.
2. Read the implementation's `CLAUDE.md` for current state.
3. Identify the current phase and step — this session is Phase 5, Entity PRD for `{EntityName}`.
4. State this explicitly and confirm with the administrator before proceeding.

### Verify Inputs

State verification before proceeding:

> "For the {EntityName} Entity PRD, I need to confirm the following are available:
>
> **Required:**
> - Master PRD: ✓ / ✗
> - Entity Inventory: ✓ / ✗
> - Persona source — Persona Inventory document, or Master PRD Personas section with backing: ✓ / ✗
> - Domain Overviews for every contributing domain: {list, with ✓ / ✗ per domain}
> - Phase 4 process documents that use this entity: {list, with ✓ / ✗ per document}
>
> **Optional — will be used if available:**
> - Previously-completed Entity PRDs for related entities: {list, with ✓ / ✗}
>
> Is this the complete set?"

If any required input is missing, stop. Do not begin the interview.

### State the Plan

> "Here is how this session will work:
>
> 1. I will present the Entity Overview (Section 1) for your confirmation — entity type, discriminator for shared entities, and activity stream.
> 2. I will present the compiled Native Field list (Section 2) for your confirmation.
> 3. I will compile every custom field from the source documents and sort them into three buckets: clearly shared across all types, clearly type-specific, and needs discussion. You will confirm the first two buckets as groups; we will walk through the third bucket one field at a time.
> 4. I will present the Relationships (Section 4), Dynamic Logic (Section 5), Layout Guidance (Section 6), and Implementation Notes (Section 7) — each for your confirmation.
> 5. We will collect Open Issues (Section 8) and capture Decisions (Section 9).
> 6. I will produce the Entity PRD document.
>
> Ready?"

---

## Interview Structure

### Section Checklist

The interview walks through the ten sections of the Entity PRD in
order. The AI checks each off as it is completed.

- [ ] Section 1 — Entity Overview
- [ ] Section 2 — Native Fields
- [ ] Section 3 — Custom Fields
- [ ] Section 4 — Relationships
- [ ] Section 5 — Dynamic Logic Rules
- [ ] Section 6 — Layout Guidance
- [ ] Section 7 — Implementation Notes
- [ ] Section 8 — Open Issues
- [ ] Section 9 — Decisions Made
- [ ] Section 10 — Interview Transcript

---

## Section 1 — Entity Overview

Compile and present:

- **CRM entity name.** From the Entity Inventory.
- **Native or Custom.** The Entity Inventory is preliminary. This session makes the determination authoritative based on the entity's full requirements. If every field that the entity needs is already covered by a platform-native entity type, the entity is Native; if any custom field is needed, the entity is Custom.
- **Entity type.** Base, Person, Company, Event, or the platform-neutral equivalent. The type controls which built-in fields are available.
- **Display labels.** Singular and plural.
- **Purpose.** Two or three sentences describing what the entity represents and what business role it plays.
- **Activity stream.** Yes or No. Entities that persist and accumulate user actions (Contact, Engagement) typically have streams on. Lookup entities typically do not.
- **Contributing domains.** Every domain whose process documents use this entity.
- **Discriminator (shared entities only).** Field name and full value list. Values must cover every business concept that maps to this entity across every contributing domain, including any anticipated in future domains.

Present to the administrator as a single confirmation:

> "Here is the Entity Overview for {EntityName}:
>
> - Native/Custom: {determination and rationale}
> - Entity type: {type}
> - Display labels: {singular} / {plural}
> - Purpose: {text}
> - Activity stream: {Yes/No}
> - Contributing domains: {list}
> - Discriminator: {field name and value list, or N/A}
>
> Does this look right?"

Resolve any disagreement before moving to Section 2.

---

## Section 2 — Native Fields

For the determined entity type, compile the full list of native
fields. For each native field, determine which PRD field name(s)
from the source documents map to it, and which processes reference
it.

Present as a table:

| Native Field Name | PRD Name(s) | Type | Referenced By |
|---|---|---|---|
| firstName | First Name | varchar | MN-INTAKE, MN-ENGAGE |

> "Here are the native fields for {entity type}. I have mapped each to the PRD name(s) used in the process documents. Anything missing or mis-mapped?"

Being thorough here prevents the single most common downstream
error: attempting to create a field in YAML that already exists
natively.

---

## Section 3 — Custom Fields

This is the primary section of the Entity PRD. It drives Phase 9
YAML Generation.

### 3.1 Compile the Full Field Inventory

From every Phase 4 process document that uses this entity, extract
every field mentioned. Deduplicate across process documents — if
two processes reference the same field, capture the union of their
specifications and note both sources.

### 3.2 Three-Bucket Sort

For each custom field, assign it to one of three buckets:

- **Clearly shared.** Field is defined in multiple domains or applies to all discriminator values of a shared entity. Example for Contact: firstName, lastName, emailAddress, phoneNumber, address.

- **Clearly type-specific.** Field is defined in only one domain for only one discriminator value and has no plausible cross-type applicability. Example for Contact: mentoringFocusAreas (Mentor only), clientIntakeDate (Client only).

- **Needs discussion.** Could reasonably be shared or type-specific; affects other entities; or raises a design question.

### 3.3 Confirm the First Two Buckets as Groups

> "I have sorted the custom fields into three buckets. Let me present the first two as groups.
>
> **Clearly Shared ({N} fields):** {bullet list with PRD name and ID for each}
> Any in this bucket that you think should actually be type-specific?
>
> **Clearly Type-Specific ({N} fields):** {bullet list grouped by discriminator value}
> Any in this bucket that you think should actually be shared?"

Resolve disagreements before moving on.

### 3.4 Walk the Needs-Discussion Bucket

For each field in the needs-discussion bucket, one at a time:

> "Field: {PRD name} ({PRD ID})
> Defined in: {process document(s)}
> Question: {the specific design question — e.g., "Is this shared or type-specific?", "What are the allowed values?", "Should this be required or optional?"}
>
> My recommendation: {recommendation and reasoning}
>
> What do you think?"

Await confirmation. Record the decision in Section 9 with a
`{ENTITY-CODE}-DEC-NNN` identifier.

### 3.5 Present the Complete Field Table

After all three buckets are resolved, present the full custom field
table. For each field, confirm field-level detail:

- Field name (lowerCamelCase)
- PRD name and ID
- Type
- Required (Yes/No/conditional)
- Allowed values (enum/multiEnum)
- Default
- Description
- Domain(s)
- Type-specific (Yes/No for shared entities)
- Visibility rule (if type-specific)
- Implementation notes (readOnly, audited, min/max, unique)

### 3.6 Propose Implementation Names

The administrator uses business names. The AI proposes the
lowerCamelCase implementation name and confirms. Do not accept a
business name into the field table; every custom field must have a
lowerCamelCase implementation name before the section is marked
complete.

---

## Section 4 — Relationships

Consolidate every relationship involving this entity from every
contributing domain. For each relationship:

- Relationship name (business-language)
- Related entity
- Link type: oneToMany / manyToOne / manyToMany / oneToOne
- Link name from this side
- Link name from the related side
- Label from this side
- Label from the related side
- Source reference (which process document and identifier)
- Contributing domain(s)

Present as a table and confirm with the administrator. Flag any
relationship that appears on one side of a pair but not the other —
the missing side must either be added here or raised as a
carry-forward request to the related Entity PRD.

---

## Section 5 — Dynamic Logic Rules

Consolidate every visibility and required-when rule for this
entity. Group by the rule's trigger:

- For shared entities, group by discriminator value:

  > **When contactType = "Client":**
  > Show: {field list}
  > Hide: {field list}
  > Required: {field list}
  >
  > **When contactType = "Mentor":**
  > Show: {field list}
  > Hide: {field list}
  > Required: {field list}

- For non-shared entities, group by the triggering condition (a
  status value, a related-entity state, a date threshold).

Every rule must cite the source: the process document and
identifier that established the rule. Rules that appear in process
documents but are not yet implementable as single-field conditions
become entries in Section 7 (Implementation Notes) or Section 8
(Open Issues).

---

## Section 6 — Layout Guidance

Propose panel/tab groupings for the entity's detail view. This is a
recommendation — final layout is set during Phase 9 YAML Generation
— but the Entity PRD captures the logical groupings that emerged
during definition.

Typical groupings:

- Core identity (name, primary identifiers)
- Contact information (for Person-type entities)
- Type-specific groups (one panel per discriminator value for
  shared entities)
- Activity and relationships (streams, linked records)
- Implementation fields (audit, system-maintained)

---

## Section 7 — Implementation Notes

Capture anything that doesn't fit in field-level properties:

- Workflow and automation rules (e.g., auto-populate Close Date on status transition)
- Calculated-field formulas
- Validation rules beyond simple required/type constraints
- Access-control notes (field-level or record-level restrictions that affect the entity as a whole)
- Integration implications (fields populated externally, outbound event triggers)

Each note cites its source process document.

---

## Section 8 — Open Issues

Collect unresolved questions specific to this entity. Format:

> **{ENTITY-CODE}-ISS-NNN** — {question, with enough context that a reviewer who did not attend the session understands what needs to be answered and why it blocks a decision}
> Blocks: {what downstream work this issue prevents}

Do not leave decisions unmade simply because they are difficult;
use Open Issues only for questions that require external input (a
stakeholder not present, a policy not yet written, a related-entity
decision not yet made).

---

## Section 9 — Decisions Made

Every decision from the session gets an entry:

> **{ENTITY-CODE}-DEC-NNN** — {what was decided}
> Rationale: {why}
> Cross-references: {related Entity PRDs or process documents that must reflect this decision, or "none"}

Cross-references are not optional. If a decision in the Contact
Entity PRD creates a requirement for the Account Entity PRD, the
decision entry must say so, and a carry-forward request must be
drafted if the Account Entity PRD is already complete (see
"Handling Discovered Updates to Prior Documents" below).

---

## Section 10 — Interview Transcript

A complete-but-condensed record of the session itself, organized by
topic area with Q/A pairs and inline Decision callouts.

### Interview Transcript Format

This format mirrors Topic 7 of `interview-master-prd.md` and
Section 10 of `interview-process-definition.md` so the transcript
convention is consistent across all interview-driven documents.

The transcript is organized by **topic area**, not chronologically.
Group related exchanges under descriptive subheadings that
correspond to the subject matter. Typical topic groupings for an
Entity PRD transcript:

- Entity Overview (Native/Custom, entity type, discriminator)
- Native Field Mapping
- Custom Field Decisions (one subheading per field in the needs-discussion bucket)
- Relationship Decisions
- Dynamic Logic Rules
- Cross-Entity Impacts

Within each topic group, use Q/A pairs:

> **Q:** {the question asked — condensed to its essential content}
>
> **A:** {the answer given — condensed to its essential content}

Condense conversational filler, false starts, and clarification
back-and-forth into clean Q/A pairs, but preserve all substantive
information. If three exchanges were needed to arrive at an answer,
combine them into one Q/A pair capturing the final understanding.
Never drop information — if it was discussed, it must appear.

When a Q/A exchange results in a decision, add a Decision callout
immediately after the pair:

> **Decision:** {what was decided and why it matters. Reference prior content that changed if applicable.}

Decision callouts are inline with the topic, not collected into a
separate section. The inline callouts sit alongside the formal
Section 9 Decisions Made entries — they do not replace them.

**What to include.** Every Q&A condensed but complete; all
decisions with inline callouts; all conflicts identified and their
resolution; all TBD items with the specific question that needs
answering; all cross-entity impacts surfaced during the session.

**What not to include.** Greetings and conversational filler; the
AI's internal reasoning or analysis; duplicate information.

**Signs you have enough.** Every substantive exchange from the
session is captured; every decision in Section 9 has a matching
inline callout; a reviewer who was not present could reconstruct
the full reasoning behind every decision in the document.

---

## Handling Discovered Updates to Prior Documents

During the Entity PRD interview it is common to discover that an
upstream document is incomplete or inconsistent — a field referenced
in a process document but never defined with a type; a relationship
asserted in one process document but absent from another; a value in
an enum list that doesn't match the Entity Inventory. This is
expected. The interview surfaces exactly these gaps.

Follow the process doc Section 10 scope-change protocol:

1. **Pause the interview at a clean stopping point** — the end of the current Entity PRD section.

2. **Assess the scope of the discovery.** The response depends on what was discovered:

   - **New entity discovered.** Process doc Section 10.2. Pause this session, update the Entity Inventory, conduct a separate Phase 5 Entity PRD session for the new entity, then resume.

   - **New field or relationship on an already-defined entity.** Process doc Section 10.3. Note the discovery, complete the current Entity PRD, then draft a carry-forward request to update the affected Entity PRD.

   - **Process document inconsistency.** Draft a carry-forward request to update the process document(s) per `guide-carry-forward-updates.md`.

   - **Entity Inventory error.** Update the Entity Inventory directly before continuing this Entity PRD.

3. **Record the discovery in Section 9 (Decisions Made).** Include a cross-reference to the carry-forward request or the upstream update.

4. **Resume the interview.** Do not silently absorb the discovery into the current Entity PRD — the upstream fix is what keeps the documents coherent over time.

### Drafting a Carry-Forward Request

Follow the procedure in `guide-carry-forward-updates.md` Section
"Gate 1 — Decision Approval". The request file is saved at:

```
{implementation}/PRDs/{domain_code}/carry-forward/SESSION-PROMPT-carry-forward-{slug}.md
```

Do not execute the carry-forward in this session — that is a
separate, two-gate session per the carry-forward guide.

---

## Closing the Interview

### Completeness Check

Before producing the document, verify:

- [ ] Section 1 — Entity Overview is confirmed.
- [ ] Section 2 — Every native field for the entity type is documented with its PRD-name mapping.
- [ ] Section 3 — Every custom field from every contributing process document is in the table with full field-level detail.
- [ ] Section 3 — Every custom field has a lowerCamelCase implementation name.
- [ ] Section 4 — Every relationship is consolidated and every relationship appears on both sides (this entity and the related entity).
- [ ] Section 5 — Every dynamic logic rule cites its source.
- [ ] Sections 6 and 7 are present (may be brief).
- [ ] Section 8 lists every open issue with the blocking context.
- [ ] Section 9 lists every decision with identifier, rationale, and cross-references.
- [ ] Section 10 has a matching inline Decision callout for every entry in Section 9.
- [ ] Every custom-field identifier traces back to a process document identifier.
- [ ] Every carry-forward request that was drafted is saved at the canonical path.

### Summary

Present a one-paragraph summary of the entity to the administrator:

> "Here is a summary of the {EntityName} Entity PRD:
>
> - {N} native fields documented
> - {N} custom fields, of which {N} are shared and {N} are type-specific
> - {N} relationships
> - {N} dynamic logic rules
> - {N} open issues
> - {N} decisions recorded
> - {N} carry-forward requests drafted
>
> Ready to produce the document?"

### Document Production

Produce the Entity PRD as a Word document at:

```
PRDs/entities/{EntityName}-Entity-PRD.docx
```

Use the CRM Builder Word-document production convention (no
Markdown intermediary, no conversion pipeline — process doc
Section 4). Commit the document to the implementation repository.

### State Next Step

> "The {EntityName} Entity PRD is complete and committed.
>
> Next step: {one of the following, as applicable}
>
> - Produce the Entity PRD for {next entity in the implementation's entity order}.
> - Begin Phase 7 Domain Reconciliation for {domain} if all Entity PRDs for that domain are now complete.
> - Execute the drafted carry-forward requests before continuing entity work, if any were drafted this session.
>
> Shall I continue with the next Entity PRD?"

Await explicit confirmation before starting a new session.

---

## Important AI Behaviors During the Interview

- **Read every input before speaking.** The quality of the three-bucket sort depends entirely on having read every process document that uses the entity. Do not skip this.

- **Propose, then confirm — do not ask open-ended questions about each field.** The batched-decision approach is what keeps the session to 45–75 minutes on complex shared entities.

- **Be thorough with native field identification.** A field created in YAML that already exists natively is the single most common configuration defect. Take time on Section 2.

- **Propose implementation names.** The administrator uses business names ("Mentoring Focus Areas"). The AI proposes the lowerCamelCase implementation name ("mentoringFocusAreas") and confirms.

- **Flag cross-domain dependencies explicitly.** If the Entity PRD references fields from a domain whose process documents are not yet complete, say so. The Entity PRD may need to be updated when those domains are defined. Record the provisional nature in Section 8.

- **Cross-reference decisions that affect other Entity PRDs.** A decision that creates a requirement for another entity (a relationship, a discriminator value, a field that must exist on the related entity) must be called out in both Section 9 and in an explicit carry-forward request if the other Entity PRD is already complete.

- **Never mention product names.** Entity PRDs are business-language documents. "Native" and "Custom" and the entity-type names (Base, Person, Company, Event) are platform-neutral classifications and remain permitted.

- **Stop at 90 minutes.** Entity PRDs for complex shared entities are the session type most likely to run long. Schedule a follow-up rather than pushing through.

---

## Changelog

- **1.1** (04-21-26) — Paired with `guide-domain-overview.md` v1.1. Persona Inventory is no longer a hard input — the Master PRD's Personas section with backing captured in the Master PRD or `CLAUDE.md` is accepted as an equivalent persona source, matching the Domain Overview guide's treatment and the CBM pilot's actual state. Previously-completed related Entity PRDs moved from required to optional inputs. Added explicit framing on Phase 4 → Phase 5 ordering: what earlier methodology called "retroactive" Entity PRDs is now the normal order per process doc Rule 5.1; Entity PRDs record what process definition surfaced rather than guess at it. Pilot-validation status: aligned with CBM MN/MR/CR actual execution (Domain Overview and process documents first, Entity PRDs after); Funding domain Entity PRDs will be the next exercise of this v1.1.
- **1.0** (04-20-26) — Initial release as `interview-entity-prd.md`, scoped to Phase 5 only. Replaces the legacy `guide-entity-definition.md` v1.3. Archetype changed from hybrid (Phase 2a Entity Discovery + Phase 2b Entity PRDs) to interview archetype for a single phase. Structure aligned with `authoring-standards.md` v1.0. Scope-change protocol cross-linked to `guide-carry-forward-updates.md`. **Not pilot-validated; see v1.1.**
