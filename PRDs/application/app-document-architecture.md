# CRM Builder — Document Architecture & Requirements Management

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026

---

## 1. Purpose and Scope

This document defines the document architecture used by CRM Builder to
capture, manage, and communicate CRM requirements for an organization.
It covers the hierarchy of documents produced, the identifier scheme
used to uniquely reference requirements and decisions, and the change
management process used to keep stakeholders informed and documents
current.

This document serves two audiences:

- **Administrators** — individuals setting up and managing a CRM
  implementation using CRM Builder. Process and workflow sections are
  written for this audience.
- **Tool Developers** — individuals building and maintaining CRM Builder.
  Implementation notes sections are written for this audience and are
  clearly marked.

CRM Builder produces four levels of documentation for every
implementation. Each level serves a distinct audience and purpose.
Together they form a complete, traceable record of requirements,
decisions, and configuration.

---

## 2. Document Hierarchy

### 2.1 Overview

```
Level 1 — Master PRD
    Audience: Executives, all stakeholders
    Purpose:  What the CRM provides to the organization

Level 2 — Domain PRDs (one per Key Business Domain)
    Audience: Domain stakeholders, administrators
    Purpose:  How each business domain operates and what the CRM supports

Level 3 — Consolidated Design
    Audience: Implementation team
    Purpose:  Single authoritative entity and field definitions across all domains

Level 4 — Verification Spec
    Audience: Technology administrator
    Purpose:  Confirm YAML configuration matches PRD requirements
```

### 2.2 Data Flow

```
Interviews
    → Level 1 Master PRD
    → Level 2 Domain PRDs
          ↓
    Tool maintains Level 3 Consolidated Design
    (conflict detection and resolution during interview process)
          ↓
    Level 3 → YAML program files
          ↓
    YAML → Level 4 Verification Spec
```

### 2.3 Relationship Between Levels

The Master PRD and Domain PRDs are **authored through the interview
process**. They are the source of truth for all requirements. Neither
document is edited directly outside the interview and change management
workflow.

The Consolidated Design is **maintained automatically by the tool** as
Domain PRDs are created and updated. It is reviewed by the
implementation team but never manually authored.

The Verification Spec is **generated from the YAML program files**. It
is used solely to confirm that the YAML faithfully represents what the
PRDs require. It is not a requirements document — it is a QA artifact.

### 2.4 Document Language by Audience

| Document | Audience | Language |
|---|---|---|
| Master PRD | Executives, all stakeholders | Business |
| Domain PRDs | Domain stakeholders, administrators | Business |
| Consolidated Design | Implementation team | Technical |
| Verification Spec | Technology administrator | Technical |

---

## 3. Key Business Domains

### 3.1 Definition

A Key Business Domain is a logical grouping of personas, processes, and
data that collectively support one key business function of the
organization. A domain is defined by function — not by persona type or
data type alone.

A domain may include multiple persona types if those personas
participate in the same business function. Personas that interact with
multiple business functions appear in multiple domains but are defined
once at the Master PRD level.

### 3.2 Identifying Domains

Domains are identified during the Master PRD interview. The interview
explores the organization's core business functions and proposes a
domain structure for review and approval before Domain PRD interviews
begin.

Each domain must satisfy the following criteria:
- It represents a distinct business function with a clear purpose
- It has identifiable personas who participate in that function
- It has data requirements that support that function
- It can be described independently of other domains without losing
  meaning

### 3.3 Domain Codes

Each domain is assigned a short alphabetic code during the Master PRD
interview. Domain codes are used in document identifiers throughout the
implementation.

**Rules for domain codes:**
- 2 to 4 uppercase letters
- Derived from the domain name — meaningful at a glance
- Unique within the implementation
- Fixed at creation — never changed after assignment
- Defined by the administrator during the Master PRD interview

**Examples:**
```
MN    → Mentoring
MR    → Mentor Recruitment
CR    → Client Recruiting
FU    → Fundraising
```

