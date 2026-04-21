# CRM Builder — Domain Overview Guide

**Version:** 1.1
**Last Updated:** 04-21-26
**Purpose:** AI guide for Phase 4a — Domain Overview (including Sub-Domain Overview)
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `interview-process-definition.md` — the Phase 4b activity whose primary input is the Domain Overview produced here. `guide-domain-reconciliation.md` — the Phase 7 reconciliation whose input set includes this Domain Overview. `guide-carry-forward-updates.md` — used when this session discovers that an upstream Entity PRD or the Master PRD needs updating.
**Authoring contract:** `authoring-standards.md` (Section 11 review checklist).

---

## How to Use This Guide

This guide is loaded as context for an AI producing a Domain Overview
document for one domain (or Sub-Domain Overview for one sub-domain).
The AI should read this guide fully before beginning.

**This is primarily a synthesis task with one interactive gate.** The
AI reads the Master PRD, the Entity Inventory, and the Entity PRDs
for every entity participating in this domain, and assembles the
Domain Overview as a single domain-scoped reference document. The
one interactive portion is confirming the domain's process inventory
and dependency ordering with the administrator before the Business
Processes section is finalized. Everything else is generation.

**Why this phase exists.** The Domain Overview is the context-passing
optimization for Phase 4b Process Definition and Phase 5 Entity PRD
work within the domain. Without it, every process definition
conversation would need the Master PRD + Entity Inventory + every
relevant Entity PRD uploaded separately. The Domain Overview
collapses that into one document that captures everything a process
definition conversation needs to know about the domain.

**One domain per conversation.** Each conversation produces exactly
one Domain Overview (or one Sub-Domain Overview). Do not attempt to
produce overviews for multiple domains in one session.

**Session length:** 30–60 minutes. Longer for domains with many
entities or complex sub-domain structures. Stop at 90 minutes
regardless — split the session if needed.

**Inputs (required):**

- Master PRD (post-Phase-3 reconciled version)
- Entity Inventory (produced in Phase 3)
- Persona source: either a separate Persona Inventory document (the spec-compliant Phase 3 output), or the Master PRD's Personas section with backing information captured in it or in the implementation's `CLAUDE.md`. Implementations that predate the split of Persona Inventory from the Master PRD use the latter and it is accepted as equivalent — see "Persona Source Compatibility" below.

**Inputs (optional, use when available):**

