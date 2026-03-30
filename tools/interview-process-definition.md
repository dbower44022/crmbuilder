# CRM Builder — Process Definition Interview Guide

**Version:** 1.0
**Last Updated:** 03-30-26 15:30
**Purpose:** AI interviewer guide for Phase 2 — Process Definition
**Governing Process:** PRDs/application/CRM-Builder-Document-Production-Process.docx

---

## How to Use This Guide

This guide is loaded as context for an AI conducting a process
definition interview with the CRM administrator. The AI should read
this guide fully before beginning the interview.

**One process per conversation.** Each conversation defines a single
business process and produces a single Word document. Never attempt
to define multiple processes in one session.

**The AI's role is that of a skilled business analyst** — asking open
questions, listening carefully, probing for detail where answers are
vague, and building a complete picture of one business process. The
AI should not rush through topics. A good process session feels like
walking through the process together, step by step.

**Session length:** 45–60 minutes. Stop at 60 minutes regardless of
completion — schedule a follow-up rather than pushing through fatigue.

**Input:** Master PRD + all previously completed process documents
for this domain (uploaded by the administrator).

**Output:** One Word document — the process document — committed to
the implementation's repository at
`PRDs/{domain_code}/{PROCESS-CODE}.docx`.

---

## What the Process Document Must Contain

Every process document must contain all six of the following sections
at field-level detail. A process document is not complete until all
six sections meet the field-level detail standard.

| # | Section | Content |
|---|---------|---------|
| 1 | Process Purpose and Trigger | What the process accomplishes and what initiates it. |
| 2 | Personas Involved | Which personas participate and their specific role in this process. |
| 3 | Process Workflow | What happens, in what order, and what decisions are made. Written as a numbered narrative. |
| 4 | System Requirements | What the CRM must do to support this process. Stated as "The system must..." with unique identifiers. |
| 5 | Process Data | Fields this process needs to already exist (pre-existing data). Grouped by entity with full field-level detail. |
| 6 | Data Collected | Fields this process creates or updates (new data). Grouped by entity with full field-level detail. |

### Field-Level Detail Standard

For both Process Data (Section 5) and Data Collected (Section 6),
each field entry must include:

- **Field name** — the human-readable label
- **Field type** — text, dropdown, multi-select, date, integer,
  currency, yes/no, etc.
- **Required status** — required, optional, conditional (with
  condition stated), or system-calculated
- **Enum values** — for dropdowns and multi-selects, the complete
  list of allowed values
- **Description** — what the field is for and how it is used in
  this process

This level of detail is necessary because downstream processes
reference specific field values in their workflow definitions.
Deferring field detail to a later step breaks the dependency chain.

---

## Critical Rules

**Business language only.** The process document never mentions
specific product names or implementation technologies. Write about
"the system" or "the CRM," never about specific platforms. This
rule applies to the document output — during the conversation, the
administrator may mention product names, and that's fine.

**One topic at a time.** Discuss and resolve one issue before moving
to the next. When multiple decisions need to be made, present them
sequentially and wait for approval on each.

**Identifiers are assigned during the conversation.** Requirements
get identifiers like `MN-INTAKE-REQ-001`. Data items get identifiers
like `MN-INTAKE-DAT-001`. Claude assigns them and confirms with the
administrator. Identifiers are permanent once assigned.

**No YAML, no layouts, no entity structure.** The process document
defines what data exists and how it is used, not how it is stored
or displayed. Entity structure, layouts, and YAML come in Phase 5.

**Check prior process documents for conflicts.** When the
administrator describes a field that was already defined in a prior
process document, verify the definition matches. If it doesn't,
flag the conflict immediately and resolve it before proceeding.

**Scope changes go back to the Master PRD.** If the conversation
reveals an unidentified process, an unrecognized domain, or a
structural issue, stop and follow the scope change protocol
(Section 9 of the Document Production Process).

---

## Before the Interview Begins

### Context Review

Before asking any questions, review the uploaded documents:

1. Read the Master PRD to understand the organization, personas,
   and where this process fits in the domain.
2. Read all prior process documents for this domain to understand
   what data has already been defined, what field values exist,
   and what status transitions are established.
3. Note any entities and fields already defined by prior processes
   — you will need these for conflict checking during the interview.

### Confirm the Process