**Reserved codes** — the following codes are reserved by the tool and
may not be used as domain codes:

```
MST   → Master PRD (non-domain items)
CD    → Consolidated Design
VS    → Verification Spec
CHG   → Change Proposals
```

---

## 4. Document Identifier Scheme

### 4.1 Purpose

Every requirement, decision, data item, persona, process, and change
in the system is assigned a unique identifier. Identifiers allow
stakeholders, administrators, and the implementation team to reference
specific items precisely in change proposals, feedback, and discussions.

### 4.2 Format

```
[DOMAIN]-[PROCESS]-[ITEMTYPE]-[SEQ]
```

| Component | Description |
|---|---|
| DOMAIN | Domain code (see Section 3.3) or reserved code |
| PROCESS | Process code — short name of the process (omitted for Master PRD items) |
| ITEMTYPE | Fixed item type code (see Section 4.3) |
| SEQ | Zero-padded sequential number assigned at creation (001, 002, etc.) |

**Examples:**
```
MST-PER-001             → Master PRD, Persona 1
MST-DOM-003             → Master PRD, Domain 3
MN-INTAKE-REQ-003       → Mentoring domain, Intake process, Requirement 3
MR-ONBOARD-DAT-002      → Mentor Recruitment, Onboarding process, Data item 2
CR-EVENTS-DEC-001       → Client Recruiting, Events process, Decision 1
CD-CONTACT-FLD-007      → Consolidated Design, Contact entity, Field 7
CHG-MN-INTAKE-012       → Change Proposal 12, affecting Mentoring Intake
```

### 4.3 Fixed Item Types

Item types are fixed by the tool. They do not vary per implementation.
The following item types are defined:

| Code | Item Type | Used In |
|---|---|---|
| PER | Persona | Master PRD, Domain PRDs |
| DOM | Domain | Master PRD |
| PRC | Process | Domain PRDs |
| REQ | Requirement | Master PRD, Domain PRDs |
| DAT | Data Item | Domain PRDs, Consolidated Design |
| FLD | Field | Consolidated Design |
| ENT | Entity | Consolidated Design |
| DEC | Decision Made | Domain PRDs |
| ISS | Open Issue | Domain PRDs |
| CHG | Change Proposal | Change Management |
| SCO | Scope Item | Master PRD |
| INT | Integration | Master PRD |

> **Note:** Item types are fixed and may only be added through a formal
> change to this architecture document. Additions require a Change
> Proposal against document identifier `MST-SCO-001` (Architecture
> Document Scope).

### 4.4 Process Codes

Process codes are assigned during Domain PRD interviews — one code per
business process within the domain.

**Rules for process codes:**
- 3 to 8 uppercase letters
- Derived from the process name — meaningful at a glance
- Unique within the domain
- Fixed at creation — never changed after assignment

**Examples:**
```
INTAKE      → Client Intake process
MATCH       → Mentor Matching process
ONBOARD     → Mentor Onboarding process
EVENTS      → Events and Workshops process
```

### 4.5 Identifier Stability

Identifiers are **permanent**. Once assigned, an identifier is never
reassigned or renumbered regardless of changes to document structure,
process order, or content. This ensures that references in change
proposals, stakeholder feedback, and external communications remain
valid indefinitely.

If a process, requirement, or data item is removed, its identifier is
marked as deprecated in the system but is never reused.

If new items are added between existing items, they receive the next
available sequential number — they do not cause existing items to
renumber.

---

## 5. Change Management Process

### 5.1 Purpose

The change management process ensures that all modifications to
requirements are tracked, communicated to affected stakeholders, and
recorded with their rationale. It prevents the common failure mode
where requirements evolve informally, leaving stakeholders uncertain
about what the current design is and why it changed.

### 5.2 Change Lifecycle

Every change follows this lifecycle:

