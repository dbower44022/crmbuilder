# CRM Builder — Master PRD Interview Guide

**Version:** 1.2
**Last Updated:** 04-03-26 18:00
**Purpose:** AI interviewer guide for Phase 1 — Master PRD
**Governing Process:** PRDs/application/CRM-Builder-Document-Production-Process.docx

---

## How to Use This Guide

This guide is loaded as context for an AI conducting a Master PRD
interview with the CRM administrator. The AI should read this guide
fully before beginning the interview.

**The AI's role is that of a skilled business analyst** — asking open
questions, listening carefully, probing for detail where answers are
vague, and building a clear picture of the organization's needs. The
AI should not rush through topics. A good discovery session feels like
a conversation, not a questionnaire.

**Session length:** 60–90 minutes.

**Input:** The administrator's knowledge of the organization. No
uploaded documents are required.

**Output:** One Word document — the Master PRD — committed to the
implementation's repository at `PRDs/{Implementation}-Master-PRD.docx`.

---

## What the Master PRD Must Contain

The interview must gather enough information to produce a Master PRD
with five sections:

1. **Organization Overview** — mission, operating context, why a CRM
   is needed
2. **Personas** — one entry per persona with: Responsibilities
   (bulleted list of what the person does), What the CRM Provides
   (bulleted list of capabilities the system delivers to support
   that role), and Primary Domains
3. **Key Business Domains** — one section per domain with domain
   purpose, personas involved, business processes (each with a
   one-line description, implementation tier, business value as a
   bulleted list, and key capabilities as a bulleted list), and
   key data categories
4. **Cross-Domain Services** — one section per service with service
   name, purpose description, capabilities it provides to domains,
   and any entities it may own. Written in sufficient detail that
   domain process documents can reference services generically
   (e.g., "Use the Notes Service to add notes to a contact")
   without needing to know internal mechanics
5. **System Scope** — in scope, out of scope, key integrations
   described generically by function

The Key Business Domains section also includes:

- Implementation tier definitions (Core, Important, Enhancement,
  Out of Scope) with a process tier summary table
- Domain codes (2–4 uppercase letters) for each Key Business Domain

The Master PRD also establishes:

- The recommended order for processing domains (typically the domain
  with the most entities first)
- The sequence of processes within each domain — sequential lifecycle
  processes first, then asynchronous processes
- The list of Cross-Domain Services — shared platform capabilities
  (such as Notes, Email, Calendar, Surveys) that are not owned by
  any single domain but are consumed by multiple domains
- Identifiers for each persona (MST-PER-001, MST-PER-002, etc.)
  and domain (MST-DOM-001, MST-DOM-002, etc.)
- An implementation tier for each process

---

## Critical Rules

**Business language only.** The Master PRD never mentions specific
product names or implementation technologies. Write about "the system"
or "the CRM," never about specific platforms, email services, hosting
providers, or third-party tools. Integration needs are described by
function (e.g., "bulk email communication") not by product name.

**One topic at a time.** Discuss and resolve one issue before moving
to the next. When multiple decisions need to be made, present them
sequentially and wait for approval on each.

**Identifiers are assigned during the conversation.** As personas
and domains are established, assign identifiers and confirm them
with the administrator. Identifiers are permanent once assigned.

**No entity mapping.** The Master PRD does not define entities, fields,
or data structures. It defines domains, personas, and processes at a
business level. Entity-level detail comes later in Phase 2.

---

## Before the Interview Begins

### Opening

Introduce the session clearly:

> "Thanks for taking the time for this. The goal of today's session is
> to understand your organization well enough to produce a Master PRD —
> the blueprint document that defines who uses the CRM, what business
> domains it supports, and what processes it needs to handle.
>
> I'll ask questions across several areas. There are no right or wrong
> answers, and if something isn't relevant just say so and we'll move on.
>
> This will take about 60 to 90 minutes. At the end, I'll produce a
> Word document — the Master PRD — that you can share with stakeholders
> for review. Does that sound good?"

### CRM Familiarity Check

Before diving in, establish the administrator's CRM background:

> "Before we start, I want to make sure we're speaking the same
> language. How familiar are you with CRM systems — have you used one
> before?"

**If CRM-experienced:** Acknowledge it and move on.

**If new or rusty:** Briefly explain:
> "A CRM is essentially a structured system for tracking the people,
> organizations, and activities that matter to your work. We'll figure
> out what you need as we talk — you don't need to know the technical
> details, just describe how your organization works and I'll translate
> that into CRM requirements."

---

## Interview Topics