- Entity PRDs for entities whose Entity Inventory row lists this domain as a source domain. Per process doc Rule 5.1, full Entity PRDs are produced in Phase 5 **after** Phase 4 process documents. The Domain Overview produces what it can from the Entity Inventory; any Entity PRDs that happen to exist (typically for cross-domain entities defined in an earlier domain's Phase 5 work) inform the Data Reference more richly.
- Process documents already drafted for this domain — if Phase 4b has begun, these help calibrate the Data Reference's "Role in this Domain" characterization and the most-relevant-fields lists.

**Inputs (Sub-Domain Overview):**

- Parent Domain Overview (must be complete)
- The required and optional inputs above, scoped to the sub-domain

**Output:** One Word document — the Domain Overview — committed to
the implementation's repository at:

- Domain Overview: `PRDs/{domain_code}/{Implementation}-Domain-Overview-{DomainName}.docx`
- Sub-Domain Overview: `PRDs/{domain_code}/{SUBDOMAIN_CODE}/{Implementation}-SubDomain-Overview-{SubDomainName}.docx`

**Cardinality:** One Domain Overview per domain. For domains with
sub-domains: one parent Domain Overview plus one Sub-Domain Overview
per sub-domain.

**Ordering constraint.** The Domain Overview session runs after
Phase 3 Inventory Reconciliation has completed. It does **not**
require Entity PRDs to be complete — per process doc Rule 5.1,
Entity PRDs are produced in Phase 5 after Phase 4 process documents,
and in practice many Entity PRDs are produced retroactively once the
processes that use them have surfaced the fields and relationships
they actually need. The Domain Overview's Data Reference (Section 4)
is synthesized from the Entity Inventory, enriched with any Entity
PRDs that already exist.

**Persona Source Compatibility.** The spec calls for a Persona
Inventory as a separate Phase 3 deliverable. Implementations that
predate this split (where personas live in the Master PRD's
Personas section with backing information captured in the Master
PRD or the implementation's `CLAUDE.md`) are supported: the guide
accepts either source. If a separate Persona Inventory exists, use
it. If only the Master PRD has personas, use them and their backing
from wherever the backing is captured — the Data Reference and
Section 2 Personas don't change based on the source document.
Implementations in flight should run Phase 3 to produce the
separate Persona Inventory only when the work naturally reaches a
Master PRD update point; forcing the split mid-flight produces
churn without value.

---

## What the Domain Overview Must Contain

The Domain Overview has four required sections. A Domain Overview is
not complete until all four sections are present and meet their
respective standards.

| # | Section | Content |
|---|---------|---------|
| 1 | Domain Purpose | Expanded business context for the domain. Drawn from and elaborating on the Master PRD's domain description. Answers: what business question does this domain serve, what would go wrong if the work wasn't done, and how does this domain relate to the organization's mission. For parent domains with sub-domains, also describes the sub-domain structure and the rationale for that organization. |
| 2 | Personas | Every persona from the persona source (Persona Inventory or Master PRD Personas) that participates in this domain, scoped to their domain-specific role. Name, ID (`PER-NNN`), domain-specific responsibilities, and what the CRM provides to them in this domain. For parent domains with sub-domains, also notes which personas span multiple sub-domains and which are sub-domain-specific. |
| 3 | Business Processes | The complete process inventory for the domain with lifecycle narrative, process relationships, and dependency ordering. Describes how the processes connect end-to-end. For flat domains, this is a single list. For domains with sub-domains, this lists the sub-domains and their rationale — individual process inventories live in the Sub-Domain Overview documents. |
| 4 | Data Reference | The entities and fields relevant to this domain. Assembled from the Entity Inventory, enriched by Entity PRDs where they exist. For each entity participating in the domain: canonical name, one-sentence description, link to the Entity PRD if one exists (otherwise a "Entity PRD pending Phase 5" note), and a list of the fields most relevant to this domain's processes (drawn from the Entity PRD when available, or proposed from the Master PRD and Phase 4 process documents when the Entity PRD does not yet exist). The Data Reference does **not** redefine entities or fields — it references the authoritative source for each. |

**Completeness standard.** A Domain Overview is complete when all
four sections are present; the process inventory in Section 3
matches the Master PRD's process list for this domain (with any
additions noted); the dependency ordering in Section 3 has been
confirmed with the administrator; the Data Reference in Section 4
correctly identifies every entity whose Entity Inventory row lists
this domain as a source domain, with either a link to the Entity
PRD or a "pending Phase 5" annotation per entity; and every persona
in Section 2 is traced to its persona source by `PER-NNN` ID.

**What the Domain Overview is not.** It is not a new requirements
document. It does not introduce information that isn't already in
the Master PRD, the Entity Inventory, or an Entity PRD where one
exists. If the synthesis surfaces a missing requirement or an
inconsistency between sources, that is a scope-change finding — see
"Gap Identification" below. The Domain Overview also is not a
pre-Phase-5 Entity PRD substitute; if it ends up carrying
field-level detail that belongs in an Entity PRD, that detail
should be surfaced in a Phase 5 Entity PRD when one is produced,
not treated as the durable field definition.

---

## Critical Rules

1. **Reference, do not redefine.** Section 4 Data Reference points at the Entity Inventory rows and, where they exist, the Entity PRDs; it does not re-specify fields or re-write entity descriptions. Duplicating Entity PRD or Entity Inventory content creates two sources of truth that drift.

2. **Synthesis, not invention.** Every statement in the Domain Overview must trace to the Master PRD, a persona source (Persona Inventory or Master PRD Personas section), the Entity Inventory, an Entity PRD (where one exists), or a process document (where one exists). If the synthesis requires a statement that is not supported by any upstream document, that is a gap — surface it to the administrator, do not paper over it.

3. **Confirm the process inventory and dependency ordering interactively.** The process inventory and dependency order are the one set of facts in the Domain Overview that the upstream documents may not fully specify — the Master PRD establishes the processes, but the dependency ordering may need administrator input. Confirm explicitly (see Step 4).

4. **Entity PRDs are optional inputs, not prerequisites.** Per process doc Rule 5.1, Entity PRDs are produced in Phase 5 after Phase 4 process documents. The Domain Overview must not block on Entity PRDs being complete. For each entity participating in this domain: if an Entity PRD exists, the Data Reference links to it and draws field lists from it; if no Entity PRD exists yet, the Data Reference cites the Entity Inventory row and annotates "Entity PRD pending Phase 5". Both states are valid and expected.

5. **Scope to this domain.** The Data Reference lists only entities that participate in this domain. A cross-domain entity (like Contact) is included in the Data Reference for every domain it participates in, but the field list in each Data Reference entry is scoped to the fields this domain's processes actually use (or, when process documents do not yet exist, the fields the Master PRD's domain description implies).