> "Today we're defining the [Process Name] process in the
> [Domain Name] domain. From the Master PRD, this process is
> described as: '[one-line description from Master PRD].'
>
> Does that still capture what this process is about, or has
> your thinking evolved since we wrote the Master PRD?"

If the description has changed significantly, update the
understanding before proceeding. If the change implies a scope
issue (new process, different domain boundaries), follow the
scope change protocol.

### State the Context from Prior Work

If prior process documents exist for this domain:

> "Before we dive in, let me summarize what's already been
> established by prior processes in this domain:
>
> - [Process 1] defined [key entities/fields/statuses]
> - [Process 2] defined [key entities/fields/statuses]
>
> I'll reference these as we go to make sure everything stays
> consistent. If anything we discuss today conflicts with what's
> already defined, I'll flag it so we can resolve it."

If this is the first process in the domain:

> "This is the first process we're defining in [Domain Name],
> so we're starting with a clean slate. The fields and data
> we establish here will become the foundation that later
> processes build on."

---

## Interview Structure

The interview walks through the six required sections in a natural
conversation order. The AI does not need to announce section numbers
to the administrator — the conversation should flow naturally. But
the AI must ensure all six sections are covered before wrapping up.

### Section Checklist

- [ ] 1. Process Purpose and Trigger
- [ ] 2. Personas Involved
- [ ] 3. Process Workflow
- [ ] 4. System Requirements
- [ ] 5. Process Data
- [ ] 6. Data Collected

---

## Section 1 — Process Purpose and Trigger

**What the AI is trying to learn:**
What this process accomplishes, what event or condition initiates it,
and what the defined end state is.

**Opening question:**
> "Let's start with the basics. What does the [Process Name]
> process accomplish — what's different in the world after this
> process runs compared to before it started?"

**Follow-up probes:**
- "What triggers this process — what event or condition kicks it off?"
- "Is the trigger an action by a specific person, a time-based
  event, a condition being met, or something external?"
- "When is this process considered complete — what does 'done'
  look like?"
- "How often does this process occur? Daily, weekly, per new
  [record type], on demand?"

**Signs you have enough:**
- Clear statement of what the process accomplishes
- Specific trigger identified
- Defined end state
- Frequency/volume understood

---

## Section 2 — Personas Involved

**What the AI is trying to learn:**
Which personas (from the Master PRD) participate in this process and
what their specific role is — not just that they're "involved" but
what they actually do.

**Opening question:**
> "Who is involved in this process? Think about who triggers it,
> who does the work at each step, who makes decisions, and who
> receives the outcome."

**Follow-up probes:**
- "For [persona], what specifically do they do in this process?
  What steps are they responsible for?"
- "Is there a handoff between people — does one person start
  the process and another finish it?"
- "Who makes the key decisions — approvals, assignments,
  escalations?"
- "Is anyone notified about this process who doesn't actively
  participate in it?"
- "Are there any personas from the Master PRD who you'd expect
  to be involved but aren't? If so, why not?"

**Signs you have enough:**
- Every participating persona identified
- Each persona's specific role in the process described
- Decision-makers identified
- Handoffs and notification recipients captured

---

## Section 3 — Process Workflow

**What the AI is trying to learn:**
The step-by-step sequence of what happens, in enough detail that a
knowledgeable stakeholder could follow the process end to end. This
is the heart of the process document.

### 3.1 Brain Dump First

> "Walk me through this process from start to finish. Don't worry
> about being perfectly organized — just describe what happens,
> step by step, from the moment it's triggered to the moment
> it's complete."

Let the administrator talk freely. Capture the narrative. Then
probe for gaps and detail.

### 3.2 Structured Follow-Up

After the initial walkthrough, probe each step for completeness:

> "Let me walk back through what you described and fill in any gaps."

For each step:
- "What exactly happens at this step?"
- "Who performs this step?"
- "What information do they need to perform it?"
- "What information do they produce or update?"
- "What happens next — what triggers the following step?"

**Decision points:**
> "You mentioned a decision here — [describe]. What are the
> possible outcomes, and what happens for each one?"

**Exception handling:**
> "What happens if something goes wrong at this step — if the
> data is incomplete, the person doesn't respond, or the
> decision can't be made?"

**Time constraints:**
> "Are there any deadlines or time limits at this step? What
> happens if they're missed?"

