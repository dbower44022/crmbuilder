# Application Generation Gap Register — Mentor Application against the prototype

**Document level:** Implementation (Level 3). Product and repository names are permitted.
**Engagement:** CRMBUILDER. Evidence: the Mentor Application process definition in the Cleveland Business Mentors engagement (record PROC-001), and the prototype application in the cbm-client-intake repository.
**Status:** Draft v0.3

## Revision control

| Version | Last Updated | Author | Change |
|---|---|---|---|
| 0.1 | 09-05-26 00:04 | Claude (Cowork) with Doug | First draft from the 09-05-26 architecture discussion. |
| 0.2 | 09-05-26 00:10 | Claude (Cowork) with Doug | Framing decision replaced: the generator is an AI agent (Doug, 09-05-26). Gaps re-scoped. |
| 0.3 | 09-05-26 00:17 | Claude (Cowork) with Doug | Rewritten for a technical, non-expert reader (Doug, 09-05-26): every record reference now states what the record says; identifiers appear only as pointers in parentheses. No change to the gaps themselves. |

## What this document is

CRM Builder is meant to become a commercial product: a non-technical user describes a business process, and an application that runs that process on top of a CRM is built for them without a software development team. The cbm-client-intake application was built by hand, with Claude doing the development, as a prototype to learn what such an application must do. It has run in production at Cleveland Business Mentors for months.

This register is a test. We took one process that is now fully written up in CRM Builder, the Mentor Application, and asked: if Claude were handed only that write-up, could it build an application equivalent to the prototype? Where it could not, what is missing?

The short answer is that the write-up is a good description of the business process and a poor specification of an application. It says what happens to a mentor candidate. It does not say what the form looks like, what the review team sees on screen, what happens when the mailbox system is down, or who is allowed to press which button. Those are the gaps.

## The Mentor Application in one paragraph

A prospective mentor fills in the Become a Mentor form on the website. The submission is saved exactly as sent, a thank-you email goes out, and a mentor record is created or updated depending on whether the person is already known. The record starts at Candidate and appears in a queue that the Mentor Administration Team watches. The Team does a quick legitimacy check, then a thorough evaluation with interviews, then votes. An accepted candidate gets a chapter email address and training, becomes Provisional, and after training the Team votes again. If approved, a CRM login is created and the mentor becomes Active. At any point the candidate can be Declined (always with a reason) or marked Dormant if they stop responding.

## How the application will be built

The decision that shapes everything below (Doug, 09-05-26): **CRM Builder holds the definition; Claude writes, tests, deploys and maintains the application code from that definition.** A technical user runs Claude, approves changes and holds the credentials, but does not write code. This is how the prototype was built, so it is proven.

Two rules follow. Generated code is never hand-edited in a way that has to survive the next regeneration; if the definition cannot express something, the definition is fixed, not the code. And every generated application shares a common core, built once and reused, so Claude only has to build the part that is specific to each process.

Because the builder is Claude and not a rigid code generator, prose in the definition is acceptable. What is not acceptable is prose that is incomplete, contradicts itself, or is silent on something the application must do. In those cases Claude will make a choice, and the next time the application is rebuilt Claude may make a different one. Each gap below is a place where that would happen today.

## Layer 1 — What the definition does not say

### GAP-01 The status lifecycle is complete but spread across seven places

An application needs one list of allowed moves: from which status to which status, who may make the move, what must be filled in before it is allowed, and what happens automatically afterward. For the Mentor Application that list can be assembled today, but only by reading the process steps and six separate decision records. Each decision settles one piece: which statuses exist and in what order; that each vote is recorded with its outcome and date; that a decline always records a reason; which emails are automatic and which a Team member sends by hand; that the CRM login is created when the Team sets Approved; and that a candidate can be Declined or Dormant at any point. Nothing states the whole lifecycle in one place.

There is also a known contradiction. The definition says a person moves the candidate to Provisional after the chapter email and training are set up. The prototype creates the mailbox automatically when the Team sets Accepted-Provisional and then moves the candidate to Provisional itself. Until that is ruled, the lifecycle cannot be written down as one list.

What to add: a transition table in CRM Builder, one row per allowed move, carrying the actor, the required fields and the automatic actions. This needs to be structured rather than prose, because the tests, the screens and the automations all refer to individual transitions.

### GAP-02 Nothing says what each field is for