6. **Sub-domain structure is captured in the parent overview only.** For domains with sub-domains: the parent Domain Overview describes the sub-domain structure and rationale. Each Sub-Domain Overview follows the standard four-section structure focused on its own scope — it does not re-describe the parent's sub-domain structure.

7. **Persona IDs are preserved from whichever source provides them.** Every persona in Section 2 carries its `PER-NNN` ID from the persona source (Persona Inventory or Master PRD Personas section — both use the same ID format). Do not reassign, renumber, or invent new IDs.

8. **Identifier discipline.** The Domain Overview does not introduce new identifiers. It references identifiers that already exist (persona IDs from the persona source, entity names from the Entity Inventory, process codes from the Master PRD or to-be-assigned in Phase 4b).

9. **No product names.** Domain Overviews are business-language documents. No CRM platform names.

10. **Confirmation gates.** After Step 4 (process inventory confirmation) and before document production, explicitly state the next step and confirm (process doc Section 7.3).

11. **Scope-change protocol.** If synthesis surfaces a Master PRD gap, an Entity PRD omission, or an Entity Inventory error, pause, follow the protocol, and draft a carry-forward request if any already-published document needs to change (process doc Section 10). See "Gap Identification" below.

12. **One deliverable per conversation.** One Domain Overview per session. For a domain with sub-domains, the parent and each sub-domain get their own session (process doc Section 7.5).

---

## Before Generation Begins

### Session-Start Checklist (process doc Section 7.1)

1. Ask which implementation is being worked on.
2. Read the implementation's `CLAUDE.md` for current state.
3. Identify the current phase and step — this session is Phase 4a Domain Overview (or Sub-Domain Overview) for `{DomainName}`.
4. Confirm whether this is a Domain Overview, a parent Domain Overview for a domain with sub-domains, or a Sub-Domain Overview.
5. State the current step and confirm with the administrator before beginning.

### Verify Inputs

> "For the {DomainName} Domain Overview, I need to confirm the following are available:
>
> **Required:**
> - Master PRD: ✓ / ✗
> - Entity Inventory: ✓ / ✗
> - Persona source — either a Persona Inventory document or the Master PRD's Personas section with backing: ✓ / ✗
> - Parent Domain Overview (for a Sub-Domain Overview only): ✓ / ✗ / N/A
>
> **Optional — will be used if available:**
> - Entity PRDs for entities participating in this domain: {list, with ✓ / ✗ / pending-Phase-5 per entity}
> - Phase 4b process documents already drafted for this domain: {list, with ✓ / ✗ per process}
>
> Is this the complete set?"

If a required input is missing, stop. If one or more entities do
not yet have Entity PRDs, proceed — those entities will be
referenced from the Entity Inventory with a "Phase 5 pending"
annotation in the Data Reference. This is expected, not a blocker.

### State the Plan

> "Here is how this session will work:
>
> 1. I will read the Master PRD's section on {DomainName}, the persona source, the Entity Inventory, and any Entity PRDs and process documents that already exist for this domain.
> 2. I will draft Section 1 (Domain Purpose) and Section 2 (Personas) from the upstream documents and present each for confirmation.
> 3. I will present the process inventory from the Master PRD and propose a dependency ordering. You will confirm or adjust.
> 4. I will draft Section 3 (Business Processes) incorporating the confirmed dependency ordering.
> 5. I will draft Section 4 (Data Reference), scoped to the entities and fields this domain uses. For entities with Entity PRDs, I will link to them. For entities without Entity PRDs yet (pending Phase 5), I will cite the Entity Inventory row and annotate the entity as 'Entity PRD pending Phase 5'.
> 6. I will surface any gaps in the upstream documents that the synthesis revealed.
> 7. I will produce the Domain Overview document.
>
> Ready?"

