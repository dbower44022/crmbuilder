# CRM Builder — Domain Reconciliation Guide

**Version:** 1.3
**Last Updated:** 04-16-26 14:00
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

**Input:** Master PRD + Domain Overview + all process documents
for the domain (uploaded by the administrator). For domains
with sub-domains, also include all Sub-Domain Overview documents.

**Output:** One Word document — the Domain PRD — committed to the
implementation's repository at
`PRDs/{domain_code}/{Implementation}-Domain-PRD-{DomainName}.docx`.

---

## What the Domain PRD Must Contain

The Domain PRD has seven sections:

| # | Section | Content |
|---|---------|---------|
| 1 | Domain Overview | Expanded business context for the domain. |
| 2 | Personas | Domain-specific roles for each participating persona. |
| 3 | Business Processes | For flat domains, one subsection per process. For domains with sub-domains, one subsection per sub-domain containing its processes. Each process includes all eight required sections from the process documents (see Step 2 for the section list and what is excluded). |
| 4 | Data Reference | Consolidated view of all data in the domain, organized by entity, with full field-level detail. |
| 5 | Decisions Made | Record of all decisions made during the process definition conversations. |
| 6 | Open Issues | Unresolved questions requiring answers before implementation. |
| 7 | Interview Transcript | Condensed Q&A record of the reconciliation conversation itself, organized by topic area with inline Decision callouts. Covers only the reconciliation session — process-level Q&A remains in the source process documents. |

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

Confirm all required documents are present. The checklist format
depends on whether the domain uses sub-domains.

**For a domain without sub-domains:**

> "For the [Domain Name] domain reconciliation, I need the
> Master PRD, the Domain Overview, and all process documents
> for this domain. Let me verify what I have:
>
> - Master PRD: ✓/✗
> - Domain Overview ([Domain Code]): ✓/✗
> - [Process 1]: ✓/✗
> - [Process 2]: ✓/✗
> - [Process N]: ✓/✗
>
> Is this the complete set, or are any documents missing?"

**For a domain with sub-domains:**

> "For the [Domain Name] domain reconciliation, I need the
> Master PRD, the Domain Overview, each Sub-Domain Overview,
> and all process documents. Let me verify what I have:
>
> - Master PRD: ✓/✗
> - Domain Overview ([Domain Code]): ✓/✗
>
> Sub-Domain: [Sub-Domain Name] ([Sub-Domain Code])
> - Sub-Domain Overview: ✓/✗
> - [Process 1]: ✓/✗
> - [Process N]: ✓/✗
>
> Sub-Domain: [Sub-Domain Name] ([Sub-Domain Code])
> - Sub-Domain Overview: ✓/✗
> - [Process 1]: ✓/✗
> - [Process N]: ✓/✗
>
> Is this the complete set, or are any documents missing?"

**Do not proceed if any process documents or overview documents
are missing.** All processes must be defined and all overview
documents must be present before reconciliation begins.

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

### 1.5 Cross-Sub-Domain Conflicts

For domains with sub-domains, repeat the checks in 1.1–1.4
across sub-domain boundaries. Sub-domains are autonomous
process areas that share a common domain purpose, but they
often touch the same entities. Conflicts between sub-domains
are more likely to go unnoticed because the process documents
were written in separate sessions with separate context.

**Check especially for:**
- The same entity field defined differently in processes
  belonging to different sub-domains
- Status values or lifecycle stages defined in one sub-domain
  that conflict with another sub-domain's assumptions
- A sub-domain that expects data created by another sub-domain
  but uses a different field name or structure
- Persona responsibilities that overlap or conflict across
  sub-domain boundaries

### 1.6 Present Conflict Summary

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

Synthesize from the Domain Overview document, the Master PRD's
domain description, and the context established across all
process documents. For domains with sub-domains, incorporate
the Sub-Domain Overview documents as well — these contain the
sub-domain structure rationale, scope boundaries, and
coordination points that belong in the domain-level overview.

Expand into a fuller picture of:

- What this domain covers and why it matters to the organization
- The scope of the domain (what's included, what's explicitly
  handled elsewhere)
- How this domain relates to other domains (if applicable)
- For domains with sub-domains: the sub-domain structure, the
  rationale for the decomposition, and how the sub-domains
  coordinate with each other

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

Include all eight required sections from each process document.
For domains without sub-domains, list processes in the
dependency order established in the Master PRD. For domains
with sub-domains, organize processes under sub-domain headings
— one heading per sub-domain, with its processes listed in
dependency order beneath it. The sub-domain order should follow
the sequence established in the Domain Overview document.

The content comes directly from the process documents with any
conflict resolutions applied.

For each process, include these eight sections:
1. Process Purpose
2. Process Triggers (preconditions, required data, initiation
   mechanism, initiating persona — preserve the structured detail,
   do not merge into a brief paragraph with Process Purpose)
3. Personas Involved
4. Process Workflow
5. Process Completion (normal completion, alternative end states,
   who declares completion, post-completion handoffs, early
   termination if applicable — this section contains important
   lifecycle rules that must not be omitted)
6. System Requirements (full requirement tables with identifiers)
7. Process Data (narrative summary of what data this process reads,
   with field IDs and entity names, referencing Section 4 Data
   Reference for full field-level detail — do not duplicate field
   tables here)