The definition links forty-eight fields to the process, but every link says the same thing: this process touches this field. An application needs to know more. Is the field something the applicant types into the public form? Something a Team member edits during review? Something the system sets on its own, such as the starting status? Something shown but never edited? In the prototype those four groups are different code. Today Claude would have to guess the group from the field's name.

What to add: a role on each field link (collected by the form, edited by the Team, set by the system, display only), and for form fields, the order and grouping they appear in.

### GAP-03 The public form is not described

The definition's entire description of the form is that the applicant "completes the form, accepts the terms, submits." The prototype form has a great deal more: which fields are required, which option lists they draw from, a file upload for a resume, a hidden trap field to catch bots, one consent checkbox that sets six separate yes/no fields across two records, a message shown to the applicant on success, a different message when the application is refused because the person is already an active mentor, and code that turns the submitted data into two CRM records.

What to add: a form definition covering the field set from GAP-02, validation, how each submitted value maps to one or more CRM fields, file handling, spam protection, and the exact messages the applicant sees. Prose would do for most of this, but the one-to-many consent mapping and the messages are exactly what prose tends to leave out.

### GAP-04 Repeat applicants are handled; what may be overwritten is not

The definition fully covers what happens when the email on a new application matches an existing person: a brand-new person is created; someone recruiting had marked as a prospect becomes a candidate; someone declined earlier becomes a candidate again with a note; anyone in any other status is refused, told to contact CBM, and the Team is notified. That is complete.

What it does not say is what happens to the existing record's other fields. The prototype fills in only fields that are empty and never overwrites anything a staff member has curated. The definition is silent, so a rebuild could overwrite.

What to add: one statement of the fill policy — which fields a repeat submission may fill and which it may never change.

### GAP-05 Automatic actions are named; what happens when they fail is not

The definition names the automatic actions: the thank-you email, the notification to the Team on a conflict, the chapter email account, training setup, the CRM login. The prototype also encodes what each action needs before it runs and what happens if it fails. The candidate's status only moves to Provisional once the mailbox is confirmed to exist. If adding the mailbox to the members group fails, the rest still succeeds and the failure is shown. If mailbox creation is switched off and the mailbox is missing, approval is blocked with a message. None of this is in the definition, and it is exactly what decides whether a rebuilt application behaves the same on a bad day.

What to add: for each automatic action, its precondition, the condition that confirms it worked, and its failure behaviour (block, or continue and show the reason). CRM Builder already has an automation record type that could hold this; for this engagement it is empty.

### GAP-06 The outside systems the application talks to are not recorded

The prototype talks to four systems: the CRM, a directory service that creates mailboxes and manages groups, an email sender, and the website. Each needs credentials and settings, which the prototype keeps in environment variables and an encrypted settings screen. CRM Builder records individual settings but has no notion of an external system, what it is used for, or what it needs.

What to add: an external system record naming the system, the capabilities used (check a mailbox exists, create one, manage groups, send mail), the settings each capability needs, and a requirement for a test-connection action. This is the one place product names belong.

### GAP-07 What the Team sees on screen is not described

The definition says a new candidate "appears in the Mentor candidates view," and defines that one list: which columns, which filter. The prototype's Mentor Administration tool has far more: a roster of every mentor with search, filters and sorting; a detail screen with a read-only summary at the top and a tabbed editor below; buttons for the allowed status moves; a separate save for the mentor's permission groups; and a bulk check that sweeps every mentor and reports problems. Nothing in the definition describes any of that, so a rebuild would produce whatever Claude thought reasonable.

What to add: a screen definition (list or detail) built from the views, the field groups from GAP-02, the transition buttons from GAP-01, and any bulk actions, each screen tied to the persona that uses it. This is the gap where two rebuilds would differ most.

### GAP-10 The review paperwork is named but has nowhere to live

The definition requires three kinds of record during review: each Team member's written opinion after the interviews, a decision summary for each vote (outcome, date, decline reason if declined), and the provisional-period checklist (training done and when, ethics agreement, background check, mentor code accepted). The checklist items exist as fields. The opinion notes and the decision summaries do not exist anywhere in the CRM, and the prototype does not capture them either.

What to add: either fields and entities for these in the CBM engagement, or a general pattern in CRM Builder — a note attached to a process step, a decision record attached to a transition — that Claude applies automatically at every vote.

### GAP-11 Who may do what, and as whom, is implicit

