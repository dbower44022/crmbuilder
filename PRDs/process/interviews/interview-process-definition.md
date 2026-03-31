# CRM Builder — Process Definition Interview Guide

**Version:** 2.0
**Last Updated:** 03-30-26 22:30
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

Every process document must contain all nine of the following sections.
Sections 7 and 8 must meet the field-level detail standard. A process
document is not complete until all nine sections are present and meet
their respective standards.

| # | Section | Content |
|---|---------|---------|
| 1 | Process Purpose | What the process accomplishes and its defined end state. |
| 2 | Process Triggers | Preconditions, required data, initiation mechanism, and initiating persona. |
| 3 | Personas Involved | Which personas participate and their specific role in this process. |
| 4 | Process Workflow | What happens, in what order, and what decisions are made. Written as a numbered narrative. |
| 5 | Process Completion | How the process ends — normal completion, alternative end states, early termination, and post-completion handoffs. |
| 6 | System Requirements | What the CRM must do to support this process. Stated as "The system must..." with unique identifiers. |
| 7 | Process Data | Fields this process references or uses to support its work. Grouped by entity with full field-level detail. |
| 8 | Data Collected | Fields this process creates or updates (new data). Grouped by entity with full field-level detail. |
| 9 | Interview Transcript | Complete record of all interview questions and answers from the session. |

### Field-Level Detail Standard

For both Process Data (Section 7) and Data Collected (Section 8),
each field entry must include:

- **Field name** — the human-readable label
- **Field type** — one of the supported field types (see Section 8.3)
- **Required status** — required, optional, conditional (with
  condition stated), or system-calculated
- **Enum values** — for enum and multi-select fields, the complete
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

The interview walks through the nine required sections in a natural
conversation order. The AI does not need to announce section numbers
to the administrator — the conversation should flow naturally. But
the AI must ensure all nine sections are covered before wrapping up.

### Section Checklist

- [ ] 1. Process Purpose
- [ ] 2. Process Triggers
- [ ] 3. Personas Involved
- [ ] 4. Process Workflow
- [ ] 5. Process Completion
- [ ] 6. System Requirements
- [ ] 7. Process Data
- [ ] 8. Data Collected
- [ ] 9. Interview Transcript

---

## Section 1 — Process Purpose

**What the AI is trying to learn:**
What this process accomplishes and what the defined end state is —
the "before and after" picture.

**Opening question:**
> "Let's start with the basics. What does the [Process Name]
> process accomplish — what's different in the world after this
> process runs compared to before it started?"

**Follow-up probes:**
- "How often does this process occur? Daily, weekly, per new
  [record type], on demand?"
- "Is this a one-time event for each [record type], or can it
  repeat?"

**Signs you have enough:**
- Clear statement of what the process accomplishes
- Defined end state — what "done" looks like
- Frequency/volume understood

---

## Section 2 — Process Triggers

**What the AI is trying to learn:**
What must be true before this process can start, what specific
event or action initiates it, and who is responsible for starting it.

### 2.1 Preconditions

> "Before this process can start, what needs to already be in
> place? Think about what records must exist, what status they
> need to be in, or what prior processes must have completed."

**Follow-up probes:**
- "Are there specific data fields that must be populated before
  this process can begin?"
- "Does a prior process need to have completed first? Which one?"
- "Are there any time-based conditions — for example, a waiting
  period or a calendar trigger?"

### 2.2 Required Data

> "Of those preconditions, what specific data must already exist
> in the system for this process to start? For example, does a
> contact record need to exist, or does a particular field need
> to have a value?"

For each required data item identified, collect the field-level
detail:
- What field or record must exist?
- What specific value or state must it be in?
- What happens if the required data is missing — does the process
  simply not start, or is there an error/notification?

### 2.3 Initiation Mechanism

> "How exactly does this process get kicked off? Does someone
> take a specific action, does it happen automatically based on
> a condition, or is it triggered by something external?"

**Follow-up probes:**
- "Is this a manual action — someone decides to start it — or
  is it automatic?"
- "If manual, where does the person go to start it — what do
  they click or do?"
