# CRM Builder — Entity Definition Guide

**Version:** 1.2
**Last Updated:** 04-04-26 21:30
**Purpose:** AI guide for Phase 2 — Entity Definition
**Governing Process:** PRDs/process/CRM-Builder-Document-Production-Process.docx

---

## How to Use This Guide

This guide is loaded as context for an AI conducting Entity
Definition. The AI should read this guide fully before beginning.

**Entity Definition has two parts:**

- **Phase 2a: Entity Discovery** — one conversation that produces
  the Entity Inventory from the Master PRD
- **Phase 2b: Entity PRDs** — one conversation per CRM entity that
  produces a detailed Entity PRD

**This is a collaborative interview.** The AI reads the Master PRD,
proposes an entity model, and works with the administrator to refine
it. The administrator brings domain knowledge about how entities
should map to the CRM platform. The AI brings structure and
thoroughness.

**Phase 2 must complete before Phase 3 (Process Definition).**
Process documents reference entities defined in this phase. If
entities are not defined first, process documents will introduce
entity assumptions that may conflict with each other.

**Input for Phase 2a:** Master PRD (completed in Phase 1).

**Input for Phase 2b:** Master PRD + Entity Inventory (from 2a) +
any existing implementation knowledge (e.g., which CRM platform is
targeted, which entities are native vs. custom).

**Output for Phase 2a:** One document — the Entity Inventory —
committed to the implementation's repository at
`PRDs/{Implementation}-Entity-Inventory.docx`.

**Output for Phase 2b:** One Word document per CRM entity — the
Entity PRD — committed to the implementation's repository at
`PRDs/entities/{EntityName}-Entity-PRD.docx`.

**Generator template:** A data-driven document generator is
available at `PRDs/process/templates/generate-entity-prd-template.js`
in the CRM Builder repository. The template separates entity-specific
data (an ENTITY object at the top of the file) from the rendering
engine (bottom of the file). To produce an Entity PRD: copy the
template, replace the ENTITY object with the entity's data from the
session, and run with Node.js. The rendering engine is never modified.

**Reference implementation:** The Contact Entity PRD (Cleveland
Business Mentors) is the reference implementation for Entity PRD
format and content. It demonstrates all nine sections, the
batched-decision interview approach, and the generator template
data structure for a complex shared entity spanning four domains.

---

## Phase 2a: Entity Discovery

### Purpose

The Entity Inventory is the mapping layer between business language
(used in the Master PRD and process documents) and CRM
implementation (used in YAML program files). It establishes:

- Every distinct entity concept mentioned in the Master PRD
- How those concepts map to actual CRM entities
- Which CRM entities are native (already exist on the platform)
  and which are custom (must be created)
- How shared entities (like Contact) distinguish between types

Without this mapping, process documents will treat "Client Contact"
and "Mentor Contact" as separate entities, and YAML generation will
not know they map to the same CRM entity.

### Before Discovery Begins

#### Verify Inputs

> "For Entity Discovery, I need the completed Master PRD. Let me
> verify:
>
> - Master PRD: ✓/✗
>
> I'll also need to understand the target CRM platform to determine
> which entities are native. What platform are we targeting, or
> should I keep this platform-agnostic?"

**Note on product names:** The Entity Inventory is an implementation
bridging document. Product names (e.g., specific CRM platform names)
are permitted here because this document maps business concepts to
platform capabilities. This is an exception to the Level 1/Level 2
product name restriction — the Entity Inventory is neither a Master
PRD, Entity PRD, process document, nor Domain PRD.

#### State the Plan

> "Here's how this session will work:
>
> 1. I'll read through the Master PRD and extract every distinct
>    entity concept — every noun that represents a record type the
>    system needs to track.
> 2. I'll propose a mapping from those concepts to CRM entities,
>    identifying native vs. custom and shared vs. dedicated.
> 3. We'll walk through the mapping together and resolve any
>    questions.
> 4. I'll produce the Entity Inventory document.
>
> Ready?"

### Step 1 — Extract Entity Concepts

Read the Master PRD systematically and extract every distinct entity
concept. Sources within the Master PRD:

- **Domain descriptions** — each domain's "Key Data Categories"
  section lists the major record types
- **Process descriptions** — each process's "Key Capabilities"
  often implies entities
- **Persona descriptions** — "What the CRM Provides" sections
  reference the records each persona works with
- **System Scope** — the In Scope section lists all major record
  types

