# CRM Builder — Domain Overview Guide

**Version:** 1.0
**Last Updated:** 04-20-26
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

**Inputs:**

- Master PRD (post-Phase-3 reconciled version)
- Entity Inventory (produced in Phase 3)
- Persona Inventory (produced in Phase 3)
- Every Entity PRD for entities whose Entity Inventory row lists this domain as a source domain
- For a Sub-Domain Overview: the parent Domain Overview (must be complete) plus the above inputs scoped to the sub-domain

**Output:** One Word document — the Domain Overview — committed to
the implementation's repository at:

- Domain Overview: `PRDs/{domain_code}/{Implementation}-Domain-Overview-{DomainName}.docx`
- Sub-Domain Overview: `PRDs/{domain_code}/{SUBDOMAIN_CODE}/{Implementation}-SubDomain-Overview-{SubDomainName}.docx`

**Cardinality:** One Domain Overview per domain. For domains with
sub-domains: one parent Domain Overview plus one Sub-Domain Overview
per sub-domain.

**Ordering constraint.** The Domain Overview session runs after
Phase 3 Inventory Reconciliation has completed and after the Entity
PRDs for every entity that participates in this domain are complete.
If an entity participating in this domain is not yet defined, the
Domain Overview is blocked until that Entity PRD is produced.

---

## What the Domain Overview Must Contain

The Domain Overview has four required sections. A Domain Overview is
not complete until all four sections are present and meet their
respective standards.

| # | Section | Content |
|---|---------|---------|
| 1 | Domain Purpose | Expanded business context for the domain. Drawn from and elaborating on the Master PRD's domain description. Answers: what business question does this domain serve, what would go wrong if the work wasn't done, and how does this domain relate to the organization's mission. For parent domains with sub-domains, also describes the sub-domain structure and the rationale for that organization. |
| 2 | Personas | Every persona from the Persona Inventory that participates in this domain, scoped to their domain-specific role. Name, ID (`PER-NNN` from the Persona Inventory), domain-specific responsibilities, and what the CRM provides to them in this domain. For parent domains with sub-domains, also notes which personas span multiple sub-domains and which are sub-domain-specific. |
| 3 | Business Processes | The complete process inventory for the domain with lifecycle narrative, process relationships, and dependency ordering. Describes how the processes connect end-to-end. For flat domains, this is a single list. For domains with sub-domains, this lists the sub-domains and their rationale — individual process inventories live in the Sub-Domain Overview documents. |
| 4 | Data Reference | The entities and fields relevant to this domain, assembled by reference to the completed Entity PRDs. For each entity participating in the domain: canonical name, one-sentence description, link to the full Entity PRD, and a list of the fields most relevant to this domain's processes. The Data Reference does **not** redefine entities or fields — it references the Entity PRDs. |

**Completeness standard.** A Domain Overview is complete when all
four sections are present; the process inventory in Section 3
matches the Master PRD's process list for this domain (with any
additions noted); the dependency ordering in Section 3 has been
confirmed with the administrator; the Data Reference in Section 4
correctly identifies every entity whose Entity Inventory row lists
this domain as a source domain; and every persona in Section 2 is
traced to the Persona Inventory by ID.

**What the Domain Overview is not.** It is not a new requirements
document. It does not introduce information that isn't already in
the Master PRD or the Entity PRDs. If the synthesis surfaces a
missing requirement or a Master PRD / Entity PRD inconsistency, that
is a scope-change finding — see "Gap Identification" below.

---

## Critical Rules

1. **Reference, do not redefine.** Section 4 Data Reference points at the Entity PRDs; it does not re-specify fields or re-write entity descriptions. Duplicating Entity PRD content creates two sources of truth that drift.

2. **Synthesis, not invention.** Every statement in the Domain Overview must trace to the Master PRD, the Persona Inventory, the Entity Inventory, or an Entity PRD. If the synthesis requires a statement that is not supported by any upstream document, that is a gap — surface it to the administrator, do not paper over it.

3. **Confirm the process inventory and dependency ordering interactively.** The process inventory and dependency order are the one set of facts in the Domain Overview that the upstream documents may not fully specify — the Master PRD establishes the processes, but the dependency ordering may need administrator input. Confirm explicitly (see Step 4).

4. **Entity PRDs must exist before the Domain Overview.** If any entity whose Entity Inventory row lists this domain as a source domain does not yet have a completed Entity PRD, stop. The Domain Overview cannot be synthesized without complete Entity PRDs for its participating entities.

5. **Scope to this domain.** The Data Reference lists only entities that participate in this domain. A cross-domain entity (like Contact) is included in the Data Reference for every domain it participates in, but the field list in each Data Reference entry is scoped to the fields this domain's processes actually use.