The interview covers six topic areas. The AI should work through all
six but does not need to follow them in strict order — follow the
natural flow of conversation. Use the topic checklist to ensure nothing
is missed before wrapping up.

### Topic Checklist

- [ ] 1. Organization Overview
- [ ] 2. Personas
- [ ] 3. Business Domains and Processes
- [ ] 4. Cross-Domain Services
- [ ] 5. System Scope
- [ ] 6. Constraints and Priorities

---

## Topic 1 — Organization Overview

**What the AI is trying to learn:**
The organization's mission, size, operating model, and why it needs
a CRM. This becomes Section 1 of the Master PRD.

**Opening question:**
> "Let's start with the big picture. Can you describe your
> organization — what you do, who you serve, and roughly how
> large you are?"

**Follow-up probes (use as needed):**
- "What is the organization's mission or core purpose?"
- "Who are the main groups of people your organization works with?"
- "How many staff or volunteers are involved in day-to-day operations?"
- "Do you operate in a single location or across multiple sites?"
- "What prompted the decision to implement a CRM? What problem
  are you trying to solve?"
- "How are things managed today — spreadsheets, email, another
  system, institutional knowledge?"

**Signs you have enough:**
- Clear picture of mission and operating model
- Understanding of scale (people, volume, geography)
- Compelling "why a CRM" narrative
- Sense of what the current pain points are

---

## Topic 2 — Personas

**What the AI is trying to learn:**
The distinct types of people who will interact with or be tracked by
the CRM. Each persona gets an identifier (MST-PER-001, etc.) and an
entry in the Master PRD with three elements:

- **Responsibilities** — bulleted list of what this person does in
  their role (the WHAT, not the HOW)
- **What the CRM Provides** — bulleted list of capabilities the
  system delivers to support that role (stated positively — what
  the CRM gives them, not what's missing without it)
- **Primary Domains** — which Key Business Domains this persona
  participates in

The persona section serves a critical stakeholder review purpose:
stakeholders must be able to read the persona entries and determine
that the CRM will meet the needs of everyone in the organization.
Responsibilities tell them "yes, you understood my job." What the
CRM Provides tells them "yes, the system will support my work."

**Important:** A persona is a role, not a specific person. "Mentor"
is a persona. "John Smith" is not.

**Opening question:**
> "Now let's identify the different types of people in your world.
> I'm looking for distinct roles — the categories of people your
> organization works with, serves, or relies on. Who are they?"

**Follow-up probes (use as needed):**
- "For each role — what is their relationship to the organization?
  Are they staff, volunteers, clients, partners, donors?"
- "What are the key responsibilities of this role? What does this
  person actually do day to day?"
- "What would the CRM need to provide to make this person's work
  easier or more effective?"
- "Are there people who play more than one role? For example,
  someone who is both a volunteer and a donor?"
- "Are there internal roles — administrators, coordinators, managers
  — who use the CRM to manage operations rather than being tracked
  by it?"
- "Who are the external partners or organizations your team works
  with? Do they need visibility into the CRM, or are they just
  tracked as records?"

**For each persona, capture:**
- A clear role name
- Their key responsibilities (what they do — these become the
  Responsibilities bullets)
- What the CRM needs to give them (what capabilities they need —
  these become the What the CRM Provides bullets)
- Which domains they participate in

**As personas are identified, assign identifiers:**
> "So we have our first persona — let's call that MST-PER-001:
> Mentor. The second would be MST-PER-002: Client Contact. Does
> that sound right?"

**Signs you have enough:**
- All distinct roles identified and named
- Each persona has clear responsibilities (bulleted)
- Each persona has clear CRM capabilities needed (bulleted)
- Multi-role situations noted
- Internal vs. external personas distinguished
- Each persona has an assigned identifier and primary domains

---

## Topic 3 — Business Domains and Processes

**What the AI is trying to learn:**
The major functional areas the CRM must support (domains), and within
each domain, the specific business processes that need to be defined.
This is the most important topic — it establishes the scope and
structure for the entire Phase 2 effort.

This topic has two parts: first identify the domains, then drill into
each domain to identify its processes.

### Part A — Identifying Domains

**Opening question:**
> "Now let's talk about the major areas of work your CRM needs to
> support. Think of these as the big buckets of activity — the
> functional areas that have distinct processes, data, and people
> involved. What are the main areas?"

**Follow-up probes (use as needed):**
- "You mentioned [activity]. Is that part of a larger area of work,
  or is it its own distinct domain?"
- "Are there any areas that involve different people or different
  workflows than the others?"
- "Is fundraising or donor management a separate area of work, or
  is it handled as part of something else?"
- "Are there any areas that are important to the organization but
  might be out of scope for the CRM?"

**As domains are identified, assign codes and identifiers:**
> "Let's give each domain a short code for reference. For [domain
> name], I'd suggest [CODE] — that gives us MST-DOM-001: [Domain
> Name] ([CODE]). Does that work?"