```
Change Identified
        ↓
Change Proposal Created (with rationale and affected identifiers)
        ↓
Stakeholders Notified (by domain)
        ↓
Response Deadline Set
        ↓
    ┌───────────────────────────────────────┐
    │                                       │
No Response                            Response Received
    ↓                                       ↓
Approved by                      Approved → Proceed
Non-Response                     Rejected → New Change Proposal
    ↓                            
Proceed                          
        ↓
Consolidated Design Updated (if approved)
        ↓
Domain PRD Decisions Made section updated
        ↓
    ┌─────────────────────────┐
Late Response Received (after deadline)
        ↓
New Change Proposal created to address late feedback
```

### 5.3 Change Proposals

A Change Proposal is a generated document describing one or more
related changes for stakeholder review. Each Change Proposal contains:

- **Change Proposal identifier** — e.g. CHG-MN-INTAKE-012
- **Date issued**
- **Response deadline**
- **Affected domain(s)**
- **Stakeholders notified**
- For each change:
  - Identifier of the item being changed (e.g. MN-INTAKE-REQ-003)
  - Current state — what the requirement or design says now
  - Proposed state — what it will say after the change
  - Rationale — why the change is being proposed
  - Impact — what else is affected by this change

Change Proposals are written in business language. Technical
implementation details are not included.

### 5.4 Delivery Channels

Change Proposals are delivered via two channels:

**Primary — Email/Document**
The tool generates a clean Change Proposal document suitable for
email distribution. The administrator sends this to the relevant
stakeholders. Stakeholders respond by reply email with their
feedback. The administrator records the response in the tool.

**Optional — Online Review**
The Change Proposal email includes a link to an online review page
where the stakeholder can read the proposal and record their
approval or rejection directly. This channel is optional — stakeholders
who prefer email may ignore the link. Responses via either channel
are recorded identically in the system.

### 5.5 Stakeholder Notification

Stakeholders are defined per domain during the Master PRD interview.
When a Change Proposal is issued:

- Stakeholders associated with the affected domain(s) are notified
- Stakeholders not associated with the affected domain are not notified
- If a change affects multiple domains, all stakeholders across all
  affected domains are notified

### 5.6 Response Deadline and Non-Response Approval

Every Change Proposal includes a response deadline set by the
administrator at the time of issue. The deadline is communicated
clearly in the Change Proposal document and email.

If no response is received by the deadline:
- The change is automatically marked **Approved by Non-Response**
- The approval date and deadline are recorded in the change log
- The Consolidated Design is updated to reflect the approved change
- The Domain PRD Decisions Made section is updated accordingly

The non-response approval mechanism allows the implementation team
to proceed with confidence after the deadline without waiting
indefinitely for explicit approval.

### 5.7 Late Responses

A late response is any feedback received after the response deadline
on a change that has been approved by non-response or explicitly
approved.

Late responses do not automatically reopen or reverse an approved
change. Instead:
- The late response is recorded in the change log against the original
  Change Proposal identifier
- A new Open Issue is created in the affected Domain PRD
- The administrator decides whether the late feedback warrants a new
  Change Proposal
- If a new Change Proposal is issued, it references the original
  Change Proposal identifier for traceability

### 5.8 Rejected Changes

If a stakeholder explicitly rejects a proposed change:
- The rejection and any comments are recorded in the change log
- The existing requirement or design remains unchanged
- The administrator determines whether to revise and reissue a new
  Change Proposal or defer the change
- A new Open Issue is created if the underlying need remains unresolved

### 5.9 Change Log

The tool maintains a complete change log for every implementation
containing:
- Every Change Proposal issued, with full content
- All stakeholder responses with timestamps
- Approval status of every change
- Late responses and their disposition

The change log is permanent and append-only. No entry is ever deleted
or modified after recording.

---

## 6. Document Specifications

### 6.1 Level 1 — Master PRD

