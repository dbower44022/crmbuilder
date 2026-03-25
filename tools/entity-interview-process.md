# CRM Builder — Entity Process Interview Guide

**Version:** 1.0  
**Last Updated:** March 2026  
**Purpose:** AI interviewer guide for Phase 2 Session B — Process Definition  
**Changelog:** See end of document.

---

## How to Use This Guide

This guide is for Session B of the entity definition process — defining
how a single entity variant behaves over its lifetime. It covers creation,
editing, lifecycle transitions, and termination.

**Run Session B after Session A** for the same entity variant. The field
inventory from Session A is prerequisite context — load it before starting.

**One entity variant per session.** Same rule as Session A — never mix
variants.

**Session length:** 30–45 minutes. Stop at 45 minutes.

**Key insight:** Process sessions frequently reveal additional fields not
identified in the data session. These fields emerge naturally from process
discussion — for example, "Pause Reason" comes up when discussing the
pause process, not when listing fields. Capture these additions and include
them in the Session C synthesis.

**Output:** A complete process definition for this entity variant, plus
any additional fields discovered. Ready for Session C synthesis.

---

## Before the Session Begins

### Opening

> "In our last session we defined all the data fields for [variant].
> Today we're covering the processes — what actually happens when a
> [variant] record is created, how it changes over time, and how it
> ends.
>
> Process discussions often reveal additional fields we didn't think
> of in the data session, so don't be surprised if new things come up.
>
> Same rule as before — if you're not sure about something, I'll
> mark it TBD and add it to the task list. Ready?"

### Context Load

> "Before we start — from our data session, [variant] has these
> lifecycle stages: [list status values from Session A]. We'll walk
> through each transition today."

---

## Section 1 — Record Creation

**What the AI is trying to learn:**
How a new [variant] record comes into existence — who creates it,
where the data comes from, and what happens immediately after creation.

**Opening question:**
> "Let's start at the beginning. How does a new [variant] record
> get created? Does someone fill out a form, does an administrator
> create it manually, does it come from an integration?"

**Follow-up probes:**

> "Who initiates the creation — the [variant] themselves, an
> administrator, an intake coordinator, or someone else?"

> "Where does the initial data come from — a web form, an email,
> a phone call, an import?"

> "When a new record is created, what happens automatically?
> For example, does a welcome email get sent, does someone get
> notified, does a task get created?"

> "Is there a review or approval step before the record is
> considered active? Who does the review?"

> "Are there any fields that get set automatically at creation —
> for example, a default status, a timestamp, an assigned
> coordinator?"

**Additional fields often discovered here:**
- Created by / assigned to (automatic)
- Intake date / application date
- Source / how they applied
- Initial assigned reviewer
- Notification recipients

---

## Section 2 — Lifecycle Transitions

**What the AI is trying to learn:**
What happens at each status change — who triggers it, what data
is captured, what notifications go out, and what other records
are affected.

Work through each status transition identified in Session A.

### For Each Transition

> "Let's talk about what happens when a [variant] moves from
> [Status A] to [Status B]. How does that transition happen?"

**Follow-up probes for each transition:**

> "Who triggers this change — the [variant] themselves, an
> administrator, an automated rule, or something else?"

> "What has to be true before this transition is allowed?
> Are there any prerequisites or approvals required?"

> "When this transition happens, what data gets recorded?
> For example, a date, a reason, who approved it?"

> "Who gets notified when this happens — the [variant],
> their assigned contact, an administrator, someone else?"

> "Does this transition affect any other records? For example,
> does it trigger reassignment of related records, lock certain
> fields, or create new records?"

> "Can this transition be reversed? If so, how?"

**Additional fields often discovered here:**
- Transition date fields (date paused, date activated, etc.)
- Reason fields (pause reason, rejection reason, departure reason)
- Approval fields (approved by, approval date)
- Notification flags

### Common Transitions to Cover

For **mentor-type** variants:
- Application submitted → Under Review
- Under Review → Provisional / Rejected
- Provisional → Active (after training + agreement)
- Active → Paused (temporary hold)
- Paused → Active (resuming)
- Active → Inactive (long-term stop)
- Inactive → Active (reactivation)
- Any → Resigned / Departed

For **client-type** variants:
- Request submitted → Under Review
- Under Review → Assigned / Declined
- Assigned → Active engagement
- Active → Completed / Abandoned

For **organization-type** variants:
- Prospect → Active partner
- Active → Inactive / Former

---

## Section 3 — Record Editing

**What the AI is trying to learn:**
Who can edit which fields, when editing is restricted, and how
changes are tracked.

**Opening question:**
> "Once a [variant] record exists and is active, who can make
> changes to it and what can they change?"

**Follow-up probes:**