- "If automatic, what condition triggers it?"
- "Can this process be started at any time, or only during
  certain windows?"

### 2.4 Initiating Persona

> "Who is responsible for starting this process? Is it always
> the same persona, or can different people initiate it?"

**Follow-up probes:**
- "Does the initiating persona need any special authority or
  role to start this process?"
- "Can someone delegate the initiation to another person?"

**Signs you have enough:**
- All preconditions identified (records, statuses, prior processes)
- Required data specified with field-level detail
- Initiation mechanism clearly described (manual/automatic/external)
- Initiating persona identified with any authority requirements
- Behavior when preconditions are not met is understood

---

## Section 3 — Personas Involved

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

## Section 4 — Process Workflow

**What the AI is trying to learn:**
The step-by-step sequence of what happens, in enough detail that a
knowledgeable stakeholder could follow the process end to end. This
is the heart of the process document.

### 4.1 Brain Dump First

> "Walk me through this process from start to finish. Don't worry
> about being perfectly organized — just describe what happens,
> step by step, from the moment it's triggered to the moment
> it's complete."

Let the administrator talk freely. Capture the narrative. Then
probe for gaps and detail.

### 4.2 Structured Follow-Up

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

### 4.3 Workflow Completeness Check

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

## Section 5 — Process Completion

**What the AI is trying to learn:**
How this process ends — both the normal successful conclusion and
any alternative endings. What state records are in when the process
is done, who declares it complete, and what happens next.

### 5.1 Normal Completion

> "When this process ends successfully, what does that look
> like? What state are the records in, and how does everyone
> know the process is done?"

**Follow-up probes:**
- "What specific conditions must be met for the process to be
  considered complete?"
- "Is there a final action someone takes — an approval, a
  status change, a notification — that marks it as done?"

### 5.2 Multiple End States

> "Can this process end in more than one way? For example,
> an application might be approved, declined, or withdrawn —
> are there different outcomes like that for this process?"

For each alternative end state:
- "What is this end state called?"
- "What conditions lead to this outcome?"
- "What state are the records left in?"
- "Is this end state final, or can the process be restarted
  or reopened?"

### 5.3 Who Declares Completion

> "Who is responsible for marking this process as complete?
> Is it automatic based on a condition, or does a specific
> persona confirm it?"

**Follow-up probes:**
- "Does the same persona always close it out, or can it vary?"
- "Is there an approval or sign-off required before the process
  can be marked complete?"

### 5.4 Post-Completion Handoffs

> "After this process is complete, does anything else happen?
> Think about whether completing this process triggers another
> process, sends a notification, or creates a task for someone."

**Follow-up probes:**
- "Does anyone need to be notified that this process has
  completed?"
- "Does the completion of this process serve as a precondition
  for any other process?"
- "Is there any follow-up work that happens outside the system?"

### 5.5 Early Termination and Exception Paths

> "How does this process end when something goes wrong or
> someone drops out? Think about situations where the process
> can't continue — the person stops responding, a requirement
> can't be met, or someone decides to cancel."

**Follow-up probes:**
- "Who has the authority to terminate this process early?"
- "When a process is terminated early, what happens to the
  records — are they deleted, archived, or left in a specific
  status?"
- "Can a terminated process be restarted later, or is it
  final?"
- "Are there any cleanup steps when a process ends early —
  notifications, reassignments, or record updates?"

**Signs you have enough:**
- Normal completion conditions clearly defined
- All alternative end states identified with their conditions
- Persona responsible for declaring completion identified
- Post-completion handoffs and notifications captured
- Early termination paths described with authority and cleanup steps
- Record states at each end point understood

---

## Section 6 — System Requirements

**What the AI is trying to learn:**
What the CRM must do to support this process. These are stated as
"The system must..." requirements, each with a unique identifier.

The AI derives most requirements from the workflow discussion, then
confirms and probes for anything missing.

### 6.1 AI Proposes Requirements

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

### 6.2 Probe for Missing Requirements