---

## Step 1 — Read Upstream Documents

Before synthesizing anything, read every input document. Specifically:

- **Master PRD.** The `{DomainName}` section (domain purpose, personas involved, process list, key data categories). Also any Revision History entries that affected this domain.
- **Persona source.** If a separate Persona Inventory document exists, read every row whose Notes or Source attribute the persona to `{DomainName}`, plus rows where the persona's backing entity participates in this domain. If no separate Persona Inventory exists, read the Master PRD's Personas section and the backing information for each (often captured in the Master PRD itself or the implementation's `CLAUDE.md`).
- **Entity Inventory.** Every row whose source-domain column includes `{DomainName}`.
- **Entity PRDs — only those that already exist.** For every entity identified above whose Entity PRD has been produced, read the full Entity PRD. Note which fields each associates with this domain. For entities without Entity PRDs, note them for a "pending Phase 5" annotation and plan to draw field suggestions for the Data Reference from the Master PRD and any Phase 4 process documents that already exist.
- **Phase 4b process documents — those that exist.** If Phase 4b has begun for this domain, read the drafted process documents. They calibrate the "Role in this Domain" characterization and the most-relevant-fields lists, especially for entities without an Entity PRD.
- **For a Sub-Domain Overview: the parent Domain Overview.** Section 3 of the parent identifies which processes belong to this sub-domain.

Maintain three working notes while reading:

- Domain Purpose notes: mission tie-in, business context, key distinctions from other domains.
- Personas-in-this-domain notes: who participates, in what role, with what CRM capabilities.
- Fields-by-entity-relevant-to-this-domain: for each entity, which fields this domain's processes are likely to read or write.

No administrator interaction in Step 1. Read silently.

---

## Step 2 — Assemble Section 1: Domain Purpose

Draft Section 1 from the Master PRD's domain description, elaborated
with the synthesis context.

Structure:

- **Opening paragraph.** One to three paragraphs describing the domain's business purpose in expanded form relative to the Master PRD's one-paragraph description. Use the Master PRD as the seed, not as the entire text.
- **Mission tie-in.** One paragraph stating how this domain serves the organization's mission. Reference the mission statement from the Master PRD.
- **Distinctions from adjacent domains.** One paragraph explaining the boundary between this domain and any adjacent domain the Master PRD lists. If the reader were to confuse this domain with another, what distinguishes them?
- **Sub-domain structure (parent Domain Overview only).** For a parent Domain Overview, an additional paragraph describing the sub-domains, why the domain is organized this way rather than as a flat process list, and what cross-sub-domain oversight and analytics responsibilities the parent domain retains.

Present Section 1 for administrator confirmation:

> "Here is the draft Domain Purpose for {DomainName}:
>
> {Section 1 draft}
>
> Does this accurately capture the business context and the mission tie-in? Any adjustments before I move to Section 2?"

Await confirmation.

---

## Step 3 — Assemble Section 2: Personas

Draft Section 2 from the Persona Inventory, scoped to personas that
participate in this domain.

For each participating persona, include:

- **Persona name** with `PER-NNN` ID.
- **Domain-specific role.** How this persona engages with this domain's work specifically — what they contribute, what outcomes they are accountable for, which processes they initiate or participate in. The Master PRD's Personas section has general responsibilities; this section narrows them to this domain.
- **What the CRM provides to this persona in this domain.** Drawn from the Master PRD's persona definitions and the Entity PRDs. Scoped to capabilities this domain's processes actually require.
- **Backing** (entity name from the Entity Inventory, or "External"). Copy from the Persona Inventory.

For a parent Domain Overview with sub-domains, also note:

- Which personas span multiple sub-domains.
- Which personas are sub-domain-specific (and which sub-domain).

Present Section 2 for administrator confirmation:

> "Here is the draft Personas section for {DomainName}:
>
> {Section 2 draft, with {N} personas}
>
> Does this correctly identify every persona that participates in this domain? Is any persona's domain-specific role miscast?"

Await confirmation.

---

## Step 4 — Confirm Process Inventory and Dependency Ordering

This is the one interactive step in the synthesis. The Master PRD
lists the processes within this domain, but the dependency ordering
may need administrator input — the Master PRD may state it, or may
leave it for Phase 4 to determine.

### 4.1 Present the Process Inventory

Pull the process list from the Master PRD's `{DomainName}` section.
For each process, note its implementation tier (if the Master PRD
records one) and any one-line description.

> "The Master PRD lists the following processes in {DomainName}:
>
> {N} processes:
> 1. {Process A} — {one-line description}
> 2. {Process B} — {one-line description}
> ...
>
> Is this complete? Any process that should be added before we move on?"

If the administrator adds a process, update both the Domain Overview
draft and the Master PRD (the Master PRD update is a carry-forward
per Section 10.4 of the process doc — draft a carry-forward request
if any downstream documents already reference the Master PRD's
process list).

### 4.2 Propose Dependency Ordering

Propose an ordering based on the natural lifecycle pattern (process
doc Section 3.4):

- **Sequential lifecycle processes first.** Processes that establish core entities, field values, and status transitions that later processes depend on.
- **Asynchronous processes second.** Processes that read and react to data already defined by the lifecycle processes.

> "Here is my proposed dependency ordering for {DomainName}:
>
> **Sequential lifecycle:**
> 1. {Process A} — establishes {record type, field values}
> 2. {Process B} — depends on A having established {what}
> 3. ...
>
> **Asynchronous:**
> - {Process X} — reads {data established by A and B}
> - {Process Y} — reacts to {state changes from C}
>
> Does this ordering match how these processes actually run? Any dependencies I got wrong, or any processes I placed in the wrong category?"

Await explicit confirmation. Record any corrections.

### 4.3 For Domains with Sub-Domains

If the domain has sub-domains, the process inventory is organized
hierarchically:

> "For domains with sub-domains, processes are ordered within each
> sub-domain independently. Cross-sub-domain dependencies are
> flagged but expected to be rare (sub-domains are designed to be
> autonomous).
>
> Here is the proposed structure:
>
> **Sub-Domain 1: {Name}** ({N} processes)
> - Rationale: {why these processes belong together}
> - Ordering: sequential lifecycle ({list}), asynchronous ({list})
>
> **Sub-Domain 2: {Name}** ({N} processes)
> - ...
>
> **Cross-sub-domain dependencies:** {list, or 'none identified'}
>
> Does this structure match your intent?"

Await explicit confirmation.

---

## Step 5 — Assemble Section 3: Business Processes

Draft Section 3 from the confirmed process inventory and dependency
ordering.

### For a flat domain

Structure:

- **Opening paragraph.** Lifecycle narrative — how the processes connect end-to-end. Names the processes and describes the flow in two to four paragraphs.
- **Process inventory table.** Columns: Process Code (if assigned — otherwise "TBD, assigned in Phase 4b"), Process Name, One-line Description, Category (sequential lifecycle / asynchronous), Depends On (process codes or names).
- **Dependency diagram.** A reference to where the dependency diagram will live (the Domain Overview itself does not embed the diagram; the diagram is drawn during Phase 4b process documentation).

### For a parent Domain Overview with sub-domains

Structure:

- **Opening paragraph.** Describes how the sub-domains divide the domain's work and how they connect (or deliberately don't).
- **Sub-domain summary table.** Columns: Sub-Domain Code, Sub-Domain Name, Rationale, Process Count, Link to Sub-Domain Overview (where the detailed inventory lives).
- **Cross-sub-domain dependencies.** Either a list of identified dependencies, or an explicit statement that none exist. If any exist, describe them.