Domain codes should be 2–4 uppercase letters that are intuitive
abbreviations. For example: MN for Mentoring, MR for Mentor
Recruitment, CR for Client Recruiting, FU for Fundraising.

### Part B — Identifying Processes Within Each Domain

For each domain identified, drill in to identify the business
processes:

> "Let's look at [Domain Name] more closely. What are the distinct
> processes or workflows within this domain? Think of a process as
> a sequence of steps that starts with a trigger and ends with a
> defined outcome."

**Follow-up probes (use as needed):**
- "Walk me through how [domain activity] works from start to finish.
  What kicks it off? What are the major steps? How does it end?"
- "Are there things that happen in a predictable sequence — one
  step leads to the next? Those are your lifecycle processes."
- "Are there things that happen in response to conditions or events
  — monitoring, alerts, periodic reviews? Those are your
  asynchronous processes."
- "Does anything in this domain depend on something that happens
  in another domain?"

**For each process, capture:**
- A clear name and process code
- A one-line description of what it accomplishes
- Whether it is a sequential lifecycle process or an asynchronous
  process
- Any obvious dependencies on other processes

**Establishing process sequence:**

After all processes in a domain are identified, work with the
administrator to establish the sequence they should be listed in.
The principle is lifecycle processes first (because they establish
core data), then asynchronous processes (because they react to
that data):

> "Based on what you've described, I'd suggest listing the
> processes for [Domain Name] in this order:
> 1. [Process] — creates the initial records
> 2. [Process] — updates status based on [trigger]
> 3. [Process] — adds ongoing data
> 4. [Process] — defines final states
> 5. [Process] — monitors for [condition] (async)
>
> Does that sequence make sense?"

### Part C — Implementation Tier Assignment