> "Are there any other things the system must do to support
> this process that I haven't captured? Think about:
> - Anything the system should prevent or enforce
> - Any alerts or reminders that should fire automatically
> - Any reports or views specific to this process
> - Any rules about who can access what data"

### 6.3 Confirm Identifiers

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

## Section 7 — Process Data (Supporting)

**What the AI is trying to learn:**
What data this process references or uses to support its work —
fields that help personas during the process but are not
preconditions for starting it. These are fields the process reads
but does not create.

Note: Required data — fields that must exist before the process
can start — belongs in Section 2 (Process Triggers). This section
captures supporting and reference data only.

This section is grouped by entity. Each field must meet the
field-level detail standard.

### 7.1 Opening

> "Now let's identify the supporting data this process
> references during its work. We've already covered the data
> that must exist for the process to start — this is about
> the additional information that helps people do their job
> during the process, even if the process could technically
> proceed without it."

### 7.2 Walk Through the Workflow

Go step by step through the workflow and identify what supporting
data each step references:

> "At step [N], [persona] needs to [action]. What information
> do they reference or look at to help them do that — beyond
> what we already identified as required to start the process?"

For each field identified, collect the field-level detail:

> "What would you call this field?"
> "What type of data is it — a single selection from a list,
> free text, a date, a number?"

For enum and multi-select fields:
> "What are all the possible values?"

> "In a sentence, what is this field for in the context of
> this process?"

### 7.3 Relationships

When the process references a connection between records — for
example, looking up which mentor is assigned to a client, or
viewing which organization a contact belongs to — capture it as
a data item described in business terms.

> "At this step, you mentioned looking at [the relationship].
> Let me capture that — [proposed description]."