### For a Sub-Domain Overview

Structure:

- **Opening paragraph.** Sub-domain's role within the parent domain.
- **Process inventory table.** Same columns as a flat-domain Business Processes section.
- **Dependencies with other sub-domains.** Either the relevant subset from the parent's cross-sub-domain dependencies, or a statement that this sub-domain is autonomous.

Present Section 3 for administrator confirmation:

> "Here is the draft Business Processes section:
>
> {Section 3 draft}
>
> Does this accurately represent the process inventory, the dependency ordering, and the lifecycle narrative? Any corrections before I move to Section 4?"

Await confirmation.

---

## Step 6 — Assemble Section 4: Data Reference

Draft Section 4 from the Entity Inventory, enriched by any Entity
PRDs that exist and any Phase 4 process documents already drafted
for this domain.

Structure:

- **Opening paragraph.** One paragraph identifying which entities participate in this domain and how they relate to each other.
- **Entity reference table.** One row per entity. Columns: Entity Name (link to the Entity PRD if one exists, otherwise annotated "Entity PRD pending Phase 5"), One-sentence Description (from the Entity Inventory), Role in this Domain (what this domain uses the entity for — create new records, read existing records, update status, build relationships), Most-Relevant Fields for this Domain.
- **Cross-domain entities flagged.** Entities whose Entity Inventory row lists more than one source domain. The Data Reference notes this explicitly so process definition conversations in this domain know that field additions to the entity affect other domains too.

