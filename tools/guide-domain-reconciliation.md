# CRM Builder — Domain Reconciliation Guide

**Version:** 1.0
**Last Updated:** 03-30-26 16:00
**Purpose:** AI guide for Phase 3 — Domain Reconciliation
**Governing Process:** PRDs/application/CRM-Builder-Document-Production-Process.docx

---

## How to Use This Guide

This guide is loaded as context for an AI performing domain
reconciliation. The AI should read this guide fully before beginning.

**This is a synthesis task, not an interview.** The AI reads all
process documents for a domain, assembles them into a Domain PRD,
and surfaces conflicts for the administrator to resolve. The
administrator's role is to answer questions and review the output,
not to provide new information.

**One domain per conversation.** Each conversation reconciles all
process documents for a single domain and produces a single Domain
PRD.

**Session length:** 30–60 minutes, depending on the number of
processes and conflicts discovered.

**Input:** Master PRD + all process documents for the domain
(uploaded by the administrator).

**Output:** One Word document — the Domain PRD — committed to the
implementation's repository at
`PRDs/{domain_code}/{Implementation}-Domain-PRD-{DomainName}.docx`.

---

## What the Domain PRD Must Contain

The Domain PRD has six sections:

| # | Section | Content |
|---|---------|---------|
| 1 | Domain Overview | Expanded business context for the domain. |
| 2 | Personas | Domain-specific roles for each participating persona. |
| 3 | Business Processes | One subsection per process, each containing all six required sections from the process documents. |
| 4 | Data Reference | Consolidated view of all data in the domain, organized by entity, with full field-level detail. |
| 5 | Decisions Made | Record of all decisions made during the process definition conversations. |
| 6 | Open Issues | Unresolved questions requiring answers before implementation. |

---

## Critical Rules

**Business language only.** Same rule as the process documents — no
product names or implementation technologies in the Domain PRD.

**One topic at a time.** When conflicts are discovered, present them
one at a time and wait for resolution before proceeding to the next.

**Identifiers are preserved.** All identifiers assigned during Phase 2
process conversations carry forward unchanged. New identifiers are
only assigned for decisions (DEC) and open issues (ISS) that emerge
during reconciliation.

**The process documents are the source of truth.** The Domain PRD
assembles and reconciles — it does not invent new requirements,
add new fields, or change process workflows. If something is missing,
it becomes an open issue, not a silent addition.

**After Claude produces the Domain PRD, humans own the document.**
The team may clean up formatting, add workflow diagrams, refine
wording, and restructure sections. Claude is not the permanent
custodian.

---

## Before Reconciliation Begins

### Verify Inputs

Confirm all required documents are present:

> "For the [Domain Name] domain reconciliation, I need the
> Master PRD and all process documents for this domain. Let me
> verify what I have:
>
> - Master PRD: ✓/✗
> - [Process 1]: ✓/✗
> - [Process 2]: ✓/✗
> - [Process N]: ✓/✗
>
> Is this the complete set, or are any documents missing?"

**Do not proceed if any process documents are missing.** All
processes must be defined before reconciliation begins.

### State the Plan

> "Here's how this session will work:
>
> 1. I'll read through all the process documents and identify
>    any conflicts or inconsistencies.
> 2. I'll present each conflict for you to resolve.
> 3. Once all conflicts are resolved, I'll assemble the Domain
>    PRD and present it for your review.
>
> The heavy lifting is on my side — your job is to make
> decisions on anything I flag. Ready?"

---

## Step 1 — Conflict Detection

Read all process documents and check for the following categories
of conflict. Work through each category systematically.

### 1.1 Field Definition Conflicts

The most common conflict type. The same field on the same entity
is defined differently in two or more process documents.

**Check for:**
- Same field name, different type (e.g., one process says dropdown,
  another says text)
- Same field name, different required status
- Same dropdown field, different value lists (e.g., one process
  lists four values, another lists six)
- Same field name, different descriptions that imply different
  meanings
- Different field names that appear to describe the same data

**When a conflict is found:**

> "I found a conflict on [Entity] → [Field Name]:
>
> - In [Process A] ([ID]): [definition]
> - In [Process B] ([ID]): [definition]
>
> These need to be consistent in the Domain PRD. Which definition
> is correct, or do we need a combined definition?"