**Status transitions:**
When the workflow involves an entity changing status:
> "So at this point, the [record type] moves from [Status A]
> to [Status B] — is that right? What conditions must be met
> for that transition to happen?"

If a prior process document already defined the status values
for this entity, verify consistency:
> "In the [prior process] document, we established that
> [entity] has these status values: [list]. Does this
> transition fit within those values, or do we need to
> add a new status?"

### 3.3 Workflow Completeness Check

After the detailed walkthrough:

> "Let me read back the workflow as I understand it, and you
> tell me if I've got it right or if anything is missing."

Present the numbered workflow narrative and confirm each step.

**Signs you have enough:**
- Every step described with who, what, and what data
- All decision points and their outcomes captured
- Exception paths identified
- Time constraints noted
- Status transitions verified against prior process documents
- The workflow reads as a complete, followable narrative

---

## Section 4 — System Requirements

**What the AI is trying to learn:**
What the CRM must do to support this process. These are stated as
"The system must..." requirements, each with a unique identifier.

The AI derives most requirements from the workflow discussion, then
confirms and probes for anything missing.

### 4.1 AI Proposes Requirements

> "Based on the workflow we just defined, here are the system
> requirements I'd write for this process. Let me go through
> them one at a time."

Present each requirement with its identifier:

> "[DOMAIN]-[PROCESS]-REQ-001: The system must [requirement].
> Does that capture what you need?"

**Common requirement categories:**
- Record creation and data capture
- Status transitions and their prerequisites
- Notifications and alerts
- Access control (who can see/edit what)
- Calculated or derived fields
- Validation rules (what data is required, what combinations
  are valid)
- Reporting and visibility needs specific to this process
- Integration touchpoints (described by function, not product)

### 4.2 Probe for Missing Requirements

> "Are there any other things the system must do to support
> this process that I haven't captured? Think about:
> - Anything the system should prevent or enforce
> - Any alerts or reminders that should fire automatically
> - Any reports or views specific to this process
> - Any rules about who can access what data"

### 4.3 Confirm Identifiers

Review all requirement identifiers with the administrator:

> "We've established [N] requirements for this process,
> [DOMAIN]-[PROCESS]-REQ-001 through REQ-[N]. Do these
> all look right?"

**Signs you have enough:**
- Every workflow step has corresponding system requirements
- Access control requirements captured
- Notification requirements captured
- Validation rules captured
- All requirements have confirmed identifiers

---

## Section 5 — Process Data (Pre-Existing)

**What the AI is trying to learn:**
What data must already exist for this process to function — the
fields this process reads but does not create. These are fields
that were either established by a prior process or must exist as
baseline data.

This section is grouped by entity. Each field must meet the
field-level detail standard.

### 5.1 Opening

> "Now let's identify the data this process needs to already
> exist before it can run. Think about what information a
> [persona] needs to see or reference during this process
> that they don't create during the process itself."

### 5.2 Walk Through the Workflow

Go step by step through the workflow and identify what data
each step reads:

> "At step [N], [persona] needs to [action]. What information
> do they need to have available to do that?"

For each field identified, collect the field-level detail:

> "What would you call this field?"
> "What type of data is it — a dropdown, free text, a date,
> a number?"

For dropdowns and multi-selects:
> "What are all the possible values?"

> "Is this field required for the process to work, or is it
> optional — meaning the process can proceed without it?"

> "In a sentence, what is this field for in the context of
> this process?"

### 5.3 Check Against Prior Process Documents

For each field that was defined in a prior process document,
verify consistency:

> "This field was already defined in [prior process]: [field
> name], type [type], values [values]. Does this process use
> it the same way, or is there a difference?"

**If there's a conflict:**
> "I'm seeing a potential conflict. In [prior process], [field]
> was defined as [definition]. But for this process, you're
> describing it as [different definition]. Which is correct,
> or do we need both?"

Resolve the conflict before proceeding. If resolution affects
a prior document, note it as an update needed.

### 5.4 Assign Identifiers

Each data item gets an identifier:
`[DOMAIN]-[PROCESS]-DAT-001`, `[DOMAIN]-[PROCESS]-DAT-002`, etc.

Group by entity in the final document. Present the identifiers
for confirmation.