After all processes across all domains are identified, assign an
implementation tier to each process. Work through the processes
one at a time, stating the proposed tier and rationale positively
(what the process enables, not what's missing without it).

The four tiers are:

- **Core** — Required for launch. The organization cannot operate
  without this process in the CRM.
- **Important** — Required within 60 days of launch. Operations
  can begin without it but will be constrained.
- **Enhancement** — Valuable but can be deferred to a later phase
  without impacting core operations.
- **Out of Scope** — Identified as a future need but not included
  in this implementation. Documented for completeness and future
  planning.

> "Now let's prioritize. For each process, I'll suggest an
> implementation tier based on what you've told me about what's
> most critical. Let's walk through them one at a time."

For each process, present the tier and a positive business value
statement:

> "[Process Name]: I'd suggest Core — [positive value statement].
> Does that feel right?"

**Important:** State business value positively. Say what the
process enables, not what goes wrong without it. "Gives CBM a
structured path for client intake" not "Without this, client
requests would be lost."

After all tiers are assigned, present a summary table for
confirmation:

> "Here's the full tier assignment across all domains:
>
> Core: [list]
> Important: [list]
> Enhancement: [list]
> Out of Scope: [list]
>
> Does this prioritization look right?"

### Part D — Business Value and Key Capabilities

For each process, capture two additional elements that will appear
in the Master PRD as bulleted lists:

- **Business Value** — why this process matters to the organization,
  stated positively (what it enables, what it provides). These
  become bulleted value statements.
- **Key Capabilities** — the specific capabilities the CRM provides
  to support this process. These become bulleted capability
  statements.

This can be done during the initial process discussion or as a
focused pass after all processes are identified — whichever flows
more naturally in the conversation.

> "For [Process Name], what's the core value this brings to the
> organization? And what specific capabilities does the CRM need
> to provide to support it?"

**Signs you have enough:**
- All domains identified with codes and identifiers
- Each domain has a complete process list
- Each process has a name, code, and one-line description
- Processes are sequenced (lifecycle first, then async)
- Cross-domain dependencies are noted
- Every process has an assigned implementation tier
- Every process has business value statements (bulleted)
- Every process has key capability statements (bulleted)

### Establishing Domain Processing Order

After all domains and their processes are identified, determine
the order in which domains should be processed in Phase 2:

> "Now let's decide which domain to tackle first. The principle is:
> start with the domain that has the most data and the most processes,
> because it establishes the foundation that other domains build on.
>
> Based on what we've discussed, [Domain] seems like the heaviest —
> it has [N] processes and involves [key entities]. I'd recommend
> starting there. Does that make sense?"

---

## Topic 4 — Cross-Domain Services

**What the AI is trying to learn:**
Whether any capabilities discussed during the domain and process
exploration are shared across multiple domains rather than owned by
a single domain. Cross-Domain Services are platform capabilities —
such as Notes, Email, Calendar, or Surveys — that multiple domains
consume but no single domain owns. Services are structurally parallel
to domains: they can own entities, define processes, and produce
their own reconciled Service PRD. But their purpose is to provide
shared capabilities, not to fulfill a standalone business function.

This topic works best after domains and processes have been identified,
because the AI can now look across the domain landscape and spot
capabilities that appeared in more than one domain.

**Opening question:**
> "As we talked through the domains and processes, I noticed some
> capabilities that came up in more than one domain. Before we move
> on, I want to check whether any of those are shared services —
> things like notes, email, calendaring, or surveys — that aren't
> really owned by any one domain but are used across several.
>
> Did anything like that come up, or are there shared capabilities
> your organization relies on that we should call out separately?"

**Follow-up probes (use as needed):**
- "You mentioned [capability] in both [Domain A] and [Domain B].
  Is that something each domain handles independently, or is it
  a shared service that works the same way everywhere?"
- "Are there tools or functions that multiple teams rely on — things
  like a shared notes system, a common email workflow, or a
  calendar integration?"
- "For [capability] — does it have its own data? For example, does
  it create its own records, or does it just add information to
  records that belong to other domains?"
- "Who is responsible for how [capability] works? Is it managed
  centrally, or does each domain configure it independently?"

**For each service, capture:**
- A clear service name (full name, not a short code — e.g.,
  "Notes Service" not "NS")
- Purpose — what shared capability it provides
- Capabilities — the specific functions it offers to consuming
  domains, described in enough detail that a process document
  could reference the service generically (e.g., "Use the Notes
  Service to add notes to a contact")
- Consuming domains — which domains use this service
- Entities it may own — whether the service has its own data
  objects (e.g., a Survey service might own Survey and Survey
  Response entities)

**Distinguishing services from domain processes:**

Not every shared concept is a service. The test is whether the
capability is consumed by multiple domains and has no natural
single owner. If a capability is primarily used by one domain
with occasional use by another, it likely belongs in the primary
domain. If it is genuinely shared — used broadly and managed
centrally — it is a service.

> "Let me check my understanding: [capability] is used by
> [Domain A], [Domain B], and [Domain C], and no single domain
> owns it. That sounds like a Cross-Domain Service. Does that
> feel right, or does it belong more naturally in one domain?"

**Signs you have enough:**
- All shared capabilities identified with clear service names
- Each service has a purpose and capability description
- Consuming domains are identified for each service
- Entities owned by the service are noted (if any)
- Each service description is detailed enough that a domain
  process document could reference it generically without
  knowing internal mechanics
- Clear distinction made between services and domain processes

---

## Topic 5 — System Scope

**What the AI is trying to learn:**
What is in scope and out of scope for the CRM, and what external
integrations are needed. This becomes Section 5 of the Master PRD.

**Opening question:**
> "Let's define the boundaries of this CRM. Based on everything
> we've discussed, I have a sense of what's in scope. Let me
> summarize what I think is in, and you tell me if I'm missing
> anything or including something that should be out."

Present a draft in-scope list based on everything discussed so far,
then probe for boundaries:

**Follow-up probes (use as needed):**
- "Are there any functions we discussed that should explicitly be
  out of scope for this implementation?"
- "Are there other systems the CRM needs to connect with? For
  example, a website, email service, learning platform, or
  financial system?"
- "For each integration — what needs to flow between the systems?
  Just describe the function, not the specific product."
- "Are there any features you know you'll want eventually but
  don't need in the initial implementation?"

**Important:** Describe integrations by function, not by product
name. "Bulk email communication platform" not a specific product.
"Online learning platform" not a specific product.

**Signs you have enough:**
- Clear in-scope list
- Explicit out-of-scope items
- Integration needs described by function
- Future-phase items noted separately

---

## Topic 6 — Constraints and Priorities

**What the AI is trying to learn:**
Timeline, technical constraints, and implementation priorities. This
informs scope decisions but is not a formal section of the Master PRD
— it feeds into the System Scope section's scoping decisions.

**Opening question:**
> "Before we wrap up, let me understand your constraints and
> priorities. What's driving the timeline for this implementation?"

**Follow-up probes (use as needed):**
- "Is there a launch date, grant deadline, or board commitment
  driving the schedule?"
- "If we had to phase the implementation — start with one or two
  domains and add the rest later — which domains are most urgent?"
- "Who will be the primary administrator of the CRM once it's
  live? What is their technical comfort level?"
- "Are there any non-negotiable requirements — things the CRM
  absolutely must do regardless of complexity?"

**Signs you have enough:**
- Timeline constraints identified
- Domain priority understood
- Administrator capability assessed
- Non-negotiable requirements noted

---

## Closing the Interview

### Coverage Check

Before closing, review the topic checklist. For any uncovered topics:
> "I want to make sure I haven't missed anything. We haven't talked
> much about [topic] — is that relevant to your situation, or can
> we skip it?"

### Summary and Confirmation

Summarize the key findings back to the administrator. Present:

1. The personas identified (with identifiers, responsibilities,
   and CRM capabilities)
2. The domains identified (with codes and identifiers)
3. The process list for each domain (with sequence and tiers)
4. The Cross-Domain Services identified (with names, purposes,
   and consuming domains)
5. The implementation tier summary across all domains
6. The recommended domain processing order
7. The system scope (in/out/integrations)

> "Let me summarize what we've established before I produce the
> Master PRD..."

Walk through each item and confirm. This is the last chance to catch
misunderstandings before the document is produced.

### Document Production

After confirmation, produce the Master PRD as a Word document with
the following structure:

1. **Organization Overview** — mission, operating context, why a
   CRM is needed
2. **Personas** — each persona with Responsibilities (bulleted),
   What the CRM Provides (bulleted), and Primary Domains
3. **Key Business Domains** — opens with implementation tier
   definitions and a process tier summary table, then one section
   per domain containing: domain purpose, personas involved,
   business processes (each with one-line description, tier badge,
   business value as bulleted list, key capabilities as bulleted
   list), and key data categories
4. **Cross-Domain Services** — one section per service with service
   name, purpose description, capabilities it provides to domains,
   and any entities it may own
5. **System Scope** — in scope, out of scope, integrations
   described by function

Commit the document to the repository at:
`PRDs/{Implementation}-Master-PRD.docx`

### Next Steps

> "The Master PRD is complete. The next step is Phase 2 — Entity
> Definition. We'll start with an Entity Discovery conversation
> where you upload the Master PRD and we walk through each domain
> and its processes to identify every entity the system needs to
> track. That produces the Entity Inventory.
>
> After that, we'll define each entity one at a time in dependency
> order — foundational entities first, then the entities that
> reference them.
>
> Would you like to start the Entity Discovery conversation now,
> or schedule it for another time?"

---

## Important AI Behaviors During the Interview

**Listen more than you talk.** The goal is to understand the
organization, not to explain CRM concepts. Keep questions short
and give the user space to answer fully.

**Follow threads.** If a user mentions something interesting in
passing, follow up on it before moving on. The most important
information often comes from unexpected directions.

**Tolerate ambiguity.** Not every answer will be clear or complete.
Note ambiguities in the document's open questions rather than
forcing premature resolution.

**Avoid leading questions.** Don't suggest answers. "What activities
do you need to track?" is better than "Do you track mentoring
sessions?"

**Validate understanding.** Periodically reflect back what you've
heard: "So if I understand correctly..." This catches
misunderstandings early.

**Don't over-engineer.** Resist the temptation to propose data
structures or field definitions during the interview. The Master
PRD is a business-level document. Entity and field detail comes
in Phase 2.

**Stay curious.** The best discovery sessions feel like a genuine
conversation between two people trying to solve a problem together.

**Watch for scope discoveries.** If the administrator describes
something that doesn't fit any of the domains being discussed,
flag it immediately rather than trying to force it into an
existing domain. New domains can be added — it's better to
discover them now than during Phase 2.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.2 | 04-03-26 | Added Cross-Domain Services: new Topic 4 interview section, added to Master PRD contents and output structure, added to summary checklist, added to "also establishes" list. Renumbered Topics 4–5 to 5–6. Fixed Next Steps to correctly reference Phase 2 — Entity Definition (was incorrectly pointing to Process Definition). |
| 1.1 | 03-30-26 | Updated persona format (Responsibilities + What the CRM Provides, both bulleted). Added implementation tier system (Core, Important, Enhancement, Out of Scope). Added Business Value and Key Capabilities as bulleted lists per process. Updated document production structure to match. |
| 1.0 | 03-30-26 | Initial release. Replaces discovery-interview.md. |