For each concept found, record:
- The business name used in the Master PRD (e.g., "Client
  Organization", "Mentor Contact", "Engagement")
- Which domain(s) reference it
- A brief description of what it represents

Present the extracted list to the administrator:

> "I've identified [N] distinct entity concepts in the Master PRD.
> Here they are, grouped by domain:
>
> [list]
>
> Did I miss anything, or are any of these not actually separate
> entities?"

### Step 2 — Propose Entity Mapping

For each entity concept, propose how it maps to the CRM:

**Identify native entities.** Most CRM platforms have built-in
entities for common concepts. Typical native entities include:
- Contact (or Person) — individual people
- Account (or Organization/Company) — businesses or organizations
- User — system users with login credentials

Native entities cannot be created or deleted via YAML. They can
only have fields added and layouts modified.

**Identify shared entities.** Multiple business concepts may map to
a single CRM entity. The most common pattern is Contact:
- "Client Contact", "Mentor Contact", "Partner Contact" → all map
  to the native Contact entity
- Distinguished by a discriminator field (e.g., contactType)

**Identify custom entities.** Business concepts with no native
equivalent must be created as custom entities:
- Engagement, Session, Partnership Agreement, Donation, etc.
- Each needs an entity type (Base, Person, Company, Event)

Present the proposed mapping:

> "Here's how I'd map the [N] entity concepts to CRM entities:
>
> **Native Entities (already exist):**
> - Contact → used for: Client Contact, Mentor Contact, Partner
>   Contact, Administrator
>   - Discriminator: contactType field
> - Account → used for: Client Organization, Partner Organization,
>   Donor Organization
>   - Discriminator: accountType field (if needed)
>
> **Custom Entities (must be created):**
> - Engagement (Base) — mentoring relationships
> - Session (Event) — individual mentoring meetings
> - [etc.]
>
> Does this mapping make sense? Any concepts that should be
> combined or separated differently?"

**Note:** These mappings are preliminary. The Entity PRD
conversation (Phase 2b) is where Native/Custom and Entity Type
are authoritatively determined based on the entity's full
requirements.

### Step 3 — Resolve Questions

Common questions that arise during entity mapping:

**Shared vs. separate entities.** When two business concepts share
most of their fields, they should usually be the same entity with
a type discriminator. When they share few fields, they should be
separate entities. Discuss with the administrator.

**Discriminator values.** For shared entities, agree on the complete
list of type values. These must cover all business concepts that
map to the entity, including any that may be defined in future
domains.

**Entity types for custom entities.** The choice affects which
built-in fields are available:
- Base — name and description only
- Person — adds first/last name, email, phone, address
- Company — adds email, phone, billing/shipping address
- Event — adds date start/end, duration, status, parent

**Cross-domain entities.** Some entities are referenced by multiple
domains. Identify these and note all contributing domains. The
Entity PRD for cross-domain entities must consolidate fields from
all domains.

### Step 4 — Produce the Entity Inventory

The Entity Inventory document has the following structure:

**Section 1: Overview**
Brief description of the implementation, the target CRM platform
(if known), and the total entity count.

**Section 2: Entity Map**
A table mapping every business entity concept to its CRM entity:

| PRD Entity Name | CRM Entity | Native/Custom | Entity Type | Discriminator | Discriminator Value | Domain(s) |
|----------------|------------|---------------|-------------|---------------|--------------------| ----------|
| Client Contact | Contact | Native | Person | contactType | Client | MN, CR |
| Mentor Contact | Contact | Native | Person | contactType | Mentor | MN, MR |
| Client Organization | Account | Native | Company | — | — | MN, CR |
| Engagement | Engagement | Custom | Base | — | — | MN |
| Session | Session | Custom | Event | — | — | MN |

**Section 3: Shared Entity Summary**
For each shared entity (Contact, Account, etc.), document:
- All business concepts that map to it
- The discriminator field and its values
- Which domains contribute fields to this entity
- A note that the Entity PRD must consolidate fields from all
  domains

**Section 4: Custom Entity Summary**
For each custom entity, document:
- Entity type and rationale
- Display labels (singular and plural)
- Which domain owns the entity
- Whether the entity needs an activity stream

**Section 5: Cross-Domain Entity Matrix**
A matrix showing which entities are referenced by which domains.
This helps identify Entity PRDs that need input from multiple
domains:

| CRM Entity | MN | MR | CR | FU |
|-----------|----|----|----|----|
| Contact   | ✓  | ✓  | ✓  |    |
| Account   | ✓  |    | ✓  | ✓  |
| Engagement| ✓  |    |    |    |
| Session   | ✓  |    |    |    |

**Section 6: Interview Transcript**
A complete but condensed record of the Entity Discovery
conversation — every question asked, every answer given, and every
decision made — organized by topic area with Q/A pairs and inline
Decision callouts. See **Interview Transcript Format** at the end
of Phase 2b for the full specification. Topic groupings for the
Entity Inventory transcript typically include the entity concepts
discussed, native vs. custom determinations, discriminator
decisions on shared entities, and cross-domain entity scope.

### State Next Step

> "The Entity Inventory is complete. The next step is to produce
> Entity PRDs — one per CRM entity. Each Entity PRD will
> consolidate all fields, relationships, and implementation details
> for that entity.
>
> I'd recommend starting with [entity name] because [rationale —
> typically the most complex or most cross-domain entity].
>
> For the first Entity PRD conversation, upload the Master PRD and
> the Entity Inventory."