6. **Sub-domain structure is captured in the parent overview only.** For domains with sub-domains: the parent Domain Overview describes the sub-domain structure and rationale. Each Sub-Domain Overview follows the standard four-section structure focused on its own scope — it does not re-describe the parent's sub-domain structure.

7. **Persona IDs from the Persona Inventory are preserved.** Every persona in Section 2 carries its `PER-NNN` ID from the Persona Inventory. Do not reassign, renumber, or invent new IDs.

8. **Identifier discipline.** The Domain Overview does not introduce new identifiers. It references identifiers that already exist (persona IDs from the Persona Inventory, entity names from the Entity Inventory, process codes from the Master PRD or to-be-assigned in Phase 4b).

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
> - Master PRD: ✓ / ✗
> - Entity Inventory: ✓ / ✗
> - Persona Inventory: ✓ / ✗
> - Entity PRDs for every entity participating in this domain: {list, with ✓ / ✗ per entity}
> - Parent Domain Overview (for a Sub-Domain Overview only): ✓ / ✗ / N/A
>
> Is this the complete set?"

If any entity participating in this domain does not have a completed
Entity PRD, stop. Report the missing Entity PRD(s) and request they
be produced before resuming. Do not begin the Domain Overview with
incomplete Entity PRDs.

### State the Plan

> "Here is how this session will work:
>
> 1. I will read the Master PRD's section on {DomainName}, the Persona Inventory, the Entity Inventory, and every Entity PRD for entities participating in this domain.
> 2. I will draft Section 1 (Domain Purpose) and Section 2 (Personas) from the upstream documents and present each for confirmation.
> 3. I will present the process inventory from the Master PRD and propose a dependency ordering. You will confirm or adjust.
> 4. I will draft Section 3 (Business Processes) incorporating the confirmed dependency ordering.
> 5. I will draft Section 4 (Data Reference), scoped to the entities and fields this domain uses.
> 6. I will surface any gaps in the upstream documents that the synthesis revealed.
> 7. I will produce the Domain Overview document.
>
> Ready?"

---

## Step 1 — Read Upstream Documents

Before synthesizing anything, read every input document. Specifically:

- **Master PRD.** The `{DomainName}` section (domain purpose, personas involved, process list, key data categories). Also any Revision History entries that affected this domain.
- **Persona Inventory.** Every row whose Notes or Source attribute this persona to `{DomainName}`. Also rows where the persona's backing entity participates in this domain.
- **Entity Inventory.** Every row whose source-domain column includes `{DomainName}`.
- **Entity PRDs.** For every entity identified above, read the full Entity PRD. Note which fields each Entity PRD associates with this domain (the Domain(s) column on each custom field).
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

Draft Section 4 from the Entity Inventory and Entity PRDs, scoped to
this domain.

Structure:

- **Opening paragraph.** One paragraph identifying which entities participate in this domain and how they relate to each other.
- **Entity reference table.** One row per entity. Columns: Entity Name (link to the full Entity PRD), One-sentence Description (from the Entity Inventory), Role in this Domain (what this domain uses the entity for — create new records, read existing records, update status, build relationships), Most-Relevant Fields for this Domain (short list, not comprehensive).
- **Cross-domain entities flagged.** Entities whose Entity Inventory row lists more than one source domain. The Data Reference notes this explicitly so process definition conversations in this domain know that field additions to the entity affect other domains too.

For each entity row, the "Most-Relevant Fields" list is typically 5–
15 fields — enough to orient process definition conversations, not
the comprehensive field list. The comprehensive list is in the
Entity PRD.

> "Reminder: the Data Reference references the Entity PRDs. It does
> not redefine entities or fields. Anyone reading the Domain
> Overview who needs full field detail follows the link to the
> Entity PRD."

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
- [ ] Section 2 Personas lists every persona from the Persona Inventory that participates in this domain, each with a `PER-NNN` ID.
- [ ] Section 3 Business Processes reflects the administrator-confirmed process inventory and dependency ordering.
- [ ] Section 4 Data Reference lists every entity whose Entity Inventory row includes this domain as a source domain.
- [ ] Every entity in Section 4 has a link to its Entity PRD and a scoped fields-relevant-to-this-domain list.
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

- **1.0** (04-20-26) — Initial release. Scoped to Phase 4a Domain Overview, including the parent Domain Overview and Sub-Domain Overview variants per `CRM-Builder-Document-Production-Process.docx` Section 3.4. Codifies the synthesis-with-one-gate archetype (silent read, draft Sections 1–2, interactive process-inventory and dependency-ordering gate, draft Sections 3–4, gap identification, document production). Entity-PRD-must-exist-first precondition is an explicit Critical Rule. Structure aligned with `authoring-standards.md` v1.0. Scope-change protocol cross-links to Entity PRD, Entity Inventory, Master PRD, and carry-forward paths.