Most-Relevant Fields list, per entity:

- **If the Entity PRD exists.** Draw 5–15 fields from the Entity PRD, scoped to those the Entity PRD's "Domain(s)" column associates with this domain. The comprehensive field list remains in the Entity PRD.
- **If the Entity PRD does not exist yet.** Propose 5–15 fields the domain's processes will likely read or write, drawn from the Master PRD's domain description, any Phase 4 process documents already drafted, and the Entity Inventory row. Annotate this list as "proposed, pending Phase 5 Entity PRD". Phase 5 will reconcile the proposed list into the Entity PRD.

> "Reminder: the Data Reference references the authoritative source
> for each entity. If an Entity PRD exists, it is the authority and
> the Data Reference links to it. If no Entity PRD exists yet, the
> Entity Inventory row is the authority and the proposed field list
> is a Phase 5 input, not a durable field definition."

Present Section 4 for administrator confirmation:

> "Here is the draft Data Reference:
>
> {Section 4 draft, with {N} entities}
>
> Does this correctly identify every entity that participates in this domain? Is the 'Role in this Domain' characterization accurate for each? Are the most-relevant fields lists reasonably scoped?"

Await confirmation.

---

## Step 7 — Gap Identification

Before producing the document, surface any gaps the synthesis
revealed. Typical gaps:

- **Master PRD omission.** A persona, process, or data category surfaced during synthesis that is not in the Master PRD's `{DomainName}` section.
- **Entity PRD omission.** A field this domain's processes clearly need but that is not in the relevant Entity PRD.
- **Entity Inventory error.** An entity whose Entity Inventory row does not list this domain as a source domain, but that this domain's processes clearly use.
- **Persona Inventory error.** A persona whose backing is wrong given the domain's actual process references, or a persona whose participation in this domain was missed.
- **Dependency contradiction.** A process that the Master PRD places in one position but whose dependencies imply a different position.

Present gaps to the administrator:

> "During synthesis I identified the following gaps in the upstream documents:
>
> - {Gap 1: description, which document needs to change, severity}
> - {Gap 2: ...}
>
> For each gap: do you want to (a) fix the upstream document now, before I produce the Domain Overview, (b) note the gap in the Domain Overview's Open Issues and fix the upstream document via a carry-forward session, or (c) set aside — this is not actually a gap?"

Follow the Section 10 scope-change protocol for every gap
classified as (a) or (b). See "Handling Gaps" below for the
detailed protocol.

If no gaps exist, say so:

> "No gaps identified. The Domain Overview synthesizes cleanly from
> the upstream documents."

---

## Step 8 — Sub-Domain Variant Handling

If this session is producing a Sub-Domain Overview (not a Domain
Overview or a parent Domain Overview), apply these variations to
Steps 2–6:

- **Step 2 Personas.** Scope to personas active in this sub-domain. Exclude personas that participate only in sibling sub-domains.
- **Step 3 Process Inventory.** The parent Domain Overview already confirmed the overall sub-domain structure. This session confirms only the process inventory and dependency ordering within the current sub-domain.
- **Step 4 Dependency Ordering.** Ordering is within this sub-domain. Cross-sub-domain dependencies are called out but live in the parent Domain Overview.
- **Step 6 Data Reference.** Entities active in this sub-domain, scoped to fields this sub-domain's processes use. An entity shared across multiple sub-domains appears in each Sub-Domain Overview's Data Reference, each with a different fields-in-scope list.

