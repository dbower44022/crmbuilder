# CRM Builder — PRD Creation & Requirements Management

**Version:** 2.0
**Status:** Draft — Planned Feature
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md, app-document-architecture.md

---

## 1. Purpose

This document defines the requirements for the PRD Creation feature
in CRM Builder — the AI-assisted process of capturing an organization's
CRM requirements, generating the human-readable PRD documents that
describe those requirements, and producing the YAML program files that
deploy them.

PRD Creation addresses the hardest part of any CRM implementation:
translating what an organization does into a well-structured data model.
This feature guides non-technical users through that process using
structured AI-assisted interviews, producing the documentation
stakeholders can review and the configuration files the tool can deploy.

The document architecture, identifier scheme, and change management
process that govern all documents produced by this feature are defined
in `app-document-architecture.md`. This document defines the
interview process and tool behavior specific to PRD Creation.

---

## 2. Status

PRD Creation is a planned feature. The requirements in this document
define the intended behavior. Implementation has not yet begun.

The current tool assumes YAML program files already exist and focuses
on deploying them. PRD Creation adds the upstream capability that
produces those files in the first place.

---

## 3. Core Concept — Requirements First, Configuration Second

CRM Builder produces four levels of documentation for every
implementation. PRD Creation is responsible for producing the first
two levels:

```
Level 1 — Master PRD
    Produced by: Master PRD interview
    Purpose:     What the CRM provides to the organization

Level 2 — Domain PRDs (one per Key Business Domain)
    Produced by: Domain PRD interviews
    Purpose:     How each business domain operates and what
                 the CRM supports

Level 3 — Consolidated Design
    Produced by: Tool (maintained automatically during interviews)
    Purpose:     Single authoritative entity and field definitions

Level 4 — Verification Spec
    Produced by: Documentation Generator (from YAML)
    Purpose:     Confirm YAML matches PRD requirements
```

The PRDs are the source of truth. The Consolidated Design is derived
from the PRDs. The YAML is generated from the Consolidated Design.
The Verification Spec confirms the YAML is correct.

Neither the PRDs nor the Consolidated Design are ever edited directly
outside the interview and change management workflow. Direct editing
breaks the traceability that makes the system reliable.

---

## 4. The Requirements Workflow

PRD Creation supports the first two phases of the CRM Builder workflow:

```
Phase 1 — Master PRD Interview
  AI-assisted interview about the organization
       ↓
  Key Business Domains identified and defined
       ↓
  Personas defined
       ↓
  Master PRD produced
       ↓
Phase 2 — Domain PRD Interviews (one per domain)
  AI-assisted interview for each Key Business Domain
       ↓
  Business processes, requirements, and data defined
       ↓
  Domain PRD produced
  Consolidated Design updated by tool
       ↓
Phase 3 — YAML Generation
  Consolidated Design reviewed and approved
       ↓
  YAML program files generated
       ↓
  Verification Spec generated from YAML
```

Phase 1 establishes the organizational context and domain structure.
Phase 2 defines the detailed requirements for each domain. Phase 3
produces the deployable configuration.

Domain PRD interviews may begin before the Master PRD has received
formal stakeholder approval. Early Domain PRD work serves to validate
and refine the Master PRD. All documents are subject to change
management as defined in `app-document-architecture.md`.

---

## 5. Phase 1 — Master PRD Interview

### 5.1 Purpose

The Master PRD interview gathers enough information about the
organization to produce a complete Master PRD — defining the
organizational context, all personas, all Key Business Domains,
and the system scope.

### 5.2 Interview Topics

The interview covers the following areas in a conversational,
guided format:

- **Organization type** — nonprofit, business, association, etc.
- **Core mission** — what the organization does and for whom
- **Why a CRM is needed** — the problem being solved
- **Personas** — all people who interact with the system, their
  roles, and their relationship to the organization
- **Key Business Domains** — the major functional areas of the
  organization that the CRM must support
- **System scope** — what is in and out of scope for this
  implementation
- **Key integrations** — other systems the CRM must connect to,
  described generically by function

The interview is conversational, not a form. The AI asks follow-up
questions based on the organization's answers and guides the user
toward a complete picture without requiring CRM expertise.

### 5.3 Key Business Domain Identification

A Key Business Domain is a logical grouping of personas, processes,
and data that collectively support one key business function of the
organization. The interview must help the administrator identify
domains that satisfy the following criteria:

- Represents a distinct business function with a clear purpose
- Has identifiable personas who participate in that function
- Has data requirements that support that function
- Can be described independently of other domains without losing
  meaning

For each domain identified, the interview captures:
- Domain name and purpose
- Domain code — a short alphabetic code used in document identifiers
- Personas involved
- Key processes at a summary level
- Key data categories at a summary level

Domain codes are assigned during this interview and are permanent.
See `app-document-architecture.md` Section 3.3 for domain code rules.

### 5.4 Stakeholder Definition

During the Master PRD interview, the administrator defines the
stakeholders for each domain. Stakeholders are the individuals who
receive Change Proposals and provide feedback on requirements for
their domain.

For each stakeholder the tool records:
- Name and contact information
- Domain associations
- Whether they are the designated approver for their domain

Stakeholder definitions are used by the change management process
throughout the life of the implementation.

### 5.5 Output — Master PRD

The Master PRD interview produces a complete Master PRD document.
The structure of the Master PRD is defined in
`app-document-architecture.md` Section 6.1.

The Master PRD is shared with all stakeholders for review using
the change management process defined in
`app-document-architecture.md` Section 5.