8. Data Collected (narrative summary of what data this process
   creates or updates, with field IDs and entity names, referencing
   Section 4 Data Reference for full field-level detail — do not
   duplicate field tables here)

**Sections excluded per process (with rationale):**
- Open Issues — compiled into Domain PRD Section 6, not repeated
  per process
- Updates to Prior Documents — these have already been applied to
  the process documents and are not needed in the Domain PRD
- Interview Transcript — source material for the process document,
  not domain-level content

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

### Section 7: Interview Transcript

A complete but condensed record of the **reconciliation
conversation itself** — every question asked, every answer given,
and every decision made during the reconciliation session. This
covers only the reconciliation discussion. Q&A from the original
process definition sessions remains in Section 11 of each source
process document and is **not** duplicated here.

The transcript is organized by **topic area**, not chronologically.
Typical topic groupings for a reconciliation transcript include
field definition conflicts, status value conflicts, persona role
conflicts, cross-process gaps, and any cross-cutting design
questions surfaced during assembly.

Within each topic group, use **Q/A pairs**:

> **Q:** [The question asked — condensed to its essential content]
>
> **A:** [The answer given — condensed to its essential content]

Condense conversational filler into clean Q/A pairs but preserve
all substantive information. Never drop information — if it was
discussed, it must appear.

When a Q/A exchange results in a reconciliation decision, add a
**Decision:** callout immediately after the Q/A pair:

> **Decision:** [What was decided and why. Reference the
> `[DOMAIN]-RECON-DEC-NNN` identifier from Section 5.]

Inline Decision callouts in the transcript sit alongside the
formal Section 5 Decisions Made entries, not in place of them.
Each reconciliation decision should appear in both places: once
formally in the Section 5 table with its identifier, and once
inline in the transcript next to the discussion that produced it.

**What to include:** every reconciliation Q&A condensed but
complete; all reconciliation decisions with inline callouts;
all conflicts identified and how each was resolved; all new open
issues surfaced during reconciliation.

**What not to include:** greetings and conversational filler;
the AI's internal reasoning; Q&A from the original process
definition sessions (those live in the process documents);
duplicate information.

**Signs you have enough:** every substantive exchange from the
reconciliation session is captured; all reconciliation decisions
have inline callouts cross-referencing their Section 5 ID; a
reviewer who was not present could reconstruct the full reasoning
behind every reconciliation decision.

This section mirrors Topic 7 of `interview-master-prd.md`,
Section 11 of `interview-process-definition.md`, and Section 6 /
Section 10 of `guide-entity-definition.md`, so the transcript
convention is consistent across all interview-driven documents.

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
> **Business Processes:** [N] processes across [N] sub-domains:
> - [Sub-Domain Name]: [list process names]
> - [Sub-Domain Name]: [list process names]
>
> [Or for flat domains: [N] processes, in this order:
> [list process names]]
>
> **Data Reference:** [N] entities with [N] total fields.
> [Note any entities that appear in many processes.]
>
> **Decisions Made:** [N] decisions recorded.
>
> **Open Issues:** [N] issues requiring resolution before
> implementation.
>
> **Interview Transcript:** [N] reconciliation topic groups
> captured with inline Decision callouts.
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
> conversation, upload the Master PRD, Domain Overview, and all
> process documents for [next domain]. If it uses sub-domains,
> include the Sub-Domain Overview documents as well.
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
| 1.3 | 04-16-26 | Added sub-domain support throughout. Input verification now branches into flat-domain and sub-domain-structured checklists, requiring Domain Overview and Sub-Domain Overview documents. Added §1.5 Cross-Sub-Domain Conflicts as a new conflict detection category (renumbered Present Conflict Summary to §1.6). Updated Section 1 Domain Overview assembly to draw from Domain Overview and Sub-Domain Overview documents. Updated Section 3 Business Processes to organize processes under sub-domain headings when applicable. Updated the Section 3 description in the Domain PRD contents table. Updated the Step 3 review walkthrough and Step 4 next-step prompt to reflect sub-domain-aware inputs. Fixed header version (was stuck at 1.1, changelog already had 1.2). |
| 1.2 | 04-11-26 | Reversed the v1.1 Interview Transcript exclusion. Added Interview Transcript as Section 7 of the Domain PRD, scoped to the reconciliation conversation only — Q&A from the original process definition sessions remains in Section 11 of each source process document and is not duplicated. Inline Decision callouts in the transcript sit alongside the formal Section 5 Decisions Made entries (each reconciliation decision appears in both places, cross-referenced by its [DOMAIN]-RECON-DEC-NNN identifier). Updated Step 3 Review walkthrough to mention the new section. Brings reconciliation into parity with the master, entity, and process definition guides for transcript capture. |
| 1.1 | 04-01-26 | Updated Business Processes section from 6 to 8 required sections per process to match the current 11-section process document format (v2.4). Added Process Triggers and Process Completion as separate sections. Added explicit exclusion list (Open Issues, Updates to Prior Documents, Interview Transcript) with rationale. Changed Process Data and Data Collected to narrative summaries referencing Section 4 Data Reference instead of duplicating field tables. |
| 1.0 | 03-30-26 | Initial release. |