Wait for resolution before proceeding to the next conflict.

### 1.2 Status Value Conflicts

Status fields are high-risk for conflicts because multiple
processes often touch the same entity's lifecycle.

**Check for:**
- Missing status values (a process references a transition to a
  status that isn't in the value list)
- Overlapping status meanings (two different status values that
  appear to mean the same thing)
- Conflicting transition rules (Process A says you can go from
  X to Y, Process B says you can't)
- Color coding inconsistencies

**When a conflict is found:**

> "I found a status conflict on [Entity] → [Status Field]:
>
> - [Process A] defines these values: [list]
> - [Process B] defines these values: [list]
> - The combined set would be: [merged list]
> - Potential issue: [describe the conflict]
>
> How should we resolve this?"

### 1.3 Persona Role Conflicts

Less common but important — the same persona described with
different responsibilities across processes.

**Check for:**
- A persona described as a decision-maker in one process but
  only a participant in another, where both seem to describe
  the same activity
- A persona included in one process but absent from another
  where you'd expect them to participate

**When a conflict is found:**

> "I noticed a potential inconsistency with [Persona]:
>
> - In [Process A]: [role description]
> - In [Process B]: [role description]
>
> Are these both correct, or should the role be consistent?"

### 1.4 Cross-Process Gaps

These aren't conflicts between documents — they're gaps that
only become visible when all processes are viewed together.

**Check for:**
- A status value defined in one process that no other process
  ever transitions out of (a dead end)
- A field created in one process that no subsequent process
  reads or uses
- A process that expects data to exist, but no prior process
  creates that data
- Missing processes — lifecycle stages with no process covering
  the transition

**When a gap is found:**

> "I noticed a potential gap when looking across all processes:
>
> [Description of the gap]
>
> Is this intentional, or does something need to be added?"

If the gap implies a missing process, follow the scope change
protocol from the Document Production Process (Section 9).

### 1.5 Present Conflict Summary

After checking all categories, present a summary:

> "I've completed my conflict check. Here's what I found:
>
> - Field conflicts: [N] (all resolved above)
> - Status conflicts: [N] (all resolved above)
> - Persona conflicts: [N] (all resolved above)
> - Cross-process gaps: [N] (all resolved above)
>
> [Or: No conflicts found — the process documents are consistent.]
>
> Ready for me to assemble the Domain PRD?"

---

## Step 2 — Domain PRD Assembly

With all conflicts resolved, assemble the Domain PRD. The
following sections describe what goes into each part.

### Section 1: Domain Overview

Synthesize from the Master PRD's domain description and the
context established across all process documents. Expand the
one-paragraph Master PRD description into a fuller picture of:

- What this domain covers and why it matters to the organization
- The scope of the domain (what's included, what's explicitly
  handled elsewhere)
- How this domain relates to other domains (if applicable)

This section is written by the AI based on what the documents
contain. Confirm with the administrator:

> "Here's the Domain Overview I've written based on the Master
> PRD and the process documents. Does this accurately capture
> the domain?"

### Section 2: Personas

For each persona that participates in any process within this
domain, compile their domain-specific role:

- Persona name and identifier (from Master PRD)
- Their role within this domain specifically
- Which processes they participate in and what they do in each

This is a synthesis of the Personas Involved sections from all
process documents, deduplicated and organized by persona rather
than by process.

### Section 3: Business Processes

Include all six required sections from each process document,
in the dependency order established in the Master PRD. This is
primarily a reorganization — the content comes directly from the
process documents with any conflict resolutions applied.

For each process:
1. Process Purpose and Trigger
2. Personas Involved
3. Process Workflow
4. System Requirements (with identifiers)
5. Process Data (with identifiers and field-level detail)
6. Data Collected (with identifiers and field-level detail)

**Apply conflict resolutions:** Where a conflict was resolved
in Step 1, use the resolved definition. Do not carry forward
the conflicting version.

### Section 4: Data Reference

This is the unique contribution of the Domain PRD — a
consolidated view of all data in the domain organized by entity.

**For each entity that appears in any process document:**

1. List every field defined across all processes (deduplicated)
2. For each field, provide the full field-level detail:
   - Field name
   - Field type
   - Required status
   - Enum values (complete merged list)
   - Description (synthesized if defined differently across
     processes — the description should capture the field's
     role across all processes, not just one)
3. Note which processes defined or reference each field
4. Preserve field identifiers from the process documents

**Present the Data Reference as tables grouped by entity:**

**Entity: [Entity Name]**

| ID | Field Name | Type | Required | Enum Values | Description | Defined In |
|----|-----------|------|----------|-------------|-------------|------------|
| [ID] | [Name] | [Type] | [Status] | [Values or —] | [Description] | [Process list] |

The "Defined In" column traces each field back to the process
document(s) that established it.

### Section 5: Decisions Made

Compile all decisions made during the process definition
conversations, plus any decisions made during this reconciliation
session (conflict resolutions).

Assign new identifiers for reconciliation decisions:
`[DOMAIN]-RECON-DEC-001`, `[DOMAIN]-RECON-DEC-002`, etc.

| ID | Decision | Rationale | Made During |
|----|----------|-----------|-------------|
| [ID] | [Decision] | [Why] | [Process name or Reconciliation] |

### Section 6: Open Issues

Compile all TBD items from all process documents, plus any new
open issues discovered during reconciliation.

Assign new identifiers for reconciliation issues:
`[DOMAIN]-RECON-ISS-001`, `[DOMAIN]-RECON-ISS-002`, etc.

| ID | Issue | Question | Needs Input From | Source |
|----|-------|----------|-----------------|--------|
| [ID] | [Issue] | [Specific question] | [Stakeholder] | [Process name or Reconciliation] |

---

## Step 3 — Review

Present the assembled Domain PRD to the administrator for review.
Walk through each section:

> "The Domain PRD for [Domain Name] is assembled. Let me walk
> through the key sections:
>
> **Domain Overview:** [brief summary]
>
> **Personas:** [N] personas participate in this domain.
>
> **Business Processes:** [N] processes, in this order:
> [list process names]
>
> **Data Reference:** [N] entities with [N] total fields.
> [Note any entities that appear in many processes.]
>
> **Decisions Made:** [N] decisions recorded.
>
> **Open Issues:** [N] issues requiring resolution before
> implementation.
>
> Would you like to review any section in detail before I
> produce the final document?"

---

## Step 4 — Document Production and Next Steps

After the administrator approves, produce the Domain PRD as a
Word document and commit it to the repository at:
`PRDs/{domain_code}/{Implementation}-Domain-PRD-{DomainName}.docx`

### State Next Step

> "The [Domain Name] Domain PRD is complete and committed.
>
> **If more domains need reconciliation:**
> The next step is reconciliation for [next domain]. For that
> conversation, upload the Master PRD plus all process documents
> for [next domain].
>
> **If all domains are reconciled:**
> All Domain PRDs are now complete. The next step is Phase 4 —
> Stakeholder Review. Share the Domain PRDs with stakeholders
> via Google Docs for review and feedback. This phase happens
> outside of Claude.
>
> After stakeholder review is complete, we'll move to Phase 5 —
> YAML Generation."

---

## Important AI Behaviors During Reconciliation

**Be systematic, not conversational.** This session is about
thoroughness, not discovery. Work through the conflict categories
methodically. Don't skip categories even if you think there are
no conflicts — verify.

**Present conflicts clearly.** Each conflict should be stated with
the exact definitions from each process document, side by side,
so the administrator can make an informed decision. Never
summarize away the details.

**One conflict at a time.** Don't present a list of ten conflicts
and ask the administrator to resolve them all. Present one, resolve
it, move to the next.

**Don't invent.** The Domain PRD assembles what exists. If the
process documents don't cover something, it becomes an open issue
— the AI does not fill in the gap with assumptions.

**Trace everything.** Every field, requirement, and decision in the
Domain PRD should be traceable to a specific process document or
to a reconciliation decision. The "Defined In" and "Made During"
columns serve this purpose.

**The Data Reference is the most valuable section.** It's the only
place where all fields for all entities in the domain are visible
in one consolidated view. Take extra care with deduplication and
completeness here — it will be the primary reference for YAML
generation in Phase 5.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0 | 03-30-26 | Initial release. |