**Produced by:** Master PRD interview
**Audience:** Executives, all stakeholders
**Purpose:** Define what the CRM provides to the organization

#### Structure

**1. Organization Overview**
- Mission and operating context
- Who the organization serves
- Why a CRM is needed
- Solution summary — what the CRM implementation covers at the
  highest level

**2. Personas**

One entry per persona. Each entry contains:
- Persona name — the label used consistently throughout all documents
- Description — who this person is in the context of the organization
- Relationship to the organization — volunteer, client, staff,
  external partner, funder, etc.
- Primary domain(s) — which domains this persona participates in
- What the CRM provides to them — summary level

The System Administrator persona is defined here but does not appear
prominently in domain sections.

**3. Key Business Domains**

One section per domain. Each section contains:
- Domain purpose — one paragraph definition
- Personas involved — references to Section 2 personas
- Key Processes — one subsection per process containing:
  - Process name and one line description
  - High level requirements — "The system must..." statements
    scoped to this process
- Key Data — major categories of information managed in this domain,
  without field level detail

**4. System Scope**
- In Scope — what this CRM implementation covers
- Out of Scope — what is explicitly not handled by the CRM
- Key Integrations — described generically by function, not by
  product name:
  - Learning Management System
  - Website
  - Email System
  - (additional integrations as applicable)

---

### 6.2 Level 2 — Domain PRD

**Produced by:** Domain PRD interview (one per Key Business Domain)
**Audience:** Domain stakeholders, administrators
**Purpose:** Define how each business domain operates and what the
CRM supports in sufficient detail for a knowledgeable stakeholder
to fully understand all processes, data, and personas in that domain

#### Structure

**1. Domain Overview**
Expands on the one paragraph domain purpose from the Master PRD.
Provides fuller business context for the domain including its
importance to the organization and how it relates to other domains.

**2. Personas**
The personas from the Master PRD that participate in this domain,
with additional detail about their specific role within this domain's
processes.

**3. Business Processes**

One section per process. Each process section contains:

- **Process Purpose and Trigger** — what the process accomplishes
  and what initiates it
- **Personas Involved** — which personas participate and their
  role in this specific process
- **Process Workflow** — what happens, in what order, and what
  decisions are made. Written in narrative form at a level of detail
  sufficient for a knowledgeable stakeholder to follow the process
  end to end
- **System Requirements** — what the CRM must do to support this
  process, stated as "The system must..." statements
- **Process Data** — data the system must have available to execute
  the process (pre-existing data requirements)
- **Data Collected** — data captured as a result of running the
  process (new data created by the process)

**4. Data Reference**
A consolidated view of all data managed in this domain, organized
by entity, with field level detail. Includes field name, type,
whether required, and business purpose.

**5. Decisions Made**
A record of all decisions made during the requirements process for
this domain. Each entry contains:
- Decision identifier
- The decision made
- Rationale
- Date approved
- Change Proposal reference (if the decision resulted from a change)

This section is populated automatically by the tool from approved
Change Proposals and interview decisions. It is never manually authored.

**6. Open Issues**
Unresolved questions that must be answered before implementation
can proceed. Each entry contains:
- Issue identifier
- Description of the unresolved question
- Why it is unresolved
- Who is responsible for resolving it
- Target resolution date

**7. Interview Transcript**
The complete verbatim record of all interview sessions conducted
to produce this Domain PRD. Provides the full audit trail of
questions asked and answers given, enabling stakeholders not
present to review the reasoning behind all requirements and
decisions.

---

### 6.3 Level 3 — Consolidated Design

**Produced by:** Tool (maintained automatically as Domain PRDs are created)
**Audience:** Implementation team
**Purpose:** Single authoritative definition of every entity and
field across all domains, with full traceability to source requirements

This is an internal implementation document. It is not distributed
to stakeholders.

#### Structure

**1. Entity Index**
A summary table of all entities in the system containing:
- Entity name
- Entity type
- Domains that reference this entity
- Current approval status