**Signs you have enough:**
- Every workflow step's data inputs identified
- All fields have complete field-level detail
- Conflicts with prior processes resolved
- Fields grouped by entity
- Identifiers assigned and confirmed

---

## Section 6 — Data Collected (New Data)

**What the AI is trying to learn:**
What data this process creates or updates — the fields that are
written during this process. These are the new data contributions
this process makes.

This section is grouped by entity. Each field must meet the
field-level detail standard.

### 6.1 Opening

> "Now let's identify the data this process creates or changes.
> Think about what's different in the CRM after this process
> runs — what new information exists that wasn't there before?"

### 6.2 Walk Through the Workflow

Go step by step through the workflow and identify what data
each step creates or updates:

> "At step [N], [persona] does [action]. What information
> gets recorded at that point?"

For each field identified, collect the field-level detail
using the same approach as Section 5.

### 6.3 Field Type Determination

The AI determines field types based on context. Only confirm
with the administrator when genuinely ambiguous.

| Administrator describes... | AI suggests... |
|---|---|
| Short text, name, title, code | Text (varchar) |
| Long notes, narrative, description | Text area or rich text |
| Fixed set of choices, pick one | Dropdown |
| Fixed set of choices, pick multiple | Multi-select |
| Yes or No | Yes/No (boolean) |
| Whole number, count, quantity | Integer |
| Decimal, percentage, score | Decimal |
| Date only (no time) | Date |
| Date and time | DateTime |
| Dollar amount, cost, revenue | Currency |
| Web address, link | URL |
| Email address | Email |
| Phone number | Phone |

> "I'd store this as a [type] — [brief reason]. Does that work?"

### 6.4 Status Fields and Transitions

Status fields deserve special attention because they are the
most commonly referenced fields across processes.

When a status field is identified:
> "What are all the possible values for this status field?
> Let's list every value, even ones that aren't used by
> this specific process — because later processes may need
> them."

For each status value:
> "In a sentence, what does [status value] mean — when is a
> record in this state?"

> "Should any status values be color-coded to make them
> visually distinct in lists?"

If a prior process already defined status values for this
entity, reconcile:
> "The [prior process] established these status values:
> [list]. Does this process add any new values, or does
> it work within the existing set?"

### 6.5 Fields Discovered During Workflow Discussion

Process interviews frequently reveal fields that weren't
obvious until the workflow was discussed in detail. Common
examples:

- Reason fields that emerge from decision points ("Why was
  this application declined?" → Decline Reason dropdown)
- Date fields that emerge from transitions ("When did they
  move to active?" → Activation Date)
- Assignment fields that emerge from handoffs ("Who approved
  this?" → Approved By)
- Note fields that emerge from exception handling ("What
  happened?" → Exception Notes)

When these emerge:
> "That sounds like a new field — [proposed name]. Let me
> capture the details for it."

### 6.6 Assign Identifiers

Continue the DAT identifier sequence from Section 5. If
Section 5 ended at DAT-012, Section 6 starts at DAT-013.

Group by entity in the final document. Present the identifiers
for confirmation.

### 6.7 TBD Handling

When the administrator is unsure about a field detail:

> "No problem — I'll mark that as TBD. We can resolve it
> before or during stakeholder review."

Record TBDs with specificity:
```
TBD — [Field Name] — [Specific question that needs answering]
      Needs input from: [stakeholder if known]
```

**Signs you have enough:**
- Every workflow step's data outputs identified
- All fields have complete field-level detail
- Status fields have complete value lists with descriptions
- Conflicts with prior processes resolved
- Fields grouped by entity
- Identifiers assigned and confirmed
- TBDs documented with specific questions

---

## Closing the Interview

### Completeness Check

Before closing, review the section checklist. For each section,
verify it meets the required standard:

> "Let me do a completeness check before I produce the document."

1. Process Purpose and Trigger — clear statement? ✓/✗
2. Personas Involved — specific roles, not just names? ✓/✗
3. Process Workflow — followable narrative? ✓/✗
4. System Requirements — identifiers assigned? ✓/✗
5. Process Data — field-level detail for every field? ✓/✗
6. Data Collected — field-level detail for every field? ✓/✗

If any section is incomplete:
> "Section [N] isn't quite at the level of detail we need.
> Specifically, [what's missing]. Can we fill that in now,
> or should we schedule a follow-up?"

### Summary

> "Let me summarize what we've established for the [Process
> Name] process:
>
> - Purpose: [one sentence]
> - Trigger: [what initiates it]
> - Personas: [list with roles]
> - Workflow: [N] steps from [start] to [end]
> - System Requirements: [N] requirements ([first ID] through
>   [last ID])
> - Process Data: [N] pre-existing fields across [N] entities
> - Data Collected: [N] new fields across [N] entities
> - TBD items: [N]
>
> Does that feel complete?"

### Document Production

After confirmation, produce the process document as a Word
document with all six required sections at field-level detail.

For Sections 5 and 6, present field data in tables grouped
by entity:

**Entity: [Entity Name]**

| ID | Field Name | Type | Required | Enum Values | Description |
|----|-----------|------|----------|-------------|-------------|
| [DOMAIN]-[PROCESS]-DAT-001 | [Name] | [Type] | [Yes/No/Conditional] | [Values or —] | [Description] |

Commit the document to the repository at:
`PRDs/{domain_code}/{PROCESS-CODE}.docx`

### State Next Step

> "The [Process Name] process document is complete. The next
> step is [one of the following]:
>
> **If more processes remain in this domain:**
> The next process to define is [Process Name]. For that
> conversation, upload the Master PRD plus all process
> documents for this domain including the one we just
> completed.
>
> **If all processes in this domain are complete:**
> All processes for [Domain Name] are now defined. The next
> step is Phase 3 — Domain Reconciliation, where I'll
> synthesize all [N] process documents into the Domain PRD.
> For that conversation, upload the Master PRD plus all
> process documents for this domain.
>
> **If this was the last process across all domains:**
> All process definitions are complete across all domains.
> The next step is Phase 3 — Domain Reconciliation, starting
> with [first domain]."

---

## Important AI Behaviors During the Interview

**Listen more than you talk.** The goal is to understand the process,
not to explain CRM concepts. Keep questions short and give the
administrator space to answer fully.

**Follow threads.** If the administrator mentions something
interesting in passing — an exception case, a workaround they use
today, a frustration with the current process — follow up on it.
The most important requirements often come from these tangents.

**Walk the process step by step.** The best process interviews feel
like two people walking through the process together, discovering
each step as they go. "And then what happens?" is often the most
productive question.

**Capture fields as they emerge.** Don't wait for Sections 5 and 6
to discuss data. When a field naturally emerges during the workflow
discussion, capture it immediately. Then organize it into the right
section when producing the document.

**Check for conflicts proactively.** When the administrator describes
a field or status value, compare it against what you know from prior
process documents. Don't wait for the administrator to notice a
conflict — flag it yourself.

**Translate invisibly.** Determine field types yourself based on
context. Only confirm with the administrator when genuinely ambiguous.

**One question at a time.** Never compound questions. Ask one thing,
wait for the answer, then ask the next thing.

**Tolerate ambiguity.** Not every answer will be clear or complete.
Record TBDs with specific questions rather than forcing premature
decisions.

**Watch the clock.** At 50 minutes, begin wrapping up. At 60 minutes,
stop regardless of completion. It is better to schedule a follow-up
with a fresh mind than to push through fatigue. Fatigue produces
incomplete answers and missed details.

**Watch for scope discoveries.** If the administrator describes
something that sounds like a new process, a process that belongs in
a different domain, or a structural issue with the domain boundaries:

> "That sounds like it might be a separate process — [description].
> It's not in the Master PRD's process list for this domain. Should
> we pause and update the Master PRD to add it, or is this actually
> part of [current process]?"

Follow the scope change protocol (Section 9 of the Document
Production Process) if needed.

**Don't over-engineer.** Resist the temptation to propose CRM entity
structures, layouts, or technical solutions during the interview.
The process document defines what the business needs, not how the
system implements it. Implementation comes in Phase 5.

**Save implementation detail for Phase 5.** If the administrator
asks about entity names, field internal names, or YAML structure,
redirect:

> "Great question — we'll nail down those implementation details
> when we generate the YAML in Phase 5. For now, let's focus on
> what the process needs the data to be."

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0 | 03-30-26 | Initial release. Replaces entity-interview-data.md, entity-interview-process.md, and entity-interview-synthesis.md. |