---

## Phase 2b: Entity PRDs

### Purpose

Each Entity PRD is the implementation-ready specification for a
single CRM entity. It consolidates everything needed for YAML
generation:

- All fields from all domains that contribute to this entity
- Native vs. custom designation per field
- Shared fields vs. type-specific fields
- Dynamic logic visibility rules
- Relationships to other entities
- Implementation notes (readOnly, audited, default values, etc.)

The Entity PRD is the primary input for YAML generation (Phase 6).
The Domain PRD provides the business context; the Entity PRD
provides the implementation mapping.

### Before the Entity PRD Session

#### Verify Inputs

> "For the [Entity Name] Entity PRD, I need:
>
> - Master PRD: ✓/✗
> - Entity Inventory: ✓/✗
> - [Domain PRD or process documents that reference this entity]:
>   ✓/✗
>
> Is this the complete set?"

**When to use Domain PRDs vs. process documents:**
- If Domain PRDs exist for all domains that reference this entity,
  use the Domain PRDs (they are the reconciled source of truth)
- If Domain PRDs do not yet exist, use the process documents
  directly — the Entity PRD will need to reconcile field
  definitions across processes just as the Domain PRD would

#### State the Plan

> "Here's how this session will work:
>
> 1. I'll compile all fields for [Entity Name] from the source
>    documents, identifying which are native and which are custom.
> 2. For shared entities, I'll sort custom fields into three
>    buckets: clearly shared, clearly type-specific, and needs
>    discussion. You'll confirm the first two as groups.
> 3. We'll work through the needs-discussion bucket one question
>    at a time.
> 4. I'll present the complete field compilation for review.
> 5. I'll produce the Entity PRD document using the generator
>    template.
>
> Ready?"

### Entity PRD Structure

The Entity PRD document has the following sections:

**Section 1: Entity Overview**
- CRM entity name
- Native or custom
- Entity type (Base, Person, Company, Event)
- Display labels (singular, plural)
- Description and purpose
- Activity stream enabled (yes/no)
- All domains that contribute fields to this entity
- For shared entities: the discriminator field and its values

**Section 2: Native Fields**
Fields that already exist on the entity because of its type. These
are not created by YAML — they are documented here so process
documents can reference them correctly.

For the Contact entity (Person type), native fields include:
firstName, lastName, emailAddress, phoneNumber, address, etc.

For each native field, document:
- Native field name (as it exists on the platform)
- PRD field name(s) that map to it (e.g., "First Name" in
  MN-INTAKE maps to native firstName)
- Which domains/processes reference it

Present as a table:

| Native Field Name | PRD Name(s) | Type | Referenced By |
|------------------|-------------|------|---------------|
| firstName | First Name | varchar | MN-INTAKE, MN-ENGAGE |

**Section 3: Custom Fields**
Fields that must be created via YAML. This is the primary field
table for YAML generation.