**2. Entity Definitions**

One section per entity containing:
- Entity name, type, and purpose
- Complete field list as a table with columns:
  - Field identifier
  - Field name
  - Type
  - Required
  - Source domain and process identifier
  - Business rationale
  - Conflict notes (if two domains made competing claims,
    the resolution and approving authority)

**3. Change History**
Every change made to any entity definition, containing:
- Change Proposal identifier
- Date approved
- What changed
- Approval status and method (explicit or non-response)

---

### 6.4 Level 4 — Verification Spec

**Produced by:** Tool (generated from YAML program files)
**Audience:** Technology administrator
**Purpose:** Confirm that YAML configuration matches PRD requirements

This document is a QA artifact, not a requirements document. Its
sole purpose is to allow the administrator to verify that what has
been configured matches what was specified. It is generated after
YAML files are produced and is used for review before go-live.

The Verification Spec structure is defined in feat-doc-generator.md.

---

## 7. Tool Implementation Notes

*This section is written for CRM Builder developers.*

### 7.1 Identifier Assignment

The tool is responsible for assigning all identifiers. Identifiers
are never manually assigned by administrators. The tool must:

- Maintain a registry of all assigned identifiers per implementation
- Assign the next available sequential number within each
  domain/process/itemtype combination
- Prevent reassignment of deprecated identifiers
- Expose identifiers in all UI surfaces where items are displayed

### 7.2 Consolidated Design Maintenance

The tool maintains the Consolidated Design in real time as Domain
PRD interviews proceed. When a Domain PRD interview defines a field:

1. The tool checks the Consolidated Design for an existing field
   with the same name or internal name on the same entity
2. If no conflict — the field is added to the Consolidated Design
   with a reference to the source domain and process identifier
3. If a conflict exists — the tool surfaces the conflict during
   the interview and presents the existing definition for comparison.
   The administrator must either:
   - Adopt the existing definition (no change to Consolidated Design)
   - Propose a modification (creates a Change Proposal)
   - Override with justification (recorded as a Decision)

Nothing pending approval flows into the Consolidated Design or
into YAML generation.

### 7.3 Change Proposal Generation

The tool generates Change Proposal documents in two formats:
- A formatted document suitable for email distribution (.docx or .pdf)
- An online review page accessible via a link included in the
  email distribution

Both formats present identical content. Stakeholder responses via
either channel are recorded identically in the change log.

### 7.4 Decisions Made Automation

The Decisions Made section of each Domain PRD is populated
automatically by the tool. The tool must:

- Record every decision made during interview sessions with
  timestamp and rationale
- Record every approved Change Proposal as a decision with
  the Change Proposal identifier as reference
- Never require the administrator to manually author Decisions Made
  entries

### 7.5 Stakeholder Management

The tool maintains a stakeholder registry per implementation
containing:
- Stakeholder name and contact information
- Domain associations
- Change Proposal history (sent, responded, non-response)

Stakeholder associations are defined during the Master PRD interview
and may be updated at any time via the change management process.

### 7.6 Non-Response Approval Automation

The tool must monitor response deadlines for all open Change
Proposals. When a deadline passes with no response recorded:

- The change status is updated to Approved by Non-Response
- The approval timestamp is recorded
- The Consolidated Design is updated
- The affected Domain PRD Decisions Made section is updated
- The administrator is notified that the deadline has passed
  and the change has been approved

### 7.7 Architecture Document Changes

This document is itself subject to change management. Changes to
the document architecture — including additions to fixed item types,
domain code rules, or process definitions — require a Change Proposal
issued against the architecture document scope identifier.

The tool must maintain a version history of this document and
surface the current version to administrators during onboarding
and interview sessions.

---

*This document defines the governing architecture for all CRM Builder
document production. Individual feature PRDs (feat-prd-creation.md,
feat-doc-generator.md) define the implementation details of specific
tool features within this architecture.*