The prototype runs every read and write as the signed-in staff member, so the CRM's own permissions apply. The one exception is creating a CRM login, which only an administrator may do, so that runs under a dedicated administrator account. Access to the tool itself is limited to members of the Mentor Administration Team. The definition names the personas and the CRM roles exist, but nothing says which actions run as the user, which need the administrator account, or which team membership opens which screen.

What to add: on each screen and each automatic action, the identity it runs as (the signed-in user or the service account) and the rule that admits a persona to it.

### Two items moved to a different process

The prototype's Mentor Administration tool also computes five live client counts per mentor (active clients, maximum, available, assigned in the last thirty days, lifetime) and a completeness check that marks a mentor record Complete or Incomplete with reasons. Those belong to the day-to-day Mentor Administration process, which takes over once a mentor is Active, not to the application process. They stay on the list for that process (record PROC-002) and are not counted against this one.

## Layer 2 — What Claude needs beyond the definition

### GAP-12 A defined role for the Claude that builds applications

CRM Builder already stores agent profiles, skills and operating rules, and loads the relevant rules into a Claude session automatically at start. There is not yet a profile for the Claude that builds an application: what it reads, in what order, what it produces, what it may not decide on its own, and when it must stop and ask.

What to add: an application-builder agent profile with a skill that walks the definition in a fixed order, and a standing rule that any behaviour the definition does not state is raised as a planning item rather than invented.

### GAP-13 A common core that Claude reuses instead of rebuilding

The prototype contains a large amount of code that every generated application needs identically (listed under Layer 3). It lives inside one hand-built application. If Claude starts each new client from an empty repository, it rebuilds that core each time, differently.

What to add: the core extracted into a versioned library with a written contract — how a form registers itself, how a status transition is declared, how an automatic action names the outside system it uses — so Claude builds only the process-specific layer. This is the largest item in the register and I have not sized it.

### GAP-14 Tests generated from the definition

Nothing today checks that a built application does what the definition says. CRM Builder has the start of a verification generator for CRM configuration, but nothing for application behaviour.

What to add: a test specification produced from the definition — one case per status transition, per repeat-applicant branch, per automatic action's precondition and failure path, per form outcome message — that the application must pass before it is deployed. This is what makes it safe to rebuild from a changed definition.

### GAP-15 A trail from each piece of code back to the definition

The prototype's code cites decisions in comments, by hand and inconsistently. There is no rule that generated code, tests and screens name the parts of the definition they implement.

What to add: a rule that every generated module, test and screen carries the identifiers of the process, transition, form, view, automation and requirement it realises. Then a change to one part of the definition can be traced to the code it affects, and a rebuild can be reviewed as a diff against the definition rather than as a pile of code.

### GAP-16 A procedure for "the definition changed"

The prototype is maintained by prompting Claude. There is no written procedure for bringing an application back into line after its definition changes: which records changed, which code is affected (GAP-15), which tests must run again (GAP-14), how the technical user approves the change, and how it is deployed.

What to add: that procedure, recorded as a process in the CRMBUILDER engagement and executed by the agent profile of GAP-12.

## Layer 3 — What the common core contains

These are services the prototype already has and every generated application needs unchanged. They are listed to give GAP-13 a scope.

- Capture and delivery: every submission is saved to the application's own database before the CRM is touched; if that database is down, the submission is written to a file and replayed later (required by the definition, not yet built); a background worker delivers to the CRM and can safely retry without creating duplicates; a receipt record in the CRM tracks each submission with one status vocabulary.
- Reconciliation: a scheduled sweep and a manual button that re-check the CRM against the capture database and fix drift.
- Sign-in with CRM credentials, so the CRM enforces permissions, plus a service account for administrator-only actions.
- Tolerance for drift: submitted option values are checked against the CRM's live option lists and a mismatch is noted rather than failing the write; phone numbers are normalized; file attachments are uploaded.
- Email sending from templates through a configured sender, switched on or off by settings.
- An encrypted settings store with an administrator screen and a test-connection button per outside system.

## Where the definition is ahead of the prototype

In three places the definition is right and the prototype is behind, and each is already recorded as a planning item for the prototype: the four-way handling of repeat applicants, the automatic thank-you email under a setting, and the required decline reason. Under the new approach these become the first three test cases (GAP-14) for the rebuilt application rather than patches to the prototype.

## Next required step

Rule the contradiction in GAP-01: does a person move the candidate to Provisional after setting up email and training, as the definition says, or does the application do it once the mailbox exists, as the prototype does? Then write the transition table (GAP-01) and the field roles (GAP-02). Everything in Layer 2 depends on those two.