For each custom field, document using the standard PRD field table
format (two rows per field):
- Field name (lowerCamelCase for YAML)
- PRD field name and ID
- Type
- Required (Yes/No — with conditional notes in description)
- Values (for enum/multiEnum)
- Default
- Description
- Domain(s) that define or reference this field
- Type-specific (Yes/No — for shared entities only)
- Visibility rule (for type-specific fields, e.g., "Show when
  contactType = Mentor")
- Implementation notes (readOnly, audited, min/max, etc.)

**Section 4: Relationships**
All relationships involving this entity, compiled from all domains.

For each relationship:
- Relationship name
- Related entity
- Link type (oneToMany, manyToOne, manyToMany)
- Link names (both sides)
- Labels (both sides)
- PRD reference
- Domain(s)

**Section 5: Dynamic Logic Rules**
Consolidated visibility rules for type-specific fields and panels.
Grouped by discriminator value:

> **When contactType = "Client":**
> Show: [field list]
> Hide: [field list]
>
> **When contactType = "Mentor":**
> Show: [field list]
> Hide: [field list]

**Section 6: Layout Guidance**
Suggested panel/tab grouping for the entity's detail view. This is
a recommendation — the final layout is determined during YAML
generation, but the Entity PRD captures the logical groupings
established during entity definition.

**Section 7: Implementation Notes**
Any implementation-specific notes that don't fit in field-level
properties:
- Workflow/automation rules (e.g., auto-populate Close Date on
  status transition)
- Calculated field formulas
- Validation rules beyond simple required/type constraints
- Access control notes (field-level or record-level restrictions)

**Section 8: Open Issues**
Unresolved questions specific to this entity's implementation.

**Section 9: Decisions Made**
Decisions made during the entity definition session. Each decision
has an identifier (format: {ENTITY-CODE}-DEC-NNN) and a description
of the decision and its rationale. Decisions that affect other
Entity PRDs should be cross-referenced (e.g., "Primary Contact is
on the Account-Contact relationship — see Account Entity PRD").

**Section 10: Interview Transcript**
A complete but condensed record of the Entity PRD conversation
itself — every question asked, every answer given, and every
decision made — organized by topic area with Q/A pairs and inline
Decision callouts. Topic groupings for an Entity PRD transcript
typically include field-by-field discussions, relationship
decisions, dynamic logic rules, and cross-entity impacts. See
**Interview Transcript Format** below for the full specification.

### Interview Transcript Format

This format applies to **both** Section 6 of the Entity Inventory
(Phase 2a) and Section 10 of each Entity PRD (Phase 2b). It mirrors
Topic 7 of `interview-master-prd.md` and Section 11 of
`interview-process-definition.md` so the transcript convention is
consistent across all interview-driven documents.

The transcript is organized by **topic area**, not chronologically.
Group related exchanges under descriptive subheadings that
correspond to the subject matter discussed. Within each topic
group, use **Q/A pairs**:

> **Q:** [The question asked — condensed to its essential content]
>
> **A:** [The answer given — condensed to its essential content]

Condense conversational filler, false starts, and back-and-forth
clarification into clean Q/A pairs, but preserve all substantive
information. If three exchanges were needed to arrive at an
answer, combine them into one Q/A pair that captures the final
understanding. Never drop information — if it was discussed, it
must appear.

When a Q/A exchange results in a decision — especially one that
changes prior content, resolves an ambiguity, or establishes a new
rule — add a **Decision:** callout immediately after the Q/A pair:

> **Decision:** [What was decided and why it matters. Reference
> the prior content that changed if applicable.]

Decision callouts are inline with the topic, not collected into a
separate section. (For Entity PRDs, decisions are also recorded
formally in Section 9 with their `{ENTITY-CODE}-DEC-NNN`
identifiers; the inline callouts in the transcript do not replace
Section 9, they sit alongside it next to the discussion that
produced them.)

**What to include:** every Q&A condensed but complete; all
decisions with inline callouts; all conflicts identified and their
resolution; all TBD items with the specific question that needs
answering; all cross-entity impacts surfaced during the session.

**What not to include:** greetings and conversational filler; the
AI's internal reasoning or analysis; duplicate information.

**Signs you have enough:** every substantive exchange from the
session is captured; all decisions have inline callouts; a
reviewer who was not present could reconstruct the full reasoning
behind every decision in the document.

---

## Critical Rules

**Business language in PRD references, implementation language in
field specifications.** The Entity PRD bridges both worlds. PRD
field names appear in the "PRD Name" column. Implementation field
names appear in the "Field Name" column. Both must be present so
the mapping is traceable.

**One entity per conversation.** Complex entities like Contact
(shared across multiple domains and types) deserve a dedicated
session. Do not rush through multiple entities.

**Do not invent fields.** The Entity PRD consolidates what the
Master PRD, Domain PRDs, and process documents define. If a field
seems to be missing, it becomes an open issue — the AI does not
silently add it.

**Native fields are documented, not created.** The Entity PRD must
clearly distinguish native fields (already on the platform) from
custom fields (created via YAML). This prevents duplicate field
creation.

**Identifiers are preserved.** Field identifiers from process
documents and Domain PRDs carry forward. The Entity PRD adds the
implementation field name alongside the PRD identifier.

**Cross-domain consolidation is essential.** For entities that span
multiple domains (Contact, Account), the Entity PRD must include
fields from ALL contributing domains, not just the domain currently
being worked on. If some domains have not yet completed their
process documents, note the incomplete domains and flag the entity
for update when those domains are defined.

**Native/Custom is determined in the Entity PRD, not the Entity
Inventory.** The Entity Inventory may record preliminary
Native/Custom and Entity Type assessments, but these are not
authoritative. The Entity PRD conversation establishes the
definitive determination based on the entity's full requirements.
Entities added to the inventory before their requirements are
fully defined should use TBD for Native/Custom and Entity Type.

---

## Important AI Behaviors During Entity Definition

**Batch obvious decisions, drill into ambiguous ones.** Do not ask
about each field individually. Compile the full field inventory from
source documents and present it in three buckets: clearly shared
(confirm as a group), clearly type-specific (confirm as a group),
and needs discussion (resolve one at a time). A field is "clearly
type-specific" if it is defined in only one domain for only one
entity type and has no plausible cross-type applicability. A field
"needs discussion" if it could reasonably be shared or type-specific,
if it affects other entities, or if it raises a design question.
This approach dramatically reduces session length while preserving
thoroughness on the questions that matter.

**Upload and reference prior Entity PRDs.** When producing Entity
PRDs for entities that have relationships to already-defined
entities, upload the prior Entity PRDs as session input. Decisions
in prior Entity PRDs may create requirements for the current entity
(e.g., "Primary Contact is on the Account-Contact relationship"
decided in the Contact Entity PRD creates a requirement the Account
Entity PRD must implement).

**Be thorough with native field identification.** The most common
error in YAML generation is attempting to create a field that
already exists natively. Take time to identify all native fields
for the entity type.

**Propose implementation names.** The administrator uses business
names ("Mentoring Focus Areas"). The AI should propose the
lowerCamelCase implementation name ("mentoringFocusAreas") and
confirm.

**Flag cross-domain dependencies.** If the Entity PRD references
fields from a domain whose process documents are not yet complete,
flag this explicitly. The Entity PRD may need to be updated when
those domains are defined.

**Use the generator template.** After all decisions are made and the
field compilation is confirmed, use the Entity PRD generator template
to produce the Word document. Copy the template, populate the ENTITY
data object with the session's content, run with Node.js, and
validate. The rendering engine is never modified — only the data
changes per entity.

**The Entity PRD is the YAML generator's primary input.** Every
field that should appear in YAML must be in the Entity PRD. Every
field in the Entity PRD must trace back to a process document or
Domain PRD. This traceability is what makes the system work.

---

## Retroactive Entity Definition

In cases where process documents and Domain PRDs were completed
before Entity Definition (i.e., Phase 2 was skipped), Entity
Definition can be performed retroactively.

The approach is the same, with these differences:
- **Input for Phase 2a:** Master PRD + all completed Domain PRDs
  (richer source than Master PRD alone)
- **Input for Phase 2b:** Entity Inventory + Domain PRDs + process
  documents (all available sources)
- **No upstream changes:** Process documents and Domain PRDs remain
  unchanged. The Entity PRDs add the missing implementation mapping
  layer without modifying the requirements documents.

Retroactive Entity Definition is a recovery path. The recommended
approach is to complete Phase 2 before Phase 3, as designed in the
Document Production Process.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.3 | 04-11-26 | Added Interview Transcript as Section 6 of the Entity Inventory (Phase 2a) and Section 10 of each Entity PRD (Phase 2b). Added a shared Interview Transcript Format spec at the end of the Entity PRD Structure section, mirroring Topic 7 of interview-master-prd.md and Section 11 of interview-process-definition.md. Captures all Q&A condensed but complete, organized by topic area with inline Decision callouts, so reviewers can reconstruct the reasoning behind every entity and field decision. Inline Decision callouts in the transcript sit alongside the formal Section 9 Decisions Made entries, not in place of them. |
| 1.2 | 04-04-26 | Added Native/Custom determination principle: Entity Inventory assessments are preliminary; Entity PRD is authoritative. Added note to Step 2 (Propose Entity Mapping) and new Critical Rule. |
| 1.1 | 04-02-26 | Added batched-decision approach to AI behaviors. Added generator template reference and usage instructions. Added reference implementation note (Contact Entity PRD). Added Section 9 (Decisions Made) to Entity PRD structure. Updated State the Plan to reflect batched workflow. Replaced "ask about each field" with three-bucket batching. Added prior Entity PRD cross-referencing guidance. |
| 1.0 | 04-01-26 | Initial release. |
