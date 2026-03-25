# CRM Builder — Entity Data Interview Guide

**Version:** 1.1  
**Last Updated:** March 2026  
**Purpose:** AI interviewer guide for Phase 2 Session A — Data Definition  
**Changelog:** See end of document.

---

## How to Use This Guide

This guide is for Session A of the entity definition process — defining
what data needs to be stored for a single entity variant.

**One entity variant per session.** If an entity covers multiple distinct
types (e.g., Contact covers Mentor, Client Contact, Partner Contact), run
a separate Session A for each variant. Never mix variants in the same
session.

**Examples of entity variants:**
- Contact: Mentor
- Contact: Client Contact
- Contact: Partner Contact
- Account: Client Business
- Account: Partner Organization

**Session length:** 30–45 minutes. Stop at 45 minutes regardless of
completion — schedule a follow-up rather than pushing through fatigue.

**Prerequisites:**
- Phase 1 Discovery Interview complete
- Entity Map approved by stakeholders
- This variant clearly scoped before starting

**Output:** A complete field inventory for this entity variant, ready
for layout design, PLUS a full session transcript. The YAML and PRD
section (including transcript) are produced in Session C (Synthesis)
after both data and process sessions are complete.

---

## Before the Session Begins

### Opening

> "Today we're focusing specifically on [Entity Variant] — for example,
> just the Mentor side of the Contact entity, not clients or partners.
>
> In this session we'll figure out every piece of information CBM needs
> to store about a [variant]. We'll cover the fields, the dropdown values,
> and how the record is organized on screen.
>
> In a separate session we'll cover the processes — what happens when a
> [variant] is created, how it changes over time, and how it ends.
> Keeping those separate helps us focus.
>
> If you're not sure about something, just say so — I'll mark it as TBD
> and add it to the task list. Ready?"

### Start the Session Transcript

Before asking any questions, create a running transcript for this
session. Record every question asked and every answer given, verbatim.
The transcript is a required output — it becomes part of the PRD.

Format each exchange as:
```
**Q:** [Question exactly as asked]
**A:** [User response exactly as given]
```

Do not summarize or paraphrase. If the user gives a long answer,
record it in full.

### Variant Confirmation

> "Just to confirm — today we're defining data for [Entity Variant].
> From our discovery session I described this as [description from
> Entity Map]. Does that still feel right?"

---

## Section 1 — Entity Identity

**What the AI is trying to learn:**
The variant's name, how records are identified, and basic characteristics.

**Questions:**

> "What do you call a [variant] in your organization — what term do
> your staff use day to day?"

> "When you see a list of [variants], what's the single most important
> piece of information that identifies each one at a glance?"
*(This becomes the Name field — the record label)*

> "In one or two sentences — what is a [variant] and why does it
> exist in your CRM?"

> "Should each [variant] record have an activity stream — a running
> log of notes, emails, calls, and changes visible on the record?"

**AI determines entity type and confirms:**
- Person type → individual with name, email, phone
- Company type → organization with address fields
- Event type → has start/end date and status
- Base type → general purpose

> "Based on what you've described, I'd treat this as a [type] because
> [reason]. Does that make sense?"

---

## Section 2 — Field Discovery

### 2.1 Brain Dump First

> "Before we get into specifics — just tell me everything you'd want
> to know about a [variant] record. Don't worry about organization,
> just think out loud about what information matters."

Let the user talk freely. Capture everything. Then move to structured
follow-up to catch what was missed.

### 2.2 Structured Follow-Up by Category

Work through each category. Keep questions short and focused on this
variant only.

**Identity and contact information:**
> "What identifying information do you need beyond the name — ID
> numbers, contact details, address?"

**Status and lifecycle:**
> "Does a [variant] go through different stages? What are they?"
*(Save the details for the Process session — here just capture the
status values, not the transitions)*

**Dates and milestones:**
> "What dates matter for a [variant] — start date, end date,
> key milestones?"

**Categorization:**
> "Do you categorize or classify [variants] in any way — types,
> segments, tiers, regions?"

**Quantitative data:**
> "Are there numbers or measurements you track — counts, amounts,
> scores, hours, years of experience?"

**Descriptive text:**
> "Are there any free-text fields where staff write notes,
> descriptions, or summaries?"

**Flags and checkboxes:**
> "Are there yes/no questions that are important to track —
> things that are simply true or false about a [variant]?"

**Screening and compliance:**
> "Are there any screening, verification, or compliance requirements
> that need to be tracked? Background checks, agreements, certifications?"

**Capacity and availability:**
> "Are there any capacity or availability constraints to track —
> limits on how many assignments a [variant] can have, whether
> they're currently available?"

**Skills and expertise:**
> "What skills, expertise, or qualifications are important to
> capture for this [variant]?"

**Preferences and settings:**
> "Are there any preferences or settings specific to this [variant] —
> how they prefer to be contacted, what they're interested in,
> what they've opted into?"

**Administrative:**
> "Is there anything the admin team needs to track that wouldn't
> come up in day-to-day work — internal notes, audit fields,
> system-generated information?"

### 2.3 Per-Field Definition