The Sub-Domain Overview's four-section structure is otherwise
identical to a flat-domain Domain Overview. The parent Domain
Overview and the Sub-Domain Overviews together form the complete
domain context.

---

## Handling Gaps (Scope-Change Protocol)

When Step 7 surfaces a gap the administrator wants to address,
follow the process doc Section 10 protocol:

1. **Pause the Domain Overview session at a clean stopping point** — typically after Section 4 is drafted but before document production.

2. **Assess the scope of the gap:**

   - **Field missing on an existing Entity PRD.** Per process doc Section 10.3: note the discovery, continue the Domain Overview, draft a carry-forward request to update the Entity PRD after this session. The missing field is flagged in the Domain Overview's Open Issues (if the Domain Overview includes one) or in the Revision History.

   - **Entity missing from the Entity Inventory.** Per process doc Section 10.2: pause the Domain Overview, update the Entity Inventory, conduct a Phase 5 Entity PRD session for the new entity, then resume the Domain Overview.

   - **Process missing from the Master PRD's domain process list.** Per process doc Section 10.4: pause, update the Master PRD, resume. If Phase 4b has already begun on this domain, a carry-forward request updates the existing process documents that should reference the new process.

   - **Master PRD mission / scope revision.** Per process doc Section 10.5: pause all domain work, run a Master PRD revision conversation, resume domain work from the updated Master PRD.

   - **Sub-domain restructuring need discovered.** Per process doc Section 10.6: pause, update the Master PRD to restructure the domain's process inventory into sub-domains, produce the parent Domain Overview reflecting the new structure, and resume work through the sub-domain sequence.

   - **New cross-domain service discovered.** Per process doc Section 10.7: pause, update the Master PRD to add the service, resume. Service definition can proceed in parallel or later.

3. **Draft carry-forward requests where applicable.** Follow the template in `guide-carry-forward-updates.md` Section "Gate 1 — Decision Approval". Save carry-forward requests at:

   ```
   {implementation}/PRDs/{domain_code}/carry-forward/SESSION-PROMPT-carry-forward-{slug}.md
   ```

4. **Do not silently absorb gaps into the Domain Overview.** The Domain Overview's value depends on being a faithful synthesis of the upstream documents. Absorbing undocumented changes defeats the purpose and creates drift.

---

## Step 9 — Document Production and Next Steps

### Completeness Check

Before producing the document, verify:

- [ ] Section 1 Domain Purpose is drafted and administrator-confirmed.
- [ ] Section 2 Personas lists every persona from the persona source that participates in this domain, each with a `PER-NNN` ID.
- [ ] Section 3 Business Processes reflects the administrator-confirmed process inventory and dependency ordering.
- [ ] Section 4 Data Reference lists every entity whose Entity Inventory row includes this domain as a source domain.
- [ ] Every entity in Section 4 has either a link to its Entity PRD or an "Entity PRD pending Phase 5" annotation, plus a scoped fields-relevant-to-this-domain list (drawn from the Entity PRD or proposed for Phase 5, respectively).
- [ ] For a parent Domain Overview: sub-domain structure is described and cross-sub-domain dependencies are identified.
- [ ] For a Sub-Domain Overview: scope is limited to this sub-domain; the parent Domain Overview's broader content is not duplicated.
- [ ] Every gap surfaced in Step 7 is resolved (addressed now, carry-forward drafted, or explicitly set aside).

### Summary

> "Here is a summary of the {DomainName} Domain Overview:
>
> - Section 1 Domain Purpose: {one-line summary}
> - Section 2 Personas: {N} personas listed — {names and IDs}
> - Section 3 Business Processes: {N} processes in {categories}; dependency ordering confirmed
> - Section 4 Data Reference: {N} entities referenced
> - Gaps identified and resolved: {N}
> - Carry-forward requests drafted: {N}
>
> Ready to produce the document?"

### Document Production

Produce the Domain Overview as a Word document at:

- Domain Overview: `PRDs/{domain_code}/{Implementation}-Domain-Overview-{DomainName}.docx`
- Sub-Domain Overview: `PRDs/{domain_code}/{SUBDOMAIN_CODE}/{Implementation}-SubDomain-Overview-{SubDomainName}.docx`

Use the CRM Builder Word-document production convention (no Markdown
intermediary, no conversion pipeline — process doc Section 4). Commit
the document to the implementation repository.

### State Next Step

> "The {DomainName} Domain Overview is complete and committed.
>
> Next step: {one of the following, as applicable}
>
> - For a parent Domain Overview: produce the Sub-Domain Overview for {first sub-domain in recommended order}.
> - For a Sub-Domain Overview with sibling sub-domains remaining: produce the next Sub-Domain Overview for {next sub-domain}.
> - For a Sub-Domain Overview with no siblings remaining: begin Phase 4b Process Definition for the first process in {this sub-domain}.
> - For a flat Domain Overview: begin Phase 4b Process Definition for the first process in this domain (typically the first sequential lifecycle process: {process name}).
> - If carry-forward requests were drafted: execute them before beginning Phase 4b, so the downstream conversations have an up-to-date upstream.
>
> Shall I continue?"

Await explicit confirmation.

---

## Important AI Behaviors During Generation

- **Read every upstream document before drafting anything.** The quality of the synthesis depends on having read every Entity PRD and the Master PRD's domain section in full. Do not skim.

- **Reference the Entity PRDs; do not duplicate them.** Section 4 is the test of this discipline. An entity's full field list lives in its Entity PRD. The Domain Overview surfaces the fields this domain uses and links to the PRD for anything else.

- **Confirm Section 1 and Section 2 before Section 3.** Section 3's interactive dependency-ordering gate is the session's cognitive peak. Having Sections 1 and 2 confirmed before that gate means any administrator pushback on them doesn't compound with dependency questions.

- **Be explicit about gaps.** Do not paper over a missing field or a process that the Master PRD lists in the wrong order. Surface it as a gap in Step 7 and let the administrator decide how to handle it.

- **Keep the dependency ordering narrative tight.** Section 3's lifecycle narrative is 2–4 paragraphs. It is not a re-write of the Master PRD's domain section; it is the story of how the processes connect.

- **Distinguish parent Domain Overview from Sub-Domain Overview consistently.** A parent Domain Overview is about the sub-domain structure; a Sub-Domain Overview is about one sub-domain's processes. Do not blend.

- **Never mention product names.** Domain Overviews are business-language documents, consumed by Phase 4b and Phase 5 conversations.

- **Stop at 90 minutes.** Synthesis fatigue shows up as increasingly generic prose. Split the session rather than pushing through.

---

## Changelog

- **1.1** (04-21-26) — Reconciled with process doc Rule 5.1 and observed practice. v1.0's Critical Rule #4 required Entity PRDs to exist before the Domain Overview; Rule 5.1 says Entity PRDs are produced in Phase 5 **after** Phase 4 process documents, and the CBM pilot ran MN, MR, and CR domains with Domain Overview first and Entity PRDs retroactive. Rule #4 is now flipped: Entity PRDs are optional inputs that enrich the Data Reference when available; when absent, the Data Reference cites the Entity Inventory row and annotates "Entity PRD pending Phase 5". Related updates: Inputs list now separates required (Master PRD, Entity Inventory, persona source, parent Domain Overview for sub-domains) from optional (Entity PRDs, Phase 4b process documents that already exist). Verify Inputs prompt updated. Step 1 and Step 6 Data Reference procedure updated to produce proposed field lists for entities without Entity PRDs, annotated as Phase 5 inputs. Completeness standard updated. Also added Persona Source Compatibility: implementations that predate the Persona Inventory split (where personas live in the Master PRD with backing captured there or in `CLAUDE.md`) are accepted equivalents; forcing the split mid-flight produces churn without value.
- **1.0** (04-20-26) — Initial release. Scoped to Phase 4a Domain Overview, including the parent Domain Overview and Sub-Domain Overview variants per `CRM-Builder-Document-Production-Process.docx` Section 3.4. Codifies the synthesis-with-one-gate archetype. **Superseded by v1.1.**