Describe relationships in business language (e.g., "the mentor
assigned to this client" rather than implementation terms). How
the relationship is stored in the system is an implementation
detail handled in Phase 5.

### 7.4 Check Against Prior Process Documents

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

### 7.5 Assign Identifiers

Each data item gets an identifier:
`[DOMAIN]-[PROCESS]-DAT-001`, `[DOMAIN]-[PROCESS]-DAT-002`, etc.

Group by entity in the final document. Present the identifiers
for confirmation.

**Signs you have enough:**
- Every workflow step's supporting data inputs identified
- All fields have complete field-level detail
- Relationships described in business terms
- Conflicts with prior processes resolved
- Fields grouped by entity
- Identifiers assigned and confirmed

---

## Section 8 — Data Collected (New Data)

**What the AI is trying to learn:**
What data this process creates or updates — the fields that are
written during this process. These are the new data contributions
this process makes.

This section is grouped by entity. Each field must meet the
field-level detail standard.

### 8.1 Opening

> "Now let's identify the data this process creates or changes.
> Think about what's different in the CRM after this process
> runs — what new information exists that wasn't there before?"

### 8.2 Walk Through the Workflow

Go step by step through the workflow and identify what data
each step creates or updates:

> "At step [N], [persona] does [action]. What information
> gets recorded at that point?"

For each field identified, collect the field-level detail
using the same approach as Section 7.

### 8.3 Field Type Determination

The AI determines field types based on context. Only confirm
with the administrator when genuinely ambiguous. The following
table lists all supported field types:

| Administrator describes... | Field Type | Notes |
|---|---|---|
| Short text, name, title, code | varchar | Has optional max length |
| Long notes, narrative, comments | text | Multi-line plain text |
| Formatted content with bold, lists, links | wysiwyg | Rich text with formatting |
| Yes or No, true/false, on/off | bool | Boolean |
| Whole number, count, quantity | int | Has optional min/max |
| Decimal, percentage, score, rating | float | Has optional min/max |
| Date only (no time) | date | |
| Date and time | datetime | |
| Dollar amount, cost, revenue | currency | |
| Web address, link | url | |
| Email address | email | |
| Phone number | phone | |
| Fixed set of choices, pick one | enum | Requires complete list of allowed values |
| Fixed set of choices, pick multiple | multiEnum | Requires complete list of allowed values |

> "I'd store this as a [type] — [brief reason]. Does that work?"

### 8.4 Status Fields and Transitions

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

### 8.5 Relationships Created

When the process creates or establishes a connection between
records — for example, assigning a mentor to a client, or
linking a meeting to an engagement — capture it as a data item
described in business terms.

> "This step creates a connection — [proposed description].
> Let me capture the details."

Describe relationships in business language. Implementation
details (how the relationship is stored, link types, field
names) are handled in Phase 5.

### 8.6 Fields Discovered During Workflow Discussion

Process interviews frequently reveal fields that weren't
obvious until the workflow was discussed in detail. Common
examples:

- Reason fields that emerge from decision points ("Why was
  this application declined?" → Decline Reason enum)
- Date fields that emerge from transitions ("When did they
  move to active?" → Activation Date)
- Assignment fields that emerge from handoffs ("Who approved
  this?" → Approved By)
- Note fields that emerge from exception handling ("What
  happened?" → Exception Notes)

When these emerge:
> "That sounds like a new field — [proposed name]. Let me
> capture the details for it."

### 8.7 Assign Identifiers

Continue the DAT identifier sequence from Section 7. If
Section 7 ended at DAT-012, Section 8 starts at DAT-013.

Group by entity in the final document. Present the identifiers
for confirmation.

### 8.8 TBD Handling

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
- Relationships described in business terms
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

1. Process Purpose — clear statement of what the process accomplishes? ✓/✗
2. Process Triggers — preconditions, required data, mechanism, and persona? ✓/✗
3. Personas Involved — specific roles, not just names? ✓/✗
4. Process Workflow — followable narrative? ✓/✗
5. Process Completion — all end states, handoffs, and early termination? ✓/✗
6. System Requirements — identifiers assigned? ✓/✗
7. Process Data — field-level detail for every supporting field? ✓/✗
8. Data Collected — field-level detail for every field? ✓/✗

If any section is incomplete:
> "Section [N] isn't quite at the level of detail we need.
> Specifically, [what's missing]. Can we fill that in now,
> or should we schedule a follow-up?"

### Summary

> "Let me summarize what we've established for the [Process
> Name] process:
>
> - Purpose: [one sentence]
> - Triggers: [preconditions, mechanism, initiating persona]
> - Personas: [list with roles]
> - Workflow: [N] steps from [start] to [end]
> - Completion: [normal end state plus N alternative end states]
> - System Requirements: [N] requirements ([first ID] through
>   [last ID])
> - Process Data: [N] supporting fields across [N] entities
> - Data Collected: [N] new fields across [N] entities
> - TBD items: [N]
>
> Does that feel complete?"

### Document Production

After confirmation, produce the process document as a Word
document with all nine required sections.

For Sections 7 and 8, present field data in tables grouped
by entity:

**Entity: [Entity Name]**

| ID | Field Name | Type | Required | Enum Values | Description |
|----|-----------|------|----------|-------------|-------------|
| [DOMAIN]-[PROCESS]-DAT-001 | [Name] | [Type] | [Yes/No/Conditional] | [Values or —] | [Description] |

Section 9 (Interview Transcript) must contain the complete
record of all questions asked and answers given during the
session. Include the full conversational exchange — do not
summarize or condense the interview content. This provides
an audit trail and allows future reviewers to understand the
reasoning behind decisions made during the interview.

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

**Capture fields as they emerge.** Don't wait for Sections 7 and 8
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
| 2.0 | 03-30-26 | Major restructure: Split Process Purpose and Trigger into separate sections (1 and 2). Added Process Triggers section with preconditions, required data, initiation mechanism, and initiating persona. Added Process Completion section (5) covering normal completion, multiple end states, early termination, and post-completion handoffs. Reframed Process Data (7) as supporting data — required prerequisite data moved to Process Triggers. Replaced field type table with authoritative 14-type list from YAML schema. Added relationship guidance to Sections 7 and 8. Added Interview Transcript as Section 9. Document now has nine required sections. |
| 1.0 | 03-30-26 | Initial release. Replaces entity-interview-data.md, entity-interview-process.md, and entity-interview-synthesis.md. |