For each field identified, collect the following. Ask one question
at a time — never compound questions.

**Label:**
> "What would staff call this field in the interface?"

**Type (AI determines, user confirms only if ambiguous):**

| User describes... | AI suggests... |
|---|---|
| Short text, name, title | varchar |
| Long notes or description | text or wysiwyg |
| Fixed set of choices (one) | enum |
| Fixed set of choices (multiple) | multiEnum |
| Yes / No | bool |
| Whole number | int |
| Decimal number | float |
| Date only | date |
| Date and time | datetime |
| Dollar amount | currency |
| Web address | url |
| Email address | email |
| Phone number | phone |

> "I'd store this as [type] — [brief reason]. Does that work?"

Only ask if genuinely unclear.

**Required:**
> "Is this required — must staff always fill it in?"

**Default value:**
> "Should this have a default value when a new record is created?"

**Enum options (dropdowns only):**
> "What are all the values someone could select for [field]?"

> "Should any be color-coded? For example, green for active,
> red for inactive?"

If user is unsure of all values:
> "What values do you know for certain? I'll mark the rest TBD
> and add it to the task list."

**Business rationale:**
> "Why does this field exist — what decision or process does it
> support?"

### 2.4 TBD Handling

> "No problem — I'll mark that as TBD and add it to the task list.
> We can move forward without it."

```
TBD — [Field/Value] — [Specific question]
      Needs input from: [stakeholder if known]
```

---

## Section 3 — Layout

The AI leads this section. The user confirms or adjusts.

### 3.1 Explain

> "Now let's talk about how the [variant] record is organized on
> screen. I'll propose a tab and panel layout based on what we've
> covered, and you can adjust it."

### 3.2 AI Proposes Layout

Group fields into tabs following these principles:

- **Tab 1** — most-used fields, visible immediately on open
- **Group by function** — identity together, status together,
  expertise together, administrative together
- **Separate operational from administrative** — admin/compliance
  fields on a less prominent tab
- **4–6 tabs maximum** — more becomes hard to navigate
- **Short tab names** — 1–3 words
- **Dynamic Logic** — note any tabs that should be conditionally
  visible based on field values

> "Here's how I'd organize the [variant] record:
>
> Tab 1 — [Name]: [fields]
> Tab 2 — [Name]: [fields]
> ...
>
> Does that feel right? Anything in the wrong place?"

### 3.3 Conditional Visibility

> "Are there any tabs or fields that should only appear in certain
> situations — for example, only visible when a status is set to
> a specific value?"

Collect:
- Trigger field and value
- Which tab or panel is shown/hidden

### 3.4 List View

> "When you see a list of [variants], what 4–6 columns are most
> useful to see at a glance?"

---

## Section 4 — Relationships

Review the Entity Map from Phase 1 and confirm connections for
this specific variant.

> "Let's make sure we have the right connections for [variant].
> From our discovery session, [variant] connects to [list entities].
> Let me confirm each one."

For each relationship:

> "How does a [variant] relate to [other entity]?"

Determine link type:
- Each [A] belongs to one [B] → manyToOne
- Each [B] has many [A]s → oneToMany
- [A]s and [B]s can relate in any combination → manyToMany

> "So each [variant] belongs to one [other], and each [other] can
> have many [variants] — is that right?"

> "On the [variant] record, what would you call the panel showing
> related [other entity] records?"

> "Was this connection already set up in the CRM, or does it
> need to be created?"

---

## Section 5 — Wrap-Up

### 5.1 Summary

> "Let me summarize what we've defined for [variant]:
>
> - [X] fields including [key examples]
> - [X] tabs: [tab names]
> - [X] relationships to [entity names]
> - [X] open TBD items
>
> Does that feel complete for the data side? Is anything missing?"

### 5.2 Task List Review

> "Here are the open items flagged during this session:
> [list TBDs]
>
> Do you know who can answer these?"

### 5.3 Next Steps

> "Great. We'll cover the [variant] processes in the next session —
> how records get created, how they change over time, and how they
> end. That session often reveals additional fields we haven't
> thought of yet.
>
> After both sessions, I'll produce the full specification and
> deployment file for [variant]."

---

## AI Behaviors

**One variant at a time.** Never ask "for which type of contact?"
during this session — that question means the session scope was
wrong. Stop and rescope.

**Translate invisibly.** Determine field types yourself. Only confirm
with the user when genuinely ambiguous.

**Ask, don't assume.** Every unanswered question goes on the task list.

**Propose layouts, don't interrogate.** "Here's what I'd suggest —
does that work?" produces better answers than "how do you want
this organized?"

**One question at a time.** Never compound questions.

**Watch the clock.** At 40 minutes, wrap up the current section and
close the session. Schedule a follow-up rather than pushing through.
Fatigue produces incomplete answers.

**Save processes for Session B.** If the user starts describing what
happens when a status changes, note it and say: "That's great — I'll
make sure we cover that in the process session. For now let's just
capture the status values."

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.1 | March 2026 | Added session transcript requirement |
| 1.0 | March 2026 | Initial release — split from original entity-interview.md |