> "Are there any fields that should be locked once set — for
> example, fields that are set at creation and should never
> change?"

> "Are there fields that only certain staff should be able
> to edit — for example, sensitive fields that only
> administrators can change?"

> "When important fields change — like status or assignment —
> should the change be logged with a timestamp and who made it?"

> "Are there any fields that are set by the system and should
> never be manually edited?"

**Additional fields often discovered here:**
- Read-only fields (calculated, system-set)
- Audit trail requirements
- Field-level permissions

---

## Section 4 — Record Termination

**What the AI is trying to learn:**
What happens when a [variant] record reaches its end state —
resignation, departure, closure, archival.

**Opening question:**
> "What happens when a [variant] reaches the end of their
> relationship with your organization? Walk me through
> what occurs."

**Follow-up probes:**

> "When a [variant] leaves or is closed, what happens to
> the records connected to them? For example, do active
> engagements get reassigned, do related records get
> archived?"

> "Is the record ever fully deleted, or is it always
> retained for historical reference?"

> "Can a [variant] return after leaving? If so, what
> process do they go through to be reactivated?"

> "Are there any exit interviews, surveys, or closing
> communications that need to be tracked?"

> "Who is responsible for managing the offboarding
> process — updating the record, notifying affected
> parties, reassigning work?"

**Additional fields often discovered here:**
- Termination reason
- Termination date
- Eligible for rehire / return
- Exit survey completed
- Offboarding checklist items

---

## Section 5 — Notifications and Communications

**What the AI is trying to learn:**
The automated communications triggered by events in this
entity's lifecycle.

**Opening question:**
> "Let's make sure we've captured all the automated
> communications tied to [variant] events. What emails,
> reminders, or notifications should the system send
> automatically?"

**Follow-up probes:**

> "When a new [variant] record is created, who gets notified
> and what do they receive?"

> "Are there any reminder emails — for example, when a
> deadline is approaching or an action hasn't been taken
> within a certain time?"

> "When a status changes, who gets notified?"

> "Are there any recurring communications — annual renewals,
> periodic check-ins, milestone recognitions?"

**Additional fields often discovered here:**
- Notification preference fields
- Opt-in/opt-out flags
- Last contacted date
- Communication history fields

**Note:** Complex notification workflows will be flagged as
manual configuration items (Administration → Workflows).

---

## Section 6 — Integrations and Automation

**What the AI is trying to learn:**
How external systems interact with this entity's lifecycle.

**Opening question:**
> "Are there any external systems involved in the [variant]
> lifecycle — for example, a website form that creates records,
> a calendar system that syncs, or a training platform that
> updates completion status?"

**Follow-up probes:**

> "Does any data flow automatically from an external system
> into this record? What data and when?"

> "Does any data flow from this record out to an external
> system? What and when?"

> "Are there any manual steps that currently happen outside
> the CRM that should ideally be automated?"

---

## Section 7 — Wrap-Up

### 7.1 Summary

> "Let me summarize the processes we've defined for [variant]:
>
> - Creation: [brief description]
> - Key transitions: [list]
> - Termination: [brief description]
> - Additional fields discovered: [list any new fields]
> - [X] open TBD items
>
> Does that feel complete? Is any process missing?"

### 7.2 Additional Fields Review

> "During this session we identified some additional fields
> that weren't in our data session:
> [list new fields]
>
> I'll add these to the field inventory before producing
> the final specification."

### 7.3 Task List Review

> "Here are the open items flagged during this session:
> [list TBDs and manual config items]"

### 7.4 Next Steps

> "We now have the complete picture for [variant] — all the
> data fields from Session A and all the processes from today.
>
> I'll synthesize both into the final specification: a PRD
> section, a deployment YAML file, and a task list.
>
> The next entity variant session would cover [next variant].
> Does that timing work for you?"

---

## AI Behaviors

**Stay in process mode.** If the user starts discussing new data
fields unrelated to processes, note them and say: "Good catch —
I'll add that to the field list and we'll include it in the
synthesis."

**Follow threads.** "What happens next?" is often the most
productive question. Processes have natural flows — follow them.

**Capture every trigger.** For every process, identify: who/what
triggers it, what conditions must be met, what happens as a result.

**Flag manual config explicitly.** Complex workflows, formula
fields, and role-based permissions cannot be deployed by CRM
Builder. Flag them clearly:
```
MANUAL CONFIG — [description]
                Configure in: [location] after deployment
```

**Watch the clock.** At 40 minutes, wrap up and close. Schedule
a follow-up if needed.

**One variant at a time.** If the user starts describing a
different variant's process, redirect: "Let's finish [current
variant] first and we'll cover [other variant] in its own session."

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0 | March 2026 | Initial release — split from original entity-interview.md |