---

## 6. Phase 2 — Domain PRD Interviews

### 6.1 Purpose

Each Domain PRD interview produces the detailed requirements
specification for a single Key Business Domain — its business
processes, personas, system requirements, and data. One interview
session per domain.

### 6.2 Interview Topics

For each domain, the interview covers:

**Domain Context**
- Expanded domain purpose and business context
- How this domain relates to other domains
- Personas involved and their specific roles within this domain

**Business Processes**

For each process within the domain:
- Process name and purpose
- What triggers the process
- Personas involved and their role
- Process workflow — what happens, in what order, what decisions
  are made
- System requirements — what the CRM must do to support this process
- Process data — what data must be available to execute the process
- Data collected — what data is captured as a result of the process

**Data Requirements**
- All data entities required by this domain
- Fields required for each entity, with business rationale
- Field types, required status, and allowed values

### 6.3 Native Entity Awareness

The Domain PRD interview is aware of the native entities provided
by the selected CRM platform. Where a domain's data requirements
can be met by extending a native entity rather than creating a
custom one, the interview recommends that approach.

For EspoCRM, native entities include Account, Contact, Lead,
Opportunity, Case, Task, Meeting, Call, Email, and Document.

### 6.4 Conflict Detection

During the Domain PRD interview, the tool continuously checks all
data requirements against the Consolidated Design. If a field or
entity being defined in this domain already exists from a previous
domain interview, the tool surfaces the conflict immediately and
presents the existing definition for comparison.

The administrator must resolve the conflict before the interview
proceeds:
- **Adopt** — use the existing definition without change
- **Modify** — propose a change via the change management process
- **Override** — accept a domain-specific variation with a recorded
  justification

Conflicts are never silently resolved. Every conflict resolution
is recorded in the Consolidated Design with its rationale and
source domain identifiers.

### 6.5 Output — Domain PRD and Consolidated Design Update

Each Domain PRD interview produces two outputs simultaneously:

**A Domain PRD** — a complete requirements document for the domain
written in business language, suitable for review by domain
stakeholders. The structure of the Domain PRD is defined in
`app-document-architecture.md` Section 6.2.

**A Consolidated Design update** — the tool updates the Consolidated
Design with all entities and fields defined during the interview,
with full traceability to the source domain and process identifiers.

Both outputs are produced together. The Domain PRD is never produced
without a corresponding Consolidated Design update, and vice versa.

---

## 7. Interview Interface

### 7.1 Conversational UI

PRD Creation interviews are conducted through a conversational
interface — a structured chat where the AI asks questions, the user
responds, and the AI guides the conversation toward a complete
requirements definition.

The interface must:
- Present one topic at a time to avoid overwhelming the user
- Allow the user to go back and revise earlier answers
- Show what has been captured so far so the user can verify
- Provide examples and explanations when the user is uncertain
- Surface conflicts with the Consolidated Design immediately
  when they are detected

### 7.2 Identifier Assignment

The tool assigns a unique identifier to every item captured during
the interview — every persona, domain, process, requirement, data
item, and decision. Identifiers are assigned automatically and
displayed in the interview UI alongside the item they identify.

The identifier scheme is defined in `app-document-architecture.md`
Section 4. Identifiers are permanent and never reassigned.

### 7.3 Preview Before Commit

Before generating output (Master PRD, Domain PRD, or Consolidated
Design update), the tool presents a summary of what will be produced
and asks for confirmation. The administrator can request changes
before the output is finalized.

### 7.4 Incremental Output

Output is produced incrementally as interviews complete:
- The Master PRD is produced after Phase 1 and can be shared with
  stakeholders before any Domain PRD interviews begin
- Each Domain PRD is produced when that domain's interview is
  complete
- The Consolidated Design is updated continuously throughout all
  Domain PRD interviews

---

## 8. Change Management

All changes to requirements after initial production follow the
change management process defined in `app-document-architecture.md`
Section 5.

The PRD Creation feature is responsible for:
- Providing a UI for the administrator to initiate Change Proposals
- Generating Change Proposal documents for distribution
- Recording stakeholder responses against Change Proposal identifiers
- Updating Domain PRDs and the Consolidated Design when changes
  are approved
- Populating the Decisions Made section of Domain PRDs automatically
  from approved changes
- Monitoring response deadlines and processing non-response approvals

Neither the Master PRD nor any Domain PRD is ever edited directly
outside the change management workflow.

---

## 9. Integration with Deployment

The YAML program files are generated from the Consolidated Design,
not directly from the Domain PRDs. The Consolidated Design is the
single authoritative source for YAML generation.

Once the Consolidated Design has been reviewed and approved:
- YAML program files are generated for each entity
- Files are placed in the project folder's `programs/` directory
- They appear immediately in the Program File panel
- They can be deployed to a CRM instance using the standard
  Validate → Run → Verify workflow
- The Verification Spec is generated from the deployed YAML to
  confirm it matches the PRD requirements

---

## 10. Future Considerations

- **CRM platform awareness** — the interview can tailor its
  recommendations based on the CRM platform already selected,
  suggesting native entities and field types that are well-supported
  on that platform
- **Template library** — common organization types (nonprofits,
  professional associations, service businesses) may benefit from
  starting templates that pre-populate common domains, processes,
  and entities
- **Import from existing PRD** — organizations that have existing
  Word document requirements may want to import them as a starting
  point rather than conducting the full interview from scratch
- **Multi-language support** — conducting interviews and producing
  PRD documents in languages other than English
